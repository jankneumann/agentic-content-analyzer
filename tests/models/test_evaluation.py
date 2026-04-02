"""Tests for evaluation and routing models."""

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.evaluation import (
    DatasetStatus,
    EvaluationConsensus,
    EvaluationDataset,
    EvaluationResult,
    EvaluationSample,
    JudgeType,
    Preference,
    RoutingConfig,
    RoutingDecision,
    RoutingMode,
)


# ---- StrEnum tests ----


class TestEnums:
    def test_routing_mode_values(self):
        assert RoutingMode.FIXED == "fixed"
        assert RoutingMode.DYNAMIC == "dynamic"

    def test_dataset_status_values(self):
        assert DatasetStatus.PENDING_EVALUATION == "pending_evaluation"
        assert DatasetStatus.EVALUATED == "evaluated"
        assert DatasetStatus.CALIBRATED == "calibrated"

    def test_judge_type_values(self):
        assert JudgeType.LLM == "llm"
        assert JudgeType.HUMAN == "human"

    def test_preference_values(self):
        assert Preference.STRONG_WINS == "strong_wins"
        assert Preference.WEAK_WINS == "weak_wins"
        assert Preference.TIE == "tie"


# ---- Model instantiation tests ----


class TestModelCreation:
    def test_create_routing_config(self, db_session):
        config = RoutingConfig(
            step="summarization",
            mode=RoutingMode.FIXED,
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
            threshold=0.7,
            enabled=True,
        )
        db_session.add(config)
        db_session.commit()

        fetched = db_session.query(RoutingConfig).filter_by(step="summarization").one()
        assert fetched.mode == "fixed"
        assert fetched.strong_model == "claude-sonnet-4-5"
        assert fetched.threshold == 0.7
        assert fetched.enabled is True

    def test_create_evaluation_dataset(self, db_session):
        dataset = EvaluationDataset(
            step="summarization",
            name="Test Dataset",
            sample_count=10,
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
        )
        db_session.add(dataset)
        db_session.commit()

        fetched = db_session.query(EvaluationDataset).filter_by(name="Test Dataset").one()
        assert fetched.step == "summarization"
        assert fetched.sample_count == 10
        assert fetched.status == DatasetStatus.PENDING_EVALUATION

    def test_create_evaluation_sample(self, db_session):
        dataset = EvaluationDataset(
            step="summarization",
            sample_count=1,
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
        )
        db_session.add(dataset)
        db_session.flush()

        sample = EvaluationSample(
            dataset_id=dataset.id,
            prompt_text="Summarize this article about AI",
            prompt_hash="abc123",
            strong_output="Strong model output",
            weak_output="Weak model output",
            strong_tokens=100,
            weak_tokens=80,
        )
        db_session.add(sample)
        db_session.commit()

        fetched = db_session.query(EvaluationSample).filter_by(prompt_hash="abc123").one()
        assert fetched.prompt_text == "Summarize this article about AI"
        assert fetched.strong_tokens == 100

    def test_create_evaluation_result(self, db_session):
        dataset = EvaluationDataset(
            step="summarization",
            sample_count=1,
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
        )
        db_session.add(dataset)
        db_session.flush()

        sample = EvaluationSample(
            dataset_id=dataset.id,
            prompt_text="Test prompt",
            prompt_hash="def456",
        )
        db_session.add(sample)
        db_session.flush()

        result = EvaluationResult(
            sample_id=sample.id,
            judge_model="claude-sonnet-4-5",
            judge_type=JudgeType.LLM,
            preference=Preference.STRONG_WINS,
            critiques={"accuracy": "strong is better", "completeness": "tie"},
            reasoning="Strong model provided more detail",
            position_order="strong_first",
        )
        db_session.add(result)
        db_session.commit()

        fetched = db_session.query(EvaluationResult).filter_by(judge_model="claude-sonnet-4-5").one()
        assert fetched.preference == "strong_wins"
        assert fetched.weight == 1.0  # default
        assert fetched.critiques["accuracy"] == "strong is better"

    def test_create_evaluation_consensus(self, db_session):
        dataset = EvaluationDataset(
            step="summarization",
            sample_count=1,
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
        )
        db_session.add(dataset)
        db_session.flush()

        sample = EvaluationSample(
            dataset_id=dataset.id,
            prompt_text="Test prompt",
            prompt_hash="ghi789",
        )
        db_session.add(sample)
        db_session.flush()

        consensus = EvaluationConsensus(
            sample_id=sample.id,
            consensus_preference=Preference.TIE,
            agreement_rate=0.85,
            dimension_verdicts={"accuracy": "tie", "completeness": "strong_wins"},
        )
        db_session.add(consensus)
        db_session.commit()

        fetched = db_session.query(EvaluationConsensus).filter_by(sample_id=sample.id).one()
        assert fetched.consensus_preference == "tie"
        assert fetched.agreement_rate == 0.85

    def test_create_routing_decision(self, db_session):
        decision = RoutingDecision(
            step="summarization",
            prompt_hash="jkl012",
            complexity_score=0.3,
            threshold=0.5,
            model_selected="claude-haiku-4-5",
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
            cost_actual=0.001,
            tokens_input=500,
            tokens_output=200,
        )
        db_session.add(decision)
        db_session.commit()

        fetched = db_session.query(RoutingDecision).filter_by(prompt_hash="jkl012").one()
        assert fetched.complexity_score == 0.3
        assert fetched.model_selected == "claude-haiku-4-5"


