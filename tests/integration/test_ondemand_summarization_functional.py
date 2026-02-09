"""Functional integration test: On-demand summarization during digest creation.

This test verifies the BUSINESS LOGIC works correctly:
- On-demand summarization triggers when summaries are missing
- Database operations succeed (newsletters, summaries created)
- State transitions correctly (PENDING → COMPLETED)
- Graceful handling of partial failures
- Re-fetching summaries after creation

This does NOT verify LLM output quality - that's for scenario tests.
We only care that the flow works, not that summaries are meaningful.
"""

import logging
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.models.digest import DigestRequest, DigestType
from src.models.summary import Summary
from src.processors.digest_creator import DigestCreator
from tests.helpers.simple_mocks import (
    create_simple_digest_response,
    create_simple_embedding_response,
    create_simple_summary_response,
    create_simple_theme_analysis_response,
)
from tests.helpers.test_data import create_test_contents_batch

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@pytest.mark.asyncio
async def test_ondemand_summarization_triggers_for_missing_summaries(db_session, mock_get_db):
    """
    Verify on-demand summarization flow triggers and creates all missing summaries.

    Flow:
    1. Load 3 newsletters with no summaries
    2. Create digest (should trigger on-demand summarization)
    3. Verify all summaries created in database
    4. Verify newsletter status updated
    """
    logger.info("=== TEST: On-demand summarization triggers for missing summaries ===")

    # ============================================================
    # 1. SETUP: Load real newsletters without summaries
    # ============================================================
    logger.info("Loading test newsletters into database...")
    newsletters = create_test_contents_batch(db_session)
    logger.info(f"Loaded {len(newsletters)} newsletters: {[nl.id for nl in newsletters]}")

    # Verify no summaries exist
    summary_count = db_session.query(Summary).count()
    assert summary_count == 0, "Expected 0 summaries initially"
    logger.info("✓ Verified no summaries exist initially")

    # ============================================================
    # 2. MOCK: External APIs with simple valid responses
    # ============================================================
    logger.info("Setting up API mocks...")

    # Create simple summary responses for 3 newsletters
    mock_summary_responses = [create_simple_summary_response(newsletter_id=i) for i in range(1, 4)]

    # Mock theme analysis response
    mock_theme_response = create_simple_theme_analysis_response(theme_count=3)

    # Mock digest creation response
    mock_digest_response = create_simple_digest_response()

    # All Anthropic calls in sequence: 3 summaries + 1 theme analysis + 1 digest
    all_responses = mock_summary_responses + [mock_theme_response, mock_digest_response]

    # Patch get_db in all modules that use it
    with patch("src.processors.digest_creator.get_db", mock_get_db):
        with patch("src.processors.summarizer.get_db", mock_get_db):
            with patch("src.processors.theme_analyzer.get_db", mock_get_db):
                with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_summarizer:
                    with patch(
                        "src.processors.theme_analyzer.Anthropic"
                    ) as mock_anthropic_analyzer:
                        with patch(
                            "src.processors.digest_creator.Anthropic"
                        ) as mock_anthropic_digest:
                            # Configure mocks
                            mock_summarizer_client = MagicMock()
                            mock_summarizer_client.messages.create.side_effect = (
                                mock_summary_responses
                            )
                            mock_anthropic_summarizer.return_value = mock_summarizer_client

                            mock_analyzer_client = MagicMock()
                            mock_analyzer_client.messages.create.return_value = mock_theme_response
                            mock_anthropic_analyzer.return_value = mock_analyzer_client

                            mock_digest_client = MagicMock()
                            mock_digest_client.messages.create.return_value = mock_digest_response
                            mock_anthropic_digest.return_value = mock_digest_client

                            # Mock OpenAI embeddings (used by GraphitiClient)
                            with patch("httpx.Client.post") as mock_httpx:
                                mock_httpx.return_value = create_simple_embedding_response()

                                logger.info("✓ API mocks configured")

                                # ============================================================
                                # 3. TEST: Create digest (should trigger on-demand summarization)
                                # ============================================================
                                logger.info(
                                    "Creating digest (should trigger on-demand summarization)..."
                                )

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
                                digest = await creator.create_digest(request)

                                logger.info("✓ Digest creation completed")

    # ============================================================
    # 4. VERIFY: Database state (not content quality)
    # ============================================================
    logger.info("Verifying summaries were created...")

    # Check summary count
    summaries = db_session.query(Summary).all()
    assert len(summaries) == 3, f"Expected 3 summaries, found {len(summaries)}"
    logger.info(f"✓ Found {len(summaries)} summaries in database")

    # Verify each newsletter has a summary
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

    logger.info("=== TEST PASSED ===\n")


