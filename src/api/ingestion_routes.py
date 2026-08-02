"""Canonical upload and typed-ingestion submission routes."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)

from src.api.workflow_dependencies import (
    get_operation_service,
    get_sources_config,
    get_upload_service,
)
from src.config.release_identity import release_identity
from src.config.sources import SourcesConfig
from src.contracts.workflow_models import (
    IngestCommand,
    IngestionHistoryPage,
    IngestionOutcome,
    OperationHandle,
    TerminalOperationStatus,
    UploadReference,
)
from src.ingestion.registry import SOURCE_REGISTRY
from src.models.jobs import OperationType
from src.services.operation_service import OperationService
from src.services.upload_service import UploadService

router = APIRouter(prefix="/api/v1", tags=["ingestion"])

_UPLOAD_MEDIA_TYPES = frozenset(
    {
        "application/epub+zip",
        "application/msword",
        "application/pdf",
        "application/rtf",
        "application/vnd.ms-outlook",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "audio/mpeg",
        "audio/wav",
        "image/gif",
        "image/jpeg",
        "image/png",
        "text/csv",
        "text/html",
        "text/markdown",
        "text/plain",
    }
)

_UPLOAD_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    ".epub": (b"PK\x03\x04",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".jpeg": (b"\xff\xd8\xff",),
    ".jpg": (b"\xff\xd8\xff",),
    ".mp3": (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"),
    ".msg": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
    ".pdf": (b"%PDF",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".pptx": (b"PK\x03\x04",),
    ".wav": (b"RIFF",),
    ".xlsx": (b"PK\x03\x04",),
    ".zip": (b"PK\x03\x04", b"PK\x05\x06"),
    ".docx": (b"PK\x03\x04",),
}

_UPLOAD_EXTENSION_MEDIA: dict[str, frozenset[str]] = {
    ".csv": frozenset({"text/csv", "text/plain"}),
    ".doc": frozenset({"application/msword"}),
    ".docx": frozenset({"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}),
    ".epub": frozenset({"application/epub+zip"}),
    ".gif": frozenset({"image/gif"}),
    ".htm": frozenset({"text/html"}),
    ".html": frozenset({"text/html"}),
    ".jpeg": frozenset({"image/jpeg"}),
    ".jpg": frozenset({"image/jpeg"}),
    ".md": frozenset({"text/markdown", "text/plain"}),
    ".mp3": frozenset({"audio/mpeg"}),
    ".msg": frozenset({"application/vnd.ms-outlook"}),
    ".pdf": frozenset({"application/pdf"}),
    ".png": frozenset({"image/png"}),
    ".pptx": frozenset(
        {"application/vnd.openxmlformats-officedocument.presentationml.presentation"}
    ),
    ".rtf": frozenset({"application/rtf"}),
    ".txt": frozenset({"text/plain"}),
    ".wav": frozenset({"audio/wav"}),
    ".xlsx": frozenset({"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}),
    ".zip": frozenset({"application/zip"}),
}


@router.get("/ingestions", response_model=IngestionHistoryPage)
async def list_ingestion_history(
    command_key: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    configured_source_key: Annotated[str | None, Query(pattern=r"^src_[a-f0-9]{20}$")] = None,
    outcome: IngestionOutcome | None = None,
    status_filter: Annotated[
        TerminalOperationStatus | None,
        Query(alias="status"),
    ] = None,
    parent_operation_id: Annotated[
        str | None,
        Query(pattern=r"^[1-9][0-9]*$", max_length=19),
    ] = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1, max_length=2048)] = None,
    service: OperationService = Depends(get_operation_service),
) -> IngestionHistoryPage:
    page = await service.list_ingestion_history(
        command_key=command_key,
        configured_source_key=configured_source_key,
        outcome=outcome,
        status=status_filter,
        parent_operation_id=parent_operation_id,
        created_after=created_after,
        created_before=created_before,
        limit=limit,
        cursor=cursor,
    )
    return IngestionHistoryPage.model_validate(page.model_dump(mode="json"))


@router.post("/uploads", response_model=UploadReference, status_code=status.HTTP_201_CREATED)
async def create_upload(
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
    publication: Annotated[str | None, Form()] = None,
    service: UploadService = Depends(get_upload_service),
) -> UploadReference:
    media_type = (file.content_type or "application/octet-stream").split(";", 1)[0].lower()
    if media_type not in _UPLOAD_MEDIA_TYPES:
        raise HTTPException(status_code=422, detail=f"Unsupported upload media type: {media_type}")
    data = await file.read(service.max_size_bytes + 1)
    if len(data) > service.max_size_bytes:
        raise HTTPException(status_code=413, detail="Upload exceeds the configured size limit")
    suffix = Path(file.filename or "").suffix.lower()
    expected_media = _UPLOAD_EXTENSION_MEDIA.get(suffix)
    if expected_media is None or media_type not in expected_media:
        raise HTTPException(status_code=422, detail="Upload media type does not match its filename")
    signatures = _UPLOAD_SIGNATURES.get(suffix)
    if signatures and not any(data.startswith(signature) for signature in signatures):
        raise HTTPException(status_code=422, detail="Upload content does not match its filename")
    try:
        return await service.store(
            data,
            file.filename or "",
            media_type,
            title=title,
            publication=publication,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid upload") from exc


@router.post(
    "/ingestions",
    response_model=OperationHandle,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_ingestion(
    command: IngestCommand,
    response: Response,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=8, max_length=200)
    ] = None,
    service: OperationService = Depends(get_operation_service),
    config: SourcesConfig = Depends(get_sources_config),
) -> OperationHandle:
    if getattr(command, "configured_sources", None) is not None:
        raise HTTPException(
            status_code=422,
            detail="configured_sources is an internal scheduler snapshot and cannot be supplied",
        )
    payload = command.model_dump(mode="json", exclude_none=True)
    descriptor = SOURCE_REGISTRY.get(command.kind)
    if descriptor.config_accessor is not None:
        configured_sources = [
            source.model_dump(mode="json") for source in descriptor.config_accessor(config)
        ]
        if not configured_sources:
            raise HTTPException(
                status_code=422,
                detail=f"No enabled configured sources are available for '{descriptor.key}'",
            )
        payload["configured_sources"] = configured_sources
    handle = await service.submit(
        OperationType.INGESTION_EXECUTE,
        payload,
        idempotency_key=idempotency_key,
    )
    revision, revision_source = release_identity()
    response.headers["X-Release-Revision"] = revision
    response.headers["X-Release-Revision-Source"] = revision_source
    return OperationHandle.model_validate(handle.model_dump(mode="json"))
