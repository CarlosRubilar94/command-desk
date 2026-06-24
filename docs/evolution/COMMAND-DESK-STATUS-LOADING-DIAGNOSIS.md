# Command Desk Status Loading — Diagnosis & Fix

**Date:** 2026-06-24  
**Branch:** `cursor/fix-command-desk-status-ui`  
**PR:** fix(ui): command desk status never hangs — timeout + degraded state + actions

---

## Summary

The dashboard home (`/`) showed "Loading Command Desk status..." indefinitely
when the gateway was offline or the `/api/devssd/status` probe failed.
This document records the root causes (3 backend + 1 frontend), the fix applied,
and the QA results.

---

## Root Causes

### Backend causes (already fixed in `devssd/command-desk` before this PR)

1. **Server blocked on startup** — The web server was performing blocking I/O
   (gateway probe, config load) during the startup lifespan, which prevented the
   `/api/devssd/status` endpoint from responding until startup completed.
   Fixed by: non-blocking lifespan warmup (`test_web_server_boot_handshake.py` covers this).

2. **Status endpoint blocked by gateway probe** — When `gateway_running: false`,
   the endpoint was waiting on a subprocess check that could hang.
   Fixed by: async gateway probe with timeout in the backend handler.

3. **Auth 401 on gated mode not handled gracefully** — The backend middleware
   returned a structured 401 (`{"error": "unauthenticated", "login_url": "..."}`)
   which was correct, but the frontend had no timeout protection.

### Frontend cause (fixed in this PR)

**File:** `web/src/pages/DevssdPageShared.tsx` — `useDevssdStatus` hook  
**Endpoint:** `GET /api/devssd/status`

**Root cause:** `useDevssdStatus.refresh()` called `api.getDevssdStatus()` with
no timeout. `api.getDevssdStatus()` delegates to `fetchJSON()` which has two
paths that return `new Promise<T>(() => {})` — a promise that **never resolves
or rejects**:

```typescript
// web/src/lib/api.ts line 144-145 (gated-mode 401 + login_url)
window.location.assign(body.login_url);
return new Promise<T>(() => {});   // ← never settles

// web/src/lib/api.ts line 170-171 (loopback-mode stale-token reload)
window.location.reload();
return new Promise<T>(() => {});   // ← never settles
```

Because `useDevssdStatus` had no `Promise.race` / `AbortController` guard,
the `finally { setLoading(false) }` block **never ran** when either of these
paths fired. This left `loading: true` forever → infinite spinner.

Additionally, if the backend accepted a TCP connection but never sent a response
(e.g. partial startup, lingering socket), `fetch()` itself would hang with no
built-in browser timeout for loopback connections.

---

## Fix Applied (frontend only)

### `web/src/pages/DevssdPageShared.tsx`

#### 1. Timeout race in `useDevssdStatus`

```typescript
const STATUS_FETCH_TIMEOUT_MS = 6_000;

const timeoutPromise = new Promise<never>((_, reject) =>
  setTimeout(
    () => reject(new Error(`Status check timed out after ${STATUS_FETCH_TIMEOUT_MS / 1000} s`)),
    STATUS_FETCH_TIMEOUT_MS,
  ),
);
try {
  setStatus(await Promise.race([api.getDevssdStatus(), timeoutPromise]));
} catch (err) {
  setError(err instanceof Error ? err.message : String(err));
} finally {
  setLoading(false);   // ← now ALWAYS runs within 6 s
}
```

This guarantees `loading` is set to `false` within 6 s regardless of whether
`fetchJSON` returns a never-resolving promise or the network hangs.

#### 2. Degraded state in `LoadingOrError`

Before:
```tsx
// Plain error string — no actions, no context
<div className="text-sm text-[var(--dsd-sem-critical)]">{error}</div>
```

