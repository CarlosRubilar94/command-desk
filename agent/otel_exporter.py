"""OpenTelemetry trace/span exporter for Hermes observability.

Wraps the ``opentelemetry-sdk`` + ``opentelemetry-exporter-otlp-proto-grpc``
(or HTTP) packages to emit traces from key Hermes operations to an OTLP
collector.

**DEFAULT-OFF** — the exporter is a no-op unless explicitly enabled via:
  * ``HERMES_OTEL_ENABLED=1`` environment variable, OR
  * ``observability.otel.enabled: true`` in config.yaml.

Security
--------
  * NO secret-shaped attribute values are emitted in spans.
  * ``_sanitize_attributes`` scrubs common credential patterns before export.
  * Span names include operation type + model name; user prompt text is
    NEVER included unless ``HERMES_OTEL_INCLUDE_PROMPTS=1`` is explicitly
    set (default False).

Lazy SDK import
---------------
Same pattern as ``anthropic_adapter`` — the ``opentelemetry-sdk`` and
exporter packages are optional dependencies.  If absent, all public API
returns no-op stubs.  Install with:
  pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http

Usage
-----
    from agent.otel_exporter import HermesOtelExporter, SpanContext

    exporter = HermesOtelExporter.from_env()
    with exporter.start_span("llm_call", {"model": "gpt-4o", "provider": "openai"}) as span:
        # ... do work ...
        exporter.record_usage(span, input_tokens=100, output_tokens=50)
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, Iterator, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Secret scrubbing
# ---------------------------------------------------------------------------

_SECRET_ATTR_PATTERN = re.compile(
    r"""(?xi)
    (?: api[_\-]?key | access[_\-]?token | password | secret | bearer |
        sk- | ghp_ | cursor_ | AKIA[0-9A-Z]{16} | -----BEGIN |
        authorization | credential )
    """,
    re.IGNORECASE,
)

# Attribute KEYS that should never appear in spans
_BLOCKED_ATTR_KEYS = frozenset(
    {
        "api_key", "access_token", "password", "secret", "token",
        "authorization", "credential", "bearer", "auth",
    }
)


def _sanitize_attributes(attrs: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of *attrs* with secret-shaped keys/values removed.

    Keys matching _BLOCKED_ATTR_KEYS are dropped entirely.
    String values that look like secrets are replaced with ``"[REDACTED]"``.
    """
    result: Dict[str, Any] = {}
    for k, v in attrs.items():
        k_lower = k.lower()
        if k_lower in _BLOCKED_ATTR_KEYS:
            continue
        if isinstance(v, str) and _SECRET_ATTR_PATTERN.search(v):
            result[k] = "[REDACTED]"
        else:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# Lazy OTEL SDK import
# ---------------------------------------------------------------------------

_otel_sdk: Any = ...  # sentinel


def _get_otel() -> Optional[Any]:
    """Return a namespace with trace/resource/exporter; None if absent."""
    global _otel_sdk
    if _otel_sdk is ...:
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import (
                BatchSpanProcessor,
                ConsoleSpanExporter,
                SimpleSpanProcessor,
            )
            from opentelemetry.sdk.resources import Resource

            # Try OTLP HTTP exporter; fall back to console on ImportError
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )
            except ImportError:
                OTLPSpanExporter = None  # type: ignore[assignment]

            import types
            ns = types.SimpleNamespace(
                trace=trace,
                TracerProvider=TracerProvider,
                BatchSpanProcessor=BatchSpanProcessor,
                SimpleSpanProcessor=SimpleSpanProcessor,
                ConsoleSpanExporter=ConsoleSpanExporter,
                Resource=Resource,
                OTLPSpanExporter=OTLPSpanExporter,
            )
            _otel_sdk = ns
        except ImportError:
            logger.debug(
                "opentelemetry-sdk not installed; HermesOtelExporter is a no-op. "
                "Install with: pip install opentelemetry-sdk "
                "opentelemetry-exporter-otlp-proto-http"
            )
            _otel_sdk = None
    return _otel_sdk  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class OtelConfig:
    """Resolved OTEL configuration."""

    enabled: bool = False
    endpoint: str = "http://localhost:4318"  # OTLP HTTP default
    service_name: str = "hermes-agent"
    include_prompts: bool = False  # opt-in to include prompt text in spans
    backend: str = "otlp"  # "otlp" | "console"

    @classmethod
    def from_env(cls) -> "OtelConfig":
        """Build config from environment variables."""
        return cls(
            enabled=os.environ.get("HERMES_OTEL_ENABLED", "").lower()
            in ("1", "true", "yes"),
            endpoint=os.environ.get(
                "HERMES_OTEL_ENDPOINT", "http://localhost:4318"
            ),
            service_name=os.environ.get("HERMES_OTEL_SERVICE_NAME", "hermes-agent"),
            include_prompts=os.environ.get(
                "HERMES_OTEL_INCLUDE_PROMPTS", ""
            ).lower()
            in ("1", "true", "yes"),
            backend=os.environ.get("HERMES_OTEL_BACKEND", "otlp").lower(),
        )


# ---------------------------------------------------------------------------
# No-op span context for when OTEL is disabled / unavailable
# ---------------------------------------------------------------------------


