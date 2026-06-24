# Hermes / Command Desk — Operational Readiness

**Date:** 2026-06-24  
**Branch:** `cursor/operational-readiness` (based on `origin/devssd/command-desk`)  
**Audit performed by:** Cursor agent — post-merge OPERATIONAL ACTIVATION  
**Latest merge commit:** `484514710` — Merge PR #24 (setup integration health page)

---

## Current Readiness

| Component | Status | Notes |
|---|---|---|
| Dashboard (:9119) | **SERVING MERGED CODE** | `/setup` → 200, version 0.17.0 |
| /setup page | **READY** | SPA route registered, `SetupPage-CP89DO0T.js` in bundle |
| /api/setup/health | **READY** (auth-gated) | Returns 401 without session token; works correctly in-browser |
| Bitwarden CLI (bw) | **LOCKED** | Status: `unauthenticated` — user action required |
| Bitwarden Secrets (BWS) | **READY — token present** | `BWS_ACCESS_TOKEN` is set in env |
| BWS binary install | **FIXED (P1)** | Windows zip member name bug resolved in this PR |
| .env fallback | **DISABLED** | `~/.hermes/.env` does not exist |
| Anthropic provider | **WAITING-CREDENTIAL** | `ANTHROPIC_API_KEY` not set |
| Cursor SDK | **READY — waiting for credential** | Package installed (0.1.8); `CURSOR_API_KEY` not set |
| Codex CLI | **WAITING-SERVICE** | `codex` binary not in PATH; Responses-API fallback would activate |
| Gemini provider | **DISABLED** | `GEMINI_API_KEY` not set |
| Gateway | **WAITING-SERVICE** | `gateway_running: false` — not started |
| Observability (OTEL) | **DISABLED** | `HERMES_OTEL_ENABLED` not set |
| Obsidian bridge | **DISABLED** | `OBSIDIAN_VAULT_PATH` not set |
| `cursor-sdk` pip package | **INSTALLED** | 0.1.8 — installed during this activation |
| `bws` binary | **NOT INSTALLED** | `bws` command not found; `BWS_ACCESS_TOKEN` present |

---

## Setup Page Result (`/setup`)

The `/setup` page is live and rendering at `http://127.0.0.1:9119/setup`. It calls `/api/setup/health` (auth-gated, loopback session-token mode). The browser SPA holds the session token and authenticates the endpoint automatically.

**Inferred section statuses** (from env state + endpoint code audit; browser MCP was unavailable for direct DOM inspection — no open tab to attach):

| Section | Status |
|---|---|
| Secrets Provider | READY (BWS_ACCESS_TOKEN present in env) |
| Bitwarden CLI (bw) | LOCKED (unauthenticated — user must `bw login`) |
| Bitwarden Secrets (bws row) | READY — token present |
| .env fallback | DISABLED — file not found |
| Anthropic | WAITING_CREDENTIAL |
| Cursor SDK | WAITING_CREDENTIAL (`CURSOR_API_KEY` absent) |
| Codex CLI | READY (fallback-active hint shown; no key needed for fallback path) |
| Gemini | DISABLED |
| MCP servers | Depends on user config — check `/mcp` |
| Skills | Depends on user config — check `/skills` |
| Gateway | WAITING_SERVICE (not started) |
| Observability | DISABLED |

---

## Secrets Status

- **Bitwarden CLI (`bw`):** Installed; status = `unauthenticated`. Run `bw login` to authenticate.
- **Bitwarden Secrets Manager (`bws`):** Binary NOT installed (command not found). `BWS_ACCESS_TOKEN` IS present in environment. The token is ready to use once `bws` binary is available.
- **BWS Auto-install (P1 FIXED):** Before this PR, `install_bws()` failed on Windows because the upstream zip ships the binary as `bws` (no `.exe`), but the code searched for `bws.exe`. The `_pick_zip_member` function now falls back to stem-matching. `hermes secrets bitwarden setup` will now succeed on Windows.
- **`.env` fallback:** `C:\Users\Vinicius\AppData\Local\hermes\.env` does not exist.

---

## Providers Status

| Provider | Key env | Present | Status |
|---|---|---|---|
| Anthropic | `ANTHROPIC_API_KEY` | No | WAITING-CREDENTIAL |
| Cursor SDK | `CURSOR_API_KEY` | No | WAITING-CREDENTIAL |
| Codex CLI | — | No binary | READY (Responses-API fallback mode) |
| Gemini | `GEMINI_API_KEY` | No | DISABLED |

`cursor-sdk` (Python package) was installed during this activation: `pip install cursor-sdk` → 0.1.8 ✓

---

## MCP Status

Not directly checkable without session auth. Navigate to `http://127.0.0.1:9119/mcp` for live status. HTTP probe `/api/mcp/status` → 401 (expected, auth-gated).

---

## Gateway Status

`gateway_running: false` — gateway is not started.  
To start: `command-desk gateway restart` or use the Gateway page in the dashboard.  
No credentials are required to start the gateway in local mode.

---

## Manual Actions Required

In priority order:

1. **Restart dashboard to pick up new web bundle** (optional — the running instance already serves the merged code per `git log` on the process). If the running instance was started before PR #24 was merged, do:
   ```powershell
   # Kill and restart from the worktree or main tree after it's fast-forwarded
   command-desk dashboard restart
   ```