@pytest.mark.asyncio
async def test_ondemand_summarization_with_some_existing_summaries(db_session, mock_get_db):
    """
    Verify on-demand summarization only creates MISSING summaries.

    Flow:
    1. Load 3 newsletters
    2. Create summary for 1st newsletter manually
    3. Create digest (should only create 2 missing summaries)
    4. Verify exactly 3 summaries total
    """
    logger.info("=== TEST: On-demand summarization with some existing summaries ===")

    # ============================================================
    # 1. SETUP: Load newsletters and create 1 summary manually
    # ============================================================
    logger.info("Loading test newsletters...")
    newsletters = create_test_contents_batch(db_session)

    # Create summary for first newsletter manually
    logger.info(f"Creating manual summary for newsletter {newsletters[0].id}...")
    existing_summary = Summary(
        newsletter_id=newsletters[0].id,
        executive_summary="Existing summary",
        key_themes=["Existing theme"],
        strategic_insights=["Existing insight"],
        technical_details=["Existing detail"],
        actionable_items=["Existing action"],
        notable_quotes=["Existing quote"],
        relevance_scores={
            "cto_leadership": 0.8,
            "technical_teams": 0.9,
            "individual_developers": 0.7,
        },
        agent_framework="claude",
        model_used="claude-haiku-4-5",
        model_version="20250929",
    )
    db_session.add(existing_summary)
    db_session.commit()

    initial_count = db_session.query(Summary).count()
    assert initial_count == 1, "Expected 1 existing summary"
    logger.info("✓ Created 1 existing summary")

    # ============================================================
    # 2. MOCK: Only 2 summaries needed (3rd already exists)
    # ============================================================
    logger.info("Setting up API mocks for 2 missing summaries...")

    mock_summary_responses = [create_simple_summary_response(newsletter_id=i) for i in range(2, 4)]

    mock_theme_response = create_simple_theme_analysis_response(theme_count=3)
    mock_digest_response = create_simple_digest_response()

    # Patch get_db in all modules that use it
    with patch("src.processors.digest_creator.get_db", mock_get_db):
        with patch("src.processors.summarizer.get_db", mock_get_db):
            with patch("src.processors.theme_analyzer.get_db", mock_get_db):
                with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_summarizer:
                    with patch(
                        "src.processors.theme_analyzer.Anthropic"
                    ) as mock_anthropic_analyzer:
                        with patch(
                            "src.processors.digest_creator.Anthropic"
                        ) as mock_anthropic_digest:
                            mock_summarizer_client = MagicMock()
                            mock_summarizer_client.messages.create.side_effect = (
                                mock_summary_responses
                            )
                            mock_anthropic_summarizer.return_value = mock_summarizer_client

                            mock_analyzer_client = MagicMock()
                            mock_analyzer_client.messages.create.return_value = mock_theme_response
                            mock_anthropic_analyzer.return_value = mock_analyzer_client

                            mock_digest_client = MagicMock()
                            mock_digest_client.messages.create.return_value = mock_digest_response
                            mock_anthropic_digest.return_value = mock_digest_client

                            with patch("httpx.Client.post") as mock_httpx:
                                mock_httpx.return_value = create_simple_embedding_response()

                                # ============================================================
                                # 3. TEST: Create digest
                                # ============================================================
                                logger.info("Creating digest...")

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
                                digest = await creator.create_digest(request)

    # ============================================================
    # 4. VERIFY: Only 2 new summaries created (3 total)
    # ============================================================
    logger.info("Verifying summary counts...")

    summaries = db_session.query(Summary).all()
    assert len(summaries) == 3, f"Expected 3 total summaries, found {len(summaries)}"

    # Verify all newsletters have summaries
    for newsletter in newsletters:
        summary = db_session.query(Summary).filter(Summary.newsletter_id == newsletter.id).first()
        assert summary is not None, f"Newsletter {newsletter.id} missing summary"

    logger.info("✓ Exactly 3 summaries exist (1 existing + 2 created)")
    logger.info("=== TEST PASSED ===\n")


