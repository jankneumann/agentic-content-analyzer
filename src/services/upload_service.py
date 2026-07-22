"""Durable upload references backed by the configured file storage provider."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.config import settings
from src.contracts.workflow_models import UploadReference
from src.services.file_storage import FileStorageProvider, get_storage


class ResolvedUpload(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    filename: str
    media_type: str
    size_bytes: int = Field(ge=0)
    data: bytes
    title: str | None = None
    publication: str | None = None


class MaterializedUpload(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    path: Path
    title: str | None = None
    publication: str | None = None


class _UploadManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(1, ge=1, le=1)
    storage_path: str
    filename: str
    media_type: str
    size_bytes: int = Field(ge=0)
    payload_sha256: str = Field(min_length=64, max_length=64)
    title: str | None = None
    publication: str | None = None


class UploadService:
    """Store a payload plus a manifest that can be resolved by any worker."""

    def __init__(
        self,
        storage: FileStorageProvider | None = None,
        max_size_bytes: int | None = None,
    ) -> None:
        self.storage = storage or get_storage(bucket="uploads")
        self.max_size_bytes = (
            max_size_bytes
            if max_size_bytes is not None
            else settings.max_upload_size_mb * 1024 * 1024
        )

    async def store(
        self,
        data: bytes,
        filename: str,
        media_type: str,
        *,
        title: str | None = None,
        publication: str | None = None,
    ) -> UploadReference:
        size_bytes = len(data)
        if size_bytes > self.max_size_bytes:
            raise ValueError(
                f"Upload size {size_bytes} bytes exceeds limit {self.max_size_bytes} bytes"
            )
        safe_filename = Path(filename).name
        if not safe_filename:
            raise ValueError("Upload filename is required")

        storage_path = await self.storage.save(
            data,
            safe_filename,
            media_type,
            upload_kind="payload",
        )
        manifest = _UploadManifest(
            storage_path=storage_path,
            filename=safe_filename,
            media_type=media_type,
            size_bytes=size_bytes,
            payload_sha256=hashlib.sha256(data).hexdigest(),
            title=title,
            publication=publication,
        )
        try:
            manifest_path = await self.storage.save(
                manifest.model_dump_json().encode(),
                f"{safe_filename}.upload.json",
                "application/vnd.aca.upload+json",
                upload_kind="manifest",
            )
        except Exception:
            await self.storage.delete(storage_path)
            raise
        return UploadReference(
            id=self.reference_id_for_path(manifest_path),
            filename=safe_filename,
            media_type=media_type,
            size_bytes=size_bytes,
            title=title,
            publication=publication,
        )

    async def resolve(self, upload_id: str) -> ResolvedUpload:
        manifest_path = self._path_for_reference(upload_id)
        try:
            manifest_data = await self.storage.get(manifest_path)
            manifest = _UploadManifest.model_validate_json(manifest_data)
            self._validate_payload_path(manifest.storage_path)
            payload = await self.storage.get(manifest.storage_path)
        except (
            FileNotFoundError,
            json.JSONDecodeError,
            ValidationError,
            UnicodeDecodeError,
            ValueError,
        ) as exc:
            raise ValueError(f"Invalid upload reference '{upload_id}'") from exc
        if len(payload) != manifest.size_bytes:
            raise ValueError(f"Invalid upload reference '{upload_id}': payload size mismatch")
        payload_digest = hashlib.sha256(payload).hexdigest()
        if not hmac.compare_digest(payload_digest, manifest.payload_sha256):
            raise ValueError(f"Invalid upload reference '{upload_id}': payload digest mismatch")
        return ResolvedUpload(
            filename=manifest.filename,
            media_type=manifest.media_type,
            size_bytes=manifest.size_bytes,
            data=payload,
            title=manifest.title,
            publication=manifest.publication,
        )

    def reference_id_for_path(self, manifest_path: str) -> str:
        """Encode an internal manifest path as a namespaced public reference."""
        self._validate_manifest_path(manifest_path)
        encoded = base64.urlsafe_b64encode(manifest_path.encode()).decode().rstrip("=")
        return f"upl_{encoded}"

    def _path_for_reference(self, upload_id: str) -> str:
        if not upload_id.startswith("upl_"):
            raise ValueError(f"Invalid upload reference '{upload_id}'")
        encoded = upload_id.removeprefix("upl_")
        try:
            padding = "=" * (-len(encoded) % 4)
            manifest_path = base64.b64decode(
                encoded + padding,
                altchars=b"-_",
                validate=True,
            ).decode()
            self._validate_manifest_path(manifest_path)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError(f"Invalid upload reference '{upload_id}'") from exc
        return manifest_path

    @classmethod
    def _validate_manifest_path(cls, storage_path: str) -> None:
        cls._validate_payload_path(storage_path)
        if not storage_path.endswith(".upload.json"):
            raise ValueError("Invalid upload reference path")

    @staticmethod
    def _validate_payload_path(storage_path: str) -> None:
        path = Path(storage_path)
        if not storage_path.startswith("uploads/") or path.is_absolute() or ".." in path.parts:
            raise ValueError("Invalid upload reference path")

    async def resolve_many(self, upload_ids: list[str]) -> list[ResolvedUpload]:
        return [await self.resolve(upload_id) for upload_id in upload_ids]

    @contextmanager
    def materialize_sync(self, upload_ids: list[str]) -> Iterator[list[MaterializedUpload]]:
        """Materialize durable references for the existing path-based parser API."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            uploads = asyncio.run(self.resolve_many(upload_ids))
        else:
            raise RuntimeError("materialize_sync must run outside an active event loop")

        with tempfile.TemporaryDirectory(prefix="aca-uploads-") as directory:
            root = Path(directory)
            materialized = []
            used_names: set[str] = set()
            for index, upload in enumerate(uploads):
                filename = Path(upload.filename).name
                if filename in used_names:
                    filename = f"{index:03d}-{filename}"
                used_names.add(filename)
                path = root / filename
                path.write_bytes(upload.data)
                materialized.append(
                    MaterializedUpload(
                        path=path,
                        title=upload.title,
                        publication=upload.publication,
                    )
                )
            yield materialized