# ---- Default values tests ----


class TestDefaults:
    def test_routing_config_defaults(self, db_session):
        config = RoutingConfig(step="theme_analysis")
        db_session.add(config)
        db_session.commit()

        fetched = db_session.query(RoutingConfig).filter_by(step="theme_analysis").one()
        assert fetched.mode == RoutingMode.FIXED
        assert fetched.threshold == 0.5
        assert fetched.enabled is False

    def test_dataset_status_default(self, db_session):
        dataset = EvaluationDataset(
            step="summarization",
            sample_count=5,
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
        )
        db_session.add(dataset)
        db_session.commit()

        fetched = db_session.query(EvaluationDataset).one()
        assert fetched.status == DatasetStatus.PENDING_EVALUATION

    def test_evaluation_result_weight_default(self, db_session):
        dataset = EvaluationDataset(
            step="summarization",
            sample_count=1,
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
        )
        db_session.add(dataset)
        db_session.flush()

        sample = EvaluationSample(
            dataset_id=dataset.id,
            prompt_text="Test",
            prompt_hash="test_default",
        )
        db_session.add(sample)
        db_session.flush()

        result = EvaluationResult(
            sample_id=sample.id,
            judge_model="claude-sonnet-4-5",
            judge_type="llm",
            preference="tie",
            critiques={"overall": "equal"},
        )
        db_session.add(result)
        db_session.commit()

        assert result.weight == 1.0


# ---- Required fields tests ----


class TestRequiredFields:
    def test_routing_config_requires_step(self, db_session):
        config = RoutingConfig(mode="fixed")
        db_session.add(config)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_evaluation_dataset_requires_strong_model(self, db_session):
        dataset = EvaluationDataset(
            step="summarization",
            sample_count=5,
            weak_model="claude-haiku-4-5",
        )
        db_session.add(dataset)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_evaluation_sample_requires_dataset_id(self, db_session):
        sample = EvaluationSample(
            prompt_text="Test",
            prompt_hash="test123",
        )
        db_session.add(sample)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_evaluation_result_requires_critiques(self, db_session):
        dataset = EvaluationDataset(
            step="summarization",
            sample_count=1,
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
        )
        db_session.add(dataset)
        db_session.flush()

        sample = EvaluationSample(
            dataset_id=dataset.id,
            prompt_text="Test",
            prompt_hash="req_test",
        )
        db_session.add(sample)
        db_session.flush()

        result = EvaluationResult(
            sample_id=sample.id,
            judge_model="claude-sonnet-4-5",
            judge_type="llm",
            preference="tie",
            # critiques is missing — nullable=False
        )
        db_session.add(result)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_routing_decision_requires_complexity_score(self, db_session):
        decision = RoutingDecision(
            step="summarization",
            prompt_hash="test",
            threshold=0.5,
            model_selected="claude-haiku-4-5",
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
            # complexity_score is missing — nullable=False
        )
        db_session.add(decision)
        with pytest.raises(IntegrityError):
            db_session.commit()