class _NoopSpan:
    """Placeholder span that accepts all operations silently."""

    def set_attribute(self, key: str, value: Any) -> None:  # noqa: ARG002
        pass

    def set_status(self, *args: Any, **kwargs: Any) -> None:
        pass

    def record_exception(self, exc: Exception, **kwargs: Any) -> None:  # noqa: ARG002
        pass

    def end(self) -> None:
        pass


# ---------------------------------------------------------------------------
# HermesOtelExporter
# ---------------------------------------------------------------------------


class HermesOtelExporter:
    """Emit OpenTelemetry traces for key Hermes operations.

    When disabled (default) all operations are no-ops and add zero overhead.
    """

    def __init__(self, config: OtelConfig) -> None:
        self._config = config
        self._tracer: Optional[Any] = None
        self._provider: Optional[Any] = None

        if config.enabled:
            self._setup_provider()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "HermesOtelExporter":
        """Create an exporter configured from environment variables."""
        return cls(OtelConfig.from_env())

    @classmethod
    def from_config_dict(cls, cfg: Dict[str, Any]) -> "HermesOtelExporter":
        """Create from a parsed config.yaml ``observability.otel`` dict."""
        otel_cfg = cfg.get("observability", {}).get("otel", {})
        config = OtelConfig(
            enabled=bool(otel_cfg.get("enabled", False)),
            endpoint=str(
                otel_cfg.get("endpoint", "http://localhost:4318")
            ),
            service_name=str(otel_cfg.get("service_name", "hermes-agent")),
            include_prompts=bool(otel_cfg.get("include_prompts", False)),
            backend=str(otel_cfg.get("backend", "otlp")).lower(),
        )
        return cls(config)

    # ------------------------------------------------------------------
    # Internal setup
    # ------------------------------------------------------------------

    def _setup_provider(self) -> None:
        otel = _get_otel()
        if otel is None:
            logger.warning(
                "HERMES_OTEL_ENABLED=1 but opentelemetry-sdk is not installed. "
                "Install: pip install opentelemetry-sdk "
                "opentelemetry-exporter-otlp-proto-http"
            )
            self._config = OtelConfig(enabled=False)
            return

        try:
            resource = otel.Resource.create(
                {
                    "service.name": self._config.service_name,
                    "service.version": _hermes_version(),
                }
            )
            provider = otel.TracerProvider(resource=resource)

            if self._config.backend == "console":
                processor = otel.SimpleSpanProcessor(otel.ConsoleSpanExporter())
            else:
                if otel.OTLPSpanExporter is None:
                    logger.warning(
                        "OTLP exporter not available; falling back to console. "
                        "Install: pip install opentelemetry-exporter-otlp-proto-http"
                    )
                    processor = otel.SimpleSpanProcessor(otel.ConsoleSpanExporter())
                else:
                    span_exporter = otel.OTLPSpanExporter(
                        endpoint=self._config.endpoint
                    )
                    processor = otel.BatchSpanProcessor(span_exporter)

            provider.add_span_processor(processor)
            self._provider = provider
            self._tracer = otel.trace.get_tracer(
                "hermes.agent", tracer_provider=provider
            )
            logger.info(
                "OTEL exporter initialised — backend=%s endpoint=%s",
                self._config.backend,
                self._config.endpoint,
            )
        except Exception as exc:
            logger.warning("OTEL provider setup failed: %s", exc)
            self._config = OtelConfig(enabled=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._config.enabled and self._tracer is not None

    @contextmanager
    def start_span(
        self,
        operation: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Generator[Any, None, None]:
        """Context manager that creates a span for *operation*.

        When disabled, yields a ``_NoopSpan`` so callers need not check
        ``enabled`` before using the span.

        Attributes are sanitized before being added to the span; secret-shaped
        values are replaced with ``"[REDACTED]"``.
        """
        if not self.enabled:
            yield _NoopSpan()
            return

        otel = _get_otel()
        if otel is None:
            yield _NoopSpan()
            return

        safe_attrs = _sanitize_attributes(attributes or {})

        with self._tracer.start_as_current_span(operation) as span:
            for k, v in safe_attrs.items():
                try:
                    span.set_attribute(k, v)
                except Exception:
                    pass
            try:
                yield span
            except Exception as exc:
                try:
                    span.record_exception(exc)
                    from opentelemetry.trace import StatusCode

                    span.set_status(StatusCode.ERROR, str(exc))
                except Exception:
                    pass
                raise

    def record_usage(
        self,
        span: Any,
        *,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> None:
        """Record LLM token-usage attributes on *span*.

        Safe to call on a ``_NoopSpan`` (no-op).
        """
        if input_tokens is not None:
            try:
                span.set_attribute("llm.usage.input_tokens", input_tokens)
            except Exception:
                pass
        if output_tokens is not None:
            try:
                span.set_attribute("llm.usage.output_tokens", output_tokens)
            except Exception:
                pass
        if model:
            try:
                span.set_attribute("llm.model", model)
            except Exception:
                pass
        if provider:
            try:
                span.set_attribute("llm.provider", provider)
            except Exception:
                pass

    def shutdown(self) -> None:
        """Flush and shut down the span processor.  Call at process exit."""
        if self._provider is not None:
            try:
                self._provider.shutdown()
            except Exception as exc:
                logger.debug("OTEL provider shutdown error: %s", exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hermes_version() -> str:
    try:
        from importlib.metadata import version

        return version("hermes-agent")
    except Exception:
        return "unknown"
