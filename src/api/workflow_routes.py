"""Canonical job-backed workflow submission routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status
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
    body: BaseModel,
    http_request: Request,
    operation_type: OperationType,
    idempotency_key: str | None,
    service: OperationService,
) -> OperationHandle:
    handle = await service.submit(
        operation_type,
        body.model_dump(mode="json", exclude_none=True),
        idempotency_key=idempotency_key,
    )
    http_request.state.audit_submitted_operation_id = handle.operation_id
    return OperationHandle.model_validate(handle.model_dump(mode="json"))


@router.post("/summarization-runs", response_model=OperationHandle, status_code=202)
async def submit_summarization(
    body: SummarizationRequest,
    http_request: Request,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=8, max_length=200)
    ] = None,
    service: OperationService = Depends(get_operation_service),
) -> OperationHandle:
    return await _submit(
        body, http_request, OperationType.SUMMARIZATION_RUN, idempotency_key, service
    )


@router.post("/theme-analyses", response_model=OperationHandle, status_code=202)
async def submit_theme_analysis(
    body: ThemeAnalysisRequest,
    http_request: Request,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=8, max_length=200)
    ] = None,
    service: OperationService = Depends(get_operation_service),
) -> OperationHandle:
    return await _submit(
        body, http_request, OperationType.THEME_ANALYSIS_CREATE, idempotency_key, service
    )


@router.post("/digests", response_model=OperationHandle, status_code=202)
async def submit_digest(
    body: DigestCreateRequest,
    http_request: Request,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=8, max_length=200)
    ] = None,
    service: OperationService = Depends(get_operation_service),
) -> OperationHandle:
    return await _submit(body, http_request, OperationType.DIGEST_CREATE, idempotency_key, service)


@router.post("/pipeline-runs", response_model=OperationHandle, status_code=202)
async def submit_pipeline(
    body: PipelineRequest,
    http_request: Request,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=8, max_length=200)
    ] = None,
    service: OperationService = Depends(get_operation_service),
) -> OperationHandle:
    return await _submit(body, http_request, OperationType.PIPELINE_RUN, idempotency_key, service)


@router.post("/podcast-scripts", response_model=OperationHandle, status_code=202)
async def submit_podcast_script(
    body: PodcastScriptRequest,
    http_request: Request,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=8, max_length=200)
    ] = None,
    service: OperationService = Depends(get_operation_service),
) -> OperationHandle:
    return await _submit(
        body, http_request, OperationType.PODCAST_SCRIPT_CREATE, idempotency_key, service
    )


@router.post("/podcasts", response_model=OperationHandle, status_code=202)
async def submit_podcast_audio(
    body: PodcastAudioRequest,
    http_request: Request,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=8, max_length=200)
    ] = None,
    service: OperationService = Depends(get_operation_service),
) -> OperationHandle:
    return await _submit(
        body, http_request, OperationType.PODCAST_AUDIO_CREATE, idempotency_key, service
    )


@router.post("/audio-digests", response_model=OperationHandle, status_code=status.HTTP_202_ACCEPTED)
async def submit_audio_digest(
    body: AudioDigestRequest,
    http_request: Request,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=8, max_length=200)
    ] = None,
    service: OperationService = Depends(get_operation_service),
) -> OperationHandle:
    return await _submit(
        body, http_request, OperationType.AUDIO_DIGEST_CREATE, idempotency_key, service
    )
