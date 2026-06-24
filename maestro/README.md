# Maestro — Email → WhatsApp daily digest (Phase 1 / MVP)

Maestro is a **thin orchestration layer over Hermes**: it ingests unread/recent
email from one or more accounts, runs a cheap triage pass, reasons over the
triaged material, and delivers a **digest + actionable ideas** to your WhatsApp
self-chat. It reuses Hermes' existing WhatsApp bridge, cron scheduler, MCP and
`.env` — it is not a new service.

> **Phase 1 is strictly READ-ONLY.** No email is ever modified, archived, marked
> read, or deleted. Phase 2 action stubs exist in `actions_phase2.py` but are
> hard-disabled.

Architecture / research background: `docs/automations/maestro-email-whatsapp.md`.

## Pipeline

```
cron (07:00 BRT, no_agent) → maestro.cli run
  1. Ingest (metadata-first, only unread / last N hours, multi-account)
       • Gmail pessoal  → MCP user-google-tools (list_messages format=metadata)
       • Hostinger empresa → IMAP (stdlib imaplib, BODY.PEEK + EXAMINE = read-only)
  2. Normalize → dedupe-by-thread → seen-id cache → hard cap   (token economy)
  3. Triage (cheap): Gemini Flash → priority/category/needs_action  [fallback: heuristic]
  4. Fetch bodies ONLY for items that passed triage (truncated)   (token economy)
  5. Reason: Claude Code CLI headless subprocess (`claude -p`)     [fallback: template]
       → email treated as UNTRUSTED DATA (anti-prompt-injection)
  6. Digest (WhatsApp markdown, chunked) → deliver to self-chat via the bridge
```

Models: **Gemini Flash** for cheap triage (uses `GEMINI_API_KEY`/`GOOGLE_API_KEY`
already in `.env`); **Claude Code CLI** as a headless subprocess for reasoning
(Pro/OAuth — **no API key**, runs on the machine where `claude` is authenticated).

## Running it

```bash
# Fully offline validation with sample data (no creds, never sends WhatsApp):
python -m maestro.cli run --mock --dry-run

# Real read-only dry-run (reads live IMAP/MCP if configured, writes a preview
# file, sends NOTHING):
python -m maestro.cli run --dry-run

# Inspect resolved config (secrets masked):
python -m maestro.cli print-config

# Live (sends the digest to your WhatsApp self-chat):
python -m maestro.cli run            # or: run --live
```

Dry-run writes the digest to `<HERMES_HOME>/maestro/preview/digest-<ts>.md`.

## Environment variables

All secrets are read from `<HERMES_HOME>/.env` (Windows: `%LOCALAPPDATA%\hermes\.env`)
or the process environment — **never hardcoded, never committed**. See
[`.env.example`](./.env.example). Key ones:

### Hostinger "empresa" (IMAP, app password per mailbox)

| Var | Required | Default | Notes |
|---|---|---|---|
| `MAESTRO_HOSTINGER_EMPRESA_USER` | ✅ | — | full mailbox address |
| `MAESTRO_HOSTINGER_EMPRESA_APP_PASSWORD` | ✅ | — | hPanel → Emails → mailbox → app password |
| `MAESTRO_HOSTINGER_EMPRESA_PROVIDER` | — | `hostinger` | **Hostinger-vs-Titan flag**: `hostinger`→`imap.hostinger.com`, `titan`→`imap.titan.email` |
| `MAESTRO_HOSTINGER_EMPRESA_HOST` | — | from provider | explicit host override |
| `MAESTRO_HOSTINGER_EMPRESA_PORT` | — | `993` | |
| `MAESTRO_HOSTINGER_EMPRESA_SSL` | — | `true` | |
| `MAESTRO_HOSTINGER_EMPRESA_MAILBOX` | — | `INBOX` | |

### Gmail pessoal (MCP — no secret stored here; OAuth lives in Hermes' MCP layer)

| Var | Default | Notes |
|---|---|---|
| `MAESTRO_GMAIL_PESSOAL_ENABLED` | `false` | set `true` to enable Gmail ingestion |
| `MAESTRO_GMAIL_MCP_SERVER` | `user-google-tools` | configured MCP server name |
| `MAESTRO_GMAIL_QUERY` | `is:unread newer_than:1d` | Gmail search query |

### Triage / reasoning / delivery / window

