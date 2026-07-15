"""Durable podcast-script workflow."""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any, cast

from sqlalchemy.orm import Session

from src.contracts.workflow_models import PodcastScriptRequest
from src.models.jobs import ResourceReference
from src.models.podcast import (
    PodcastLength,
    PodcastRequest,
    PodcastScriptRecord,
    PodcastStatus,
)
from src.processors.podcast_script_generator import PodcastScriptGenerator
from src.services.operation_service import OperationService
from src.storage.database import get_db
from src.workflows.resource import recover_owned_resource


class PodcastScriptWorkflow:
    """Reserve and persist one provenance-constrained podcast script."""

    def __init__(
        self,
        *,
        operation_service: OperationService | Any | None = None,
        generator: PodcastScriptGenerator | Any | None = None,
        session_factory: Callable[[], AbstractContextManager[Session]] = get_db,
    ) -> None:
        self.operations = operation_service or OperationService()
        self.generator = generator or PodcastScriptGenerator()
        self.session_factory = session_factory

    async def execute(
        self,
        operation_id: str | int,
        request: PodcastScriptRequest,
    ) -> PodcastScriptRecord:
        existing = await self._existing(operation_id)
        if existing is not None and existing.status not in {
            PodcastStatus.SCRIPT_GENERATING,
            PodcastStatus.FAILED,
        }:
            await self._attach_result(operation_id, existing)
            return existing
        if existing is None:
            with self.session_factory() as db:
                record = PodcastScriptRecord(
                    operation_id=int(operation_id),
                    digest_id=request.digest_id,
                    length=request.length,
                    status=PodcastStatus.SCRIPT_GENERATING,
                )
                db.add(record)
                db.commit()
                db.refresh(record)
                record_id = cast(int, record.id)
            await self.operations.attach_resource(
                operation_id,
                ResourceReference(
                    type="podcast_script",
                    id=str(record_id),
                    url=f"/api/v1/scripts/{record_id}",
                ),
            )
        else:
            record_id = cast(int, existing.id)
            with self.session_factory() as db:
                loaded = db.get(PodcastScriptRecord, record_id)
                if loaded is None:
                    raise RuntimeError("Attached podcast script resource does not exist")
                record = loaded
                record.status = PodcastStatus.SCRIPT_GENERATING
                record.error_message = None
                db.commit()

        started = time.monotonic()
        try:
            await self.operations.update_progress(operation_id, 20, "Generating podcast script")
            script, metadata = await self.generator.generate_script(
                PodcastRequest(
                    digest_id=request.digest_id,
                    length=PodcastLength(request.length),
                    enable_web_search=request.enable_web_search,
                    custom_focus_topics=request.custom_focus_topics or [],
                    custom_instructions=request.custom_instructions,
                )
            )
            with self.session_factory() as db:
                loaded = db.get(PodcastScriptRecord, record_id)
                if loaded is None:
                    raise RuntimeError(f"Reserved podcast script {record_id} disappeared")
                record = loaded
                record.script_json = script.model_dump(mode="json")
                record.title = script.title
                record.word_count = script.word_count
                record.estimated_duration_seconds = script.estimated_duration_seconds
                record.status = PodcastStatus.SCRIPT_PENDING_REVIEW
                record.newsletter_ids_available = [
                    item.get("id") for item in script.sources_summary
                ]
                record.newsletter_ids_fetched = metadata.content_ids_fetched
                record.source_content_ids_available = list(self.generator.available_content_ids)
                record.source_content_ids_cited = list(self.generator.cited_content_ids)
                record.selection_fingerprint = self.generator.selection_fingerprint
                record.web_search_queries = metadata.web_searches
                record.tool_call_count = metadata.tool_call_count
                record.model_used = self.generator.model_used
                record.model_version = self.generator.model_version
                record.token_usage = {
                    "input_tokens": self.generator.input_tokens,
                    "output_tokens": self.generator.output_tokens,
                }
                record.processing_time_seconds = int(time.monotonic() - started)
                db.commit()
                db.refresh(record)
        except Exception as exc:
            with self.session_factory() as db:
                failed = db.get(PodcastScriptRecord, record_id)
                if failed is not None:
                    failed.status = PodcastStatus.FAILED
                    failed.error_message = str(exc)
                    db.commit()
            raise
        await self._attach_result(operation_id, record)
        return cast(PodcastScriptRecord, record)

    async def _existing(self, operation_id: str | int) -> PodcastScriptRecord | None:
        return await recover_owned_resource(
            operations=self.operations,
            session_factory=self.session_factory,
            model=PodcastScriptRecord,
            operation_id=operation_id,
            resource_type="podcast_script",
            resource_url=lambda record_id: f"/api/v1/scripts/{record_id}",
        )

    async def _attach_result(self, operation_id: str | int, record: PodcastScriptRecord) -> None:
        await self.operations.attach_result(
            operation_id,
            {"script_id": record.id, "selection_fingerprint": record.selection_fingerprint},
        )
        await self.operations.update_progress(operation_id, 100, "Podcast script complete")
