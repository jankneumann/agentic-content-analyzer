"""API endpoints for podcast audio management.

Provides REST endpoints for:
- Podcast listing with filters
- Audio streaming/download
- Audio generation from approved scripts
- Podcast statistics
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from src.models.podcast import (
    AudioGenerationRequest,
    Podcast,
    PodcastScriptRecord,
    PodcastStatus,
    VoicePersona,
    VoiceProvider,
)
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/podcasts", tags=["podcasts"])


# --- Request/Response Models ---


class PodcastListItem(BaseModel):
    """Podcast summary for list views."""

    id: int
    script_id: int
    title: str | None
    digest_id: int | None
    length: str | None
    duration_seconds: int | None
    file_size_bytes: int | None
    audio_format: str
    voice_provider: str | None
    status: str
    created_at: str | None
    completed_at: str | None


class PodcastDetail(BaseModel):
    """Full podcast details."""

    id: int
    script_id: int
    title: str | None
    digest_id: int | None
    length: str | None
    word_count: int | None
    estimated_duration_seconds: int | None
    duration_seconds: int | None
    file_size_bytes: int | None
    audio_url: str | None
    audio_format: str
    voice_provider: str | None
    alex_voice: str | None
    sam_voice: str | None
    status: str
    error_message: str | None
    created_at: str | None
    completed_at: str | None


class PodcastStatistics(BaseModel):
    """Statistics about podcasts."""

    total: int
    generating: int
    completed: int
    failed: int
    total_duration_seconds: int
    by_voice_provider: dict


class GenerateAudioRequest(BaseModel):
    """Request to generate audio from an approved script."""

    script_id: int = Field(..., description="ID of the approved script")
    voice_provider: str = Field(default="openai_tts", description="TTS provider")
    alex_voice: str = Field(default="alex_male", description="Voice for Alex persona")
    sam_voice: str = Field(default="sam_female", description="Voice for Sam persona")


# --- Background Tasks ---


async def generate_audio_task(
    script_id: int,
    podcast_id: int,
    voice_provider: VoiceProvider,
    alex_voice: VoicePersona,
    sam_voice: VoicePersona,
) -> None:
    """Background task for audio generation."""
    logger.info(f"Starting audio generation for script {script_id}, podcast {podcast_id}")

    try:
        from src.delivery.audio_generator import PodcastAudioGenerator
        from src.models.podcast import PodcastScript

        # Get the script
        with get_db() as db:
            script_record = (
                db.query(PodcastScriptRecord)
                .filter(PodcastScriptRecord.id == script_id)
                .first()
            )

            if not script_record or not script_record.script_json:
                raise ValueError(f"Script {script_id} not found or has no content")

            # Update script status
            script_record.status = PodcastStatus.AUDIO_GENERATING
            db.commit()

            script_data = script_record.script_json

        # Parse script
        script = PodcastScript(**script_data)

        # Generate audio
        generator = PodcastAudioGenerator(
            provider=voice_provider,
            alex_voice=alex_voice,
            sam_voice=sam_voice,
        )

        # Create output directory
        output_dir = Path("output/podcasts")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"podcast_{podcast_id}.mp3"

        # Generate audio
        metadata = await generator.generate_podcast(script, str(output_path))

        # Update podcast record
        with get_db() as db:
            podcast = db.query(Podcast).filter(Podcast.id == podcast_id).first()
            podcast.audio_url = str(output_path)
            podcast.duration_seconds = metadata.duration_seconds
            podcast.file_size_bytes = metadata.file_size_bytes
            podcast.status = "completed"
            podcast.completed_at = datetime.utcnow()

            # Update script status
            script_record = (
                db.query(PodcastScriptRecord)
                .filter(PodcastScriptRecord.id == script_id)
                .first()
            )
            script_record.status = PodcastStatus.COMPLETED
            db.commit()

        logger.info(f"Audio generation completed for podcast {podcast_id}")

    except Exception as e:
        logger.error(f"Audio generation failed: {e}")
        with get_db() as db:
            podcast = db.query(Podcast).filter(Podcast.id == podcast_id).first()
            if podcast:
                podcast.status = "failed"
                podcast.error_message = str(e)

            script_record = (
                db.query(PodcastScriptRecord)
                .filter(PodcastScriptRecord.id == script_id)
                .first()
            )
            if script_record:
                script_record.status = PodcastStatus.FAILED
                script_record.error_message = str(e)

            db.commit()


# --- Endpoints ---


@router.get("/", response_model=List[PodcastListItem])
async def list_podcasts(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, le=100, description="Maximum results"),
    offset: int = Query(0, description="Offset for pagination"),
) -> List[PodcastListItem]:
    """List podcasts with optional filtering."""
    with get_db() as db:
        query = (
            db.query(Podcast, PodcastScriptRecord)
            .join(PodcastScriptRecord, Podcast.script_id == PodcastScriptRecord.id)
        )

        if status:
            query = query.filter(Podcast.status == status)

        results = (
            query.order_by(Podcast.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return [
            PodcastListItem(
                id=podcast.id,
                script_id=podcast.script_id,
                title=script.title,
                digest_id=script.digest_id,
                length=script.length,
                duration_seconds=podcast.duration_seconds,
                file_size_bytes=podcast.file_size_bytes,
                audio_format=podcast.audio_format or "mp3",
                voice_provider=podcast.voice_provider,
                status=podcast.status,
                created_at=podcast.created_at.isoformat() if podcast.created_at else None,
                completed_at=podcast.completed_at.isoformat() if podcast.completed_at else None,
            )
            for podcast, script in results
        ]


@router.get("/statistics", response_model=PodcastStatistics)
async def get_podcast_statistics() -> PodcastStatistics:
    """Get statistics about podcasts."""
    with get_db() as db:
        total = db.query(Podcast).count()

        def count_by_status(status: str) -> int:
            return db.query(Podcast).filter(Podcast.status == status).count()

        # Calculate total duration
        from sqlalchemy import func
        total_duration = (
            db.query(func.sum(Podcast.duration_seconds))
            .filter(Podcast.status == "completed")
            .scalar()
        ) or 0

        # Count by voice provider
        by_provider = {}
        for provider in VoiceProvider:
            count = (
                db.query(Podcast)
                .filter(Podcast.voice_provider == provider.value)
                .count()
            )
            if count > 0:
                by_provider[provider.value] = count

        return PodcastStatistics(
            total=total,
            generating=count_by_status("generating"),
            completed=count_by_status("completed"),
            failed=count_by_status("failed"),
            total_duration_seconds=total_duration,
            by_voice_provider=by_provider,
        )


@router.get("/{podcast_id}", response_model=PodcastDetail)
async def get_podcast(podcast_id: int) -> PodcastDetail:
    """Get full podcast details."""
    with get_db() as db:
        result = (
            db.query(Podcast, PodcastScriptRecord)
            .join(PodcastScriptRecord, Podcast.script_id == PodcastScriptRecord.id)
            .filter(Podcast.id == podcast_id)
            .first()
        )

        if not result:
            raise HTTPException(status_code=404, detail="Podcast not found")

        podcast, script = result

        return PodcastDetail(
            id=podcast.id,
            script_id=podcast.script_id,
            title=script.title,
            digest_id=script.digest_id,
            length=script.length.value if script.length else None,
            word_count=script.word_count,
            estimated_duration_seconds=script.estimated_duration_seconds,
            duration_seconds=podcast.duration_seconds,
            file_size_bytes=podcast.file_size_bytes,
            audio_url=podcast.audio_url,
            audio_format=podcast.audio_format or "mp3",
            voice_provider=podcast.voice_provider,
            alex_voice=podcast.alex_voice,
            sam_voice=podcast.sam_voice,
            status=podcast.status,
            error_message=podcast.error_message,
            created_at=podcast.created_at.isoformat() if podcast.created_at else None,
            completed_at=podcast.completed_at.isoformat() if podcast.completed_at else None,
        )


@router.post("/generate", response_model=dict)
async def generate_audio(
    request: GenerateAudioRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Generate audio from an approved script.

    Starts audio generation in background and returns immediately.
    Poll GET /podcasts/{podcast_id} for status.
    """
    logger.info(f"Received audio generation request for script {request.script_id}")

    # Validate script exists and is approved
    with get_db() as db:
        script = (
            db.query(PodcastScriptRecord)
            .filter(PodcastScriptRecord.id == request.script_id)
            .first()
        )

        if not script:
            raise HTTPException(status_code=404, detail="Script not found")

        if script.status != "script_approved":
            raise HTTPException(
                status_code=400,
                detail=f"Script must be approved before audio generation. Current status: {script.status}",
            )

        # Validate voice provider and personas
        try:
            voice_provider = VoiceProvider(request.voice_provider)
            alex_voice = VoicePersona(request.alex_voice)
            sam_voice = VoicePersona(request.sam_voice)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid voice configuration: {e}")

        # Create podcast record
        podcast = Podcast(
            script_id=request.script_id,
            audio_format="mp3",
            voice_provider=voice_provider.value,
            alex_voice=alex_voice.value,
            sam_voice=sam_voice.value,
            status="generating",
        )
        db.add(podcast)
        db.commit()
        db.refresh(podcast)
        podcast_id = podcast.id

    # Queue background task
    background_tasks.add_task(
        generate_audio_task,
        request.script_id,
        podcast_id,
        voice_provider,
        alex_voice,
        sam_voice,
    )

    return {
        "status": "queued",
        "message": "Audio generation started",
        "podcast_id": podcast_id,
        "script_id": request.script_id,
    }


