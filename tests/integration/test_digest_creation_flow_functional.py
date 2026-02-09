"""Functional integration test: Digest creation flow.

This test verifies the DIGEST CREATION FLOW works correctly:
- Creating digests from newsletters with existing summaries
- Theme analysis integration
- Digest structure and content validation
- Database operations (digest storage)
- Different digest types (DAILY, WEEKLY)
- Error handling

This does NOT verify LLM output quality - that's for scenario tests.
We only care that the flow works, not that digests are meaningful.
"""

import logging
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.models.digest import Digest, DigestRequest, DigestType
from src.models.summary import Summary
from src.processors.digest_creator import DigestCreator
from tests.helpers.simple_mocks import (
    create_simple_digest_response,
    create_simple_embedding_response,
    create_simple_theme_analysis_response,
)
from tests.helpers.test_data import create_test_contents_batch

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@pytest.mark.asyncio
async def test_create_daily_digest_with_summaries(db_session, mock_get_db):
    """
    Verify daily digest creation works with existing summaries.

    Flow:
    1. Load 3 newsletters
    2. Create summaries for all newsletters
    3. Create daily digest
    4. Verify digest created with correct structure
    5. Verify digest saved to database
    """
    logger.info("=== TEST: Create daily digest with existing summaries ===")

    # ============================================================
    # 1. SETUP: Load newsletters and create summaries
    # ============================================================
    logger.info("Loading test newsletters and creating summaries...")
    newsletters = create_test_contents_batch(db_session)

    # Create summaries for all newsletters
    for i, newsletter in enumerate(newsletters, 1):
        summary = Summary(
            content_id=newsletter.id,
            executive_summary=f"Summary for newsletter {i}",
            key_themes=[f"Theme {i}A", f"Theme {i}B"],
            strategic_insights=[f"Insight {i}"],
            technical_details=[f"Detail {i}"],
            actionable_items=[f"Action {i}"],
            notable_quotes=[f"Quote {i}"],
            relevance_scores={
                "cto_leadership": 0.8,
                "technical_teams": 0.9,
                "individual_developers": 0.7,
            },
            agent_framework="claude",
            model_used="claude-haiku-4-5",
            model_version="20250929",
        )
        db_session.add(summary)
    db_session.commit()

    logger.info(f"✓ Created summaries for {len(newsletters)} newsletters")

    # Verify setup
    assert db_session.query(Summary).count() == 3
    assert db_session.query(Digest).count() == 0

    # ============================================================
    # 2. MOCK: Theme analysis and digest creation APIs
    # ============================================================
    logger.info("Setting up API mocks...")
    mock_theme_response = create_simple_theme_analysis_response(theme_count=3)
    mock_digest_response = create_simple_digest_response()

    # Patch get_db and Anthropic
    with patch("src.processors.digest_creator.get_db", mock_get_db):
        with patch("src.processors.summarizer.get_db", mock_get_db):
            with patch("src.processors.theme_analyzer.get_db", mock_get_db):
                with patch("src.processors.theme_analyzer.Anthropic") as mock_anthropic_analyzer:
                    with patch("src.processors.digest_creator.Anthropic") as mock_anthropic_digest:
                        mock_analyzer_client = MagicMock()
                        mock_analyzer_client.messages.create.return_value = mock_theme_response
                        mock_anthropic_analyzer.return_value = mock_analyzer_client

                        mock_digest_client = MagicMock()
                        mock_digest_client.messages.create.return_value = mock_digest_response
                        mock_anthropic_digest.return_value = mock_digest_client

                        with patch("httpx.Client.post") as mock_httpx:
                            mock_httpx.return_value = create_simple_embedding_response()

                            # ============================================================
                            # 3. TEST: Create daily digest
                            # ============================================================
                            logger.info("Creating daily digest...")

                            request = DigestRequest(
                                digest_type=DigestType.DAILY,
                                period_start=datetime(2025, 1, 12, 0, 0, 0),
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
    # 4. VERIFY: Digest structure and content
    # ============================================================
    logger.info("Verifying digest structure...")

    assert digest is not None, "Digest should be created"
    assert digest.digest_type == DigestType.DAILY
    assert digest.newsletter_count == 3
    assert digest.title is not None
    assert digest.executive_overview is not None
    assert digest.agent_framework == "claude"
    assert digest.model_used is not None

    # Verify sections (can be empty for functional test)
    assert isinstance(digest.strategic_insights, list)
    assert isinstance(digest.technical_developments, list)
    assert isinstance(digest.emerging_trends, list)
    assert isinstance(digest.actionable_recommendations, dict)

    # Verify sources
    assert len(digest.sources) == 3, f"Expected 3 sources, got {len(digest.sources)}"

    logger.info(
        f"✓ Digest structure valid: {digest.newsletter_count} newsletters, {len(digest.sources)} sources"
    )
    logger.info("=== TEST PASSED ===\n")


@pytest.mark.asyncio
async def test_create_weekly_digest(db_session, mock_get_db):
    """
    Verify weekly digest creation works.

    Flow:
    1. Load newsletters spanning multiple days
    2. Create summaries
    3. Create weekly digest
    4. Verify digest type is WEEKLY
    """
    logger.info("=== TEST: Create weekly digest ===")

    # ============================================================
    # 1. SETUP: Load newsletters and create summaries
    # ============================================================
    logger.info("Loading test newsletters and creating summaries...")
    newsletters = create_test_contents_batch(db_session)

    # Create summaries
    for i, newsletter in enumerate(newsletters, 1):
        summary = Summary(
            content_id=newsletter.id,
            executive_summary=f"Summary {i}",
            key_themes=[f"Theme {i}"],
            strategic_insights=[f"Insight {i}"],
            technical_details=[f"Detail {i}"],
            actionable_items=[f"Action {i}"],
            notable_quotes=[f"Quote {i}"],
            relevance_scores={
                "cto_leadership": 0.8,
                "technical_teams": 0.9,
                "individual_developers": 0.7,
            },
            agent_framework="claude",
            model_used="claude-haiku-4-5",
            model_version="20250929",
        )
        db_session.add(summary)
    db_session.commit()

    logger.info(f"✓ Created summaries for {len(newsletters)} newsletters")

    # ============================================================
    # 2. MOCK: APIs
    # ============================================================
    logger.info("Setting up API mocks...")
    mock_theme_response = create_simple_theme_analysis_response(theme_count=3)
    mock_digest_response = create_simple_digest_response()

    with patch("src.processors.digest_creator.get_db", mock_get_db):
        with patch("src.processors.summarizer.get_db", mock_get_db):
            with patch("src.processors.theme_analyzer.get_db", mock_get_db):
                with patch("src.processors.theme_analyzer.Anthropic") as mock_anthropic_analyzer:
                    with patch("src.processors.digest_creator.Anthropic") as mock_anthropic_digest:
                        mock_analyzer_client = MagicMock()
                        mock_analyzer_client.messages.create.return_value = mock_theme_response
                        mock_anthropic_analyzer.return_value = mock_analyzer_client

                        mock_digest_client = MagicMock()
                        mock_digest_client.messages.create.return_value = mock_digest_response
                        mock_anthropic_digest.return_value = mock_digest_client

                        with patch("httpx.Client.post") as mock_httpx:
                            mock_httpx.return_value = create_simple_embedding_response()

                            # ============================================================
                            # 3. TEST: Create weekly digest
                            # ============================================================
                            logger.info("Creating weekly digest...")

                            request = DigestRequest(
                                digest_type=DigestType.WEEKLY,
                                period_start=datetime(2025, 1, 12, 0, 0, 0),
                                period_end=datetime(2025, 1, 19, 23, 59, 59),  # 7 days
                                max_strategic_insights=10,
                                max_technical_developments=10,
                                max_emerging_trends=5,
                                include_historical_context=False,
                            )

                            creator = DigestCreator()
                            digest = await creator.create_digest(request)

                            logger.info("✓ Weekly digest creation completed")

    # ============================================================
    # 4. VERIFY: Digest is WEEKLY type
    # ============================================================
    logger.info("Verifying weekly digest...")

    assert digest is not None
    assert digest.digest_type == DigestType.WEEKLY, f"Expected WEEKLY, got {digest.digest_type}"
    assert digest.newsletter_count == 3

    logger.info(f"✓ Weekly digest created: {digest.newsletter_count} newsletters")
    logger.info("=== TEST PASSED ===\n")


@pytest.mark.asyncio
async def test_create_digest_with_empty_period(db_session, mock_get_db):
    """
    Verify digest creation handles empty periods gracefully.

    Flow:
    1. Load newsletters
    2. Request digest for period with NO newsletters
    3. Verify empty digest created
    4. Verify newsletter_count = 0
    """
    logger.info("=== TEST: Create digest with empty period ===")

    # ============================================================
    # 1. SETUP: Load newsletters (but request different period)
    # ============================================================
    logger.info("Loading test newsletters...")
    newsletters = create_test_contents_batch(db_session)
    logger.info(f"Loaded {len(newsletters)} newsletters (dated 2025-01-13 to 2025-01-15)")

    # ============================================================
    # 2. TEST: Request digest for period with no newsletters
    # ============================================================
    logger.info("Creating digest for empty period (2025-02-01)...")

    # Request period that doesn't contain our newsletters
    request = DigestRequest(
        digest_type=DigestType.DAILY,
        period_start=datetime(2025, 2, 1, 0, 0, 0),  # February (no newsletters)
        period_end=datetime(2025, 2, 1, 23, 59, 59),
        max_strategic_insights=5,
        max_technical_developments=5,
        max_emerging_trends=3,
        include_historical_context=False,
    )

    # Patch get_db (no API mocks needed for empty digest)
    with patch("src.processors.digest_creator.get_db", mock_get_db):
        with patch("src.processors.summarizer.get_db", mock_get_db):
            with patch("src.processors.theme_analyzer.get_db", mock_get_db):
                creator = DigestCreator()
                digest = await creator.create_digest(request)

    # ============================================================
    # 3. VERIFY: Empty digest created gracefully
    # ============================================================
    logger.info("Verifying empty digest...")

    assert digest is not None, "Digest should be created even for empty period"
    assert digest.newsletter_count == 0, f"Expected 0 newsletters, got {digest.newsletter_count}"
    assert len(digest.sources) == 0, "Sources should be empty"

    logger.info("✓ Empty digest created gracefully")
    logger.info("=== TEST PASSED ===\n")


@pytest.mark.asyncio
async def test_digest_includes_all_newsletter_sources(db_session, mock_get_db):
    """
    Verify digest sources list includes all newsletters.

    Flow:
    1. Load 3 newsletters with different publications
    2. Create summaries
    3. Create digest
    4. Verify sources list has all 3 newsletters with correct metadata
    """
    logger.info("=== TEST: Digest includes all newsletter sources ===")

    # ============================================================
    # 1. SETUP: Load newsletters and create summaries
    # ============================================================
    logger.info("Loading test newsletters...")
    newsletters = create_test_contents_batch(db_session)

    # Create summaries
    for i, newsletter in enumerate(newsletters, 1):
        summary = Summary(
            content_id=newsletter.id,
            executive_summary=f"Summary {i}",
            key_themes=[f"Theme {i}"],
            strategic_insights=[f"Insight {i}"],
            technical_details=[f"Detail {i}"],
            actionable_items=[f"Action {i}"],
            notable_quotes=[f"Quote {i}"],
            relevance_scores={
                "cto_leadership": 0.8,
                "technical_teams": 0.9,
                "individual_developers": 0.7,
            },
            agent_framework="claude",
            model_used="claude-haiku-4-5",
            model_version="20250929",
        )
        db_session.add(summary)
    db_session.commit()

    logger.info(f"✓ Created summaries for {len(newsletters)} newsletters")

    # ============================================================
    # 2. MOCK: APIs
    # ============================================================
    mock_theme_response = create_simple_theme_analysis_response(theme_count=3)
    mock_digest_response = create_simple_digest_response()

    with patch("src.processors.digest_creator.get_db", mock_get_db):
        with patch("src.processors.summarizer.get_db", mock_get_db):
            with patch("src.processors.theme_analyzer.get_db", mock_get_db):
                with patch("src.processors.theme_analyzer.Anthropic") as mock_anthropic_analyzer:
                    with patch("src.processors.digest_creator.Anthropic") as mock_anthropic_digest:
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
                                period_start=datetime(2025, 1, 12, 0, 0, 0),
                                period_end=datetime(2025, 1, 15, 23, 59, 59),
                                max_strategic_insights=5,
                                max_technical_developments=5,
                                max_emerging_trends=3,
                                include_historical_context=False,
                            )

                            creator = DigestCreator()
                            digest = await creator.create_digest(request)

    # ============================================================
    # 4. VERIFY: Sources list complete and accurate
    # ============================================================
    logger.info("Verifying sources list...")

    assert len(digest.sources) == 3, f"Expected 3 sources, got {len(digest.sources)}"

    # Verify each source has required fields
    newsletter_titles = {nl.title for nl in newsletters}
    source_titles = set()

    for source in digest.sources:
        assert "title" in source, "Source missing 'title' field"
        assert "publication" in source, "Source missing 'publication' field"
        assert "date" in source, "Source missing 'date' field"
        # Note: 'id' is not included in sources, only title/publication/date/url

        source_titles.add(source["title"])
        logger.info(f"✓ Source: {source['publication']} - {source['title']} ({source['date']})")

    # Verify all newsletter titles are in sources
    assert source_titles == newsletter_titles, "Source titles should match newsletter titles"

    logger.info(f"✓ All {len(digest.sources)} sources present with correct metadata")
    logger.info("=== TEST PASSED ===\n")


