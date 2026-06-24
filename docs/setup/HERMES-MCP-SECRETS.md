# Hermes MCP Secrets Management

How MCP server credentials are stored and resolved in the Hermes DevSSD setup.

## Principle: `.env` is for secrets

Per the Hermes contribution policy, `~/.hermes/.env` holds only secrets
(API keys, tokens, passwords). Behavioral settings go in `config.yaml`.

MCP server credentials (API keys, tokens) are written to `~/.hermes/.env`
by the installer (`hermes mcp install`, dashboard Install button) and read
at spawn time by `mcp_tool._resolve_mcp_server_config()`.

**`.env` is never committed to git. Never put secret values in config.yaml.**

## Secrets Map (env var names only — never values)

| Server | Env Var | Notes |
|--------|---------|-------|
| github | `GITHUB_PERSONAL_ACCESS_TOKEN` | Fine-grained token, min scopes: repo, read:org |
| vercel | `VERCEL_TOKEN` | Account or team scoped token |
| hetzner | `HCLOUD_TOKEN` | Set via `hcloud context create`, not directly in env |
| openrouter | `OPENROUTER_API_KEY` | From openrouter.ai/keys |
| bitwarden | `BWS_ACCESS_TOKEN` | Bitwarden SM machine account token |
| google-workspace | `GOOGLE_MCP_PROFILE` | Not a secret — just a profile name |
| deploy-orchestrator | `HCLOUD_TOKEN` | Same as hetzner |
| n8n | `N8N_API_KEY`, `N8N_BASE_URL` | N8N_BASE_URL is not secret |

## Bitwarden Secret Manager (DevSSD integration)

Several MCP servers use `bitwarden-secret-resolver.js`, which resolves
secrets through a chain:

```
1. process.env (current shell env)
2. Windows user env (HKCU\Environment via PowerShell)
3. ~/.hermes/.env (Hermes env file)
4. Bitwarden SM (via bws CLI — requires BWS_ACCESS_TOKEN + authenticated bw session)
```

Current Bitwarden status: **unauthenticated** (`bw status` → `{"status":"unauthenticated"}`).

To unlock Bitwarden and enable SM secret resolution:
```powershell
bw login                  # browser-based login
# or if already logged in:
bw unlock                 # enters master password, returns BW_SESSION
$env:BW_SESSION = "..."   # set the session token
bw status                 # confirm: {"status":"unlocked"}
```

After unlocking, servers that were `WAITING_BITWARDEN` will re-check on the
next gateway restart and show `READY` if their secrets are in the SM vault.

## Security Properties

1. **No secrets in config.yaml**: `_save_mcp_server()` stores env vars
   via `save_env_value()` → `~/.hermes/.env`, never in `config.yaml`.

2. **No secrets in API responses**: `_redact_mcp_env()` replaces all env
   values with `"***"` before returning them from any `/api/mcp/*` endpoint.

3. **No secrets in logs**: The MCP tool layer logs server names and tool
   counts, never env var values.

4. **No secrets in git**: `~/.hermes/.env` is in the user's home directory
   and is NOT in any git-tracked repository. Never commit `.env` files.

5. **Security scanning at save time**: `mcp_security.validate_mcp_server_entry()`
   runs on every save to reject exfiltration-shaped commands (shell interpreters
   with egress payloads, June 2026 hermes-0day IOC blocklist).

## Rotating Credentials

To rotate a credential:
```bash
hermes mcp configure <name>   # interactive re-prompt
# or directly:
hermes env set <VARNAME>      # writes to ~/.hermes/.env
```

After rotating, restart the gateway for the new credential to take effect:
```bash
hermes gateway restart
```

## Bitwarden SM vs direct `.env`

| Approach | Pros | Cons |
|----------|------|------|
| Direct `~/.hermes/.env` | Simple, no extra tool | Unencrypted file, no audit trail |
| Bitwarden SM | Encrypted vault, audit logs, rotation | Requires bw login + BWS_ACCESS_TOKEN setup |

DevSSD uses Bitwarden SM as the canonical secret store. The `bitwarden-secret-resolver`
falls back to direct env if Bitwarden is unavailable, so both approaches are
always supported.
