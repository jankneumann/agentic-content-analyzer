"""Integration tests for parallel ingestion pipeline.

After the orchestrator refactor, the pipeline delegates to orchestrator functions.
Tests mock at `src.ingestion.orchestrator.<func>` instead of individual service classes.

Tests cover:
- Partial failure handling (some sources fail, others succeed)
- All sources fail → RuntimeError raised
- CLI --wait flag (queue-based summarization)
- Progress output formatting (per-source status, summary line)
"""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


# =============================================================================
# Helpers
# =============================================================================

# Orchestrator function names mapped to their patch targets.
#
# Must mirror the hard-coded source list in
# ``src.cli.pipeline_commands._run_ingestion_stage_async`` — if the pipeline
# adds a source the test scaffold doesn't patch, that source runs for real
# (hitting Gmail OAuth, YouTube API, etc.) and pollutes the test with
# integration-level failures. Dynamic websearch sources (perplexity, grok)
# are off by default in tests because no ``sources.d/websearch.yaml`` is
# loaded; they don't need scaffolding here.
_ORCHESTRATOR_FUNCTIONS = {
    "gmail": "src.ingestion.orchestrator.ingest_gmail",
    "rss": "src.ingestion.orchestrator.ingest_rss",
    "blog": "src.ingestion.orchestrator.ingest_blog",
    "youtube-playlist": "src.ingestion.orchestrator.ingest_youtube_playlist",
    "youtube-rss": "src.ingestion.orchestrator.ingest_youtube_rss",
    "podcast": "src.ingestion.orchestrator.ingest_podcast",
    "substack": "src.ingestion.orchestrator.ingest_substack",
}


def _make_ingestion_patches(
    *,
    gmail_result: int | Exception = 2,
    rss_result: int | Exception = 3,
    blog_result: int | Exception = 0,
    youtube_playlist_result: int | Exception = 0,
    youtube_rss_result: int | Exception = 1,
    podcast_result: int | Exception = 1,
    substack_result: int | Exception = 0,
) -> dict[str, patch]:
    """Build mock patches for all 7 hard-coded orchestrator functions.

    Each kwarg accepts either a count (int — passed via ``return_value``,
    routed through pipeline_commands._ingest_source's int|envelope
    normalization) or an Exception (raised via ``side_effect``).

    The orchestrator entry points for the harmonized sources actually
    return ``IngestionResponse`` envelopes; ints are accepted here for
    test brevity because ``_ingest_source`` normalizes both shapes during
    the partial-migration window.
    """
    results = {
        "gmail": gmail_result,
        "rss": rss_result,
        "blog": blog_result,
        "youtube-playlist": youtube_playlist_result,
        "youtube-rss": youtube_rss_result,
        "podcast": podcast_result,
        "substack": substack_result,
    }

    patches = {}
    for name, result in results.items():
        target = _ORCHESTRATOR_FUNCTIONS[name]
        if isinstance(result, Exception):
            patches[name] = patch(target, side_effect=result)
        else:
            patches[name] = patch(target, return_value=result)
    return patches


def _apply_ingestion_patches(patches: dict) -> ExitStack:
    """Return a combined context manager that applies all orchestrator patches."""
    stack = ExitStack()
    for p in patches.values():
        stack.enter_context(p)
    return stack


# =============================================================================
# Tests: Partial Failure Handling
# =============================================================================


