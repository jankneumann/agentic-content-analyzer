"""Tests for ReviewService."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.digest import Digest, DigestStatus, DigestType
from src.models.revision import RevisionContext, RevisionResult, RevisionTurn
from src.services.review_service import ReviewService


@pytest.fixture
def sample_digest():
    """Create sample digest."""
    digest = Digest(
        digest_type=DigestType.DAILY,
        period_start=datetime(2025, 1, 15, 0, 0, 0),
        period_end=datetime(2025, 1, 15, 23, 59, 59),
        title="AI Advances - January 15, 2025",
        executive_overview="Key AI developments...",
        strategic_insights=[{"title": "RAG", "summary": "Test"}],
        technical_developments=[],
        emerging_trends=[],
        actionable_recommendations={},
        sources=[],
        newsletter_count=5,
        status=DigestStatus.PENDING_REVIEW,
        agent_framework="claude",
        model_used="claude-sonnet-4-5",
    )
    digest.id = 1
    digest.revision_count = 0
    digest.revision_history = None
    return digest


@pytest.fixture
def mock_digest_reviser():
    """Create mock DigestReviser."""
    with patch("src.services.review_service.DigestReviser") as mock_class:
        mock_reviser = MagicMock()
        mock_class.return_value = mock_reviser
        yield mock_reviser


class TestReviewServiceInitialization:
    """Tests for ReviewService initialization."""

    @patch("src.config.settings")
    def test_initialization_default(self, mock_settings):
        """Test initialization with default config."""
        mock_config = MagicMock()
        mock_settings.get_model_config.return_value = mock_config

        service = ReviewService()

        assert service.model_config == mock_config
        assert service.reviser is not None

    def test_initialization_with_config(self):
        """Test initialization with custom config."""
        mock_config = MagicMock()

        service = ReviewService(model_config=mock_config)

        assert service.model_config == mock_config


class TestReviewServiceListPendingReviews:
    """Tests for list_pending_reviews method."""

    @pytest.mark.asyncio
    async def test_list_pending_reviews_success(self, sample_digest):
        """Test listing pending reviews."""
        with patch("src.services.review_service.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            # Mock query
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.all.return_value = [sample_digest]

            mock_db.query.return_value = mock_query

            service = ReviewService()
            digests = await service.list_pending_reviews()

            assert len(digests) == 1
            assert digests[0].id == 1
            assert digests[0].status == DigestStatus.PENDING_REVIEW

    @pytest.mark.asyncio
    async def test_list_pending_reviews_empty(self):
        """Test listing when no pending reviews."""
        with patch("src.services.review_service.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.all.return_value = []

            mock_db.query.return_value = mock_query

            service = ReviewService()
            digests = await service.list_pending_reviews()

            assert len(digests) == 0


class TestReviewServiceGetDigest:
    """Tests for get_digest method."""

    @pytest.mark.asyncio
    async def test_get_digest_found(self, sample_digest):
        """Test getting existing digest."""
        with patch("src.services.review_service.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_db.query.return_value.filter_by.return_value.first.return_value = sample_digest

            service = ReviewService()
            digest = await service.get_digest(digest_id=1)

            assert digest is not None
            assert digest.id == 1

    @pytest.mark.asyncio
    async def test_get_digest_not_found(self):
        """Test getting non-existent digest."""
        with patch("src.services.review_service.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_db.query.return_value.filter_by.return_value.first.return_value = None

            service = ReviewService()
            digest = await service.get_digest(digest_id=999)

            assert digest is None


class TestReviewServiceStartRevisionSession:
    """Tests for start_revision_session method."""

    @pytest.mark.asyncio
    async def test_start_revision_session_success(self, sample_digest, mock_digest_reviser):
        """Test starting revision session."""
        mock_context = MagicMock(spec=RevisionContext)
        mock_context.digest = sample_digest
        mock_digest_reviser.load_context = AsyncMock(return_value=mock_context)

        service = ReviewService()
        service.reviser = mock_digest_reviser

        context = await service.start_revision_session(
            digest_id=1,
            session_id="test-session",
            reviewer="test@example.com",
        )

        assert context == mock_context
        mock_digest_reviser.load_context.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_start_revision_session_invalid_status(self, sample_digest, mock_digest_reviser):
        """Test starting session with invalid digest status."""
        # Set digest to DELIVERED (not reviewable)
        sample_digest.status = DigestStatus.DELIVERED

        mock_context = MagicMock(spec=RevisionContext)
        mock_context.digest = sample_digest
        mock_digest_reviser.load_context = AsyncMock(return_value=mock_context)

        service = ReviewService()
        service.reviser = mock_digest_reviser

        with pytest.raises(ValueError, match="not reviewable"):
            await service.start_revision_session(
                digest_id=1,
                session_id="test-session",
                reviewer="test@example.com",
            )


class TestReviewServiceProcessRevisionTurn:
    """Tests for process_revision_turn method."""

    @pytest.mark.asyncio
    async def test_process_revision_turn(self, mock_digest_reviser):
        """Test processing revision turn."""
        mock_context = MagicMock()
        mock_result = RevisionResult(
            revised_content="New content",
            section_modified="executive_overview",
            explanation="Made it more concise",
        )

        mock_digest_reviser.revise_section = AsyncMock(return_value=mock_result)

        service = ReviewService()
        service.reviser = mock_digest_reviser

        result = await service.process_revision_turn(
            context=mock_context,
            user_input="Make it shorter",
            conversation_history=[],
            session_id="test-session",
        )

        assert result == mock_result
        mock_digest_reviser.revise_section.assert_called_once()


class TestReviewServiceApplyRevision:
    """Tests for apply_revision method."""

    @pytest.mark.asyncio
    async def test_apply_revision_success(self, sample_digest, mock_digest_reviser):
        """Test applying revision."""
        updated_digest = sample_digest
        updated_digest.revision_count = 1

        with patch("src.services.review_service.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_db.query.return_value.filter_by.return_value.first.return_value = sample_digest

            mock_digest_reviser.apply_revision = AsyncMock(return_value=updated_digest)

            service = ReviewService()
            service.reviser = mock_digest_reviser

            result = await service.apply_revision(
                digest_id=1,
                section="executive_overview",
                new_content="New content",
            )

            assert result.revision_count == 1
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_revision_digest_not_found(self):
        """Test applying revision to non-existent digest."""
        with patch("src.services.review_service.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_db.query.return_value.filter_by.return_value.first.return_value = None

            service = ReviewService()

            with pytest.raises(ValueError, match="not found"):
                await service.apply_revision(
                    digest_id=999,
                    section="test",
                    new_content="test",
                )


class TestReviewServiceFinalizeReview:
    """Tests for finalize_review method."""

    @pytest.mark.asyncio
    async def test_finalize_review_approve(self, sample_digest):
        """Test finalizing review with approval."""
        with patch("src.services.review_service.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_db.query.return_value.filter_by.return_value.first.return_value = sample_digest

            service = ReviewService()

            revision_history = {"sessions": [{"session_id": "test"}]}

            result = await service.finalize_review(
                digest_id=1,
                action="approve",
                revision_history=revision_history,
                reviewer="test@example.com",
            )

            assert result.status == DigestStatus.APPROVED
            assert result.reviewed_by == "test@example.com"
            assert result.reviewed_at is not None
            assert result.revision_history == revision_history

    @pytest.mark.asyncio
    async def test_finalize_review_reject(self, sample_digest):
        """Test finalizing review with rejection."""
        with patch("src.services.review_service.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_db.query.return_value.filter_by.return_value.first.return_value = sample_digest

            service = ReviewService()

            result = await service.finalize_review(
                digest_id=1,
                action="reject",
                revision_history={},
                reviewer="test@example.com",
                review_notes="Not ready",
            )

            assert result.status == DigestStatus.REJECTED
            assert result.review_notes == "Not ready"

    @pytest.mark.asyncio
    async def test_finalize_review_save_draft(self, sample_digest):
        """Test finalizing review as save-draft."""
        with patch("src.services.review_service.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_db.query.return_value.filter_by.return_value.first.return_value = sample_digest

            service = ReviewService()

            result = await service.finalize_review(
                digest_id=1,
                action="save-draft",
                revision_history={},
                reviewer="test@example.com",
            )

            assert result.status == DigestStatus.PENDING_REVIEW

    @pytest.mark.asyncio
    async def test_finalize_review_invalid_action(self, sample_digest):
        """Test finalizing review with invalid action."""
        with patch("src.services.review_service.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_db.query.return_value.filter_by.return_value.first.return_value = sample_digest

            service = ReviewService()

            with pytest.raises(ValueError, match="Invalid action"):
                await service.finalize_review(
                    digest_id=1,
                    action="invalid",
                    revision_history={},
                    reviewer="test@example.com",
                )


class TestReviewServiceQuickReview:
    """Tests for quick_review method."""

    @pytest.mark.asyncio
    async def test_quick_review_approve(self, sample_digest):
        """Test quick approval."""
        with patch("src.services.review_service.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_db.query.return_value.filter_by.return_value.first.return_value = sample_digest

            service = ReviewService()

            result = await service.quick_review(
                digest_id=1,
                action="approve",
                reviewer="test@example.com",
            )

            assert result.status == DigestStatus.APPROVED
            assert "quick" in str(result.revision_history)

    @pytest.mark.asyncio
    async def test_quick_review_reject(self, sample_digest):
        """Test quick rejection."""
        with patch("src.services.review_service.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_db.query.return_value.filter_by.return_value.first.return_value = sample_digest

            service = ReviewService()

            result = await service.quick_review(
                digest_id=1,
                action="reject",
                reviewer="test@example.com",
                notes="Too technical",
            )

            assert result.status == DigestStatus.REJECTED
            assert result.review_notes == "Too technical"


class TestReviewServiceCreateRevisionTurn:
    """Tests for create_revision_turn method."""

    @pytest.mark.asyncio
    async def test_create_revision_turn(self):
        """Test creating revision turn object."""
        service = ReviewService()

        turn = await service.create_revision_turn(
            turn_number=1,
            user_input="Test input",
            ai_response="Test response",
            section_modified="test_section",
            change_accepted=True,
            tools_called=["tool1"],
        )

        assert isinstance(turn, RevisionTurn)
        assert turn.turn == 1
        assert turn.user_input == "Test input"
        assert turn.change_accepted is True
        assert turn.tools_called == ["tool1"]


class TestReviewServiceCostCalculation:
    """Tests for calculate_revision_cost method."""

    def test_calculate_revision_cost(self, mock_digest_reviser):
        """Test cost calculation."""
        mock_digest_reviser.calculate_cost.return_value = 0.05

        service = ReviewService()
        service.reviser = mock_digest_reviser

        cost = service.calculate_revision_cost()

        assert cost == 0.05
        mock_digest_reviser.calculate_cost.assert_called_once()