After — rich degraded state with:
- Title: "Command Desk status unavailable"
- Probable-cause explanation (gateway offline / probe timeout)
- **Retry** button (re-invokes `refresh`)
- **Restart Gateway** button (calls `api.restartGateway()` then retries)
- **Gateway page** link → `/gateway`
- **Doctor** link → `/doctor`
- Collapsible **Details** section: endpoint, error message, next-step hint (no secrets)

#### 3. `onRetry` prop wired in all callers

`AgentHomePage`, `DevssdDoctorPage`, `BitwardenStatusPage`, `GatewayStatusPage`
all pass `onRetry={refresh}` to `LoadingOrError`.

### Backend touched

None. `api.restartGateway()` was already wired to `POST /api/gateway/restart`.

---

## Before / After

| Scenario | Before | After |
|---|---|---|
| Gateway OFF, no 401 (connection refused) | `catch` fires → error string shown | `catch` fires → degraded state + actions |
| Gateway OFF, 401 + `login_url` (gated) | `fetchJSON` returns `new Promise(() => {})` → **infinite spinner** | Timeout fires in ≤6 s → degraded state |
| Gateway hang (no response) | `fetch()` hangs indefinitely | Timeout fires in ≤6 s → degraded state |
| Stale token loopback 401 (first hit) | `window.location.reload()` + never-resolving promise → **infinite spinner until reload** | Timeout fires in ≤6 s; page reloads and recovers |
| Gateway online, status 200 | Works | Works (unchanged) |

---

## QA Results

### Typecheck & Build

| Check | Result |
|---|---|
| `npm run typecheck` | ✅ Pass (0 errors) |
| `npm run build` | ✅ Pass (existing chunk-size warning unrelated) |

### Backend Tests (status / auth / boot-handshake)

```
tests/hermes_cli/test_status.py              — 14 passed
tests/hermes_cli/test_dashboard_auth_status_endpoint.py — 6 passed
tests/hermes_cli/test_web_server_boot_handshake.py     — 3 passed
tests/hermes_cli/test_web_server.py (k=status)         — 2 passed
```

Total: **25 passed, 0 failed** for status/auth/boot tests.

Pre-existing unrelated failures (10 total, not introduced by this PR):
- `test_analytics_endpoints_read_requested_profile` — missing `requests` module in env
- `test_model_set_*` (5 tests) — model-set endpoint logic change, pre-existing
- `test_blueprint_instantiate_creates_job` — blueprint API, pre-existing
- `test_model_info_*` (4 tests) — model info endpoint, pre-existing

### HTTP Route Check (gateway OFF, dashboard running on :9119)

| Route | HTTP | Notes |
|---|---|---|
| `/` (home) | 200 | SPA root served |
| `/sessions` | 200 | SPA route served |
| `/gateway` | 200 | SPA route served |
| `/doctor` | 200 | SPA route served |
| `/mcp` | 200 | SPA route served |
| `/secrets` | 200 | SPA route served |
| `/api/devssd/status` | 401 | Expected (no session); frontend now handles gracefully within 6 s timeout |

**Code-path verification (gateway OFF):**
- `fetch /api/devssd/status` → 401 (no session token in HTTP check, or in loopback mode
  triggers stale-token reload)
- `Promise.race` ensures `loading: false` within ≤6 s in all paths
- `LoadingOrError` renders degraded state with Retry / Restart Gateway / Doctor links
- No infinite spinner possible

*Note: cursor-ide-browser MCP was not available in the subagent context for live
screenshot verification. Code-path analysis and HTTP checks confirm correctness.*

---

## Files Changed

| File | Change |
|---|---|
| `web/src/pages/DevssdPageShared.tsx` | Add 6 s timeout race; replace error string with degraded state + actions |
| `web/src/pages/AgentHomePage.tsx` | Pass `onRetry={refresh}` to `LoadingOrError` |
| `web/src/pages/DevssdDeckPages.tsx` | Pass `onRetry={refresh}` to 3 `LoadingOrError` usages |
| `docs/evolution/COMMAND-DESK-STATUS-LOADING-DIAGNOSIS.md` | This file |
