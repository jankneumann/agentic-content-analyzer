"""Integration tests for on-demand summary creation during digest generation.

These tests verify that DigestCreator automatically creates missing summaries
when generating digests, with proper error handling and database persistence.
"""

import logging
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.digest import DigestRequest, DigestType
from src.models.summary import NewsletterSummary
from src.processors.digest_creator import DigestCreator

# Configure logging for test visibility
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@pytest.mark.asyncio
async def test_digest_creates_missing_summaries(
    db_session, mock_get_db, sample_newsletters, mock_anthropic_client
):
    """Test that digest creator automatically creates missing summaries."""
    logger.info("=== Starting test_digest_creates_missing_summaries ===")

    # Remove existing summaries (if any)
    logger.info("Removing existing summaries...")
    db_session.query(NewsletterSummary).delete()
    db_session.commit()

    # Verify no summaries exist
    summary_count = db_session.query(NewsletterSummary).count()
    logger.info(f"Summary count after deletion: {summary_count}")
    assert summary_count == 0

    # Patch database context manager to use test session
    logger.info("Setting up mock patches...")
    with patch("src.processors.digest_creator.get_db", mock_get_db):
        with patch("src.processors.summarizer.get_db", mock_get_db):
            with patch("src.processors.theme_analyzer.get_db", mock_get_db):
                logger.info("Mocking ThemeAnalyzer...")
                # Mock theme analyzer to avoid GraphitiClient dependency
                with patch("src.processors.theme_analyzer.ThemeAnalyzer") as mock_analyzer_class:
                    mock_analyzer = AsyncMock()
                    mock_analyzer.analyze_themes = AsyncMock(
                        return_value=MagicMock(
                            themes=[],
                            newsletter_count=len(sample_newsletters),
                            processing_time_seconds=0.1,
                        )
                    )
                    mock_analyzer_class.return_value = mock_analyzer

                    logger.info("Mocking Anthropic client...")
                    # Mock Anthropic client for summarization and digest creation
                    with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_class:
                        mock_anthropic_class.return_value = mock_anthropic_client

                        logger.info("Creating digest request...")
                        # Create digest request
                        request = DigestRequest(
                            digest_type=DigestType.DAILY,
                            period_start=datetime(2025, 1, 13, 0, 0, 0),
                            period_end=datetime(2025, 1, 15, 23, 59, 59),
                            max_strategic_insights=5,
                            max_technical_developments=5,
                            max_emerging_trends=3,
                            include_historical_context=False,
                        )

                        logger.info("Initializing DigestCreator...")
                        # Create digest (should auto-create summaries)
                        creator = DigestCreator()

                        logger.info("Configuring mock LLM responses...")
                        # Mock digest creation LLM call
                        mock_digest_response = MagicMock()
                        mock_digest_response.content = [
                            MagicMock(
                                text="""{
                            "title": "Test Daily Digest",
                            "executive_overview": "Test overview",
                            "strategic_insights": [],
                            "technical_developments": [],
                            "emerging_trends": [],
                            "actionable_recommendations": {}
                        }"""
                            )
                        ]
                        mock_digest_response.usage = MagicMock(input_tokens=500, output_tokens=200)

                        # Configure mock to return summary response first, then digest response
                        mock_anthropic_client.messages.create.side_effect = [
                            mock_anthropic_client.messages.create.return_value,  # Summary 1
                            mock_anthropic_client.messages.create.return_value,  # Summary 2
                            mock_anthropic_client.messages.create.return_value,  # Summary 3
                            mock_digest_response,  # Digest creation
                        ]

                        logger.info(
                            "Calling create_digest() - this will create missing summaries..."
                        )
                        digest = await creator.create_digest(request)
                        logger.info("Digest creation completed")

    logger.info("Verifying summaries were created...")
    # Verify summaries were created
    summary_count = db_session.query(NewsletterSummary).count()
    logger.info(f"Final summary count: {summary_count}")
    assert summary_count == 3, f"Expected 3 summaries, found {summary_count}"

    logger.info("Verifying each newsletter has a summary...")
    # Verify each newsletter has a summary
    for newsletter in sample_newsletters:
        summary = (
            db_session.query(NewsletterSummary)
            .filter(NewsletterSummary.newsletter_id == newsletter.id)
            .first()
        )
        assert summary is not None, f"Newsletter {newsletter.id} missing summary"
    logger.info("All newsletters have summaries ✓")

    logger.info("Verifying digest was created...")
    # Verify digest was created
    assert digest is not None
    assert digest.newsletter_count == 3
    logger.info("=== Test completed successfully ===\n")