# ---- Relationship tests ----


class TestRelationships:
    def _create_dataset_with_samples(self, db_session, num_samples=2):
        """Helper to create a dataset with samples."""
        dataset = EvaluationDataset(
            step="summarization",
            name="Relationship Test",
            sample_count=num_samples,
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
        )
        db_session.add(dataset)
        db_session.flush()

        samples = []
        for i in range(num_samples):
            sample = EvaluationSample(
                dataset_id=dataset.id,
                prompt_text=f"Prompt {i}",
                prompt_hash=f"hash_{i}_{id(dataset)}",
            )
            db_session.add(sample)
            samples.append(sample)

        db_session.flush()
        return dataset, samples

    def test_dataset_samples_relationship(self, db_session):
        dataset, samples = self._create_dataset_with_samples(db_session)
        db_session.commit()

        fetched = db_session.query(EvaluationDataset).filter_by(id=dataset.id).one()
        assert len(fetched.samples) == 2
        assert fetched.samples[0].prompt_text.startswith("Prompt")

    def test_sample_dataset_back_populates(self, db_session):
        dataset, samples = self._create_dataset_with_samples(db_session, num_samples=1)
        db_session.commit()

        fetched_sample = db_session.query(EvaluationSample).filter_by(id=samples[0].id).one()
        assert fetched_sample.dataset.name == "Relationship Test"

    def test_sample_results_relationship(self, db_session):
        dataset, samples = self._create_dataset_with_samples(db_session, num_samples=1)
        sample = samples[0]

        result1 = EvaluationResult(
            sample_id=sample.id,
            judge_model="claude-sonnet-4-5",
            judge_type="llm",
            preference="strong_wins",
            critiques={"overall": "strong better"},
            position_order="strong_first",
        )
        result2 = EvaluationResult(
            sample_id=sample.id,
            judge_model="gpt-4o",
            judge_type="llm",
            preference="tie",
            critiques={"overall": "equal"},
            position_order="weak_first",
        )
        db_session.add_all([result1, result2])
        db_session.commit()

        fetched = db_session.query(EvaluationSample).filter_by(id=sample.id).one()
        assert len(fetched.results) == 2

    def test_sample_consensus_relationship(self, db_session):
        dataset, samples = self._create_dataset_with_samples(db_session, num_samples=1)
        sample = samples[0]

        consensus = EvaluationConsensus(
            sample_id=sample.id,
            consensus_preference="strong_wins",
            agreement_rate=0.9,
        )
        db_session.add(consensus)
        db_session.commit()

        fetched = db_session.query(EvaluationSample).filter_by(id=sample.id).one()
        assert fetched.consensus is not None
        assert fetched.consensus.agreement_rate == 0.9

    def test_consensus_sample_back_populates(self, db_session):
        dataset, samples = self._create_dataset_with_samples(db_session, num_samples=1)
        sample = samples[0]

        consensus = EvaluationConsensus(
            sample_id=sample.id,
            consensus_preference="tie",
            agreement_rate=0.75,
        )
        db_session.add(consensus)
        db_session.commit()

        fetched = db_session.query(EvaluationConsensus).filter_by(sample_id=sample.id).one()
        assert fetched.sample.prompt_text == "Prompt 0"


# ---- Cascade delete tests ----


