"""Cursor CLI runtime — single-shot provider via subprocess.

Drives one Hermes turn by calling the ``cursor-agent`` CLI with ``-p`` (print/
non-interactive mode, uses the local Cursor subscription session, zero API-key
cost).

Design (Approach A — text-generator only):
  - cursor-agent is invoked as a **dumb text generator**.
  - Hermes retains full ownership of the conversation loop, tool calls,
    skills, MCP, and memory.  cursor-agent is a drop-in replacement for the
    HTTP API call.
  - Streaming: MVP uses ``--output-format text`` (blocking).
  - ``--trust`` avoids workspace-trust prompts in headless environments.
  - No ``--force``: the agent will NOT modify files (read/analyse only),
    mirroring claude-cli's ``--disallowedTools "*"`` approach.

One subprocess per turn (stateless from Hermes perspective).

Authentication:
  The cursor-agent CLI authenticates via the user's existing Cursor
  subscription/login.  No CURSOR_API_KEY is required or supported on this
  path.  If the user has not logged in, the CLI exits non-zero; the error
  message instructs them to run ``cursor-agent login``.

Prompt passing:
  cursor-agent receives the prompt as a positional argument (not via stdin).
  To stay within OS command-line length limits (~32 KB on Windows), the
  conversation history budget is kept at 8 KB (tighter than claude-cli's
  24 KB) while the system prompt and current user turn are always preserved.

Called from run_conversation() when ``agent.api_mode == "cursor_cli"``.
Returns the same dict shape as the chat_completions / codex_app_server paths.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default binary name resolved via shutil.which (handles PATHEXT on Windows:
# cursor-agent.cmd / cursor-agent.exe).
DEFAULT_CURSOR_BIN = "cursor-agent"

# Hard cap on how long we wait for a single-turn CLI response (seconds).
DEFAULT_TIMEOUT = 120

# Maximum bytes of *conversation history* embedded in the prompt argument.
# Tighter than claude-cli (24 KB) because cursor-agent receives the context
# as a command-line argument and OS argument length limits apply (~32 KB on
# Windows, 128 KB on Linux). System prompt + current user turn are exempt.
_HISTORY_MAX_CHARS = 8_000

# Marker inserted when middle history is truncated.
_TRUNCATION_MARKER = "[...earlier turns truncated...]\n\n"

# ---------------------------------------------------------------------------
# Fallback: cursor-cli itself is a *fallback* destination from claude-cli
# (via the chain in claude_cli_runtime.py). When cursor-agent is absent or
# fails, surface a clear actionable message instead of a raw OSError.
# ---------------------------------------------------------------------------

# Banner prepended to fallback answers so the user always knows a fallback ran.
_FALLBACK_BANNER = "[cursor-cli]\n\n"


def _find_cursor_bin(agent) -> Optional[str]:
    """Return the resolved path to the cursor-agent CLI binary, or None.

    Resolves via ``shutil.which`` to honour PATHEXT on Windows
    (finds ``cursor-agent.cmd`` / ``cursor-agent.exe``). An absolute path
    stored in ``agent.cursor_bin`` is used directly when the file exists.
    """
    bin_name = (
        str(getattr(agent, "cursor_bin", None) or "").strip() or DEFAULT_CURSOR_BIN
    )
    # Absolute path provided and exists — use directly.
    if os.path.sep in bin_name and os.path.exists(bin_name):
        return bin_name
    return shutil.which(bin_name)


def _build_context_prompt(messages: List[Dict[str, Any]], user_message: str) -> str:
    """Synthesize a plain-text prompt from Hermes message history.

    cursor-agent ``-p`` receives the prompt as a positional argument.  We
    reconstruct the conversation as a Human/Assistant transcript so the model
    has context without session-resume mechanics.

    Tool-call messages (type assistant with tool_calls, or role tool) are
    converted to a brief «[tool: name → result]» inline note.
    """
    system_blocks: List[str] = []
    history_lines: List[str] = []
    for msg in messages:
        role = str(msg.get("role") or "").lower()
        content = msg.get("content") or ""

        # Stringify content (may be list of blocks or plain string).
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(str(block.get("text") or ""))
                    elif block.get("type") == "tool_result":
                        tool_id = block.get("tool_use_id", "?")
                        result_content = block.get("content") or ""
                        if isinstance(result_content, list):
                            result_content = " ".join(
                                str(b.get("text", "")) for b in result_content
                                if isinstance(b, dict)
                            )
                        text_parts.append(f"[tool-result {tool_id}: {str(result_content)[:200]}]")
                else:
                    text_parts.append(str(block))
            content = " ".join(text_parts).strip()
        else:
            content = str(content).strip()

        # Skip empty or purely structural messages.
        if not content:
            tool_calls = msg.get("tool_calls") or []
            if role == "assistant" and tool_calls:
                names = [
                    str(tc.get("function", {}).get("name", "?"))
                    for tc in tool_calls
                    if isinstance(tc, dict)
                ]
                content = "[used tools: " + ", ".join(names) + "]"
            else:
                continue

        if role == "system":
            system_blocks.append(f"[SYSTEM CONTEXT]\n{content}\n[/SYSTEM CONTEXT]")
        elif role == "user":
            history_lines.append(f"Human: {content}")
        elif role == "assistant":
            history_lines.append(f"Assistant: {content}")
        elif role == "tool":
            tool_call_id = str(msg.get("tool_call_id") or "?")
            history_lines.append(f"[tool-result {tool_call_id}: {content[:200]}]")

    system_part = "\n\n".join(system_blocks)
    history_part = "\n\n".join(history_lines)
    # The current user turn is ALWAYS preserved in full.
    current_turn = f"Human: {user_message}\n\nAssistant:"

    # Apply the history budget to the middle turns only (oldest first).
    if len(history_part) > _HISTORY_MAX_CHARS:
        keep_tail = max(_HISTORY_MAX_CHARS - len(_TRUNCATION_MARKER), 0)
        history_part = _TRUNCATION_MARKER + history_part[-keep_tail:]

    sections = [s for s in (system_part, history_part, current_turn) if s]
    return "\n\n".join(sections)


def _cursor_failure_result(
    *,
    err: str,
    api_calls: int,
    messages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a failure result dict for a cursor-cli error.

    cursor-cli is itself a fallback destination — it does not chain further.
    The error is always surfaced, never swallowed.
    """
    return {
        "final_response": f"[cursor-cli error] {err}",
        "messages": messages,
        "api_calls": api_calls,
        "completed": False,
        "partial": True,
        "error": err,
    }


