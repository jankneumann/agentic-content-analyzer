"""Tests for ingest CLI commands.

After the orchestrator refactor, CLI commands delegate to orchestrator functions.
Tests mock at `src.ingestion.orchestrator.<func>` instead of individual service classes.
"""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


def _gmail_envelope(items: int):
    """Build a gmail IngestionResponse mock — see post-round-4 docstring above."""
    from src.ingestion.result import IngestionResponse

    return IngestionResponse(
        command="ingest.gmail",
        source="gmail",
        status="ok",
        items_ingested=items,
    )


class TestIngestGmail:
    """Post-round-4 (2026-05-08): ingest_gmail returns ``IngestionResponse``;
    mocks must mimic that shape — returning a bare int would mask production
    bugs where the consumer treats a Pydantic model as if it were an int.
    """

    @patch("src.ingestion.orchestrator.ingest_gmail")
    def test_gmail_success(self, mock_ingest):
        mock_ingest.return_value = _gmail_envelope(5)

        result = runner.invoke(app, ["--direct", "ingest", "gmail"])
        assert result.exit_code == 0
        assert "5" in result.output
        assert "Gmail ingestion complete" in result.output

    @patch("src.ingestion.orchestrator.ingest_gmail")
    def test_gmail_with_options(self, mock_ingest):
        mock_ingest.return_value = _gmail_envelope(3)

        result = runner.invoke(
            app,
            [
                "ingest",
                "gmail",
                "--query",
                "label:test",
                "--max",
                "5",
                "--days",
                "7",
                "--force",
            ],
        )
        assert result.exit_code == 0
        mock_ingest.assert_called_once()
        call_kwargs = mock_ingest.call_args[1]
        assert call_kwargs["query"] == "label:test"
        assert call_kwargs["max_results"] == 5
        assert call_kwargs["after_date"] is not None
        assert call_kwargs["force_reprocess"] is True

    @patch("src.ingestion.orchestrator.ingest_gmail")
    def test_gmail_failure(self, mock_ingest):
        mock_ingest.side_effect = RuntimeError("Auth failed")

        result = runner.invoke(app, ["--direct", "ingest", "gmail"])
        assert result.exit_code == 1
        assert "Gmail ingestion failed" in result.output

    @patch("src.ingestion.orchestrator.ingest_gmail")
    def test_gmail_json_mode(self, mock_ingest):
        mock_ingest.return_value = _gmail_envelope(2)

        result = runner.invoke(app, ["--json", "--direct", "ingest", "gmail"])
        assert result.exit_code == 0
        assert '"source": "gmail"' in result.output
        assert '"items_ingested": 2' in result.output
        assert '"status": "ok"' in result.output


class TestIngestRss:
    @patch("src.ingestion.orchestrator.ingest_rss")
    def test_rss_success(self, mock_ingest):
        from src.ingestion.result import IngestionResponse

        mock_ingest.return_value = IngestionResponse(
            command="ingest.rss",
            source="rss",
            status="ok",
            items_ingested=10,
        )

        result = runner.invoke(app, ["--direct", "ingest", "rss"])
        assert result.exit_code == 0
        assert "10" in result.output
        assert "RSS ingestion complete" in result.output

    @patch("src.ingestion.orchestrator.ingest_rss")
    def test_rss_failure(self, mock_ingest):
        mock_ingest.side_effect = ConnectionError("Network error")

        result = runner.invoke(app, ["--direct", "ingest", "rss"])
        assert result.exit_code == 1
        assert "RSS ingestion failed" in result.output

    @patch("src.ingestion.orchestrator.ingest_rss")
    def test_rss_consumes_response_envelope(self, mock_ingest):
        """CLI surfaces warnings from the IngestionResponse return value.

        Replaces the legacy ``on_result`` callback wiring: now that
        ``ingest_rss`` returns ``IngestionResponse`` directly, the CLI consumes
        the return value and renders warnings/errors from it. Asserting the
        warning content surfaces in stdout proves the envelope was actually
        traversed, not just the count extracted.
        """
        from src.ingestion.result import IngestionResponse, IngestionWarning

        mock_ingest.return_value = IngestionResponse(
            command="ingest.rss",
            source="rss",
            status="ok",
            items_ingested=5,
            warnings=[
                IngestionWarning(
                    code="feed_redirected",
                    message="redirected",
                    url="https://example.com/feed",
                    redirected_to="https://example.com/new-feed",
                )
            ],
        )

        result = runner.invoke(app, ["--direct", "ingest", "rss"])
        assert result.exit_code == 0
        assert "https://example.com/new-feed" in result.output