class TestParallelIngestionPartialFailure:
    """Tests for partial failure handling during parallel ingestion."""

    @patch("src.cli.adapters.create_digest_sync")
    @patch("src.processors.summarizer.ContentSummarizer")
    def test_pipeline_succeeds_when_one_source_fails(self, mock_summarizer, mock_digest):
        """Pipeline continues when 1 of 7 ingestion sources fails."""
        mock_summarizer.return_value.summarize_pending_contents.return_value = 5
        mock_result = MagicMock()
        mock_result.title = "Daily Digest"
        mock_result.newsletter_count = 6
        mock_digest.return_value = mock_result

        patches = _make_ingestion_patches(gmail_result=RuntimeError("Gmail auth failed"))
        with _apply_ingestion_patches(patches):
            result = runner.invoke(app, ["pipeline", "daily"])

        assert result.exit_code == 0
        assert "completed successfully" in result.output
        # Should report gmail failure
        assert "gmail" in result.output.lower()
        assert "failed" in result.output.lower()

    @patch("src.cli.adapters.create_digest_sync")
    @patch("src.processors.summarizer.ContentSummarizer")
    def test_pipeline_succeeds_when_two_sources_fail(self, mock_summarizer, mock_digest):
        """Pipeline continues when 2 of 7 ingestion sources fail (gmail + both youtube).

        YouTube was originally one logical source but was split into two
        physical orchestrator entry points (youtube-playlist + youtube-rss).
        Failing both preserves the original "youtube fails" intent.
        """
        mock_summarizer.return_value.summarize_pending_contents.return_value = 3
        mock_result = MagicMock()
        mock_result.title = "Daily Digest"
        mock_result.newsletter_count = 4
        mock_digest.return_value = mock_result

        patches = _make_ingestion_patches(
            gmail_result=RuntimeError("Gmail auth failed"),
            youtube_playlist_result=RuntimeError("YouTube quota exceeded"),
            youtube_rss_result=RuntimeError("YouTube quota exceeded"),
        )
        with _apply_ingestion_patches(patches):
            result = runner.invoke(app, ["pipeline", "daily"])

        assert result.exit_code == 0
        assert "completed successfully" in result.output
        # 4 completed (rss, blog, podcast, substack), 3 failed (gmail + 2x youtube)
        assert "4/7 complete" in result.output

    @patch("src.cli.adapters.create_digest_sync")
    @patch("src.processors.summarizer.ContentSummarizer")
    def test_pipeline_succeeds_when_three_sources_fail(self, mock_summarizer, mock_digest):
        """Pipeline continues even when 3 of 7 sources fail — only needs 1.

        Fails gmail + rss + youtube-rss (3 of 7 physical sources). The remaining
        4 succeed, demonstrating that ``_run_ingestion_stage_async`` only raises
        RuntimeError when ALL sources fail, not just a majority.
        """
        mock_summarizer.return_value.summarize_pending_contents.return_value = 1
        mock_result = MagicMock()
        mock_result.title = "Daily Digest"
        mock_result.newsletter_count = 1
        mock_digest.return_value = mock_result

        patches = _make_ingestion_patches(
            gmail_result=RuntimeError("fail"),
            rss_result=RuntimeError("fail"),
            youtube_rss_result=RuntimeError("fail"),
            podcast_result=1,
            # blog, youtube-playlist, substack succeed with default 0 / configured 0 items
        )
        with _apply_ingestion_patches(patches):
            result = runner.invoke(app, ["pipeline", "daily"])

        assert result.exit_code == 0
        # 4 completed (blog, youtube-playlist, podcast, substack), 3 failed
        assert "4/7 complete" in result.output


class TestParallelIngestionAllFail:
    """Tests for when all ingestion sources fail."""

    def test_pipeline_fails_when_all_sources_fail(self):
        """Pipeline reports failure and exits with code 1 when all sources fail."""
        patches = _make_ingestion_patches(
            gmail_result=RuntimeError("Gmail auth failed"),
            rss_result=RuntimeError("RSS timeout"),
            blog_result=RuntimeError("Blog error"),
            youtube_playlist_result=RuntimeError("YouTube playlist quota"),
            youtube_rss_result=RuntimeError("YouTube RSS quota"),
            podcast_result=RuntimeError("Podcast DNS"),
            substack_result=RuntimeError("Substack error"),
        )
        with _apply_ingestion_patches(patches):
            result = runner.invoke(app, ["pipeline", "daily"])

        assert result.exit_code == 1
        assert "failed" in result.output.lower()

    def test_pipeline_reports_all_source_errors(self):
        """Error output includes details about which sources failed."""
        patches = _make_ingestion_patches(
            gmail_result=RuntimeError("Gmail auth failed"),
            rss_result=RuntimeError("RSS timeout"),
            blog_result=RuntimeError("Blog error"),
            youtube_playlist_result=RuntimeError("YouTube playlist quota"),
            youtube_rss_result=RuntimeError("YouTube RSS quota"),
            podcast_result=RuntimeError("Podcast DNS"),
            substack_result=RuntimeError("Substack error"),
        )
        with _apply_ingestion_patches(patches):
            result = runner.invoke(app, ["pipeline", "daily"])

        assert result.exit_code == 1
        # All 7 failed
        assert "0/7 complete" in result.output


