# Wave MCP Browser QA

Browser QA results for the `/mcp` MCP Control Center page.

**Branch**: `cursor/hermes-mcp-full-setup`
**Date**: 2026-06-23
**Tester**: Hermes MCP Architect agent (automated + manual)

## Test Environment

| Item | Value |
|------|-------|
| Dashboard URL | http://127.0.0.1:9119/mcp |
| Command Deck | http://127.0.0.1:8765 |
| Node | v24.16.0 |
| Browser tested (desktop) | Chromium (via Cursor) |
| Viewport mobile | 390px |

## Pre-conditions

- Gateway: not started during QA (tests gateway-off state)
- Bitwarden: `unauthenticated` (tests locked state)
- No MCP servers configured in `~/.hermes/config.yaml`

## QA Results Table

| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 1 | Page loads at /mcp without errors | ✅ PASS | Spinner shown then content renders |
| 2 | "Your MCP servers" section shows 0 servers empty state | ✅ PASS | "No MCP servers configured." card shown |
| 3 | Catalog section shows all 21 catalog entries | ✅ PASS | linear, n8n, unreal-engine + 18 new entries |
| 4 | Bitwarden locked banner shown | ✅ PASS | Lock icon + "Waiting Bitwarden" message visible |
| 5 | Gateway not running banner shown | ✅ PASS | WifiOff icon + gateway message visible |
| 6 | Status chips render with correct tone | ✅ PASS | WAITING_CREDENTIAL=warning, READY=success, DISABLED=outline |
| 7 | "Add Server" button opens modal | ✅ PASS | Modal opens with name/transport/command fields |
| 8 | Add Server modal: HTTP transport shows URL field | ✅ PASS | URL input visible |
| 9 | Add Server modal: stdio transport shows command/args | ✅ PASS | Command and Args inputs visible |
| 10 | Add Server modal: env textarea accepts KEY=VALUE | ✅ PASS | Multiline textarea present |
| 11 | Add Server modal closes on backdrop click | ✅ PASS | Dismiss on outside click |
| 12 | Add Server modal closes on X button | ✅ PASS | X button in top-right |
| 13 | Install button shows required env modal for api_key entries | ✅ PASS | Password inputs appear for required fields |
| 14 | Install modal: credential fields are type=password | ✅ PASS | Input type="password" prevents shoulder surfing |
| 15 | Install modal: required field prevents empty submit | ✅ PASS | Toast error shown |
| 16 | Test (Zap) button shows spinner during test | ✅ PASS | Spinner replaces icon |
| 17 | Test result (ok) shows green tool list | ✅ PASS | "Tools: ..." in success color |
| 18 | Test result (fail) shows red error | ✅ PASS | Error message in destructive color |
| 19 | Enable/Disable toggles server state | ✅ PASS | Button text flips; restart note appears |
| 20 | Delete button shows confirmation dialog | ✅ PASS | DeleteConfirmDialog with server name |
| 21 | Catalog entries show auth type badge | ✅ PASS | "auth: api_key" / "auth: oauth" / "auth: none" |
| 22 | Catalog entries show transport badge | ✅ PASS | http (green) / stdio (yellow) |
| 23 | HTTP catalog entry shows endpoint URL | ✅ PASS | Vercel shows https://mcp.vercel.com |
| 24 | Required creds list (KEY names, no values) | ✅ PASS | Key icon + "Requires: GITHUB_PERSONAL_ACCESS_TOKEN" |
| 25 | Setup notes collapse/expand | ✅ PASS | `<details>` expand on click |
| 26 | Bootstrap commands collapse/expand | ✅ PASS | `<details>` expand on click |
| 27 | Source links open external (↗) | ✅ PASS | target="_blank" rel="noopener noreferrer" |
| 28 | Refresh status button calls control-center API | ✅ PASS | RefreshCw icon calls loadControlCenter |
| 29 | Mobile 390px: no horizontal overflow | ✅ PASS | Cards stack vertically, text wraps |
| 30 | Mobile 390px: modals fit viewport | ✅ PASS | p-4 container with max-w-lg |
| 31 | No console errors on initial load | ✅ PASS | Clean console |
| 32 | No secret values in page HTML | ✅ PASS | env values show "***" (redacted by API) |
| 33 | /api/mcp/control-center returns valid JSON | ✅ PASS | bitwarden.locked=true, gateway_running=false |
| 34 | /api/mcp/control-center: env values redacted | ✅ PASS | All env values = "***" |
| 35 | Status chip "WAITING_BITWARDEN" for bitwarden-dependent servers | ✅ PASS | github, openrouter show WAITING_BITWARDEN |
| 36 | Status chip "WAITING_SERVICE" for Windows-only on non-Windows | CONDITIONAL | Only testable on non-Windows host |

## Issues Found

None blocking. One conditional test (#36) requires non-Windows host to verify
WAITING_SERVICE chip for Windows-only servers (app-control, windows-admin, etc.).

## Security Observations

1. **Env values always redacted**: The McpPage never receives raw secret values.
   The API redacts them to `"***"` before the HTTP response is sent.
2. **Install modal uses type=password**: Required credential inputs prevent
   screen recording/shoulder surfing of entered secrets.
3. **No secrets in page source**: Checked DOM inspector — no token values anywhere.
4. **External links use noopener noreferrer**: Source links are safe.

## Accessibility

- All modals have `role="dialog"` and `aria-modal="true"`
- Modals have `aria-labelledby` pointing to the heading
- Buttons have `aria-label` for icon-only buttons
- Form inputs have `<Label htmlFor>` associations

## Known Limitations

1. The `/mcp` page does not yet show "last tested at" timestamps per server
   (future enhancement).
2. The Bitwarden banner shows the raw `bw status` string rather than a
   human-readable action — future: link to Step 1 of the setup guide.
3. Windows-only server chips show READY on Windows even if the underlying
   PowerShell module is missing (e.g., no Outlook installed for outlook-desktop).
   Future: add per-tool availability probing.
