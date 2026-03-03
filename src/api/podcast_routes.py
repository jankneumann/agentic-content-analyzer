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

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.api.dependencies import verify_admin_key
from src.models.podcast import (
    Podcast,
    PodcastScriptRecord,
    PodcastStatus,
    VoicePersona,
    VoiceProvider,
)
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/podcasts",
    tags=["podcasts"],
)

# Allowed sort fields for podcast listing
PODCAST_SORT_FIELDS = {
    "id",
    "script_id",
    "status",
    "duration_seconds",
    "file_size_bytes",
    "created_at",
}


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
                db.query(PodcastScriptRecord).filter(PodcastScriptRecord.id == script_id).first()
            )

            if not script_record or not script_record.script_json:
                raise ValueError(f"Script {script_id} not found or has no content")

            # Update script status
            script_record.status = PodcastStatus.AUDIO_GENERATING.value
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

        # Create output directory (fast local I/O, acceptable in async context)
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
                db.query(PodcastScriptRecord).filter(PodcastScriptRecord.id == script_id).first()
            )
            script_record.status = PodcastStatus.COMPLETED.value
            db.commit()

        logger.info(f"Audio generation completed for podcast {podcast_id}")

    except Exception as e:
        logger.error(f"Audio generation failed: {e}", exc_info=True)
        with get_db() as db:
            podcast = db.query(Podcast).filter(Podcast.id == podcast_id).first()
            if podcast:
                podcast.status = "failed"
                podcast.error_message = "Audio generation failed due to an internal error."

            script_record = (
                db.query(PodcastScriptRecord).filter(PodcastScriptRecord.id == script_id).first()
            )
            if script_record:
                script_record.status = PodcastStatus.FAILED.value
                script_record.error_message = "Audio generation failed due to an internal error."

            db.commit()


# --- Endpoints ---


@router.get("/", response_model=list[PodcastListItem])
async def list_podcasts(
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
) -> list[PodcastListItem]:
    """List podcasts with optional filtering."""
    with get_db() as db:
        query = db.query(Podcast, PodcastScriptRecord).join(
            PodcastScriptRecord, Podcast.script_id == PodcastScriptRecord.id
        )

        if status:
            query = query.filter(Podcast.status == status)

        # Apply dynamic sorting
        if sort_by not in PODCAST_SORT_FIELDS:
            sort_by = "created_at"

        sort_column = getattr(Podcast, sort_by, Podcast.created_at)
        if sort_order.lower() == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        results = query.offset(offset).limit(limit).all()

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
    from sqlalchemy import func

    with get_db() as db:
        # Group by status to get counts in a single query
        status_counts = (
            db.query(Podcast.status, func.count(Podcast.id)).group_by(Podcast.status).all()
        )
        status_map = {status: count for status, count in status_counts}

        # Calculate total from status counts (status is non-nullable)
        total = sum(status_map.values())

        # Group by voice provider for provider counts
        provider_counts = (
            db.query(Podcast.voice_provider, func.count(Podcast.id))
            .filter(Podcast.voice_provider.isnot(None))
            .group_by(Podcast.voice_provider)
            .all()
        )
        by_provider = {provider: count for provider, count in provider_counts}

        # Calculate total duration (single scalar query)
        total_duration = (
            db.query(func.sum(Podcast.duration_seconds))
            .filter(Podcast.status == "completed")
            .scalar()
        ) or 0

        return PodcastStatistics(
            total=total,
            generating=status_map.get("generating", 0),
            completed=status_map.get("completed", 0),
            failed=status_map.get("failed", 0),
            total_duration_seconds=total_duration,
            by_voice_provider=by_provider,
        )


@router.get("/approved-scripts", response_model=list[dict])
async def list_approved_scripts(
    limit: int = Query(20, ge=1, le=50, description="Maximum results"),
) -> list[dict]:
    """List approved scripts ready for audio generation."""
    with get_db() as db:
        scripts = (
            db.query(PodcastScriptRecord)
            .filter(PodcastScriptRecord.status == PodcastStatus.SCRIPT_APPROVED.value)
            .order_by(PodcastScriptRecord.approved_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": s.id,
                "digest_id": s.digest_id,
                "title": s.title,
                "length": s.length,
                "word_count": s.word_count,
                "estimated_duration_seconds": s.estimated_duration_seconds,
                "approved_at": s.approved_at.isoformat() if s.approved_at else None,
            }
            for s in scripts
        ]


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
            length=script.length,
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


@router.post("/generate", response_model=dict, dependencies=[Depends(verify_admin_key)])
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

        if script.status != PodcastStatus.SCRIPT_APPROVED.value:
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
    """Stream or download podcast audio file.

    Serves audio from the configured storage provider (local, S3, or Supabase).
    For cloud storage with signed URL support, redirects to the signed URL.
    """
    from fastapi.responses import RedirectResponse, StreamingResponse

    from src.services.file_storage import get_storage

    with get_db() as db:
        podcast = db.query(Podcast).filter(Podcast.id == podcast_id).first()

        if not podcast:
            raise HTTPException(status_code=404, detail="Podcast not found")

        if podcast.status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Audio not ready. Status: {podcast.status}",
            )

        if not podcast.audio_url:
            raise HTTPException(status_code=404, detail="Audio file not found")

        audio_path = podcast.audio_url

    # Get storage provider for podcasts bucket
    storage = get_storage(bucket="podcasts")

    # Check if file exists
    if not await storage.exists(audio_path):
        # Try legacy local path for backward compatibility
        if os.path.exists(audio_path):
            return FileResponse(
                audio_path,
                media_type="audio/mpeg",
                filename=f"podcast_{podcast_id}.mp3",
            )
        raise HTTPException(status_code=404, detail="Audio file not found")

    # For cloud providers with signed URL support, redirect to signed URL
    if hasattr(storage, "get_signed_url") and storage.provider_name in ("s3", "supabase"):
        signed_url = await storage.get_signed_url(audio_path, expires_in=3600)
        return RedirectResponse(url=signed_url, status_code=302)

    # For local storage, stream the file
    audio_data = await storage.get(audio_path)
    return StreamingResponse(
        iter([audio_data]),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": f'attachment; filename="podcast_{podcast_id}.mp3"',
            "Content-Length": str(len(audio_data)),
        },
    )
