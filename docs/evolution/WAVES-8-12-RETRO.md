# Command Desk — Waves 8–15 Retro & Audit

> Branch: `cursor/command-desk-wave-next` (stacked on `cursor/command-desk-exec-evolution` / PR #10) · PR #11 · Mode: Executive Council.
> Every wave: implemented by a background subagent (NO git), then orchestrator-validated (build + targeted tests), committed, pushed, logged on the PR.

## What shipped

### Wave 8 — Real Agent Replay
Step playback (play/pause/step/jump/speed), expanded timeline w/ per-step duration, tool-call inspector + payload-aware viewer, error-step highlight, trace↔session links. Route `/replay`. FE only (reuses `/api/traces`).

### Wave 9 — Mission Builder
`/missions/builder`: template picker, step editor (add/remove/reorder), per-task agent+model, pre-run cost estimate (heuristic), save-as-custom-template + instantiate. +3 additive authed template APIs. 8 tests.

### Wave 10 — Cost Guardrails
Pure **default-off** decision engine, opt-in expensive-model block + auto-fallback, daily + per-mission budgets, premium alert, Guardrails + Savings panels. Routing byte-for-byte unchanged when disabled. 23 tests.

### Wave 11 — Ops Autopilot
Pure incident detection + **operator-triggered** diagnose (ops-watchdog mission + Kanban task + report scaffold). No auto-execution. 14 tests.

### Wave 12 — UX Enterprise Polish
Error boundaries, density modes, DataTable sort/filter, full breadcrumbs, skeleton/empty audit, palette routes, responsive/mobile. FE only.

### Wave 13 — Performance & Bundle Hardening
Vendor chunk splitting (`vendor-react`, `vendor-ui`, `vendor-icons`), fixed `DevssdPages` ineffective dynamic import (eager home split from a true lazy deck chunk; warning gone), replay step-list windowing. FE only.

### Wave 14 — Cost Accuracy
Unified pricing module (`hermes_cli/pricing.py`); per-call `cost_usd` + `savings_usd` recorded on spans (allowlisted); routing **annotates** a baseline without changing selection; `/api/costs/savings` + `by-mission` return real recorded data with `is_estimate`; actual/estimated badges. 35 tests (incl. routing no-regression).

### Wave 15 — Performance Round 2
Lazy-loaded the persistent chat host so the xterm/terminal stack leaves the initial path. **`index` 1,084 → 548 kB (gzip 302 → 159 kB)**; `vendor-terminal` (~496 kB) now on-demand. FE only.

## Validation summary
| Wave | typecheck | build | backend tests |
|------|-----------|-------|---------------|
| 8 Replay | 0 | green | reuse |
| 9 Mission Builder | 0 | green | 8 |
| 10 Cost Guardrails | 0 | green | 23 (routing no-regress) |
| 11 Ops Autopilot | 0 | green | 14 |
| 12 UX Polish | 0 | green | FE-only |
| 13 Perf/Bundle | 0 | green | FE-only |
| 14 Cost Accuracy | 0 | green | 35 (routing no-regress) |
| 15 Perf Round 2 | 0 | green | FE-only |

## Perf trajectory
Initial `index` 1,144 kB (gzip 324) → after Wave 13 (vendor split) 1,084 kB → after Wave 15 (chat lazy) **548 kB (gzip 159)**. Vendors isolated for long-term caching; per-route chunks lazy.

## Safety posture
No deploy, no merge, no secrets/auth changes, no destructive migrations. New endpoints authenticated + profile-scoped. Runtime-affecting features default-off (guardrails) / operator-triggered (autopilot) / record-only (cost accuracy).

## Remaining backlog (prioritized — needs a scope decision)
1. **Deeper `index` decomposition** (~548 kB → target lower): route-decompose the always-eager shell chrome (sidebar/status/plugin host). Moderate risk to shell/chat UX — recommend a dedicated, carefully-reviewed pass.
2. **Pre-existing ~848 pytest collection errors** on the FULL suite (identical on base branch; missing optional deps). Repo-health cleanup, large and unrelated to this evolution — recommend a separate maintenance effort.
3. Minor polish: Missions→Replay link (needs `trace_id` on `MissionRow`); session full subtree via `parent_id`; replay payload viewer when capture enabled; guardrails per-mission id propagation; premium-run classification precision in real savings.

## Status
Roadmap (P0–P2 + Waves 8–15) implemented and validated. High-ROI frontier closed; remaining items are deeper refactors or base-branch maintenance that warrant explicit scoping before further spend.
