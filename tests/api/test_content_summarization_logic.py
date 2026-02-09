from unittest.mock import AsyncMock, patch

import pytest

from src.models.content import ContentSource, ContentStatus
from tests.factories.content import ContentFactory
from tests.factories.summary import SummaryFactory


class TestTriggerSummarizationLogic:
    """Tests for content summarization trigger logic."""

    @pytest.fixture
    def mock_enqueue(self):
        """Mock the queue enqueue function to avoid DB connection."""
        with patch(
            "src.api.content_routes._enqueue_summarization_batch_job", new_callable=AsyncMock
        ) as mock:
            mock.return_value = 123
            yield mock

    def test_identifies_correct_content(self, client, db_session, mock_enqueue):
        """Verify that only eligible content is selected for summarization."""
        # 1. Pending, No Summary -> Should be picked up
        c1 = ContentFactory(
            pending=True,
            source_type=ContentSource.MANUAL,
            source_id="c1",
            title="Pending No Summary",
            markdown_content="content",
            content_hash="h1",
        )

        # 2. Completed, Has Summary -> Should NOT be picked up
        c2 = ContentFactory(
            source_type=ContentSource.MANUAL,
            source_id="c2",
            title="Completed Has Summary",
            markdown_content="content",
            content_hash="h2",
            status=ContentStatus.COMPLETED,
        )
        SummaryFactory(
            content=c2,
            content_id=c2.id,
            executive_summary="sum",
            key_themes=[],
            strategic_insights=[],
            technical_details=[],
            actionable_items=[],
            notable_quotes=[],
            relevance_scores={},
            agent_framework="claude",
        )

        # 3. Parsed, Has Summary -> Should NOT be picked up
        c3 = ContentFactory(
            parsed=True,
            source_type=ContentSource.MANUAL,
            source_id="c3",
            title="Parsed Has Summary",
            markdown_content="content",
            content_hash="h3",
        )
        SummaryFactory(
            content=c3,
            content_id=c3.id,
            executive_summary="sum",
            key_themes=[],
            strategic_insights=[],
            technical_details=[],
            actionable_items=[],
            notable_quotes=[],
            relevance_scores={},
            agent_framework="claude",
        )

        # 4. Failed, No Summary -> Should NOT be picked up unless retry_failed=True
        ContentFactory(
            failed=True,
            source_type=ContentSource.MANUAL,
            source_id="c4",
            title="Failed No Summary",
            markdown_content="content",
            content_hash="h4",
        )

        # 5. Parsed, No Summary -> Should be picked up
        c5 = ContentFactory(
            parsed=True,
            source_type=ContentSource.MANUAL,
            source_id="c5",
            title="Parsed No Summary",
            markdown_content="content",
            content_hash="h5",
        )

        # Act: Trigger summarization (default: no force, no retry_failed)
        response = client.post("/api/v1/contents/summarize", json={})
        assert response.status_code == 200

        # Verify: Only c1 and c5 should be enqueued
        assert mock_enqueue.called
        call_args = mock_enqueue.call_args
        content_ids = call_args[0][0]  # first arg is content_ids

        assert set(content_ids) == {c1.id, c5.id}

    def test_retry_failed(self, client, db_session, mock_enqueue):
        """Verify retry_failed flag includes failed content."""
        c4 = ContentFactory(
            failed=True,
            source_type=ContentSource.MANUAL,
            source_id="c4_retry",
            title="Failed No Summary",
            markdown_content="content",
            content_hash="h4_retry",
        )

        # Act: Trigger with retry_failed=True
        response = client.post("/api/v1/contents/summarize", json={"retry_failed": True})
        assert response.status_code == 200

        # Verify: c4 should be enqueued
        call_args = mock_enqueue.call_args
        content_ids = call_args[0][0]
        assert c4.id in content_ids

    def test_force(self, client, db_session, mock_enqueue):
        """Verify force flag includes already summarized content."""
        c2 = ContentFactory(
            source_type=ContentSource.MANUAL,
            source_id="c2_force",
            title="Completed Has Summary",
            markdown_content="content",
            content_hash="h2_force",
            status=ContentStatus.COMPLETED,
        )
        SummaryFactory(
            content=c2,
            content_id=c2.id,
            executive_summary="sum",
            key_themes=[],
            strategic_insights=[],
            technical_details=[],
            actionable_items=[],
            notable_quotes=[],
            relevance_scores={},
            agent_framework="claude",
        )

        # Act: Trigger with content_ids and force=True
        response = client.post(
            "/api/v1/contents/summarize", json={"content_ids": [c2.id], "force": True}
        )
        assert response.status_code == 200

        # Verify: c2 should be enqueued despite having summary
        call_args = mock_enqueue.call_args
        content_ids = call_args[0][0]
        assert c2.id in content_ids
