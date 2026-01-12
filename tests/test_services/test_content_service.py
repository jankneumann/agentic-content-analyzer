"""Tests for ContentService."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.models.content import (
    Content,
    ContentCreate,
    ContentSource,
    ContentStatus,
    ContentUpdate,
)
from src.services.content_service import ContentService


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return MagicMock()


@pytest.fixture
def service(mock_db):
    """Create ContentService with mock database."""
    return ContentService(mock_db)


@pytest.fixture
def sample_content():
    """Create sample Content object."""
    content = Content(
        source_type=ContentSource.GMAIL,
        source_id="msg-12345",
        title="Test Newsletter",
        markdown_content="# Test\n\nContent here.",
        content_hash="abc123def456",
        status=ContentStatus.PENDING,
        ingested_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
    )
    content.id = 1
    return content


@pytest.fixture
def sample_create_data():
    """Create sample ContentCreate data."""
    return ContentCreate(
        source_type=ContentSource.MANUAL,
        source_id="manual-001",
        title="Manual Content",
        markdown_content="# Manual\n\nCreated via API.",
        content_hash="hash123",
    )


class TestContentServiceCreate:
    """Tests for ContentService.create method."""

    @patch("src.services.content_service.generate_markdown_hash")
    def test_create_generates_hash_if_empty(self, mock_hash, service, mock_db, sample_create_data):
        """Create generates hash if content_hash is empty."""
        mock_hash.return_value = "generated_hash_123"
        sample_create_data.content_hash = ""

        service.create(sample_create_data, check_duplicate=False)

        mock_hash.assert_called_once_with(sample_create_data.markdown_content)
        mock_db.add.assert_called_once()

    def test_create_uses_provided_hash(self, service, mock_db, sample_create_data):
        """Create uses provided hash if not empty."""
        service.create(sample_create_data, check_duplicate=False)

        # Verify the content was added
        mock_db.add.assert_called_once()
        added_content = mock_db.add.call_args[0][0]
        assert added_content.content_hash == "hash123"

    def test_create_checks_duplicate_when_enabled(self, service, mock_db, sample_create_data):
        """Create checks for duplicates when check_duplicate=True."""
        # Mock find_by_hash to return an existing content
        existing = MagicMock()
        existing.id = 99

        with patch.object(service, "find_by_hash", return_value=existing):
            service.create(sample_create_data, check_duplicate=True)

        # Verify canonical_id is set
        added_content = mock_db.add.call_args[0][0]
        assert added_content.canonical_id == 99

    def test_create_no_canonical_when_no_duplicate(self, service, mock_db, sample_create_data):
        """Create sets canonical_id to None when no duplicate found."""
        with patch.object(service, "find_by_hash", return_value=None):
            service.create(sample_create_data, check_duplicate=True)

        added_content = mock_db.add.call_args[0][0]
        assert added_content.canonical_id is None


class TestContentServiceGet:
    """Tests for ContentService.get method."""

    def test_get_returns_content(self, service, mock_db, sample_content):
        """Get returns content by ID."""
        mock_db.get.return_value = sample_content

        result = service.get(1)

        mock_db.get.assert_called_once_with(Content, 1)
        assert result == sample_content

    def test_get_returns_none_for_missing(self, service, mock_db):
        """Get returns None when content not found."""
        mock_db.get.return_value = None

        result = service.get(999)

        assert result is None


class TestContentServiceGetBySource:
    """Tests for ContentService.get_by_source method."""

    def test_get_by_source_returns_content(self, service, mock_db, sample_content):
        """Get by source returns matching content."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_content
        mock_db.execute.return_value = mock_result

        result = service.get_by_source(ContentSource.GMAIL, "msg-12345")

        assert result == sample_content

    def test_get_by_source_returns_none_for_missing(self, service, mock_db):
        """Get by source returns None when not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = service.get_by_source(ContentSource.RSS, "unknown")

        assert result is None


class TestContentServiceFindByHash:
    """Tests for ContentService.find_by_hash method."""

    def test_find_by_hash_returns_canonical(self, service, mock_db, sample_content):
        """Find by hash returns canonical content."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_content
        mock_db.execute.return_value = mock_result

        result = service.find_by_hash("abc123def456")

        assert result == sample_content


