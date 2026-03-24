"""Tests for the HTTP path of ingest CLI commands.

When --direct is NOT set, each ingest command calls _ingest_via_api() which
delegates to the backend API via httpx. On httpx.ConnectError, commands
auto-fallback to direct mode (_<source>_direct functions).

These tests mock _ingest_via_api to verify each command builds the correct
source name and params dict. Fallback tests mock both _ingest_via_api (raising
ConnectError) and the _<source>_direct function.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Gmail HTTP path
# ---------------------------------------------------------------------------


class TestIngestHttpGmail:
    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_gmail_default_params(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "gmail"])
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "gmail",
            {"query": "label:newsletters-ai", "force_reprocess": False},
            "Gmail ingestion",
        )

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_gmail_with_all_options(self, mock_api: MagicMock) -> None:
        result = runner.invoke(
            app,
            ["ingest", "gmail", "--query", "label:test", "--max", "20", "--days", "7", "--force"],
        )
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "gmail",
            {
                "query": "label:test",
                "force_reprocess": True,
                "max_results": 20,
                "days_back": 7,
            },
            "Gmail ingestion",
        )

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_gmail_max_only(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "gmail", "--max", "5"])
        assert result.exit_code == 0
        params = mock_api.call_args[0][1]
        assert params["max_results"] == 5
        assert "days_back" not in params

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_gmail_days_only(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "gmail", "--days", "3"])
        assert result.exit_code == 0
        params = mock_api.call_args[0][1]
        assert params["days_back"] == 3
        assert "max_results" not in params

    @patch("src.cli.ingest_commands._gmail_direct")
    @patch(
        "src.cli.ingest_commands._ingest_via_api",
        side_effect=httpx.ConnectError("Connection refused"),
    )
    def test_gmail_fallback_on_connect_error(
        self, mock_api: MagicMock, mock_direct: MagicMock
    ) -> None:
        result = runner.invoke(app, ["ingest", "gmail"])
        assert result.exit_code == 0
        mock_direct.assert_called_once()


# ---------------------------------------------------------------------------
# RSS HTTP path
# ---------------------------------------------------------------------------


class TestIngestHttpRss:
    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_rss_default_params(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "rss"])
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "rss",
            {"max_results": 10, "force_reprocess": False},
            "RSS ingestion",
        )

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_rss_with_options(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "rss", "--max", "25", "--days", "14", "--force"])
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "rss",
            {"max_results": 25, "force_reprocess": True, "days_back": 14},
            "RSS ingestion",
        )

    @patch("src.cli.ingest_commands._rss_direct")
    @patch(
        "src.cli.ingest_commands._ingest_via_api",
        side_effect=httpx.ConnectError("Connection refused"),
    )
    def test_rss_fallback_on_connect_error(
        self, mock_api: MagicMock, mock_direct: MagicMock
    ) -> None:
        result = runner.invoke(app, ["ingest", "rss"])
        assert result.exit_code == 0
        mock_direct.assert_called_once()


# ---------------------------------------------------------------------------
# Substack HTTP path
# ---------------------------------------------------------------------------


class TestIngestHttpSubstack:
    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_substack_default_params(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "substack"])
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "substack",
            {"max_results": 10, "force_reprocess": False},
            "Substack ingestion",
        )

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_substack_with_session_cookie(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "substack", "--session-cookie", "abc123"])
        assert result.exit_code == 0
        params = mock_api.call_args[0][1]
        assert params["session_cookie"] == "abc123"

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_substack_with_all_options(self, mock_api: MagicMock) -> None:
        result = runner.invoke(
            app,
            [
                "ingest",
                "substack",
                "--max",
                "15",
                "--days",
                "5",
                "--force",
                "--session-cookie",
                "cookie-val",
            ],
        )
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "substack",
            {
                "max_results": 15,
                "force_reprocess": True,
                "days_back": 5,
                "session_cookie": "cookie-val",
            },
            "Substack ingestion",
        )

    @patch("src.cli.ingest_commands._substack_direct")
    @patch(
        "src.cli.ingest_commands._ingest_via_api",
        side_effect=httpx.ConnectError("Connection refused"),
    )
    def test_substack_fallback_on_connect_error(
        self, mock_api: MagicMock, mock_direct: MagicMock
    ) -> None:
        result = runner.invoke(app, ["ingest", "substack"])
        assert result.exit_code == 0
        mock_direct.assert_called_once()


# ---------------------------------------------------------------------------
# YouTube HTTP path
# ---------------------------------------------------------------------------


class TestIngestHttpYoutube:
    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_youtube_default_params(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "youtube"])
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "youtube",
            {"max_results": 10, "force_reprocess": False},
            "YouTube ingestion",
        )

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_youtube_with_options(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "youtube", "--max", "5", "--days", "3", "--force"])
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "youtube",
            {"max_results": 5, "force_reprocess": True, "days_back": 3},
            "YouTube ingestion",
        )

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_youtube_public_only(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "youtube", "--public-only"])
        assert result.exit_code == 0
        params = mock_api.call_args[0][1]
        assert params["public_only"] is True

    @patch("src.cli.ingest_commands._youtube_direct")
    @patch(
        "src.cli.ingest_commands._ingest_via_api",
        side_effect=httpx.ConnectError("Connection refused"),
    )
    def test_youtube_fallback_on_connect_error(
        self, mock_api: MagicMock, mock_direct: MagicMock
    ) -> None:
        result = runner.invoke(app, ["ingest", "youtube"])
        assert result.exit_code == 0
        mock_direct.assert_called_once()


# ---------------------------------------------------------------------------
# YouTube Playlist HTTP path
# ---------------------------------------------------------------------------


class TestIngestHttpYoutubePlaylist:
    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_youtube_playlist_default_params(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "youtube-playlist"])
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "youtube-playlist",
            {"max_results": 10, "force_reprocess": False},
            "YouTube playlist ingestion",
        )

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_youtube_playlist_with_options(self, mock_api: MagicMock) -> None:
        result = runner.invoke(
            app,
            ["ingest", "youtube-playlist", "--max", "3", "--days", "7", "--force"],
        )
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "youtube-playlist",
            {"max_results": 3, "force_reprocess": True, "days_back": 7},
            "YouTube playlist ingestion",
        )

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_youtube_playlist_public_only(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "youtube-playlist", "--public-only"])
        assert result.exit_code == 0
        params = mock_api.call_args[0][1]
        assert params["public_only"] is True

    @patch("src.cli.ingest_commands._youtube_direct")
    @patch(
        "src.cli.ingest_commands._ingest_via_api",
        side_effect=httpx.ConnectError("Connection refused"),
    )
    def test_youtube_playlist_fallback_on_connect_error(
        self, mock_api: MagicMock, mock_direct: MagicMock
    ) -> None:
        result = runner.invoke(app, ["ingest", "youtube-playlist"])
        assert result.exit_code == 0
        mock_direct.assert_called_once()


# ---------------------------------------------------------------------------
# YouTube RSS HTTP path
# ---------------------------------------------------------------------------


class TestIngestHttpYoutubeRss:
    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_youtube_rss_default_params(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "youtube-rss"])
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "youtube-rss",
            {"max_results": 10, "force_reprocess": False},
            "YouTube RSS ingestion",
        )

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_youtube_rss_with_options(self, mock_api: MagicMock) -> None:
        result = runner.invoke(
            app, ["ingest", "youtube-rss", "--max", "8", "--days", "2", "--force"]
        )
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "youtube-rss",
            {"max_results": 8, "force_reprocess": True, "days_back": 2},
            "YouTube RSS ingestion",
        )

    @patch("src.cli.ingest_commands._youtube_direct")
    @patch(
        "src.cli.ingest_commands._ingest_via_api",
        side_effect=httpx.ConnectError("Connection refused"),
    )
    def test_youtube_rss_fallback_on_connect_error(
        self, mock_api: MagicMock, mock_direct: MagicMock
    ) -> None:
        result = runner.invoke(app, ["ingest", "youtube-rss"])
        assert result.exit_code == 0
        mock_direct.assert_called_once()


# ---------------------------------------------------------------------------
# Podcast HTTP path
# ---------------------------------------------------------------------------


class TestIngestHttpPodcast:
    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_podcast_default_params(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "podcast"])
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "podcast",
            {"max_results": 10, "force_reprocess": False},
            "Podcast ingestion",
        )

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_podcast_with_options(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "podcast", "--max", "5", "--days", "7", "--force"])
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "podcast",
            {"max_results": 5, "force_reprocess": True, "days_back": 7},
            "Podcast ingestion",
        )

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_podcast_no_transcribe(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "podcast", "--no-transcribe"])
        assert result.exit_code == 0
        params = mock_api.call_args[0][1]
        assert params["transcribe"] is False

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_podcast_transcribe_default_not_in_params(self, mock_api: MagicMock) -> None:
        """When --transcribe (default), the transcribe key is NOT sent in params."""
        result = runner.invoke(app, ["ingest", "podcast"])
        assert result.exit_code == 0
        params = mock_api.call_args[0][1]
        assert "transcribe" not in params

    @patch("src.cli.ingest_commands._podcast_direct")
    @patch(
        "src.cli.ingest_commands._ingest_via_api",
        side_effect=httpx.ConnectError("Connection refused"),
    )
    def test_podcast_fallback_on_connect_error(
        self, mock_api: MagicMock, mock_direct: MagicMock
    ) -> None:
        result = runner.invoke(app, ["ingest", "podcast"])
        assert result.exit_code == 0
        mock_direct.assert_called_once()


# ---------------------------------------------------------------------------
# X Search HTTP path
# ---------------------------------------------------------------------------


class TestIngestHttpXsearch:
    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_xsearch_default_params(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "xsearch"])
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "xsearch",
            {"force_reprocess": False},
            "X search ingestion",
        )

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_xsearch_with_prompt(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "xsearch", "--prompt", "AI agents 2026"])
        assert result.exit_code == 0
        params = mock_api.call_args[0][1]
        assert params["prompt"] == "AI agents 2026"

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_xsearch_with_max_threads(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "xsearch", "--max-threads", "15"])
        assert result.exit_code == 0
        params = mock_api.call_args[0][1]
        assert params["max_threads"] == 15

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_xsearch_with_all_options(self, mock_api: MagicMock) -> None:
        result = runner.invoke(
            app,
            ["ingest", "xsearch", "--prompt", "LLM news", "--max-threads", "10", "--force"],
        )
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "xsearch",
            {"force_reprocess": True, "prompt": "LLM news", "max_threads": 10},
            "X search ingestion",
        )

    @patch("src.cli.ingest_commands._xsearch_direct")
    @patch(
        "src.cli.ingest_commands._ingest_via_api",
        side_effect=httpx.ConnectError("Connection refused"),
    )
    def test_xsearch_fallback_on_connect_error(
        self, mock_api: MagicMock, mock_direct: MagicMock
    ) -> None:
        result = runner.invoke(app, ["ingest", "xsearch"])
        assert result.exit_code == 0
        mock_direct.assert_called_once()


# ---------------------------------------------------------------------------
# Perplexity Search HTTP path
# ---------------------------------------------------------------------------


class TestIngestHttpPerplexitySearch:
    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_perplexity_default_params(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "perplexity-search"])
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "perplexity",
            {"force_reprocess": False},
            "Perplexity search ingestion",
        )

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_perplexity_with_prompt(self, mock_api: MagicMock) -> None:
        result = runner.invoke(
            app, ["ingest", "perplexity-search", "--prompt", "latest AI breakthroughs"]
        )
        assert result.exit_code == 0
        params = mock_api.call_args[0][1]
        assert params["prompt"] == "latest AI breakthroughs"

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_perplexity_with_max_results(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "perplexity-search", "--max-results", "20"])
        assert result.exit_code == 0
        params = mock_api.call_args[0][1]
        assert params["max_results"] == 20

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_perplexity_with_recency_filter(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "perplexity-search", "--recency", "week"])
        assert result.exit_code == 0
        params = mock_api.call_args[0][1]
        assert params["recency_filter"] == "week"

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_perplexity_with_context_size(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "perplexity-search", "--context-size", "high"])
        assert result.exit_code == 0
        params = mock_api.call_args[0][1]
        assert params["context_size"] == "high"

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_perplexity_with_all_options(self, mock_api: MagicMock) -> None:
        result = runner.invoke(
            app,
            [
                "ingest",
                "perplexity-search",
                "--prompt",
                "transformer architectures",
                "--max-results",
                "15",
                "--force",
                "--recency",
                "month",
                "--context-size",
                "medium",
            ],
        )
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "perplexity",
            {
                "force_reprocess": True,
                "prompt": "transformer architectures",
                "max_results": 15,
                "recency_filter": "month",
                "context_size": "medium",
            },
            "Perplexity search ingestion",
        )

    @patch("src.cli.ingest_commands._perplexity_direct")
    @patch(
        "src.cli.ingest_commands._ingest_via_api",
        side_effect=httpx.ConnectError("Connection refused"),
    )
    def test_perplexity_fallback_on_connect_error(
        self, mock_api: MagicMock, mock_direct: MagicMock
    ) -> None:
        result = runner.invoke(app, ["ingest", "perplexity-search"])
        assert result.exit_code == 0
        mock_direct.assert_called_once()


# ---------------------------------------------------------------------------
# URL HTTP path
# ---------------------------------------------------------------------------


class TestIngestHttpUrl:
    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_url_minimal(self, mock_api: MagicMock) -> None:
        result = runner.invoke(app, ["ingest", "url", "https://example.com/article"])
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "url",
            {"url": "https://example.com/article"},
            "URL ingestion",
        )

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_url_with_title(self, mock_api: MagicMock) -> None:
        result = runner.invoke(
            app,
            ["ingest", "url", "https://example.com/post", "--title", "My Article"],
        )
        assert result.exit_code == 0
        params = mock_api.call_args[0][1]
        assert params["url"] == "https://example.com/post"
        assert params["title"] == "My Article"

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_url_with_tags(self, mock_api: MagicMock) -> None:
        result = runner.invoke(
            app,
            ["ingest", "url", "https://example.com", "--tag", "ai", "--tag", "news"],
        )
        assert result.exit_code == 0
        params = mock_api.call_args[0][1]
        assert params["tags"] == ["ai", "news"]

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_url_with_notes(self, mock_api: MagicMock) -> None:
        result = runner.invoke(
            app,
            ["ingest", "url", "https://example.com", "--notes", "Worth reviewing"],
        )
        assert result.exit_code == 0
        params = mock_api.call_args[0][1]
        assert params["notes"] == "Worth reviewing"

    @patch("src.cli.ingest_commands._ingest_via_api")
    def test_url_with_all_options(self, mock_api: MagicMock) -> None:
        result = runner.invoke(
            app,
            [
                "ingest",
                "url",
                "https://example.com/full",
                "--title",
                "Full Test",
                "--tag",
                "test",
                "--notes",
                "Testing all params",
            ],
        )
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            "url",
            {
                "url": "https://example.com/full",
                "title": "Full Test",
                "tags": ["test"],
                "notes": "Testing all params",
            },
            "URL ingestion",
        )

    @patch("src.cli.ingest_commands._url_direct")
    @patch(
        "src.cli.ingest_commands._ingest_via_api",
        side_effect=httpx.ConnectError("Connection refused"),
    )
    def test_url_fallback_on_connect_error(
        self, mock_api: MagicMock, mock_direct: MagicMock
    ) -> None:
        result = runner.invoke(app, ["ingest", "url", "https://example.com/fallback"])
        assert result.exit_code == 0
        mock_direct.assert_called_once()


# ---------------------------------------------------------------------------
# Fallback tests with argument verification
# ---------------------------------------------------------------------------


class TestIngestHttpFallbackArgs:
    """Verify that fallback to direct mode passes the correct arguments."""

    @patch("src.cli.ingest_commands._gmail_direct")
    @patch(
        "src.cli.ingest_commands._ingest_via_api",
        side_effect=httpx.ConnectError("Connection refused"),
    )
    def test_gmail_fallback_passes_args(self, mock_api: MagicMock, mock_direct: MagicMock) -> None:
        runner.invoke(
            app,
            ["ingest", "gmail", "--query", "label:test", "--max", "5", "--force"],
        )
        mock_direct.assert_called_once()
        args = mock_direct.call_args
        assert args[0][0] == "label:test"  # query
        assert args[0][1] == 5  # max_results
        assert args[0][3] is True  # force

    @patch("src.cli.ingest_commands._rss_direct")
    @patch(
        "src.cli.ingest_commands._ingest_via_api",
        side_effect=httpx.ConnectError("Connection refused"),
    )
    def test_rss_fallback_passes_args(self, mock_api: MagicMock, mock_direct: MagicMock) -> None:
        runner.invoke(app, ["ingest", "rss", "--max", "25", "--force"])
        mock_direct.assert_called_once()
        args = mock_direct.call_args
        assert args[0][0] == 25  # max_results
        assert args[0][2] is True  # force

    @patch("src.cli.ingest_commands._url_direct")
    @patch(
        "src.cli.ingest_commands._ingest_via_api",
        side_effect=httpx.ConnectError("Connection refused"),
    )
    def test_url_fallback_passes_args(self, mock_api: MagicMock, mock_direct: MagicMock) -> None:
        runner.invoke(
            app,
            [
                "ingest",
                "url",
                "https://example.com",
                "--title",
                "Test",
                "--tag",
                "ai",
                "--notes",
                "Note",
            ],
        )
        mock_direct.assert_called_once_with("https://example.com", "Test", ["ai"], "Note")

    @patch("src.cli.ingest_commands._xsearch_direct")
    @patch(
        "src.cli.ingest_commands._ingest_via_api",
        side_effect=httpx.ConnectError("Connection refused"),
    )
    def test_xsearch_fallback_passes_args(
        self, mock_api: MagicMock, mock_direct: MagicMock
    ) -> None:
        runner.invoke(
            app,
            ["ingest", "xsearch", "--prompt", "AI news", "--max-threads", "10", "--force"],
        )
        mock_direct.assert_called_once_with("AI news", 10, True)

    @patch("src.cli.ingest_commands._perplexity_direct")
    @patch(
        "src.cli.ingest_commands._ingest_via_api",
        side_effect=httpx.ConnectError("Connection refused"),
    )
    def test_perplexity_fallback_passes_args(
        self, mock_api: MagicMock, mock_direct: MagicMock
    ) -> None:
        runner.invoke(
            app,
            [
                "ingest",
                "perplexity-search",
                "--prompt",
                "LLMs",
                "--max-results",
                "20",
                "--force",
                "--recency",
                "week",
                "--context-size",
                "high",
            ],
        )
        mock_direct.assert_called_once_with("LLMs", 20, True, "week", "high")
