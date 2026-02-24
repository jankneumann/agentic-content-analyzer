"""CLI commands for end-to-end pipeline execution.

Usage:
    aca pipeline daily
    aca pipeline weekly

Parallel Ingestion:
    All 7 ingestion sources (Gmail, RSS, YouTube Playlist, YouTube RSS, Podcast,
    Substack, X Search) run concurrently via asyncio.gather(). Total ingestion
    time equals the slowest source, not the sum of all sources.

OpenTelemetry Instrumentation:
    Each pipeline stage creates an OTel span for observability:
    - pipeline.ingestion: Parallel source ingestion with item_count
    - pipeline.summarization: Content summarization with item_count
    - pipeline.digest: Digest creation with digest_type
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated, Any

import typer

from src.cli.output import is_json_mode, output_result
from src.telemetry.metrics import (
    record_pipeline_stage_completed,
    record_pipeline_stage_failed,
    record_pipeline_stage_started,
)
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from opentelemetry.trace import Span

logger = get_logger(__name__)

app = typer.Typer(help="Run end-to-end ingest -> summarize -> digest pipelines.")


def _get_tracer() -> Any:
    """Get OTel tracer if available, otherwise return None."""
    try:
        from opentelemetry import trace

        return trace.get_tracer("newsletter-aggregator")
    except ImportError:
        return None


class _StageContext:
    """Context object for pipeline stage tracking.

    Stores item_count for metrics reporting at stage completion.
    """

    def __init__(self, span: Span | None = None) -> None:
        self.span = span
        self.item_count: int = 0

    def set_attribute(self, key: str, value: int | str) -> None:
        """Set attribute on span if available."""
        if self.span:
            self.span.set_attribute(key, value)
        # Track item_count for metrics
        if key == "item_count" and isinstance(value, int):
            self.item_count = value


@contextmanager
def _pipeline_stage_span(
    stage_name: str,
    pipeline_type: str,
) -> Generator[_StageContext, None, None]:
    """Create an OTel span for a pipeline stage with metrics.

    Creates a span named 'pipeline.{stage_name}' with attributes:
    - pipeline_type: "daily" or "weekly"
    - stage: Stage name (ingestion, summarization, digest)
    - status: success|failure on completion
    - item_count: Number of items processed (set by caller via ctx.set_attribute)
    - error_message: Present if failed

    Also records pipeline stage metrics (started/completed/failed counters).

    Args:
        stage_name: Stage name (ingestion, summarization, digest)
        pipeline_type: Pipeline type (daily, weekly)

    Yields:
        StageContext object for setting attributes and tracking item_count
    """
    # Record stage started metric
    record_pipeline_stage_started(stage_name)

    tracer = _get_tracer()
    if tracer is None:
        ctx = _StageContext(None)
        try:
            yield ctx
            record_pipeline_stage_completed(stage_name, ctx.item_count)
        except Exception as e:
            record_pipeline_stage_failed(stage_name, str(e))
            raise
        return

    with tracer.start_as_current_span(f"pipeline.{stage_name}") as span:
        span.set_attribute("pipeline_type", pipeline_type)
        span.set_attribute("stage", stage_name)
        ctx = _StageContext(span)
        try:
            yield ctx
            span.set_attribute("status", "success")
            record_pipeline_stage_completed(stage_name, ctx.item_count)
        except Exception as e:
            span.set_attribute("status", "failure")
            span.set_attribute("error_message", str(e))
            span.record_exception(e)
            record_pipeline_stage_failed(stage_name, str(e))
            raise


async def _ingest_source(
    source_name: str,
    ingest_func: Callable[[], int],
) -> tuple[str, int | None, str | None]:
    """Ingest from a single source asynchronously.

    Wraps the synchronous ingestion service call in asyncio.to_thread()
    to enable parallel execution without blocking.

    Args:
        source_name: Name of the source (gmail, rss, youtube, podcast)
        ingest_func: Callable that performs the ingestion and returns count

    Returns:
        Tuple of (source_name, count, error_message)
        - count is None if failed
        - error_message is None if succeeded
    """
    try:
        # Import OTel tracer for per-source spans
        try:
            from opentelemetry import trace

            tracer = trace.get_tracer("newsletter-aggregator")
        except ImportError:
            tracer = None

        # Create span for this source
        if tracer:
            with tracer.start_as_current_span(f"ingestion.{source_name}") as span:
                span.set_attribute("source", source_name)
                try:
                    count = await asyncio.to_thread(ingest_func)
                    span.set_attribute("status", "success")
                    span.set_attribute("item_count", count)
                    return (source_name, count, None)
                except Exception as e:
                    span.set_attribute("status", "error")
                    span.set_attribute("error_type", type(e).__name__)
                    span.set_attribute("error_message", str(e))
                    span.record_exception(e)
                    return (source_name, None, str(e))
        else:
            count = await asyncio.to_thread(ingest_func)
            return (source_name, count, None)

    except Exception as e:
        logger.error(f"Ingestion failed for {source_name}: {e}")
        return (source_name, None, str(e))


async def _run_ingestion_stage_async() -> dict[str, int]:
    """Run all ingestion sources in parallel and return counts per source.

    Uses asyncio.gather() to run all 5 sources concurrently via the
    shared orchestrator layer. Total ingestion time equals the slowest
    source, not the sum of all sources.

    Returns:
        Dictionary mapping source name to number of items ingested.

    Raises:
        RuntimeError: If all ingestion sources fail.
    """
    from src.ingestion.orchestrator import (
        ingest_gmail,
        ingest_podcast,
        ingest_rss,
        ingest_substack,
        ingest_xsearch,
        ingest_youtube_playlist,
        ingest_youtube_rss,
    )

    source_count = 7
    typer.echo(f"  Running parallel ingestion ({source_count} sources)...")

    # Define ingestion tasks — each orchestrator function is a plain
    # synchronous function, wrapped in asyncio.to_thread by _ingest_source.
    # YouTube playlists and RSS are separate tasks so rate limits on RSS
    # don't block higher-priority playlist ingestion.
    tasks = [
        _ingest_source("gmail", ingest_gmail),
        _ingest_source("rss", ingest_rss),
        _ingest_source("youtube-playlist", ingest_youtube_playlist),
        _ingest_source("youtube-rss", ingest_youtube_rss),
        _ingest_source("podcast", ingest_podcast),
        _ingest_source("substack", ingest_substack),
        _ingest_source("xsearch", ingest_xsearch),
    ]

    # Run all sources in parallel
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    results: dict[str, int] = {}
    errors: dict[str, str] = {}
    completed = 0
    failed = 0

    for result in results_list:
        if isinstance(result, BaseException):
            # Unexpected exception from gather
            errors["unknown"] = str(result)
            failed += 1
        else:
            # result is tuple[str, int | None, str | None] from _ingest_source
            assert isinstance(result, tuple)
            source_name, count, error = result
            if error:
                errors[source_name] = error
                failed += 1
                typer.echo(f"    ✗ {source_name}: failed ({error})")
            else:
                results[source_name] = count or 0
                completed += 1
                typer.echo(f"    ✓ {source_name}: {count} items ingested")

    # Summary
    typer.echo(f"  [{completed}/{source_count} complete, {failed} failed]")

    # If every source failed, raise so the pipeline reports stage failure
    if len(errors) == source_count and len(results) == 0:
        raise RuntimeError(
            "All ingestion sources failed: " + "; ".join(f"{k}: {v}" for k, v in errors.items())
        )

    return results


def _run_ingestion_stage(pipeline_type: str = "daily") -> dict[str, int]:
    """Run all ingestion sources in parallel and return counts per source.

    Wrapper that runs the async parallel ingestion in the event loop.
    Creates an OTel span for the entire ingestion stage.

    Args:
        pipeline_type: Pipeline type for span attributes (daily, weekly)

    Returns:
        Dictionary mapping source name to number of items ingested.

    Raises:
        RuntimeError: If all ingestion sources fail.
    """
    with _pipeline_stage_span("ingestion", pipeline_type) as ctx:
        results = asyncio.run(_run_ingestion_stage_async())
        total_items = sum(results.values())
        ctx.set_attribute("item_count", total_items)
        ctx.set_attribute("source_count", len(results))
        return results


async def _wait_for_jobs(job_ids: list[int], poll_interval: float = 2.0) -> dict[str, int]:
    """Wait for a list of jobs to complete.

    Polls the job status until all jobs reach a terminal state (completed/failed).

    Args:
        job_ids: List of job IDs to wait for
        poll_interval: Seconds between status checks

    Returns:
        Dictionary with completed_count and failed_count
    """
    from src.queue.setup import get_job_status

    completed = 0
    failed = 0
    pending = set(job_ids)

    while pending:
        for job_id in list(pending):
            job = await get_job_status(job_id)
            if job is None:
                # Job not found (shouldn't happen)
                pending.discard(job_id)
                failed += 1
            elif job.is_terminal:
                pending.discard(job_id)
                if job.status.value == "completed":
                    completed += 1
                else:
                    failed += 1

        if pending:
            typer.echo(
                f"  Progress: {completed + failed}/{len(job_ids)} "
                f"({completed} completed, {failed} failed, {len(pending)} pending)"
            )
            await asyncio.sleep(poll_interval)

    return {"completed_count": completed, "failed_count": failed}


def _run_summarization_stage(pipeline_type: str = "daily", use_queue: bool = False) -> int:
    """Run summarization on all pending content.

    Creates an OTel span for the entire summarization stage.

    Args:
        pipeline_type: Pipeline type for span attributes (daily, weekly)
        use_queue: If True, enqueue jobs for worker processing and wait.
                   If False, process directly (default, backward compatible).

    Returns:
        Number of content items successfully summarized.
    """
    from src.processors.summarizer import ContentSummarizer

    with _pipeline_stage_span("summarization", pipeline_type) as ctx:
        summarizer = ContentSummarizer()

        if use_queue:
            typer.echo("  Enqueueing pending content for summarization...")

            # Enqueue jobs asynchronously
            async def enqueue_and_wait() -> int:
                result = await summarizer.enqueue_pending_contents()
                enqueued = result["enqueued_count"]
                skipped = result["skipped_count"]
                job_ids = result["job_ids"]
                assert isinstance(job_ids, list)  # Always list[int] from enqueue_pending_contents

                if not job_ids:
                    typer.echo("  No new content to summarize.")
                    return 0

                typer.echo(f"  Enqueued {enqueued} jobs ({skipped} already in queue)")
                typer.echo("  Waiting for worker completion...")

                wait_result = await _wait_for_jobs(job_ids)
                return wait_result["completed_count"]

            count = asyncio.run(enqueue_and_wait())
        else:
            typer.echo("  Summarizing pending content...")
            count = summarizer.summarize_pending_contents()

        typer.echo(f"  Summarized {count} content items")
        ctx.set_attribute("item_count", count)
        return count


def _run_digest_stage(
    digest_type: str,
    period_start: datetime,
    period_end: datetime,
    pipeline_type: str = "daily",
) -> dict:
    """Create a digest for the given period.

    Creates an OTel span for the digest creation stage.

    Args:
        digest_type: Either "daily" or "weekly".
        period_start: Start of the digest period (inclusive).
        period_end: End of the digest period (exclusive).
        pipeline_type: Pipeline type for span attributes (daily, weekly)

    Returns:
        Dictionary with digest creation result metadata.
    """
    from src.cli.adapters import create_digest_sync
    from src.models.digest import DigestRequest, DigestType

    with _pipeline_stage_span("digest", pipeline_type) as ctx:
        dtype = DigestType.DAILY if digest_type == "daily" else DigestType.WEEKLY

        request = DigestRequest(
            digest_type=dtype,
            period_start=period_start,
            period_end=period_end,
        )

        typer.echo(
            f"  Creating {digest_type} digest for "
            f"{period_start.strftime('%Y-%m-%d')} to {period_end.strftime('%Y-%m-%d')}..."
        )
        result = create_digest_sync(request)
        typer.echo(f"  Digest created: {result.title}")

        ctx.set_attribute("digest_type", digest_type)
        ctx.set_attribute("item_count", result.newsletter_count)
        ctx.set_attribute("period_start", period_start.isoformat())
        ctx.set_attribute("period_end", period_end.isoformat())

        return {
            "title": result.title,
            "digest_type": digest_type,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "newsletter_count": result.newsletter_count,
        }


@app.command("daily")
def daily(
    date: Annotated[
        str | None,
        typer.Option(
            "--date",
            "-d",
            help="Target date in YYYY-MM-DD format (default: today).",
        ),
    ] = None,
    wait: Annotated[
        bool,
        typer.Option(
            "--wait",
            "-w",
            help="Enqueue summarization jobs and wait for worker completion instead of direct processing.",
        ),
    ] = False,
) -> None:
    """Run the full daily pipeline: ingest all sources, summarize, create daily digest.

    Stages run sequentially:
    1. Ingest from all configured sources (Gmail, RSS, YouTube, Podcast)
    2. Summarize all pending content (or enqueue for workers with --wait)
    3. Create daily digest for the target date

    If a stage fails, the pipeline reports which stage failed and exits with code 1.
    Successfully completed stages are NOT rolled back.

    Use --wait flag to enqueue summarization jobs for worker pool processing
    instead of direct in-process summarization.
    """
    # Parse target date
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            typer.echo(f"Error: Invalid date format '{date}'. Expected YYYY-MM-DD.")
            raise typer.Exit(1)
    else:
        now = datetime.now(UTC)
        target_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

    period_start = target_date
    period_end = target_date + timedelta(days=1)

    typer.echo(f"Running daily pipeline for {target_date.strftime('%Y-%m-%d')}")
    typer.echo("=" * 60)

    pipeline_result: dict = {
        "pipeline": "daily",
        "date": target_date.strftime("%Y-%m-%d"),
        "stages": {},
    }

    # Stage 1: Ingestion
    typer.echo("\nStage 1/3: Content Ingestion")
    try:
        ingestion_counts = _run_ingestion_stage(pipeline_type="daily")
        pipeline_result["stages"]["ingestion"] = {
            "status": "completed",
            "counts": ingestion_counts,
        }
    except Exception as e:
        typer.echo(f"\nPipeline failed at Stage 1 (Ingestion): {e}")
        pipeline_result["stages"]["ingestion"] = {
            "status": "failed",
            "error": str(e),
        }
        if is_json_mode():
            output_result(pipeline_result, success=False)
        raise typer.Exit(1)

    # Stage 2: Summarization
    typer.echo("\nStage 2/3: Content Summarization")
    try:
        summarized_count = _run_summarization_stage(pipeline_type="daily", use_queue=wait)
        pipeline_result["stages"]["summarization"] = {
            "status": "completed",
            "count": summarized_count,
            "mode": "queue" if wait else "direct",
        }
    except Exception as e:
        typer.echo(f"\nPipeline failed at Stage 2 (Summarization): {e}")
        pipeline_result["stages"]["summarization"] = {
            "status": "failed",
            "error": str(e),
        }
        if is_json_mode():
            output_result(pipeline_result, success=False)
        raise typer.Exit(1)

    # Stage 3: Digest Creation
    typer.echo("\nStage 3/3: Digest Creation")
    try:
        digest_info = _run_digest_stage("daily", period_start, period_end, pipeline_type="daily")
        pipeline_result["stages"]["digest"] = {
            "status": "completed",
            **digest_info,
        }
    except Exception as e:
        typer.echo(f"\nPipeline failed at Stage 3 (Digest Creation): {e}")
        pipeline_result["stages"]["digest"] = {
            "status": "failed",
            "error": str(e),
        }
        if is_json_mode():
            output_result(pipeline_result, success=False)
        raise typer.Exit(1)

    # Success
    typer.echo("\n" + "=" * 60)
    typer.echo("Daily pipeline completed successfully.")
    total_ingested = sum(ingestion_counts.values())
    typer.echo(
        f"  Ingested: {total_ingested} items | "
        f"Summarized: {summarized_count} | "
        f"Digest: {digest_info['title']}"
    )

    if is_json_mode():
        output_result(pipeline_result)


@app.command("weekly")
def weekly(
    week: Annotated[
        str | None,
        typer.Option(
            "--week",
            "-w",
            help="Start-of-week date in YYYY-MM-DD format (default: start of current week, Monday).",
        ),
    ] = None,
    wait: Annotated[
        bool,
        typer.Option(
            "--wait",
            help="Enqueue summarization jobs and wait for worker completion instead of direct processing.",
        ),
    ] = False,
) -> None:
    """Run the full weekly pipeline: ingest all sources, summarize, create weekly digest.

    Stages run sequentially:
    1. Ingest from all configured sources (Gmail, RSS, YouTube, Podcast)
    2. Summarize all pending content (or enqueue for workers with --wait)
    3. Create weekly digest for the target week

    If a stage fails, the pipeline reports which stage failed and exits with code 1.
    Successfully completed stages are NOT rolled back.

    Use --wait flag to enqueue summarization jobs for worker pool processing
    instead of direct in-process summarization.
    """
    # Parse target week start date
    if week:
        try:
            week_start = datetime.strptime(week, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            typer.echo(f"Error: Invalid date format '{week}'. Expected YYYY-MM-DD.")
            raise typer.Exit(1)
    else:
        now = datetime.now(UTC)
        # Monday of the current week
        days_since_monday = now.weekday()
        week_start = (now - timedelta(days=days_since_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    period_start = week_start
    period_end = week_start + timedelta(days=7)

    typer.echo(f"Running weekly pipeline for week of {week_start.strftime('%Y-%m-%d')}")
    typer.echo("=" * 60)

    pipeline_result: dict = {
        "pipeline": "weekly",
        "week_start": week_start.strftime("%Y-%m-%d"),
        "stages": {},
    }

    # Stage 1: Ingestion
    typer.echo("\nStage 1/3: Content Ingestion")
    try:
        ingestion_counts = _run_ingestion_stage(pipeline_type="weekly")
        pipeline_result["stages"]["ingestion"] = {
            "status": "completed",
            "counts": ingestion_counts,
        }
    except Exception as e:
        typer.echo(f"\nPipeline failed at Stage 1 (Ingestion): {e}")
        pipeline_result["stages"]["ingestion"] = {
            "status": "failed",
            "error": str(e),
        }
        if is_json_mode():
            output_result(pipeline_result, success=False)
        raise typer.Exit(1)

    # Stage 2: Summarization
    typer.echo("\nStage 2/3: Content Summarization")
    try:
        summarized_count = _run_summarization_stage(pipeline_type="weekly", use_queue=wait)
        pipeline_result["stages"]["summarization"] = {
            "status": "completed",
            "count": summarized_count,
            "mode": "queue" if wait else "direct",
        }
    except Exception as e:
        typer.echo(f"\nPipeline failed at Stage 2 (Summarization): {e}")
        pipeline_result["stages"]["summarization"] = {
            "status": "failed",
            "error": str(e),
        }
        if is_json_mode():
            output_result(pipeline_result, success=False)
        raise typer.Exit(1)

    # Stage 3: Digest Creation
    typer.echo("\nStage 3/3: Digest Creation")
    try:
        digest_info = _run_digest_stage("weekly", period_start, period_end, pipeline_type="weekly")
        pipeline_result["stages"]["digest"] = {
            "status": "completed",
            **digest_info,
        }
    except Exception as e:
        typer.echo(f"\nPipeline failed at Stage 3 (Digest Creation): {e}")
        pipeline_result["stages"]["digest"] = {
            "status": "failed",
            "error": str(e),
        }
        if is_json_mode():
            output_result(pipeline_result, success=False)
        raise typer.Exit(1)

    # Success
    typer.echo("\n" + "=" * 60)
    typer.echo("Weekly pipeline completed successfully.")
    total_ingested = sum(ingestion_counts.values())
    typer.echo(
        f"  Ingested: {total_ingested} items | "
        f"Summarized: {summarized_count} | "
        f"Digest: {digest_info['title']}"
    )

    if is_json_mode():
        output_result(pipeline_result)
