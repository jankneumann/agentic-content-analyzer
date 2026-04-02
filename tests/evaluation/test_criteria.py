"""Tests for evaluation criteria loading and configuration."""

import pytest
import yaml
from pathlib import Path
from src.evaluation.criteria import (
    EvaluationConfig,
    JudgeConfig,
    QualityDimension,
    StepCriteria,
    get_criteria_for_step,
    load_evaluation_config,
)


class TestQualityDimension:
    def test_create_dimension(self):
        dim = QualityDimension(
            name="accuracy",
            description="Facts are correct",
            fail_when="Misrepresents facts",
        )
        assert dim.name == "accuracy"
        assert dim.description == "Facts are correct"
        assert dim.fail_when == "Misrepresents facts"


class TestStepCriteria:
    def test_dimension_names(self):
        criteria = StepCriteria(
            step="summarization",
            dimensions=[
                QualityDimension("accuracy", "desc", "fail"),
                QualityDimension("completeness", "desc", "fail"),
            ],
        )
        assert criteria.dimension_names() == ["accuracy", "completeness"]

    def test_empty_dimensions(self):
        criteria = StepCriteria(step="unknown")
        assert criteria.dimension_names() == []


class TestLoadEvaluationConfig:
    def test_load_from_settings(self):
        """Load the actual settings/evaluation.yaml."""
        config = load_evaluation_config()
        assert len(config.judges) >= 1
        assert config.human_review_weight == 2.0
        assert "_default" in config.criteria
        assert "summarization" in config.criteria

    def test_load_missing_file_returns_defaults(self, tmp_path):
        missing = tmp_path / "nonexistent.yaml"
        config = load_evaluation_config(missing)
        assert "_default" in config.criteria
        assert len(config.criteria["_default"].dimensions) == 4

    def test_load_custom_yaml(self, tmp_path):
        custom = tmp_path / "eval.yaml"
        custom.write_text(yaml.dump({
            "evaluation": {
                "judges": [{"model": "test-model", "weight": 0.5}],
                "human_review_weight": 3.0,
                "criteria": {
                    "_default": {
                        "accuracy": {
                            "description": "Test accuracy",
                            "fail_when": "Test fail",
                        }
                    },
                    "summarization": {
                        "clarity": {
                            "description": "Test clarity",
                            "fail_when": "Test clarity fail",
                        }
                    },
                },
            }
        }))
        config = load_evaluation_config(custom)
        assert len(config.judges) == 1
        assert config.judges[0].model == "test-model"
        assert config.judges[0].weight == 0.5
        assert config.human_review_weight == 3.0
        assert "summarization" in config.criteria
        assert config.criteria["summarization"].dimensions[0].name == "clarity"

    def test_summarization_has_five_dimensions(self):
        config = load_evaluation_config()
        criteria = config.criteria["summarization"]
        assert len(criteria.dimensions) == 5
        names = criteria.dimension_names()
        assert "accuracy" in names
        assert "completeness" in names
        assert "conciseness" in names
        assert "clarity" in names
        assert "key_insight_capture" in names

    def test_digest_creation_has_four_dimensions(self):
        config = load_evaluation_config()
        criteria = config.criteria["digest_creation"]
        assert len(criteria.dimensions) == 4
        names = criteria.dimension_names()
        assert "narrative_flow" in names
        assert "theme_coherence" in names

    def test_podcast_script_has_four_dimensions(self):
        config = load_evaluation_config()
        criteria = config.criteria["podcast_script"]
        assert len(criteria.dimensions) == 4
        names = criteria.dimension_names()
        assert "conversational_tone" in names
        assert "pacing" in names

    def test_default_has_four_dimensions(self):
        config = load_evaluation_config()
        criteria = config.criteria["_default"]
        assert len(criteria.dimensions) == 4


class TestGetCriteriaForStep:
    def test_known_step(self):
        config = load_evaluation_config()
        criteria = get_criteria_for_step(config, "summarization")
        assert criteria.step == "summarization"
        assert len(criteria.dimensions) == 5

    def test_unknown_step_falls_back_to_default(self):
        config = load_evaluation_config()
        criteria = get_criteria_for_step(config, "some_unknown_step")
        assert criteria.step == "_default"

    def test_no_default_raises(self):
        config = EvaluationConfig(criteria={
            "summarization": StepCriteria(step="summarization")
        })
        with pytest.raises(ValueError, match="No criteria found"):
            get_criteria_for_step(config, "unknown_step")