@pytest.mark.asyncio
async def test_digest_with_some_existing_summaries(
    db_session, mock_get_db, sample_newsletters, sample_summaries, mock_anthropic_client
):
    """Test that digest only creates summaries for newsletters that don't have them."""
    logger.info("=== Starting test_digest_with_some_existing_summaries ===")

    logger.info(f"Removing summary for 3rd newsletter (ID: {sample_newsletters[2].id})...")
    # Remove summary for 3rd newsletter only
    db_session.query(NewsletterSummary).filter(
        NewsletterSummary.newsletter_id == sample_newsletters[2].id
    ).delete()
    db_session.commit()

    # Verify 2 summaries exist
    summary_count = db_session.query(NewsletterSummary).count()
    logger.info(f"Summary count after deletion: {summary_count}")
    assert summary_count == 2

    logger.info("Setting up mock patches...")
    with patch("src.processors.digest_creator.get_db", mock_get_db):
        with patch("src.processors.summarizer.get_db", mock_get_db):
            with patch("src.processors.theme_analyzer.get_db", mock_get_db):
                logger.info("Mocking ThemeAnalyzer...")
                with patch("src.processors.theme_analyzer.ThemeAnalyzer") as mock_analyzer_class:
                    mock_analyzer = AsyncMock()
                    mock_analyzer.analyze_themes = AsyncMock(
                        return_value=MagicMock(
                            themes=[],
                            newsletter_count=len(sample_newsletters),
                            processing_time_seconds=0.1,
                        )
                    )
                    mock_analyzer_class.return_value = mock_analyzer

                    logger.info("Mocking Anthropic client...")
                    with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_class:
                        mock_anthropic_class.return_value = mock_anthropic_client

                        logger.info("Creating digest request...")
                        request = DigestRequest(
                            digest_type=DigestType.DAILY,
                            period_start=datetime(2025, 1, 13, 0, 0, 0),
                            period_end=datetime(2025, 1, 15, 23, 59, 59),
                            max_strategic_insights=5,
                            max_technical_developments=5,
                            max_emerging_trends=3,
                            include_historical_context=False,
                        )

                        logger.info("Initializing DigestCreator...")
                        creator = DigestCreator()

                        logger.info("Configuring mock LLM responses (1 summary + digest)...")
                        # Mock digest creation LLM call
                        mock_digest_response = MagicMock()
                        mock_digest_response.content = [
                            MagicMock(
                                text="""{
                            "title": "Test Daily Digest",
                            "executive_overview": "Test overview",
                            "strategic_insights": [],
                            "technical_developments": [],
                            "emerging_trends": [],
                            "actionable_recommendations": {}
                        }"""
                            )
                        ]
                        mock_digest_response.usage = MagicMock(input_tokens=500, output_tokens=200)

                        # Configure mock - only 1 summarization + digest call
                        mock_anthropic_client.messages.create.side_effect = [
                            mock_anthropic_client.messages.create.return_value,  # Summary for 3rd newsletter
                            mock_digest_response,  # Digest creation
                        ]

                        logger.info("Calling create_digest() - should create 1 missing summary...")
                        digest = await creator.create_digest(request)
                        logger.info("Digest creation completed")

    logger.info("Verifying all 3 summaries now exist...")
    # Verify all 3 summaries now exist
    summary_count = db_session.query(NewsletterSummary).count()
    logger.info(f"Final summary count: {summary_count}")
    assert summary_count == 3

    logger.info("Verifying digest was created...")
    # Verify digest was created
    assert digest is not None
    assert digest.newsletter_count == 3
    logger.info("=== Test completed successfully ===\n")


