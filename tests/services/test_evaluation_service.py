"""Tests for EvaluationService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.evaluation_service import (
    DatasetInfo,
    EvaluationReport,
    EvaluationService,
)


class TestCreateDataset:
    def test_creates_dataset_without_db(self):
        service = EvaluationService(db_session=None)
        info = service.create_dataset(
            step="summarization",
            name="test_dataset",
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
            sample_count=10,
        )
        assert isinstance(info, DatasetInfo)
        assert info.step == "summarization"
        assert info.name == "test_dataset"
        assert info.sample_count == 10

    def test_default_name(self):
        service = EvaluationService(db_session=None)
        info = service.create_dataset(step="summarization")
        assert info.step == "summarization"


class TestAddSample:
    def test_adds_sample_without_db(self):
        service = EvaluationService(db_session=None)
        sample_id = service.add_sample(
            dataset_id=1,
            prompt_text="Test prompt",
            strong_output="Strong output",
            weak_output="Weak output",
        )
        assert sample_id == 0  # No DB returns 0


class TestRunEvaluation:
    @pytest.mark.asyncio
    async def test_requires_db_session(self):
        service = EvaluationService(db_session=None)
        with pytest.raises(RuntimeError, match="Database session required"):
            await service.run_evaluation(1, MagicMock())


class TestGetDatasets:
    def test_returns_empty_without_db(self):
        service = EvaluationService(db_session=None)
        assert service.get_datasets() == []


class TestGenerateReport:
    def test_returns_empty_without_db(self):
        service = EvaluationService(db_session=None)
        assert service.generate_report() == []