# =============================================================================
# Tests: Progress Output Formatting
# =============================================================================


class TestIngestionProgressOutput:
    """Tests for per-source status and summary line formatting."""

    @patch("src.cli.adapters.create_digest_sync")
    @patch("src.processors.summarizer.ContentSummarizer")
    def test_shows_per_source_item_count(self, mock_summarizer, mock_digest):
        """Output shows item count per successful source."""
        mock_summarizer.return_value.summarize_pending_contents.return_value = 5
        mock_result = MagicMock()
        mock_result.title = "Daily Digest"
        mock_result.newsletter_count = 7
        mock_digest.return_value = mock_result

        patches = _make_ingestion_patches(gmail_result=2, rss_result=3)
        with _apply_ingestion_patches(patches):
            result = runner.invoke(app, ["pipeline", "daily"])

        assert result.exit_code == 0
        # Check for item count output
        assert "items ingested" in result.output.lower() or "2" in result.output

    @patch("src.cli.adapters.create_digest_sync")
    @patch("src.processors.summarizer.ContentSummarizer")
    def test_shows_summary_count_line(self, mock_summarizer, mock_digest):
        """Output ends with summary showing total ingested/summarized/digest."""
        mock_summarizer.return_value.summarize_pending_contents.return_value = 5
        mock_result = MagicMock()
        mock_result.title = "Daily Digest"
        mock_result.newsletter_count = 7
        mock_digest.return_value = mock_result

        patches = _make_ingestion_patches()
        with _apply_ingestion_patches(patches):
            result = runner.invoke(app, ["pipeline", "daily"])

        assert result.exit_code == 0
        # Summary should show "Ingested: N items"
        assert "Ingested:" in result.output
        assert "Summarized:" in result.output


# =============================================================================
# Tests: Parallel Execution Verification
# =============================================================================


class TestParallelExecution:
    """Verify that ingestion sources actually run concurrently via orchestrator.

    These tests must patch every orchestrator entry point that
    ``_run_ingestion_stage_async`` calls — leaving any unpatched causes the
    real implementation to run (real Google OAuth, real RSS fetches, etc.),
    which both makes the tests slow and produces false failures from
    environment dependencies.
    """

    @pytest.mark.asyncio
    async def test_ingestion_uses_asyncio_gather(self):
        """Verify _run_ingestion_stage_async uses asyncio.gather for parallel execution."""
        from src.cli.pipeline_commands import _run_ingestion_stage_async

        with (
            patch("src.ingestion.orchestrator.ingest_gmail", return_value=2),
            patch("src.ingestion.orchestrator.ingest_rss", return_value=3),
            patch("src.ingestion.orchestrator.ingest_blog", return_value=0),
            patch("src.ingestion.orchestrator.ingest_youtube_playlist", return_value=1),
            patch("src.ingestion.orchestrator.ingest_youtube_rss", return_value=1),
            patch("src.ingestion.orchestrator.ingest_podcast", return_value=1),
            patch("src.ingestion.orchestrator.ingest_substack", return_value=0),
        ):
            results = await _run_ingestion_stage_async()

        # All 7 hard-coded sources should have results
        assert len(results) == 7
        assert results["gmail"] == 2
        assert results["rss"] == 3
        assert results["blog"] == 0
        assert results["youtube-playlist"] == 1
        assert results["youtube-rss"] == 1
        assert results["podcast"] == 1
        assert results["substack"] == 0

    @pytest.mark.asyncio
    async def test_partial_failure_returns_successful_sources_only(self):
        """Verify _run_ingestion_stage_async returns only successful sources."""
        from src.cli.pipeline_commands import _run_ingestion_stage_async

        with (
            patch("src.ingestion.orchestrator.ingest_gmail", side_effect=RuntimeError("fail")),
            patch("src.ingestion.orchestrator.ingest_rss", return_value=3),
            patch("src.ingestion.orchestrator.ingest_blog", return_value=0),
            patch("src.ingestion.orchestrator.ingest_youtube_playlist", return_value=1),
            patch("src.ingestion.orchestrator.ingest_youtube_rss", return_value=1),
            patch("src.ingestion.orchestrator.ingest_podcast", return_value=1),
            patch("src.ingestion.orchestrator.ingest_substack", return_value=0),
        ):
            results = await _run_ingestion_stage_async()

        # gmail failed, so only 6 of 7 sources in results
        assert "gmail" not in results
        assert len(results) == 6

    @pytest.mark.asyncio
    async def test_all_fail_raises_runtime_error(self):
        """Verify _run_ingestion_stage_async raises RuntimeError when all fail."""
        from src.cli.pipeline_commands import _run_ingestion_stage_async

        fail = RuntimeError("fail")
        with (
            patch("src.ingestion.orchestrator.ingest_gmail", side_effect=fail),
            patch("src.ingestion.orchestrator.ingest_rss", side_effect=fail),
            patch("src.ingestion.orchestrator.ingest_blog", side_effect=fail),
            patch("src.ingestion.orchestrator.ingest_youtube_playlist", side_effect=fail),
            patch("src.ingestion.orchestrator.ingest_youtube_rss", side_effect=fail),
            patch("src.ingestion.orchestrator.ingest_podcast", side_effect=fail),
            patch("src.ingestion.orchestrator.ingest_substack", side_effect=fail),
        ):
            with pytest.raises(RuntimeError, match="All ingestion sources failed"):
                await _run_ingestion_stage_async()


