from __future__ import annotations

import base64
import json
from hashlib import sha256
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.services.upload_service import UploadService


@pytest.fixture
def storage() -> AsyncMock:
    mock = AsyncMock()
    mock.save.side_effect = [
        "uploads/2026/07/payload_report.pdf",
        "uploads/2026/07/manifest_report.upload.json",
    ]
    return mock


@pytest.mark.asyncio
async def test_store_persists_payload_and_durable_manifest(storage: AsyncMock) -> None:
    service = UploadService(storage=storage, max_size_bytes=100)

    reference = await service.store(
        b"pdf bytes",
        "report.pdf",
        "application/pdf",
        title="Architecture report",
        publication="Internal",
    )

    assert reference.id.startswith("upl_")
    assert "manifest_report" not in reference.id
    assert reference.filename == "report.pdf"
    assert reference.media_type == "application/pdf"
    assert reference.size_bytes == 9
    assert reference.title == "Architecture report"
    assert reference.publication == "Internal"
    assert storage.save.await_count == 2
    manifest = json.loads(storage.save.await_args_list[1].args[0])
    assert manifest == {
        "schema_version": 1,
        "storage_path": "uploads/2026/07/payload_report.pdf",
        "filename": "report.pdf",
        "media_type": "application/pdf",
        "size_bytes": 9,
        "payload_sha256": sha256(b"pdf bytes").hexdigest(),
        "title": "Architecture report",
        "publication": "Internal",
    }


@pytest.mark.asyncio
async def test_resolve_loads_manifest_then_payload(storage: AsyncMock) -> None:
    manifest = {
        "schema_version": 1,
        "storage_path": "uploads/2026/07/payload_report.pdf",
        "filename": "report.pdf",
        "media_type": "application/pdf",
        "size_bytes": 9,
        "payload_sha256": sha256(b"pdf bytes").hexdigest(),
        "title": "Architecture report",
        "publication": "Internal",
    }
    service = UploadService(storage=storage)
    upload_id = service.reference_id_for_path("uploads/2026/07/manifest_report.upload.json")
    storage.get.side_effect = [json.dumps(manifest).encode(), b"pdf bytes"]

    resolved = await service.resolve(upload_id)

    assert resolved.filename == "report.pdf"
    assert resolved.data == b"pdf bytes"
    assert resolved.title == "Architecture report"
    assert resolved.publication == "Internal"
    assert storage.get.await_args_list[0].args == ("uploads/2026/07/manifest_report.upload.json",)
    assert storage.get.await_args_list[1].args == ("uploads/2026/07/payload_report.pdf",)


@pytest.mark.asyncio
async def test_store_rejects_oversized_upload_before_storage(storage: AsyncMock) -> None:
    service = UploadService(storage=storage, max_size_bytes=3)

    with pytest.raises(ValueError, match="exceeds"):
        await service.store(b"four", "too-large.txt", "text/plain")

    storage.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_rejects_invalid_or_mismatched_manifest(storage: AsyncMock) -> None:
    storage.get.side_effect = [b"{}"]
    service = UploadService(storage=storage)

    with pytest.raises(ValueError, match="Invalid upload reference"):
        await service.resolve(service.reference_id_for_path("uploads/bad.upload.json"))


@pytest.mark.asyncio
async def test_resolve_rejects_raw_paths_and_payload_digest_mismatch(storage: AsyncMock) -> None:
    service = UploadService(storage=storage)

    with pytest.raises(ValueError, match="Invalid upload reference"):
        await service.resolve("uploads/manifest.json")
    storage.get.assert_not_awaited()

    manifest = {
        "schema_version": 1,
        "storage_path": "uploads/payload",
        "filename": "report.pdf",
        "media_type": "application/pdf",
        "size_bytes": 9,
        "payload_sha256": sha256(b"different").hexdigest(),
        "title": None,
        "publication": None,
    }
    storage.get.side_effect = [json.dumps(manifest).encode(), b"pdf bytes"]
    upload_id = service.reference_id_for_path("uploads/manifest.upload.json")
    with pytest.raises(ValueError, match="digest mismatch"):
        await service.resolve(upload_id)


@pytest.mark.asyncio
async def test_resolve_rejects_token_for_non_manifest_json(storage: AsyncMock) -> None:
    service = UploadService(storage=storage)
    encoded = base64.urlsafe_b64encode(b"uploads/config.json").decode().rstrip("=")

    with pytest.raises(ValueError, match="Invalid upload reference"):
        await service.resolve(f"upl_{encoded}")

    storage.get.assert_not_awaited()


def test_materialize_sync_creates_named_files_and_removes_them(storage: AsyncMock) -> None:
    manifest = {
        "schema_version": 1,
        "storage_path": "uploads/payload",
        "filename": "../report.pdf",
        "media_type": "application/pdf",
        "size_bytes": 9,
        "payload_sha256": sha256(b"pdf bytes").hexdigest(),
        "title": "Report",
        "publication": "Internal",
    }
    storage.get.side_effect = [json.dumps(manifest).encode(), b"pdf bytes"]
    service = UploadService(storage=storage)
    upload_id = service.reference_id_for_path("uploads/manifest.upload.json")

    with service.materialize_sync([upload_id]) as uploads:
        assert len(uploads) == 1
        assert uploads[0].path.name == "report.pdf"
        assert uploads[0].path.read_bytes() == b"pdf bytes"
        assert uploads[0].title == "Report"
        assert uploads[0].publication == "Internal"
        parent = uploads[0].path.parent

    assert not Path(parent).exists()
