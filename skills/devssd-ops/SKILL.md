---
name: devssd-ops
description: DevSSD operational context — Obsidian memory vault, Command Deck MCP, RTK token economy. Use when coordinating infra, memory flush, or Deck↔Desk runbooks on Windows.
---

# DevSSD Ops (Command Desk skill)

Persistent agent brain for the DevSSD workstation. **Command Deck** (`control-center`, `:8765`) monitors **Command Desk** (this fork, dashboard `:9119`).

## Obsidian memory (canonical)

- Vault: `G:\Meu Drive\03-Documentacao\Obsidian-DevSSD`
- Bootstrap: `00-AI/START-HERE.md`, `00-AI/working-context.md`
- Sync: `C:\Users\Vinicius\Documents\scripts\update-obsidian-devssd-memory.py`
- PreCompact flush: `--flush-session`
- **Never** store secrets in the vault

## Command Deck integration

| Resource | Location |
|----------|----------|
| Dashboard | http://127.0.0.1:8765 |
| Desk dashboard | http://127.0.0.1:9119 |
| Collector | `control-center/lib/collectors/command-desk.js` |
| Runbooks | `command-desk-doctor`, `command-desk-start`, `devssd-obsidian-desk-restart` |

Deck runbook **Memória Obsidian + restart Desk** flushes session notes and restarts `:9119`.

## RTK token economy

```powershell
$env:HERMES_HOME = "$env:USERPROFILE\.command-desk"
rtk init --agent hermes
```

Plugin `rtk-rewrite` enabled in `%COMMAND_DESK_HOME%\config.yaml`.

## MCP registry (Cursor / Deck)

Registry SSOT: `C:\Users\Vinicius\Documents\Codex\mcp\`
Sync script: `control-center/scripts/sync-mcp-registry.ps1`

Relevant MCPs for DevSSD: `user-openrouter`, `user-bitwarden`, `user-computer-control-center`, `user-github`.

## Secrets

Bitwarden SM project `DevSSD-keys` — only `BWS_ACCESS_TOKEN` local. Session export:

```powershell
. control-center\scripts\bitwarden-env-sync.ps1
```

## Docs

- `command-desk/docs/COMMAND-DESK-ARCHITECTURE.md`
- `command-desk/README-COMMAND-DESK.md`
- `control-center/.cursor/AGENTS.md` (CommandDesk agent role)
