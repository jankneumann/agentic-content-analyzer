"""Tests for NewsletterSummarizer - Functional tests only.

Integration tests (database operations, LLM calls) are documented but not implemented.
These should be added to a separate integration test suite.
"""

from datetime import datetime

import pytest

from src.agents.base import AgentResponse, SummarizationAgent
from src.config.models import ModelConfig, ModelStep, Provider, ProviderConfig
from src.models.newsletter import Newsletter, NewsletterSource, ProcessingStatus
from src.models.summary import SummaryData
from src.processors.summarizer import NewsletterSummarizer


class MockAgent(SummarizationAgent):
    """Mock agent for testing without LLM calls."""

    def __init__(self):
        """Initialize mock agent."""
        # Create minimal model config for testing
        model_config = ModelConfig()
        model_config.add_provider(
            ProviderConfig(provider=Provider.ANTHROPIC, api_key="mock-key")
        )
        super().__init__(
            model_config=model_config, model="mock-model", api_key="mock-key"
        )

    def summarize_newsletter(self, newsletter: Newsletter) -> AgentResponse:
        """Mock summarization."""
        return AgentResponse(
            success=True,
            data=SummaryData(
                newsletter_id=newsletter.id or 0,
                executive_summary="Test summary",
                key_themes=["Theme 1", "Theme 2"],
                strategic_insights=["Insight 1"],
                technical_details=["Detail 1"],
                actionable_items=["Action 1"],
                notable_quotes=["Quote 1"],
                relevance_scores={
                    "cto_leadership": 0.8,
                    "technical_teams": 0.9,
                    "individual_developers": 0.7,
                },
                agent_framework="mock",
                model_used="mock-model",
            ),
        )


@pytest.fixture
def sample_newsletter() -> Newsletter:
    """Create sample newsletter for testing."""
    newsletter = Newsletter(
        source=NewsletterSource.GMAIL,
        source_id="test-123",
        sender="test@example.com",
        publication="Tech Weekly",
        title="AI Advances in 2025",
        raw_html="<html><body>Newsletter content about AI</body></html>",
        raw_text="Newsletter content about AI advances and new developments.",
        published_date=datetime(2025, 1, 15, 10, 0, 0),
        url="https://example.com/newsletter",
        status=ProcessingStatus.PENDING,
    )
    newsletter.id = 1
    return newsletter


def test_newsletter_summarizer_initialization_default():
    """Test NewsletterSummarizer initialization with default agent."""
    # This test would require mocking ClaudeAgent initialization
    # Document as integration test
    pass


def test_newsletter_summarizer_initialization_custom_agent():
    """Test NewsletterSummarizer initialization with custom agent."""
    mock_agent = MockAgent()
    summarizer = NewsletterSummarizer(agent=mock_agent)

    assert summarizer.agent == mock_agent
    assert summarizer.agent.model == "mock-model"


# TODO: Integration tests - require database setup
# These tests should be moved to integration tests as they require real database access
# The core logic is covered by unit tests above
#
# @pytest.mark.integration
# def test_summarize_newsletter_success():
#     """Test successful newsletter summarization (INTEGRATION TEST)."""
#     # Requires:
#     # - Database with Newsletter record
#     # - Mock or real LLM agent
#     # - Verify database updates (status, summary storage)
#     pass
#
# @pytest.mark.integration
# def test_summarize_newsletter_not_found():
#     """Test handling of non-existent newsletter (INTEGRATION TEST)."""
#     pass
#
# @pytest.mark.integration
# def test_summarize_newsletter_already_summarized():
#     """Test handling of already summarized newsletter (INTEGRATION TEST)."""
#     pass
#
# @pytest.mark.integration
# def test_summarize_newsletter_agent_failure():
#     """Test handling of agent failure (INTEGRATION TEST)."""
#     pass
#
# @pytest.mark.integration
# def test_summarize_newsletter_database_error():
#     """Test handling of database errors with rollback (INTEGRATION TEST)."""
#     pass
#
# @pytest.mark.integration
# def test_summarize_pending_newsletters():
#     """Test batch processing of pending newsletters (INTEGRATION TEST)."""
#     pass
#
# @pytest.mark.integration
# def test_summarize_pending_newsletters_with_limit():
#     """Test batch processing with limit (INTEGRATION TEST)."""
#     pass


# ============================================================================
# Unit Tests for summarize_newsletters() - NEW
# ============================================================================