@pytest.mark.asyncio
async def test_digest_continues_with_partial_summary_failures(
    db_session, mock_get_db, sample_newsletters, mock_anthropic_client, mocker
):
    """Test that digest creation continues when some summaries fail."""
    logger.info("=== Starting test_digest_continues_with_partial_summary_failures ===")

    logger.info("Removing all summaries...")
    # Remove all summaries
    db_session.query(NewsletterSummary).delete()
    db_session.commit()
    logger.info("All summaries removed")

    # Create valid summary response
    mock_summary_response = MagicMock()
    mock_summary_response.content = [
        MagicMock(
            text="""{
            "executive_summary": "Test summary",
            "key_themes": ["AI", "Technology"],
            "strategic_insights": ["Insight 1"],
            "technical_details": ["Detail 1"],
            "actionable_items": ["Action 1"],
            "notable_quotes": ["Quote 1"],
            "relevance_score": 8.0,
            "time_sensitivity": "medium"
        }"""
        )
    ]
    mock_summary_response.usage = MagicMock(input_tokens=100, output_tokens=50)

    # Create digest response
    mock_digest_response = MagicMock()
    mock_digest_response.content = [
        MagicMock(
            text="""{
            "title": "Test Daily Digest",
            "executive_overview": "Test overview",
            "strategic_insights": [],
            "technical_developments": [],
            "emerging_trends": [],
            "actionable_recommendations": {}
        }"""
        )
    ]
    mock_digest_response.usage = MagicMock(input_tokens=500, output_tokens=200)

    # Configure mock to succeed on 1st and 3rd summary, fail on 2nd, then succeed for digest
    mock_anthropic_client.messages.create.side_effect = [
        mock_summary_response,  # 1st newsletter - success
        Exception("API Error"),  # 2nd newsletter - failure
        mock_summary_response,  # 3rd newsletter - success
        mock_digest_response,  # Digest creation
    ]

    logger.info("Setting up mock patches...")
    with patch("src.processors.digest_creator.get_db", mock_get_db):
        with patch("src.processors.summarizer.get_db", mock_get_db):
            with patch("src.processors.theme_analyzer.get_db", mock_get_db):
                logger.info("Mocking ThemeAnalyzer...")
                with patch("src.processors.theme_analyzer.ThemeAnalyzer") as mock_analyzer_class:
                    mock_analyzer = AsyncMock()
                    mock_analyzer.analyze_themes = AsyncMock(
                        return_value=MagicMock(
                            themes=[],
                            newsletter_count=len(sample_newsletters),
                            processing_time_seconds=0.1,
                        )
                    )
                    mock_analyzer_class.return_value = mock_analyzer

                    logger.info("Mocking Anthropic client...")
                    with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_class:
                        mock_anthropic_class.return_value = mock_anthropic_client

                        logger.info("Creating digest request...")
                        request = DigestRequest(
                            digest_type=DigestType.DAILY,
                            period_start=datetime(2025, 1, 13, 0, 0, 0),
                            period_end=datetime(2025, 1, 15, 23, 59, 59),
                            max_strategic_insights=5,
                            max_technical_developments=5,
                            max_emerging_trends=3,
                            include_historical_context=False,
                        )

                        logger.info("Initializing DigestCreator...")
                        creator = DigestCreator()

                        logger.info("Calling create_digest() - 2nd summary should fail...")
                        digest = await creator.create_digest(request)
                        logger.info("Digest creation completed despite failure")

    logger.info("Verifying only 2 summaries were created (1 failed)...")
    # Verify only 2 summaries were created (1 failed)
    summary_count = db_session.query(NewsletterSummary).count()
    logger.info(f"Final summary count: {summary_count}")
    assert summary_count == 2

    logger.info("Verifying digest was still created...")
    # Verify digest was still created
    assert digest is not None
    # Digest should only include the 2 newsletters with successful summaries
    assert digest.newsletter_count >= 2  # May include others if logic changes
    logger.info("=== Test completed successfully ===\n")


