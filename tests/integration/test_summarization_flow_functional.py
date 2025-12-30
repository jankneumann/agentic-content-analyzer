"""Functional integration test: Newsletter summarization flow.

This test verifies the SUMMARIZATION FLOW works correctly:
- Individual newsletter summarization
- Batch newsletter summarization
- Database operations (summary storage, newsletter status updates)
- Error handling (invalid IDs, duplicate summarization)

This does NOT verify LLM output quality - that's for scenario tests.
We only care that the flow works, not that summaries are meaningful.
"""

import pytest
import logging
from unittest.mock import patch, MagicMock

from src.models.newsletter import Newsletter, ProcessingStatus
from src.models.summary import NewsletterSummary
from src.processors.summarizer import NewsletterSummarizer

from tests.helpers.test_data import create_test_newsletters_batch, get_default_test_newsletters
from tests.helpers.simple_mocks import create_simple_summary_response

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def test_summarize_single_newsletter(db_session, mock_get_db):
    """
    Verify single newsletter summarization works correctly.

    Flow:
    1. Load 1 newsletter
    2. Call summarizer.summarize_newsletter()
    3. Verify summary created in database
    4. Verify newsletter status updated to COMPLETED
    """
    logger.info("=== TEST: Summarize single newsletter ===")

    # ============================================================
    # 1. SETUP: Load one newsletter
    # ============================================================
    logger.info("Loading test newsletter...")
    newsletters = create_test_newsletters_batch(
        db_session,
        filenames=[get_default_test_newsletters()[0]]  # Just first one
    )
    newsletter = newsletters[0]
    logger.info(f"Loaded newsletter {newsletter.id}: {newsletter.title}")

    # Verify no summaries exist
    assert db_session.query(NewsletterSummary).count() == 0
    assert newsletter.status == ProcessingStatus.PENDING
    logger.info("✓ Verified initial state")

    # ============================================================
    # 2. MOCK: Anthropic API
    # ============================================================
    logger.info("Setting up API mocks...")
    mock_response = create_simple_summary_response(newsletter_id=newsletter.id)

    # Patch get_db and Anthropic
    with patch("src.processors.summarizer.get_db", mock_get_db):
        with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            # ============================================================
            # 3. TEST: Summarize newsletter
            # ============================================================
            logger.info("Summarizing newsletter...")
            summarizer = NewsletterSummarizer()
            success = summarizer.summarize_newsletter(newsletter.id)

            logger.info(f"✓ Summarization completed with success={success}")

    # ============================================================
    # 4. VERIFY: Database state
    # ============================================================
    logger.info("Verifying summary was created...")

    # Refresh newsletter to get updated status
    db_session.refresh(newsletter)

    # Check summary exists
    summary = db_session.query(NewsletterSummary).filter(
        NewsletterSummary.newsletter_id == newsletter.id
    ).first()

    assert summary is not None, "Summary should be created"
    assert success is True, "Summarization should succeed"
    assert newsletter.status == ProcessingStatus.COMPLETED, "Newsletter status should be COMPLETED"

    # Verify summary has required fields
    assert summary.executive_summary is not None
    assert len(summary.key_themes) > 0
    assert len(summary.strategic_insights) > 0
    assert summary.agent_framework == "claude"
    assert summary.model_used is not None

    logger.info(f"✓ Summary created with {len(summary.key_themes)} themes")
    logger.info("=== TEST PASSED ===\n")


