"""Tests for `aca curate` CLI commands, focused on the youtube-rss extension.

The health-check/plan/apply engine itself is covered in
tests/services/test_source_curator.py; here we verify the CLI wiring: that
``curate youtube-rss`` loads YouTube sources, drives the shared engine, and
writes (only) under --apply.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import yaml
from typer.testing import CliRunner

from src.cli.app import app
from src.config.sources import SourcesConfig, YouTubeRSSSource
from src.services.source_curator import FeedHealth, FeedStatus

runner = CliRunner()

_DEAD = "https://www.youtube.com/feeds/videos.xml?channel_id=UCdeadchannel000000000"
_LIVE = "https://www.youtube.com/feeds/videos.xml?channel_id=UClivechannel000000000"


def _yt_config() -> SourcesConfig:
    return SourcesConfig(
        sources=[
            YouTubeRSSSource(name="Dead Channel", url=_DEAD),
            YouTubeRSSSource(name="Live Channel", url=_LIVE),
        ]
    )


def _write_yt_file(path):
    path.write_text(
        "defaults:\n"
        "  type: youtube_rss\n"
        "sources:\n"
        f"- name: Dead Channel\n  url: {_DEAD}\n"
        f"- name: Live Channel\n  url: {_LIVE}\n"
    )


def _health_results():
    return [
        FeedHealth(_DEAD, "Dead Channel", FeedStatus.FAIL_HTTP, "404"),
        FeedHealth(_LIVE, "Live Channel", FeedStatus.OK, "12 entries", entry_count=12),
    ]


class TestCurateYoutubeRss:
    @patch("src.services.source_curator.check_rss_feeds", new_callable=AsyncMock)
    @patch("src.cli.curate_commands._load_sources")
    def test_dry_run_reports_without_writing(self, mock_load, mock_check, tmp_path):
        mock_load.return_value = _yt_config()
        mock_check.return_value = _health_results()
        feed_file = tmp_path / "youtube_rss.yaml"
        _write_yt_file(feed_file)
        before = feed_file.read_text()

        result = runner.invoke(app, ["curate", "youtube-rss", "--file", str(feed_file)])

        assert result.exit_code == 0
        assert "Checked 2 channels" in result.output
        assert "Dead Channel" in result.output
        assert "Dry run" in result.output
        # report-only: file untouched
        assert feed_file.read_text() == before

    @patch("src.services.source_curator.check_rss_feeds", new_callable=AsyncMock)
    @patch("src.cli.curate_commands._load_sources")
    def test_apply_disables_dead_channel(self, mock_load, mock_check, tmp_path):
        mock_load.return_value = _yt_config()
        mock_check.return_value = _health_results()
        feed_file = tmp_path / "youtube_rss.yaml"
        _write_yt_file(feed_file)

        result = runner.invoke(
            app, ["curate", "youtube-rss", "--file", str(feed_file), "--apply"]
        )

        assert result.exit_code == 0
        data = {s["url"]: s for s in yaml.safe_load(feed_file.read_text())["sources"]}
        # dead channel disabled in place; live channel left alone
        assert data[_DEAD]["enabled"] is False
        assert "enabled" not in data[_LIVE]

    @patch("src.cli.curate_commands._load_sources")
    def test_no_sources_exits_nonzero(self, mock_load, tmp_path):
        mock_load.return_value = SourcesConfig(sources=[])
        result = runner.invoke(app, ["curate", "youtube-rss"])
        assert result.exit_code == 1
        assert "No YouTube RSS sources found." in result.output


class TestCurateYoutubeRssViaApi:
    @patch("src.services.source_curator.check_youtube_feeds_via_api")
    @patch("src.cli.curate_commands._load_sources")
    def test_via_api_uses_data_api_transport(self, mock_load, mock_api, tmp_path):
        mock_load.return_value = _yt_config()
        mock_api.return_value = _health_results()
        feed_file = tmp_path / "youtube_rss.yaml"
        _write_yt_file(feed_file)

        result = runner.invoke(
            app, ["curate", "youtube-rss", "--file", str(feed_file), "--via-api", "--apply"]
        )

        assert result.exit_code == 0
        assert "via YouTube Data API" in result.output
        mock_api.assert_called_once()
        # the API path drives the same plan/apply engine: dead channel disabled
        data = {s["url"]: s for s in yaml.safe_load(feed_file.read_text())["sources"]}
        assert data[_DEAD]["enabled"] is False

    @patch("src.services.source_curator.check_youtube_feeds_via_api")
    @patch("src.cli.curate_commands._load_sources")
    def test_via_api_missing_credentials_exits(self, mock_load, mock_api, tmp_path):
        mock_load.return_value = _yt_config()
        mock_api.side_effect = RuntimeError("YouTube Data API check needs YOUTUBE_API_KEY")
        feed_file = tmp_path / "youtube_rss.yaml"
        _write_yt_file(feed_file)

        result = runner.invoke(
            app, ["curate", "youtube-rss", "--file", str(feed_file), "--via-api"]
        )

        assert result.exit_code == 1
        assert "YOUTUBE_API_KEY" in result.output