class TestCascadeDeletes:
    def test_delete_dataset_cascades_to_samples(self, db_session):
        dataset = EvaluationDataset(
            step="summarization",
            sample_count=2,
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
        )
        db_session.add(dataset)
        db_session.flush()

        for i in range(2):
            sample = EvaluationSample(
                dataset_id=dataset.id,
                prompt_text=f"Cascade test {i}",
                prompt_hash=f"cascade_{i}",
            )
            db_session.add(sample)
        db_session.commit()

        assert db_session.query(EvaluationSample).filter_by(dataset_id=dataset.id).count() == 2

        db_session.delete(dataset)
        db_session.commit()

        assert db_session.query(EvaluationSample).filter_by(dataset_id=dataset.id).count() == 0

    def test_delete_sample_cascades_to_results(self, db_session):
        dataset = EvaluationDataset(
            step="summarization",
            sample_count=1,
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
        )
        db_session.add(dataset)
        db_session.flush()

        sample = EvaluationSample(
            dataset_id=dataset.id,
            prompt_text="Cascade result test",
            prompt_hash="cascade_result",
        )
        db_session.add(sample)
        db_session.flush()

        result = EvaluationResult(
            sample_id=sample.id,
            judge_model="claude-sonnet-4-5",
            judge_type="llm",
            preference="tie",
            critiques={"overall": "equal"},
        )
        db_session.add(result)
        db_session.commit()

        sample_id = sample.id
        assert db_session.query(EvaluationResult).filter_by(sample_id=sample_id).count() == 1

        db_session.delete(sample)
        db_session.commit()

        assert db_session.query(EvaluationResult).filter_by(sample_id=sample_id).count() == 0

    def test_delete_sample_cascades_to_consensus(self, db_session):
        dataset = EvaluationDataset(
            step="summarization",
            sample_count=1,
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
        )
        db_session.add(dataset)
        db_session.flush()

        sample = EvaluationSample(
            dataset_id=dataset.id,
            prompt_text="Cascade consensus test",
            prompt_hash="cascade_consensus",
        )
        db_session.add(sample)
        db_session.flush()

        consensus = EvaluationConsensus(
            sample_id=sample.id,
            consensus_preference="strong_wins",
            agreement_rate=0.95,
        )
        db_session.add(consensus)
        db_session.commit()

        sample_id = sample.id
        assert db_session.query(EvaluationConsensus).filter_by(sample_id=sample_id).count() == 1

        db_session.delete(sample)
        db_session.commit()

        assert db_session.query(EvaluationConsensus).filter_by(sample_id=sample_id).count() == 0

    def test_delete_dataset_cascades_through_samples_to_results(self, db_session):
        """Deleting a dataset should cascade through samples to results and consensus."""
        dataset = EvaluationDataset(
            step="summarization",
            sample_count=1,
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
        )
        db_session.add(dataset)
        db_session.flush()

        sample = EvaluationSample(
            dataset_id=dataset.id,
            prompt_text="Deep cascade test",
            prompt_hash="deep_cascade",
        )
        db_session.add(sample)
        db_session.flush()

        result = EvaluationResult(
            sample_id=sample.id,
            judge_model="claude-sonnet-4-5",
            judge_type="llm",
            preference="strong_wins",
            critiques={"overall": "strong"},
        )
        consensus = EvaluationConsensus(
            sample_id=sample.id,
            consensus_preference="strong_wins",
            agreement_rate=1.0,
        )
        db_session.add_all([result, consensus])
        db_session.commit()

        sample_id = sample.id
        db_session.delete(dataset)
        db_session.commit()

        assert db_session.query(EvaluationResult).filter_by(sample_id=sample_id).count() == 0
        assert db_session.query(EvaluationConsensus).filter_by(sample_id=sample_id).count() == 0


# ---- Unique constraint tests ----


class TestUniqueConstraints:
    def test_routing_config_step_unique(self, db_session):
        config1 = RoutingConfig(step="summarization")
        config2 = RoutingConfig(step="summarization")
        db_session.add(config1)
        db_session.commit()

        db_session.add(config2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_consensus_sample_id_unique(self, db_session):
        dataset = EvaluationDataset(
            step="summarization",
            sample_count=1,
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
        )
        db_session.add(dataset)
        db_session.flush()

        sample = EvaluationSample(
            dataset_id=dataset.id,
            prompt_text="Unique test",
            prompt_hash="unique_test",
        )
        db_session.add(sample)
        db_session.flush()

        c1 = EvaluationConsensus(
            sample_id=sample.id,
            consensus_preference="tie",
        )
        db_session.add(c1)
        db_session.commit()

        c2 = EvaluationConsensus(
            sample_id=sample.id,
            consensus_preference="strong_wins",
        )
        db_session.add(c2)
        with pytest.raises(IntegrityError):
            db_session.commit()
