# Hermes OTEL Exporter

> File: `agent/otel_exporter.py`
> Status: **DEFAULT-OFF** (zero overhead when disabled)

---

## Overview

`HermesOtelExporter` emits OpenTelemetry traces for key Hermes operations
(LLM calls, retries, tool invocations) to an OTLP collector.

The exporter is **disabled by default** — it becomes active only when
`HERMES_OTEL_ENABLED=1` is set AND the `opentelemetry-sdk` package is installed.

## Enable

```bash
# Minimal — enables OTLP HTTP export to localhost:4318
export HERMES_OTEL_ENABLED=1

# Full configuration
export HERMES_OTEL_ENABLED=1
export HERMES_OTEL_ENDPOINT=http://your-collector:4318
export HERMES_OTEL_SERVICE_NAME=hermes-agent
export HERMES_OTEL_BACKEND=otlp   # "otlp" (default) or "console"

# Opt-in to include user prompt text in spans (OFF by default)
export HERMES_OTEL_INCLUDE_PROMPTS=1
```

Or via `config.yaml`:

```yaml
observability:
  otel:
    enabled: true
    endpoint: http://localhost:4318
    service_name: hermes-agent
    backend: otlp
    include_prompts: false
```

## Install SDK

```bash
pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
```

## Usage in Hermes code

```python
from agent.otel_exporter import HermesOtelExporter

exporter = HermesOtelExporter.from_env()  # or from_config_dict(cfg)

with exporter.start_span("llm_call", {"model": "gpt-4o", "provider": "openai"}) as span:
    response = call_llm(...)
    exporter.record_usage(span, input_tokens=100, output_tokens=50)
```

## Security

| Concern | Mitigation |
|---|---|
| Secret values in spans | `_sanitize_attributes()` replaces credential-shaped values with `[REDACTED]` |
| Blocked attribute keys | `api_key`, `access_token`, `password`, `secret`, `token`, `authorization` etc. are dropped entirely |
| Prompt text | NOT included unless `HERMES_OTEL_INCLUDE_PROMPTS=1` is explicitly set |

## Tests

```bash
uv run pytest tests/test_otel_exporter.py -v
# 19 passed
```
