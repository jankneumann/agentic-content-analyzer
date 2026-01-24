"""Audio digest API endpoints.

Provides REST endpoints for:
- Creating audio digests from digests (background task)
- Listing audio digests for a digest
- Getting audio digest details
- Streaming audio files
"""

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response

from src.models.audio_digest import (
    AudioDigest,
    AudioDigestCreate,
    AudioDigestListItem,
    AudioDigestResponse,
    AudioDigestStatus,
)
from src.models.digest import Digest
from src.processors.audio_digest_generator import AudioDigestGenerator
from src.services.file_storage import get_storage
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["audio-digests"])


async def _generate_audio_digest_task(
    audio_digest_id: int,
    digest_id: int,
    voice: str,
    speed: float,
    provider: str,
) -> None:
    """Background task for audio generation.

    Creates an AudioDigestGenerator and generates audio for the digest.
    The generator handles status updates on success/failure.

    Args:
        audio_digest_id: ID of the AudioDigest record to update
        digest_id: ID of the Digest to generate audio from
        voice: Voice preset or ID to use
        speed: Speech speed multiplier
        provider: TTS provider name
    """
    try:
        logger.info(
            f"Starting audio digest generation for digest {digest_id} "
            f"(audio_digest_id={audio_digest_id})"
        )

        # Update status to processing
        with get_db() as db:
            audio_digest = db.query(AudioDigest).filter(AudioDigest.id == audio_digest_id).first()
            if audio_digest:
                audio_digest.status = AudioDigestStatus.PROCESSING
                db.commit()

        # Create generator and generate audio
        # Note: The generator creates its own AudioDigest record, so we need to
        # update our existing record instead
        generator = AudioDigestGenerator(
            provider=provider,
            voice=voice,
            speed=speed,
        )

        # Load digest and prepare text
        with get_db() as db:
            digest = db.query(Digest).filter(Digest.id == digest_id).first()
            if not digest:
                raise ValueError(f"Digest {digest_id} not found")

            # Prepare text from digest
            prepared_text = generator.text_preparer.prepare_digest(digest)
            text_char_count = len(prepared_text)

        # Resolve voice ID and synthesize
        from src.config import settings

        voice_id = settings.get_audio_digest_voice_id(voice)

        # Import chunk threshold from generator
        from src.processors.audio_digest_generator import SINGLE_CHUNK_THRESHOLD

        if text_char_count <= SINGLE_CHUNK_THRESHOLD:
            audio_bytes, chunk_count = await generator._synthesize_short(prepared_text, voice_id)
        else:
            audio_bytes, chunk_count = await generator._synthesize_long(prepared_text, voice_id)

        # Upload to storage
        storage = get_storage(bucket="audio-digests")
        filename = f"audio_digest_{audio_digest_id}.mp3"
        storage_path = await storage.save(
            data=audio_bytes,
            filename=filename,
            content_type="audio/mpeg",
        )

        # Calculate duration estimate
        estimated_duration = generator.text_preparer.estimate_duration(prepared_text)

        # Update the existing record with success
        from datetime import UTC, datetime

        with get_db() as db:
            audio_digest = db.query(AudioDigest).filter(AudioDigest.id == audio_digest_id).first()
            if audio_digest:
                audio_digest.audio_url = storage_path
                audio_digest.duration_seconds = estimated_duration
                audio_digest.file_size_bytes = len(audio_bytes)
                audio_digest.text_char_count = text_char_count
                audio_digest.chunk_count = chunk_count
                audio_digest.status = AudioDigestStatus.COMPLETED
                audio_digest.completed_at = datetime.now(UTC)
                db.commit()

        logger.info(
            f"Audio digest {audio_digest_id} generated successfully: "
            f"{len(audio_bytes) / 1024:.1f} KB, ~{estimated_duration:.0f}s"
        )

    except Exception as e:
        logger.error(f"Audio digest {audio_digest_id} generation failed: {e}")
        # Update record with failure status
        with get_db() as db:
            audio_digest = db.query(AudioDigest).filter(AudioDigest.id == audio_digest_id).first()
            if audio_digest:
                audio_digest.status = AudioDigestStatus.FAILED
                audio_digest.error_message = str(e)
                db.commit()


@router.post("/digests/{digest_id}/audio", response_model=AudioDigestResponse)
async def create_audio_digest(
    digest_id: int,
    request: AudioDigestCreate,
    background_tasks: BackgroundTasks,
) -> AudioDigestResponse:
    """Generate an audio digest from a digest.

    The audio generation runs in the background. Poll the returned
    audio digest ID to check completion status.

    Args:
        digest_id: ID of the digest to generate audio from
        request: Audio generation configuration (voice, speed, provider)
        background_tasks: FastAPI background tasks handler

    Returns:
        AudioDigestResponse with status "pending"

    Raises:
        HTTPException: 404 if digest not found
    """
    with get_db() as db:
        # Verify digest exists
        digest = db.query(Digest).filter(Digest.id == digest_id).first()
        if not digest:
            raise HTTPException(status_code=404, detail=f"Digest {digest_id} not found")

        # Create pending audio digest record
        audio_digest = AudioDigest(
            digest_id=digest_id,
            voice=request.voice,
            speed=request.speed,
            provider=request.provider,
            status=AudioDigestStatus.PENDING,
        )
        db.add(audio_digest)
        db.commit()
        db.refresh(audio_digest)
        audio_digest_id = audio_digest.id
        response = AudioDigestResponse.model_validate(audio_digest)

    # Queue background task
    background_tasks.add_task(
        _generate_audio_digest_task,
        audio_digest_id,
        digest_id,
        request.voice,
        request.speed,
        request.provider,
    )

    logger.info(f"Queued audio digest generation for digest {digest_id}")
    return response


