# Command Desk

DevSSD fork of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) — persistent AI agent (skills, memory, gateway, cron).

Command Desk is the primary portal for Vinicius' Hermes Agent.

**Command Deck** (`../control-center`, port **8765**) stays as the operational dashboard that monitors this agent. Command Desk exposes Deck status/pages through its own UI.

## Quick start (Windows dev)

```powershell
cd C:\Users\Vinicius\Documents\Codex\command-desk
.\scripts\install-command-desk-dev.ps1
$env:COMMAND_DESK_HOME = "$env:USERPROFILE\.command-desk"
command-desk doctor
command-desk dashboard
```

Dashboard: http://127.0.0.1:9119

Main pages:

| Page | URL |
|------|-----|
| Agent Home | http://127.0.0.1:9119/agent |
| Multi-agent hub | http://127.0.0.1:9119/multi-agent |
| Chat/Run | http://127.0.0.1:9119/run |
| Skills DevSSD | http://127.0.0.1:9119/skills |
| Config/Doctor | http://127.0.0.1:9119/doctor |
| Secrets / Bitwarden | http://127.0.0.1:9119/secrets |
| Gateway / API | http://127.0.0.1:9119/gateway |
| Command Deck Ops | http://127.0.0.1:9119/command-deck |

From Command Deck: runbook **Command Desk dashboard** or `scripts\command-desk-start.ps1`.

### Web UI build (Windows)

Full Vite build may hang or fail on some Windows npm workspace setups (`tsc`/`.vite-temp` ENOENT). Fallback:

```powershell
.\scripts\bootstrap-web-dist-stub.ps1   # API + minimal HTML
command-desk dashboard --port 9119 --no-open --skip-build
```

For full UI, prefer the Command Desk build helper. It uses the Codex bundled
Node runtime when present and falls back to `node`:

```powershell
npm run build:web:desk
# or directly:
.\scripts\build-command-desk-web.ps1
```

Stable end-to-end validation:

```powershell
npm run validate:desk
# or directly:
.\scripts\validate-command-desk.ps1
```

Stop the dashboard first if rebuild fails with `EPERM` on `web_dist/assets`.

## Home directory

| Variable | Default |
|----------|---------|
| `COMMAND_DESK_HOME` | `%USERPROFILE%\.command-desk` |
| `HERMES_HOME` | alias (plugins/upstream compat) |

## CLI aliases

- `command-desk` — primary (DevSSD)
- `hermes` — upstream alias (same entrypoint)

## RTK token economy

```powershell
$env:HERMES_HOME = "$env:USERPROFILE\.command-desk"
rtk init --agent hermes
```

Enable `rtk-rewrite` in `%COMMAND_DESK_HOME%\config.yaml` under `plugins.enabled`.

## Docs

- [COMMAND-DESK-ARCHITECTURE.md](docs/COMMAND-DESK-ARCHITECTURE.md) — ports, APIs, integration
- [CURSOR-LOCAL-MULTI-AGENT.md](docs/CURSOR-LOCAL-MULTI-AGENT.md) — Cursor subagents + Hermes runtime
- Upstream: https://hermes-agent.nousresearch.com/docs/

## DevSSD model setup (non-interactive)

After Bitwarden SM is configured (`secrets.bitwarden.enabled: true`):

```powershell
. ..\control-center\scripts\bitwarden-env-sync.ps1
.\scripts\setup-devssd-model.ps1
# optional free tier:
# .\scripts\setup-devssd-model.ps1 -Model "meta-llama/llama-3.3-70b-instruct:free"
command-desk doctor
```

Default model in `%COMMAND_DESK_HOME%\config.yaml`:

```yaml
model:
  provider: openrouter
  default: google/gemini-2.5-flash
```

Interactive wizard (TTY): `command-desk setup model`

## Skills (DevSSD)

Bundled stub: `skills/devssd-ops/SKILL.md` — Obsidian vault, Command Deck MCP, RTK, Bitwarden sync pointers.

Copy or symlink into `%COMMAND_DESK_HOME%\skills\` if the agent should load it by default.

## Smoke checklist

| Check | Command |
|-------|---------|
| Version | `command-desk --version` |
| Doctor | `command-desk doctor` |
| Dashboard public status | http://127.0.0.1:9119/api/status |
| DevSSD protected status | http://127.0.0.1:9119/api/devssd/status |
| End-to-end validation | `npm run validate:desk` |
| One-shot | `command-desk -z "Reply OK only" --cli` |
| Gateway | `command-desk gateway status` |
| Bitwarden | `command-desk secrets bitwarden status` |

From Command Deck: runbooks **Command Desk dashboard**, **Obsidian flush + restart Desk**.

## Next steps (manual)

1. **Gateway** — messaging bridge (Telegram/Discord/WhatsApp):
   ```powershell
   command-desk gateway install   # Scheduled Task (auto-start)
   # or foreground:
   command-desk gateway run
   ```
   Configure platform tokens via `command-desk setup gateway` or env vars. API: `:8642/health`.

2. **WSL (optional)** — prefer Windows-native install for dashboard build; if using WSL, use Linux Node inside WSL (not Windows `npm` through default distro).

3. **Upstream branch** — track DevSSD fork changes:
   ```powershell
   git checkout -B devssd/command-desk
   git remote add upstream https://github.com/NousResearch/hermes-agent.git  # if missing
   git fetch upstream
   ```

4. **OpenRouter credits** — if one-shot fails with payment errors, add credits or switch to a `:free` model via `setup-devssd-model.ps1`.

## Upstream sync

```powershell
git remote add upstream https://github.com/NousResearch/hermes-agent.git
git fetch upstream
```

Branch: `devssd/command-desk`
