# Hermes Cursor SDK Integration

> File: `agent/cursor_adapter.py`
> Status: **READY-WAITING-CREDENTIAL**

---

## What it does

`CursorAgentAdapter` wraps the `cursor-sdk` Python package to expose Cursor
agents as first-class Hermes sub-tasks.  Hermes can:

- Launch a Cursor agent with a prompt (`start_task`)
- Stream assistant-message events in real time (`stream_events`)
- Resume a previously started agent (`resume_task`)
- Cancel an in-flight run (`cancel_task`)
- Query the current status of an agent (`get_status`)
- Retrieve a cost estimate (placeholder — SDK does not expose token counts yet)

## Installation

```bash
pip install cursor-sdk
```

Then set the API key (key lives at https://cursor.com/dashboard/integrations):

```bash
# Option A — environment variable
export CURSOR_API_KEY="cursor_..."

# Option B — Bitwarden Secrets Manager
# Add CURSOR_API_KEY to your Bitwarden project; Hermes injects it at startup.
```

## Usage example

```python
from agent.cursor_adapter import CursorAgentAdapter, CursorAdapterCredentialError

adapter = CursorAgentAdapter(model="composer-2.5", cwd="/path/to/repo")

# One-shot
result = adapter.start_task("Refactor src/utils.py for readability")
print(result.status, result.result_text)

# Streaming
for event in adapter.stream_events("Find and fix the auth bug"):
    if event["type"] == "text":
        print(event["text"], end="")
```

## Security boundary

- `CursorAgentAdapter` raises `CursorAdapterCredentialError` if `CURSOR_API_KEY` is absent.
- The API key is **never** logged or included in error messages.
- Construction and import succeed even when the key is absent or the SDK is not installed.

## Credential status

| Component | Status |
|---|---|
| `cursor-sdk` package | Not in `pyproject.toml` (optional; lazy-import) |
| `CURSOR_API_KEY` | READY-WAITING-CREDENTIAL — must be set before live calls |

## Tests

```bash
uv run pytest tests/test_cursor_adapter.py -v
# 17 passed
```
