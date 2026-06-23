from __future__ import annotations


def test_price_for_model_uses_known_model_override():
    from hermes_cli.pricing import price_for_model

    rate_in, rate_out = price_for_model("google/gemini-3-flash-preview")
    assert rate_in == 0.15
    assert rate_out == 0.60


def test_price_for_model_falls_back_to_tier_defaults():
    from hermes_cli.pricing import price_for_model

    premium_in, premium_out = price_for_model("anthropic/claude-opus-4.8")
    perf_in, perf_out = price_for_model("some-unknown-model")

    assert premium_in > perf_in
    assert premium_out > perf_out