def test_summarize_multiple_newsletters_batch(db_session, mock_get_db):
    """
    Verify batch summarization of multiple newsletters works.

    Flow:
    1. Load 3 newsletters
    2. Call summarizer.summarize_newsletters() with all IDs
    3. Verify all summaries created
    4. Verify batch tracking (created_count, skipped_count, failed_ids)
    """
    logger.info("=== TEST: Batch summarization of multiple newsletters ===")

    # ============================================================
    # 1. SETUP: Load 3 newsletters
    # ============================================================
    logger.info("Loading test newsletters...")
    newsletters = create_test_newsletters_batch(
        db_session,
        filenames=get_default_test_newsletters()
    )
    newsletter_ids = [nl.id for nl in newsletters]
    logger.info(f"Loaded {len(newsletters)} newsletters: {newsletter_ids}")

    # Verify no summaries exist
    assert db_session.query(NewsletterSummary).count() == 0
    logger.info("✓ Verified no summaries exist initially")

    # ============================================================
    # 2. MOCK: Anthropic API for 3 newsletters
    # ============================================================
    logger.info("Setting up API mocks for batch summarization...")
    mock_responses = [
        create_simple_summary_response(newsletter_id=i) for i in range(1, 4)
    ]

    # Patch get_db and Anthropic
    with patch("src.processors.summarizer.get_db", mock_get_db):
        with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = mock_responses
            mock_anthropic.return_value = mock_client

            # ============================================================
            # 3. TEST: Batch summarize all newsletters
            # ============================================================
            logger.info("Starting batch summarization...")
            summarizer = NewsletterSummarizer()
            result = summarizer.summarize_newsletters(newsletter_ids)

            logger.info(f"✓ Batch summarization completed: {result}")

    # ============================================================
    # 4. VERIFY: Batch results and database state
    # ============================================================
    logger.info("Verifying batch results...")

    # Check result tracking
    assert result['created_count'] == 3, f"Expected 3 created, got {result['created_count']}"
    assert result['skipped_count'] == 0, f"Expected 0 skipped, got {result['skipped_count']}"
    assert len(result['failed_ids']) == 0, f"Expected 0 failures, got {result['failed_ids']}"

    # Check database
    summaries = db_session.query(NewsletterSummary).all()
    assert len(summaries) == 3, f"Expected 3 summaries in DB, found {len(summaries)}"

    # Verify each newsletter has a summary
    for newsletter in newsletters:
        db_session.refresh(newsletter)
        summary = db_session.query(NewsletterSummary).filter(
            NewsletterSummary.newsletter_id == newsletter.id
        ).first()

        assert summary is not None, f"Newsletter {newsletter.id} missing summary"
        assert newsletter.status == ProcessingStatus.COMPLETED
        logger.info(f"✓ Newsletter {newsletter.id} summarized successfully")

    logger.info("=== TEST PASSED ===\n")


def test_summarize_skips_existing_summaries(db_session, mock_get_db):
    """
    Verify summarizer skips newsletters that already have summaries.

    Flow:
    1. Load 3 newsletters
    2. Create summary for 1st newsletter manually
    3. Call batch summarizer with all 3 IDs
    4. Verify only 2 new summaries created (1 skipped)
    """
    logger.info("=== TEST: Summarizer skips existing summaries ===")

    # ============================================================
    # 1. SETUP: Load newsletters and create 1 summary manually
    # ============================================================
    logger.info("Loading test newsletters...")
    newsletters = create_test_newsletters_batch(
        db_session,
        filenames=get_default_test_newsletters()
    )

    # Create summary for first newsletter manually
    logger.info(f"Creating manual summary for newsletter {newsletters[0].id}...")
    existing_summary = NewsletterSummary(
        newsletter_id=newsletters[0].id,
        executive_summary="Existing summary",
        key_themes=["Existing theme"],
        strategic_insights=["Existing insight"],
        technical_details=["Existing detail"],
        actionable_items=["Existing action"],
        notable_quotes=["Existing quote"],
        relevance_scores={"cto_leadership": 0.8, "technical_teams": 0.9, "individual_developers": 0.7},
        agent_framework="claude",
        model_used="claude-haiku-4-5",
        model_version="20250929",
    )
    db_session.add(existing_summary)
    db_session.commit()

    initial_count = db_session.query(NewsletterSummary).count()
    assert initial_count == 1, "Expected 1 existing summary"
    logger.info("✓ Created 1 existing summary")

    # ============================================================
    # 2. MOCK: Only 2 API calls needed (3rd already exists)
    # ============================================================
    logger.info("Setting up API mocks for 2 missing summaries...")
    mock_responses = [
        create_simple_summary_response(newsletter_id=i) for i in range(2, 4)
    ]

    newsletter_ids = [nl.id for nl in newsletters]

    # Patch get_db and Anthropic
    with patch("src.processors.summarizer.get_db", mock_get_db):
        with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = mock_responses
            mock_anthropic.return_value = mock_client

            # ============================================================
            # 3. TEST: Batch summarize (should skip existing)
            # ============================================================
            logger.info("Starting batch summarization...")
            summarizer = NewsletterSummarizer()
            result = summarizer.summarize_newsletters(newsletter_ids)

            logger.info(f"✓ Batch summarization completed: {result}")

    # ============================================================
    # 4. VERIFY: Only 2 new summaries created
    # ============================================================
    logger.info("Verifying results...")

    # Check result tracking
    assert result['created_count'] == 2, f"Expected 2 created, got {result['created_count']}"
    assert result['skipped_count'] == 1, f"Expected 1 skipped, got {result['skipped_count']}"
    assert len(result['failed_ids']) == 0, f"Expected 0 failures, got {result['failed_ids']}"

    # Check database - should have exactly 3 summaries total
    summaries = db_session.query(NewsletterSummary).all()
    assert len(summaries) == 3, f"Expected 3 total summaries, found {len(summaries)}"

    # Verify all newsletters have summaries
    for newsletter in newsletters:
        summary = db_session.query(NewsletterSummary).filter(
            NewsletterSummary.newsletter_id == newsletter.id
        ).first()
        assert summary is not None, f"Newsletter {newsletter.id} missing summary"

    logger.info("✓ Exactly 3 summaries exist (1 existing + 2 created)")
    logger.info("=== TEST PASSED ===\n")


