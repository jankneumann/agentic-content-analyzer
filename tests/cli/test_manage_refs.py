"""Tests for manage extract-refs and resolve-refs CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


class TestExtractRefs:
    @patch("src.storage.database.get_db")
    @patch("src.services.reference_extractor.ReferenceExtractor")
    def test_extract_refs_dry_run(self, mock_extractor_cls, mock_get_db):
        """Dry run should report found references without storing."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        # Simulate 2 content items, each with 1 reference
        content1 = MagicMock(id=1)
        content2 = MagicMock(id=2)
        mock_db.query.return_value.all.return_value = [content1, content2]

        extractor = MagicMock()
        mock_extractor_cls.return_value = extractor
        ref1 = MagicMock()
        ref2 = MagicMock()
        extractor.extract_from_content.side_effect = [[ref1], [ref2]]

        result = runner.invoke(app, ["manage", "extract-refs", "--dry-run"])

        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "2" in result.output  # 2 references found
        # store_references should NOT be called in dry run
        extractor.store_references.assert_not_called()

    @patch("src.storage.database.get_db")
    @patch("src.services.reference_extractor.ReferenceExtractor")
    def test_extract_refs_stores_references(self, mock_extractor_cls, mock_get_db):
        """Non-dry-run should store references."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        content1 = MagicMock(id=10)
        mock_db.query.return_value.all.return_value = [content1]

        extractor = MagicMock()
        mock_extractor_cls.return_value = extractor
        ref = MagicMock()
        extractor.extract_from_content.return_value = [ref]
        extractor.store_references.return_value = 1

        result = runner.invoke(app, ["manage", "extract-refs"])

        assert result.exit_code == 0
        assert "Extracted 1 references from 1 content items" in result.output
        extractor.store_references.assert_called_once_with(10, [ref], mock_db)

    @patch("src.storage.database.get_db")
    @patch("src.services.reference_extractor.ReferenceExtractor")
    def test_extract_refs_with_after_filter(self, mock_extractor_cls, mock_get_db):
        """--after flag should apply date filter."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        query_mock = MagicMock()
        mock_db.query.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.all.return_value = []

        extractor = MagicMock()
        mock_extractor_cls.return_value = extractor

        result = runner.invoke(app, ["manage", "extract-refs", "--after", "2025-01-01"])

        assert result.exit_code == 0
        # filter() should have been called for the date
        query_mock.filter.assert_called()

    @patch("src.storage.database.get_db")
    @patch("src.services.reference_extractor.ReferenceExtractor")
    def test_extract_refs_with_source_filter(self, mock_extractor_cls, mock_get_db):
        """--source flag should apply source type filter."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        query_mock = MagicMock()
        mock_db.query.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.all.return_value = []

        extractor = MagicMock()
        mock_extractor_cls.return_value = extractor

        result = runner.invoke(app, ["manage", "extract-refs", "--source", "rss"])

        assert result.exit_code == 0
        query_mock.filter.assert_called()

    @patch("src.storage.database.get_db")
    @patch("src.services.reference_extractor.ReferenceExtractor")
    def test_extract_refs_no_refs_found(self, mock_extractor_cls, mock_get_db):
        """When no references are found, should report zero."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        content1 = MagicMock(id=1)
        mock_db.query.return_value.all.return_value = [content1]

        extractor = MagicMock()
        mock_extractor_cls.return_value = extractor
        extractor.extract_from_content.return_value = []

        result = runner.invoke(app, ["manage", "extract-refs"])

        assert result.exit_code == 0
        assert "Extracted 0 references from 1 content items" in result.output


class TestResolveRefs:
    @patch("src.storage.database.get_db")
    @patch("src.services.reference_resolver.ReferenceResolver")
    def test_resolve_refs(self, mock_resolver_cls, mock_get_db):
        """Basic resolve should report count."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        resolver = MagicMock()
        mock_resolver_cls.return_value = resolver
        resolver.resolve_batch.return_value = 5

        result = runner.invoke(app, ["manage", "resolve-refs"])

        assert result.exit_code == 0
        assert "Resolved 5 references" in result.output
        resolver.resolve_batch.assert_called_once_with(100)

    @patch("src.storage.database.get_db")
    @patch("src.services.reference_resolver.ReferenceResolver")
    def test_resolve_refs_with_batch_size(self, mock_resolver_cls, mock_get_db):
        """Custom batch size should be passed through."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        resolver = MagicMock()
        mock_resolver_cls.return_value = resolver
        resolver.resolve_batch.return_value = 3

        result = runner.invoke(app, ["manage", "resolve-refs", "--batch-size", "50"])

        assert result.exit_code == 0
        assert "Resolved 3 references" in result.output
        assert "batch_size=50" in result.output
        resolver.resolve_batch.assert_called_once_with(50)

    @patch("src.storage.database.get_db")
    @patch("src.services.reference_resolver.ReferenceResolver")
    def test_resolve_refs_with_auto_ingest(self, mock_resolver_cls, mock_get_db):
        """--auto-ingest flag should display guidance message."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        resolver = MagicMock()
        mock_resolver_cls.return_value = resolver
        resolver.resolve_batch.return_value = 0

        result = runner.invoke(app, ["manage", "resolve-refs", "--auto-ingest"])

        assert result.exit_code == 0
        assert "Auto-ingest" in result.output

    @patch("src.storage.database.get_db")
    @patch("src.services.reference_resolver.ReferenceResolver")
    def test_resolve_refs_zero_resolved(self, mock_resolver_cls, mock_get_db):
        """When nothing to resolve, should report zero."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        resolver = MagicMock()
        mock_resolver_cls.return_value = resolver
        resolver.resolve_batch.return_value = 0

        result = runner.invoke(app, ["manage", "resolve-refs"])

        assert result.exit_code == 0
        assert "Resolved 0 references" in result.output
