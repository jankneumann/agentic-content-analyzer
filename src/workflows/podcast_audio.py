"""Durable podcast-audio workflow."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.orm import Session

from src.contracts.workflow_models import PodcastAudioRequest
from src.models.jobs import ResourceReference
from src.models.podcast import (
    Podcast,
    PodcastScript,
    PodcastScriptRecord,
    PodcastStatus,
    VoicePersona,
    VoiceProvider,
)
from src.services.operation_service import OperationService
from src.services.podcast_audio_service import PodcastAudioService
from src.storage.database import get_db
from src.workflows.resource import recover_owned_resource


class PodcastAudioWorkflow:
    """Generate audio only from one approved persisted script."""

    def __init__(
        self,
        *,
        operation_service: OperationService | Any | None = None,
        audio_service: PodcastAudioService | Any | None = None,
        session_factory: Callable[[], AbstractContextManager[Session]] = get_db,
    ) -> None:
        self.operations = operation_service or OperationService()
        self.audio_service = audio_service or PodcastAudioService()
        self.session_factory = session_factory

    async def execute(self, operation_id: str | int, request: PodcastAudioRequest) -> Podcast:
        existing = await self._existing(operation_id)
        if existing is not None and existing.status == "completed":
            await self._attach_result(operation_id, existing)
            return existing
        with self.session_factory() as db:
            script_record = db.get(PodcastScriptRecord, request.script_id)
            if script_record is None or script_record.status != PodcastStatus.SCRIPT_APPROVED:
                raise ValueError(f"Podcast script {request.script_id} must be approved")
            if not script_record.script_json:
                raise ValueError(f"Podcast script {request.script_id} has no content")
            script = PodcastScript.model_validate(script_record.script_json)
            if existing is None:
                record = Podcast(
                    operation_id=int(operation_id),
                    script_id=request.script_id,
                    voice_provider=request.voice_provider,
                    alex_voice=request.alex_voice,
                    sam_voice=request.sam_voice,
                    status="generating",
                )
                db.add(record)
                db.commit()
                db.refresh(record)
                record_id = cast(int, record.id)
            else:
                loaded = db.get(Podcast, cast(int, existing.id))
                if loaded is None:
                    raise RuntimeError("Attached podcast resource does not exist")
                record = loaded
                record.status = "generating"
                record.error_message = None
                db.commit()
                record_id = cast(int, record.id)
        if existing is None:
            await self.operations.attach_resource(
                operation_id,
                ResourceReference(
                    type="podcast", id=str(record_id), url=f"/api/v1/podcasts/{record_id}"
                ),
            )

        try:
            await self.operations.update_progress(operation_id, 20, "Generating podcast audio")
            artifact = await self.audio_service.generate(
                script,
                podcast_id=record_id,
                provider=VoiceProvider(request.voice_provider),
                alex_voice=VoicePersona(request.alex_voice),
                sam_voice=VoicePersona(request.sam_voice),
                speed=1.0,
            )
            with self.session_factory() as db:
                loaded = db.get(Podcast, record_id)
                if loaded is None:
                    raise RuntimeError(f"Reserved podcast {record_id} disappeared")
                record = loaded
                record.audio_url = artifact.storage_path
                record.audio_format = artifact.audio_format
                record.duration_seconds = artifact.duration_seconds
                record.file_size_bytes = artifact.file_size_bytes
                record.voice_config = artifact.voice_config
                record.status = "completed"
                record.completed_at = datetime.now(UTC)
                db.commit()
                db.refresh(record)
        except Exception as exc:
            with self.session_factory() as db:
                failed = db.get(Podcast, record_id)
                if failed is not None:
                    failed.status = "failed"
                    failed.error_message = str(exc)
                    db.commit()
            raise
        await self._attach_result(operation_id, record)
        return cast(Podcast, record)

    async def _existing(self, operation_id: str | int) -> Podcast | None:
        return await recover_owned_resource(
            operations=self.operations,
            session_factory=self.session_factory,
            model=Podcast,
            operation_id=operation_id,
            resource_type="podcast",
            resource_url=lambda record_id: f"/api/v1/podcasts/{record_id}",
        )

    async def _attach_result(self, operation_id: str | int, record: Podcast) -> None:
        await self.operations.attach_result(operation_id, {"podcast_id": record.id})
        await self.operations.update_progress(operation_id, 100, "Podcast audio complete")