@router.get("/{podcast_id}/audio")
async def stream_audio(podcast_id: int):
    """Stream or download podcast audio file."""
    with get_db() as db:
        podcast = db.query(Podcast).filter(Podcast.id == podcast_id).first()

        if not podcast:
            raise HTTPException(status_code=404, detail="Podcast not found")

        if podcast.status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Audio not ready. Status: {podcast.status}",
            )

        if not podcast.audio_url or not os.path.exists(podcast.audio_url):
            raise HTTPException(status_code=404, detail="Audio file not found")

        return FileResponse(
            podcast.audio_url,
            media_type="audio/mpeg",
            filename=f"podcast_{podcast_id}.mp3",
        )


@router.get("/approved-scripts", response_model=List[dict])
async def list_approved_scripts(
    limit: int = Query(20, le=50, description="Maximum results"),
) -> List[dict]:
    """List approved scripts ready for audio generation."""
    with get_db() as db:
        scripts = (
            db.query(PodcastScriptRecord)
            .filter(PodcastScriptRecord.status == PodcastStatus.SCRIPT_APPROVED)
            .order_by(PodcastScriptRecord.approved_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": s.id,
                "digest_id": s.digest_id,
                "title": s.title,
                "length": s.length.value if s.length else None,
                "word_count": s.word_count,
                "estimated_duration_seconds": s.estimated_duration_seconds,
                "approved_at": s.approved_at.isoformat() if s.approved_at else None,
            }
            for s in scripts
        ]
