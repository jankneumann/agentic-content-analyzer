"""Tests for remaining CLI commands — HTTP path.

Tests the HTTP (API) code path for review, analyze, podcast, jobs,
settings, and prompt commands by mocking get_api_client at the
source module (src.cli.api_client) since all command modules import
it lazily from there.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Review commands
# ---------------------------------------------------------------------------


class TestReviewListHTTP:
    """Test HTTP path for 'aca review list'."""

    @patch("src.cli.api_client.get_api_client")
    def test_list_calls_client(self, mock_get_client: MagicMock) -> None:
        """review list calls client.list_digests with pending_review status."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.list_digests.return_value = []

        result = runner.invoke(app, ["review", "list"])
        assert result.exit_code == 0
        mock_client.list_digests.assert_called_once_with(status="pending_review")

    @patch("src.cli.api_client.get_api_client")
    def test_list_displays_digests(self, mock_get_client: MagicMock) -> None:
        """review list renders returned digests."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.list_digests.return_value = [
            {
                "id": 1,
                "digest_type": "daily",
                "title": "Test Digest",
                "status": "pending_review",
                "period_start": "2025-01-15",
                "period_end": "2025-01-16",
                "newsletter_count": 5,
                "revision_count": 0,
                "created_at": "2025-01-15 10:00",
            }
        ]

        result = runner.invoke(app, ["review", "list"])
        assert result.exit_code == 0
        assert "Test Digest" in result.output

    @patch("src.cli.review_commands._list_reviews_direct")
    @patch("src.cli.api_client.get_api_client")
    def test_list_fallback_on_connect_error(
        self, mock_get_client: MagicMock, mock_direct: MagicMock
    ) -> None:
        """ConnectError triggers fallback to direct mode."""
        mock_get_client.side_effect = httpx.ConnectError("Connection refused")
        result = runner.invoke(app, ["review", "list"])
        assert result.exit_code == 0
        mock_direct.assert_called_once()


class TestReviewViewHTTP:
    """Test HTTP path for 'aca review view <id>'."""

    @patch("src.cli.api_client.get_api_client")
    def test_view_calls_client(self, mock_get_client: MagicMock) -> None:
        """review view 5 calls client.get_digest(5)."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.get_digest.return_value = {
            "id": 5,
            "digest_type": "daily",
            "title": "View Test",
            "status": "pending_review",
            "period_start": "2025-01-15",
            "period_end": "2025-01-16",
            "newsletter_count": 3,
            "revision_count": 0,
            "created_at": "2025-01-15 10:00",
            "model_used": "claude",
            "markdown_content": "# Test content",
        }

        result = runner.invoke(app, ["review", "view", "5"])
        assert result.exit_code == 0
        mock_client.get_digest.assert_called_once_with(5)


# ---------------------------------------------------------------------------
# Analyze commands
# ---------------------------------------------------------------------------


class TestAnalyzeThemesHTTP:
    """Test HTTP path for 'aca analyze themes'."""

    @patch("src.cli.api_client.get_api_client")
    def test_themes_calls_client(self, mock_get_client: MagicMock) -> None:
        """analyze themes calls client.analyze_themes."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.analyze_themes.return_value = {
            "themes": [
                {
                    "name": "LLM Scaling",
                    "description": "Large model trends",
                    "category": "technology",
                    "trend": "growing",
                    "content_ids": [1, 2, 3],
                    "relevance_score": 0.9,
                }
            ],
            "total_themes": 1,
            "content_count": 10,
        }

        result = runner.invoke(app, ["analyze", "themes"])
        assert result.exit_code == 0
        mock_client.analyze_themes.assert_called_once()
        assert "LLM Scaling" in result.output

    @patch("src.cli.analyze_commands._analyze_themes_direct")
    @patch("src.cli.api_client.get_api_client")
    def test_themes_fallback_on_connect_error(
        self, mock_get_client: MagicMock, mock_direct: MagicMock
    ) -> None:
        """ConnectError triggers fallback to direct mode."""
        mock_get_client.side_effect = httpx.ConnectError("Connection refused")
        result = runner.invoke(app, ["analyze", "themes"])
        # May exit 0 or non-zero depending on direct mock; just check fallback called
        mock_direct.assert_called_once()


# ---------------------------------------------------------------------------
# Podcast commands
# ---------------------------------------------------------------------------


class TestPodcastGenerateHTTP:
    """Test HTTP path for 'aca podcast generate'."""

    @patch("src.cli.api_client.get_api_client")
    def test_generate_calls_client(self, mock_get_client: MagicMock) -> None:
        """podcast generate calls client.generate_podcast with digest_id."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.generate_podcast.return_value = {
            "id": 10,
            "digest_id": 7,
            "title": "AI Podcast #7",
            "length": "standard",
            "word_count": 3000,
            "status": "completed",
        }

        result = runner.invoke(app, ["podcast", "generate", "--digest-id", "7"])
        assert result.exit_code == 0
        mock_client.generate_podcast.assert_called_once_with(digest_id=7)
        assert "Podcast script generated" in result.output


