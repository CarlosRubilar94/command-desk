# Tracing Enablement (Wave 1A)

`sqlite_traces` is now bundled and auto-enabled by default (no manual plugin
toggle required), while still using the existing hook bus (no agent-loop
changes).

## Default enablement

- New installs and existing profiles load `observability/sqlite_traces`
  automatically.
- You can explicitly turn it off via `plugins.disabled` if needed for incident
  isolation.

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
- `traces.db` permissions are tightened best-effort (`0600` on POSIX, owner ACL
  tightening attempt on Windows via `icacls` when available).
