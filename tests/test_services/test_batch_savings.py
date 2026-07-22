"""Unit tests for batch cost-savings projection (pure, no DB)."""

from __future__ import annotations

from src.config.models import ModelConfig, ModelStep
from src.services.batch.savings import (
    BATCH_DISCOUNT,
    STEP_TOKEN_ESTIMATES,
    compute_batch_savings,
)


def test_covers_all_batch_eligible_steps():
    result = compute_batch_savings(ModelConfig(), {})
    steps = {row["step"] for row in result["steps"]}
    assert steps == {s.value for s in STEP_TOKEN_ESTIMATES}


def test_batch_cost_is_half_standard():
    volumes = {ModelStep.CONTENT_FILTERING: 1000}
    result = compute_batch_savings(ModelConfig(), volumes)
    cf = next(r for r in result["steps"] if r["step"] == ModelStep.CONTENT_FILTERING.value)

    assert cf["items"] == 1000
    assert cf["std_cost"] > 0
    # Flat 50% discount: batch is exactly half, savings is the other half.
    assert cf["batch_cost"] == round(cf["std_cost"] * BATCH_DISCOUNT, 6)
    assert round(cf["batch_cost"] + cf["savings"], 6) == cf["std_cost"]


def test_totals_sum_step_rows():
    volumes = dict.fromkeys(STEP_TOKEN_ESTIMATES, 100)
    result = compute_batch_savings(ModelConfig(), volumes)

    assert result["total_std_cost"] == round(sum(r["std_cost"] for r in result["steps"]), 6)
    assert result["total_batch_cost"] == round(sum(r["batch_cost"] for r in result["steps"]), 6)
    assert result["total_savings"] == round(
        result["total_std_cost"] - result["total_batch_cost"], 6
    )


def test_zero_volume_is_zero_cost():
    result = compute_batch_savings(ModelConfig(), {})
    assert result["total_std_cost"] == 0
    assert result["total_savings"] == 0
    assert all(r["items"] == 0 for r in result["steps"])


def test_report_exports_reproducible_assumptions():
    result = compute_batch_savings(ModelConfig(), {})

    assert result["assumptions"] == {
        "batch_discount": 0.5,
        "pricing_basis": "configured model input/output price per 1M tokens",
        "volume_basis": (
            "content rows for filtering; YouTube content rows for caption and video steps"
        ),
        "limitations": (
            "planning estimate only; row counts do not identify borderline filters, "
            "caption availability, or provider cache effects"
        ),
        "token_estimates": {
            step.value: {"input_tokens_each": values[0], "output_tokens_each": values[1]}
            for step, values in STEP_TOKEN_ESTIMATES.items()
        },
    }