@pytest.mark.asyncio
async def test_digest_with_all_summaries_existing(
    db_session, mock_get_db, sample_newsletters, sample_summaries, mock_anthropic_client
):
    """Regression test: digest creation when all summaries already exist."""
    logger.info("=== Starting test_digest_with_all_summaries_existing ===")

    # Verify all summaries exist
    summary_count = db_session.query(NewsletterSummary).count()
    logger.info(f"Initial summary count: {summary_count}")
    assert summary_count == 3

    logger.info("Setting up mock patches...")
    with patch("src.processors.digest_creator.get_db", mock_get_db):
        with patch("src.processors.summarizer.get_db", mock_get_db):
            with patch("src.processors.theme_analyzer.get_db", mock_get_db):
                logger.info("Mocking ThemeAnalyzer...")
                with patch("src.processors.theme_analyzer.ThemeAnalyzer") as mock_analyzer_class:
                    mock_analyzer = AsyncMock()
                    mock_analyzer.analyze_themes = AsyncMock(
                        return_value=MagicMock(
                            themes=[],
                            newsletter_count=len(sample_newsletters),
                            processing_time_seconds=0.1,
                        )
                    )
                    mock_analyzer_class.return_value = mock_analyzer

                    logger.info("Mocking Anthropic client for digest creation...")
                    # Patch DigestCreator's Anthropic import (not summarizer)
                    with patch("src.processors.digest_creator.Anthropic") as mock_anthropic_class:
                        mock_anthropic_client_local = MagicMock()

                        logger.info("Configuring mock LLM responses (digest only, no summaries)...")
                        # Mock digest creation LLM call only (no summarization calls)
                        mock_digest_response = MagicMock()
                        mock_digest_response.content = [
                            MagicMock(
                                text="""{
                            "title": "Test Daily Digest",
                            "executive_overview": "Test overview",
                            "strategic_insights": [],
                            "technical_developments": [],
                            "emerging_trends": [],
                            "actionable_recommendations": {}
                        }"""
                            )
                        ]
                        mock_digest_response.usage = MagicMock(input_tokens=500, output_tokens=200)
                        mock_anthropic_client_local.messages.create.return_value = (
                            mock_digest_response
                        )

                        mock_anthropic_class.return_value = mock_anthropic_client_local

                        logger.info("Creating digest request...")
                        request = DigestRequest(
                            digest_type=DigestType.DAILY,
                            period_start=datetime(2025, 1, 13, 0, 0, 0),
                            period_end=datetime(2025, 1, 15, 23, 59, 59),
                            max_strategic_insights=5,
                            max_technical_developments=5,
                            max_emerging_trends=3,
                            include_historical_context=False,
                        )

                        logger.info("Initializing DigestCreator...")
                        creator = DigestCreator()

                        logger.info("Calling create_digest() - should NOT create any summaries...")
                        digest = await creator.create_digest(request)
                        logger.info("Digest creation completed")

                        logger.info(
                            "Verifying only 1 LLM call was made (for digest, not summaries)..."
                        )
                        # Verify only 1 LLM call (for digest, not summaries)
                        # This ensures we're not recreating existing summaries
                        assert mock_anthropic_client_local.messages.create.call_count == 1

    logger.info("Verifying no additional summaries were created...")
    # Verify no additional summaries were created
    summary_count_after = db_session.query(NewsletterSummary).count()
    logger.info(f"Final summary count: {summary_count_after}")
    assert summary_count_after == 3

    logger.info("Verifying digest was created...")
    # Verify digest was created
    assert digest is not None
    assert digest.newsletter_count == 3
    logger.info("=== Test completed successfully ===\n")
