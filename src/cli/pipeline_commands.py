"""CLI commands for end-to-end pipeline execution.

Usage:
    aca pipeline daily
    aca pipeline weekly
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from src.cli.output import is_json_mode, output_result

app = typer.Typer(help="Run end-to-end ingest -> summarize -> digest pipelines.")


def _run_ingestion_stage() -> dict[str, int]:
    """Run all ingestion sources and return counts per source.

    Sequentially ingests from Gmail, RSS, YouTube, and Podcast sources.
    Each source is attempted independently; failures are captured but do
    not prevent other sources from running.

    Returns:
        Dictionary mapping source name to number of items ingested.

    Raises:
        RuntimeError: If all ingestion sources fail.
    """
    from src.ingestion.gmail import GmailContentIngestionService
    from src.ingestion.podcast import PodcastContentIngestionService
    from src.ingestion.rss import RSSContentIngestionService
    from src.ingestion.youtube import YouTubeContentIngestionService

    results: dict[str, int] = {}
    errors: dict[str, str] = {}

    # Gmail
    typer.echo("  [1/4] Ingesting from Gmail...")
    try:
        gmail_service = GmailContentIngestionService()
        results["gmail"] = gmail_service.ingest_content()
        typer.echo(f"         Gmail: {results['gmail']} items ingested")
    except Exception as e:
        errors["gmail"] = str(e)
        typer.echo(f"         Gmail: failed ({e})")

    # RSS
    typer.echo("  [2/4] Ingesting from RSS feeds...")
    try:
        rss_service = RSSContentIngestionService()
        results["rss"] = rss_service.ingest_content()
        typer.echo(f"         RSS: {results['rss']} items ingested")
    except Exception as e:
        errors["rss"] = str(e)
        typer.echo(f"         RSS: failed ({e})")

    # YouTube
    typer.echo("  [3/4] Ingesting from YouTube...")
    try:
        youtube_service = YouTubeContentIngestionService()
        results["youtube"] = youtube_service.ingest_all_playlists()
        typer.echo(f"         YouTube: {results['youtube']} items ingested")
    except Exception as e:
        errors["youtube"] = str(e)
        typer.echo(f"         YouTube: failed ({e})")

    # Podcast
    typer.echo("  [4/4] Ingesting from Podcasts...")
    try:
        podcast_service = PodcastContentIngestionService()
        results["podcast"] = podcast_service.ingest_all_feeds()
        typer.echo(f"         Podcast: {results['podcast']} items ingested")
    except Exception as e:
        errors["podcast"] = str(e)
        typer.echo(f"         Podcast: failed ({e})")

    # If every source failed, raise so the pipeline reports stage failure
    if len(errors) == 4 and len(results) == 0:
        raise RuntimeError(
            "All ingestion sources failed: " + "; ".join(f"{k}: {v}" for k, v in errors.items())
        )

    return results


def _run_summarization_stage() -> int:
    """Run summarization on all pending content.

    Returns:
        Number of content items successfully summarized.
    """
    from src.processors.summarizer import ContentSummarizer

    typer.echo("  Summarizing pending content...")
    summarizer = ContentSummarizer()
    count = summarizer.summarize_pending_contents()
    typer.echo(f"  Summarized {count} content items")
    return count


def _run_digest_stage(digest_type: str, period_start: datetime, period_end: datetime) -> dict:
    """Create a digest for the given period.

    Args:
        digest_type: Either "daily" or "weekly".
        period_start: Start of the digest period (inclusive).
        period_end: End of the digest period (exclusive).

    Returns:
        Dictionary with digest creation result metadata.
    """
    from src.cli.adapters import create_digest_sync
    from src.models.digest import DigestRequest, DigestType

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
) -> None:
    """Run the full daily pipeline: ingest all sources, summarize, create daily digest.

    Stages run sequentially:
    1. Ingest from all configured sources (Gmail, RSS, YouTube, Podcast)
    2. Summarize all pending content
    3. Create daily digest for the target date

    If a stage fails, the pipeline reports which stage failed and exits with code 1.
    Successfully completed stages are NOT rolled back.
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
        ingestion_counts = _run_ingestion_stage()
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
        summarized_count = _run_summarization_stage()
        pipeline_result["stages"]["summarization"] = {
            "status": "completed",
            "count": summarized_count,
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
        digest_info = _run_digest_stage("daily", period_start, period_end)
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
) -> None:
    """Run the full weekly pipeline: ingest all sources, summarize, create weekly digest.

    Stages run sequentially:
    1. Ingest from all configured sources (Gmail, RSS, YouTube, Podcast)
    2. Summarize all pending content
    3. Create weekly digest for the target week

    If a stage fails, the pipeline reports which stage failed and exits with code 1.
    Successfully completed stages are NOT rolled back.
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
        ingestion_counts = _run_ingestion_stage()
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
        summarized_count = _run_summarization_stage()
        pipeline_result["stages"]["summarization"] = {
            "status": "completed",
            "count": summarized_count,
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
        digest_info = _run_digest_stage("weekly", period_start, period_end)
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
