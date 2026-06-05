"""Tests for the `aca kb` CLI commands.

These tests mock the KnowledgeBaseService at its module-level location
(``src.cli.kb_commands.<service>``) so the CLI's behavior can be verified
without running the underlying service. The DB session is also mocked
out via the ``get_db()`` context manager since CLI tests don't connect
to a real DB.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.app import app


@pytest.fixture
def runner():
    return CliRunner()


@contextmanager
def _fake_db_session():
    yield MagicMock()


# ---------------------------------------------------------------------------
# compile
# ---------------------------------------------------------------------------


class TestKBCompile:
    def test_compile_json_output(self, runner, monkeypatch):
        """kb.7: `aca kb compile --json` returns CompileSummary as JSON."""
        from datetime import UTC, datetime

        from src.services.knowledge_base import CompileSummary

        summary = CompileSummary(
            started_at=datetime(2026, 4, 9, tzinfo=UTC),
            finished_at=datetime(2026, 4, 9, tzinfo=UTC),
            topics_found=2,
            topics_compiled=2,
        )

        mock_service = MagicMock()
        mock_service.compile = AsyncMock(return_value=summary)

        with (
            patch("src.services.knowledge_base.KnowledgeBaseService", return_value=mock_service),
            patch("src.storage.database.get_db", return_value=_fake_db_session()),
        ):
            result = runner.invoke(app, ["--json", "kb", "compile"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["topics_compiled"] == 2

    def test_compile_full_flag(self, runner):
        """kb.7: --full flag invokes compile_full()."""
        from datetime import UTC, datetime

        from src.services.knowledge_base import CompileSummary

        summary = CompileSummary(
            started_at=datetime(2026, 4, 9, tzinfo=UTC),
            finished_at=datetime(2026, 4, 9, tzinfo=UTC),
        )
        mock_service = MagicMock()
        mock_service.compile_full = AsyncMock(return_value=summary)
        mock_service.compile = AsyncMock(return_value=summary)

        with (
            patch("src.services.knowledge_base.KnowledgeBaseService", return_value=mock_service),
            patch("src.storage.database.get_db", return_value=_fake_db_session()),
        ):
            result = runner.invoke(app, ["kb", "compile", "--full"])

        assert result.exit_code == 0, result.output
        mock_service.compile_full.assert_called_once()
        mock_service.compile.assert_not_called()

    def test_compile_concurrency_returns_exit_code_2(self, runner):
        """kb.7: KBCompileLockError → exit code 2."""
        from src.services.knowledge_base import KBCompileLockError

        mock_service = MagicMock()
        mock_service.compile = AsyncMock(side_effect=KBCompileLockError("Compile already running"))

        with (
            patch("src.services.knowledge_base.KnowledgeBaseService", return_value=mock_service),
            patch("src.storage.database.get_db", return_value=_fake_db_session()),
        ):
            result = runner.invoke(app, ["kb", "compile"])

        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# list / show / index
# ---------------------------------------------------------------------------


class TestKBList:
    def test_list_no_topics_json(self, runner):
        """kb.7: empty list returns empty JSON array."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        @contextmanager
        def fake_get_db():
            yield mock_db

        with patch("src.storage.database.get_db", side_effect=fake_get_db):
            result = runner.invoke(app, ["--json", "kb", "list"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["topics"] == []
        assert payload["count"] == 0


class TestKBShow:
    def test_show_topic_not_found(self, runner):
        """kb.7: show with unknown slug exits 1."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        @contextmanager
        def fake_get_db():
            yield mock_db

        with patch("src.storage.database.get_db", side_effect=fake_get_db):
            result = runner.invoke(app, ["kb", "show", "missing-slug"])

        assert result.exit_code == 1


class TestKBIndex:
    def test_index_missing_returns_friendly_message(self, runner):
        """kb.7: missing index doesn't crash."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        @contextmanager
        def fake_get_db():
            yield mock_db

        with patch("src.storage.database.get_db", side_effect=fake_get_db):
            result = runner.invoke(app, ["kb", "index"])

        assert result.exit_code == 0
        assert "No index found" in result.output or result.output == ""


# ---------------------------------------------------------------------------
# HTTP routing under a remote profile
# ---------------------------------------------------------------------------


class TestKBHttpRouting:
    """Under a remote profile, read commands fetch from the prod API instead
    of the local DB (split-brain fix). These patch is_remote_backend True and
    a mock ApiClient.
    """

    @patch("src.cli.kb_commands.is_remote_backend", return_value=True)
    @patch("src.cli.api_client.get_api_client")
    def test_list_routes_to_api(self, mock_get_client, _remote, runner):
        client = MagicMock()
        client.kb_list_topics.return_value = [
            {
                "slug": "rag",
                "name": "RAG",
                "category": "ml",
                "trend": "growing",
                "status": "active",
                "relevance_score": 0.91,
                "mention_count": 7,
                "last_compiled_at": None,
            }
        ]
        mock_get_client.return_value = client

        result = runner.invoke(app, ["--json", "kb", "list"])

        assert result.exit_code == 0, result.output
        client.kb_list_topics.assert_called_once()
        client.close.assert_called_once()
        payload = json.loads(result.output)
        assert payload["count"] == 1
        assert payload["topics"][0]["slug"] == "rag"

    @patch("src.cli.kb_commands.is_remote_backend", return_value=True)
    @patch("src.cli.api_client.get_api_client")
    def test_show_routes_to_api(self, mock_get_client, _remote, runner):
        client = MagicMock()
        client.kb_get_topic.return_value = {
            "slug": "rag",
            "name": "RAG",
            "category": "ml",
            "status": "active",
            "trend": "growing",
            "summary": "s",
            "article_md": "# Body",
            "article_version": 3,
            "relevance_score": 0.9,
            "novelty_score": 0.4,
            "mention_count": 7,
            "source_content_ids": [],
            "related_topic_ids": [],
            "last_compiled_at": None,
        }
        mock_get_client.return_value = client

        result = runner.invoke(app, ["--json", "kb", "show", "rag"])

        assert result.exit_code == 0, result.output
        client.kb_get_topic.assert_called_once_with("rag")
        payload = json.loads(result.output)
        assert payload["article_version"] == 3

    @patch("src.cli.kb_commands.is_remote_backend", return_value=True)
    @patch("src.cli.api_client.get_api_client")
    def test_show_404_exits_1(self, mock_get_client, _remote, runner):
        import httpx

        req = httpx.Request("GET", "http://x/api/v1/kb/topics/missing")
        resp = httpx.Response(404, request=req)
        client = MagicMock()
        client.kb_get_topic.side_effect = httpx.HTTPStatusError("404", request=req, response=resp)
        mock_get_client.return_value = client

        result = runner.invoke(app, ["kb", "show", "missing"])

        assert result.exit_code == 1
        assert "Topic not found" in result.output

    @patch("src.cli.kb_commands.is_remote_backend", return_value=True)
    @patch("src.cli.api_client.get_api_client")
    def test_index_routes_to_api(self, mock_get_client, _remote, runner):
        client = MagicMock()
        client.kb_index.return_value = {
            "index_type": "master",
            "content": "# KB Index",
            "generated_at": None,
        }
        mock_get_client.return_value = client

        result = runner.invoke(app, ["kb", "index"])

        assert result.exit_code == 0, result.output
        client.kb_index.assert_called_once_with(None)
        assert "# KB Index" in result.output

    @patch("src.cli.kb_commands.is_remote_backend", return_value=True)
    @patch("src.cli.api_client.get_api_client")
    def test_query_routes_to_api(self, mock_get_client, _remote, runner):
        client = MagicMock()
        client.kb_query.return_value = {"answer": "42", "topics": ["rag"], "truncated": False}
        mock_get_client.return_value = client

        result = runner.invoke(app, ["kb", "query", "what is the answer?"])

        assert result.exit_code == 0, result.output
        client.kb_query.assert_called_once_with("what is the answer?", file_back=False)
        assert "42" in result.output

    @patch("src.config.settings.get_settings")
    def test_direct_flag_under_remote_is_refused(self, mock_get_settings, runner):
        # --direct opts out of HTTP; the guard then refuses (no silent local DB).
        # Patch get_settings so both _route_to_api and guard_remote_backend see remote.
        mock_get_settings.return_value = MagicMock(api_base_url="https://api.aca.rotkohl.ai")
        result = runner.invoke(app, ["--direct", "kb", "list"])
        assert result.exit_code == 1
        assert "Refusing to run" in result.output