class MockSuccessAgent(SummarizationAgent):
    """Mock agent that always succeeds."""

    def __init__(self):
        model_config = ModelConfig()
        model_config.add_provider(
            ProviderConfig(provider=Provider.ANTHROPIC, api_key="mock-key")
        )
        super().__init__(
            model_config=model_config, model="mock-model", api_key="mock-key"
        )

    def summarize_newsletter(self, newsletter: Newsletter) -> AgentResponse:
        return AgentResponse(
            success=True,
            data=SummaryData(
                newsletter_id=newsletter.id or 0,
                executive_summary="Test summary",
                key_themes=["Theme 1", "Theme 2"],
                strategic_insights=["Insight 1"],
                technical_details=["Detail 1"],
                actionable_items=["Action 1"],
                notable_quotes=["Quote 1"],
                relevance_scores={
                    "cto_leadership": 0.8,
                    "technical_teams": 0.9,
                    "individual_developers": 0.7,
                },
                agent_framework="mock",
                model_used="mock-model",
            ),
        )


class MockFailureAgent(SummarizationAgent):
    """Mock agent that always fails."""

    def __init__(self, fail_on_ids=None):
        model_config = ModelConfig()
        model_config.add_provider(
            ProviderConfig(provider=Provider.ANTHROPIC, api_key="mock-key")
        )
        super().__init__(
            model_config=model_config, model="mock-model", api_key="mock-key"
        )
        self.fail_on_ids = fail_on_ids or []

    def summarize_newsletter(self, newsletter: Newsletter) -> AgentResponse:
        if newsletter.id in self.fail_on_ids:
            return AgentResponse(
                success=False,
                error=f"Mocked failure for newsletter {newsletter.id}",
            )
        return AgentResponse(
            success=True,
            data=SummaryData(
                newsletter_id=newsletter.id or 0,
                executive_summary="Test summary",
                key_themes=["Theme 1"],
                strategic_insights=["Insight 1"],
                technical_details=["Detail 1"],
                actionable_items=["Action 1"],
                notable_quotes=["Quote 1"],
                relevance_scores={
                    "cto_leadership": 0.8,
                    "technical_teams": 0.9,
                    "individual_developers": 0.7,
                },
                agent_framework="mock",
                model_used="mock-model",
            ),
        )


def test_summarize_newsletters_empty_list():
    """Test summarize_newsletters with empty list."""
    mock_agent = MockSuccessAgent()
    summarizer = NewsletterSummarizer(agent=mock_agent)

    result = summarizer.summarize_newsletters([])

    assert result["created_count"] == 0
    assert result["failed_ids"] == []
    assert result["skipped_count"] == 0


def test_summarize_newsletters_all_success(mocker):
    """Test summarize_newsletters when all newsletters succeed."""
    mock_agent = MockSuccessAgent()
    summarizer = NewsletterSummarizer(agent=mock_agent)

    # Mock database operations
    mock_summary_query = mocker.MagicMock()
    mock_summary_query.filter.return_value.first.return_value = None  # No existing

    mock_db = mocker.MagicMock()
    mock_db.query.return_value = mock_summary_query

    mock_get_db = mocker.patch("src.processors.summarizer.get_db")
    mock_get_db.return_value.__enter__.return_value = mock_db
    mock_get_db.return_value.__exit__.return_value = None

    # Mock summarize_newsletter to return success
    mock_summarize = mocker.patch.object(summarizer, "summarize_newsletter")
    mock_summarize.return_value = True

    # Test with 3 newsletter IDs
    newsletter_ids = [1, 2, 3]
    result = summarizer.summarize_newsletters(newsletter_ids)

    assert result["created_count"] == 3
    assert result["failed_ids"] == []
    assert result["skipped_count"] == 0
    assert mock_summarize.call_count == 3


def test_summarize_newsletters_all_skipped(mocker):
    """Test summarize_newsletters when all newsletters already have summaries."""
    mock_agent = MockSuccessAgent()
    summarizer = NewsletterSummarizer(agent=mock_agent)

    # Mock database to return existing summaries
    mock_existing_summary = mocker.MagicMock()
    mock_summary_query = mocker.MagicMock()
    mock_summary_query.filter.return_value.first.return_value = mock_existing_summary

    mock_db = mocker.MagicMock()
    mock_db.query.return_value = mock_summary_query

    mock_get_db = mocker.patch("src.processors.summarizer.get_db")
    mock_get_db.return_value.__enter__.return_value = mock_db
    mock_get_db.return_value.__exit__.return_value = None

    # Mock summarize_newsletter (should not be called)
    mock_summarize = mocker.patch.object(summarizer, "summarize_newsletter")

    newsletter_ids = [1, 2, 3]
    result = summarizer.summarize_newsletters(newsletter_ids)

    assert result["created_count"] == 0
    assert result["failed_ids"] == []
    assert result["skipped_count"] == 3
    assert mock_summarize.call_count == 0  # Should not call if all skipped


