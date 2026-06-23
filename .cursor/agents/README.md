# Cursor — multi-agente local (Command Desk)

Workflow de **desenvolvimento no IDE** — separado do multi-agente **runtime** do Hermes (`delegate_task`, Kanban, Cron).

## Subagentes

| Agente | Modelo | Papel |
|--------|--------|------|
| `orchestrator` | Opus (pai) | Coordena fases; não implementa se couber no implementer |
| `project-analyst` | Composer fast | Análise inicial do repo e padrão recomendado |
| `explorer` | Composer fast | Busca arquivos/símbolos (readonly) |
| `planner` | inherit | Plano técnico + critérios de aceite (readonly) |
| `implementer` | Composer fast | Código e testes da fase atual |
| `spec-reviewer` | Composer | Spec compliance pós-implementação |
| `verifier` | Composer | Testes, lint, checklist AGENTS.md |

## Fluxo padrão

```
project-analyst → planner → [implementer → spec-reviewer → verifier] × N fases
         ↑
    explorer (se codebase desconhecido)
```

## Como invocar no Cursor

1. **Chat principal (Opus):** peça para orquestrar com subagentes.
2. **Task tool:** lance `@explorer`, `@planner`, `@implementer`, etc.
3. **Paralelo:** apenas tarefas independentes (ex.: `web/` + `docs/`).

Exemplo de prompt:

```
@orchestrator Implemente [feature X]:
1. project-analyst — mapear impacto
2. planner — plano em fases
3. implementer + spec-reviewer + verifier por fase
Testes: scripts/run_tests.sh <paths>
```

## Hermes runtime (fora do Cursor)

| Necessidade | Ferramenta |
|-------------|------------|
| Paralelismo imediato | `delegate_task` (economy via `smart_model_routing`) |
| Pipeline durável | `command-desk kanban` + swarm |
| Agendado | `command-desk cron` |
| Dev deste repo | `.cursor/agents/` (esta pasta) |

## Docs

- `docs/CURSOR-LOCAL-MULTI-AGENT.md` — guia completo
- Skill: `skills/devssd-ops/multi-agent-playbook/SKILL.md`
- Dashboard: http://127.0.0.1:9119/multi-agent
