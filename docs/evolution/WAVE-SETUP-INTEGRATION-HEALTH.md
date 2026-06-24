# Wave: Setup / Integration Health Page

**Route:** `/setup`  
**Nav label:** "Integration Health"  
**PR:** Add Setup / Integration Health dashboard  
**Branch:** `cursor/setup-integration-health`  
**Base:** `devssd/command-desk` (includes PRs #17/#18/#20/#22/#23)

---

## What it shows

A read-only, single-page aggregation of every Hermes integration — visible immediately even when the gateway is offline (uses the PR #23 degraded-state pattern with Retry/Restart actions).

### 7 Sections

| # | Section | Status computation | Status values |
|---|---------|-------------------|---------------|
| 1 | **Secrets Provider** | `bw status` (read-only); `BWS_ACCESS_TOKEN` env name; `.env` file exists check | READY / LOCKED / WAITING_CREDENTIAL / DISABLED |
| 2 | **Model Providers** | Env var name presence (bool only): `ANTHROPIC_API_KEY`, `CURSOR_API_KEY`, `GEMINI_API_KEY`; Codex: `shutil.which("codex")` | READY / WAITING_CREDENTIAL / DISABLED |
| 3 | **MCP Servers** | Aggregated from `_get_mcp_servers` + `_resolve_server_status` (counts by chip) | READY / WAITING_CREDENTIAL / FAILED / DISABLED |
| 4 | **Skills** | `_setup_skill_counts`: active vs disabled vs total | READY / DISABLED |
| 5 | **Gateway** | `_resolve_gateway_liveness()` → running bool + state string | READY / WAITING_SERVICE |
| 6 | **Observability** | `HERMES_OTEL_ENABLED` env (bool), `OBSIDIAN_VAULT_PATH` env (bool) | READY / DISABLED |
| 7 | **Summary bar** | Counts + readiness % across all section statuses | Visual progress bar |

### Readiness %

```
readiness_pct = round(ready_count / total_items * 100)
```

Items counted: `secrets` + each `provider` entry + `mcp` + `skills` + `gateway` + `observability` = 9 items (4 providers + 5 sections).

---

## Backend: `GET /api/setup/health`

Added in `hermes_cli/web_server.py`, after the `/api/mcp/control-center` endpoint.

**Security contract:**
- Returns ONLY: env-var **names**, **booleans**, and **status enum strings**
- Secret values NEVER included (same contract as `_redact_mcp_env`)
- Bitwarden: `bw status` ONLY — no `bw unlock` / `bw login` calls
- Provider keys: `os.environ.get(name, "") != ""` → `True/False`

**Response shape:**
```json
{
  "secrets": { "status": "READY|LOCKED|WAITING_CREDENTIAL", "bw_cli_available": bool, "bw_locked": bool, "bws_token_env": "BWS_ACCESS_TOKEN", "bws_token_present": bool, "env_fallback_exists": bool, "hint": null | "..." },
  "providers": [{ "name": "...", "key_env": "...", "key_present": bool, "status": "...", "hint": null | "..." }],
  "mcp": { "status": "...", "total": int, "ready": int, "waiting": int, "disabled": int, "failed": int, "hint": null | "..." },
  "skills": { "status": "...", "active": int, "disabled": int, "total": int, "hint": null | "..." },
  "gateway": { "status": "...", "running": bool, "state": "running|stopped|...", "hint": null | "..." },
  "observability": { "status": "...", "otel_enabled": bool, "otel_env": "HERMES_OTEL_ENABLED", "obsidian_bridge_status": "...", "hint": null | "..." },
  "summary": { "ready": int, "waiting_credential": int, "waiting_service": int, "failed": int, "disabled": int, "total": int, "readiness_pct": int }
}
```

---

## Frontend: `SetupPage.tsx`

- Path: `web/src/pages/SetupPage.tsx`
- Lazy-loaded via `App.tsx` (same pattern as all other pages)
- Reuses: `DeckCard`, `DeckBtn`, `DeckBtnLink`, `Badge` with McpPage status chip patterns
- Degraded state (gateway OFF / timeout): mirrors PR #23 `DevssdPageShared.tsx` — no infinite spinner, Retry + Restart + Doctor links

---

## QA Table — Gateway OFF

Tested with gateway stopped (backend up, `/api/setup/health` unreachable):

| Check | Result |
|-------|--------|
| `/setup` loads without infinite spinner | ✅ Shows degraded card within 6 s timeout |
| No console-fatal errors | ✅ |
| No secrets in DOM | ✅ (NEVER rendered — only names/booleans) |
| No secrets in network response | ✅ Backend enforces at source |
| Retry button visible | ✅ |
| Restart Gateway button visible | ✅ |
| Doctor link works | ✅ → `/doctor` |
| `/mcp` still loads | ✅ (independent page) |
| `/secrets` still loads | ✅ (independent page) |
| `/doctor` still loads | ✅ (independent page) |

---

## Validation

- `npm run typecheck` → **0 errors**
- `npm run build` → **✓ built** (pre-existing chunk size warnings unrelated)
- `python -m pytest tests/hermes_cli/test_setup_health_api.py -v` → **16/16 passed**
- `python -m pytest tests/hermes_cli/test_setup_health_api.py tests/hermes_cli/test_mcp_control_center.py tests/hermes_cli/test_status.py tests/hermes_cli/test_mcp_config.py -v` → **95/95 passed**

---

## Security

- **No secrets in DOM or API response** — only env var names (strings) and boolean presence flags
- **Bitwarden: read-only** — only `bw status` called; never `bw unlock`, `bw login`, or any vault-read
- **No .env content read** — only checks file existence (`Path.is_file()`) and var presence bool
- **Redaction**: inherits `_redact_mcp_env` / `_bw_status` patterns from existing MCP control-center

---

## Cross-PR conflict risk

**Shared files modified:**
- `web/src/App.tsx` — added lazy import + route + nav entry (low risk; additive)
- `web/src/lib/api.ts` — appended types + `getSetupHealth` method (low risk; additive)
- `hermes_cli/web_server.py` — inserted endpoint block after line 9447 (low risk; insertion after MCP endpoint)

**Not touched:** dispatcher, subprocess manager, Cursor/Codex adapters, ACP server, MAIN working tree.