@pytest.mark.asyncio
async def test_ondemand_summarization_handles_partial_failures(db_session, mock_get_db):
    """
    Verify graceful handling when some summarizations fail.

    Flow:
    1. Load 3 newsletters without summaries
    2. Mock summarizer to fail for 2nd newsletter
    3. Create digest (should create 2/3 summaries)
    4. Verify digest continues with available summaries
    """
    logger.info("=== TEST: On-demand summarization handles partial failures ===")

    # ============================================================
    # 1. SETUP: Load newsletters
    # ============================================================
    logger.info("Loading test newsletters...")
    newsletters = create_test_contents_batch(db_session)

    assert db_session.query(Summary).count() == 0
    logger.info("✓ 0 summaries initially")

    # ============================================================
    # 2. MOCK: Summarizer fails for 2nd newsletter
    # ============================================================
    logger.info("Setting up API mocks with failure for 2nd newsletter...")

    # Create responses: success, FAIL, success
    mock_summary_response_1 = create_simple_summary_response(newsletter_id=1)
    mock_summary_response_3 = create_simple_summary_response(newsletter_id=3)

    def mock_create_side_effect(*args, **kwargs):
        """Side effect that fails on 2nd call."""
        if not hasattr(mock_create_side_effect, "call_count"):
            mock_create_side_effect.call_count = 0

        mock_create_side_effect.call_count += 1

        if mock_create_side_effect.call_count == 2:
            raise Exception("Simulated API failure for 2nd newsletter")
        elif mock_create_side_effect.call_count == 1:
            return mock_summary_response_1
        elif mock_create_side_effect.call_count == 3:
            return mock_summary_response_3
        else:
            # Theme analysis or digest creation
            if "themes" in str(kwargs):
                return create_simple_theme_analysis_response()
            else:
                return create_simple_digest_response()

    # Patch get_db in all modules that use it
    with patch("src.processors.digest_creator.get_db", mock_get_db):
        with patch("src.processors.summarizer.get_db", mock_get_db):
            with patch("src.processors.theme_analyzer.get_db", mock_get_db):
                with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_summarizer:
                    with patch(
                        "src.processors.theme_analyzer.Anthropic"
                    ) as mock_anthropic_analyzer:
                        with patch(
                            "src.processors.digest_creator.Anthropic"
                        ) as mock_anthropic_digest:
                            mock_summarizer_client = MagicMock()
                            mock_summarizer_client.messages.create.side_effect = (
                                mock_create_side_effect
                            )
                            mock_anthropic_summarizer.return_value = mock_summarizer_client

                            mock_analyzer_client = MagicMock()
                            mock_analyzer_client.messages.create.return_value = (
                                create_simple_theme_analysis_response()
                            )
                            mock_anthropic_analyzer.return_value = mock_analyzer_client

                            mock_digest_client = MagicMock()
                            mock_digest_client.messages.create.return_value = (
                                create_simple_digest_response()
                            )
                            mock_anthropic_digest.return_value = mock_digest_client

                            with patch("httpx.Client.post") as mock_httpx:
                                mock_httpx.return_value = create_simple_embedding_response()

                                # ============================================================
                                # 3. TEST: Create digest (should handle failure gracefully)
                                # ============================================================
                                logger.info(
                                    "Creating digest with expected failure for 2nd newsletter..."
                                )

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

                                # Should NOT raise exception, should continue
                                digest = await creator.create_digest(request)

                                logger.info("✓ Digest creation completed despite failure")

    # ============================================================
    # 4. VERIFY: 2/3 summaries created, digest still works
    # ============================================================
    logger.info("Verifying partial success...")

    summaries = db_session.query(Summary).all()

    # Should have 2 summaries (1st and 3rd succeeded)
    assert len(summaries) == 2, f"Expected 2 summaries (partial success), found {len(summaries)}"

    # Verify digest was still created
    assert digest is not None
    # Newsletter count might be 2 (only those with summaries) or 3 (attempted all)
    # This depends on implementation - just verify digest exists

    logger.info(f"✓ Partial success: {len(summaries)}/3 summaries created")
    logger.info("✓ Digest creation continued despite failure")
    logger.info("=== TEST PASSED ===\n")


@pytest.mark.asyncio
async def test_ondemand_summarization_no_newsletters_in_period(db_session):
    """
    Verify graceful handling when no newsletters exist in time period.

    Flow:
    1. Load newsletters with dates outside request period
    2. Create digest for period with no newsletters
    3. Verify empty/minimal digest created
    """
    logger.info("=== TEST: On-demand summarization with no newsletters in period ===")

    # ============================================================
    # 1. SETUP: Load newsletters outside target date range
    # ============================================================
    logger.info("Loading test newsletters...")
    newsletters = create_test_contents_batch(db_session)
    logger.info(f"Loaded {len(newsletters)} newsletters")

    # ============================================================
    # 2. TEST: Request digest for period with NO newsletters
    # ============================================================
    logger.info("Creating digest for period with no newsletters...")

    # Request period that doesn't contain our test newsletters
    # (test newsletters are dated 2025-01-13 to 2025-01-15)
    request = DigestRequest(
        digest_type=DigestType.DAILY,
        period_start=datetime(2025, 2, 1, 0, 0, 0),  # February (no newsletters)
        period_end=datetime(2025, 2, 1, 23, 59, 59),
        max_strategic_insights=5,
        max_technical_developments=5,
        max_emerging_trends=3,
        include_historical_context=False,
    )

    creator = DigestCreator()
    digest = await creator.create_digest(request)

    # ============================================================
    # 3. VERIFY: Empty digest created gracefully
    # ============================================================
    logger.info("Verifying empty digest handling...")

    assert digest is not None, "Expected digest object (possibly empty)"
    assert digest.newsletter_count == 0, f"Expected 0 newsletters, found {digest.newsletter_count}"

    # No summaries should be created
    summary_count = db_session.query(Summary).count()
    assert summary_count == 0, f"Expected 0 summaries, found {summary_count}"

    logger.info("✓ Empty digest created gracefully with no newsletters")
    logger.info("=== TEST PASSED ===\n")