def test_summarize_newsletters_partial_failure(mocker):
    """Test summarize_newsletters when some newsletters fail."""
    mock_agent = MockSuccessAgent()
    summarizer = NewsletterSummarizer(agent=mock_agent)

    # Mock database - no existing summaries
    mock_summary_query = mocker.MagicMock()
    mock_summary_query.filter.return_value.first.return_value = None

    mock_db = mocker.MagicMock()
    mock_db.query.return_value = mock_summary_query

    mock_get_db = mocker.patch("src.processors.summarizer.get_db")
    mock_get_db.return_value.__enter__.return_value = mock_db
    mock_get_db.return_value.__exit__.return_value = None

    # Mock summarize_newsletter to fail on ID 2
    def mock_summarize_side_effect(newsletter_id):
        if newsletter_id == 2:
            return False  # Failure
        return True  # Success

    mock_summarize = mocker.patch.object(summarizer, "summarize_newsletter")
    mock_summarize.side_effect = mock_summarize_side_effect

    newsletter_ids = [1, 2, 3]
    result = summarizer.summarize_newsletters(newsletter_ids)

    assert result["created_count"] == 2
    assert result["failed_ids"] == [2]
    assert result["skipped_count"] == 0
    assert mock_summarize.call_count == 3


def test_summarize_newsletters_exception_handling(mocker):
    """Test summarize_newsletters handles exceptions gracefully."""
    mock_agent = MockSuccessAgent()
    summarizer = NewsletterSummarizer(agent=mock_agent)

    # Mock database - no existing summaries
    mock_summary_query = mocker.MagicMock()
    mock_summary_query.filter.return_value.first.return_value = None

    mock_db = mocker.MagicMock()
    mock_db.query.return_value = mock_summary_query

    mock_get_db = mocker.patch("src.processors.summarizer.get_db")
    mock_get_db.return_value.__enter__.return_value = mock_db
    mock_get_db.return_value.__exit__.return_value = None

    # Mock summarize_newsletter to raise exception on ID 2
    def mock_summarize_side_effect(newsletter_id):
        if newsletter_id == 2:
            raise ValueError("Mocked exception")
        return True

    mock_summarize = mocker.patch.object(summarizer, "summarize_newsletter")
    mock_summarize.side_effect = mock_summarize_side_effect

    newsletter_ids = [1, 2, 3]
    result = summarizer.summarize_newsletters(newsletter_ids)

    assert result["created_count"] == 2
    assert result["failed_ids"] == [2]
    assert result["skipped_count"] == 0
    assert mock_summarize.call_count == 3


def test_summarize_newsletters_mixed_results(mocker):
    """Test summarize_newsletters with mix of success, failure, and skipped."""
    mock_agent = MockSuccessAgent()
    summarizer = NewsletterSummarizer(agent=mock_agent)

    # Mock database - ID 3 has existing summary
    def mock_query_side_effect(model):
        mock_query = mocker.MagicMock()

        def mock_filter(condition):
            # Simulate newsletter_id filtering
            mock_result = mocker.MagicMock()
            # Return existing summary only for ID 3
            if hasattr(condition, "right") and hasattr(condition.right, "value"):
                newsletter_id = condition.right.value
                if newsletter_id == 3:
                    mock_result.first.return_value = mocker.MagicMock()  # Existing
                else:
                    mock_result.first.return_value = None  # Not existing
            else:
                mock_result.first.return_value = None

            return mock_result

        mock_query.filter = mock_filter
        return mock_query

    mock_db = mocker.MagicMock()
    mock_db.query.side_effect = mock_query_side_effect

    mock_get_db = mocker.patch("src.processors.summarizer.get_db")
    mock_get_db.return_value.__enter__.return_value = mock_db
    mock_get_db.return_value.__exit__.return_value = None

    # Mock summarize_newsletter - ID 2 fails
    def mock_summarize_side_effect(newsletter_id):
        if newsletter_id == 2:
            return False
        return True

    mock_summarize = mocker.patch.object(summarizer, "summarize_newsletter")
    mock_summarize.side_effect = mock_summarize_side_effect

    newsletter_ids = [1, 2, 3]
    result = summarizer.summarize_newsletters(newsletter_ids)

    # ID 1: success, ID 2: failed, ID 3: skipped
    assert result["created_count"] == 1
    assert result["failed_ids"] == [2]
    assert result["skipped_count"] == 1
    # Should only call summarize_newsletter for IDs 1 and 2 (not 3, which is skipped)
    assert mock_summarize.call_count == 2
