# Hermes / Command Desk — Phase 0 Install Inventory

> Generated: 2026-06-23  
> Repo: `C:\Users\Vinicius\Documents\Codex\command-desk`  
> Branch: `cursor/hermes-full-orchestration-setup`  
> Dashboard (Desk): `http://127.0.0.1:9119`  
> Command Deck (ops UI): `http://127.0.0.1:8765`

---

## 1. Tooling Inventory

| Tool | Version | Path |
|------|---------|------|
| Python | 3.12.10 | `C:\Users\Vinicius\AppData\Local\Programs\Python\Python312\python.exe` |
| Node.js | 24.16.0 | `C:\Program Files\nodejs\node.exe` |
| npm | 11.13.0 | `C:\Program Files\nodejs\npm.cmd` |
| Git | 2.54.0.windows.1 | `C:\Program Files\Git\cmd\git.exe` |
| Bitwarden CLI (`bw`) | 2026.5.0 | `C:\Users\Vinicius\AppData\Local\Microsoft\WinGet\Packages\…\bw.exe` |
| Claude Code (`claude`) | 2.1.183 | `C:\Users\Vinicius\.local\bin\claude.exe` |
| Cursor CLI (`cursor`) | 3.8.22 (46fb7aafe) | `C:\Users\Vinicius\AppData\Local\Programs\cursor\…\cursor.cmd` |
| Codex CLI | **ABSENT** — `where.exe codex` → not found | — |

**bw status**: `{"status":"unauthenticated","serverUrl":null,"lastSync":null}` — vault is **unauthenticated** (not just locked; no server configured via `bw` CLI). Note: Hermes uses `bws` (Bitwarden Secrets Manager CLI), not `bw`. `bws` is auto-installed into `~/.command-desk/bin/` at first use.

---

## 2. Repository / Codebase Map

### Git situation

- `command-desk/` — **git repo**, branch `cursor/fix-missions-navigate-scope` (before phase-0 branch creation)
- `control-center/` — **NOT a git repo** (standalone Node.js project, no `.git`)
- No git repo exists at `C:\Users\Vinicius\Documents\Codex\` root level

### Command Desk repo (`command-desk/`) — Python/TypeScript hybrid

**Backend**: Python (pyproject.toml, uv.lock, setup.py). Entry points: `cli.py`, `run_agent.py`, `hermes_bootstrap.py`, `mcp_serve.py`, `batch_runner.py`

**Frontend / Web dashboard (`:9119`)**: Vite + React/TypeScript in `web/` — `vite.config.ts`, `vitest.config.ts`, `tsconfig*.json`, `package.json` (with node_modules). Test runner: vitest.

**Key directories**:
```
agent/              — core agent loop, providers, subprocess bootstrap
  secret_sources/   — bitwarden.py (BWS integration)
  anthropic_adapter.py, codex_responses_adapter.py, codex_runtime.py,
  gemini_native_adapter.py, bedrock_adapter.py, azure_identity_adapter.py
  usage_pricing.py  — cost/billing dataclasses
  credits_tracker.py, insights.py
