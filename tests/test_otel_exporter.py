"""Tests for agent.otel_exporter — OpenTelemetry trace/span exporter.

The opentelemetry-sdk is mocked so the suite runs without it installed.
Validates:
  * Default-off: no SDK import when disabled.
  * Sanitization: secret-shaped keys/values are scrubbed.
  * No-op span: correct pass-through API when disabled.
  * Enabled path: span operations called on the real SDK mock.
  * from_env(): respects HERMES_OTEL_ENABLED env var.
  * from_config_dict(): reads observability.otel section.
  * shutdown() is safe when provider is None.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.otel_exporter import (  # noqa: E402
    HermesOtelExporter,
    OtelConfig,
    _NoopSpan,
    _sanitize_attributes,
    _get_otel,
)
import agent.otel_exporter as _otel_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_otel_cache():
    original = _otel_mod._otel_sdk
    _otel_mod._otel_sdk = ...
    yield
    _otel_mod._otel_sdk = original


def _make_fake_otel() -> SimpleNamespace:
    """Build a minimal mock of the opentelemetry SDK namespace."""
    fake_span = MagicMock(name="span")
    fake_span.__enter__ = MagicMock(return_value=fake_span)
    fake_span.__exit__ = MagicMock(return_value=False)

    fake_tracer = MagicMock(name="tracer")
    fake_tracer.start_as_current_span.return_value = fake_span

    fake_provider = MagicMock(name="TracerProvider_instance")
    TracerProvider = MagicMock(return_value=fake_provider)

    fake_trace = MagicMock(name="trace_module")
    fake_trace.get_tracer.return_value = fake_tracer

    Resource = MagicMock()
    Resource.create.return_value = MagicMock()

    BatchSpanProcessor = MagicMock()
    SimpleSpanProcessor = MagicMock()
    ConsoleSpanExporter = MagicMock()
    OTLPSpanExporter = MagicMock()

    return SimpleNamespace(
        trace=fake_trace,
        TracerProvider=TracerProvider,
        BatchSpanProcessor=BatchSpanProcessor,
        SimpleSpanProcessor=SimpleSpanProcessor,
        ConsoleSpanExporter=ConsoleSpanExporter,
        Resource=Resource,
        OTLPSpanExporter=OTLPSpanExporter,
        # expose the span for assertions
        _fake_span=fake_span,
        _fake_provider=fake_provider,
        _fake_tracer=fake_tracer,
    )


# ---------------------------------------------------------------------------
# _sanitize_attributes
# ---------------------------------------------------------------------------


class TestSanitizeAttributes:
    def test_drops_secret_key(self):
        result = _sanitize_attributes({"api_key": "sk-abc", "model": "gpt-4o"})
        assert "api_key" not in result
        assert result["model"] == "gpt-4o"

    def test_redacts_secret_value(self):
        result = _sanitize_attributes({"info": "sk-supersecret", "ok": "hello"})
        assert result["info"] == "[REDACTED]"
        assert result["ok"] == "hello"

    def test_passes_clean_attrs(self):
        attrs = {"model": "gpt-4o", "provider": "openai", "tokens": 100}
        assert _sanitize_attributes(attrs) == attrs

    def test_empty_dict(self):
        assert _sanitize_attributes({}) == {}


# ---------------------------------------------------------------------------
# _get_otel
# ---------------------------------------------------------------------------


class TestGetOtel:
    def test_returns_none_when_not_installed(self):
        with patch.dict("sys.modules", {"opentelemetry": None}):
            _otel_mod._otel_sdk = ...
            result = _get_otel()
        assert result is None

    def test_returns_namespace_when_installed(self):
        fake = _make_fake_otel()
        _otel_mod._otel_sdk = fake
        result = _get_otel()
        assert result is fake


# ---------------------------------------------------------------------------
# Default-off
# ---------------------------------------------------------------------------


class TestDefaultOff:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("HERMES_OTEL_ENABLED", raising=False)
        exporter = HermesOtelExporter.from_env()
        assert not exporter.enabled

    def test_noop_span_when_disabled(self, monkeypatch):
        monkeypatch.delenv("HERMES_OTEL_ENABLED", raising=False)
        exporter = HermesOtelExporter.from_env()
        with exporter.start_span("test_op", {"model": "gpt-4o"}) as span:
            assert isinstance(span, _NoopSpan)

    def test_record_usage_safe_on_noop(self, monkeypatch):
        monkeypatch.delenv("HERMES_OTEL_ENABLED", raising=False)
        exporter = HermesOtelExporter.from_env()
        noop = _NoopSpan()
        exporter.record_usage(noop, input_tokens=10, output_tokens=5)  # must not raise

    def test_shutdown_safe_when_disabled(self, monkeypatch):
        monkeypatch.delenv("HERMES_OTEL_ENABLED", raising=False)
        exporter = HermesOtelExporter.from_env()
        exporter.shutdown()  # must not raise


# ---------------------------------------------------------------------------
# from_env / from_config_dict
# ---------------------------------------------------------------------------


class TestFromEnv:
    def test_enabled_from_env(self, monkeypatch):
        monkeypatch.setenv("HERMES_OTEL_ENABLED", "1")
        _otel_mod._otel_sdk = None  # pretend SDK absent — should not crash
        exporter = HermesOtelExporter.from_env()
        assert not exporter.enabled  # SDK absent → disabled gracefully

    def test_include_prompts_default_false(self, monkeypatch):
        monkeypatch.delenv("HERMES_OTEL_INCLUDE_PROMPTS", raising=False)
        cfg = OtelConfig.from_env()
        assert cfg.include_prompts is False

    def test_include_prompts_opt_in(self, monkeypatch):
        monkeypatch.setenv("HERMES_OTEL_INCLUDE_PROMPTS", "1")
        cfg = OtelConfig.from_env()
        assert cfg.include_prompts is True


class TestFromConfigDict:
    def test_parses_otel_section(self):
        cfg = {
            "observability": {
                "otel": {
                    "enabled": True,
                    "endpoint": "http://collector:4318",
                    "service_name": "my-hermes",
                    "backend": "console",
                }
            }
        }
        _otel_mod._otel_sdk = None  # SDK absent
        exporter = HermesOtelExporter.from_config_dict(cfg)
        assert not exporter.enabled  # SDK absent → disabled gracefully

    def test_missing_section_defaults(self):
        _otel_mod._otel_sdk = None
        exporter = HermesOtelExporter.from_config_dict({})
        assert not exporter.enabled


# ---------------------------------------------------------------------------
# Enabled path (with mocked SDK)
# ---------------------------------------------------------------------------


class TestEnabledPath:
    def test_span_started_when_enabled(self):
        fake = _make_fake_otel()
        _otel_mod._otel_sdk = fake
        config = OtelConfig(enabled=True, backend="console")
        exporter = HermesOtelExporter(config)
        assert exporter.enabled

        with exporter.start_span("llm_call", {"model": "gpt-4o", "provider": "openai"}):
            pass

        fake._fake_tracer.start_as_current_span.assert_called_once_with("llm_call")

    def test_secret_attr_scrubbed_in_real_span(self):
        fake = _make_fake_otel()
        _otel_mod._otel_sdk = fake
        config = OtelConfig(enabled=True, backend="console")
        exporter = HermesOtelExporter(config)

        with exporter.start_span("llm_call", {"api_key": "sk-secret", "model": "gpt-4o"}) as span:
            pass

        # "api_key" must not appear in any set_attribute calls
        called_keys = [
            c.args[0]
            for c in fake._fake_span.set_attribute.call_args_list
        ]
        assert "api_key" not in called_keys
        assert "model" in called_keys

    def test_record_usage_sets_attributes(self):
        fake = _make_fake_otel()
        _otel_mod._otel_sdk = fake
        config = OtelConfig(enabled=True, backend="console")
        exporter = HermesOtelExporter(config)
        noop_or_span = MagicMock()
        exporter.record_usage(
            noop_or_span, input_tokens=100, output_tokens=50, model="gpt-4o"
        )
        noop_or_span.set_attribute.assert_any_call("llm.usage.input_tokens", 100)
        noop_or_span.set_attribute.assert_any_call("llm.usage.output_tokens", 50)
        noop_or_span.set_attribute.assert_any_call("llm.model", "gpt-4o")

    def test_exception_recorded_and_re_raised(self):
        fake = _make_fake_otel()
        _otel_mod._otel_sdk = fake

        # Patch StatusCode import inside start_span to avoid import error
        with patch("agent.otel_exporter._get_otel", return_value=fake):
            config = OtelConfig(enabled=True, backend="console")
            exporter = HermesOtelExporter(config)
            assert exporter.enabled

            with pytest.raises(ValueError, match="boom"):
                with exporter.start_span("failing_op") as span:
                    raise ValueError("boom")

            fake._fake_span.record_exception.assert_called_once()