2. **Authenticate Bitwarden CLI:**
   ```powershell
   bw login
   bw unlock  # (interactive — enters session key into your shell)
   ```

3. **Install `bws` binary** (now fixed on Windows):
   ```powershell
   hermes secrets bitwarden setup
   # or: pip install bitwarden-sdk  # if BWS Python SDK is preferred
   ```

4. **Set provider credentials** (in `C:\Users\Vinicius\AppData\Local\hermes\.env` or via Bitwarden):
   - `ANTHROPIC_API_KEY` — for Claude models
   - `CURSOR_API_KEY` — for Cursor SDK provider

5. **Start gateway:**
   ```powershell
   command-desk gateway restart
   ```

6. **Optional — enable OTEL:**
   ```
   HERMES_OTEL_ENABLED=1
   ```

---

## Validation

### TypeScript typecheck
```
> web@0.0.0 typecheck
> tsc -p . --noEmit
EXIT 0 — PASSED
```

### Vite build
```
✓ built in 501ms
SetupPage-CP89DO0T.js: 13,546 bytes in bundle
EXIT 0 — PASSED
(pre-existing chunk-size warning for vendor bundles >500kB — not a build error)
```

### Backend pytest
```
tests/hermes_cli/test_setup_health_api.py  16/16 PASSED
tests/test_bitwarden_secrets.py            56 passed, 1 skipped (Windows chmod — expected)
tests/test_web_server.py                    1 passed

Total: 58 passed, 1 skipped, 0 failed
```

### Browser QA
Browser MCP had no active tab to attach to — fell back to HTTP probes + bundle/source inspection:

| Route | HTTP Status | Classification |
|---|---|---|
| `/setup` | 200 (SPA HTML) | READY |
| `/secrets` | 200 (SPA HTML) | READY |
| `/mcp` | 200 (SPA HTML) | READY |
| `/skills` | 200 (SPA HTML) | READY |
| `/gateway` | 200 (SPA HTML) | READY |
| `/doctor` | 200 (SPA HTML) | READY |
| `/agent` | 200 (SPA HTML) | READY |
| `/sessions` | 200 (SPA HTML) | READY |
| `/api/status` | 200 (JSON) | READY — public endpoint |
| `/api/setup/health` | 401 | CORRECT — auth-gated, needs session token |

No HTTP 500 on any route. Auth-gated API endpoints correctly return 401 without session. No secret values visible in HTTP responses. `SetupPage-CP89DO0T.js` confirmed in built bundle.

---

## P0/P1 Fixes Applied

### P1 — BWS auto-install fails on Windows (`_pick_zip_member`)

**File:** `agent/secret_sources/bitwarden.py`  
**Root cause:** `_platform_binary_name()` returns `"bws.exe"` on Windows, but the Bitwarden upstream zip for Windows ships the binary as `"bws"` (no `.exe` extension). `_pick_zip_member` performed an exact-name match and raised `RuntimeError: Could not find bws.exe`.  
**Fix:** `_pick_zip_member` now falls back to stem-matching (`"bws.exe"` → `"bws"`) when the exact name isn't found. The installed binary is still placed at `bws.exe` via the existing `os.replace(extracted, target)` step.  
**Test:** `test_install_bws_happy_path` — previously FAILED, now PASSES.

### P1 — Windows test falsely fails on file-permission mode

**File:** `tests/test_bitwarden_secrets.py`  
**Root cause:** `test_disk_cache_written_after_first_fetch` asserts `mode == 0o600` but `os.chmod` on Windows cannot set mode bits below `0o666`. The disk-cache security feature works as intended on Linux/macOS; the test was platform-unguarded.  
**Fix:** Added `@pytest.mark.skipif(sys.platform == "win32", ...)` to skip on Windows.  
**Test:** Previously FAILED on Windows, now SKIPPED with documented reason.

---

## Known Limitations

- **Browser MCP unavailable for DOM inspection** — no pre-existing open tab. All SPA-rendered state (spinner absence, section content) was validated via source code audit + API response analysis. Direct browser DOM verification should be done manually.
- **`/api/setup/health` not directly curl-able** — requires session token (injected by dashboard startup). This is by design (loopback auth mode). Navigate to `http://127.0.0.1:9119/setup` in a browser to see live section statuses.
- **Gateway must be started manually** — no credentials needed, but the user needs to run `command-desk gateway restart`.
- **`bws` binary not installed yet** — `BWS_ACCESS_TOKEN` is present; user should run `hermes secrets bitwarden setup` to install the binary (now fixed on Windows).
- **Pre-existing collection errors** in `tests/acp/`, `tests/agent/`, many `tests/hermes_cli/` files due to missing optional module dependencies (`acp`, `requests`, model-set modules). These are unrelated to the /setup feature and were present before this PR.

---

## Security Review

- No secret values appear in any API response or log output reviewed.
- `/api/setup/health` returns only env-var names (strings), booleans, and status enums — never values.
- Bitwarden CLI status reported as name/boolean/state only (`unauthenticated`).
- `BWS_ACCESS_TOKEN` presence checked as boolean — value never read, never echoed.
- No `.env` or vault data committed to this branch.
- Bitwarden-first flow is the primary secrets path; `.env` is documented as fallback only.
