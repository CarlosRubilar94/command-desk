# Cursor CLI Provider (`cursor-cli`)

## Overview

The `cursor-cli` provider drives one Hermes turn via the **`cursor-agent`** CLI
subprocess, using the user's **Cursor subscription session** (no API key).
This mirrors what `claude-cli` does for Claude Code subscribers.

```
Hermes agent loop  →  run_cursor_cli_turn()  →  subprocess: cursor-agent -p
                                                 --output-format text
                                                 --trust
```

Authentication is handled entirely by the user's Cursor subscription login
(`cursor-agent login`). **No `CURSOR_API_KEY` is required or used on this path.**

## Architecture: text-generator mode

Hermes retains full control of the agent loop, tool dispatch, skills, MCP, and
memory. `cursor-agent` acts as a pure language-model endpoint:

- The conversation history is synthesised as a `Human: / Assistant:` transcript.
- `cursor-agent -p` is called **without `--force`**, so it cannot write files
  or execute shell commands (text generation only).
- `--trust` prevents interactive workspace-trust prompts in headless environments.
- One subprocess per turn (stateless).

## Installation

```powershell
# Windows PowerShell — install Cursor CLI
irm 'https://cursor.com/install?win32=true' | iex

# Authenticate with your Cursor subscription (one-time)
cursor-agent login
```

On macOS/Linux:
```bash
curl https://cursor.com/install -fsS | bash
cursor-agent login
```

Verify installation:
```powershell
cursor-agent --version
```

## Configuration

In `~/.hermes/config.yaml` (or `%LOCALAPPDATA%\hermes\config.yaml`):

```yaml
model:
  provider: cursor-cli
  default: cursor-small   # display name only; actual model is cursor-agent's default
  # Optional: override which Cursor model the CLI uses
  # cursor_cli_model: claude-4.6-sonnet
  # cursor_bin: C:\Users\Me\AppData\Local\Programs\cursor-agent\cursor-agent.exe
```

## Role in the fallback chain

`cursor-cli` is also the **second fallback leg** in the claude-cli chain.
When `claude-cli` fails AND `openai-codex` is unavailable, Hermes tries
`cursor-cli` automatically:

```
claude -p fails → openai-codex (Codex CLI) → cursor-agent -p
                           ↑                          ↑
                   (if not installed,          (if not installed,
                    try next)                   chain ends + error)
```

See `docs/setup/CLAUDE-CLI-PROVIDER.md` → "Automatic fallback chain".

## How it authenticates

The `cursor-agent` binary reads the user's Cursor subscription session from
local storage (set by `cursor-agent login`). No environment variable is read.
**Never set `CURSOR_API_KEY`** — this provider intentionally bypasses API-key
authentication; the subscription session is always preferred.

## Error messages

| Situation | Message |
|-----------|---------|
| Binary not on PATH | "Cursor CLI (cursor-agent) não encontrado no PATH. Instale via: irm '…' \| iex  e autentique com: cursor-agent login" |
| Not logged in (exit 1 with "login" in stderr) | "Cursor CLI falhou — parece não autenticado. Execute: cursor-agent login" |
| Timeout | "Cursor CLI timed out after Ns" |

## Files changed

| File | Change |
|------|--------|
| `agent/cursor_cli_runtime.py` | **New** — `run_cursor_cli_turn()` + `_build_context_prompt()` + `_find_cursor_bin()` |
| `agent/agent_init.py` | +20 lines — `cursor-cli` api_mode forcing + keyless init block |
| `agent/conversation_loop.py` | +15 lines — dispatch when `api_mode == "cursor_cli"` |
| `hermes_cli/runtime_provider.py` | +18 lines — `_VALID_API_MODES` + short-circuit + pool-entry branch |
| `agent/auxiliary_client.py` | +20 lines — zero-cost guard (skip aux tasks for cursor-cli) |
| `agent/claude_cli_runtime.py` | +~200 lines — fallback chain extended: codex → cursor-cli |
| `tests/agent/test_cursor_cli_runtime.py` | **New** — offline unit tests |
| `tests/agent/test_fallback_chain.py` | **New** — chain ordering / exhaustion tests |
| `tests/run_agent/test_cursor_cli_init_no_api_key.py` | **New** — keyless init regression tests |

## Invariants / safety

- No API key is required, read, or logged.
- `cursor-agent` cannot write files (no `--force` flag passed).
- Hermes skills, MCP servers, and memory work normally.
- The subprocess is fully isolated from Hermes' credential store.
- Auxiliary tasks (compression, memory review, vision) degrade gracefully to
  no-op when `cursor-cli` is the main provider (no paid fallback to avoid
  surprise billing).

## Limitations (MVP)

1. **No streaming.** The TUI shows "thinking…" until the subprocess returns.
2. **History as text.** Conversation rebuilt as `Human: / Assistant:` transcript
   (tool calls converted to inline notes).
3. **History budget: 8 KB** (tighter than claude-cli's 24 KB) because
   `cursor-agent` receives the prompt as a positional argument rather than
   via stdin.
4. **No token accounting.** `api_calls = 1` is reported; token counts are not
   available from `--output-format text`.

## Testing

```powershell
python -m pytest tests/agent/test_cursor_cli_runtime.py tests/agent/test_fallback_chain.py tests/run_agent/test_cursor_cli_init_no_api_key.py -v
```

## Follow-up work

- [ ] Streaming via `--output-format stream-json`
- [ ] Token usage extraction from stream-json events
- [ ] Test with a real `cursor-agent` login to validate headless invocation
- [ ] Wire `cursor_bin` / `cursor_cli_model` / `cursor_cli_timeout` from
      `model.*` config via proper config loader (currently `getattr` defaults)
