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
```

To revert to direct API:

```yaml
model:
  provider: anthropic
  default: anthropic/claude-sonnet-4.6
```

## Files changed

| File | Change |
|------|--------|
| `agent/claude_cli_runtime.py` | **New** — `run_claude_cli_turn()` + prompt builder |
| `agent/conversation_loop.py` | +15 lines — early dispatch when `api_mode == "claude_cli"` |
| `hermes_cli/runtime_provider.py` | +12 lines — `_VALID_API_MODES` entry + short-circuit in `resolve_runtime_provider()` + `claude-cli` branch in `_resolve_runtime_from_pool_entry()` |
| `tests/agent/test_claude_cli_runtime.py` | **New** — 17 offline unit tests |
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
