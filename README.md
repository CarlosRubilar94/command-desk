# Command Desk

DevSSD fork of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) — persistent AI agent (skills, memory, gateway, cron).

**Command Desk** = the agent and its web dashboard (`:9119`).  
**Command Deck** = optional ops UI (sibling repo `control-center`, port `:8765`) that monitors DevSSD services.

Upstream Hermes docs: [docs/UPSTREAM-README.md](docs/UPSTREAM-README.md) | [hermes-agent.nousresearch.com](https://hermes-agent.nousresearch.com/docs/)

## Quick start (Windows dev)

```powershell
git clone https://github.com/CarlosRubilar94/command-desk.git
cd command-desk
$env:COMMAND_DESK_HOME = "$env:USERPROFILE\.command-desk"
pip install -e .
command-desk doctor
command-desk dashboard
```

Installer script for Windows hosts: `scripts/install.ps1`.

Dashboard: http://127.0.0.1:9119

| Page | URL |
|------|-----|
| Agent Home | http://127.0.0.1:9119/agent |
| Chat/Run | http://127.0.0.1:9119/run |
| Skills DevSSD | http://127.0.0.1:9119/skills |
| Config/Doctor | http://127.0.0.1:9119/doctor |
| Secrets / Bitwarden | http://127.0.0.1:9119/secrets |
| Gateway / API | http://127.0.0.1:9119/gateway |
| Command Deck Ops | http://127.0.0.1:9119/command-deck |

Ops scripts: `integrations/command-deck/scripts/` (start, doctor, smoke, gateway).

### Web UI build (Windows)

```powershell
npm install
npm run build -w web
command-desk dashboard --port 9119 --no-open --skip-build
```

If build fails on Windows, use upstream stub or `command-desk dashboard --skip-build`.

## Home directory

| Variable | Default |
|----------|---------|
| `COMMAND_DESK_HOME` | `%USERPROFILE%\.command-desk` |
| `HERMES_HOME` | alias (upstream compat) |

## CLI aliases

- `command-desk` — primary (DevSSD)
- `hermes` — upstream alias (same entrypoint)

## Command Deck integration

See [integrations/command-deck/README.md](integrations/command-deck/README.md) for collector contract, Bitwarden runbook, and gateway docs.

The full Command Deck dashboard remains in a separate `control-center` repo (not included here).

## Docs

- [integrations/command-deck/docs/BITWARDEN-SECRETS.md](integrations/command-deck/docs/BITWARDEN-SECRETS.md)
- [integrations/command-deck/docs/COMMAND-DESK-GATEWAY.md](integrations/command-deck/docs/COMMAND-DESK-GATEWAY.md)
- Upstream: https://hermes-agent.nousresearch.com/docs/

## Smoke checklist

| Check | Command |
|-------|---------|
| Version | `command-desk --version` |
| Doctor | `command-desk doctor` |
| Dashboard status | http://127.0.0.1:9119/api/status |
| DevSSD status | http://127.0.0.1:9119/api/devssd/status |
| One-shot | `command-desk -z "Reply OK only" --cli` |
| Gateway | `command-desk gateway status` |
| Bitwarden | `command-desk secrets bitwarden status` |

## Upstream sync

```powershell
git remote add upstream https://github.com/NousResearch/hermes-agent.git  # if missing
git fetch upstream
git merge upstream/main   # or rebase on devssd/command-desk
```

Branch: `devssd/command-desk`

## License

MIT — see [LICENSE](LICENSE). Fork based on Nous Research Hermes Agent.
