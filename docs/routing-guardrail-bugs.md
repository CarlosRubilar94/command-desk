# Routing & Guardrail Pre-existing Bugs

> **Scope**: These bugs are pre-existing and **outside Wave 17 scope**. No code changes are included in this document.
> Static analysis performed on branch `cursor/command-desk-wave17` (commit `593ffcdda`).

---

## Bug 1 — Routing annotation keyed by `effective_task_id`, not aux task name

**Severity**: HIGH  
**Location**: `agent/conversation_loop.py:3642-3644`

### Root Cause

`consume_routing_annotation(effective_task_id, agent.model)` is called with the **session-level `effective_task_id`** as the lookup key. However, `_record_routing_annotation` in `smart_model_routing.py` stores annotations keyed by the **auxiliary task name** (e.g., `"compression"`, `"title_generation"`). These two keys never match — `effective_task_id` is a runtime session identifier, while the store is populated with short task-name strings from `ECONOMY_TASKS`. Result: `_annotation_store().pop(task_key, None)` always returns `None`, so the `_routing_annotation` dict in the `post_api_request` hook is always empty, and baseline/selected tier metadata is absent from all spans.

### Proposed Fix

Replace the call in `conversation_loop.py` with the **auxiliary task name** at the point where the aux call resolves, or expose the task name alongside `effective_task_id` so the annotation can be consumed with the correct key. One clean approach: pass the resolved task name from `resolve_aux_routing` through to the hook call site, e.g. `consume_routing_annotation(aux_task_name, agent.model)`.

### Risk / Blast Radius

Low implementation risk — only affects observability metadata on spans; no functional path changes. No user-facing regression possible.

### Suggested Test

Assert that after `resolve_aux_routing("compression", ...)` runs, `consume_routing_annotation("compression", resolved_model)` returns a non-empty dict containing `baseline_model` and `selected_model`.

---

## Bug 2 — `action=block` RuntimeError swallowed by auxiliary_client broad except

**Severity**: HIGH  
**Location**: `agent/smart_model_routing.py:328-331` (raise site) / `agent/auxiliary_client.py:3395-3396` (catch site)

### Root Cause

`resolve_aux_routing` raises `RuntimeError` when the guardrail decision is `action=block` (lines 328–331). The call site in `auxiliary_client.py` wraps the call in:

```python
except Exception as exc:
    logger.debug("smart_model_routing aux resolve skipped: %s", exc)
```

`RuntimeError` is a subclass of `Exception`, so the block is silently logged at DEBUG level and execution continues with the **original (premium) model** unchanged — directly defeating the budget block.

### Proposed Fix

Either (a) re-raise `RuntimeError` (budget-block) as a specific, named exception (e.g., `CostGuardrailBlockedError`) and catch it explicitly in `auxiliary_client.py` to abort the aux call, or (b) narrow the `except Exception` in `auxiliary_client.py` to exclude `RuntimeError` and propagate it up so the caller can handle it intentionally.

### Risk / Blast Radius

Medium — narrowing the `except Exception` could surface previously silent errors. Must audit all code paths that call `resolve_aux_routing` to ensure only `CostGuardrailBlockedError` bubbles, not transient import/config errors. Test coverage on budget-block path is strongly recommended before shipping.

### Suggested Test

Mock `_guardrail_decision_for_model` to return `action=block`; assert that the auxiliary request is **not** dispatched and the caller receives an error or skips the call rather than using the premium model.

---

## Bug 3 — `_guardrail_decision_for_model` unreachable when only `cost_guardrails.enabled=true`

**Severity**: HIGH  
**Location**: `agent/smart_model_routing.py:259-260`

### Root Cause

`resolve_aux_routing` has an early-return guard:

```python
if not is_routing_enabled() or not task:
    return main_provider, main_model
```

`is_routing_enabled()` checks `smart_model_routing.enabled` (line 68-69). `_guardrail_decision_for_model` checks `cost_guardrails.enabled` (line 205-207). These are **two independent config keys**. A deployment that sets only `cost_guardrails.enabled: true` (without `smart_model_routing.enabled: true`) will never reach `_guardrail_decision_for_model`, so budget enforcement is silently bypassed for all auxiliary calls.

### Proposed Fix

Extract the guardrail check out of `resolve_aux_routing` or add a separate entry point that runs `_guardrail_decision_for_model` independently of `is_routing_enabled()`. Concretely: check `cost_guardrails.enabled` before the early-return, and enforce the budget guard even when smart routing is off.

### Risk / Blast Radius

Medium — the change affects which code path runs for every aux call when `cost_guardrails.enabled=true`. Must ensure the guardrail check is idempotent and does not add latency on the hot path when both flags are false. Config documentation should also be updated to clarify that budget enforcement requires `smart_model_routing.enabled: true` (until fixed).

### Suggested Test

Set `cost_guardrails.enabled: true`, `smart_model_routing.enabled: false`, and a budget that the model would exceed; assert that `_guardrail_decision_for_model` is called and returns a non-`None` decision.

---

## Bug 4 — Guardrail spend query uses default `SessionDB()` path, not profile-scoped DB

**Severity**: MEDIUM  
**Location**: `agent/smart_model_routing.py:222`

### Root Cause

`_guardrail_decision_for_model` instantiates `SessionDB()` with no arguments (line 222), relying on the class default path. The mission-spend helper `_mission_spend_today` on line 185 correctly uses `SessionDB(db_path=get_hermes_home() / "state.db")` with the explicit profile-scoped path from `get_hermes_home()`. The Command Desk dashboard also reads session data from the profile-scoped DB. If the user runs multiple profiles (e.g., separate `--profile` flags), the default `SessionDB()` path may resolve to the **wrong profile's database**, causing the spend query to return incorrect totals — leading to either false triggers (block/warn on a profile with no spend) or missed enforcement (no block on a profile that has exceeded budget).

### Proposed Fix

Replace `db = SessionDB()` with `db = SessionDB(db_path=get_hermes_home() / "state.db")`, consistent with the pattern used in `_mission_spend_today`. If `get_hermes_home()` is not already imported in the `_guardrail_decision_for_model` scope, add the import inside the try block.

### Risk / Blast Radius

Low — single-line change; only affects multi-profile setups. Single-profile users are unaffected. No behavioral change expected in the common case.

### Suggested Test

Instantiate two profiles with different `HERMES_HOME` values; write spend data to profile A's DB only; assert that running the guardrail check under profile B does not see profile A's spend, and vice versa.