def _yt_envelope(command: str, source: str, n: int):
    """Helper: build a minimal IngestionResponse for YouTube CLI mocks.

    Mocks for the migrated youtube orchestrator entry points MUST return
    real ``IngestionResponse`` instances — returning ints worked before
    the migration but now masks production bugs where the CLI consumer
    treats a Pydantic model like an int.
    """
    from src.ingestion.result import IngestionResponse

    return IngestionResponse(
        command=command,
        source=source,
        status="ok",
        items_ingested=n,
    )


class TestIngestYoutube:
    @patch("src.ingestion.orchestrator.ingest_youtube")
    def test_youtube_success(self, mock_ingest):
        mock_ingest.return_value = _yt_envelope("ingest.youtube", "youtube", 6)

        result = runner.invoke(app, ["--direct", "ingest", "youtube"])
        assert result.exit_code == 0
        assert "6" in result.output
        assert "YouTube ingestion complete" in result.output

    @patch("src.ingestion.orchestrator.ingest_youtube")
    def test_youtube_public_only(self, mock_ingest):
        mock_ingest.return_value = _yt_envelope("ingest.youtube", "youtube", 1)

        result = runner.invoke(app, ["--direct", "ingest", "youtube", "--public-only"])
        assert result.exit_code == 0
        call_kwargs = mock_ingest.call_args[1]
        assert call_kwargs["use_oauth"] is False

    @patch("src.ingestion.orchestrator.ingest_youtube")
    def test_youtube_failure(self, mock_ingest):
        mock_ingest.side_effect = RuntimeError("API error")

        result = runner.invoke(app, ["--direct", "ingest", "youtube"])
        assert result.exit_code == 1
        assert "YouTube ingestion failed" in result.output


class TestIngestYoutubePlaylist:
    @patch("src.ingestion.orchestrator.ingest_youtube_playlist")
    def test_youtube_playlist_success(self, mock_ingest):
        mock_ingest.return_value = _yt_envelope("ingest.youtube-playlist", "youtube-playlist", 3)

        result = runner.invoke(app, ["--direct", "ingest", "youtube-playlist"])
        assert result.exit_code == 0
        assert "3" in result.output
        assert "YouTube playlist ingestion complete" in result.output

    @patch("src.ingestion.orchestrator.ingest_youtube_playlist")
    def test_youtube_playlist_with_options(self, mock_ingest):
        mock_ingest.return_value = _yt_envelope("ingest.youtube-playlist", "youtube-playlist", 2)

        result = runner.invoke(
            app,
            ["ingest", "youtube-playlist", "--max", "5", "--days", "3", "--force"],
        )
        assert result.exit_code == 0
        call_kwargs = mock_ingest.call_args[1]
        assert call_kwargs["max_videos"] == 5
        assert call_kwargs["after_date"] is not None
        assert call_kwargs["force_reprocess"] is True

    @patch("src.ingestion.orchestrator.ingest_youtube_playlist")
    def test_youtube_playlist_public_only(self, mock_ingest):
        mock_ingest.return_value = _yt_envelope("ingest.youtube-playlist", "youtube-playlist", 1)

        result = runner.invoke(app, ["--direct", "ingest", "youtube-playlist", "--public-only"])
        assert result.exit_code == 0
        call_kwargs = mock_ingest.call_args[1]
        assert call_kwargs["use_oauth"] is False

    @patch("src.ingestion.orchestrator.ingest_youtube_playlist")
    def test_youtube_playlist_failure(self, mock_ingest):
        mock_ingest.side_effect = RuntimeError("API error")

        result = runner.invoke(app, ["--direct", "ingest", "youtube-playlist"])
        assert result.exit_code == 1
        assert "YouTube playlist ingestion failed" in result.output

    @patch("src.ingestion.orchestrator.ingest_youtube_playlist")
    def test_youtube_playlist_json_mode(self, mock_ingest):
        mock_ingest.return_value = _yt_envelope("ingest.youtube-playlist", "youtube-playlist", 4)

        result = runner.invoke(app, ["--json", "--direct", "ingest", "youtube-playlist"])
        assert result.exit_code == 0
        assert '"source": "youtube-playlist"' in result.output
        assert '"items_ingested": 4' in result.output


