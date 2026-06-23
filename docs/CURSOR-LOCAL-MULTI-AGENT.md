# Cursor local multi-agent + Hermes runtime

Command Desk has **two** multi-agent layers. Use the right one.

## Layer comparison

| Layer | Mechanism | Runs on | Best for |
|-------|-----------|---------|----------|
| **Cursor (local dev)** | `.cursor/agents/` + Task tool | Your IDE | Editing this repo, PRs, refactors |
| **Hermes in-process** | `delegate_task` | Agent session | Parallel research, quick workers |
| **Kanban** | SQLite + dispatcher | Gateway / daemon | Durable pipelines, multi-profile |
| **Cron** | Scheduler | Background | Recurring briefings, watchdogs |

## Cursor local workflow

Subagents live in `.cursor/agents/` (versioned in git).

```
Opus (you) ─ orchestrator
  ├─ project-analyst   → scope + risks
  ├─ explorer          → file/symbol map (optional)
  ├─ planner           → phased plan + acceptance criteria
  └─ per phase:
       implementer → spec-reviewer → verifier
```

### Invoke in Cursor

```
@orchestrator [your task]

Use project-analyst first, then planner, then implementer with
spec-reviewer and verifier after each phase.
Run scripts/run_tests.sh on touched paths.
```

Parallel Task only when files don't overlap (e.g. `web/` + `docs/`).

## Hermes runtime workflow

### Smart model routing (economy vs performance)

Enable in `%COMMAND_DESK_HOME%\config.yaml` or dashboard `/routing`:

```yaml
smart_model_routing:
  enabled: true
  delegation_tier: economy
```

- **Economy:** compression, titles, goal_judge, **delegate_task** subagents
- **Performance:** kanban_decomposer, curator, vision, main chat synthesis

CLI: `command-desk routing --enable --delegation-tier economy`

### Recommended config

```yaml
smart_model_routing:
  enabled: true
  delegation_tier: economy
  delegation_reasoning_effort: low

delegation:
  max_concurrent_children: 3
  max_async_children: 3
  max_spawn_depth: 2
  orchestrator_enabled: true

kanban:
  dispatch_in_gateway: true
  dispatch_interval_seconds: 30
  max_in_progress: 4
  auto_decompose: true
  orchestrator_profile: orchestrator
  default_assignee: coder

cron:
  max_parallel_jobs: 4
  ticker_interval_seconds: 30
```

### Playbooks

| Goal | Pattern |
|------|---------|
| Large feature | Kanban triage → auto_decompose → workers |
| Parallel research | `delegate_task` batch (3–5 tasks) |
| Orchestrator tree | `role="orchestrator"` + economy workers |
| Daily briefing | Cron + cheap model |
| Dev in IDE | Cursor subagents (not delegate_task) |
| Swarm | `command-desk kanban swarm --worker … --verifier … --synthesizer …` |

## Profiles (Hermes)

Create isolated profiles for fleet work:

```powershell
command-desk profile create orchestrator --clone
command-desk profile create coder --clone
command-desk profile create researcher --clone
```

See `integrations/command-deck/templates/multiagent-profiles.example.yaml`.

## Dashboard

| Page | URL |
|------|-----|
| Multi-agent hub | http://127.0.0.1:9119/multi-agent |
| Fleet ops | http://127.0.0.1:9119/ops |
| Model routing | http://127.0.0.1:9119/routing |

## Verification

```bash
command-desk doctor
command-desk routing
scripts/run_tests.sh tests/hermes_cli/test_fleet_status.py tests/hermes_cli/test_routing_api.py tests/hermes_cli/test_multi_agent_hub.py -q
```
