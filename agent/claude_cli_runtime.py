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

# ---------------------------------------------------------------------------
# Automatic fallback to Codex when the Claude Pro session/usage/rate limit is
# hit (see docs/setup/CLAUDE-CLI-PROVIDER.md → "Automatic fallback").
#
# Observed live: when the Pro quota is exhausted, ``claude -p`` exits 1 with
# stderr like:
#   "You've hit your session limit · resets 7:50pm (America/Sao_Paulo)"
# We detect that (and any non-zero exit) and route the SAME turn through the
# Codex app-server runtime, which uses the user's Codex subscription/CLI and
# needs no API key.  The fallback ALWAYS prepends a banner — it never swallows
# the failure silently.
# ---------------------------------------------------------------------------

# Case-insensitive substrings that mark a usage/session/rate limit.
_LIMIT_PATTERNS = (
    "session limit",
    "usage limit",
    "rate limit",
    "rate-limit",
    "ratelimit",
    "limit reached",
    "reached your limit",
    "resets",
    "too many requests",
    "quota",
    "429",
)

# Banner prepended to the Codex answer so the user always sees a fallback ran.
_FALLBACK_BANNER_LIMIT = "[claude-cli no limite Pro — respondendo via Codex]\n\n"
_FALLBACK_BANNER_ERROR = "[claude-cli falhou — respondendo via Codex]\n\n"

# Config values that disable the fallback.
_FALLBACK_DISABLED_VALUES = {"", "none", "off", "false", "0", "no", "disabled"}
# Config values that select the Codex app-server fallback.
_FALLBACK_CODEX_VALUES = {
    "openai-codex",
    "openai_codex",
    "codex",
    "codex-cli",
    "codex_app_server",
    "codex-app-server",
}


def _is_usage_limit_error(text: str) -> bool:
    """Return True when ``text`` looks like a Claude usage/session/rate limit."""
    if not text:
        return False
    low = text.lower()
    return any(pattern in low for pattern in _LIMIT_PATTERNS)


def _resolve_codex_fallback(agent) -> str:
    """Normalize the configured claude-cli fallback target.

    Returns ``"openai-codex"`` when the Codex fallback is enabled, or ``""``
    when it is disabled / unconfigured / unsupported.

    Default is ON for real agents: when the attribute is absent, ``getattr``
    yields the ``"openai-codex"`` default string.  Test doubles (MagicMock)
    yield a non-string sentinel, which is treated as disabled so unit tests
    never spawn a real Codex subprocess unless they opt in with an explicit
    string value.
    """
    raw = getattr(agent, "claude_cli_fallback", "openai-codex")
    if not isinstance(raw, str):
        return ""
    val = raw.strip().lower()
    if val in _FALLBACK_DISABLED_VALUES:
        return ""
    if val in _FALLBACK_CODEX_VALUES:
        return "openai-codex"
    logger.warning(
        "claude_cli_fallback=%r is not a supported fallback provider "
        "(only 'openai-codex'); treating claude-cli failure as a hard error.",
        raw,
    )
    return ""


