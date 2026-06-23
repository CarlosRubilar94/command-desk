# Command Desk — Waves 8–12 Retro & Audit

> Branch: `cursor/command-desk-wave-next` (stacked on `cursor/command-desk-exec-evolution` / PR #10) · PR #11 · Mode: Executive Council.
> All waves: implemented by a background subagent (NO git), then orchestrator-validated (build + targeted tests), committed, pushed, logged on the PR.

## What shipped

### Wave 8 — Real Agent Replay
Step-by-step playback (play/pause/step ±/jump/speed), expanded timeline with per-step duration bars, tool-call inspector + payload-aware viewer (locked callout when capture is off), error-step highlight, trace↔session links.
- FE: `web/src/pages/ReplayPage.tsx` + `web/src/pages/replay/*`, route `/replay?trace=|session=`, entry from Traces/Sessions.
- No backend changes (reuses `/api/traces`). typecheck 0, build green.

### Wave 9 — Mission Builder
`/missions/builder`: template picker, step editor (add/remove/reorder), per-task agent+model, pre-run **cost estimate** (transparent heuristic), save-as-custom-template + instantiate.
- FE: `MissionBuilderPage.tsx`, `MissionsPage` entry, `api.ts`, breadcrumbs.
- BE: `mission_templates.py` (custom templates → `custom_templates.json`), 3 additive authed endpoints (`GET /api/templates/{id}`, `POST /api/templates`, `POST /api/templates/instantiate-draft`).
- 8 new tests. typecheck 0, build green.

### Wave 10 — Cost Guardrails
Pure **default-off** decision engine, opt-in expensive-model block + auto-fallback to economy, daily + per-mission budgets, premium-usage alert, Guardrails + Savings panels on `/costs`.
- BE: `cost_guardrails.py` (new), gated wiring in `agent/smart_model_routing.py`, `config.py` (`cost_guardrails`, defaults off), `GET/PUT /api/costs/guardrails`.
- **Routing is byte-for-byte unchanged when disabled** (verified by routing suite). 23 targeted tests pass. typecheck 0, build green.

### Wave 11 — Ops Autopilot
Pure incident detection (recurring errors, failed/blocked runs, over-budget, slow agents, severity-ranked); **operator-triggered** diagnose → ops-watchdog mission + Kanban task (registry fallback) + report scaffold. **No agent execution / no background loops.**
- BE: `ops_autopilot.py` (new), `GET /api/ops/autopilot/incidents`, `POST /api/ops/autopilot/diagnose`.
- FE: Autopilot panel on `/ops`. 14 targeted tests pass. typecheck 0, build green.

### Wave 12 — UX Enterprise Polish
Error boundaries (`ds/ErrorBoundary` wraps the route area), density modes (compact/cozy via context + `data-density` tokens, persisted), DataTable quick-filter + sorting (Missions, Cost-by-Model), breadcrumb coverage incl `/replay`, skeleton/empty-state audit, palette lists Mission Builder + Replay, responsive/mobile verified.
- FE only: `ds/ErrorBoundary.tsx`, `contexts/DensityContext.tsx`, `ds/DataTable.tsx`, `App.tsx`, `DeckPageShell.tsx`, `CommandPalette.tsx`, `MissionsPage`, `CostsPage`, `devssd-tokens.css`. typecheck 0, build green.

## Validation summary
| Wave | typecheck | build | backend tests |
|------|-----------|-------|---------------|
| 8 | 0 | green | n/a (reuse) |
| 9 | 0 | green | 8 pass |
| 10 | 0 | green | 23 pass (incl. routing no-regress) |
| 11 | 0 | green | 14 pass |
| 12 | 0 | green | n/a (FE only) |

## Safety posture
No deploy, no merge, no secrets/auth changes, no destructive migrations. All new endpoints authenticated + profile-scoped. Runtime-affecting features (guardrails, autopilot) are default-off / operator-triggered.

## Risks & follow-ups (prioritized)
1. **Bundle size** — core `index` (~1.14 MB) + Nous DS `card` (~387 kB) chunks exceed 500 kB; against the Dashboard <1s / pages <500ms targets this is the top perf item → **Wave 13 (perf/bundle hardening)**.
2. **`DevssdPages.tsx` ineffective dynamic import** (eager for home + lazy for deck pages) — split for real code-split.
3. **Cost accuracy** — Mission Builder estimate + `costs/by-mission` are heuristic/estimate until per-call routing savings are recorded.
4. **Replay** — step list not virtualized (>1000 spans may lag); Missions→Replay link deferred (no `trace_id` on `MissionRow`).
5. **Guardrails** — per-mission runtime enforcement needs mission-id env present.
6. **Autopilot** — diagnose scaffolds only (no remediation execution by design); custom-template save mutates in-process globals (JSON-persisted).

## Next
Wave 13 — Performance & bundle hardening (manualChunks/DS split, fix DevssdPages dynamic import, replay virtualization), then re-audit cost accuracy.
