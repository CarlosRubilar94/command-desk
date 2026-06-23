---
name: multi-agent-playbook
description: Playbooks multi-agente DevSSD — Cursor local + Hermes runtime.
version: 1.0.0
author: Carlos Vinícius Rezador Rubilar
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [multi-agent, orchestration, cursor, kanban, delegation]
    related_skills: [devssd-ops, plan, subagent-driven-development]
---

# Multi-Agent Playbook (DevSSD)

Dois modos: **Cursor local** (dev deste repo) e **Hermes runtime** (agente em produção).

## When to Use

- Escolher entre Cursor subagents vs `delegate_task` vs Kanban vs Cron
- Montar pipeline dev, pesquisa ou ops DevSSD
- Ativar economy routing para subagentes

## Cursor local (IDE)

Subagentes em `.cursor/agents/`. Fluxo:

1. `project-analyst` — escopo e riscos
2. `planner` — plano por fases
3. Por fase: `implementer` → `spec-reviewer` → `verifier`

Prompt típico no Cursor:

```
@orchestrator [tarefa]
Use two-stage review. Testes: scripts/run_tests.sh <paths>
```

**Não** use `delegate_task` para editar arquivos do repo no Cursor.

## Hermes — pesquisa paralela

```
Delegue 3 pesquisas web em paralelo sobre [tema].
Cada subagente usa economy; sintetize no final.
```

Requer `smart_model_routing.enabled: true` e `delegation_tier: economy`.

## Hermes — feature grande (Kanban)

```powershell
command-desk kanban init
command-desk kanban create "Feature X" --status triage
command-desk routing --enable
```

`auto_decompose` quebra em subtarefas; dispatcher a cada 30s.

## Hermes — swarm (research → verify → write)

```powershell
command-desk kanban swarm "Relatório sobre X" `
  --worker researcher --worker researcher `
  --verifier reviewer --synthesizer writer
```

## Hermes — cron briefing

```powershell
command-desk cron add "Briefing diário" --schedule "0 9 * * *" `
  --model google/gemini-2.5-flash
```

## Config economy (recomendada)

```yaml
smart_model_routing:
  enabled: true
  delegation_tier: economy
delegation:
  max_spawn_depth: 2
kanban:
  dispatch_interval_seconds: 30
  max_in_progress: 4
cron:
  max_parallel_jobs: 4
```

CLI: `command-desk routing`

## Verification

```powershell
command-desk doctor
command-desk routing
# Dashboard: http://127.0.0.1:9119/multi-agent
```

## Docs

- `docs/CURSOR-LOCAL-MULTI-AGENT.md`
- `.cursor/agents/README.md`
