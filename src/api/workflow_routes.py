"""Canonical job-backed workflow submission routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel

from src.api.workflow_dependencies import get_operation_service
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
from src.models.jobs import OperationType
from src.services.operation_service import OperationService

router = APIRouter(prefix="/api/v1", tags=["workflows"])


async def _submit(
    request: BaseModel,
    operation_type: OperationType,
    idempotency_key: str | None,
    service: OperationService,
) -> OperationHandle:
    handle = await service.submit(
        operation_type,
        request.model_dump(mode="json", exclude_none=True),
        idempotency_key=idempotency_key,
    )
    return OperationHandle.model_validate(handle.model_dump(mode="json"))


@router.post("/summarization-runs", response_model=OperationHandle, status_code=202)
async def submit_summarization(
    request: SummarizationRequest,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=8, max_length=200)
    ] = None,
    service: OperationService = Depends(get_operation_service),
) -> OperationHandle:
    return await _submit(request, OperationType.SUMMARIZATION_RUN, idempotency_key, service)


@router.post("/theme-analyses", response_model=OperationHandle, status_code=202)
async def submit_theme_analysis(
    request: ThemeAnalysisRequest,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=8, max_length=200)
    ] = None,
    service: OperationService = Depends(get_operation_service),
) -> OperationHandle:
    return await _submit(request, OperationType.THEME_ANALYSIS_CREATE, idempotency_key, service)


@router.post("/digests", response_model=OperationHandle, status_code=202)
async def submit_digest(
    request: DigestCreateRequest,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=8, max_length=200)
    ] = None,
    service: OperationService = Depends(get_operation_service),
) -> OperationHandle:
    return await _submit(request, OperationType.DIGEST_CREATE, idempotency_key, service)


@router.post("/pipeline-runs", response_model=OperationHandle, status_code=202)
async def submit_pipeline(
    request: PipelineRequest,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=8, max_length=200)
    ] = None,
    service: OperationService = Depends(get_operation_service),
) -> OperationHandle:
    return await _submit(request, OperationType.PIPELINE_RUN, idempotency_key, service)


@router.post("/podcast-scripts", response_model=OperationHandle, status_code=202)
async def submit_podcast_script(
    request: PodcastScriptRequest,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=8, max_length=200)
    ] = None,
    service: OperationService = Depends(get_operation_service),
) -> OperationHandle:
    return await _submit(request, OperationType.PODCAST_SCRIPT_CREATE, idempotency_key, service)


@router.post("/podcasts", response_model=OperationHandle, status_code=202)
async def submit_podcast_audio(
    request: PodcastAudioRequest,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=8, max_length=200)
    ] = None,
    service: OperationService = Depends(get_operation_service),
) -> OperationHandle:
    return await _submit(request, OperationType.PODCAST_AUDIO_CREATE, idempotency_key, service)


@router.post("/audio-digests", response_model=OperationHandle, status_code=status.HTTP_202_ACCEPTED)
async def submit_audio_digest(
    request: AudioDigestRequest,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=8, max_length=200)
    ] = None,
    service: OperationService = Depends(get_operation_service),
) -> OperationHandle:
    return await _submit(request, OperationType.AUDIO_DIGEST_CREATE, idempotency_key, service)