@router.get("/digests/{digest_id}/audio", response_model=list[AudioDigestListItem])
async def list_digest_audio(digest_id: int) -> list[AudioDigestListItem]:
    """List all audio digests for a given digest.

    Args:
        digest_id: ID of the digest to list audio for

    Returns:
        List of AudioDigestListItem with summary information
    """
    with get_db() as db:
        audio_digests = (
            db.query(AudioDigest)
            .filter(AudioDigest.digest_id == digest_id)
            .order_by(AudioDigest.created_at.desc())
            .all()
        )
        return [AudioDigestListItem.model_validate(ad) for ad in audio_digests]


@router.get("/audio-digests/{audio_digest_id}", response_model=AudioDigestResponse)
async def get_audio_digest(audio_digest_id: int) -> AudioDigestResponse:
    """Get details of a specific audio digest.

    Args:
        audio_digest_id: ID of the audio digest

    Returns:
        AudioDigestResponse with full details

    Raises:
        HTTPException: 404 if audio digest not found
    """
    with get_db() as db:
        audio_digest = db.query(AudioDigest).filter(AudioDigest.id == audio_digest_id).first()
        if not audio_digest:
            raise HTTPException(status_code=404, detail=f"Audio digest {audio_digest_id} not found")
        return AudioDigestResponse.model_validate(audio_digest)


@router.get("/audio-digests/{audio_digest_id}/stream")
async def stream_audio_digest(
    audio_digest_id: int,
    request: Request,
) -> Response:
    """Stream the audio file for an audio digest.

    Supports HTTP range requests for seeking.
    For cloud storage, redirects to a signed URL.

    Args:
        audio_digest_id: ID of the audio digest
        request: FastAPI Request object for headers

    Returns:
        FileResponse for local files, RedirectResponse for cloud storage

    Raises:
        HTTPException: 404 if audio digest or file not found
        HTTPException: 400 if audio digest not ready
    """
    with get_db() as db:
        audio_digest = db.query(AudioDigest).filter(AudioDigest.id == audio_digest_id).first()
        if not audio_digest:
            raise HTTPException(status_code=404, detail=f"Audio digest {audio_digest_id} not found")

        if audio_digest.status != AudioDigestStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Audio digest not ready (status: {audio_digest.status.value})",
            )

        if not audio_digest.audio_url:
            raise HTTPException(status_code=404, detail="Audio file not found")

        audio_url = audio_digest.audio_url

    # Get storage provider
    storage = get_storage(bucket="audio-digests")

    # For cloud storage with signed URLs, redirect
    if hasattr(storage, "get_signed_url"):
        try:
            signed_url = await storage.get_signed_url(audio_url)
            return RedirectResponse(url=signed_url, status_code=307)
        except Exception as e:
            logger.warning(f"Failed to get signed URL, falling back to local: {e}")

    # For local storage, resolve and serve the file
    if hasattr(storage, "_resolve_path"):
        file_path = storage._resolve_path(audio_url)
    else:
        # Fallback: treat audio_url as a path
        file_path = Path(audio_url)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    # Return file with proper headers for streaming
    return FileResponse(
        path=file_path,
        media_type="audio/mpeg",
        filename=f"audio_digest_{audio_digest_id}.mp3",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
        },
    )


@router.delete("/audio-digests/{audio_digest_id}")
async def delete_audio_digest(audio_digest_id: int) -> dict:
    """Delete an audio digest and its associated audio file.

    Args:
        audio_digest_id: ID of the audio digest to delete

    Returns:
        Confirmation message

    Raises:
        HTTPException: 404 if audio digest not found
    """
    with get_db() as db:
        audio_digest = db.query(AudioDigest).filter(AudioDigest.id == audio_digest_id).first()
        if not audio_digest:
            raise HTTPException(status_code=404, detail=f"Audio digest {audio_digest_id} not found")

        audio_url = audio_digest.audio_url

        # Delete the database record
        db.delete(audio_digest)
        db.commit()

    # Try to delete the audio file if it exists
    if audio_url:
        try:
            storage = get_storage(bucket="audio-digests")
            await storage.delete(audio_url)
            logger.info(f"Deleted audio file: {audio_url}")
        except Exception as e:
            logger.warning(f"Failed to delete audio file {audio_url}: {e}")

    return {"message": f"Audio digest {audio_digest_id} deleted"}
