"""Integration tests for newsletter summarization workflow.

Tests the end-to-end flow:
1. Newsletter exists in database (PENDING status)
2. Summarizer processes newsletter
3. Summary is stored in database
4. Newsletter status updated to COMPLETED
"""

from unittest.mock import patch

import pytest

from src.models.newsletter import Newsletter, ProcessingStatus
from src.models.summary import NewsletterSummary
from src.processors.summarizer import NewsletterSummarizer


@pytest.mark.integration
def test_summarize_newsletter_success(
    db_session, sample_newsletters, mock_anthropic_client, mock_get_db
):
    """Test successful newsletter summarization workflow."""
    newsletter = sample_newsletters[0]

    # Verify initial state
    assert newsletter.status == ProcessingStatus.PENDING

    # Ensure no summary exists
    existing = (
        db_session.query(NewsletterSummary)
        .filter(NewsletterSummary.newsletter_id == newsletter.id)
        .first()
    )
    assert existing is None

    # Run summarization with mocked LLM and database
    with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_anthropic_client

        with patch("src.processors.summarizer.get_db", mock_get_db):
            summarizer = NewsletterSummarizer()
            result = summarizer.summarize_newsletter(newsletter.id)

    # Verify success
    assert result is True

    # Verify newsletter status updated
    db_session.refresh(newsletter)
    assert newsletter.status == ProcessingStatus.COMPLETED

    # Verify summary was created
    summary = (
        db_session.query(NewsletterSummary)
        .filter(NewsletterSummary.newsletter_id == newsletter.id)
        .first()
    )

    assert summary is not None
    assert summary.executive_summary == "Test summary of newsletter content."
    assert len(summary.key_themes) == 3
    assert "Theme 1" in summary.key_themes
    assert len(summary.strategic_insights) == 2
    assert len(summary.technical_details) == 2
    assert summary.relevance_scores["cto_leadership"] == 0.8
    assert summary.agent_framework == "claude"
    assert summary.model_used == "claude-haiku-4-5-20251001"
    assert summary.token_usage == 1500  # 1000 input + 500 output


@pytest.mark.integration
def test_summarize_newsletter_not_found(db_session, mock_get_db):
    """Test handling of non-existent newsletter."""
    with patch("src.agents.claude.summarizer.Anthropic"):
        with patch("src.processors.summarizer.get_db", mock_get_db):
            summarizer = NewsletterSummarizer()
            result = summarizer.summarize_newsletter(99999)  # Non-existent ID

    assert result is False


@pytest.mark.integration
def test_summarize_newsletter_already_summarized(
    db_session, sample_newsletters, sample_summaries, mock_get_db
):
    """Test that already-summarized newsletters are skipped."""
    newsletter = sample_newsletters[0]

    # Verify summary already exists
    existing = (
        db_session.query(NewsletterSummary)
        .filter(NewsletterSummary.newsletter_id == newsletter.id)
        .first()
    )
    assert existing is not None

    # Run summarization
    with patch("src.agents.claude.summarizer.Anthropic"):
        with patch("src.processors.summarizer.get_db", mock_get_db):
            summarizer = NewsletterSummarizer()
            result = summarizer.summarize_newsletter(newsletter.id)

    # Should return success (already summarized)
    assert result is True

    # Verify only one summary exists (no duplicate created)
    summaries = (
        db_session.query(NewsletterSummary)
        .filter(NewsletterSummary.newsletter_id == newsletter.id)
        .all()
    )
    assert len(summaries) == 1


@pytest.mark.integration
def test_summarize_newsletter_llm_error(db_session, sample_newsletters, mock_get_db):
    """Test handling of LLM API errors."""
    newsletter = sample_newsletters[0]

    # Mock LLM to raise exception
    mock_client = type('MockClient', (), {})()
    mock_client.messages = type('Messages', (), {})()
    mock_client.messages.create = lambda **kwargs: (_ for _ in ()).throw(
        Exception("API Error")
    )

    with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_client

        with patch("src.processors.summarizer.get_db", mock_get_db):
            summarizer = NewsletterSummarizer()
            result = summarizer.summarize_newsletter(newsletter.id)

    # Should handle error gracefully
    assert result is False

    # Verify newsletter status is FAILED
    db_session.refresh(newsletter)
    assert newsletter.status == ProcessingStatus.FAILED
    assert newsletter.error_message is not None
    assert "API Error" in newsletter.error_message


@pytest.mark.integration
def test_summarize_pending_newsletters(
    db_session, sample_newsletters, mock_anthropic_client, mock_get_db
):
    """Test batch summarization of pending newsletters."""
    # All newsletters should be PENDING
    for newsletter in sample_newsletters:
        assert newsletter.status == ProcessingStatus.PENDING

    # Run batch summarization
    with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_anthropic_client

        with patch("src.processors.summarizer.get_db", mock_get_db):
            summarizer = NewsletterSummarizer()
            count = summarizer.summarize_pending_newsletters()

    # Should have summarized all 3 newsletters
    assert count == 3

    # Verify all newsletters are now COMPLETED
    for newsletter in sample_newsletters:
        db_session.refresh(newsletter)
        assert newsletter.status == ProcessingStatus.COMPLETED

    # Verify summaries were created
    summaries = db_session.query(NewsletterSummary).all()
    assert len(summaries) == 3


@pytest.mark.integration
def test_summarize_pending_newsletters_with_limit(
    db_session, sample_newsletters, mock_anthropic_client, mock_get_db
):
    """Test batch summarization with limit."""
    # Run batch summarization with limit of 2
    with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_anthropic_client

        with patch("src.processors.summarizer.get_db", mock_get_db):
            summarizer = NewsletterSummarizer()
            count = summarizer.summarize_pending_newsletters(limit=2)

    # Should have summarized only 2 newsletters
    assert count == 2

    # Verify summaries created
    summaries = db_session.query(NewsletterSummary).all()
    assert len(summaries) == 2

    # Verify one newsletter still pending
    pending = (
        db_session.query(Newsletter)
        .filter(Newsletter.status == ProcessingStatus.PENDING)
        .count()
    )
    assert pending == 1


@pytest.mark.integration
def test_summarize_newsletter_status_transitions(
    db_session, sample_newsletters, mock_anthropic_client, mock_get_db
):
    """Test newsletter status transitions during summarization."""
    newsletter = sample_newsletters[0]

    # Start: PENDING
    assert newsletter.status == ProcessingStatus.PENDING

    # During processing, status should be PROCESSING
    # (we can't easily test this without threading, but it's set in the code)

    # Run summarization
    with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_anthropic_client

        with patch("src.processors.summarizer.get_db", mock_get_db):
            summarizer = NewsletterSummarizer()
            result = summarizer.summarize_newsletter(newsletter.id)

    assert result is True

    # End: COMPLETED
    db_session.refresh(newsletter)
    assert newsletter.status == ProcessingStatus.COMPLETED
    assert newsletter.error_message is None