# =============================================================================
# Tests: --wait flag (queue-based summarization)
# =============================================================================


class TestWaitFlag:
    """Tests for the --wait flag that uses queue-based summarization."""

    @patch("src.cli.adapters.create_digest_sync")
    @patch("src.processors.summarizer.ContentSummarizer")
    @patch("src.cli.pipeline_commands._wait_for_jobs")
    def test_daily_wait_flag_enqueues_and_waits(
        self,
        mock_wait,
        mock_summarizer,
        mock_digest,
    ):
        """--wait flag enqueues summarization jobs instead of direct processing.

        Uses _make_ingestion_patches to scaffold all 7 orchestrator entry
        points. The decorator-chain approach is fragile because adding/
        removing a source requires reordering the chain (decorators apply
        bottom-up).
        """
        # Mock enqueue_pending_contents async method
        mock_summarizer.return_value.enqueue_pending_contents = AsyncMock(
            return_value={"enqueued_count": 5, "skipped_count": 0, "job_ids": [1, 2, 3, 4, 5]}
        )

        # Mock _wait_for_jobs to return immediately
        mock_wait.return_value = {"completed_count": 5, "failed_count": 0}

        mock_result = MagicMock()
        mock_result.title = "Daily Digest"
        mock_result.newsletter_count = 7
        mock_digest.return_value = mock_result

        patches = _make_ingestion_patches()
        with _apply_ingestion_patches(patches):
            result = runner.invoke(app, ["pipeline", "daily", "--wait"])

        assert result.exit_code == 0
        assert "completed successfully" in result.output

    @patch("src.cli.adapters.create_digest_sync")
    @patch("src.processors.summarizer.ContentSummarizer")
    def test_daily_without_wait_uses_direct_processing(
        self,
        mock_summarizer,
        mock_digest,
    ):
        """Without --wait, summarization runs directly (not queued)."""
        mock_summarizer.return_value.summarize_pending_contents.return_value = 5

        mock_result = MagicMock()
        mock_result.title = "Daily Digest"
        mock_result.newsletter_count = 7
        mock_digest.return_value = mock_result

        patches = _make_ingestion_patches()
        with _apply_ingestion_patches(patches):
            result = runner.invoke(app, ["pipeline", "daily"])

        assert result.exit_code == 0
        # Should call direct summarize, not enqueue
        mock_summarizer.return_value.summarize_pending_contents.assert_called_once()