acp_adapter/        — ACP/JSON-RPC server (server.py ~2000 lines)
acp_registry/       — ACP registry
gateway/            — gateway service
hermes/             — core Hermes library
hermes_cli/         — CLI entry
integrations/       — third-party integrations
providers/          — provider base (base.py, README.md)
skills/             — skills system
tools/              — tool implementations
tests/              — 100+ pytest test files
web/                — React dashboard (Vite)
docs/               — architecture docs
scripts/            — install-command-desk-dev.ps1, setup-devssd-model.ps1, etc.
```

**`web/` package.json scripts**: (Vite project — likely: `dev`, `build`, `test`, `typecheck` — not read in full to avoid token waste)

### Control Center (`control-center/`) — Node.js ops dashboard (`:8765`)

**Stack**: Plain Node.js HTTP (no framework), SQLite via `lib/db/`. Version: 5.0.6.

**Routes**: `routes/actions.js`, `routes/events.js`, `routes/status.js`, `routes/usage.js`

**Collectors**: `lib/collectors/` — anthropic, claude, claude-code, claude-desktop, codex, cursor, cursor-tokens, command-desk, devssd, dns, github, hetzner, linkvantagem, linkvantagem-workers, mcp, mcp-supervisor, monitors, obsidian, rtk, system, token-ledger, vercel

**Tests**: `tests/api.test.js`, `tests/command-desk-collector.test.js`, `tests/format-numbers.test.js`, `tests/ops-model.test.js`, `tests/rtk-collector.test.js`, `tests/safe-view.test.js` (runner: `node --test`)

**Key scripts**: `scripts/command-desk-start.ps1`, `scripts/command-desk-doctor.ps1`, `scripts/command-desk-gateway-start.ps1`, `scripts/bitwarden-env-sync.ps1`, `scripts/health-check.ps1`

### HERMES_HOME / COMMAND_DESK_HOME

`~/.command-desk` **EXISTS** and is populated:
```
.env, auth.json, config.yaml, state.db, state.db-shm, state.db-wal
gateway.pid, gateway.lock, gateway_state.json
response_store.db, kanban.db
sessions/, logs/, memories/, backups/
bin/  (bws auto-installed here)
hooks/, plugins/, skills/, sandboxes/
SOUL.md, channel_directory.json
```
Instance is running (gateway.pid present). `.env` present — **NOT read** (potential secrets).

---

## 3. Subsystem State Assessment

| Subsystem | State | Path / Notes |
|-----------|-------|-------------|
| **Secrets provider (Bitwarden/BWS)** | EXISTS | `agent/secret_sources/bitwarden.py` — full BWS CLI auto-install, SHA-256 verified, in-process cache, fail-open design. Bootstrap secret: `BWS_ACCESS_TOKEN` in `~/.command-desk/.env` |
| **`.env` / local secrets** | EXISTS | `~/.command-desk/.env` (redacted — not read) |
| **SecretProvider abstraction** | EXISTS | `agent/secret_sources/__init__.py` + bitwarden.py; fail-open: missing BWS never blocks startup |
| **Anthropic adapter + health** | EXISTS | `agent/anthropic_adapter.py` (~2500 lines) — API key, OAuth, Claude Code credential paths |
| **OpenAI/Codex adapter** | EXISTS | `agent/codex_responses_adapter.py` + `agent/codex_runtime.py` — Responses API + App Server subprocess route |
| **Gemini adapter** | EXISTS | `agent/gemini_native_adapter.py` + `agent/gemini_schema.py` |
| **Bedrock adapter** | EXISTS | `agent/bedrock_adapter.py` |
| **Azure adapter** | EXISTS | `agent/azure_identity_adapter.py` |
| **Cursor SDK usage** | **MISSING** | No `@cursor/sdk` / `cursor-sdk` reference found; `agent/codex_runtime.py` drives Codex via subprocess/Responses API, not Cursor SDK |
| **Subprocess manager** | EXISTS | `agent/process_bootstrap.py` (_SafeWriter, lazy OpenAI import, proxy resolution); `batch_runner.py` |
| **Codex worker isolation (CODEX_HOME)** | EXISTS | `agent/codex_runtime.py` — passes `COMMAND_DESK_HOME`/`HERMES_HOME` env to subprocess; `tests/test_subprocess_home_isolation.py` confirms isolation tested |
| **Task dispatcher / worker pool / model+cost policy** | EXISTS | `agent/smart_model_routing.py`, `agent/iteration_budget.py`, `agent/tool_dispatch_helpers.py`, `agent/tool_executor.py`; cost policy via `agent/usage_pricing.py` + `agent/credits_tracker.py` |
| **Cost tracking / billing** | EXISTS | `agent/usage_pricing.py` (`CanonicalUsage`, `BillingRoute`, `CostStatus`, `CostSource` dataclasses); `agent/credits_tracker.py`, `agent/insights.py`, `agent/billing_view.py` |
| **Traces / observability** | PARTIAL | `docs/observability/` dir + `tests/observability/`; `agent/stream_diag.py`, `agent/trajectory.py`, `trajectory_compressor.py`; no dedicated OTEL/Jaeger exporter found |
| **ACP / JSON-RPC server** | EXISTS | `acp_adapter/server.py` (~2000 lines) — full ACP implementation: sessions, fork, auth, tools, streaming, MCP servers |
| **Obsidian context ingestion** | PARTIAL | `control-center/lib/collectors/obsidian.js` (collector for Deck); NO dedicated Obsidian module in `command-desk/agent/`; no `agent/obsidian*.py` found. Gap: Hermes does not natively ingest Obsidian vault context |
| **Setup/integration health page** | EXISTS | `agent/status.py` (gateway status); `scripts/command-desk-doctor.ps1`; control-center `routes/status.js` surfaces command-desk health |
| **Gateway** | EXISTS | `gateway/` dir + `~/.command-desk/gateway.pid` (running) |
| **DB / persistence** | EXISTS | `~/.command-desk/state.db`, `kanban.db`, `response_store.db`; control-center: `lib/db/index.js` + `lib/db/schema.sql` |
| **RTK plugin** | EXISTS | `lib/collectors/rtk.js` (control-center); `config.yaml` checked for `plugins.enabled: [rtk-rewrite]` at startup |

---

## 4. Phase Feasibility Verdict

### Mostly-done (foundation already in place)

- **Phase 1 — Secrets/BWS**: EXISTS. `bitwarden.py` is production-ready with auto-install, caching, fail-open. Only gap: `bw` CLI is unauthenticated — BWS token must be in `~/.command-desk/.env`.
- **Phase 2 — Model providers**: EXISTS. Anthropic, Codex (Responses + App Server), Gemini, Bedrock, Azure all implemented. Smart routing in `smart_model_routing.py`.
- **Phase 3 — Subprocess / isolation**: EXISTS. `process_bootstrap.py` + `codex_runtime.py` + `test_subprocess_home_isolation.py`.
- **Phase 4 — Cost tracking**: EXISTS. `usage_pricing.py`, `credits_tracker.py`, `billing_view.py` — very mature.
- **Phase 5 — ACP/JSON-RPC**: EXISTS. `acp_adapter/server.py` is ~2000 lines, full protocol.
- **Phase 6 — Task dispatcher + model policy**: EXISTS. `smart_model_routing.py`, `iteration_budget.py`, `tool_executor.py`.
- **Phase 10 — DB persistence**: EXISTS. SQLite state.db, kanban.db, response_store.db all live.
- **Phase 11 — Gateway**: EXISTS and running.
- **Phase 13 — Setup/health**: EXISTS. doctor script + status route.

### Real build work needed

- **Phase 7 — Cursor SDK integration**: MISSING. No `@cursor/sdk` usage. If phases require Cursor-native agent dispatch (vs. subprocess Codex), this needs to be built.
- **Phase 8 — Obsidian ingestion in Hermes**: PARTIAL. Control-center has `obsidian.js` collector (reads vault files), but `command-desk/agent/` has no Obsidian module. Needs a memory/context injection bridge from vault to agent system prompt or skill.
- **Phase 9 — Observability/traces**: PARTIAL. `stream_diag.py` + trajectory compressor exist, but no OTEL exporter or structured trace sink. Needs a decision: lightweight file-based traces vs. OTEL.
- **Phase 12 — Web dashboard hang fix**: NOT in scope here (separate diagnostic). Dashboard at `:9119` depends on `web/src/` Vite app. The "Loading Command Desk status..." hang is being investigated separately.

### Overengineering / Risk flags (Devil's Advocate)

1. **Auth race on gateway start**: `gateway.pid` + `gateway.lock` exist but `.command-desk/config.yaml` has a `.corrupt` backup from 2026-06-22 — YAML corruption risk on startup.
2. **Cost blowup**: `smart_model_routing.py` routes autonomously; no hard per-session spend cap visible from inventory. `iteration_budget.py` exists but budget enforcement must be verified.
3. **Secret leakage**: `BWS_ACCESS_TOKEN` in plaintext `~/.command-desk/.env`; `agent/redact.py` exists (good), but any logging path that dumps env vars bypasses it.
4. **bw CLI unauthenticated**: `bw status` → `unauthenticated` — means `bw`-based env sync scripts (`bitwarden-env-sync.ps1`) will fail silently. BWS path (via `bws`) is independent and may work if token is already in `.env`.
5. **control-center has no git repo**: Cannot branch/diff control-center changes directly. All git operations must target `command-desk/`. Risk of untracked drift.
6. **Codex CLI absent**: `where.exe codex` → not found. Any phase requiring Codex CLI subprocess will fall back to Responses API path — verify `codex_app_server` vs `codex_responses` mode in config.
7. **Obsidian bridge complexity**: Building vault ingestion into Hermes risks token-economy bloat (vault can be large). Prefer narrow skill/tool call rather than full vault injection.

### Recommended parallelization for phases 1–13

```
Group A (no-ops / verification only):
  Phase 1 (secrets), Phase 2 (providers), Phase 3 (subprocess),
  Phase 4 (cost), Phase 5 (ACP), Phase 6 (dispatcher),
  Phase 10 (DB), Phase 11 (gateway), Phase 13 (health)
  → Run Explorer subagent to confirm each is wired end-to-end; no new code.

Group B (parallel build, disjoint ownership):
  Phase 7 (Cursor SDK) — agent/cursor_sdk_adapter.py
  Phase 8 (Obsidian) — agent/obsidian_context.py or skills/obsidian/
  Phase 9 (Observability) — agent/otel_exporter.py or traces/

Group C (sequential, depends on B):
  Phase 12 (dashboard hang) — web/ frontend; separate diagnostic underway.
```

---

## 5. Notes for Subsequent Phases

- `bw` CLI is **unauthenticated**; use `bws` (auto-installed to `~/.command-desk/bin/`) for secret pull — do NOT call `bw unlock`.
- Codex CLI absent from PATH — Codex turns will use `codex_responses` API mode; verify `config.yaml` `api_mode` setting before Phase 7.
- `config.yaml.corrupt.*` backup in `~/.command-desk/` — review before restart.
- `control-center/` is not a git repo; no branching possible there. Doc this for ops team.
- Dashboard hang (`:9119` "Loading Command Desk status…") is being diagnosed separately — do not modify `web/src/` until that investigation completes.
