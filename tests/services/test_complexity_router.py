"""Tests for ComplexityRouter.

Tests cover:
- classify with/without trained model (cold start fallback)
- Embedding failure fallback
- Model persistence (save/load)
- RoutingDecisionInfo fields
"""

import pytest
from unittest.mock import MagicMock

from src.services.complexity_router import ComplexityRouter, RoutingDecisionInfo


class TestClassifyColdStart:
    def test_no_classifier_falls_back_to_strong(self):
        """Without trained classifier, always selects strong model."""
        router = ComplexityRouter(embed_fn=lambda x: [0.1] * 10)
        result = router.classify(
            prompt="test prompt",
            step="summarization",
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
            threshold=0.5,
        )
        assert result.model_selected == "claude-sonnet-4-5"
        assert result.complexity_score == 1.0

    def test_no_embed_fn_falls_back_to_strong(self):
        """Without embedding function, falls back to strong model."""
        router = ComplexityRouter(embed_fn=None)
        # Manually set a classifier to skip cold start check
        router._classifiers["summarization"] = MagicMock()
        result = router.classify(
            prompt="test",
            step="summarization",
            strong_model="strong",
            weak_model="weak",
            threshold=0.5,
        )
        assert result.model_selected == "strong"


class TestClassifyEmbeddingFailure:
    def test_embedding_exception_falls_back(self):
        """Embedding function error falls back to strong model."""
        def bad_embed(text):
            raise RuntimeError("API timeout")

        router = ComplexityRouter(embed_fn=bad_embed)
        router._classifiers["summarization"] = MagicMock()
        result = router.classify(
            prompt="test",
            step="summarization",
            strong_model="strong",
            weak_model="weak",
            threshold=0.5,
        )
        assert result.model_selected == "strong"
        assert result.complexity_score == 1.0


class TestClassifyWithTrainedModel:
    def test_routes_to_weak_below_threshold(self):
        """Low complexity score routes to weak model."""
        mock_clf = MagicMock()
        mock_clf.predict_proba.return_value = [[0.8, 0.2]]  # 20% complex

        router = ComplexityRouter(embed_fn=lambda x: [0.1] * 10)
        router._classifiers["summarization"] = mock_clf
        result = router.classify(
            prompt="simple prompt",
            step="summarization",
            strong_model="strong",
            weak_model="weak",
            threshold=0.5,
        )
        assert result.model_selected == "weak"
        assert result.complexity_score == pytest.approx(0.2)

    def test_routes_to_strong_above_threshold(self):
        """High complexity score routes to strong model."""
        mock_clf = MagicMock()
        mock_clf.predict_proba.return_value = [[0.3, 0.7]]  # 70% complex

        router = ComplexityRouter(embed_fn=lambda x: [0.1] * 10)
        router._classifiers["summarization"] = mock_clf
        result = router.classify(
            prompt="complex prompt",
            step="summarization",
            strong_model="strong",
            weak_model="weak",
            threshold=0.5,
        )
        assert result.model_selected == "strong"
        assert result.complexity_score == pytest.approx(0.7)

    def test_at_threshold_routes_to_strong(self):
        """Score exactly at threshold (>=) routes to strong model."""
        mock_clf = MagicMock()
        mock_clf.predict_proba.return_value = [[0.5, 0.5]]  # Exactly 0.5

        router = ComplexityRouter(embed_fn=lambda x: [0.1] * 10)
        router._classifiers["summarization"] = mock_clf
        result = router.classify(
            prompt="borderline",
            step="summarization",
            strong_model="strong",
            weak_model="weak",
            threshold=0.5,
        )
        assert result.model_selected == "strong"

    def test_classifier_inference_failure_falls_back(self):
        """Classifier error falls back to strong model."""
        mock_clf = MagicMock()
        mock_clf.predict_proba.side_effect = RuntimeError("inference error")

        router = ComplexityRouter(embed_fn=lambda x: [0.1] * 10)
        router._classifiers["summarization"] = mock_clf
        result = router.classify(
            prompt="test",
            step="summarization",
            strong_model="strong",
            weak_model="weak",
            threshold=0.5,
        )
        assert result.model_selected == "strong"


class TestRoutingDecisionInfo:
    def test_fields(self):
        info = RoutingDecisionInfo(
            step="summarization",
            complexity_score=0.7,
            threshold=0.5,
            model_selected="strong",
            strong_model="strong",
            weak_model="weak",
            prompt_hash="abc123",
        )
        assert info.step == "summarization"
        assert info.complexity_score == 0.7
        assert info.prompt_hash == "abc123"


class TestModelPersistence:
    def test_save_and_load(self, tmp_path):
        """Save and load a trained classifier."""
        from sklearn.linear_model import LogisticRegression

        router = ComplexityRouter(embed_fn=lambda x: [0.1] * 10)
        # Train a real simple classifier (picklable)
        clf = LogisticRegression(max_iter=100)
        clf.fit([[0.1, 0.2], [0.9, 0.8], [0.15, 0.25], [0.85, 0.75]], [0, 1, 0, 1])
        router._classifiers["summarization"] = clf
        router._classifier_versions["summarization"] = "test-v1"

        save_path = tmp_path / "test_model.pkl"
        router.save_model("summarization", save_path)
        assert save_path.exists()

        # Load into a new router
        router2 = ComplexityRouter(embed_fn=lambda x: [0.1] * 10)
        loaded = router2.load_model("summarization", save_path)
        assert loaded is True
        assert "summarization" in router2._classifiers

    def test_load_nonexistent_returns_false(self, tmp_path):
        router = ComplexityRouter()
        loaded = router.load_model("summarization", tmp_path / "nonexistent.pkl")
        assert loaded is False

    def test_save_without_classifier_raises(self, tmp_path):
        router = ComplexityRouter()
        with pytest.raises(ValueError, match="No trained classifier"):
            router.save_model("summarization", tmp_path / "model.pkl")
