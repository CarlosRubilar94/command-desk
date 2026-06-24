# Claude Code CLI Provider (`claude-cli`)

## Problem

Direct HTTP calls to `api.anthropic.com` via the `anthropic` provider draw
from the **Extra Usage** pool when the active Claude account is a **Pro**
subscription, not the plan's included usage.  The error returned is:

```
400 — "Third-party apps now draw from your extra usage, not your plan limits.
Add more at claude.ai/settings/usage"
```

The `claude` CLI installed on this machine is authenticated via the Pro
OAuth session and **does not** have this restriction.

## Architecture Decision: Approach A — text-generator mode

Two approaches were evaluated:

### A — Claude CLI as dumb text generator (chosen)

```
Hermes agent loop  →  run_claude_cli_turn()  →  subprocess: claude -p
                                                 --disallowedTools "*"
                                                 --no-session-persistence
```

- All Claude Code tools are **disabled** (`--disallowedTools "*"`).
- Claude CLI acts purely as a language model endpoint: it receives a
  synthesised conversation-history prompt and returns plain text.
- Hermes **retains full control** of the agent loop, tool calls, skills,
  MCP servers, and memory.
- One subprocess per turn (stateless); Claude CLI's session persistence
  is disabled to avoid side-effects.

**Pros:** clean, isolated, reversible; existing `anthropic`/`codex`/`cursor`
providers are completely unaffected; Hermes tools/skills/MCP work normally.

**Cons:** no token streaming in MVP (blocking until Claude responds); no
per-turn context caching; conversation history is synthesised as a text
transcript rather than native multi-turn API messages (some nuance lost).

### B — Claude CLI as full agent (rejected)

```
Hermes agent loop  →  CodexAppServerSession-style session  →  claude subprocess
```

Hermes would hand over the entire turn to a live Claude Code session (like
the `codex_app_server` path does for Codex).  Claude's own tools and MCP
would run instead of Hermes'.

**Rejected because:** two competing agents (Hermes tools vs Claude Code tools)
create prompt conflicts, Hermes skills/memory integration is lost, system-prompt
conflict (each has its own), and the UX breaks for /chat sessions that rely on
Hermes skills.

## Configuration

In `~/.hermes/config.yaml` (or `%LOCALAPPDATA%\hermes\config.yaml`):

```yaml
model:
  provider: claude-cli
  default: claude-sonnet-4-5   # display name only; actual model is Claude CLI's default
  # Optional: override which Claude model the CLI uses (requires --model support)
  # claude_bin: C:\Users\Me\AppData\Roaming\npm\claude.cmd
  # claude_cli_model: claude-opus-4-8
  # Automatic fallback chain when the Pro session/usage/rate limit is hit.
  # Comma-separated ordered list of providers to try on claude-cli failure.
  # Default: openai-codex,cursor-cli (Codex first, then Cursor).
  # Single value still works for backward compat (e.g. "openai-codex").
  # Set to "" or "none" to disable completely.
  # claude_cli_fallback: openai-codex,cursor-cli
```

To revert to direct API:

```yaml
model:
  provider: anthropic
  default: anthropic/claude-sonnet-4.6
```

## Automatic fallback chain (Pro limit → Codex → Cursor)

When the local Claude **Pro** session runs out of quota, `claude -p` exits
non-zero with a stderr notice such as:

```
You've hit your session limit · resets 7:50pm (America/Sao_Paulo)
```

Rather than surfacing a dead end, `run_claude_cli_turn()` walks an ordered
**fallback chain** (default: `openai-codex,cursor-cli`) and returns the first
successful response, prefixed with a short banner:

```
[claude-cli no limite Pro — respondendo via Codex]

<codex answer…>
```

If Codex is also unavailable (not installed / WinError 2), the chain continues
to cursor-cli automatically:

```
[claude-cli no limite Pro — respondendo via Cursor]

<cursor-cli answer…>
```

### How it works

- **Detection** — `_is_usage_limit_error()` matches (case-insensitive)
  `session limit`, `usage limit`, `rate limit`, `limit reached`, `resets`,
  `too many requests`, `quota`, `429`, … in the CLI's stderr/stdout.
