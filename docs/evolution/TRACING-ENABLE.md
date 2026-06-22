# Tracing Enablement (Wave 1A)

`sqlite_traces` follows the existing plugin opt-in flow and does not require
agent-loop changes.

## Enable the plugin

```powershell
hermes plugins enable observability/sqlite_traces
```

## Tracing defaults

Add (or merge) this block in `~/.hermes/config.yaml`:

```yaml
tracing:
  enabled: true
  sample_rate: 1.0
  capture_payloads: false
  retention_days: 14
  queue_max: 1024
```

Notes:
- `capture_payloads` stays `false` by default for security.
- Storage is `~/.hermes/traces.db` (separate from `state.db`).
- Span attributes are allowlisted metadata only (no prompts/tool args/files).