class TestPodcastListScriptsHTTP:
    """Test HTTP path for 'aca podcast list-scripts'."""

    @patch("src.cli.api_client.get_api_client")
    def test_list_scripts_calls_client(self, mock_get_client: MagicMock) -> None:
        """podcast list-scripts calls client.list_scripts."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.list_scripts.return_value = {
            "scripts": [],
            "total": 0,
        }

        result = runner.invoke(app, ["podcast", "list-scripts"])
        assert result.exit_code == 0
        mock_client.list_scripts.assert_called_once()


# ---------------------------------------------------------------------------
# Job commands
# ---------------------------------------------------------------------------


class TestJobsListHTTP:
    """Test HTTP path for 'aca jobs list'."""

    @patch("src.cli.api_client.get_api_client")
    def test_list_calls_client(self, mock_get_client: MagicMock) -> None:
        """jobs list calls client.list_jobs with default params."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.list_jobs.return_value = {
            "jobs": [],
            "total": 0,
        }

        result = runner.invoke(app, ["jobs", "list"])
        assert result.exit_code == 0
        mock_client.list_jobs.assert_called_once_with(limit=20, offset=0)

    @patch("src.cli.api_client.get_api_client")
    def test_list_with_status_filter(self, mock_get_client: MagicMock) -> None:
        """jobs list --status failed passes status param."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.list_jobs.return_value = {"jobs": [], "total": 0}

        result = runner.invoke(app, ["jobs", "list", "--status", "failed"])
        assert result.exit_code == 0
        mock_client.list_jobs.assert_called_once_with(limit=20, offset=0, status="failed")


class TestJobsShowHTTP:
    """Test HTTP path for 'aca jobs show <id>'."""

    @patch("src.cli.api_client.get_api_client")
    def test_show_calls_client(self, mock_get_client: MagicMock) -> None:
        """jobs show 1 calls client.get_job(1)."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.get_job.return_value = {
            "id": 1,
            "entrypoint": "summarize_content",
            "status": "completed",
            "priority": 0,
            "retry_count": 0,
            "progress": 100,
            "created_at": "2025-01-15T10:00:00",
            "payload": {},
        }

        result = runner.invoke(app, ["jobs", "show", "1"])
        assert result.exit_code == 0
        mock_client.get_job.assert_called_once_with(1)

    @patch("src.cli.job_commands._show_job_direct")
    @patch("src.cli.api_client.get_api_client")
    def test_show_fallback_on_connect_error(
        self, mock_get_client: MagicMock, mock_direct: MagicMock
    ) -> None:
        """ConnectError triggers fallback to direct mode."""
        mock_get_client.side_effect = httpx.ConnectError("Connection refused")
        result = runner.invoke(app, ["jobs", "show", "1"])
        assert result.exit_code == 0
        mock_direct.assert_called_once_with(1)


class TestJobsRetryHTTP:
    """Test HTTP path for 'aca jobs retry <id>'."""

    @patch("src.cli.api_client.get_api_client")
    def test_retry_calls_client(self, mock_get_client: MagicMock) -> None:
        """jobs retry 5 calls client.retry_job(5)."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.retry_job.return_value = {"id": 5, "retry_count": 1}

        result = runner.invoke(app, ["jobs", "retry", "5"])
        assert result.exit_code == 0
        mock_client.retry_job.assert_called_once_with(5)


# ---------------------------------------------------------------------------
# Settings commands
# ---------------------------------------------------------------------------


class TestSettingsListHTTP:
    """Test HTTP path for 'aca settings list'."""

    @patch("src.cli.api_client.get_api_client")
    def test_list_calls_client(self, mock_get_client: MagicMock) -> None:
        """settings list calls client.list_settings."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.list_settings.return_value = {
            "overrides": [],
            "count": 0,
        }

        result = runner.invoke(app, ["settings", "list"])
        assert result.exit_code == 0
        mock_client.list_settings.assert_called_once_with()

    @patch("src.cli.api_client.get_api_client")
    def test_list_with_prefix(self, mock_get_client: MagicMock) -> None:
        """settings list --prefix model passes prefix param."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.list_settings.return_value = {
            "overrides": [
                {"key": "model.summarization", "value": "claude-haiku-4-5", "version": 1}
            ],
            "count": 1,
        }

        result = runner.invoke(app, ["settings", "list", "--prefix", "model"])
        assert result.exit_code == 0
        mock_client.list_settings.assert_called_once_with(prefix="model")

    @patch("src.cli.settings_commands._list_settings_direct")
    @patch("src.cli.api_client.get_api_client")
    def test_list_fallback_on_connect_error(
        self, mock_get_client: MagicMock, mock_direct: MagicMock
    ) -> None:
        """ConnectError triggers fallback to direct mode."""
        mock_get_client.side_effect = httpx.ConnectError("Connection refused")
        result = runner.invoke(app, ["settings", "list"])
        assert result.exit_code == 0
        mock_direct.assert_called_once()


class TestSettingsGetHTTP:
    """Test HTTP path for 'aca settings get <key>'."""

    @patch("src.cli.api_client.get_api_client")
    def test_get_calls_client(self, mock_get_client: MagicMock) -> None:
        """settings get model.summarization calls client.get_setting."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.get_setting.return_value = {
            "key": "model.summarization",
            "value": "claude-haiku-4-5",
            "version": 2,
        }

        result = runner.invoke(app, ["settings", "get", "model.summarization"])
        assert result.exit_code == 0
        mock_client.get_setting.assert_called_once_with("model.summarization")


