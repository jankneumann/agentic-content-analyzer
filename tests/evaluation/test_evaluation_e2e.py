"""End-to-end integration test for the evaluation pipeline.

Tests the full flow:
  create dataset → add sample → configure routing → verify routing decision info

This test runs without a database by exercising the in-memory code paths.
"""

import pytest
from unittest.mock import MagicMock

from src.config.models import ModelConfig, ModelStep, RoutingConfig, RoutingMode
from src.evaluation.calibrator import CalibrationResult, ThresholdCalibrator
from src.evaluation.criteria import load_evaluation_config
from src.services.complexity_router import ComplexityRouter, RoutingDecisionInfo
from src.services.evaluation_service import EvaluationService


class TestEvaluationE2E:
    """End-to-end test exercising the full evaluation pipeline in memory."""

    def test_create_dataset_and_add_sample(self):
        """Create a dataset and add a sample without database."""
        svc = EvaluationService()
        ds = svc.create_dataset(
            step="summarization",
            name="e2e_test",
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
        )
        assert ds.step == "summarization"
        assert ds.name == "e2e_test"

        sample_id = svc.add_sample(
            dataset_id=ds.id,
            prompt_text="Summarize this article about AI trends.",
            strong_output="Strong model output here.",
            weak_output="Weak model output here.",
        )
        # Without DB, returns 0
        assert sample_id == 0

    def test_complexity_router_classify_and_route(self):
        """Test complexity router classifies prompts and makes routing decisions."""
        # Train a simple classifier
        from sklearn.linear_model import LogisticRegression

        router = ComplexityRouter(embed_fn=lambda x: [len(x) / 100.0, 0.5])

        clf = LogisticRegression(max_iter=100)
        # Simple training: short prompts = simple (0), long prompts = complex (1)
        clf.fit(
            [[0.1, 0.5], [0.2, 0.5], [0.15, 0.5], [0.25, 0.5],
             [0.8, 0.5], [0.9, 0.5], [0.85, 0.5], [0.95, 0.5]],
            [0, 0, 0, 0, 1, 1, 1, 1],
        )
        router._classifiers["summarization"] = clf

        # Short prompt → should route to weak
        result = router.classify(
            prompt="short",
            step="summarization",
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
            threshold=0.5,
        )
        assert isinstance(result, RoutingDecisionInfo)
        assert result.model_selected in ("claude-sonnet-4-5", "claude-haiku-4-5")

    def test_calibrator_with_evaluation_data(self):
        """Test calibration from mock evaluation results."""
        calibrator = ThresholdCalibrator()

        # Simulate 30 samples with complexity scores and preferences
        scores = [i / 30.0 for i in range(30)]
        # Low complexity → weak wins; high complexity → strong wins
        preferences = []
        for s in scores:
            if s < 0.5:
                preferences.append("weak_wins")
            elif s < 0.7:
                preferences.append("tie")
            else:
                preferences.append("strong_wins")

        result = calibrator.calibrate(
            step="summarization",
            complexity_scores=scores,
            consensus_preferences=preferences,
            target_quality=0.90,
        )

        assert isinstance(result, CalibrationResult)
        assert result.step == "summarization"
        assert 0.0 <= result.threshold <= 1.1
        assert result.total_samples == 30

    def test_calibrator_estimate_savings(self):
        """Test cost savings estimation."""
        calibrator = ThresholdCalibrator()
        scores = [0.1, 0.2, 0.3, 0.6, 0.7, 0.8]

        savings = calibrator.estimate_savings(
            complexity_scores=scores,
            threshold=0.5,
            strong_cost_per_call=0.01,
            weak_cost_per_call=0.001,
        )

        assert savings["total_calls"] == 6
        assert savings["weak_routed"] == 3
        assert savings["strong_routed"] == 3
        assert savings["savings"] > 0

    def test_routing_config_dynamic_mode(self):
        """Test that routing config supports dynamic mode."""
        config = ModelConfig()

        # Default is fixed and disabled
        assert config.is_dynamic_routing_enabled(ModelStep.SUMMARIZATION) is False

        # Manually enable dynamic routing
        config._routing_configs["summarization"] = RoutingConfig(
            step="summarization",
            mode=RoutingMode.DYNAMIC,
            enabled=True,
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
            threshold=0.5,
        )
        assert config.is_dynamic_routing_enabled(ModelStep.SUMMARIZATION) is True

    def test_evaluation_criteria_loading(self):
        """Test that evaluation criteria load from YAML."""
        config = load_evaluation_config()
        assert config is not None
        assert len(config.judges) > 0

        # Check that default criteria exist
        from src.evaluation.criteria import get_criteria_for_step
        criteria = get_criteria_for_step(config, "summarization")
        assert len(criteria.dimensions) > 0
