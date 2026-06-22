# Command Desk — Architecture (DevSSD fork)

Fork of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) v0.17.0.
**Command Deck** (Node, `:8765`) monitors and controls **Command Desk** (Python agent).

## Ports

| Service | Default port | Health / status |
|---------|--------------|-----------------|
| Web dashboard | **9119** | `GET /api/status` (public liveness) |
| Gateway API (OpenAI-compat) | **8642** | `GET /health`, `GET /health/detailed` |
| Webhooks | **8644** | `GET /health` |
| Command Deck (sibling) | **8765** | `GET /api/status` (probed by Desk) |

## Key paths (repo)

| Area | Path |
|------|------|
| CLI entry | `hermes_cli/main.py` |
| Agent loop | `agent/conversation_loop.py` |
| Gateway | `gateway/run.py` |
| Dashboard server | `hermes_cli/web_server.py` |
| Config loader | `hermes_cli/config.py` |
| Home resolver | `hermes_constants.py` → `get_hermes_home()` |
| Plugins | `hermes_cli/plugins.py`, `plugins/` |
| Deck integration | `integrations/command-deck/` |

## Runtime home

- Windows: `%USERPROFILE%\.command-desk` (override via `COMMAND_DESK_HOME` or `HERMES_HOME`)
- Install tree: `%LOCALAPPDATA%\command-desk\` (venv/binaries when using managed install)

## `/api/status` (dashboard :9119)

Public probe — no auth on network-exposed installs. Safe fields for Command Deck collector:

```json
{
  "version": "0.17.0",
  "gateway_running": true,
  "gateway_state": "running",
  "gateway_platforms": {},
  "active_sessions": 0,
  "active_agents": 0,
  "auth_required": false
}
```

Loopback-only extras: `hermes_home`, `config_path`, `gateway_pid`.

Optional query: `?profile=<name>` for profile-scoped gateway badge.

## `/api/devssd/status` (protected DevSSD snapshot)

Operational snapshot for DevSSD UI pages (`/agent`, `/doctor`, `/command-deck`). **No secret values** are returned.

```json
{
  "version": "0.17.0",
  "hermes_home": "C:\\Users\\...\\.command-desk",
  "gateway_running": false,
  "gateway_state": "stopped",
  "dashboard_up": true,
  "command_deck_up": true,
  "agent": {
    "model": "google/gemini-2.5-flash",
    "provider": "openrouter",
    "devssd_skill_installed": true
  },
  "bitwarden": {
    "enabled": true,
    "token_present": true,
    "project_configured": true,
    "bws_found": true
  },
  "command_deck": {
    "available": true,
    "url": "http://127.0.0.1:8765/api/status",
    "app_url": "http://127.0.0.1:8765"
  }
}
```

Probes Command Deck at `COMMAND_DECK_URL` (default `http://127.0.0.1:8765`).

## Gateway API `:8642/health`

Returns `{"status": "ok"}` when API server is up. `/health/detailed` includes gateway state for cross-container probes.

## Bitwarden (secrets)

- SM project: **DevSSD-keys**
- Local bootstrap only: `BWS_ACCESS_TOKEN` in `%COMMAND_DESK_HOME%\.env`
- Provider keys synced via `command-desk secrets bitwarden sync` or `control-center/scripts/bitwarden-env-sync.ps1`
- Status in UI: `/secrets` page and `bitwarden` block in `/api/devssd/status`
- Runbook: `integrations/command-deck/docs/BITWARDEN-SECRETS.md`

## CLI smoke

```powershell
command-desk --version
command-desk doctor
command-desk dashboard --port 9119
command-desk gateway status
```

## RTK integration

```powershell
$env:HERMES_HOME = "$env:USERPROFILE\.command-desk"
rtk init --agent hermes
```

Enables `rtk-rewrite` plugin under `%HERMES_HOME%\plugins\rtk-rewrite\`.

## Command Deck integration

Collector contract: `integrations/command-deck/collector-contract/command-desk.js`  
Live collector (sibling repo): `control-center/lib/collectors/command-desk.js`

Monitors in Command Deck `config.json`:

- `http://127.0.0.1:9119/api/status`
- `http://127.0.0.1:8642/health`

Runbooks (Command Deck `server.js` TASKS): `command-desk-doctor`, `command-desk-start`, `command-desk-gateway-start`, `devssd-obsidian-desk-restart`.

## Windows web build

Full Vite build on Windows may fail with `tsc`/`.vite-temp` ENOENT in some npm workspace setups.

**Recommended:**

```powershell
.\scripts\build-command-desk-web.ps1
# or: npm run build:web:desk
```

Uses `vite build --configLoader runner` (see `web/package.json`). Prefers Codex-bundled Node when present, else `node` on PATH.

**Fallback (API-only stub):**

```powershell
.\scripts\bootstrap-web-dist-stub.ps1
command-desk dashboard --port 9119 --no-open --skip-build
```

Stop the dashboard before rebuild if `EPERM` on `hermes_cli/web_dist/assets`.

## Validation

```powershell
.\scripts\validate-command-desk.ps1
# or: npm run validate:desk
```

Checks CLI, doctor, `:9119/api/status`, `:9119/api/devssd/status`, and `web_dist/index.html`.