class TestIngestYoutubeRss:
    @patch("src.ingestion.orchestrator.ingest_youtube_rss")
    def test_youtube_rss_success(self, mock_ingest):
        mock_ingest.return_value = _yt_envelope("ingest.youtube-rss", "youtube-rss", 15)

        result = runner.invoke(app, ["--direct", "ingest", "youtube-rss"])
        assert result.exit_code == 0
        assert "15" in result.output
        assert "YouTube RSS ingestion complete" in result.output

    @patch("src.ingestion.orchestrator.ingest_youtube_rss")
    def test_youtube_rss_with_options(self, mock_ingest):
        mock_ingest.return_value = _yt_envelope("ingest.youtube-rss", "youtube-rss", 8)

        result = runner.invoke(
            app,
            ["ingest", "youtube-rss", "--max", "20", "--days", "14", "--force"],
        )
        assert result.exit_code == 0
        call_kwargs = mock_ingest.call_args[1]
        assert call_kwargs["max_videos"] == 20
        assert call_kwargs["force_reprocess"] is True

    @patch("src.ingestion.orchestrator.ingest_youtube_rss")
    def test_youtube_rss_failure(self, mock_ingest):
        mock_ingest.side_effect = RuntimeError("Rate limited")

        result = runner.invoke(app, ["--direct", "ingest", "youtube-rss"])
        assert result.exit_code == 1
        assert "YouTube RSS ingestion failed" in result.output

    @patch("src.ingestion.orchestrator.ingest_youtube_rss")
    def test_youtube_rss_json_mode(self, mock_ingest):
        mock_ingest.return_value = _yt_envelope("ingest.youtube-rss", "youtube-rss", 7)

        result = runner.invoke(app, ["--json", "--direct", "ingest", "youtube-rss"])
        assert result.exit_code == 0
        assert '"source": "youtube-rss"' in result.output
        assert '"items_ingested": 7' in result.output

    @patch("src.ingestion.orchestrator.ingest_youtube_rss")
    def test_youtube_rss_no_public_only_flag(self, mock_ingest):
        """youtube-rss should NOT have a --public-only flag (RSS doesn't use OAuth)."""
        mock_ingest.return_value = _yt_envelope("ingest.youtube-rss", "youtube-rss", 0)

        result = runner.invoke(app, ["--direct", "ingest", "youtube-rss", "--public-only"])
        # Should fail because --public-only is not a valid option for youtube-rss
        assert result.exit_code != 0


def _podcast_envelope(n: int):
    from src.ingestion.result import IngestionResponse

    return IngestionResponse(
        command="ingest.podcast",
        source="podcast",
        status="ok",
        items_ingested=n,
    )


class TestIngestPodcast:
    @patch("src.ingestion.orchestrator.ingest_podcast")
    def test_podcast_success(self, mock_ingest):
        mock_ingest.return_value = _podcast_envelope(4)

        result = runner.invoke(app, ["--direct", "ingest", "podcast"])
        assert result.exit_code == 0
        assert "4" in result.output
        assert "Podcast ingestion complete" in result.output

    @patch("src.ingestion.orchestrator.ingest_podcast")
    def test_podcast_failure(self, mock_ingest):
        mock_ingest.side_effect = RuntimeError("Feed error")

        result = runner.invoke(app, ["--direct", "ingest", "podcast"])
        assert result.exit_code == 1
        assert "Podcast ingestion failed" in result.output


def _files_envelope(*, ingested: int = 0, failed: int = 0, results=None, errors=None):
    """Build a files IngestionResponse mock.

    Mirrors what ``ingest_files`` emits post round-4 harmonization (2026-05-08):
    items_ingested = successful files, items_failed = per-file failures,
    details.results = the per-file metadata the rich-mode CLI renders into a
    summary table.
    """
    from src.ingestion.result import IngestionResponse

    if ingested > 0 and failed > 0:
        status = "partial"
    elif ingested > 0:
        status = "ok"
    elif failed > 0:
        status = "error"
    else:
        status = "ok"

    return IngestionResponse(
        command="ingest.files",
        source="files",
        status=status,
        items_ingested=ingested,
        items_failed=failed,
        errors=errors or [],
        details={"results": results or []},
    )


