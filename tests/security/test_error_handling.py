from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# Ensure modules are loaded
from src.api.content_routes import (
    _ingestion_tasks,
    _run_content_ingestion,
    _run_content_summarization,
    _summarization_tasks,
)
from src.api.digest_routes import generate_digest_task
from src.models.content import ContentSource
from src.models.digest import DigestRequest, DigestType


@pytest.mark.asyncio
async def test_content_ingestion_error_handling():
    """Test that content ingestion handles errors securely (no leakage)."""
    task_id = "test_ingestion_safe"
    _ingestion_tasks[task_id] = {"status": "queued"}

    sensitive_error = "OperationalError: FATAL: password authentication failed"

    with patch("src.ingestion.gmail.GmailContentIngestionService") as MockService:
        instance = MockService.return_value
        instance.ingest_content.side_effect = Exception(sensitive_error)

        await _run_content_ingestion(
            task_id=task_id,
            source=ContentSource.GMAIL,
            max_results=10,
            days_back=7,
            force_reprocess=False,
        )

        task_status = _ingestion_tasks[task_id]
        assert task_status["status"] == "error"
        # Verify sensitive details are NOT leaked
        assert sensitive_error not in task_status["message"]
        # Verify generic message is present
        assert "An internal error occurred" in task_status["message"]


@pytest.mark.asyncio
async def test_content_summarization_error_handling():
    """Test that content summarization handles errors securely (no leakage)."""
    task_id = "test_summarization_safe"
    _summarization_tasks[task_id] = {
        "status": "queued",
        "completed": 0,
        "failed": 0,
        "processed": 0,
        "progress": 0,
    }

    sensitive_error = "ConnectionTimeout: Failed to connect to Anthropic API"

    with patch(
        "src.processors.summarizer.NewsletterSummarizer", side_effect=Exception(sensitive_error)
    ):
        await _run_content_summarization(task_id=task_id, content_ids=[1], force=False)

        task_status = _summarization_tasks[task_id]
        assert task_status["status"] == "error"
        assert sensitive_error not in task_status["message"]
        assert "An internal error occurred" in task_status["message"]


@pytest.mark.asyncio
async def test_digest_generation_error_handling():
    """Test that digest generation handles errors securely (no leakage)."""
    sensitive_error = "ValueError: Invalid API Key 'sk-proj-12345'"

    request = DigestRequest(
        digest_type=DigestType.DAILY, period_start=datetime.now(), period_end=datetime.now()
    )

    mock_db = MagicMock()
    mock_digest = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_digest

    mock_db_ctx = MagicMock()
    mock_db_ctx.__enter__.return_value = mock_db
    mock_db_ctx.__exit__.return_value = None

    with (
        patch("src.api.digest_routes.get_db", return_value=mock_db_ctx),
        patch("src.api.digest_routes.DigestCreator") as MockCreator,
    ):
        instance = MockCreator.return_value
        instance.create_digest.side_effect = Exception(sensitive_error)

        await generate_digest_task(request)

        # Verify review_notes has generic message
        assert sensitive_error not in mock_digest.review_notes
        assert "An internal error occurred" in mock_digest.review_notes
