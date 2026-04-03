"""Embedded queue worker that processes jobs from pgqueuer_jobs table.

Uses SELECT FOR UPDATE SKIP LOCKED to claim jobs from our custom
pgqueuer_jobs table and dispatch them to registered task handlers.

This is a lightweight alternative to PGQueuer's run() which expects
its own native schema. Our custom table has additional features like
progress tracking and batch reconciliation.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

import asyncpg

from src.storage.database import get_queue_connection_string
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Registry of entrypoint → async handler functions
_handlers: dict[str, Callable[..., Coroutine[Any, Any, None]]] = {}


def _sqlalchemy_url_to_asyncpg(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgres://", 1)
    return url


def register_handler(entrypoint: str) -> Callable:
    """Decorator to register an async handler for a job entrypoint."""

    def decorator(func: Callable[..., Coroutine[Any, Any, None]]) -> Callable:
        _handlers[entrypoint] = func
        return func

    return decorator


async def _claim_jobs(
    conn: asyncpg.Connection,
    *,
    batch_size: int = 5,
) -> list[dict[str, Any]]:
    """Claim available jobs using SELECT FOR UPDATE SKIP LOCKED."""
    rows = await conn.fetch(
        """
        UPDATE pgqueuer_jobs
        SET status = 'in_progress',
            started_at = COALESCE(started_at, NOW()),
            heartbeat_at = NOW()
        WHERE id IN (
            SELECT id FROM pgqueuer_jobs
            WHERE status = 'queued'
              AND execute_after <= NOW()
            ORDER BY priority DESC, created_at ASC
            LIMIT $1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING id, entrypoint, payload
        """,
        batch_size,
    )
    return [dict(row) for row in rows]


async def _complete_job(conn: asyncpg.Connection, job_id: int) -> None:
    """Mark a job as completed."""
    await conn.execute(
        """
        UPDATE pgqueuer_jobs
        SET status = 'completed', completed_at = NOW(), heartbeat_at = NOW()
        WHERE id = $1
        """,
        job_id,
    )


async def _fail_job(conn: asyncpg.Connection, job_id: int, error: str) -> None:
    """Mark a job as failed with an error message."""
    await conn.execute(
        """
        UPDATE pgqueuer_jobs
        SET status = 'failed', error = $2, completed_at = NOW(), heartbeat_at = NOW()
        WHERE id = $1
        """,
        job_id,
        error[:1000],  # Truncate long error messages
    )


async def _emit_job_notification(
    job_id: int,
    entrypoint: str,
    payload: dict[str, Any],
    *,
    error: str | None = None,
) -> None:
    """Emit a notification event for a completed or failed job.

    Maps entrypoints to notification event types and generates
    human-readable titles and summaries.
    """
    try:
        from src.models.notification import NotificationEventType
        from src.services.notification_service import get_dispatcher

        dispatcher = get_dispatcher()

        if error:
            await dispatcher.emit(
                event_type=NotificationEventType.JOB_FAILURE,
                title=f"Job failed: {entrypoint}",
                summary=error[:200],
                payload={
                    "job_id": job_id,
                    "entrypoint": entrypoint,
                    "error": error[:500],
                    "url": "/jobs",
                },
            )
            return

        # Map entrypoints to event types
        entrypoint_event_map: dict[str, tuple[NotificationEventType, str]] = {
            "summarize_content": (
                NotificationEventType.BATCH_SUMMARY,
                "Content summarized",
            ),
            "process_content": (
                NotificationEventType.BATCH_SUMMARY,
                "Content processed",
            ),
            "ingest_content": (
                NotificationEventType.BATCH_SUMMARY,
                "Content ingested",
            ),
            "scan_newsletters": (
                NotificationEventType.BATCH_SUMMARY,
                "Newsletter scan complete",
            ),
            "extract_url_content": (
                NotificationEventType.BATCH_SUMMARY,
                "URL content extracted",
            ),
        }

        event_type, default_title = entrypoint_event_map.get(
            entrypoint,
            (NotificationEventType.BATCH_SUMMARY, f"Job completed: {entrypoint}"),
        )

        content_id = payload.get("content_id")
        source = payload.get("source", "")
        url = "/jobs"
        if content_id:
            url = f"/content/{content_id}"

        await dispatcher.emit(
            event_type=event_type,
            title=default_title,
            summary=f"Job {job_id} ({entrypoint}) completed successfully"
            + (f" for source '{source}'" if source else ""),
            payload={
                "job_id": job_id,
                "entrypoint": entrypoint,
                "content_id": content_id,
                "url": url,
            },
        )
    except Exception:
        # Notification emission is best-effort — never fail the job
        logger.debug("Failed to emit job notification", exc_info=True)


async def _process_job(
    conn: asyncpg.Connection,
    job: dict[str, Any],
) -> None:
    """Process a single job by dispatching to its registered handler."""
    job_id = job["id"]
    entrypoint = job["entrypoint"]
    payload = job["payload"] or {}
    if isinstance(payload, str):
        payload = json.loads(payload)

    handler = _handlers.get(entrypoint)
    if handler is None:
        logger.warning(f"No handler for entrypoint '{entrypoint}', failing job {job_id}")
        await _fail_job(conn, job_id, f"Unknown entrypoint: {entrypoint}")
        return

    async def _heartbeat_loop() -> None:
        from src.queue.setup import touch_job_heartbeat

        while True:
            await asyncio.sleep(15)
            await touch_job_heartbeat(job_id)

    heartbeat_task = asyncio.create_task(_heartbeat_loop())
    try:
        from src.queue.setup import touch_job_heartbeat

        await touch_job_heartbeat(job_id)
        await handler(job_id, payload)
        await _complete_job(conn, job_id)
        logger.info(f"Job {job_id} ({entrypoint}) completed")
        await _emit_job_notification(job_id, entrypoint, payload)
    except Exception as e:
        logger.error(f"Job {job_id} ({entrypoint}) failed: {e}", exc_info=True)
        generic_error = "Job failed due to an internal error"
        await _fail_job(conn, job_id, generic_error)
        await _emit_job_notification(job_id, entrypoint, payload, error=generic_error)
    finally:
        heartbeat_task.cancel()
        await asyncio.gather(heartbeat_task, return_exceptions=True)


async def run_worker(
    *,
    concurrency: int = 5,
    poll_interval: float = 5.0,
) -> None:
    """Run the embedded queue worker loop.

    Continuously polls pgqueuer_jobs for queued jobs, claims them
    using SELECT FOR UPDATE SKIP LOCKED, and processes them
    concurrently up to the given limit.

    Also listens on pg_notify('pgqueuer', ...) for immediate wakeup
    when new jobs are enqueued.

    Args:
        concurrency: Max concurrent job tasks
        poll_interval: Seconds between polls when no jobs found
    """
    queue_url = get_queue_connection_string()
    asyncpg_url = _sqlalchemy_url_to_asyncpg(queue_url)
    from src.queue.setup import ensure_queue_schema_compatible

    await ensure_queue_schema_compatible()

    conn = await asyncpg.connect(asyncpg_url)

    # Set up LISTEN for immediate job notification
    notify_event = asyncio.Event()

    def _on_notify(
        connection: asyncpg.Connection,
        pid: int,
        channel: str,
        payload: str,
    ) -> None:
        notify_event.set()

    await conn.add_listener("pgqueuer", _on_notify)

    active_tasks: set[asyncio.Task] = set()
    logger.info(f"Embedded worker started (concurrency={concurrency})")

    try:
        while True:
            # Clean up completed tasks
            done = {t for t in active_tasks if t.done()}
            for t in done:
                # Re-raise exceptions from tasks so they get logged
                try:
                    t.result()
                except Exception:
                    pass  # Already logged in _process_job
            active_tasks -= done

            # How many slots available?
            available = concurrency - len(active_tasks)
            if available > 0:
                jobs = await _claim_jobs(conn, batch_size=available)
                for job in jobs:
                    task = asyncio.create_task(_process_job(conn, job))
                    active_tasks.add(task)

                if jobs:
                    # Found work — immediately loop to check for more
                    continue

            # No work found — wait for notification or poll timeout
            notify_event.clear()
            try:
                await asyncio.wait_for(notify_event.wait(), timeout=poll_interval)
            except TimeoutError:
                pass

    except asyncio.CancelledError:
        logger.info("Embedded worker shutting down...")
        # Wait for active tasks to complete
        if active_tasks:
            logger.info(f"Waiting for {len(active_tasks)} active tasks...")
            await asyncio.gather(*active_tasks, return_exceptions=True)
        raise
    finally:
        await conn.remove_listener("pgqueuer", _on_notify)
        await conn.close()


def register_all_handlers() -> None:
    """Register all job handlers.

    This imports and registers handlers for all known entrypoints.
    """
    # Import here to avoid circular imports — these modules register
    # handlers via the @register_handler decorator or direct assignment.
    _register_content_handlers()
    _register_reference_handlers()
    _register_agent_handlers()
    logger.info(f"Registered {len(_handlers)} job handlers: {list(_handlers.keys())}")


def _register_content_handlers() -> None:
    """Register content processing handlers."""
    import asyncio as _asyncio

    from src.queue.setup import reconcile_batch_job_status, update_job_progress

    @register_handler("extract_url_content")
    async def extract_url_content(job_id: int, payload: dict) -> None:
        from src.services.url_extractor import URLExtractor
        from src.storage.database import get_db

        content_id = payload.get("content_id")
        if not content_id:
            raise ValueError("Missing content_id")

        with get_db() as db:
            extractor = URLExtractor(db)
            await extractor.extract_content(content_id)

    @register_handler("process_content")
    async def process_content(job_id: int, payload: dict) -> None:
        content_id = payload.get("content_id")
        task_type = payload.get("task_type", "summarize")
        if not content_id:
            raise ValueError("Missing content_id")

        if task_type == "summarize":
            from src.processors.summarizer import ContentSummarizer

            summarizer = ContentSummarizer()
            await _asyncio.to_thread(summarizer.summarize_content, content_id)
        else:
            raise ValueError(f"Unknown task_type: {task_type}")

    @register_handler("scan_newsletters")
    async def scan_newsletters(job_id: int, payload: dict) -> None:
        from src.ingestion.gmail import GmailContentIngestionService

        service = GmailContentIngestionService()
        labels = payload.get("labels")
        if labels is None:
            # Keep scheduler defaults aligned with Gmail ingestion defaults.
            service.ingest_content()
        else:
            label_query = " OR ".join(f"label:{label}" for label in labels) if labels else ""
            service.ingest_content(query=label_query)

    @register_handler("summarize_content")
    async def summarize_content(job_id: int, payload: dict) -> None:
        from anthropic import RateLimitError

        from src.processors.summarizer import ContentSummarizer

        content_id = payload.get("content_id")
        if not content_id:
            raise ValueError("Missing content_id")

        await update_job_progress(job_id, 10, "Starting summarization")

        RATE_LIMIT_BACKOFF_DELAYS = [5, 10, 20]
        last_error: Exception | None = None

        for attempt, delay in enumerate([*RATE_LIMIT_BACKOFF_DELAYS, None], start=1):
            try:
                summarizer = ContentSummarizer()
                success = await _asyncio.to_thread(summarizer.summarize_content, content_id)

                if success:
                    await update_job_progress(job_id, 100, "Completed")
                    await reconcile_batch_job_status(job_id)
                    return
                else:
                    raise RuntimeError(
                        f"Summarization returned failure for content_id={content_id}"
                    )

            except RateLimitError as e:
                last_error = e
                if delay is not None:
                    logger.warning(
                        f"Rate limited on attempt {attempt} for content_id={content_id}, "
                        f"retrying in {delay}s"
                    )
                    await update_job_progress(
                        job_id, 10, f"Rate limited, retrying in {delay}s (attempt {attempt})"
                    )
                    await _asyncio.sleep(delay)
                else:
                    raise

            except Exception:
                raise

        if last_error:
            raise last_error

    @register_handler("ingest_content")
    async def ingest_content(job_id: int, payload: dict) -> None:
        from datetime import timedelta

        from src.ingestion.orchestrator import (
            ingest_gmail,
            ingest_perplexity_search,
            ingest_podcast,
            ingest_rss,
            ingest_substack,
            ingest_url,
            ingest_xsearch,
            ingest_youtube,
            ingest_youtube_playlist,
            ingest_youtube_rss,
        )

        source = payload.get("source", "gmail")
        # max_results=None means "use sources.d config defaults"
        max_results = payload.get("max_results")
        days_back = payload.get("days_back", 7)
        force_reprocess = payload.get("force_reprocess", False)

        await update_job_progress(job_id, 10, f"Starting {source} ingestion")

        after_date = datetime.now(UTC) - timedelta(days=days_back)

        # Build source-specific kwargs — only include max_results if explicitly set
        source_map: dict[str, tuple] = {
            "gmail": (
                ingest_gmail,
                {
                    **({"max_results": max_results} if max_results is not None else {}),
                    **({"query": payload["query"]} if "query" in payload else {}),
                },
            ),
            "rss": (
                ingest_rss,
                {**({"max_entries_per_feed": max_results} if max_results is not None else {})},
            ),
            "youtube": (
                ingest_youtube,
                {
                    **({"max_videos": max_results} if max_results is not None else {}),
                    "use_oauth": not payload.get("public_only"),
                },
            ),
            "youtube-playlist": (
                ingest_youtube_playlist,
                {**({"max_videos": max_results} if max_results is not None else {})},
            ),
            "youtube-rss": (
                ingest_youtube_rss,
                {**({"max_videos": max_results} if max_results is not None else {})},
            ),
            "podcast": (
                ingest_podcast,
                {**({"max_entries_per_feed": max_results} if max_results is not None else {})},
            ),
            "substack": (
                ingest_substack,
                {
                    **({"max_entries_per_source": max_results} if max_results is not None else {}),
                    **(
                        {"session_cookie": payload["session_cookie"]}
                        if "session_cookie" in payload
                        else {}
                    ),
                },
            ),
            "xsearch": (
                ingest_xsearch,
                {
                    **({"prompt": payload["prompt"]} if "prompt" in payload else {}),
                    **({"max_threads": payload["max_threads"]} if "max_threads" in payload else {}),
                },
            ),
            "perplexity": (
                ingest_perplexity_search,
                {
                    **({"prompt": payload["prompt"]} if "prompt" in payload else {}),
                    **({"max_results": max_results} if max_results is not None else {}),
                    **(
                        {"recency_filter": payload["recency_filter"]}
                        if "recency_filter" in payload
                        else {}
                    ),
                    **(
                        {"context_size": payload["context_size"]}
                        if "context_size" in payload
                        else {}
                    ),
                },
            ),
            "url": (
                ingest_url,
                {
                    "url": payload.get("url", ""),
                    **({"title": payload["title"]} if "title" in payload else {}),
                    **({"tags": payload["tags"]} if "tags" in payload else {}),
                    **({"notes": payload["notes"]} if "notes" in payload else {}),
                },
            ),
        }

        if source not in source_map:
            raise ValueError(f"Unsupported source: {source}")

        ingest_func, kwargs = source_map[source]

        # URL ingestion doesn't take after_date/force_reprocess
        if source == "url":
            count = await _asyncio.to_thread(lambda: ingest_func(**kwargs))
        else:
            count = await _asyncio.to_thread(
                lambda: ingest_func(
                    after_date=after_date,
                    force_reprocess=force_reprocess,
                    **kwargs,
                )
            )

        # ingest_url returns a result object, not a count
        if source == "url":
            count = 1 if count else 0

        await update_job_progress(job_id, 100, f"Ingested {count} items from {source}")

    @register_handler("run_pipeline")
    async def run_pipeline_handler(job_id: int, payload: dict) -> None:
        from src.pipeline.runner import run_pipeline

        pipeline_type = payload.get("pipeline_type", "daily")
        date = payload.get("date")
        sources = payload.get("sources")

        async def _on_progress(data: dict) -> None:
            stage = data.get("stage", "")
            status = data.get("status", "")
            message = data.get("message", f"{stage} {status}")
            progress_map = {
                ("ingestion", "started"): 10,
                ("ingestion", "completed"): 30,
                ("summarization", "started"): 35,
                ("summarization", "completed"): 70,
                ("digest", "started"): 75,
                ("digest", "completed"): 100,
            }
            pct = progress_map.get((stage, status), 50)
            await update_job_progress(job_id, pct, message)

        def _sync_progress(data: dict) -> None:
            _asyncio.get_event_loop().create_task(_on_progress(data))

        await run_pipeline(
            pipeline_type=pipeline_type,
            date=date,
            sources=sources,
            on_progress=_sync_progress,
        )


def _register_reference_handlers() -> None:
    """Register reference resolution handlers."""

    @register_handler("resolve_references")
    async def _handle_resolve_references(job_id: int, payload: dict) -> None:
        from src.services.reference_resolver import ReferenceResolver
        from src.storage.database import get_db

        content_id = payload.get("content_id")
        batch_size = payload.get("batch_size", 100)

        with get_db() as db:
            resolver = ReferenceResolver(db)
            if content_id:
                resolved = resolver.resolve_for_content(content_id)
            else:
                resolved = resolver.resolve_batch(batch_size)

        logger.info("Resolved %d references (job_id=%d)", resolved, job_id)


def _register_agent_handlers() -> None:
    """Register handlers for agent task execution."""

    @register_handler("execute_agent_task")
    async def execute_agent_task(job_id: int, payload: dict) -> None:
        """Execute an agent task through the conductor lifecycle."""
        from src.agents.approval.gates import ApprovalGate
        from src.agents.conductor import Conductor
        from src.agents.memory.provider import MemoryProvider
        from src.agents.registry import SpecialistRegistry
        from src.services.agent_service import AgentInsightService, AgentTaskService
        from src.services.llm_router import LLMRouter
        from src.storage.database import get_db

        task_id = payload["task_id"]
        task_type = payload.get("task_type", "research")
        persona = payload.get("persona", "default")
        prompt = payload.get("prompt", "")

        # Update task to PLANNING
        with get_db() as db:
            svc = AgentTaskService(db)
            svc.update_task_status(task_id, "planning")

        try:
            # Build conductor with real dependencies
            from src.config import get_model_config

            llm_router = LLMRouter(get_model_config())
            registry = SpecialistRegistry.create_default(llm_router)
            memory_provider = MemoryProvider(
                strategies={}
            )  # Empty until memory backends configured
            approval_gate = ApprovalGate()
            conductor = Conductor(
                registry=registry,
                memory_provider=memory_provider,
                approval_gate=approval_gate,
                llm_router=llm_router,
            )

            result = await conductor.execute_task(
                task_id=task_id,
                task_type=task_type,
                prompt=prompt,
                persona=persona,
            )

            # Persist results
            with get_db() as db:
                task_svc = AgentTaskService(db)
                task_svc.update_task_status(
                    task_id,
                    status=result.status,
                    result=result.result,
                    error=result.error,
                    cost=result.cost_total,
                    tokens=result.tokens_total,
                    persona_config=result.persona_snapshot,
                )

                # Store insights
                insight_svc = AgentInsightService(db)
                for insight in result.insights:
                    insight_svc.create_insight(
                        task_id=task_id,
                        insight_type=insight.get("type", "summary"),
                        title=insight.get("title", "Untitled"),
                        content=insight.get("content", ""),
                        confidence=insight.get("confidence", 0.0),
                        tags=[insight.get("type", "summary")],
                    )

            logger.info(
                "Agent task %s completed: status=%s, insights=%d, cost=$%.4f",
                task_id,
                result.status,
                len(result.insights),
                result.cost_total,
            )

        except Exception as e:
            logger.exception("Agent task %s failed: %s", task_id, e)
            with get_db() as db:
                svc = AgentTaskService(db)
                svc.update_task_status(task_id, "failed", error="Failed due to an internal error")
            raise
