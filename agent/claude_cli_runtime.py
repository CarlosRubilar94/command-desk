"""Claude Code CLI runtime — single-shot provider via subprocess.

Drives one Hermes turn by calling the ``claude`` CLI with ``-p`` (print/
non-interactive mode, uses the local Pro/OAuth session, zero API-key cost).

Design (Approach A — text-generator only):
  - Claude CLI is invoked as a **dumb text generator** with all tools disabled
    via ``--disallowedTools "*"``.
  - Hermes retains full ownership of the conversation loop, tool calls,
    skills, MCP, and memory.  Claude CLI is a drop-in replacement for the
    HTTP Anthropic API call.
  - Streaming: MVP uses ``--output-format text`` (blocking). Streaming via
    ``stream-json`` is left as a follow-up (see CLAUDE-CLI-PROVIDER.md).

One subprocess per turn (stateless from Hermes perspective). Claude CLI's own
session-persistence is disabled with ``--no-session-persistence``.

Why NOT Approach B (full agent hand-over):
  Two competing agents (Hermes tools vs Claude Code tools) cause prompt
  conflicts, duplicate tool surfaces, no Hermes memory integration, and
  fundamentally broken UX for a /chat that already expects Hermes skills.

Called from run_conversation() when ``agent.api_mode == "claude_cli"``.
Returns the same dict shape as the chat_completions / codex_app_server paths.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default binary name; caller can override via config ``model.claude_bin``.
DEFAULT_CLAUDE_BIN = "claude"

# Hard cap on how long we wait for a single-turn CLI response (seconds).
# Most conversational turns finish in <30 s; extended-thinking may need more.
DEFAULT_TIMEOUT = 120

# Maximum bytes of *conversation history* we embed in the prompt to Claude.
# This budget applies ONLY to the middle history turns — the system prompt and
# the current user turn are always preserved in full (truncating either would
# corrupt the request: dropping the system prompt loses Hermes' identity/tools
# context; dropping the current turn loses the user's actual question). Beyond
# this the middle history is truncated gracefully from the front (oldest first).
_HISTORY_MAX_CHARS = 24_000

# Marker inserted when middle history is truncated.
_TRUNCATION_MARKER = "[...earlier turns truncated...]\n\n"


def _find_claude_bin(agent) -> Optional[str]:
    """Return the resolved path to the claude CLI binary, or None."""
    bin_name = (
        str(getattr(agent, "claude_bin", None) or "").strip() or DEFAULT_CLAUDE_BIN
    )
    # Absolute path provided and exists — use directly.
    if os.path.sep in bin_name and os.path.exists(bin_name):
        return bin_name
    return shutil.which(bin_name)


def _build_context_prompt(messages: List[Dict[str, Any]], user_message: str) -> str:
    """Synthesize a plain-text prompt from Hermes message history.

    Claude CLI ``-p`` accepts a single stdin string.  We reconstruct the
    conversation as a Human/Assistant transcript so Claude has context without
    requiring session-resume mechanics.

    Tool-call messages (type assistant with tool_calls, or role tool) are
    converted to a brief «[tool: name → result]» inline note so context is
    preserved without confusing Claude CLI with OpenAI-style tool JSON.
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
                    # Skip image/document blocks — not meaningful as text.
                else:
                    text_parts.append(str(block))
            content = " ".join(text_parts).strip()
        else:
            content = str(content).strip()

        # Skip empty or purely structural messages.
        if not content:
            # Check for tool_calls on assistant messages.
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
            # Embed the system prompt once at the top, clearly labelled.
            system_blocks.append(f"[SYSTEM CONTEXT]\n{content}\n[/SYSTEM CONTEXT]")
        elif role == "user":
            history_lines.append(f"Human: {content}")
        elif role == "assistant":
            history_lines.append(f"Assistant: {content}")
        elif role == "tool":
            # Tool results are already handled via content blocks above;
            # standalone role=tool messages are OpenAI style.
            tool_call_id = str(msg.get("tool_call_id") or "?")
            history_lines.append(f"[tool-result {tool_call_id}: {content[:200]}]")

    system_part = "\n\n".join(system_blocks)
    history_part = "\n\n".join(history_lines)
    # The current user turn is ALWAYS preserved in full — it carries the
    # question Claude must answer this turn.
    current_turn = f"Human: {user_message}\n\nAssistant:"

    # Apply the history budget to the middle turns only, truncating from the
    # front (oldest first). The system prompt and current turn are exempt, so a
    # large Hermes system prompt can never crowd out the user's actual message
    # (previously a >24KB system prompt drove keep_tail negative and dropped the
    # current turn entirely).
    if len(history_part) > _HISTORY_MAX_CHARS:
        keep_tail = max(_HISTORY_MAX_CHARS - len(_TRUNCATION_MARKER), 0)
        history_part = _TRUNCATION_MARKER + history_part[-keep_tail:]

    sections = [s for s in (system_part, history_part, current_turn) if s]
    return "\n\n".join(sections)


