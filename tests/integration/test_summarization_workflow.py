"""Integration tests for content summarization workflow.

Tests the end-to-end flow:
1. Content exists in database (PARSED status)
2. Summarizer processes content
3. Summary is stored in database
4. Content status updated to COMPLETED
"""

from unittest.mock import patch

import pytest

from src.config.models import MODEL_REGISTRY
from src.models.content import Content, ContentStatus
from src.models.summary import Summary
from src.processors.summarizer import NewsletterSummarizer


@pytest.mark.integration
def test_summarize_content_success(db_session, sample_contents, mock_anthropic_client, mock_get_db):
    """Test successful content summarization workflow."""
    content = sample_contents[0]

    # Verify initial state
    assert content.status == ContentStatus.PARSED

    # Ensure no summary exists
    existing = db_session.query(Summary).filter(Summary.content_id == content.id).first()
    assert existing is None

    # Run summarization with mocked LLM and database
    with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_anthropic_client

        with patch("src.processors.summarizer.get_db", mock_get_db):
            summarizer = NewsletterSummarizer()
            result = summarizer.summarize_content(content.id)

    # Verify success
    assert result is True

    # Verify content status updated
    db_session.refresh(content)
    assert content.status == ContentStatus.COMPLETED

    # Verify summary was created
    summary = db_session.query(Summary).filter(Summary.content_id == content.id).first()

    assert summary is not None
    assert summary.executive_summary == "Test summary of newsletter content."
    assert len(summary.key_themes) == 3
    assert "Theme 1" in summary.key_themes
    assert len(summary.strategic_insights) == 2
    assert len(summary.technical_details) == 2
    assert summary.relevance_scores["cto_leadership"] == 0.8
    assert summary.agent_framework == "claude"
    # Verify model is from registry (behavior-based testing)
    assert summary.model_used in MODEL_REGISTRY, f"Model {summary.model_used} not in registry"
    # Verify model version is tracked
    assert summary.model_version is not None, "Model version should be tracked"
    assert isinstance(summary.model_version, str), "Model version should be a string"
    assert len(summary.model_version) > 0, "Model version should not be empty"
    assert summary.token_usage == 1500  # 1000 input + 500 output


@pytest.mark.integration
def test_summarize_content_not_found(db_session, mock_get_db):
    """Test handling of non-existent content."""
    with patch("src.agents.claude.summarizer.Anthropic"):
        with patch("src.processors.summarizer.get_db", mock_get_db):
            summarizer = NewsletterSummarizer()
            result = summarizer.summarize_content(99999)  # Non-existent ID

    assert result is False


@pytest.mark.integration
def test_summarize_content_already_summarized(
    db_session, sample_contents, sample_summaries, mock_get_db
):
    """Test that already-summarized contents are skipped."""
    content = sample_contents[0]

    # Verify summary already exists
    existing = db_session.query(Summary).filter(Summary.content_id == content.id).first()
    assert existing is not None

    # Run summarization
    with patch("src.agents.claude.summarizer.Anthropic"):
        with patch("src.processors.summarizer.get_db", mock_get_db):
            summarizer = NewsletterSummarizer()
            result = summarizer.summarize_content(content.id)

    # Should return success (already summarized)
    assert result is True

    # Verify only one summary exists (no duplicate created)
    summaries = db_session.query(Summary).filter(Summary.content_id == content.id).all()
    assert len(summaries) == 1


@pytest.mark.integration
def test_summarize_content_llm_error(db_session, sample_contents, mock_get_db):
    """Test handling of LLM API errors."""
    content = sample_contents[0]

    # Mock LLM to raise exception
    mock_client = type("MockClient", (), {})()
    mock_client.messages = type("Messages", (), {})()
    mock_client.messages.create = lambda **kwargs: (_ for _ in ()).throw(Exception("API Error"))

    with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_client

        with patch("src.processors.summarizer.get_db", mock_get_db):
            summarizer = NewsletterSummarizer()
            result = summarizer.summarize_content(content.id)

    # Should handle error gracefully
    assert result is False

    # Verify content status is FAILED
    db_session.refresh(content)
    assert content.status == ContentStatus.FAILED
    assert content.error_message is not None
    assert "API Error" in content.error_message


@pytest.mark.integration
def test_summarize_pending_contents(
    db_session, sample_contents, mock_anthropic_client, mock_get_db
):
    """Test batch summarization of pending contents."""
    # All contents should be PARSED
    for content in sample_contents:
        assert content.status == ContentStatus.PARSED

    # Run batch summarization
    with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_anthropic_client

        with patch("src.processors.summarizer.get_db", mock_get_db):
            summarizer = NewsletterSummarizer()
            count = summarizer.summarize_pending_contents()

    # Should have summarized all 3 contents
    assert count == 3

    # Verify all contents are now COMPLETED
    for content in sample_contents:
        db_session.refresh(content)
        assert content.status == ContentStatus.COMPLETED

    # Verify summaries were created
    summaries = db_session.query(Summary).all()
    assert len(summaries) == 3


@pytest.mark.integration
def test_summarize_pending_contents_with_limit(
    db_session, sample_contents, mock_anthropic_client, mock_get_db
):
    """Test batch summarization with limit."""
    # Run batch summarization with limit of 2
    with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_anthropic_client

        with patch("src.processors.summarizer.get_db", mock_get_db):
            summarizer = NewsletterSummarizer()
            count = summarizer.summarize_pending_contents(limit=2)

    # Should have summarized only 2 contents
    assert count == 2

    # Verify summaries created
    summaries = db_session.query(Summary).all()
    assert len(summaries) == 2

    # Verify one content still parsed (pending summarization)
    pending = db_session.query(Content).filter(Content.status == ContentStatus.PARSED).count()
    assert pending == 1


@pytest.mark.integration
def test_summarize_content_status_transitions(
    db_session, sample_contents, mock_anthropic_client, mock_get_db
):
    """Test content status transitions during summarization."""
    content = sample_contents[0]

    # Start: PARSED
    assert content.status == ContentStatus.PARSED

    # During processing, status should be PROCESSING
    # (we can't easily test this without threading, but it's set in the code)

    # Run summarization
    with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_anthropic_client

        with patch("src.processors.summarizer.get_db", mock_get_db):
            summarizer = NewsletterSummarizer()
            result = summarizer.summarize_content(content.id)

    assert result is True

    # End: COMPLETED
    db_session.refresh(content)
    assert content.status == ContentStatus.COMPLETED
    assert content.error_message is None
