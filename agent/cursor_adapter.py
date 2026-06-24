"""Cursor SDK adapter for Hermes Agent orchestration.

Wraps the ``cursor-sdk`` Python package (pip: ``cursor-sdk``) to expose
Cursor agents as first-class Hermes sub-tasks.  The integration follows
the same lazy-import + fail-open pattern as ``anthropic_adapter.py`` and
``gemini_native_adapter.py`` so the module loads fine when the SDK is absent.

Status: **READY-WAITING-CREDENTIAL**
  Live calls require ``CURSOR_API_KEY`` in the environment (or in the
  Hermes Bitwarden project).  Without it, ``CursorAgentAdapter`` raises
  ``CursorAdapterCredentialError`` on every call that touches the network.
  Import and construction succeed regardless.

Supported operations
--------------------
  start_task     — launch a new local Cursor agent for a prompt
  stream_events  — iterate assistant-message events from a run
  resume_task    — pick up a previously started agent by ID
  cancel_task    — request cancellation of an in-flight run
  get_status     — return the current status of a run
  collect_cost_estimate — return a best-effort token/cost estimate

Auth
----
  Pass ``api_key`` explicitly, or set ``CURSOR_API_KEY`` in the environment.
  Keys live at https://cursor.com/dashboard/integrations.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, Iterator, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy SDK import (same pattern as anthropic_adapter._get_anthropic_sdk)
# ---------------------------------------------------------------------------

_cursor_sdk: Any = ...  # sentinel — None means "tried and absent"


def _get_cursor_sdk() -> Any:
    """Return the ``cursor_sdk`` module, lazily imported.  None if absent."""
    global _cursor_sdk
    if _cursor_sdk is ...:
        try:
            import cursor_sdk as _sdk  # pip: cursor-sdk
            _cursor_sdk = _sdk
        except ImportError:
            logger.debug(
                "cursor-sdk not installed; CursorAgentAdapter will raise on "
                "live calls. Install with: pip install cursor-sdk"
            )
            _cursor_sdk = None
    return _cursor_sdk


# ---------------------------------------------------------------------------
# Public exceptions
# ---------------------------------------------------------------------------


class CursorAdapterError(Exception):
    """Base class for Cursor adapter errors."""


class CursorAdapterCredentialError(CursorAdapterError):
    """Raised when CURSOR_API_KEY is absent or the SDK is not installed."""


class CursorAdapterNotInstalledError(CursorAdapterError):
    """Raised when the cursor-sdk package is not installed."""


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class CursorRunResult:
    """Final result of a Cursor agent run."""

    run_id: str
    agent_id: str
    status: str  # "finished" | "error" | "cancelled"
    result_text: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CursorStatusResult:
    """Snapshot status of an agent or run."""

    agent_id: str
    run_id: Optional[str]
    status: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CursorCostEstimate:
    """Best-effort cost/token estimate for a completed run.

    The cursor-sdk does not expose per-run token counts directly; we
    return what the run result carries and note it as an estimate.
    """

    run_id: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    note: str = "Cursor SDK does not expose granular token counts; values are unavailable."


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class CursorAgentAdapter:
    """Drive Cursor agents from Hermes as orchestration sub-tasks.

    Parameters
    ----------
    api_key:
        Cursor API key.  Defaults to the ``CURSOR_API_KEY`` environment
        variable.  If neither is set, live calls raise
        ``CursorAdapterCredentialError``.
    model:
        Model ID passed to the SDK.  Defaults to ``"composer-2.5"``.
    cwd:
        Working directory for *local* agents.  Defaults to ``os.getcwd()``.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: str = "composer-2.5",
        cwd: Optional[str] = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("CURSOR_API_KEY", "")
        self._model = model
        self._cwd = cwd or os.getcwd()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_sdk(self) -> Any:
        sdk = _get_cursor_sdk()
        if sdk is None:
            raise CursorAdapterNotInstalledError(
                "cursor-sdk is not installed.  "
                "Add it with: pip install cursor-sdk  "
                "Then re-run Hermes."
            )
        return sdk

    def _require_key(self) -> str:
        if not self._api_key:
            raise CursorAdapterCredentialError(
                "CURSOR_API_KEY is not set.  "
                "Export the key or add BWS_ACCESS_TOKEN + Bitwarden project "
                "entry 'CURSOR_API_KEY' for automatic injection.  "
                "Status: READY-WAITING-CREDENTIAL"
            )
        return self._api_key

    def _make_options(self, sdk: Any) -> Any:
        """Build AgentOptions for a local run."""
        return sdk.AgentOptions(
            api_key=self._require_key(),
            model=self._model,
            local=sdk.LocalAgentOptions(cwd=self._cwd),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_task(self, prompt: str) -> CursorRunResult:
        """Launch a Cursor agent for *prompt* and wait for completion.

        Uses ``Agent.prompt`` (one-shot, auto-dispose).  For long-running
        or multi-turn tasks use ``resume_task`` / ``stream_events``.
        """
        sdk = self._require_sdk()
        key = self._require_key()
        try:
            result = sdk.Agent.prompt(
                prompt,
                sdk.AgentOptions(
                    api_key=key,
                    model=self._model,
                    local=sdk.LocalAgentOptions(cwd=self._cwd),
                ),
            )
            return CursorRunResult(
                run_id=getattr(result, "id", ""),
                agent_id=getattr(result, "agent_id", ""),
                status=getattr(result, "status", "finished"),
                result_text=getattr(result, "result", None),
            )
        except Exception as exc:
            _cursor_err = _get_cursor_sdk()
            cursor_exc_cls = getattr(_cursor_err, "CursorAgentError", None) if _cursor_err else None
            if cursor_exc_cls and isinstance(exc, cursor_exc_cls):
                raise CursorAdapterCredentialError(
                    f"Cursor agent startup failed: {exc}"
                ) from exc
            raise CursorAdapterError(f"start_task failed: {exc}") from exc

    def stream_events(
        self, prompt: str
    ) -> Generator[Dict[str, Any], None, CursorRunResult]:
        """Start an agent and yield streaming assistant-message events.

        Yields dicts with at minimum ``{"type": str, "text": str}``.
        After the generator is exhausted, the terminal run result is
        available via ``StopIteration.value``.
        """
        sdk = self._require_sdk()
        key = self._require_key()

        final_result: Optional[CursorRunResult] = None

        with sdk.Agent.create(
            model=self._model,
            api_key=key,
            local=sdk.LocalAgentOptions(cwd=self._cwd),
        ) as agent:
            run = agent.send(prompt)
            agent_id = getattr(agent, "agent_id", "")
            run_id = getattr(run, "id", "")

            for message in run.messages():
                if getattr(message, "type", None) == "assistant":
                    content_blocks = getattr(
                        getattr(message, "message", None), "content", []
                    )
                    for block in content_blocks:
                        if getattr(block, "type", None) == "text":
                            yield {"type": "text", "text": block.text}

            wait_result = run.wait()
            final_result = CursorRunResult(
                run_id=run_id,
                agent_id=agent_id,
                status=getattr(wait_result, "status", "finished"),
                result_text=getattr(wait_result, "result", None),
            )

        return final_result  # accessible as StopIteration.value

    def resume_task(self, agent_id: str, prompt: str) -> CursorRunResult:
        """Resume a previously started agent and send a follow-up prompt."""
        sdk = self._require_sdk()
        key = self._require_key()
        try:
            with sdk.Agent.resume(
                agent_id, sdk.AgentOptions(api_key=key)
            ) as agent:
                run = agent.send(prompt)
                wait_result = run.wait()
                return CursorRunResult(
                    run_id=getattr(run, "id", ""),
                    agent_id=agent_id,
                    status=getattr(wait_result, "status", "finished"),
                    result_text=getattr(wait_result, "result", None),
                )
        except Exception as exc:
            raise CursorAdapterError(f"resume_task failed: {exc}") from exc

    def cancel_task(self, run: Any) -> bool:
        """Request cancellation of *run*.  Returns True if cancel was issued.

        ``run`` should be the SDK run object obtained from a ``stream_events``
        call.  Cancel is a best-effort request; the run may still complete.
        """
        if run is None:
            return False
        if not (hasattr(run, "supports") and run.supports("cancel")):
            logger.debug("Run does not support cancellation: %r", run)
            return False
        try:
            run.cancel()
            return True
        except Exception as exc:
            logger.warning("cancel_task failed: %s", exc)
            return False

    def get_status(self, agent_id: str) -> CursorStatusResult:
        """Return a status snapshot for *agent_id*.

        Uses the ``CursorClient`` low-level API to inspect a live or
        completed agent without re-running it.
        """
        sdk = self._require_sdk()
        key = self._require_key()
        try:
            with sdk.CursorClient.launch_bridge(workspace=self._cwd) as client:
                info = client.agents.get(agent_id)
                return CursorStatusResult(
                    agent_id=agent_id,
                    run_id=None,
                    status=getattr(info, "status", "unknown"),
                    metadata={
                        "model": getattr(info, "model", None),
                        "created_at": str(getattr(info, "created_at", "")),
                    },
                )
        except Exception as exc:
            raise CursorAdapterError(f"get_status failed: {exc}") from exc

    def collect_cost_estimate(self, run_id: str) -> CursorCostEstimate:
        """Return a best-effort cost estimate for a completed run.

        The Cursor SDK does not expose per-run token counts; this method
        returns a placeholder estimate with a clear note.  Future SDK
        versions may expose usage data.
        """
        return CursorCostEstimate(
            run_id=run_id,
            note=(
                "Cursor SDK (cursor-sdk) does not currently expose per-run "
                "token counts or cost data via the Python API.  "
                "Check the Cursor Dashboard for usage metrics."
            ),
        )
