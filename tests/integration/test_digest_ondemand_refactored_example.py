"""EXAMPLE: Refactored integration test using real data and cached API responses.

This demonstrates the new testing approach:
- Real newsletter data from tests/test_data/newsletters/
- Real database operations (PostgreSQL)
- Real GraphitiClient operations (local Neo4j)
- Mocked API calls with cached responses (Anthropic, OpenAI)
"""

import pytest
import logging
from datetime import datetime
from unittest.mock import patch, MagicMock

from src.models.digest import DigestRequest, DigestType
from src.models.summary import NewsletterSummary
from src.processors.digest_creator import DigestCreator

from tests.helpers.test_data import create_test_newsletters_batch, get_default_test_newsletters
from tests.helpers.api_mocks import create_anthropic_summarization_responses

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@pytest.mark.asyncio
async def test_digest_creates_missing_summaries_refactored(db_session):
    """
    Test that digest creator automatically creates missing summaries.

    This is a REFACTORED version showing the new approach:
    - Uses real newsletter data from test files
    - Real database operations
    - Real GraphitiClient (local Neo4j)
    - Only mocks Anthropic/OpenAI API calls
    """
    logger.info("=== Starting refactored test ===")

    # ============================================================
    # 1. SETUP: Load real newsletter data into database
    # ============================================================
    logger.info("Loading test newsletters into database...")
    newsletters = create_test_newsletters_batch(
        db_session,
        filenames=get_default_test_newsletters()
    )
    logger.info(f"Loaded {len(newsletters)} newsletters: {[nl.id for nl in newsletters]}")

    # Verify no summaries exist yet
    summary_count = db_session.query(NewsletterSummary).count()
    logger.info(f"Initial summary count: {summary_count}")
    assert summary_count == 0

    # ============================================================
    # 2. MOCK: Only external API calls (Anthropic, OpenAI)
    # ============================================================
    logger.info("Setting up API mocks with cached responses...")

    # Create cached Anthropic responses for all 3 newsletters
    mock_summary_responses = create_anthropic_summarization_responses()

    # Mock Anthropic client to return cached responses
    with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_class:
        mock_client = MagicMock()

        # Configure to return cached responses in sequence
        mock_client.messages.create.side_effect = mock_summary_responses
        mock_anthropic_class.return_value = mock_client

        # Mock OpenAI embeddings (used by GraphitiClient)
        with patch("httpx.Client.post") as mock_httpx:
            # Mock OpenAI embeddings response
            mock_openai_response = MagicMock()
            mock_openai_response.status_code = 200
            mock_openai_response.json.return_value = {
                "object": "list",
                "data": [
                    {
                        "object": "embedding",
                        "embedding": [0.002] * 1536,  # Mock embedding vector
                        "index": 0
                    }
                ],
                "model": "text-embedding-3-small",
                "usage": {"prompt_tokens": 8, "total_tokens": 8}
            }
            mock_httpx.return_value = mock_openai_response

            # ============================================================
            # 3. TEST: Run digest creation (uses REAL database + GraphitiClient)
            # ============================================================
            logger.info("Creating digest with on-demand summarization...")

            request = DigestRequest(
                digest_type=DigestType.DAILY,
                period_start=datetime(2025, 1, 13, 0, 0, 0),
                period_end=datetime(2025, 1, 15, 23, 59, 59),
                max_strategic_insights=5,
                max_technical_developments=5,
                max_emerging_trends=3,
                include_historical_context=False,
            )

            creator = DigestCreator()

            # Mock digest creation response
            mock_digest_response = MagicMock()
            mock_digest_response.content = [MagicMock(text='''{
                "title": "Test Daily Digest",
                "executive_overview": "Test overview",
                "strategic_insights": [],
                "technical_developments": [],
                "emerging_trends": [],
                "actionable_recommendations": []
            }''')]
            mock_digest_response.usage = MagicMock(input_tokens=500, output_tokens=200)

            # Add digest response to mock sequence (after summaries)
            mock_client.messages.create.side_effect = mock_summary_responses + [mock_digest_response]

            digest = await creator.create_digest(request)
            logger.info("Digest creation completed")

    # ============================================================
    # 4. VERIFY: Check actual database state
    # ============================================================
    logger.info("Verifying summaries were created in database...")

    # Verify summaries were created in REAL database
    summary_count = db_session.query(NewsletterSummary).count()
    logger.info(f"Final summary count: {summary_count}")
    assert summary_count == 3, f"Expected 3 summaries, found {summary_count}"

    # Verify each newsletter has a summary with REAL data
    for newsletter in newsletters:
        summary = db_session.query(NewsletterSummary).filter(
            NewsletterSummary.newsletter_id == newsletter.id
        ).first()
        assert summary is not None, f"Newsletter {newsletter.id} missing summary"
        assert summary.executive_summary is not None
        assert len(summary.key_themes) > 0
        logger.info(f"✓ Newsletter {newsletter.id} has summary with {len(summary.key_themes)} themes")

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
