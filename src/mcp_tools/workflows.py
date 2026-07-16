"""Canonical durable workflow mutation tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from src.contracts.workflow_models import (
    AudioDigestRequest,
    DigestCreateRequest,
    OperationHandle,
    PipelineRequest,
    PodcastAudioRequest,
    PodcastScriptRequest,
    SummarizationRequest,
    ThemeAnalysisRequest,
)
from src.mcp_tools import runtime
from src.models.jobs import OperationType
from src.services.operation_service import OperationService

_CLIENT_METHODS = {
    OperationType.SUMMARIZATION_RUN: "submit_summarization",
    OperationType.THEME_ANALYSIS_CREATE: "submit_theme_analysis",
    OperationType.DIGEST_CREATE: "submit_digest",
    OperationType.PIPELINE_RUN: "submit_pipeline",
    OperationType.PODCAST_SCRIPT_CREATE: "submit_podcast_script",
    OperationType.PODCAST_AUDIO_CREATE: "submit_podcast_audio",
    OperationType.AUDIO_DIGEST_CREATE: "submit_audio_digest",
}


async def _submit(
    request: BaseModel,
    operation_type: OperationType,
    idempotency_key: str | None,
) -> dict[str, Any]:
    payload = request.model_dump(mode="json", exclude_none=True)
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        client = runtime.create_workflow_client()
        try:
            method = getattr(client, _CLIENT_METHODS[operation_type])
            return runtime.native_dict(method(payload, idempotency_key=idempotency_key))
        finally:
            client.close()
    handle = await OperationService().submit(
        operation_type,
        payload,
        idempotency_key=idempotency_key,
    )
    return runtime.native_dict(OperationHandle.model_validate(handle.model_dump(mode="json")))


@runtime.tool_boundary
async def summarize_pending(
    content_ids: list[int] | None = None,
    query: dict[str, Any] | None = None,
    force_reprocess: bool = False,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Queue canonical summarization over IDs or a content query."""
    return await _submit(
        SummarizationRequest(
            content_ids=content_ids,
            query=query,
            force_reprocess=force_reprocess,
        ),
        OperationType.SUMMARIZATION_RUN,
        idempotency_key,
    )


@runtime.tool_boundary
async def analyze_themes(
    query: dict[str, Any],
    max_themes: int = 10,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Queue theme analysis over an explicit immutable content query."""
    return await _submit(
        ThemeAnalysisRequest(query=query, max_themes=max_themes),
        OperationType.THEME_ANALYSIS_CREATE,
        idempotency_key,
    )


@runtime.tool_boundary
async def create_digest(
    digest_type: Literal["daily", "weekly"],
    period_start: str,
    period_end: str,
    query: dict[str, Any] | None = None,
    include_historical_context: bool = True,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Queue persisted daily or weekly digest generation."""
    return await _submit(
        DigestCreateRequest(
            digest_type=digest_type,
            period_start=period_start,
            period_end=period_end,
            query=query,
            include_historical_context=include_historical_context,
        ),
        OperationType.DIGEST_CREATE,
        idempotency_key,
    )


@runtime.tool_boundary
async def run_pipeline(
    period: Literal["daily", "weekly"],
    period_start: str,
    period_end: str,
    sources: list[str] | None = None,
    continue_on_source_error: bool = True,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Queue the universal ingestion-to-digest pipeline."""
    return await _submit(
        PipelineRequest(
            period=period,
            period_start=period_start,
            period_end=period_end,
            sources=sources,
            continue_on_source_error=continue_on_source_error,
        ),
        OperationType.PIPELINE_RUN,
        idempotency_key,
    )


@runtime.tool_boundary
async def generate_podcast_script(
    digest_id: int,
    length: Literal["brief", "standard", "extended"] = "standard",
    enable_web_search: bool = True,
    custom_focus_topics: list[str] | None = None,
    custom_instructions: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Queue a persisted podcast script for a digest."""
    return await _submit(
        PodcastScriptRequest(
            digest_id=digest_id,
            length=length,
            enable_web_search=enable_web_search,
            custom_focus_topics=custom_focus_topics,
            custom_instructions=custom_instructions,
        ),
        OperationType.PODCAST_SCRIPT_CREATE,
        idempotency_key,
    )


@runtime.tool_boundary
async def generate_podcast_audio(
    script_id: int,
    voice_provider: Literal["elevenlabs", "google_tts", "aws_polly", "openai_tts"] = "openai_tts",
    alex_voice: Literal["alex_male", "alex_female"] = "alex_male",
    sam_voice: Literal["sam_male", "sam_female"] = "sam_female",
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Queue persisted podcast audio generation."""
    return await _submit(
        PodcastAudioRequest(
            script_id=script_id,
            voice_provider=voice_provider,
            alex_voice=alex_voice,
            sam_voice=sam_voice,
        ),
        OperationType.PODCAST_AUDIO_CREATE,
        idempotency_key,
    )


@runtime.tool_boundary
async def generate_audio_digest(
    digest_id: int,
    provider: str = "openai",
    voice: str = "nova",
    speed: float = 1.0,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Queue persisted single-voice audio digest generation."""
    return await _submit(
        AudioDigestRequest(
            digest_id=digest_id,
            provider=provider,
            voice=voice,
            speed=speed,
        ),
        OperationType.AUDIO_DIGEST_CREATE,
        idempotency_key,
    )


TOOLS = (
    summarize_pending,
    analyze_themes,
    create_digest,
    run_pipeline,
    generate_podcast_script,
    generate_podcast_audio,
    generate_audio_digest,
)
