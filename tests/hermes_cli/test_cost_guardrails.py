from hermes_cli.cost_guardrails import evaluate_guardrails, is_premium_model


def test_default_disabled_returns_none_action():
    decision = evaluate_guardrails(
        spend_today=8.0,
        daily_budget=5.0,
        mission_spend=3.0,
        mission_budget=2.0,
        model="claude-opus-4",
        is_premium=True,
        config={},
    )
    assert decision.allow is True
    assert decision.action == "none"
    assert decision.fallback_model is None


def test_warn_when_daily_budget_exceeded():
    decision = evaluate_guardrails(
        spend_today=12.0,
        daily_budget=10.0,
        mission_spend=0.0,
        mission_budget=None,
        model="google/gemini-2.5-flash",
        is_premium=False,
        config={"enabled": True, "premium_alert": False},
    )
    assert decision.allow is True
    assert decision.action == "warn"
    assert "daily_budget_exceeded" in str(decision.reason)


def test_warn_on_premium_usage_alert():
    decision = evaluate_guardrails(
        spend_today=1.0,
        daily_budget=10.0,
        mission_spend=0.0,
        mission_budget=None,
        model="gpt-4o",
        is_premium=True,
        config={"enabled": True, "premium_alert": True},
    )
    assert decision.allow is True
    assert decision.action == "warn"
    assert "premium_model_usage" in str(decision.reason)


def test_block_expensive_without_fallback():
    decision = evaluate_guardrails(
        spend_today=1.0,
        daily_budget=10.0,
        mission_spend=0.0,
        mission_budget=None,
        model="claude-opus-4",
        is_premium=True,
        config={
            "enabled": True,
            "block_expensive": True,
            "auto_fallback": False,
        },
    )
    assert decision.allow is False
    assert decision.action == "block"
    assert decision.fallback_model is None


def test_auto_fallback_on_over_budget():
    decision = evaluate_guardrails(
        spend_today=11.0,
        daily_budget=10.0,
        mission_spend=0.0,
        mission_budget=None,
        model="gpt-4o",
        is_premium=True,
        config={
            "enabled": True,
            "auto_fallback": True,
            "fallback_model": "google/gemini-2.5-flash",
        },
    )
    assert decision.allow is True
    assert decision.action == "fallback"
    assert decision.fallback_model == "google/gemini-2.5-flash"


def test_mission_budget_overrides_warning():
    decision = evaluate_guardrails(
        spend_today=1.0,
        daily_budget=50.0,
        mission_spend=4.0,
        mission_budget=3.0,
        model="anthropic/claude-3-5-sonnet",
        is_premium=True,
        config={"enabled": True, "premium_alert": False},
    )
    assert decision.action == "warn"
    assert "mission_budget_exceeded" in str(decision.reason)


def test_budget_values_missing_do_not_trigger():
    decision = evaluate_guardrails(
        spend_today=999.0,
        daily_budget=None,
        mission_spend=999.0,
        mission_budget=None,
        model="google/gemini-2.5-flash",
        is_premium=False,
        config={"enabled": True},
    )
    assert decision.action == "none"
    assert decision.allow is True


def test_is_premium_model_default_and_custom_prefixes():
    assert is_premium_model("gpt-4o") is True
    assert is_premium_model("google/gemini-2.5-flash") is False
    assert is_premium_model(
        "custom/premium-model",
        {"premium_model_prefixes": ["custom/premium"]},
    ) is True
