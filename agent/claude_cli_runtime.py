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
# Automatic fallback chain when the Claude Pro session/usage/rate limit is hit
# (see docs/setup/CLAUDE-CLI-PROVIDER.md → "Automatic fallback").
#
# Observed live: when the Pro quota is exhausted, ``claude -p`` exits 1 with
# stderr like:
#   "You've hit your session limit · resets 7:50pm (America/Sao_Paulo)"
# We detect that (and any non-zero exit) and route the SAME turn through the
# next provider in the fallback chain (default: Codex → cursor-cli).  The
# fallback ALWAYS prepends a banner — it never swallows the failure silently.
#
# The chain is configured via ``model.claude_cli_fallback`` in config.yaml as
# a comma-separated list of provider names (e.g. "openai-codex,cursor-cli").
# A single value still works for backward compatibility.  Set to "none" / ""
# / "off" to disable fallback entirely.
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

# Config values that disable the fallback.
_FALLBACK_DISABLED_VALUES = {"", "none", "off", "false", "0", "no", "disabled"}
# Aliases → canonical provider names.
_FALLBACK_ALIASES: Dict[str, str] = {
    "openai-codex": "openai-codex",
    "openai_codex": "openai-codex",
    "codex": "openai-codex",
    "codex-cli": "openai-codex",
    "codex_app_server": "openai-codex",
    "codex-app-server": "openai-codex",
    "cursor-cli": "cursor-cli",
    "cursor_cli": "cursor-cli",
    "cursor": "cursor-cli",
}
# Supported providers in the chain.
_SUPPORTED_FALLBACK_PROVIDERS = {"openai-codex", "cursor-cli"}

# Default chain: Codex first, then cursor-cli as second leg.
_DEFAULT_FALLBACK_CHAIN = "openai-codex,cursor-cli"


def _is_usage_limit_error(text: str) -> bool:
    """Return True when ``text`` looks like a Claude usage/session/rate limit."""
    if not text:
        return False
    low = text.lower()
    return any(pattern in low for pattern in _LIMIT_PATTERNS)


def _resolve_codex_fallback(agent) -> str:
    """Normalize the configured claude-cli fallback target (legacy single-provider API).

    Returns ``"openai-codex"`` when the Codex fallback is the *first* entry in
    the chain, or ``""`` when the chain is disabled.  Kept for backward-compat
    with callers that expected a single string.
    """
    chain = _resolve_fallback_chain(agent)
    return chain[0] if chain else ""


def _resolve_fallback_chain(agent) -> List[str]:
    """Return the ordered list of fallback providers for a failed claude-cli turn.

    Reads ``agent.claude_cli_fallback`` (set by agent_init from config.yaml
    ``model.claude_cli_fallback``).  Accepts a comma-separated string of
    provider names; falls back to the module default when absent.

    Default is ON for real agents: when the attribute is absent, ``getattr``
    yields ``_DEFAULT_FALLBACK_CHAIN`` (``"openai-codex,cursor-cli"``).  Test
    doubles (MagicMock) yield a non-string sentinel, treated as disabled so
    unit tests never spawn real subprocesses unless they opt in explicitly.
    """
    raw = getattr(agent, "claude_cli_fallback", _DEFAULT_FALLBACK_CHAIN)
    if not isinstance(raw, str):
        return []
    val = raw.strip().lower()
    if val in _FALLBACK_DISABLED_VALUES:
        return []

    chain: List[str] = []
    seen: set = set()
    for token in val.split(","):
        token = token.strip()
        if not token or token in _FALLBACK_DISABLED_VALUES:
            continue
        canonical = _FALLBACK_ALIASES.get(token)
        if canonical and canonical not in seen:
            chain.append(canonical)
            seen.add(canonical)
        elif canonical is None:
            logger.warning(
                "claude_cli_fallback token %r is not a supported fallback provider "
                "(supported: %s); skipping.",
                token,
                ", ".join(sorted(_SUPPORTED_FALLBACK_PROVIDERS)),
            )
    return chain


