"""Tests for graph CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


class TestExtractEntities:
    @patch("src.cli.adapters.run_async")
    @patch("src.storage.graphiti_client.GraphitiClient")
    @patch("src.storage.database.get_db")
    def test_extract_success(self, mock_get_db, mock_graphiti_cls, mock_run_async):
        mock_content = MagicMock()
        mock_content.id = 42
        mock_content.title = "Test Article"

        mock_summary = MagicMock()
        mock_summary.id = 10

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_content
        # Second query call for summary
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            mock_summary
        )
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        mock_client = MagicMock()
        mock_graphiti_cls.return_value = mock_client
        mock_run_async.return_value = None

        result = runner.invoke(app, ["graph", "extract-entities", "--content-id", "42"])
        assert result.exit_code == 0
        assert "Successfully extracted" in result.output or "Test Article" in result.output

    @patch("src.storage.database.get_db")
    def test_extract_content_not_found(self, mock_get_db):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = runner.invoke(app, ["graph", "extract-entities", "--content-id", "999"])
        assert result.exit_code == 1
        assert "not found" in result.output

    @patch("src.storage.database.get_db")
    def test_extract_no_summary(self, mock_get_db):
        mock_content = MagicMock()
        mock_content.id = 42

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_content
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            None
        )
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = runner.invoke(app, ["graph", "extract-entities", "--content-id", "42"])
        assert result.exit_code == 1
        assert "No summary found" in result.output


class TestGraphQuery:
    @patch("src.cli.adapters.search_graph_sync")
    def test_query_success(self, mock_search):
        mock_search.return_value = [
            {"name": "RAG", "type": "concept", "content": "Retrieval-Augmented Generation"},
            {"name": "LLM", "type": "concept", "content": "Large Language Model"},
        ]

        result = runner.invoke(app, ["graph", "query", "--query", "RAG architecture"])
        assert result.exit_code == 0
        assert "2" in result.output

    @patch("src.cli.adapters.search_graph_sync")
    def test_query_no_results(self, mock_search):
        mock_search.return_value = []

        result = runner.invoke(app, ["graph", "query", "--query", "nonexistent"])
        assert result.exit_code == 0
        assert "No results found" in result.output

    @patch("src.cli.adapters.search_graph_sync")
    def test_query_connection_error(self, mock_search):
        mock_search.side_effect = ConnectionError("Neo4j unavailable")

        result = runner.invoke(app, ["graph", "query", "--query", "test"])
        assert result.exit_code == 1
        assert "unavailable" in result.output

    @patch("src.cli.adapters.search_graph_sync")
    def test_query_with_limit(self, mock_search):
        mock_search.return_value = [{"name": "Test", "type": "entity", "content": "details"}]

        result = runner.invoke(app, ["graph", "query", "--query", "test", "--limit", "5"])
        assert result.exit_code == 0
        mock_search.assert_called_once_with("test", limit=5)