def run_cursor_cli_turn(
    agent,
    *,
    user_message: str,
    original_user_message: Any,
    messages: List[Dict[str, Any]],
    effective_task_id: str,
    should_review_memory: bool = False,
) -> Dict[str, Any]:
    """Cursor CLI single-shot turn.

    Builds a plain-text prompt from conversation history, passes it to
    ``cursor-agent -p``, and returns the same result-dict shape that the
    chat_completions / codex_app_server paths return.

    Called from run_conversation() when agent.api_mode == "cursor_cli".
    Also called as a fallback leg from claude_cli_runtime when both claude-cli
    and Codex are unavailable.
    """
    cursor_bin = _find_cursor_bin(agent)
    if not cursor_bin:
        err = (
            "Cursor CLI (cursor-agent) não encontrado no PATH. "
            "Instale via: irm 'https://cursor.com/install?win32=true' | iex  "
            "e autentique com: cursor-agent login"
        )
        logger.error(err)
        return _cursor_failure_result(
            err=err,
            api_calls=0,
            messages=messages,
        )

    prompt = _build_context_prompt(messages, user_message)
    timeout = int(getattr(agent, "cursor_cli_timeout", None) or DEFAULT_TIMEOUT)

    cmd = [
        cursor_bin,
        "-p",                           # non-interactive / print mode
        "--output-format", "text",       # plain-text response
        "--trust",                       # trust workspace (no interactive prompt)
        # No --force: text generation only, no file modifications.
        prompt,                          # positional prompt argument
    ]

    # Optional: pass model override from config (e.g. cursor-cli model).
    model_override = str(getattr(agent, "cursor_cli_model", None) or "").strip()
    if model_override:
        # Insert before the prompt argument.
        cmd = cmd[:-1] + ["--model", model_override, prompt]

    logger.debug(
        "cursor-cli turn: bin=%s model_override=%r timeout=%d prompt_chars=%d",
        cursor_bin,
        model_override or "(default)",
        timeout,
        len(prompt),
    )

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        err = f"Cursor CLI timed out after {timeout}s"
        logger.error(err)
        return _cursor_failure_result(
            err=err,
            api_calls=1,
            messages=messages,
        )
    except (OSError, FileNotFoundError) as exc:
        # WinError 2 / ENOENT: binary vanished or can't be executed.
        err_detail = str(exc)
        err = (
            f"Cursor CLI não pôde ser executado: {err_detail}. "
            "Verifique se cursor-agent está instalado e no PATH."
        )
        logger.error(err)
        return _cursor_failure_result(
            err=err,
            api_calls=0,
            messages=messages,
        )

    if proc.returncode != 0:
        stderr_full = (proc.stderr or "").strip()
        stderr_tail = stderr_full[-400:]
        stdout_tail = (proc.stdout or "").strip()[-200:]
        combined = f"{stderr_tail}\n{stdout_tail}".strip()
        err = f"Cursor CLI exited {proc.returncode}: {combined}"
        logger.error(err)
        # Check for auth/login errors so the message is actionable.
        low = combined.lower()
        if any(kw in low for kw in ("login", "auth", "sign in", "not logged", "unauthorized", "401")):
            err = (
                f"Cursor CLI falhou (exit {proc.returncode}) — parece não autenticado. "
                "Execute: cursor-agent login  (usa sua assinatura Cursor, sem API key)"
            )
        return _cursor_failure_result(
            err=err,
            api_calls=1,
            messages=messages,
        )

    final_text = (proc.stdout or "").strip()
    if not final_text:
        err = "Cursor CLI returned empty output"
        logger.warning(err)
        return {
            "final_response": "[cursor-cli] (empty response)",
            "messages": messages,
            "api_calls": 1,
            "completed": True,
            "partial": False,
            "error": err,
        }

    # Append the assistant turn so memory/skill review keep working.
    messages.append({"role": "assistant", "content": final_text})

    return {
        "final_response": final_text,
        "messages": messages,
        "api_calls": 1,
        "completed": True,
        "partial": False,
        "error": None,
    }