def _run_one_fallback(
    agent,
    *,
    provider: str,
    banner: str,
    claude_error: str,
    user_message: str,
    original_user_message: Any,
    messages: List[Dict[str, Any]],
    effective_task_id: str,
    should_review_memory: bool,
) -> Optional[Dict[str, Any]]:
    """Attempt one fallback provider.  Returns the result dict on success/hard
    failure, or ``None`` when the provider is unavailable and the chain should
    continue to the next entry.

    ``None`` means "this provider is absent/unavailable, try next in chain."
    A dict (even a failed one) means "this provider was reached and is the
    terminal result" — the caller must not try further providers.
    """
    if provider == "openai-codex":
        logger.warning("claude-cli failed (%s) — falling back to Codex", claude_error)
        try:
            result = agent._run_codex_app_server_turn(
                user_message=user_message,
                original_user_message=original_user_message,
                messages=messages,
                effective_task_id=effective_task_id,
                should_review_memory=should_review_memory,
            )
        except Exception as exc:
            logger.exception("claude-cli → Codex fallback raised")
            exc_str = str(exc)
            # Missing Codex CLI (FileNotFoundError / WinError 2) — signal
            # "not available" so the chain can try cursor-cli next.
            if isinstance(exc, (FileNotFoundError, OSError)) and (
                "não encontrado" in exc_str
                or "não está no PATH" in exc_str
                or getattr(exc, "errno", None) == 2  # ENOENT / WinError 2
            ):
                logger.warning(
                    "Codex CLI ausente no PATH — continuando cadeia de fallback: %s", exc
                )
                return None  # try next in chain
            combined = f"claude-cli failed ({claude_error}); Codex fallback also failed: {exc}"
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
            # Codex completed but failed (non-zero, etc.) — continue chain
            # only when it looks like a missing binary / install problem.
            low_err = codex_err.lower()
            if any(kw in low_err for kw in (
                "não encontrado", "não está no path", "not found", "winError 2",
                "winerror 2", "enoent",
            )):
                logger.warning(
                    "Codex fallback indisponível (%s) — continuando cadeia de fallback",
                    codex_err,
                )
                return None  # try next in chain
            result["error"] = (
                f"claude-cli failed ({claude_error}); Codex fallback failed: {codex_err}"
            )
            result["final_response"] = (
                "[claude-cli falhou + Codex também falhou]\n\n"
                f"claude-cli: {claude_error}\ncodex: {codex_err}"
            )
            return result

        result["final_response"] = banner + (result.get("final_response") or "")
        return result

    if provider == "cursor-cli":
        logger.warning("Fallback chain: trying cursor-cli after previous providers failed")
        from agent.cursor_cli_runtime import run_cursor_cli_turn

        cursor_banner = "[cursor-cli fallback]\n\n"
        try:
            result = run_cursor_cli_turn(
                agent,
                user_message=user_message,
                original_user_message=original_user_message,
                messages=messages,
                effective_task_id=effective_task_id,
                should_review_memory=should_review_memory,
            )
        except Exception as exc:
            logger.exception("claude-cli → cursor-cli fallback raised")
            combined = f"claude-cli failed ({claude_error}); cursor-cli fallback also failed: {exc}"
            return {
                "final_response": (
                    f"[claude-cli error] {claude_error}\n"
                    f"[cursor-cli fallback error] {exc}"
                ),
                "messages": messages,
                "api_calls": 1,
                "completed": False,
                "partial": True,
                "error": combined,
            }

        if not isinstance(result, dict):
            return {
                "final_response": f"[claude-cli error] {claude_error}",
                "messages": messages,
                "api_calls": 1,
                "completed": False,
                "partial": True,
                "error": claude_error,
            }

        if not result.get("completed"):
            # cursor-agent not installed → signal "not available" so the chain ends.
            cursor_err = result.get("error") or "unknown cursor-cli error"
            low_err = cursor_err.lower()
            if any(kw in low_err for kw in (
                "não encontrado", "not found", "cursor-agent", "install",
            )):
                logger.warning(
                    "cursor-cli fallback indisponível (%s) — fim da cadeia", cursor_err
                )
                # No more providers: return the combined failure.
                return {
                    "final_response": (
                        f"[claude-cli error] {claude_error}\n"
                        f"[cursor-cli fallback error] {cursor_err}\n\n"
                        "Instale cursor-agent: irm 'https://cursor.com/install?win32=true' | iex"
                    ),
                    "messages": messages,
                    "api_calls": 1,
                    "completed": False,
                    "partial": True,
                    "error": f"all fallbacks failed: claude-cli({claude_error}); cursor-cli({cursor_err})",
                }
            result["error"] = (
                f"claude-cli failed ({claude_error}); cursor-cli fallback failed: {cursor_err}"
            )
            result["final_response"] = (
                "[claude-cli falhou + cursor-cli também falhou]\n\n"
                f"claude-cli: {claude_error}\ncursor-cli: {cursor_err}"
            )
            return result

        result["final_response"] = cursor_banner + (result.get("final_response") or "")
        return result

    # Unknown provider — skip silently.
    logger.warning("Unknown fallback provider %r — skipping", provider)
    return None