@pytest.mark.asyncio
async def test_digest_processing_time_tracked(db_session, mock_get_db):
    """
    Verify digest tracks processing time.

    Flow:
    1. Create digest
    2. Verify processing_time_seconds is set
    3. Verify it's a positive number
    """
    logger.info("=== TEST: Digest tracks processing time ===")

    # ============================================================
    # 1. SETUP: Load newsletters and create summaries
    # ============================================================
    newsletters = create_test_contents_batch(db_session)

    for i, newsletter in enumerate(newsletters, 1):
        summary = Summary(
            content_id=newsletter.id,
            executive_summary=f"Summary {i}",
            key_themes=[f"Theme {i}"],
            strategic_insights=[f"Insight {i}"],
            technical_details=[f"Detail {i}"],
            actionable_items=[f"Action {i}"],
            notable_quotes=[f"Quote {i}"],
            relevance_scores={
                "cto_leadership": 0.8,
                "technical_teams": 0.9,
                "individual_developers": 0.7,
            },
            agent_framework="claude",
            model_used="claude-haiku-4-5",
            model_version="20250929",
        )
        db_session.add(summary)
    db_session.commit()

    # ============================================================
    # 2. MOCK: APIs
    # ============================================================
    mock_theme_response = create_simple_theme_analysis_response(theme_count=3)
    mock_digest_response = create_simple_digest_response()

    with patch("src.processors.digest_creator.get_db", mock_get_db):
        with patch("src.processors.summarizer.get_db", mock_get_db):
            with patch("src.processors.theme_analyzer.get_db", mock_get_db):
                with patch("src.processors.theme_analyzer.Anthropic") as mock_anthropic_analyzer:
                    with patch("src.processors.digest_creator.Anthropic") as mock_anthropic_digest:
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
                            request = DigestRequest(
                                digest_type=DigestType.DAILY,
                                period_start=datetime(2025, 1, 12, 0, 0, 0),
                                period_end=datetime(2025, 1, 15, 23, 59, 59),
                                max_strategic_insights=5,
                                max_technical_developments=5,
                                max_emerging_trends=3,
                                include_historical_context=False,
                            )

                            creator = DigestCreator()
                            digest = await creator.create_digest(request)

    # ============================================================
    # 4. VERIFY: Processing time tracked
    # ============================================================
    logger.info("Verifying processing time...")

    assert digest.processing_time_seconds is not None, "Processing time should be tracked"
    assert digest.processing_time_seconds > 0, "Processing time should be positive"
    assert digest.processing_time_seconds < 60, (
        "Processing time should be reasonable (< 60s for test)"
    )

    logger.info(f"✓ Processing time tracked: {digest.processing_time_seconds:.2f}s")
    logger.info("=== TEST PASSED ===\n")


