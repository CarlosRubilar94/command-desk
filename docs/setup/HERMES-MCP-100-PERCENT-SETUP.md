# Hermes MCP 100% Setup Guide

Step-by-step guide to get all MCP servers in the DevSSD catalog from
`WAITING-*` to `READY`. Each server's current status is noted.

## Prerequisites

```bash
# Check tool availability
node --version      # v24+
npm --version       # 11+
bw --version        # 2026.5+
hcloud version      # any
```

## Step 1: Unlock Bitwarden (REQUIRED for github, openrouter, bitwarden)

```powershell
# Check current status
bw status
# → {"status":"unauthenticated"} means full login needed

bw login
# Opens browser for authentication

# If already logged in but locked:
bw unlock
# → copy the session token to BW_SESSION

$env:BW_SESSION = "your-session-token-here"
bw status
# → {"status":"unlocked"}
```

**SECURITY**: Never share `BW_SESSION`. It grants full vault read access for
the current session. Treat it like a password.

## Step 2: Configure GitHub MCP

**Status: WAITING-CREDENTIAL**

```bash
# Option A: Direct env var (simpler)
# Add to ~/.hermes/.env:
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token_here

# Option B: Bitwarden SM (after Step 1)
# Store as GITHUB_PERSONAL_ACCESS_TOKEN in your SM vault.
# The bitwarden-secret-resolver reads it automatically.
```

Generate a token at https://github.com/settings/tokens
Required scopes: `repo`, `read:org`, `pull_request`

Then install in Hermes:
```bash
hermes mcp install github
# or via dashboard: http://127.0.0.1:9119/mcp → Catalog → github → Install
```

## Step 3: Configure Vercel MCP

**Status: WAITING-CREDENTIAL**

```bash
# Add to ~/.hermes/.env:
VERCEL_TOKEN=your_vercel_token_here
```

Generate at https://vercel.com/account/tokens

Then install:
```bash
hermes mcp install vercel
```

## Step 4: Configure Hetzner MCP

**Status: WAITING-CREDENTIAL** (requires hcloud CLI context)

```powershell
# 1. Configure hcloud context (stores token in hcloud's own config)
hcloud context create devssd --token YOUR_HCLOUD_TOKEN
hcloud context use devssd

# 2. Set HCLOUD_PATH if hcloud is not on PATH
# Add to ~/.hermes/.env:
HCLOUD_PATH=C:\Users\Vinicius\AppData\Local\Microsoft\WinGet\Packages\HetznerCloud.CLI_Microsoft.Winget.Source_8wekyb3d8bbwe\hcloud.exe
```

Then install:
```bash
hermes mcp install hetzner
```

## Step 5: Configure OpenRouter MCP

**Status: WAITING-CREDENTIAL**

```bash
# Option A: Direct env var
# Add to ~/.hermes/.env:
OPENROUTER_API_KEY=sk-or-your_key_here

# Option B: Bitwarden SM (after Step 1 — automatic via resolver)
```

Generate at https://openrouter.ai/keys

Then install:
```bash
hermes mcp install openrouter
```

## Step 6: Configure Google Workspace MCP

**Status: WAITING-CREDENTIAL** (requires browser OAuth)

```bash
hermes mcp install google-workspace
# On first connection, a browser window opens for Google OAuth authorization.
# After authorizing, the token is cached in the npx package store.
```

Add `GOOGLE_MCP_PROFILE=vinicius` to `~/.hermes/.env` to scope credentials
to a named profile.

**WARNING**: This grants broad Google API access. Review at:
https://myaccount.google.com/permissions

## Step 7: Configure Bitwarden MCP

**Status: WAITING-BITWARDEN-UNLOCK**

Requires BOTH:
1. `bw login` (Step 1)
2. A Bitwarden SM machine account token

```bash
# Add to ~/.hermes/.env:
BWS_ACCESS_TOKEN=your_machine_account_token_here
```

Create a machine account at https://bitwarden.com → Secrets Manager → Machine Accounts

Then install:
```bash
hermes mcp install bitwarden
```

## Step 8: SSH Servers (already READY if SSH is configured)

**Status: READY** (if `~/.ssh/config` has hosts)

No credentials needed. Verify:
```bash
hermes mcp install ssh-servers
hermes mcp test ssh-servers
```

## Step 9: Windows-only servers (Windows hosts only)

The following servers work only on Windows:
- `app-control`, `computer-control-center`, `outlook-desktop`
- `windows-admin`, `ps-tasks`, `dns-domain` (partially), `env-manager` (partially)

**Status: WAITING-LOCAL-SERVICE** on Linux/macOS

On Windows, install:
```powershell
hermes mcp install windows-admin
hermes mcp install ps-tasks
hermes mcp install app-control
hermes mcp install computer-control-center
hermes mcp install outlook-desktop
hermes mcp install env-manager
hermes mcp install dns-domain
hermes mcp install logs
```

For `outlook-desktop`: Microsoft Outlook Desktop must be installed and running.

## Step 10: Meta/utility servers (no credentials)

```bash
hermes mcp install project-inspector    # READY immediately
hermes mcp install mcp-supervisor       # READY immediately
hermes mcp install deploy-orchestrator  # after hetzner/vercel setup
```

## Restart the Gateway

After installing or configuring servers, restart the gateway for changes to take effect:
```bash
hermes gateway restart
```

## Verify

```bash
hermes mcp list          # see all configured servers
hermes mcp test github   # test each server
hermes mcp test vercel

# Or use the dashboard
open http://127.0.0.1:9119/mcp
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `WAITING_BITWARDEN` chip | bw not logged in | `bw login` |
| `WAITING_CREDENTIAL` chip | env var missing | Add to `~/.hermes/.env` |
| `WAITING_SERVICE` chip | Windows service not running | Start Outlook / check PowerShell |
| Server test fails with "spawn error" | Command path wrong | Check `command` in config.yaml |
| Vercel test fails 401 | Token expired | Regenerate at vercel.com |
| Google tools OAuth error | Token expired | Delete cached token, reinstall |

## Security Reminders

- Never commit `~/.hermes/.env` to git
- Never paste `BW_SESSION` into chat or commits
- Rotate `GITHUB_PERSONAL_ACCESS_TOKEN` periodically
- The dashboard `/mcp` redacts all env values — only KEY NAMES are shown
- Run `hermes mcp list` to audit configured servers