# Backwards-compat alias: kept so existing call-sites that import
# _run_codex_fallback by name still resolve (e.g. tests).
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
    """Run the Codex fallback leg only (backward-compat wrapper)."""
    result = _run_one_fallback(
        agent,
        provider="openai-codex",
        banner=banner,
        claude_error=claude_error,
        user_message=user_message,
        original_user_message=original_user_message,
        messages=messages,
        effective_task_id=effective_task_id,
        should_review_memory=should_review_memory,
    )
    if result is not None:
        return result
    # Codex unavailable — return a clear hard-error without cursor-cli
    # (the compat wrapper doesn't know about the chain).
    return {
        "final_response": (
            f"[claude-cli error] {claude_error}\n"
            "[codex fallback error] Codex CLI não encontrado/instalado — "
            "instale com: npm install -g @openai/codex e depois rode `codex login`."
        ),
        "messages": messages,
        "api_calls": 1,
        "completed": False,
        "partial": True,
        "error": f"claude-cli failed ({claude_error}); Codex CLI não encontrado.",
        "claude_cli_fallback": "openai-codex",
    }


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

    Walks the fallback chain (default: openai-codex → cursor-cli) until one
    provider succeeds.  The chain is configured via ``model.claude_cli_fallback``
    in config.yaml.  The error is always surfaced, never swallowed.
    """
    chain = _resolve_fallback_chain(agent)
    if not chain:
        return {
            "final_response": f"[claude-cli error] {err}",
            "messages": messages,
            "api_calls": api_calls,
            "completed": False,
            "partial": True,
            "error": err,
        }

    # Codex-specific banners (kept for backward compat with existing tests/logs).
    _banner_limit_codex = "[claude-cli no limite Pro — respondendo via Codex]\n\n"
    _banner_error_codex = "[claude-cli falhou — respondendo via Codex]\n\n"
    _banner_limit_cursor = "[claude-cli no limite Pro — respondendo via Cursor]\n\n"
    _banner_error_cursor = "[claude-cli falhou — respondendo via Cursor]\n\n"
    _banner_limit_generic = "[claude-cli no limite Pro — respondendo via fallback]\n\n"
    _banner_error_generic = "[claude-cli falhou — respondendo via fallback]\n\n"

    def _banner_for(provider: str) -> str:
        if provider == "openai-codex":
            return _banner_limit_codex if is_limit else _banner_error_codex
        if provider == "cursor-cli":
            return _banner_limit_cursor if is_limit else _banner_error_cursor
        return _banner_limit_generic if is_limit else _banner_error_generic

    # Collect actionable hints for each unavailable provider so the final
    # "all failed" message is still helpful even when the chain exhausts.
    unavailable_hints: List[str] = []
    _CODEX_HINT = (
        "Codex CLI não encontrado/instalado — "
        "instale com: npm install -g @openai/codex  "
        "e depois rode `codex login` para autenticar com sua assinatura."
    )
    _CURSOR_HINT = (
        "Cursor CLI (cursor-agent) não encontrado — "
        "instale via: irm 'https://cursor.com/install?win32=true' | iex  "
        "e depois rode: cursor-agent login"
    )

    for provider in chain:
        banner = _banner_for(provider)
        result = _run_one_fallback(
            agent,
            provider=provider,
            banner=banner,
            claude_error=err,
            user_message=user_message,
            original_user_message=original_user_message,
            messages=messages,
            effective_task_id=effective_task_id,
            should_review_memory=should_review_memory,
        )
        if result is not None:
            return result
        # result is None → this provider was unavailable, try next.
        if provider == "openai-codex":
            unavailable_hints.append(_CODEX_HINT)
        elif provider == "cursor-cli":
            unavailable_hints.append(_CURSOR_HINT)

    # All providers in the chain were unavailable — surface actionable hints.
    hints_str = "\n".join(unavailable_hints) if unavailable_hints else "nenhum provedor disponível"
    combined_err = (
        f"claude-cli failed ({err}); all fallback providers unavailable: {hints_str}"
    )
    return {
        "final_response": (
            f"[claude-cli error] {err}\n"
            f"[todos os fallbacks indisponíveis]\n{hints_str}"
        ),
        "messages": messages,
        "api_calls": api_calls,
        "completed": False,
        "partial": True,
        "error": combined_err,
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
