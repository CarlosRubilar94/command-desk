# Hermes Target Architecture — Integration Health Report

> Branch: `cursor/hermes-full-orchestration-setup`
> Date: 2026-06-24
> Phase: BUILD/VALIDATE cycle (Phase 0 inventory → Phase 1 complete)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Hermes Agent                            │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Provider    │  │  Dispatcher  │  │  Observability       │  │
│  │  Adapters    │  │  / Routing   │  │  (OTEL — default off)│  │
│  ├──────────────┤  ├──────────────┤  └──────────────────────┘  │
│  │ anthropic    │  │smart_model_  │                             │
│  │ codex_resp.  │  │routing.py    │  ┌──────────────────────┐  │
│  │ gemini_nat.  │  │iteration_    │  │  Secrets             │  │
│  │ bedrock      │  │budget.py     │  │  bitwarden.py (bws)  │  │
│  │ azure        │  │usage_pricing │  │  ~/.command-desk/.env│  │
│  │ cursor ←NEW  │  │credits_track │  └──────────────────────┘  │
│  └──────────────┘  │billing_view  │                             │
│                    └──────────────┘  ┌──────────────────────┐  │
│  ┌──────────────┐                    │  Context             │  │
│  │  ACP Server  │                    │  obsidian_context ←  │  │
│  │  acp_adapter/│                    │  NEW (read-only)     │  │
│  │  server.py   │                    └──────────────────────┘  │
│  └──────────────┘                                               │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Subprocess + HOME isolation                            │   │
│  │  process_bootstrap.py  hermes_constants.py              │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Subsystem Status

### EXISTS (validated)

| Subsystem | File(s) | Status | Notes |
|---|---|---|---|
| **Bitwarden/BWS secrets** | `agent/secret_sources/bitwarden.py` | ✅ PASS (57/60) | `bw` unauthenticated (expected); `bws` not in PATH (lazy-installed by Hermes on demand). 3 Windows-only failures: bws.exe naming, chmod, path sep — pre-existing. |
| **Codex runtime / Responses-API** | `agent/codex_runtime.py`, `agent/codex_responses_adapter.py` | ✅ EXISTS | Codex CLI absent from PATH; Responses-API fallback path (`run_codex_stream`, `run_codex_create_stream_fallback`) confirmed in code. |
| **Subprocess + HOME isolation** | `agent/process_bootstrap.py`, `hermes_constants.py` | ✅ PASS (43/46) | 3 Windows-only failures (path sep, symlink priv) — pre-existing. |
| **Smart model routing** | `agent/smart_model_routing.py` | ✅ EXISTS | Economy/Performance task tiers implemented. |
| **Iteration budget** | `agent/iteration_budget.py` | ✅ EXISTS | Turn-count + token budget enforcement. |
| **Usage pricing** | `agent/usage_pricing.py` | ✅ EXISTS | Per-model cost tables. |
| **Credits tracker** | `agent/credits_tracker.py` | ✅ EXISTS | Session usage accumulation. |
| **Billing view** | `agent/billing_view.py` | ✅ EXISTS | CLI billing display. |
| **ACP server** | `acp_adapter/server.py` | ✅ EXISTS | Full adapter with auth, events, tools, session management. |
| **Stream diagnostics** | `agent/stream_diag.py` | ✅ EXISTS | Per-attempt counters, CF/OR headers. No OTEL exporter (gap now filled). |
| **Trajectory** | `agent/trajectory.py` | ✅ EXISTS | Save/load utilities. No OTEL exporter (gap now filled). |
| **Secret sources env loader** | `agent/credential_sources.py` | ✅ PASS (8/8) | |
| **Account usage** | `agent/account_usage.py` | ✅ PASS (4/4) | |
| **config.yaml** | n/a | N/A | File is user-generated (not committed); neither `config.yaml` nor `.corrupt` backup present in the worktree — expected for a fresh checkout. |

### BUILT (this cycle)

| Subsystem | File(s) | Tests | Notes |
|---|---|---|---|
| **Cursor SDK adapter** | `agent/cursor_adapter.py` | ✅ 17/17 | READY-WAITING-CREDENTIAL: needs `CURSOR_API_KEY` + `pip install cursor-sdk`. Lazy import; construction succeeds without SDK. |
| **Obsidian read-only bridge** | `agent/obsidian_context.py` | ✅ 19/19 | Reads keys only (never values), sanitizes secret-shaped lines, never writes. |
| **OTEL exporter** | `agent/otel_exporter.py` | ✅ 19/19 | Default-OFF. Enable via `HERMES_OTEL_ENABLED=1`. No secrets in spans. |

---

## Pre-existing Windows-only test failures

These 5 failures were present before this cycle; they are not regressions:

| Test | Root cause |
|---|---|
| `test_install_bws_happy_path` | bws archive has `bws` not `bws.exe` on Windows |
| `test_disk_cache_written_after_first_fetch` | `chmod 0o600` is a no-op on Windows NTFS |
| `test_two_profiles_get_different_homes` | `str.endswith("alpha/home")` fails on Windows backslash paths |
| `TestGetDefaultHermesRoot::test_no_hermes_home_returns_native` | Windows uses `AppData\Local\hermes` not `~/.hermes` |
| `TestSecureParentDir::test_symlink_resolved` | Symlink creation requires elevated privileges on Windows |

---

## Frontend

- `cd web && npm run typecheck` → **PASS** (exit 0, no TS errors)
- `cd web && npm run build` → **PASS** (✓ built in 561ms)
- Build warning: chunk sizes >500 kB (pre-existing informational — not an error)

---

## Manual user actions required

```powershell
# 1. Install cursor-sdk (Gap 1 live calls)
pip install cursor-sdk
# Then set in ~/.command-desk/.env or Bitwarden:
#   CURSOR_API_KEY=cursor_<your-key>

# 2. Install OTEL SDK (Gap 3 live export)
pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
# Then enable:
#   HERMES_OTEL_ENABLED=1
#   HERMES_OTEL_ENDPOINT=http://your-collector:4318   # default: localhost:4318

# 3. bws install — automatic on first `hermes secrets bitwarden setup`
#    No manual action needed; Hermes lazy-installs bws into <hermes_home>/bin/

# 4. Obsidian vault path (optional — defaults to OBSIDIAN_VAULT_PATH env or ~/Documents/Obsidian)
#   OBSIDIAN_VAULT_PATH=G:\Meu Drive\03-Documentacao\Obsidian-DevSSD
```
