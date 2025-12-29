"""Integration tests for full review workflow.

Tests the complete review flow:
1. Generate digest → PENDING_REVIEW
2. Load context for revision
3. Interactive revision with AI
4. Apply changes
5. Finalize review (approve/reject)
6. Verify database state
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.models import ModelConfig, Provider, ProviderConfig
from src.models.digest import Digest, DigestStatus, DigestType
from src.models.newsletter import Newsletter, NewsletterSource
from src.models.summary import NewsletterSummary
from src.services.review_service import ReviewService


@pytest.fixture
def mock_anthropic_response():
    """Create mock Anthropic API response."""
    mock_response = MagicMock()
    mock_response.usage = MagicMock(input_tokens=1000, output_tokens=500)
    mock_response.stop_reason = "end_turn"

    # Mock content block with text
    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = """{
        "section_modified": "executive_overview",
        "revised_content": "Revised executive summary focusing on top 3 themes...",
        "explanation": "Made the summary more concise",
        "confidence_score": 0.95
    }"""
    mock_response.content = [mock_text_block]

    return mock_response


@pytest.mark.integration
class TestFullReviewWorkflow:
    """Tests for complete review workflow."""

    @pytest.mark.asyncio
    async def test_full_workflow_approve(
        self,
        db_session,
        sample_newsletters,
        sample_summaries,
        mock_anthropic_response,
    ):
        """Test complete workflow: generate → review → revise → approve."""
        # 1. Create digest in PENDING_REVIEW status
        digest = Digest(
            digest_type=DigestType.DAILY,
            period_start=datetime(2025, 1, 15, 0, 0, 0),
            period_end=datetime(2025, 1, 15, 23, 59, 59),
            title="AI Advances - January 15, 2025",
            executive_overview="Initial executive summary...",
            strategic_insights=[
                {"title": "RAG", "summary": "Test", "details": []}
            ],
            technical_developments=[],
            emerging_trends=[],
            actionable_recommendations={},
            sources=[],
            newsletter_count=len(sample_newsletters),
            status=DigestStatus.PENDING_REVIEW,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        )
        db_session.add(digest)
        db_session.commit()

        # 2. Start review session
        with patch('src.services.review_service.get_db') as mock_get_db, \
             patch('src.processors.digest_reviser.get_db') as mock_reviser_get_db, \
             patch('src.processors.digest_reviser.Anthropic') as mock_anthropic_class:

            # Setup database mocks
            mock_get_db.return_value.__enter__.return_value = db_session
            mock_reviser_get_db.return_value.__enter__.return_value = db_session

            # Setup Anthropic mock
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_anthropic_response
            mock_anthropic_class.return_value = mock_client

            # Create service
            config = ModelConfig(
                digest_revision="claude-sonnet-4-5",
                providers=[
                    ProviderConfig(provider=Provider.ANTHROPIC, api_key="test-key")
                ],
            )
            service = ReviewService(model_config=config)

            # Load context
            session_id = str(uuid.uuid4())
            context = await service.start_revision_session(
                digest_id=digest.id,
                session_id=session_id,
                reviewer="test@example.com",
            )

            assert context is not None
            assert context.digest.id == digest.id

            # 3. Process revision turn
            result = await service.process_revision_turn(
                context=context,
                user_input="Make executive summary more concise",
                conversation_history=[],
                session_id=session_id,
            )

            assert result.section_modified == "executive_overview"
            assert "Revised executive summary" in result.revised_content

            # 4. Apply revision
            updated_digest = await service.apply_revision(
                digest_id=digest.id,
                section="executive_overview",
                new_content=result.revised_content,
            )

            assert updated_digest.revision_count == 1
            assert updated_digest.executive_overview == result.revised_content

            # 5. Create revision turn for audit
            turn = await service.create_revision_turn(
                turn_number=1,
                user_input="Make executive summary more concise",
                ai_response=result.explanation,
                section_modified=result.section_modified,
                change_accepted=True,
            )

            # 6. Finalize with approval
            revision_history = {
                "sessions": [{
                    "session_id": session_id,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                    "reviewer": "test@example.com",
                    "turns": [turn.to_dict()],
                    "final_action": "approve",
                }]
            }

            final_digest = await service.finalize_review(
                digest_id=digest.id,
                action="approve",
                revision_history=revision_history,
                reviewer="test@example.com",
            )

            # Verify final state
            assert final_digest.status == DigestStatus.APPROVED
            assert final_digest.revision_count == 1
            assert final_digest.reviewed_by == "test@example.com"
            assert final_digest.reviewed_at is not None
            assert final_digest.revision_history is not None
            assert len(final_digest.revision_history["sessions"]) == 1

    @pytest.mark.asyncio
    async def test_workflow_reject(self, db_session):
        """Test workflow with rejection."""
        # Create digest
        digest = Digest(
            digest_type=DigestType.DAILY,
            period_start=datetime(2025, 1, 15, 0, 0, 0),
            period_end=datetime(2025, 1, 15, 23, 59, 59),
            title="Test Digest",
            executive_overview="Test content",
            strategic_insights=[],
            technical_developments=[],
            emerging_trends=[],
            actionable_recommendations={},
            sources=[],
            newsletter_count=5,
            status=DigestStatus.PENDING_REVIEW,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        )
        db_session.add(digest)
        db_session.commit()

        with patch('src.services.review_service.get_db') as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = db_session

            service = ReviewService()

            # Quick reject
            result = await service.quick_review(
                digest_id=digest.id,
                action="reject",
                reviewer="test@example.com",
                notes="Content not ready",
            )

            assert result.status == DigestStatus.REJECTED
            assert result.review_notes == "Content not ready"

    @pytest.mark.asyncio
    async def test_workflow_multiple_revisions(
        self,
        db_session,
        sample_newsletters,
        sample_summaries,
        mock_anthropic_response,
    ):
        """Test workflow with multiple revision turns."""
        # Create digest
        digest = Digest(
            digest_type=DigestType.DAILY,
            period_start=datetime(2025, 1, 15, 0, 0, 0),
            period_end=datetime(2025, 1, 15, 23, 59, 59),
            title="Test Digest",
            executive_overview="Initial summary",
            strategic_insights=[{"title": "Test", "summary": "Test"}],
            technical_developments=[],
            emerging_trends=[],
            actionable_recommendations={},
            sources=[],
            newsletter_count=3,
            status=DigestStatus.PENDING_REVIEW,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        )
        db_session.add(digest)
        db_session.commit()

        with patch('src.services.review_service.get_db') as mock_get_db, \
             patch('src.processors.digest_reviser.get_db') as mock_reviser_get_db, \
             patch('src.processors.digest_reviser.Anthropic') as mock_anthropic_class:

            mock_get_db.return_value.__enter__.return_value = db_session
            mock_reviser_get_db.return_value.__enter__.return_value = db_session

            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_anthropic_response
            mock_anthropic_class.return_value = mock_client

            config = ModelConfig(
                digest_revision="claude-sonnet-4-5",
                providers=[
                    ProviderConfig(provider=Provider.ANTHROPIC, api_key="test-key")
                ],
            )
            service = ReviewService(model_config=config)

            # Start session
            session_id = str(uuid.uuid4())
            context = await service.start_revision_session(
                digest_id=digest.id,
                session_id=session_id,
                reviewer="test@example.com",
            )

            # First revision
            result1 = await service.process_revision_turn(
                context=context,
                user_input="Shorten executive summary",
                conversation_history=[],
                session_id=session_id,
            )

            await service.apply_revision(
                digest_id=digest.id,
                section=result1.section_modified,
                new_content=result1.revised_content,
            )

            # Second revision
            mock_response2 = MagicMock()
            mock_response2.usage = MagicMock(input_tokens=500, output_tokens=250)
            mock_response2.stop_reason = "end_turn"
            mock_text_block2 = MagicMock()
            mock_text_block2.type = "text"
            mock_text_block2.text = """{
                "section_modified": "strategic_insights",
                "revised_content": [{"title": "New Insight", "summary": "Updated"}],
                "explanation": "Added more strategic focus",
                "confidence_score": 0.9
            }"""
            mock_response2.content = [mock_text_block2]
            mock_client.messages.create.return_value = mock_response2

            result2 = await service.process_revision_turn(
                context=context,
                user_input="Add more strategic insights",
                conversation_history=[],
                session_id=session_id,
            )

            await service.apply_revision(
                digest_id=digest.id,
                section=result2.section_modified,
                new_content=result2.revised_content,
            )

            # Verify revision count
            final = await service.get_digest(digest.id)
            assert final.revision_count == 2

    @pytest.mark.asyncio
    async def test_workflow_save_draft(self, db_session):
        """Test saving draft without approval."""
        digest = Digest(
            digest_type=DigestType.DAILY,
            period_start=datetime(2025, 1, 15, 0, 0, 0),
            period_end=datetime(2025, 1, 15, 23, 59, 59),
            title="Test Digest",
            executive_overview="Test",
            strategic_insights=[],
            technical_developments=[],
            emerging_trends=[],
            actionable_recommendations={},
            sources=[],
            newsletter_count=1,
            status=DigestStatus.PENDING_REVIEW,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        )
        db_session.add(digest)
        db_session.commit()

        with patch('src.services.review_service.get_db') as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = db_session

            service = ReviewService()

            result = await service.finalize_review(
                digest_id=digest.id,
                action="save-draft",
                revision_history={},
                reviewer="test@example.com",
            )

            # Should remain in PENDING_REVIEW
            assert result.status == DigestStatus.PENDING_REVIEW
            assert result.reviewed_by == "test@example.com"


@pytest.mark.integration
class TestReviewWorkflowEdgeCases:
    """Tests for edge cases in review workflow."""

    @pytest.mark.asyncio
    async def test_review_already_delivered_digest(self, db_session):
        """Test that already delivered digests can't be reviewed."""
        digest = Digest(
            digest_type=DigestType.DAILY,
            period_start=datetime(2025, 1, 15, 0, 0, 0),
            period_end=datetime(2025, 1, 15, 23, 59, 59),
            title="Test",
            executive_overview="Test",
            strategic_insights=[],
            technical_developments=[],
            emerging_trends=[],
            actionable_recommendations={},
            sources=[],
            newsletter_count=1,
            status=DigestStatus.DELIVERED,  # Already delivered
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        )
        db_session.add(digest)
        db_session.commit()

        with patch('src.services.review_service.get_db') as mock_get_db, \
             patch('src.processors.digest_reviser.get_db') as mock_reviser_get_db:

            mock_get_db.return_value.__enter__.return_value = db_session
            mock_reviser_get_db.return_value.__enter__.return_value = db_session

            service = ReviewService()

            with pytest.raises(ValueError, match="not reviewable"):
                await service.start_revision_session(
                    digest_id=digest.id,
                    session_id="test",
                    reviewer="test@example.com",
                )

    @pytest.mark.asyncio
    async def test_revision_history_merge(self, db_session):
        """Test that revision history from multiple sessions is merged."""
        digest = Digest(
            digest_type=DigestType.DAILY,
            period_start=datetime(2025, 1, 15, 0, 0, 0),
            period_end=datetime(2025, 1, 15, 23, 59, 59),
            title="Test",
            executive_overview="Test",
            strategic_insights=[],
            technical_developments=[],
            emerging_trends=[],
            actionable_recommendations={},
            sources=[],
            newsletter_count=1,
            status=DigestStatus.PENDING_REVIEW,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        )
        # Set initial revision history
        digest.revision_history = {
            "sessions": [
                {"session_id": "session1", "turns": []}
            ]
        }
        db_session.add(digest)
        db_session.commit()

        with patch('src.services.review_service.get_db') as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = db_session

            service = ReviewService()

            # Add second session
            new_history = {
                "sessions": [
                    {"session_id": "session2", "turns": []}
                ]
            }

            result = await service.finalize_review(
                digest_id=digest.id,
                action="save-draft",
                revision_history=new_history,
                reviewer="test@example.com",
            )

            # Should have both sessions
            assert len(result.revision_history["sessions"]) == 2
