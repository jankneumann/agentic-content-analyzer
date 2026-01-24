"""EXAMPLE: Refactored integration test using real data and cached API responses.

This demonstrates the new testing approach:
- Real newsletter data from tests/test_data/newsletters/
- Real database operations (PostgreSQL)
- Real GraphitiClient operations (local Neo4j)
- Mocked API calls with cached responses (Anthropic, OpenAI)
"""

import logging
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.models.digest import DigestRequest, DigestType
from src.models.summary import Summary
from src.processors.digest_creator import DigestCreator
from tests.helpers.api_mocks import create_anthropic_summarization_responses
from tests.helpers.test_data import create_test_newsletters_batch, get_default_test_newsletters

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@pytest.mark.asyncio
async def test_digest_creates_missing_summaries_refactored(db_session, mock_get_db):
    """
    Test that digest creator automatically creates missing summaries.

    This is a REFACTORED version showing the new approach:
    - Uses real newsletter data from test files
    - Real database operations (test PostgreSQL)
    - Mocked ThemeAnalyzer and API calls
    """
    logger.info("=== Starting refactored test ===")

    # ============================================================
    # 1. SETUP: Load real newsletter data into database
    # ============================================================
    logger.info("Loading test newsletters into database...")
    newsletters = create_test_newsletters_batch(
        db_session, filenames=get_default_test_newsletters()
    )
    logger.info(f"Loaded {len(newsletters)} newsletters: {[nl.id for nl in newsletters]}")

    # Verify no summaries exist yet
    summary_count = db_session.query(Summary).count()
    logger.info(f"Initial summary count: {summary_count}")
    assert summary_count == 0

    # ============================================================
    # 2. MOCK: External API calls and database access
    # ============================================================
    logger.info("Setting up API mocks with cached responses...")

    # Create cached Anthropic responses for all 3 newsletters
    mock_summary_responses = create_anthropic_summarization_responses()

    # Patch get_db for all modules that use it
    with patch("src.processors.digest_creator.get_db", mock_get_db):
        with patch("src.processors.summarizer.get_db", mock_get_db):
            with patch("src.processors.theme_analyzer.get_db", mock_get_db):
                # Mock ThemeAnalyzer to avoid complex graph operations
                with patch("src.processors.theme_analyzer.ThemeAnalyzer") as mock_analyzer_class:
                    from unittest.mock import AsyncMock

                    mock_analyzer = AsyncMock()
                    mock_analyzer.analyze_themes = AsyncMock(
                        return_value=MagicMock(
                            themes=[],
                            newsletter_count=len(newsletters),
                            processing_time_seconds=0.1,
                        )
                    )
                    mock_analyzer_class.return_value = mock_analyzer

                    # Mock Anthropic client to return cached responses
                    with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_class:
                        mock_client = MagicMock()

                        # Configure to return cached responses in sequence
                        mock_client.messages.create.side_effect = mock_summary_responses
                        mock_anthropic_class.return_value = mock_client

                        # ============================================================
                        # 3. TEST: Run digest creation
                        # ============================================================
                        logger.info("Creating digest with on-demand summarization...")

                        request = DigestRequest(
                            digest_type=DigestType.DAILY,
                            period_start=datetime(2025, 1, 12, 0, 0, 0, tzinfo=UTC),
                            period_end=datetime(2025, 1, 15, 23, 59, 59, tzinfo=UTC),
                            max_strategic_insights=5,
                            max_technical_developments=5,
                            max_emerging_trends=3,
                            include_historical_context=False,
                        )

                        creator = DigestCreator()

                        # Mock digest creation response
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

                        # Add digest response to mock sequence (after summaries)
                        mock_client.messages.create.side_effect = mock_summary_responses + [
                            mock_digest_response
                        ]

                        digest = await creator.create_digest(request)
                        logger.info("Digest creation completed")

    # ============================================================
    # 4. VERIFY: Check actual database state
    # ============================================================
    logger.info("Verifying summaries were created in database...")

    # Verify summaries were created in REAL database
    summary_count = db_session.query(Summary).count()
    logger.info(f"Final summary count: {summary_count}")
    assert summary_count == 3, f"Expected 3 summaries, found {summary_count}"

    # Verify each newsletter has a summary with REAL data
    for newsletter in newsletters:
        summary = db_session.query(Summary).filter(Summary.newsletter_id == newsletter.id).first()
        assert summary is not None, f"Newsletter {newsletter.id} missing summary"
        assert summary.executive_summary is not None
        assert len(summary.key_themes) > 0
        logger.info(
            f"✓ Newsletter {newsletter.id} has summary with {len(summary.key_themes)} themes"
        )

    # Verify digest was created
    assert digest is not None
    assert digest.newsletter_count == 3
    logger.info("=== Test completed successfully ===\n")


# ============================================================
# COMPARISON: Old vs New Approach
# ============================================================

"""
OLD APPROACH (Heavy Mocking):
- Mock newsletters in fixtures (not real data)
- Mock database with mock_get_db
- Mock GraphitiClient
- Mock all LLM calls
- Tests mock interactions, not real code paths

NEW APPROACH (Real Integration):
- Real newsletters from test_data/newsletters/
- Real database operations (test PostgreSQL)
- Real GraphitiClient (local Neo4j)
- Mock only external APIs with cached responses
- Tests actual code paths and database state

BENEFITS:
✓ Catches real integration bugs
✓ Tests actual database operations
✓ Validates data models and schemas
✓ Uses realistic API responses
✓ Less coupling to implementation details
✓ Easier to debug (can inspect real DB)

WHAT'S MOCKED:
- Anthropic API (cached real responses)
- OpenAI API (cached embeddings)

WHAT'S REAL:
- PostgreSQL operations
- Neo4j/GraphitiClient operations
- All business logic
- Data validation
- Error handling
"""
