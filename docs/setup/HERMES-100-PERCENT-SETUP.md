# Hermes Full Orchestration Setup — Readiness Checklist

> Updated: 2026-06-24 (Phase 1 BUILD/VALIDATE)
> Branch: `cursor/hermes-full-orchestration-setup`

---

## Summary

Phase 0 inventory confirmed that most Hermes subsystems already exist and are
production-grade.  Phase 1 validated them (test runs), built the 3 genuine
gaps, and confirmed frontend health.

---

## Readiness Checklist

### Core runtime

| Subsystem | Status | Action required |
|---|---|---|
| Bitwarden/BWS secrets (fail-open) | ✅ READY | `bws` auto-installs on first use; set `BWS_ACCESS_TOKEN` in `~/.command-desk/.env` |
| `bw` CLI | 🔒 UNAUTHENTICATED | `bw` is unauthenticated (expected — Hermes uses `bws`, not `bw`) |
| Codex Responses-API fallback | ✅ READY | Fallback path confirmed in `codex_runtime.py`; Codex CLI absent is expected |
| Subprocess + HOME isolation | ✅ READY | 3 Windows-only pre-existing test failures (not regressions) |
| Smart model routing | ✅ READY | — |
| Iteration budget | ✅ READY | — |
| Usage pricing + credits tracker | ✅ READY | — |
| Billing view | ✅ READY | — |
| ACP server (`acp_adapter/server.py`) | ✅ READY | — |
| Stream diagnostics | ✅ READY | — |
| Trajectory save/load | ✅ READY | — |

### Gaps (newly built)

| Subsystem | Status | Action required |
|---|---|---|
| **Cursor SDK adapter** (`agent/cursor_adapter.py`) | ⚡ READY-WAITING-CREDENTIAL | `pip install cursor-sdk` + set `CURSOR_API_KEY` |
| **Obsidian context bridge** (`agent/obsidian_context.py`) | ✅ READY | Set `OBSIDIAN_VAULT_PATH` (optional, has default) |
| **OTEL exporter** (`agent/otel_exporter.py`) | ✅ READY (default-off) | `pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http` + `HERMES_OTEL_ENABLED=1` to activate |

### Frontend

| Check | Status |
|---|---|
| `npm run typecheck` | ✅ PASS |
| `npm run build` | ✅ PASS |

---

## Credential / Installation Actions

```powershell
# 1. Cursor SDK — REQUIRED for live Cursor agent dispatch
pip install cursor-sdk
# Set in ~/.command-desk/.env or Bitwarden:
#   CURSOR_API_KEY=cursor_<your-key>

# 2. OTEL — OPTIONAL, default-off
pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
# Enable: HERMES_OTEL_ENABLED=1

# 3. bws — AUTO, no manual step
# Hermes lazy-installs bws into <hermes_home>/bin/ on first use.
# Requires: BWS_ACCESS_TOKEN in ~/.command-desk/.env

# 4. Obsidian — OPTIONAL default
# Set: OBSIDIAN_VAULT_PATH if vault is not at ~/Documents/Obsidian
```

---

## Test results summary

| Suite | Pass | Fail | Notes |
|---|---|---|---|
| `test_cursor_adapter.py` | 17 | 0 | New — all pass |
| `test_obsidian_context.py` | 19 | 0 | New — all pass |
| `test_otel_exporter.py` | 19 | 0 | New — all pass |
| `test_bitwarden_secrets.py` | 58 | 2 | Pre-existing Windows failures |
| `test_subprocess_home_isolation.py` | 65 | 1 | Pre-existing Windows failure |
| `test_env_loader_secret_sources.py` | 8 | 0 | — |
| `test_account_usage.py` | 4 | 0 | — |
| `test_hermes_constants.py` | 65 | 2 | Pre-existing Windows failures |
| `acp_adapter/test_detect_provider_entra.py` | 5 | 0 | — |

---

## Docs written (this cycle)

- `docs/setup/HERMES-TARGET-ARCHITECTURE.md` — validated target arch + EXISTS vs BUILT
- `docs/setup/HERMES-CURSOR-SDK.md` — Cursor SDK adapter usage + credential status
- `docs/setup/HERMES-OBSIDIAN-CONTEXT.md` — read-only vault bridge
- `docs/setup/HERMES-OTEL-EXPORTER.md` — OTEL exporter config + security
- `docs/setup/HERMES-100-PERCENT-SETUP.md` — this file (readiness checklist)