| Var | Default | Notes |
|---|---|---|
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | — | Gemini Flash triage (usually already set) |
| `MAESTRO_TRIAGE_MODEL` | `gemini-2.5-flash` | |
| `MAESTRO_REASONING_ENABLED` | `true` | |
| `MAESTRO_CLAUDE_BIN` | `claude` | path/name of the Claude Code CLI |
| `MAESTRO_CLAUDE_ARGS` | `-p` | headless/print flag(s); prompt is piped via stdin |
| `MAESTRO_WHATSAPP_TARGET` | `WHATSAPP_HOME_CHANNEL` | your **own** number (self-chat) |
| `MAESTRO_WHATSAPP_BRIDGE_PORT` | `3000` | Baileys bridge HTTP port |
| `MAESTRO_WINDOW_HOURS` | `24` | only process mail newer than this |
| `MAESTRO_MAX_EMAILS` | `40` | hard cap per run |
| `MAESTRO_BODY_MAX_CHARS` | `1200` | body truncation |
| `MAESTRO_TIMEZONE` | `America/Sao_Paulo` | digest timestamp tz |
| `MAESTRO_DIGEST_HOUR` | `7` | cron hour |
| `MAESTRO_DRY_RUN` | `false` | global preview-only kill-switch |
| `MAESTRO_PHASE2_ACTIONS_ENABLED` | `false` | **keep disabled in Phase 1** |

WhatsApp session credentials live on disk at
`~/.hermes/platforms/whatsapp/session` (managed by the Hermes bridge) — **never
in git**.

## Activation checklist (what the owner must provide)

1. **Hostinger empresa**: in hPanel → Emails → (domain) → mailbox → **App
   passwords** → generate one named `maestro`. Confirm whether the box is
   **Hostinger Email** or **Titan** and set `MAESTRO_HOSTINGER_EMPRESA_PROVIDER`
   accordingly. Put `MAESTRO_HOSTINGER_EMPRESA_USER` / `_APP_PASSWORD` in `.env`.
2. **WhatsApp pairing (self-chat, personal number)**:
   - Start the bridge: `hermes whatsapp` and scan the QR in WhatsApp →
     **Settings → Linked devices**. Your normal WhatsApp keeps working.
   - `WHATSAPP_ENABLED=true`, `WHATSAPP_ALLOWED_USERS=<your number>`,
     and `MAESTRO_WHATSAPP_TARGET=<your number>` (self-chat).
3. **Gemini key**: ensure `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) is in `.env`
   (already used by other Hermes features).
4. **Claude CLI**: make sure `claude` is installed and logged in (Pro) on the
   machine that runs the cron. Verify: `claude -p "responda: ok"`.
5. **Gmail pessoal (optional in MVP)**: set `MAESTRO_GMAIL_PESSOAL_ENABLED=true`
   and make sure the `user-google-tools` MCP is configured + authenticated in
   Hermes (`~/.hermes/config.yaml` → `mcp_servers`). See the note below.
6. **Register the cron job** (does **not** restart the gateway):
   ```bash
   python -m maestro.cli install-cron --hour 7      # writes launcher + job
   python -m maestro.cli install-cron --dry-run     # preview the plan first
   ```
   This writes `<HERMES_HOME>/scripts/maestro_digest.py` and adds a `no_agent`
   cron job (`maestro-daily-digest`, `0 7 * * *`, `deliver=local`). The running
   gateway's ticker picks it up on the next tick. Manage it with
   `hermes cron list` / `pause` / `trigger`.
   > **Timezone:** cron fires in the Hermes-configured timezone. Set Hermes' TZ
   > to `America/Sao_Paulo` (or adjust `MAESTRO_DIGEST_HOUR`) so 07:00 = 07:00 BRT.

## Notes / assumptions

- **Claude CLI invocation**: the full prompt (trusted instructions + a fenced,
  sanitized *untrusted email data* block) is **piped to `claude -p` over stdin**.
  Adjust `MAESTRO_CLAUDE_BIN` / `MAESTRO_CLAUDE_ARGS` if your CLI differs.
- **Gmail-via-MCP live binding**: `gmail_mcp.build_hermes_mcp_client` uses a
  synchronous MCP caller if this Hermes build exposes one
  (`tools.mcp_tool.call_mcp_tool_sync`). If it doesn't, Gmail ingestion is
  **skipped with a warning** (the rest of the digest still runs); finalize the
  binding at activation. IMAP needs no such wiring.
- **Graceful degradation**: a failing account contributes a warning line to the
  digest, never a crash. With zero working accounts you still get a (mostly
  empty) digest.
- **Portability (Hetzner)**: the cron launcher resolves the repo root from
  `MAESTRO_HERMES_ROOT` / `HERMES_SRC_ROOT` (falling back to the install-time
  path), so the same job definition moves to the Hetzner host.

## Tests

```bash
python -m pytest tests/maestro -q
```

Covers normalization/dedupe, heuristic + Gemini triage (mocked HTTP), IMAP
parsing (`.eml` fixtures), Claude CLI invocation (mocked subprocess) +
anti-injection fencing, digest formatting/chunking, delivery, config, the
seen-id cache, cron registration, and the disabled Phase 2 guards. No live
credentials required.