class TestIngestFiles:
    """Post-round-4: the per-file loop moved into the orchestrator. Tests now
    mock ``src.ingestion.orchestrator.ingest_files`` (matching the post-#147
    pattern); the previous mocks at ``src.cli.adapters.ingest_file_sync`` no
    longer intercept since the CLI delegates to the orchestrator.
    """

    @patch("src.ingestion.orchestrator.ingest_files")
    def test_files_success(self, mock_ingest, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        mock_ingest.return_value = _files_envelope(
            ingested=1,
            results=[{"path": str(test_file), "content_id": 42, "title": "Test File"}],
        )

        result = runner.invoke(app, ["--direct", "ingest", "files", str(test_file)])
        assert result.exit_code == 0
        assert "1 file(s) ingested" in result.output

    @patch("src.ingestion.orchestrator.ingest_files")
    def test_files_not_found(self, mock_ingest, tmp_path):
        from src.ingestion.result import IngestionError

        missing = tmp_path / "nonexistent.txt"
        mock_ingest.return_value = _files_envelope(
            failed=1,
            errors=[
                IngestionError(
                    code="file_not_found",
                    message=f"File not found: {missing}",
                    url=str(missing),
                )
            ],
        )

        result = runner.invoke(app, ["--direct", "ingest", "files", str(missing)])
        # All-failures envelope (items_ingested=0 AND items_failed>0) ⇒ exit 1
        assert result.exit_code == 1
        assert "File not found" in result.output

    @patch("src.ingestion.orchestrator.ingest_files")
    def test_files_title_warning_multiple(self, mock_ingest, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("a")
        f2.write_text("b")

        mock_ingest.return_value = _files_envelope(
            ingested=2,
            results=[
                {"path": str(f1), "content_id": 1, "title": "A"},
                {"path": str(f2), "content_id": 2, "title": "B"},
            ],
        )

        result = runner.invoke(
            app,
            [
                "ingest",
                "files",
                str(f1),
                str(f2),
                "--title",
                "Ignored",
            ],
        )
        assert result.exit_code == 0
        assert "Warning" in result.output
        # CLI should drop --title before calling orchestrator on multi-file batch
        call_kwargs = mock_ingest.call_args[1]
        assert call_kwargs["title"] is None

    def test_files_help(self):
        result = runner.invoke(app, ["--direct", "ingest", "files", "--help"])
        assert result.exit_code == 0
        assert "Ingest one or more local files" in result.output


def _url_envelope(*, content_id: int, duplicate: bool):
    """Build a url IngestionResponse mock matching the post-round-4 shape.

    Duplicates surface as ``items_skipped=1`` (URL row already exists, nothing
    new landed); fresh URLs surface as ``items_ingested=1`` (queued for
    extraction). ``details`` carries the legacy flat keys consumers like the
    MCP wrapper still read.
    """
    from src.ingestion.result import IngestionResponse

    return IngestionResponse(
        command="ingest.url",
        source="url",
        status="ok",
        items_ingested=0 if duplicate else 1,
        items_skipped=1 if duplicate else 0,
        details={
            "content_id": content_id,
            "status": "exists" if duplicate else "queued",
            "duplicate": duplicate,
            "url": "https://example.com",
        },
    )


class TestIngestUrl:
    """Post-round-4: ingest_url returns IngestionResponse with details carrying
    the legacy flat keys (content_id/status/duplicate). Mocks updated to match.
    """

    @patch("src.ingestion.orchestrator.ingest_url")
    def test_url_success(self, mock_ingest):
        mock_ingest.return_value = _url_envelope(content_id=42, duplicate=False)

        result = runner.invoke(app, ["--direct", "ingest", "url", "https://example.com/article"])
        assert result.exit_code == 0
        assert "URL ingested" in result.output
        assert "42" in result.output

    @patch("src.ingestion.orchestrator.ingest_url")
    def test_url_duplicate(self, mock_ingest):
        mock_ingest.return_value = _url_envelope(content_id=99, duplicate=True)

        result = runner.invoke(app, ["--direct", "ingest", "url", "https://example.com/article"])
        assert result.exit_code == 0
        assert "already exists" in result.output
        assert "99" in result.output

    @patch("src.ingestion.orchestrator.ingest_url")
    def test_url_with_options(self, mock_ingest):
        mock_ingest.return_value = _url_envelope(content_id=1, duplicate=False)

        result = runner.invoke(
            app,
            [
                "ingest",
                "url",
                "https://example.com",
                "--title",
                "My Article",
                "--tag",
                "ai",
                "--tag",
                "news",
                "--notes",
                "Important",
            ],
        )
        assert result.exit_code == 0
        mock_ingest.assert_called_once()
        call_kwargs = mock_ingest.call_args[1]
        assert call_kwargs["url"] == "https://example.com"
        assert call_kwargs["title"] == "My Article"
        assert call_kwargs["tags"] == ["ai", "news"]
        assert call_kwargs["notes"] == "Important"

    @patch("src.ingestion.orchestrator.ingest_url")
    def test_url_failure(self, mock_ingest):
        mock_ingest.side_effect = RuntimeError("Connection refused")

        result = runner.invoke(app, ["--direct", "ingest", "url", "https://example.com"])
        assert result.exit_code == 1
        assert "URL ingestion failed" in result.output

    @patch("src.ingestion.orchestrator.ingest_url")
    def test_url_json_mode(self, mock_ingest):
        mock_ingest.return_value = _url_envelope(content_id=7, duplicate=False)

        result = runner.invoke(app, ["--json", "--direct", "ingest", "url", "https://example.com"])
        assert result.exit_code == 0
        assert '"source": "url"' in result.output
        # content_id / duplicate live in details on the canonical envelope
        assert '"content_id": 7' in result.output
        assert '"duplicate": false' in result.output

    @patch("src.ingestion.orchestrator.ingest_url")
    def test_url_json_mode_duplicate(self, mock_ingest):
        mock_ingest.return_value = _url_envelope(content_id=99, duplicate=True)

        result = runner.invoke(app, ["--json", "--direct", "ingest", "url", "https://example.com"])
        assert result.exit_code == 0
        assert '"duplicate": true' in result.output
        assert '"status": "exists"' in result.output

    def test_url_no_argument(self):
        result = runner.invoke(app, ["--direct", "ingest", "url"])
        assert result.exit_code != 0

    def test_url_help(self):
        result = runner.invoke(app, ["--direct", "ingest", "url", "--help"])
        assert result.exit_code == 0
        assert "Ingest a single URL" in result.output


class TestIngestXSearch:
    @staticmethod
    def _xsearch_response(*, items_ingested: int = 0, status: str = "ok"):
        from src.ingestion.result import IngestionResponse

        return IngestionResponse(
            command="ingest.xsearch",
            source="xsearch",
            status=status,  # type: ignore[arg-type]
            items_ingested=items_ingested,
            details={"tool_calls_made": 0, "threads_found": items_ingested},
        )

    @patch("src.ingestion.orchestrator.ingest_xsearch")
    def test_xsearch_success(self, mock_ingest):
        mock_ingest.return_value = self._xsearch_response(items_ingested=5)

        result = runner.invoke(app, ["--direct", "ingest", "xsearch"])
        assert result.exit_code == 0
        assert "5" in result.output
        assert "X search ingestion complete" in result.output

    @patch("src.ingestion.orchestrator.ingest_xsearch")
    def test_xsearch_with_custom_prompt(self, mock_ingest):
        mock_ingest.return_value = self._xsearch_response(items_ingested=3)

        result = runner.invoke(
            app,
            [
                "ingest",
                "xsearch",
                "--prompt",
                "Find AI model releases",
                "--max-threads",
                "20",
            ],
        )
        assert result.exit_code == 0
        mock_ingest.assert_called_once_with(
            prompt="Find AI model releases",
            max_threads=20,
            force_reprocess=False,
        )

    @patch("src.ingestion.orchestrator.ingest_xsearch")
    def test_xsearch_with_force(self, mock_ingest):
        mock_ingest.return_value = self._xsearch_response(items_ingested=1)

        result = runner.invoke(app, ["--direct", "ingest", "xsearch", "--force"])
        assert result.exit_code == 0
        mock_ingest.assert_called_once_with(
            prompt=None,
            max_threads=None,
            force_reprocess=True,
        )

    @patch("src.ingestion.orchestrator.ingest_xsearch")
    def test_xsearch_failure(self, mock_ingest):
        mock_ingest.side_effect = RuntimeError("API key invalid")

        result = runner.invoke(app, ["--direct", "ingest", "xsearch"])
        assert result.exit_code == 1
        assert "X search ingestion failed" in result.output

    @patch("src.ingestion.orchestrator.ingest_xsearch")
    def test_xsearch_json_mode(self, mock_ingest):
        mock_ingest.return_value = self._xsearch_response(items_ingested=2)

        result = runner.invoke(app, ["--json", "--direct", "ingest", "xsearch"])
        assert result.exit_code == 0
        assert '"source": "xsearch"' in result.output
        assert '"items_ingested": 2' in result.output

    @patch("src.ingestion.orchestrator.ingest_xsearch")
    def test_xsearch_json_mode_failure(self, mock_ingest):
        mock_ingest.side_effect = RuntimeError("Rate limited")

        result = runner.invoke(app, ["--json", "--direct", "ingest", "xsearch"])
        assert result.exit_code == 1
        assert '"error"' in result.output
        assert '"source": "xsearch"' in result.output

    def test_xsearch_help(self):
        result = runner.invoke(app, ["--direct", "ingest", "xsearch", "--help"])
        assert result.exit_code == 0
        assert "Grok API" in result.output
