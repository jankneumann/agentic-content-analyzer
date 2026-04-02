"""Tests for ThresholdCalibrator."""

import pytest

from src.evaluation.calibrator import CalibrationResult, ThresholdCalibrator


class TestCalibrate:
    def test_insufficient_data_raises(self):
        calibrator = ThresholdCalibrator()
        with pytest.raises(ValueError, match="Insufficient evaluation data"):
            calibrator.calibrate(
                step="summarization",
                complexity_scores=[0.1] * 10,
                consensus_preferences=["tie"] * 10,
            )

    def test_mismatched_lengths_raises(self):
        calibrator = ThresholdCalibrator()
        with pytest.raises(ValueError, match="same length"):
            calibrator.calibrate(
                step="summarization",
                complexity_scores=[0.1] * 30,
                consensus_preferences=["tie"] * 25,
            )

    def test_all_ties_finds_threshold(self):
        """When all preferences are tie, weak model always wins."""
        calibrator = ThresholdCalibrator()
        scores = [i / 30 for i in range(30)]
        prefs = ["tie"] * 30

        result = calibrator.calibrate("summarization", scores, prefs)
        assert isinstance(result, CalibrationResult)
        assert result.win_or_tie_rate >= 0.95
        assert result.total_samples == 30
        assert result.estimated_cost_savings_pct > 0

    def test_all_strong_wins_threshold_is_high(self):
        """When strong always wins, threshold should be very high (route everything to strong)."""
        calibrator = ThresholdCalibrator()
        scores = [i / 30 for i in range(30)]
        prefs = ["strong_wins"] * 30

        result = calibrator.calibrate("summarization", scores, prefs, target_quality=0.95)
        # Strong always wins means weak never acceptable — savings should be 0
        assert result.estimated_cost_savings_pct == 0.0

    def test_mixed_preferences(self):
        """Mixed preferences should find a valid threshold."""
        calibrator = ThresholdCalibrator()
        # Low complexity: weak is fine; high complexity: strong wins
        scores = [i / 30 for i in range(30)]
        prefs = ["weak_wins"] * 15 + ["strong_wins"] * 15

        result = calibrator.calibrate("summarization", scores, prefs, target_quality=0.95)
        assert result.step == "summarization"
        assert 0 < result.threshold <= 1.0
        assert result.total_samples == 30

    def test_target_quality_parameter(self):
        calibrator = ThresholdCalibrator()
        scores = [i / 30 for i in range(30)]
        prefs = ["tie"] * 30

        result = calibrator.calibrate("summarization", scores, prefs, target_quality=0.90)
        assert result.target_quality == 0.90


class TestEstimateSavings:
    def test_empty_scores(self):
        calibrator = ThresholdCalibrator()
        result = calibrator.estimate_savings([], 0.5)
        assert result["total_calls"] == 0

    def test_all_below_threshold(self):
        """All calls routed to weak → maximum savings."""
        calibrator = ThresholdCalibrator()
        result = calibrator.estimate_savings(
            [0.1, 0.2, 0.3], threshold=0.5,
            strong_cost_per_call=0.01, weak_cost_per_call=0.001,
        )
        assert result["weak_routed"] == 3
        assert result["strong_routed"] == 0
        assert result["savings"] > 0

    def test_all_above_threshold(self):
        """All calls routed to strong → no savings."""
        calibrator = ThresholdCalibrator()
        result = calibrator.estimate_savings(
            [0.6, 0.7, 0.8], threshold=0.5,
            strong_cost_per_call=0.01, weak_cost_per_call=0.001,
        )
        assert result["weak_routed"] == 0
        assert result["savings"] == 0.0

    def test_savings_calculation(self):
        """Verify savings math."""
        calibrator = ThresholdCalibrator()
        result = calibrator.estimate_savings(
            [0.1, 0.2, 0.6, 0.8], threshold=0.5,
            strong_cost_per_call=0.01, weak_cost_per_call=0.001,
        )
        # 2 weak (0.001 each) + 2 strong (0.01 each) = 0.022
        # vs 4 strong = 0.04
        # savings = 0.018
        assert result["weak_routed"] == 2
        assert result["strong_routed"] == 2
        assert result["savings"] == pytest.approx(0.018)