- **Chain execution** — `_resolve_fallback_chain(agent)` returns an ordered list
  from `model.claude_cli_fallback` (comma-separated). Each provider is tried in
  order. If a provider is unavailable (binary absent / WinError 2), the chain
  continues. A provider that actually ran and failed is **terminal** — the chain
  stops and the combined error is surfaced.
- **Never silent** — if all providers fail or are absent, the result includes
  actionable hints for each (`npm install -g @openai/codex`, `cursor-agent login`).

### Config

`model.claude_cli_fallback` (read in `agent/agent_init.py`, consumed by
`agent/claude_cli_runtime.py`). Accepts a comma-separated ordered list:

| Value | Effect |
|-------|--------|
| `openai-codex,cursor-cli` (default) | Chain: Codex first, Cursor second |
| `openai-codex` | Codex only (backward compat) |
| `cursor-cli` | Cursor only |
| `cursor-cli,openai-codex` | Cursor first, Codex second |
| `codex`, `codex_app_server` | Aliases for `openai-codex` |
| `""`, `none`, `off` | Fallback **OFF** — original claude-cli error shown |

> Native `fallback_providers` does **not** cover this case: the `claude_cli`
> path returns early in `conversation_loop.run_conversation()` (before the HTTP
> retry loop where `fallback_providers` advancement happens), so the fallback is
> implemented locally in the claude-cli runtime.

## Files changed

| File | Change |
|------|--------|
| `agent/claude_cli_runtime.py` | **New** — `run_claude_cli_turn()` + prompt builder; **+** Codex limit fallback (`_is_usage_limit_error`, `_resolve_codex_fallback`, `_run_codex_fallback`) |
| `agent/agent_init.py` | **+** wire `model.claude_cli_fallback` onto the agent (default `openai-codex`) |
| `agent/conversation_loop.py` | +15 lines — early dispatch when `api_mode == "claude_cli"` |
| `hermes_cli/runtime_provider.py` | +12 lines — `_VALID_API_MODES` entry + short-circuit in `resolve_runtime_provider()` + `claude-cli` branch in `_resolve_runtime_from_pool_entry()` |
| `tests/agent/test_claude_cli_runtime.py` | **New** — offline unit tests (incl. fallback suite) |
| `docs/setup/CLAUDE-CLI-PROVIDER.md` | **New** — this document |

## Invariants / safety

- No modifications to the `anthropic`, `openai-codex`, `cursor`, `openrouter`, or
  any existing provider paths.
- No API key is required; no secret is read, written, or logged.
- The subprocess call is fully isolated: it cannot write to Hermes' credential
  store or interfere with the running dashboard.
- `--no-session-persistence` prevents Claude CLI from creating or resuming
  sessions in `~/.claude/`, so multiple Hermes sessions do not interfere.
- `--disallowedTools "*"` prevents Claude CLI from executing shell commands,
  writing files, or making web requests during the turn.

## Limitations (MVP)

1. **No streaming.** The TUI shows "thinking…" until the subprocess returns.
   Follow-up: use `--output-format stream-json` and parse events.
2. **History as text.** Conversation is rebuilt as a `Human: / Assistant:` 
   transcript — tool-call tool_calls are converted to inline notes.  The 
   native Anthropic multi-turn format is not preserved.
3. **No token accounting.** `api_calls = 1` is reported but token counts are
   not available from `--output-format text`.  Follow-up: parse `stream-json`
   usage events.
4. **Single model per session.** The model is whatever `claude` defaults to
   (or what `--model` specifies).  No mid-session `/model` switching.

## Testing

```powershell
# From the worktree root:
python -m pytest tests/agent/test_claude_cli_runtime.py -v
```

## Follow-up work

- [ ] Streaming via `--output-format stream-json` + TUI delta callback
- [ ] Token usage extraction from stream-json events
- [ ] `/model` switching support via `claude_cli_model` config key
- [ ] Session-resume across turns via `--resume <session_id>` (optional UX)
- [ ] Short in-memory memo of "claude rate-limited until `<reset>`" to skip the
      doomed claude retry on the next turns in the same session (parse the
      `resets <time>` from stderr). Skipped for now to keep the fallback
      localized and side-effect free.
- [ ] Wire `claude_bin` / `claude_cli_model` / `claude_cli_timeout` from
      `model.*` config the same way (currently read via `getattr` defaults only).
