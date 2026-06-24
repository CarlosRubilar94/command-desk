# Command Desk — Autonomous Evolution Retro & Audit

> Branch: `cursor/command-desk-exec-evolution` · Mode: Executive Council (President = Opus 4.8) · Status: ready for review (draft PR).
> Method: project-analyst → explorer → planner → council critique → implement → spec-review → verify, in parallel waves.

## 1. What shipped

### P0 (all delivered + tested)
- **Agent Tracing** — `plugins/observability/sqlite_traces` registers on the existing plugin hook bus (`post_api_request`, `pre/post_tool_call`, `subagent_stop`) with **zero agent-loop edits**; spans persist to a dedicated `traces.db` via `hermes_cli/traces_store.py`. Bounded best-effort recorder (queue cap + `dropped_spans` + watchdog). `GET /api/traces`, `/api/traces/{id}`; `/traces` page with a span **waterfall** drawer. Tracing is **on by default**.
- **Cost Intelligence** — `/api/costs/{summary,by-model,by-day,savings,by-mission}` over `SessionDB`; `/costs` page (KPIs, per-model table, day sparkline, routing-savings, threshold alert).
- **Fleet Management** — `/api/ops/fleet-metrics` (queue, throughput, bottlenecks, recurring errors, cost today, tracer health) + `/ops` incident rows deep-linking to traces/sessions/costs.
- **Mission Control** — Missions layered on Kanban boards (central `missions` registry, no parallel system); `/api/missions[/{id}]` with progress, owners, models, cost, delegation tree, timeline, top runs; `/missions` workspace; **Dashboard Mission Overview** panel on the home landing.

### P1 (delivered)
- **UX** — global ⌘/Ctrl-K **command palette**, keyboard shortcuts (`g h/m/o/c/t`, `?` help), breadcrumbs in `DeckPageShell`; design-system loading/empty/error states everywhere.
- **Sessions** — delegation tree, reusable `TraceDrawer`, message timeline, robust session→trace resolution (`/api/traces?session_id=`).
- **Command Deck integration** — SSRF-hardened `:8765` probe + `GET /api/command-deck/overview`; `/command-deck` is now a single-pane view (deck/fleet/cost/missions/tracer) without context switching.

### P2 (delivered)
- **Analytics** — `/api/analytics/overview` (throughput, success rate, p50/p95 latency, token usage, model efficiency) + `/analytics` page.
- **Observability** — `/api/observability/alerts` (cost/errors/tracer/latency rules) + `/events`; dashboard alerts strip.
- **Automation** — 7 mission **templates** (research, code-review, feature-build, ops-watchdog, content, growth, affiliate) via `/api/templates` + `/instantiate` (board + tasks + mission + cron).

### Foundations
- **Design System** — semantic tokens (spacing/radius/type/shadow/color/motion) extending `devssd-tokens.css` + 11 primitives in `web/src/components/ds/` (DataTable, Skeleton, Empty/ErrorState, Timeline, Drawer, StatusPill, Sparkline…).
- **Performance** — route-level `React.lazy` code-splitting (21 routes → own chunks) + memoization + responsive tables.

## 2. Architecture decisions (council-ratified)
- Tracing as a **sibling SQLite exporter** on the hook bus, not loop instrumentation (longevity, no upstream-merge pain) — reuses `nemo_relay`/`langfuse` span semantics.
- **Dedicated `traces.db`** (not `state.db`, which has single-conn lock + conditional-WAL + corruption recovery).
- **Mission = outcome workspace powered by Kanban** (registry table; boards are per-file, so no pure-derive).
- **Security by default**: span attributes are an allowlist (no prompts/args/secrets), `capture_payloads` OFF, new endpoints inherit auth gate + profile scope, traces.db owner-only perms, purge cascade, SSRF-guarded deck probe.

## 3. Quality status
- **Backend tests:** 26 passing across `tests/observability` + `tests/hermes_cli/test_{costs,traces,missions,command_deck_overview,analytics_observability,templates}_api.py` (Python 3.12; 3.11 not installed locally).
- **Frontend:** `npm run typecheck --workspace web` exit 0; **Vite build green** (`✓ built`, lazy chunks emitted).
- **Process:** every P0 change passed a 4-seat council critique (CTO/PE/DA, SRE/QA/FinOps, Security, Product/UX/Innovation) + a verifier gate before merge to the branch.

## 4. Risks & tech debt (prioritized)
1. **Pre-existing**: ~848 pytest *collection* errors on the full suite (identical on base branch) — unrelated to this work but worth a dedicated cleanup (missing optional deps). Our targeted suites are green.
2. **Bundle size**: core `index` (~1.14 MB) + Nous DS `card` (~387 kB) chunks exceed 500 kB — trim/splitting opportunity.
3. **Ineffective dynamic import**: `DevssdPages.tsx` is both eager (home) and lazy (deck pages) → split into separate files to make the deck pages actually code-split.
4. **Mission cost attribution** depends on `tasks.session_id` linkage; `/api/costs/by-mission` is `is_estimate`. Routing savings is best-effort until per-call savings are recorded in `smart_model_routing`.
5. **Sessions delegation tree** only shows current-page children — a `GET /api/sessions?parent_id=` would give full subtrees.
6. **Windows ACL** hardening of `traces.db` relies on `icacls` (best-effort fallback elsewhere).
7. **Board slug** uniqueness on template instantiate is best-effort (race under concurrent identical instantiations).

## 5. Recommended next phase
- Record per-call routing savings in `smart_model_routing` → exact (not estimated) cost savings.
- Trace retention/rollup job + `traces` summary cache for very large span tables.
- Full session **replay/diff** (current upgrade adds tree+timeline+trace; replay/diff is the stretch).
- Bundle trimming (split Nous DS, lazy-load heavy DS pieces) to hit Dashboard <1s / pages <500ms targets under load.
- Onboarding flow + saved views/filters; templates → richer cron/monitoring wiring.

## 6. Safety
No deploy, no merge, no secrets/auth changes. All work on `cursor/command-desk-exec-evolution`; draft PR only.
