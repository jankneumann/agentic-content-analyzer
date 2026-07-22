"""Tests for risk-tiering and the validate-before-promote gate."""

import pytest

from src.services.model_promotion import (
    ChangeKind,
    PromotionInputs,
    RiskTier,
    can_auto_apply,
    classify_change_risk,
    evaluate_promotion,
    summarize_consensus,
)


class TestSummarizeConsensus:
    def test_empty_is_zero(self):
        assert summarize_consensus([]) == (0.0, 0.0)

    def test_candidate_wins_and_ties_count_as_parity(self):
        verdicts = [("weak", 1.0), ("tie", 0.8), ("strong", 0.6)]
        parity, agreement = summarize_consensus(verdicts)
        assert parity == pytest.approx(2 / 3)
        assert agreement == pytest.approx((1.0 + 0.8 + 0.6) / 3)

    def test_all_incumbent_wins_zero_parity(self):
        parity, _ = summarize_consensus([("strong", 0.9), ("strong", 0.9)])
        assert parity == pytest.approx(0.0)


class TestRiskTiers:
    def test_pricing_is_low_and_auto(self):
        assert classify_change_risk(ChangeKind.PRICING_DIFF) == RiskTier.LOW
        assert can_auto_apply(ChangeKind.PRICING_DIFF) is True

    def test_new_model_is_medium_gated(self):
        assert classify_change_risk(ChangeKind.NEW_MODEL) == RiskTier.MEDIUM
        assert can_auto_apply(ChangeKind.NEW_MODEL) is False

    def test_default_swap_is_high_gated(self):
        assert classify_change_risk(ChangeKind.DEFAULT_SWAP) == RiskTier.HIGH
        assert can_auto_apply(ChangeKind.DEFAULT_SWAP) is False

    def test_unknown_kind_defaults_high(self):
        assert classify_change_risk("mystery") == RiskTier.HIGH


class TestPromotionGate:
    def test_passes_when_all_criteria_met(self):
        decision = evaluate_promotion(
            PromotionInputs(
                parity_score=0.95, agreement_rate=0.8, cost_incumbent=1.0, cost_candidate=0.5
            )
        )
        assert decision.recommend is True

    def test_fails_on_low_parity(self):
        decision = evaluate_promotion(
            PromotionInputs(
                parity_score=0.5, agreement_rate=0.9, cost_incumbent=1.0, cost_candidate=0.5
            )
        )
        assert decision.recommend is False
        assert any("parity" in r for r in decision.reasons)

    def test_fails_on_low_agreement(self):
        decision = evaluate_promotion(
            PromotionInputs(
                parity_score=0.95, agreement_rate=0.3, cost_incumbent=1.0, cost_candidate=0.5
            )
        )
        assert decision.recommend is False
        assert any("agreement" in r for r in decision.reasons)

    def test_fails_when_too_expensive(self):
        decision = evaluate_promotion(
            PromotionInputs(
                parity_score=0.95, agreement_rate=0.9, cost_incumbent=1.0, cost_candidate=2.0
            )
        )
        assert decision.recommend is False
        assert any("cost" in r for r in decision.reasons)

    def test_cost_budget_ratio_allows_more_expensive(self):
        # With a 2x budget, a candidate up to 2x incumbent cost is allowed.
        decision = evaluate_promotion(
            PromotionInputs(
                parity_score=0.95, agreement_rate=0.9, cost_incumbent=1.0, cost_candidate=1.8
            ),
            cost_budget_ratio=2.0,
        )
        assert decision.recommend is True

    def test_zero_incumbent_cost_skips_budget_check(self):
        decision = evaluate_promotion(
            PromotionInputs(
                parity_score=0.95, agreement_rate=0.9, cost_incumbent=0.0, cost_candidate=5.0
            )
        )
        assert decision.recommend is True
