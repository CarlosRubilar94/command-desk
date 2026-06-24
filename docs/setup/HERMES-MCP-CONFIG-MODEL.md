# Hermes MCP Configuration Model

How MCP servers are declared, stored, and consumed by Hermes.

## Storage

MCP servers are stored in two places:

### 1. User config: `~/.hermes/config.yaml`

```yaml
mcp_servers:
  github:
    command: npx
    args: ["-y", "@github/mcp-server", "stdio"]
    enabled: true
  vercel:
    url: https://mcp.vercel.com
    enabled: true
  hetzner:
    command: node
    args: ["C:/Users/Vinicius/Documents/Codex/mcp/hetzner-hcloud-mcp.js"]
    env:
      HCLOUD_PATH: "C:/path/to/hcloud.exe"
    enabled: true
```

Fields per entry:
- `command` — executable for stdio transport
- `args` — argument list for stdio
- `url` — endpoint URL for HTTP transport
- `env` — environment variables (secrets stored in `~/.hermes/.env`, not here)
- `enabled` — whether the server is loaded at gateway startup

### 2. Catalog: `optional-mcps/<name>/manifest.yaml`

The catalog is a collection of Nous-approved MCP servers. Each entry is a
YAML manifest that declares the server's transport, auth requirements, and
install procedure. Catalog entries appear in `hermes mcp catalog` and the
dashboard's Catalog section.

Format: see [optional-mcps/github/manifest.yaml](../../optional-mcps/github/manifest.yaml)

## API Layer

The web server (`hermes_cli/web_server.py`) exposes:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/mcp/servers` | GET | List configured servers (env redacted) |
| `/api/mcp/servers` | POST | Add a new server |
| `/api/mcp/servers/{name}` | DELETE | Remove a server |
| `/api/mcp/servers/{name}/test` | POST | Test connection, return tool list |
| `/api/mcp/servers/{name}/enabled` | PUT | Enable/disable server |
| `/api/mcp/catalog` | GET | List catalog entries |
| `/api/mcp/catalog/install` | POST | Install a catalog entry |
| `/api/mcp/control-center` | GET | Enhanced status: Bitwarden, gateway, per-server chips |

## CLI Commands

```bash
hermes mcp list              # list configured servers
hermes mcp add               # interactive add wizard
hermes mcp remove <name>     # remove a server
hermes mcp test <name>       # test connection
hermes mcp catalog           # browse approved catalog
hermes mcp install <name>    # install from catalog
hermes mcp configure <name>  # reconfigure env vars
```

## Config Persistence

1. `_get_mcp_servers()` — reads `mcp_servers` from `load_config()`
2. `_save_mcp_server(name, config)` — validates via `mcp_security.py`, then
   calls `save_config()`. Runs security checks before writing (exfiltration
   shape, persistence IOC blocklist from the June 2026 hermes-0day campaign).
3. Secrets in `env` are written to `~/.hermes/.env` via `save_env_value()` —
   never into `config.yaml`.

## Transport Support

| Transport | How | Notes |
|-----------|-----|-------|
| stdio | Spawns local process | Uses `mcp.client.stdio.stdio_client()` |
| http | HTTP/SSE or Streamable HTTP | Uses `mcp.client.http` |
| OAuth | Browser flow | Managed by `tools/mcp_oauth.py` + `mcp_oauth_manager` |

## Control Center Status Chips

The `/api/mcp/control-center` endpoint returns per-server status chips:

| Chip | Meaning | Action Required |
|------|---------|----------------|
| `READY` | Server configured, credentials present | None |
| `DEGRADED` | Server running but unhealthy | Check logs |
| `WAITING_CREDENTIAL` | Required env var missing | Set in ~/.hermes/.env |
| `WAITING_SERVICE` | Local service (Windows/Outlook/etc.) not running | Start the service |
| `WAITING_BITWARDEN` | bw is locked/unauthenticated | `bw login` |
| `FAILED` | Last connection attempt failed | Check server logs |
| `DISABLED` | Server is disabled in config | Enable via dashboard |
| `NOT_INSTALLED` | Catalog entry not yet installed | Click Install |