class TestSettingsSetHTTP:
    """Test HTTP path for 'aca settings set <key> <value>'."""

    @patch("src.cli.api_client.get_api_client")
    def test_set_calls_client(self, mock_get_client: MagicMock) -> None:
        """settings set key value calls client.set_setting."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.set_setting.return_value = {
            "key": "model.summarization",
            "value": "claude-sonnet-4-5",
            "version": 3,
        }

        result = runner.invoke(app, ["settings", "set", "model.summarization", "claude-sonnet-4-5"])
        assert result.exit_code == 0
        mock_client.set_setting.assert_called_once_with("model.summarization", "claude-sonnet-4-5")


# ---------------------------------------------------------------------------
# Prompt commands
# ---------------------------------------------------------------------------


class TestPromptsListHTTP:
    """Test HTTP path for 'aca prompts list'."""

    @patch("src.cli.api_client.get_api_client")
    def test_list_calls_client(self, mock_get_client: MagicMock) -> None:
        """prompts list calls client.list_prompts."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.list_prompts.return_value = {
            "prompts": [],
            "count": 0,
        }

        result = runner.invoke(app, ["prompts", "list"])
        assert result.exit_code == 0
        mock_client.list_prompts.assert_called_once_with()

    @patch("src.cli.api_client.get_api_client")
    def test_list_with_category(self, mock_get_client: MagicMock) -> None:
        """prompts list --category pipeline passes category param."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.list_prompts.return_value = {"prompts": [], "count": 0}

        result = runner.invoke(app, ["prompts", "list", "--category", "pipeline"])
        assert result.exit_code == 0
        mock_client.list_prompts.assert_called_once_with(category="pipeline")

    @patch("src.cli.prompt_commands._list_prompts_direct")
    @patch("src.cli.api_client.get_api_client")
    def test_list_fallback_on_connect_error(
        self, mock_get_client: MagicMock, mock_direct: MagicMock
    ) -> None:
        """ConnectError triggers fallback to direct mode."""
        mock_get_client.side_effect = httpx.ConnectError("Connection refused")
        result = runner.invoke(app, ["prompts", "list"])
        assert result.exit_code == 0
        mock_direct.assert_called_once()


class TestPromptsShowHTTP:
    """Test HTTP path for 'aca prompts show <key>'."""

    @patch("src.cli.api_client.get_api_client")
    def test_show_calls_client(self, mock_get_client: MagicMock) -> None:
        """prompts show calls client.get_prompt."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.get_prompt.return_value = {
            "key": "pipeline.summarization.system",
            "has_override": False,
            "default_value": "You are a summarizer.",
            "override_value": None,
        }

        result = runner.invoke(app, ["prompts", "show", "pipeline.summarization.system"])
        assert result.exit_code == 0
        mock_client.get_prompt.assert_called_once_with("pipeline.summarization.system")


class TestPromptsSetHTTP:
    """Test HTTP path for 'aca prompts set <key> --value <val>'."""

    @patch("src.cli.api_client.get_api_client")
    def test_set_calls_client(self, mock_get_client: MagicMock) -> None:
        """prompts set calls client.set_prompt."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.set_prompt.return_value = {
            "key": "pipeline.summarization.system",
            "has_override": True,
            "version": 1,
        }

        result = runner.invoke(
            app,
            ["prompts", "set", "pipeline.summarization.system", "--value", "New prompt"],
        )
        assert result.exit_code == 0
        mock_client.set_prompt.assert_called_once_with(
            "pipeline.summarization.system", "New prompt"
        )


class TestPromptsResetHTTP:
    """Test HTTP path for 'aca prompts reset <key>'."""

    @patch("src.cli.api_client.get_api_client")
    def test_reset_calls_client(self, mock_get_client: MagicMock) -> None:
        """prompts reset calls client.reset_prompt."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["prompts", "reset", "pipeline.summarization.system"])
        assert result.exit_code == 0
        mock_client.reset_prompt.assert_called_once_with("pipeline.summarization.system")
