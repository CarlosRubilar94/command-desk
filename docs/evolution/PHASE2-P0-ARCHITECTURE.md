# Phase 2 — P0 Architecture (v2, COUNCIL-APPROVED)

> Executive Council Mode · President (Opus) ruling: **APPROVED**
> Gate: CTO / QA / SRE / Security = APPROVE_WITH_CHANGES (all folded below) · Devil's Advocate 2 criticals → RESOLVED (plugin-hook emit path; sibling-exporter positioning).
> Branch: `cursor/command-desk-exec-evolution` · Scope: P0 — Agent Tracing, Cost Intelligence, Fleet upgrade, Mission Control.

## 0. Guiding principle: reuse-first, operator-flow-first
Layer P0 on existing infrastructure; optimize the operator's daily job ("a run is stuck or burning money → find cause → stop/reroute/resume in ≤2 clicks"). Existing assets:
- `hermes_state.py::SessionDB` (`~/.hermes/state.db`): sessions with `parent_session_id`, tokens, `estimated/actual_cost_usd`; messages.
- Cost/tokens already computed per turn in `agent/conversation_loop.py` (cost ~L1875) via `agent/usage_pricing.py`.
- `hermes_cli/kanban_db.py`: durable boards (each board = its own DB at `kanban/boards/<slug>/kanban.db`).
- `hermes_cli/plugins.py`: **plugin hook bus** — `VALID_HOOKS` (`post_api_request`, `pre_tool_call`, `post_tool_call`, `subagent_stop`, …), `register_hook`/`invoke_hook`; already dispatched by the loop and consumed by `plugins/observability/nemo_relay` + `langfuse`.
- `hermes_cli/web_server.py`: FastAPI, decorator routes; auth gate ~L276-352; public allowlist in `hermes_cli/dashboard_auth/public_paths.py`.

## 1. Agent Tracing (keystone) — ships as a PLUGIN, no agent-loop edits

### 1.1 Emit path (REUSE the hook bus)
- New plugin `plugins/observability/sqlite_traces/__init__.py` with `register(ctx)` registering on `VALID_HOOKS`:
  - `post_api_request` → `llm_call` span (model, provider, tokens; cost computed via `usage_pricing`).
  - `pre_tool_call`/`post_tool_call` → `tool_call` span (tool name, duration, status, bounded error class).
  - `subagent_stop` → `delegation` span linking parent↔child `session_id` (delegation tree).
  - turn/session scoping span as parent.
- **ZERO edits** to `conversation_loop.py` / `tool_executor.py` / `delegate_tool.py`. Reuse the span semantics `nemo_relay` already builds; this is a **sibling SQLite exporter** (queryable dashboard store), not a parallel emit path.

### 1.2 Storage — dedicated `traces.db` (NOT state.db) [D2 RESOLVED]
New SQLite file `traces.db` under hermes_home, holding `spans` + `missions` registry (+ later `cost_alerts`). Join to sessions by `session_id` in app code. Owner-only file perms where supported.
```
spans(
  span_id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, parent_id TEXT, session_id TEXT,
  kind TEXT,          -- agent_turn | llm_call | tool_call | delegation
  name TEXT, agent TEXT, model TEXT, provider TEXT,
  status TEXT,        -- running | ok | error
  started_at REAL, ended_at REAL, duration_ms INTEGER,
  input_tokens INTEGER, output_tokens INTEGER, total_tokens INTEGER, cost_usd REAL,
  error TEXT,         -- bounded error class only
  attributes TEXT     -- JSON, ALLOWLIST keys only (see §3)
)
INDEX (trace_id); INDEX (session_id); INDEX (started_at, kind, status)
```
A trace = spans sharing `trace_id`; root totals derived (cache later if needed).

### 1.3 Recorder (best-effort, bounded)
- Background flush thread; **bounded in-memory queue with explicit CAP + `dropped_spans` counter** (disk-full/backpressure ⇒ drop, never OOM/raise into agent). Watchdog restarts a dead thread. Expose `dropped_spans` + thread health on `/api/ops/fleet-metrics`.
- Config: `tracing: { enabled: true, sample_rate: 1.0 [D3], capture_payloads: false [D4], retention_days: 14, queue_max: <N> }`.
- Cost: `post_api_request` provides usage/tokens, not cost — recorder computes via `usage_pricing` or reconciles from session aggregate.

### 1.4 Retention / purge
`retention_days` pruning + row cap; **cascade** `DELETE FROM spans WHERE session_id IN (...)` on session delete/compaction; VACUUM/secure-delete option for purge flows.

### 1.5 API + page
- `GET /api/traces` (filters: time/model/agent/status, paginated) · `GET /api/traces/{trace_id}` (spans).
- `/traces`: DataTable of traces → span **waterfall/timeline** drilldown (DS `Timeline`+`DataTable`); also surfaced as a contextual drawer from `/ops`, `/sessions`, `/costs`.

