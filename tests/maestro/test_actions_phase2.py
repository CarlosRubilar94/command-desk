"""Tests that Phase 2 actions are architected but hard-disabled in Phase 1."""

from __future__ import annotations

import pytest

from maestro.actions_phase2 import (
    Phase2Disabled,
    execute_permanent_delete,
    execute_trash,
    plan_trash,
)


def test_plan_trash_is_reversible_and_non_executing():
    p = plan_trash("hostinger_empresa", ["m1", "m2"], reason="newsletters")
    assert p.operation == "trash"
    assert p.reversible is True
    assert p.targets == ["m1", "m2"]
    assert "DRY-RUN" in p.preview()


def test_execute_trash_disabled_by_default():
    p = plan_trash("acc", ["m1"])
    with pytest.raises(Phase2Disabled):
        execute_trash(p)  # disabled → refuses


def test_execute_trash_requires_double_confirm_even_when_enabled():
    p = plan_trash("acc", ["m1"])
    with pytest.raises(Phase2Disabled):
        execute_trash(p, enabled=True, confirm_token="")  # missing token
    with pytest.raises(Phase2Disabled):
        execute_trash(p, enabled=True, confirm_token="CONFIRMO")  # still not implemented in P1


def test_permanent_delete_always_refuses():
    p = plan_trash("acc", ["m1"])
    with pytest.raises(Phase2Disabled):
        execute_permanent_delete(p, enabled=True, confirm_token="CONFIRMO")