def test_summarize_handles_api_failures(db_session, mock_get_db):
    """
    Verify summarizer handles API failures gracefully.

    Flow:
    1. Load 1 newsletter
    2. Mock API to raise exception
    3. Call summarizer
    4. Verify summary NOT created
    5. Verify newsletter status set to FAILED
    6. Verify error message stored
    """
    logger.info("=== TEST: Summarizer handles API failures ===")

    # ============================================================
    # 1. SETUP: Load one newsletter
    # ============================================================
    logger.info("Loading test newsletter...")
    newsletters = create_test_newsletters_batch(
        db_session,
        filenames=[get_default_test_newsletters()[0]]
    )
    newsletter = newsletters[0]
    logger.info(f"Loaded newsletter {newsletter.id}")

    assert db_session.query(NewsletterSummary).count() == 0
    logger.info("✓ Verified no summaries exist")

    # ============================================================
    # 2. MOCK: Anthropic API to raise exception
    # ============================================================
    logger.info("Setting up API mock to simulate failure...")

    # Patch get_db and Anthropic
    with patch("src.processors.summarizer.get_db", mock_get_db):
        with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = Exception("Simulated API failure")
            mock_anthropic.return_value = mock_client

            # ============================================================
            # 3. TEST: Summarize newsletter (should fail gracefully)
            # ============================================================
            logger.info("Attempting to summarize newsletter (expecting failure)...")
            summarizer = NewsletterSummarizer()
            success = summarizer.summarize_newsletter(newsletter.id)

            logger.info(f"✓ Summarization completed with success={success}")

    # ============================================================
    # 4. VERIFY: Failure handled correctly
    # ============================================================
    logger.info("Verifying failure was handled gracefully...")

    # Refresh newsletter
    db_session.refresh(newsletter)

    # Check that summary was NOT created
    summary = db_session.query(NewsletterSummary).filter(
        NewsletterSummary.newsletter_id == newsletter.id
    ).first()

    assert summary is None, "Summary should NOT be created on failure"
    assert success is False, "Summarization should return False on failure"
    assert newsletter.status == ProcessingStatus.FAILED, "Newsletter status should be FAILED"
    assert newsletter.error_message is not None, "Error message should be set"
    assert "Simulated API failure" in newsletter.error_message

    logger.info(f"✓ Failure handled: status={newsletter.status}, error='{newsletter.error_message}'")
    logger.info("=== TEST PASSED ===\n")


