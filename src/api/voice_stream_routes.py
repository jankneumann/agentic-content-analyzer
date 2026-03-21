"""
WebSocket Voice Streaming Endpoint

Streams audio from the browser to a cloud STT provider and returns
transcript results in real-time.

Protocol:
- Client sends binary audio chunks (PCM 16-bit mono 16kHz)
- Server sends JSON messages: { type, text, cleaned, confidence? }
- Auth via X-Admin-Key query parameter in WebSocket handshake
"""

import asyncio
import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from src.config.models import ModelStep, get_model_config
from src.services.cloud_stt import CloudSTTService
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["voice"])


def _verify_ws_auth(api_key: str | None) -> bool:
    """Verify WebSocket authentication via query parameter.

    Uses the same admin key comparison as REST endpoints.
    In development mode, allows access without auth.
    """
    import secrets as secrets_mod

    from src.config.settings import get_settings

    settings = get_settings()

    # If key is provided and admin key is configured, validate
    if api_key and settings.admin_api_key:
        return secrets_mod.compare_digest(api_key, settings.admin_api_key)

    # Dev mode: allow without auth; production without key: reject
    return settings.is_development


@router.websocket("/ws/voice/stream")
async def voice_stream(
    websocket: WebSocket,
    api_key: str | None = Query(None, alias="X-Admin-Key"),
):
    """WebSocket endpoint for real-time voice transcription.

    Query Parameters:
        X-Admin-Key: Admin API key for authentication
        language: BCP-47 language tag or "auto" (default: "auto")

    Client → Server: Binary audio chunks (PCM 16-bit mono 16kHz)
    Server → Client: JSON messages with transcript results

    Message format:
        {
            "type": "interim" | "final" | "error",
            "text": "transcript text",
            "cleaned": true/false,
            "confidence": 0.0-1.0 (optional, final only)
        }
    """
    # Authenticate
    if not _verify_ws_auth(api_key):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()

    # Resolve cloud STT provider from pipeline config
    try:
        config = get_model_config()
        model_id = config.get_model_for_step(ModelStep.CLOUD_STT)
        model_info = config.get_model_info(model_id)
        logger.info(
            "Cloud STT stream starting (model=%s, family=%s)",
            model_id,
            model_info.family,
        )
    except Exception:
        await websocket.send_json(
            {"type": "error", "text": "Model configuration error", "cleaned": False}
        )
        await websocket.close(code=4002, reason="Configuration error")
        return

    # Create provider
    service = CloudSTTService()
    try:
        provider = service.create_provider()
    except ValueError:
        await websocket.send_json(
            {"type": "error", "text": "Provider initialization failed", "cleaned": False}
        )
        await websocket.close(code=4003, reason="Provider error")
        return

    # Get language from query params
    language = websocket.query_params.get("language", "auto")

    # Start streaming
    forward_task: asyncio.Task | None = None  # type: ignore[type-arg]
    try:
        await provider.start_stream(language=language)

        # Task to forward results from provider to WebSocket
        async def forward_results():
            try:
                async for result in provider.get_results():
                    msg = {
                        "type": result.type.value,
                        "text": result.text,
                        "cleaned": result.cleaned,
                    }
                    if result.confidence is not None:
                        msg["confidence"] = result.confidence
                    await websocket.send_text(json.dumps(msg))
            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.error("Error forwarding STT results: %s", e)

        # Start result forwarding in background
        forward_task = asyncio.create_task(forward_results())

        # Receive audio chunks from client
        try:
            while True:
                data = await websocket.receive_bytes()
                await provider.send_audio(data)
        except WebSocketDisconnect:
            logger.debug("Client disconnected from voice stream")
        except Exception as e:
            logger.error("Error receiving audio: %s", e)

    finally:
        # Clean shutdown
        try:
            await provider.stop_stream()
        except Exception as e:
            logger.debug("Provider stop error: %s", e)

        # Wait for result forwarding to finish
        if forward_task and not forward_task.done():
            forward_task.cancel()
            try:
                await forward_task
            except asyncio.CancelledError:
                pass

        logger.debug("Voice stream session ended")
