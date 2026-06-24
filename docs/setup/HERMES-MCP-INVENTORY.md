# Hermes MCP Inventory

Complete inventory of MCP servers in the DevSSD/Hermes setup.
Generated from the `optional-mcps/` catalog and `~/.cursor/mcp.json`.

## Cursor MCP Environment (source: `~/.cursor/mcp.json`)

These are the MCP servers configured in the user's Cursor IDE. Most are
Node.js wrappers in `C:\Users\Vinicius\Documents\Codex\mcp\`.

| Server | Transport | Auth | Status | Notes |
|--------|-----------|------|--------|-------|
| cursor-app-control | stdio (Cursor-internal) | none | NOT-APPLICABLE | Cursor-only, no Hermes equivalent |
| github | stdio (node.js wrapper → .exe) | GITHUB_PERSONAL_ACCESS_TOKEN | WAITING-CREDENTIAL | Uses Bitwarden SM fallback |
| vercel | HTTP (https://mcp.vercel.com) | VERCEL_TOKEN | WAITING-CREDENTIAL | Remote, always available |
| hetzner | stdio (node.js → hcloud CLI) | HCLOUD_PATH + hcloud context | WAITING-CREDENTIAL | hcloud CLI must be configured |
| openrouter | stdio (node.js) | OPENROUTER_API_KEY | WAITING-CREDENTIAL | Uses Bitwarden SM fallback |
| bitwarden | stdio (node.js → bws.exe) | BWS_ACCESS_TOKEN | WAITING-BITWARDEN-UNLOCK | bw status: unauthenticated |
| google-tools | stdio (npx google-tools-mcp) | Google OAuth | WAITING-CREDENTIAL | Browser OAuth on first use |
| ssh-servers | stdio (node.js) | none (~/.ssh/config) | READY | SSH keys must be in agent |
| dns-domain | stdio (node.js + PowerShell) | none | WAITING-LOCAL-SERVICE (partial) | Resolve-DnsName = Windows-only |
| project-inspector | stdio (node.js) | none | READY | Cross-platform |
| deploy-orchestrator | stdio (node.js) | HCLOUD_PATH | WAITING-CREDENTIAL | Same as hetzner |
| env-manager | stdio (node.js + PowerShell) | none | WAITING-LOCAL-SERVICE (partial) | DPAPI = Windows-only |
| logs | stdio (node.js) | none | WAITING-LOCAL-SERVICE | Log paths Windows-specific |
| mcp-supervisor | stdio (node.js) | none | READY | Meta/health check tool |
| app-control | stdio (node.js + PowerShell COM) | none | WAITING-LOCAL-SERVICE | Windows-only |
| computer-control-center | stdio (node.js + PowerShell) | none | WAITING-LOCAL-SERVICE | Windows-only |
| outlook-desktop | stdio (node.js + COM) | none | WAITING-LOCAL-SERVICE | Windows + Outlook required |
| windows-admin | stdio (node.js + PowerShell) | none | WAITING-LOCAL-SERVICE | Windows-only |
| ps-tasks | stdio (node.js + Task Scheduler) | none | WAITING-LOCAL-SERVICE | Windows-only |

## Hermes Catalog Entries (`optional-mcps/`)

These are the Nous-approved catalog entries added in this PR:

| Entry | Transport | Auth | Platform |
|-------|-----------|------|----------|
| linear | HTTP | OAuth | All |
| n8n | stdio | N8N_API_KEY | All |
| unreal-engine | HTTP | none | All (needs UE editor) |
| github | stdio | GITHUB_PERSONAL_ACCESS_TOKEN | All |
| vercel | HTTP | VERCEL_TOKEN | All |
| hetzner | stdio | HCLOUD_PATH | All (needs hcloud CLI) |
| openrouter | stdio | OPENROUTER_API_KEY | All |
| google-workspace | stdio | Google OAuth | All |
| ssh-servers | stdio | none | All |
| dns-domain | stdio | none | All (Resolve-DnsName: Windows) |
| project-inspector | stdio | none | All |
| deploy-orchestrator | stdio | HCLOUD_PATH | All |
| env-manager | stdio | none | All (DPAPI: Windows) |
| logs | stdio | none | All (paths: Windows stock) |
| mcp-supervisor | stdio | none | All |
| app-control | stdio | none | Windows only |
| computer-control-center | stdio | none | Windows only |
| outlook-desktop | stdio | none | Windows only |
| windows-admin | stdio | none | Windows only |
| ps-tasks | stdio | none | Windows only |
| bitwarden | stdio | BWS_ACCESS_TOKEN | Windows (stock) |

## Credentials Mapping

| Server | Env Var | Source | Status |
|--------|---------|--------|--------|
| github | GITHUB_PERSONAL_ACCESS_TOKEN | Bitwarden SM or env | WAITING-CREDENTIAL |
| vercel | VERCEL_TOKEN | env or Bitwarden SM | WAITING-CREDENTIAL |
| hetzner | HCLOUD_TOKEN | hcloud context | WAITING-CREDENTIAL |
| openrouter | OPENROUTER_API_KEY | Bitwarden SM or env | WAITING-CREDENTIAL |
| bitwarden | BWS_ACCESS_TOKEN | env | WAITING-BITWARDEN-UNLOCK |
| google-workspace | GOOGLE_MCP_PROFILE | env (OAuth cached) | WAITING-CREDENTIAL |
| deploy-orchestrator | HCLOUD_TOKEN | hcloud context | WAITING-CREDENTIAL |

## Notes

- **cursor-app-control**: Cursor IDE internal server. Controls Cursor windows/rules.
  NOT applicable in Hermes — no catalog entry created.
- **Bitwarden SM**: Several servers use `bitwarden-secret-resolver.js` which reads
  secrets from Bitwarden SM. This requires `bw login` + BWS_ACCESS_TOKEN.
  Current `bw status`: `unauthenticated`.
- **Windows-only servers**: The DevSSD custom MCP stack has many Windows-specific
  servers using PowerShell, COM automation, and Task Scheduler. These are marked
  WAITING-LOCAL-SERVICE on non-Windows hosts.