## 2. Mission Control — outcome-centered, Kanban-powered [D1 RESOLVED]
- Each board is its own DB (no single store to derive from) → thin central registry `missions(id, board_slug, title, status, owner, created_at, tags)` in `traces.db`; rollups derived per-board lazily.
- UI noun = **Mission** (objective + tasks + agents + cost + timeline + outcome), NOT "board".
- Rollups: progress = task status counts; cost/tokens = sum over linked `session_id`; models = distinct; timeline = `task_events` + span times; owners = `assignee`; "most expensive / stuck / erroring runs".
- `GET /api/missions` (list+rollups) · `GET /api/missions/{id}`. Page: `/missions` workspace cards/table.

## 3. Security (allowlist by default)
- Span `attributes` = STRICT ALLOWLIST: span/trace/parent/session ids, kind, status, model, provider, input/output/total tokens, cost_usd, durations, bounded error-class.
- NEVER as metadata: tool args, prompt/response text, command lines, file contents, headers, URLs w/ creds/querystrings, env values.
- `capture_payloads` default OFF; if ON → per-session opt-in + secret scanner/denylist + irreversible redaction before enqueue + size caps + fixtures (terminal cmd, API key) in tests.
- New endpoints (`/api/traces`, `/api/missions`, `/api/costs*`, `/api/ops/fleet-metrics`): inherit auth gate, stay OUT of `dashboard_auth/public_paths.py`, profile-scoped, paginated; don't leak raw user_id/session graphs unless needed.
- COMMAND_DECK_URL probe: allow only `127.0.0.1`/`localhost:8765`; reject creds/querystrings/private non-loopback; cap redirects; don't echo full probe errors.

## 4. Cost Intelligence
- Source: `SessionDB` aggregates (cost already present) + per-span cost + `usage_pricing`.
- Breakdowns: by model, by mission (board), by agent/profile, by day. Routing savings via `agent/smart_model_routing.py` (downgrade attribution; baseline premium − actual).
- Alerts: thresholds (daily/mission) → flagged in payload + Mission Overview.
- `GET /api/costs/summary | /by-model | /by-day | /by-mission | /savings`. Page `/costs`: KPIs + tables + `Sparkline` trends (no chart dep).

## 5. Fleet upgrade (`/ops`)
Extend `/api/ops/fleet-status` family with new `GET /api/ops/fleet-metrics`: queue depth (kanban ready/in-progress), bottlenecks (slowest spans by avg duration), recurring errors (grouped span errors), throughput (spans/min), cost rollup (today), `dropped_spans`/tracer health. `/ops` gets alert rows that deep-link to traces/sessions/missions/costs (incident console).

## 6. Cross-linking glue (operator-flow-first)
session ↔ mission (`mission_id`/`board_slug`), trace ↔ session (`session_id`), cost rows ↔ top traces/sessions, mission ↔ most expensive/stuck/erroring runs. Every list row drills down in ≤2 clicks.

## 7. Approved BUILD ORDER (waves)
- **Wave 1 (parallel, now):**
  - 1A Tracing foundation: `sqlite_traces` plugin + `traces.db` (spans + missions registry) + shared store module + recorder (cap/dropped_spans/watchdog/best-effort) + retention/purge + config + backend unit tests. No web_server.py / frontend / loop edits.
  - 1B `/costs` MVP vertical: `/api/costs/{summary,by-model,by-day,savings}` from existing SessionDB + `/costs` page (KPIs, tables, sparkline, savings, alert banner) + route/nav/api.ts. Owns web_server.py + frontend this wave.
- **Wave 2 (parallel):** `/api/traces` + `/traces` explorer + contextual trace drawer; `/api/ops/fleet-metrics` + `/ops` alert upgrade; `/api/costs/by-mission`.
- **Wave 3:** `/api/missions` + `/missions` workspace + Dashboard **Mission Overview** panel; finish cross-link wiring.

## 8. Test plan (QA, corrected)
- Respect markers: `$env:PYTHONPATH='.'; py -3.11 -m pytest tests\<area>\test_<x>.py -q` (do NOT blanket-override addopts; keep `-m 'not integration'`).
- ≥6 unit tests: span store CRUD+retention; recorder best-effort (induced failure never raises); queue cap + `dropped_spans`; cost rollup; mission rollup from seeded board; each new API shape + auth (absent from public_paths).
- Frontend: `npm run typecheck --workspace web` (no full Vite build — known hang). Verify Tailwind `@source` covers `web/src/components/ds/**`.

## 9. Differentiation bets (Innovation)
cost-per-mission with routing-savings attribution · delegation-tree replay (parent/child agents + tools + latency + spend) · self-hosted "fleet incident console" (stuck/burning/erroring ⇒ stop/reroute/resume).

## 10. Locked decisions
D1 central `missions` registry (not pure-derive) · D2 separate `traces.db` · D3 sample_rate 1.0 · D4 capture_payloads OFF.