def run_claude_cli_turn(
    agent,
    *,
    user_message: str,
    original_user_message: Any,
    messages: List[Dict[str, Any]],
    effective_task_id: str,
    should_review_memory: bool = False,
) -> Dict[str, Any]:
    """Claude CLI single-shot turn.

    Builds a plain-text prompt from conversation history, pipes it to
    ``claude -p``, and returns the same result-dict shape that the
    chat_completions / codex_app_server paths return.

    Called from run_conversation() when agent.api_mode == "claude_cli".
    """
    claude_bin = _find_claude_bin(agent)
    if not claude_bin:
        err = (
            "Claude CLI not found on PATH. "
            "Install Claude Code and ensure `claude` is executable, "
            "or set `model.claude_bin` in config.yaml to the full path."
        )
        logger.error(err)
        return {
            "final_response": f"[claude-cli error] {err}",
            "messages": messages,
            "api_calls": 0,
            "completed": False,
            "partial": True,
            "error": err,
        }

    prompt = _build_context_prompt(messages, user_message)
    timeout = int(getattr(agent, "claude_cli_timeout", None) or DEFAULT_TIMEOUT)

    cmd = [
        claude_bin,
        "-p",                           # non-interactive / print mode
        "--disallowedTools", "*",        # disable ALL Claude Code tools
        "--no-session-persistence",      # stateless — no ~/.claude session files
        "--output-format", "text",       # plain-text response (streaming: follow-up)
    ]

    # Optional: pass model override so we can select e.g. claude-opus-4-8 from config.
    model_override = str(getattr(agent, "claude_cli_model", None) or "").strip()
    if model_override:
        cmd += ["--model", model_override]

    logger.debug(
        "claude-cli turn: bin=%s model_override=%r timeout=%d prompt_chars=%d",
        claude_bin,
        model_override or "(default)",
        timeout,
        len(prompt),
    )

    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        err = f"Claude CLI timed out after {timeout}s"
        logger.error(err)
        return {
            "final_response": f"[claude-cli error] {err}",
            "messages": messages,
            "api_calls": 1,
            "completed": False,
            "partial": True,
            "error": err,
        }
    except OSError as exc:
        err = f"Failed to launch Claude CLI: {exc}"
        logger.error(err)
        return {
            "final_response": f"[claude-cli error] {err}",
            "messages": messages,
            "api_calls": 0,
            "completed": False,
            "partial": True,
            "error": str(exc),
        }

    if proc.returncode != 0:
        stderr_tail = (proc.stderr or "").strip()[-400:]
        err = f"Claude CLI exited {proc.returncode}: {stderr_tail}"
        logger.error(err)
        return {
            "final_response": f"[claude-cli error] {err}",
            "messages": messages,
            "api_calls": 1,
            "completed": False,
            "partial": True,
            "error": err,
        }

    final_text = (proc.stdout or "").strip()
    if not final_text:
        err = "Claude CLI returned empty output"
        logger.warning(err)
        return {
            "final_response": "[claude-cli] (empty response)",
            "messages": messages,
            "api_calls": 1,
            "completed": True,
            "partial": False,
            "error": err,
        }

    # Append the assistant turn to messages so memory/skill review keep working.
    messages.append({"role": "assistant", "content": final_text})

    return {
        "final_response": final_text,
        "messages": messages,
        "api_calls": 1,
        "completed": True,
        "partial": False,
        "error": None,
    }