@pytest.mark.asyncio
async def test_digest_with_custom_limits(db_session, mock_get_db):
    """
    Verify digest respects custom section limits.

    Flow:
    1. Create digest with custom limits
    2. Verify request parameters are honored
    """
    logger.info("=== TEST: Digest with custom section limits ===")

    # ============================================================
    # 1. SETUP: Load newsletters and create summaries
    # ============================================================
    newsletters = create_test_contents_batch(db_session)

    for i, newsletter in enumerate(newsletters, 1):
        summary = Summary(
            content_id=newsletter.id,
            executive_summary=f"Summary {i}",
            key_themes=[f"Theme {i}"],
            strategic_insights=[f"Insight {i}"],
            technical_details=[f"Detail {i}"],
            actionable_items=[f"Action {i}"],
            notable_quotes=[f"Quote {i}"],
            relevance_scores={
                "cto_leadership": 0.8,
                "technical_teams": 0.9,
                "individual_developers": 0.7,
            },
            agent_framework="claude",
            model_used="claude-haiku-4-5",
            model_version="20250929",
        )
        db_session.add(summary)
    db_session.commit()

    # ============================================================
    # 2. MOCK: APIs
    # ============================================================
    mock_theme_response = create_simple_theme_analysis_response(theme_count=3)
    mock_digest_response = create_simple_digest_response()

    with patch("src.processors.digest_creator.get_db", mock_get_db):
        with patch("src.processors.summarizer.get_db", mock_get_db):
            with patch("src.processors.theme_analyzer.get_db", mock_get_db):
                with patch("src.processors.theme_analyzer.Anthropic") as mock_anthropic_analyzer:
                    with patch("src.processors.digest_creator.Anthropic") as mock_anthropic_digest:
                        mock_analyzer_client = MagicMock()
                        mock_analyzer_client.messages.create.return_value = mock_theme_response
                        mock_anthropic_analyzer.return_value = mock_analyzer_client

                        mock_digest_client = MagicMock()
                        mock_digest_client.messages.create.return_value = mock_digest_response
                        mock_anthropic_digest.return_value = mock_digest_client

                        with patch("httpx.Client.post") as mock_httpx:
                            mock_httpx.return_value = create_simple_embedding_response()

                            # ============================================================
                            # 3. TEST: Create digest with custom limits
                            # ============================================================
                            logger.info("Creating digest with custom limits...")

                            request = DigestRequest(
                                digest_type=DigestType.DAILY,
                                period_start=datetime(2025, 1, 12, 0, 0, 0),
                                period_end=datetime(2025, 1, 15, 23, 59, 59),
                                max_strategic_insights=10,  # Custom
                                max_technical_developments=15,  # Custom
                                max_emerging_trends=8,  # Custom
                                include_historical_context=False,
                            )

                            creator = DigestCreator()
                            digest = await creator.create_digest(request)

    # ============================================================
    # 4. VERIFY: Digest created (limits are enforced by LLM prompt)
    # ============================================================
    logger.info("Verifying digest with custom limits...")

    assert digest is not None
    assert digest.newsletter_count == 3

    # Note: In functional tests with simple mocks, we can't verify the actual
    # section counts match limits (that's for scenario tests with real LLM).
    # We just verify the digest was created successfully.

    logger.info("✓ Digest created with custom limits")
    logger.info("=== TEST PASSED ===\n")