class TestContentServiceUpdate:
    """Tests for ContentService.update method."""

    def test_update_returns_none_when_not_found(self, service, mock_db):
        """Update returns None when content not found."""
        mock_db.get.return_value = None

        result = service.update(999, ContentUpdate(title="New Title"))

        assert result is None

    def test_update_modifies_fields(self, service, mock_db, sample_content):
        """Update modifies specified fields."""
        mock_db.get.return_value = sample_content

        update_data = ContentUpdate(title="Updated Title", author="New Author")
        service.update(1, update_data)

        assert sample_content.title == "Updated Title"
        assert sample_content.author == "New Author"
        mock_db.commit.assert_called_once()

    @patch("src.services.content_service.generate_markdown_hash")
    def test_update_recalculates_hash_on_content_change(
        self, mock_hash, service, mock_db, sample_content
    ):
        """Update recalculates hash when markdown_content changes."""
        mock_db.get.return_value = sample_content
        mock_hash.return_value = "new_hash_456"

        update_data = ContentUpdate(markdown_content="# New Content")
        service.update(1, update_data)

        mock_hash.assert_called_once()
        assert sample_content.content_hash == "new_hash_456"


class TestContentServiceDelete:
    """Tests for ContentService.delete method."""

    def test_delete_returns_false_when_not_found(self, service, mock_db):
        """Delete returns False when content not found."""
        mock_db.get.return_value = None

        result = service.delete(999)

        assert result is False

    def test_delete_returns_true_on_success(self, service, mock_db, sample_content):
        """Delete returns True on successful deletion."""
        mock_db.get.return_value = sample_content
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = service.delete(1)

        assert result is True
        mock_db.delete.assert_called_once_with(sample_content)
        mock_db.commit.assert_called_once()

    def test_delete_unlinks_duplicates(self, service, mock_db, sample_content):
        """Delete unlinks content that references this as canonical."""
        mock_db.get.return_value = sample_content

        # Create mock duplicates
        dup1 = MagicMock()
        dup1.canonical_id = 1
        dup2 = MagicMock()
        dup2.canonical_id = 1

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [dup1, dup2]
        mock_db.execute.return_value = mock_result

        service.delete(1)

        # Verify duplicates were unlinked
        assert dup1.canonical_id is None
        assert dup2.canonical_id is None


class TestContentServiceUpdateStatus:
    """Tests for ContentService.update_status method."""

    def test_update_status_returns_none_when_not_found(self, service, mock_db):
        """Update status returns None when content not found."""
        mock_db.get.return_value = None

        result = service.update_status(999, ContentStatus.COMPLETED)

        assert result is None

    def test_update_status_sets_parsed_at_on_parsed(self, service, mock_db, sample_content):
        """Update status sets parsed_at when status is PARSED."""
        mock_db.get.return_value = sample_content
        sample_content.parsed_at = None

        service.update_status(1, ContentStatus.PARSED)

        assert sample_content.status == ContentStatus.PARSED
        assert sample_content.parsed_at is not None

    def test_update_status_sets_processed_at_on_completed(self, service, mock_db, sample_content):
        """Update status sets processed_at when status is COMPLETED."""
        mock_db.get.return_value = sample_content
        sample_content.processed_at = None

        service.update_status(1, ContentStatus.COMPLETED)

        assert sample_content.status == ContentStatus.COMPLETED
        assert sample_content.processed_at is not None

    def test_update_status_sets_error_message_on_failed(self, service, mock_db, sample_content):
        """Update status sets error message when status is FAILED."""
        mock_db.get.return_value = sample_content

        service.update_status(1, ContentStatus.FAILED, "Parser error")

        assert sample_content.status == ContentStatus.FAILED
        assert sample_content.error_message == "Parser error"


class TestContentServiceMergeDuplicates:
    """Tests for ContentService.merge_duplicates method."""

    def test_merge_returns_none_when_canonical_not_found(self, service, mock_db):
        """Merge returns None when canonical content not found."""
        mock_db.get.side_effect = [None, MagicMock()]

        result = service.merge_duplicates(999, 1)

        assert result is None

    def test_merge_returns_none_when_duplicate_not_found(self, service, mock_db):
        """Merge returns None when duplicate content not found."""
        mock_db.get.side_effect = [MagicMock(), None]

        result = service.merge_duplicates(1, 999)

        assert result is None

    def test_merge_raises_on_self_merge(self, service, mock_db, sample_content):
        """Merge raises ValueError when trying to merge content with itself."""
        mock_db.get.return_value = sample_content

        with pytest.raises(ValueError) as exc_info:
            service.merge_duplicates(1, 1)

        assert "duplicate of itself" in str(exc_info.value)

    def test_merge_sets_canonical_id(self, service, mock_db):
        """Merge sets canonical_id on duplicate content."""
        canonical = MagicMock()
        canonical.id = 1
        duplicate = MagicMock()
        duplicate.id = 2
        duplicate.canonical_id = None

        mock_db.get.side_effect = [canonical, duplicate]

        result = service.merge_duplicates(1, 2)

        assert duplicate.canonical_id == 1
        assert result == duplicate
        mock_db.commit.assert_called_once()