def test_summarize_invalid_newsletter_id(db_session, mock_get_db):
    """
    Verify summarizer handles invalid newsletter IDs gracefully.

    Flow:
    1. Call summarizer with non-existent ID
    2. Verify returns False
    3. Verify no summary created
    """
    logger.info("=== TEST: Summarizer handles invalid newsletter ID ===")

    # ============================================================
    # 1. SETUP: No newsletters loaded
    # ============================================================
    logger.info("Starting with empty database...")
    assert db_session.query(Newsletter).count() == 0
    assert db_session.query(NewsletterSummary).count() == 0
    logger.info("✓ Verified database is empty")

    # ============================================================
    # 2. TEST: Summarize non-existent newsletter
    # ============================================================
    logger.info("Attempting to summarize non-existent newsletter ID 99999...")

    # Patch get_db (no Anthropic mock needed - should fail before API call)
    with patch("src.processors.summarizer.get_db", mock_get_db):
        summarizer = NewsletterSummarizer()
        success = summarizer.summarize_newsletter(99999)

        logger.info(f"✓ Summarization completed with success={success}")

    # ============================================================
    # 3. VERIFY: Handled gracefully
    # ============================================================
    logger.info("Verifying invalid ID was handled...")

    assert success is False, "Should return False for invalid ID"
    assert db_session.query(NewsletterSummary).count() == 0, "No summary should be created"

    logger.info("✓ Invalid ID handled gracefully")
    logger.info("=== TEST PASSED ===\n")


def test_summarize_batch_with_partial_failures(db_session, mock_get_db):
    """
    Verify batch summarizer tracks failures correctly.

    Flow:
    1. Load 3 newsletters
    2. Mock API to fail for 2nd newsletter
    3. Call batch summarizer
    4. Verify 2 created, 1 failed
    5. Verify failed_ids list contains correct ID
    """
    logger.info("=== TEST: Batch summarizer handles partial failures ===")

    # ============================================================
    # 1. SETUP: Load 3 newsletters
    # ============================================================
    logger.info("Loading test newsletters...")
    newsletters = create_test_newsletters_batch(
        db_session,
        filenames=get_default_test_newsletters()
    )
    newsletter_ids = [nl.id for nl in newsletters]
    logger.info(f"Loaded {len(newsletters)} newsletters: {newsletter_ids}")

    assert db_session.query(NewsletterSummary).count() == 0
    logger.info("✓ Verified no summaries exist")

    # ============================================================
    # 2. MOCK: API fails for 2nd call
    # ============================================================
    logger.info("Setting up API mocks with failure for 2nd newsletter...")

    mock_response_1 = create_simple_summary_response(newsletter_id=1)
    mock_response_3 = create_simple_summary_response(newsletter_id=3)

    def mock_side_effect(*args, **kwargs):
        """Fail on 2nd call."""
        if not hasattr(mock_side_effect, 'call_count'):
            mock_side_effect.call_count = 0
        mock_side_effect.call_count += 1

        if mock_side_effect.call_count == 2:
            raise Exception("Simulated API failure for 2nd newsletter")
        elif mock_side_effect.call_count == 1:
            return mock_response_1
        else:
            return mock_response_3

    # Patch get_db and Anthropic
    with patch("src.processors.summarizer.get_db", mock_get_db):
        with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = mock_side_effect
            mock_anthropic.return_value = mock_client

            # ============================================================
            # 3. TEST: Batch summarize with partial failure
            # ============================================================
            logger.info("Starting batch summarization with expected failure...")
            summarizer = NewsletterSummarizer()
            result = summarizer.summarize_newsletters(newsletter_ids)

            logger.info(f"✓ Batch completed: {result}")

    # ============================================================
    # 4. VERIFY: Partial success tracked correctly
    # ============================================================
    logger.info("Verifying partial success...")

    # Check result tracking
    assert result['created_count'] == 2, f"Expected 2 created, got {result['created_count']}"
    assert result['skipped_count'] == 0, f"Expected 0 skipped, got {result['skipped_count']}"
    assert len(result['failed_ids']) == 1, f"Expected 1 failure, got {len(result['failed_ids'])}"
    assert newsletters[1].id in result['failed_ids'], "Failed ID should be in failed_ids list"

    # Check database - should have 2 summaries
    summaries = db_session.query(NewsletterSummary).all()
    assert len(summaries) == 2, f"Expected 2 summaries, found {len(summaries)}"

    # Verify newsletters 1 and 3 have summaries, 2 does not
    db_session.refresh(newsletters[0])
    db_session.refresh(newsletters[1])
    db_session.refresh(newsletters[2])

    assert newsletters[0].status == ProcessingStatus.COMPLETED
    assert newsletters[1].status == ProcessingStatus.FAILED
    assert newsletters[2].status == ProcessingStatus.COMPLETED

    logger.info("✓ Partial success: 2/3 summaries created, 1 failed as expected")
    logger.info("=== TEST PASSED ===\n")