def _run_codex_fallback(
    agent,
    *,
    banner: str,
    claude_error: str,
    user_message: str,
    original_user_message: Any,
    messages: List[Dict[str, Any]],
    effective_task_id: str,
    should_review_memory: bool,
) -> Dict[str, Any]:
    """Route a failed claude-cli turn through the Codex app-server runtime.

    Reuses the exact path the conversation loop uses for ``codex_app_server``
    (``agent._run_codex_app_server_turn`` →
    ``agent.codex_runtime.run_codex_app_server_turn``), which drives the local
    Codex CLI subprocess and requires **no API key** (the user's Codex
    subscription/OAuth).  ``banner`` is prepended to the Codex answer so the
    user always sees that a fallback occurred — the failure is never silent.
    """
    logger.warning("claude-cli failed (%s) — falling back to Codex", claude_error)
    try:
        result = agent._run_codex_app_server_turn(
            user_message=user_message,
            original_user_message=original_user_message,
            messages=messages,
            effective_task_id=effective_task_id,
            should_review_memory=should_review_memory,
        )
    except Exception as exc:  # never let the fallback hide the original error
        logger.exception("claude-cli → Codex fallback raised")
        combined = (
            f"claude-cli failed ({claude_error}); "
            f"Codex fallback also failed: {exc}"
        )
        return {
            "final_response": (
                f"[claude-cli error] {claude_error}\n"
                f"[codex fallback error] {exc}"
            ),
            "messages": messages,
            "api_calls": 1,
            "completed": False,
            "partial": True,
            "error": combined,
            "claude_cli_fallback": "openai-codex",
        }

    if not isinstance(result, dict):
        # Defensive: a misconfigured forwarder returned a non-dict.
        return {
            "final_response": f"[claude-cli error] {claude_error}",
            "messages": messages,
            "api_calls": 1,
            "completed": False,
            "partial": True,
            "error": claude_error,
        }

    result["claude_cli_fallback"] = "openai-codex"
    if not result.get("completed"):
        codex_err = result.get("error") or "unknown Codex error"
        result["error"] = (
            f"claude-cli failed ({claude_error}); "
            f"Codex fallback failed: {codex_err}"
        )
        result["final_response"] = (
            "[claude-cli falhou + Codex também falhou]\n\n"
            f"claude-cli: {claude_error}\n"
            f"codex: {codex_err}"
        )
        return result

    result["final_response"] = banner + (result.get("final_response") or "")
    return result


def _claude_failure_result(
    agent,
    *,
    err: str,
    is_limit: bool,
    api_calls: int,
    user_message: str,
    original_user_message: Any,
    messages: List[Dict[str, Any]],
    effective_task_id: str,
    should_review_memory: bool,
) -> Dict[str, Any]:
    """Result builder for a claude-cli failure.

    When the Codex fallback is enabled, route the same turn to Codex (with a
    clear banner).  Otherwise return the original claude-cli error unchanged —
    the error is always surfaced, never swallowed.
    """
    fallback = _resolve_codex_fallback(agent)
    if fallback == "openai-codex":
        banner = _FALLBACK_BANNER_LIMIT if is_limit else _FALLBACK_BANNER_ERROR
        return _run_codex_fallback(
            agent,
            banner=banner,
            claude_error=err,
            user_message=user_message,
            original_user_message=original_user_message,
            messages=messages,
            effective_task_id=effective_task_id,
            should_review_memory=should_review_memory,
        )
    return {
        "final_response": f"[claude-cli error] {err}",
        "messages": messages,
        "api_calls": api_calls,
        "completed": False,
        "partial": True,
        "error": err,
    }


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
        return _claude_failure_result(
            agent,
            err=err,
            is_limit=False,
            api_calls=0,
            user_message=user_message,
            original_user_message=original_user_message,
            messages=messages,
            effective_task_id=effective_task_id,
            should_review_memory=should_review_memory,
        )

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
        return _claude_failure_result(
            agent,
            err=err,
            is_limit=False,
            api_calls=1,
            user_message=user_message,
            original_user_message=original_user_message,
            messages=messages,
            effective_task_id=effective_task_id,
            should_review_memory=should_review_memory,
        )
    except OSError as exc:
        err = f"Failed to launch Claude CLI: {exc}"
        logger.error(err)
        return _claude_failure_result(
            agent,
            err=err,
            is_limit=False,
            api_calls=0,
            user_message=user_message,
            original_user_message=original_user_message,
            messages=messages,
            effective_task_id=effective_task_id,
            should_review_memory=should_review_memory,
        )

    if proc.returncode != 0:
        stderr_full = (proc.stderr or "").strip()
        stderr_tail = stderr_full[-400:]
        err = f"Claude CLI exited {proc.returncode}: {stderr_tail}"
        logger.error(err)
        # Detect the Pro session/usage/rate limit from stderr (and stdout, in
        # case the CLI prints the notice there) so we pick the right banner.
        is_limit = _is_usage_limit_error(
            f"{stderr_full}\n{(proc.stdout or '')}"
        )
        return _claude_failure_result(
            agent,
            err=err,
            is_limit=is_limit,
            api_calls=1,
            user_message=user_message,
            original_user_message=original_user_message,
            messages=messages,
            effective_task_id=effective_task_id,
            should_review_memory=should_review_memory,
        )

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
