from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ingestion.files import FileContentIngestionService
from src.models.content import Content, ContentSource, ContentStatus
from src.models.document import DocumentContent, DocumentFormat


def _document(markdown: str = "# Updated") -> DocumentContent:
    return DocumentContent(
        markdown_content=markdown,
        source_path="report.md",
        source_format=DocumentFormat.MARKDOWN,
        parser_used="test",
    )


def test_new_file_identity_persists_raw_digest() -> None:
    service = FileContentIngestionService(router=MagicMock(), db=MagicMock())
    digest = hashlib.sha256(b"raw file").hexdigest()

    content = service._create_content(
        _document(), MagicMock(stem="report", name="report.md"), digest, None, None
    )

    assert content.source_id == f"file:{digest}"
    assert content.metadata_json["file_sha256"] == digest


@pytest.mark.asyncio
async def test_force_reprocess_updates_existing_canonical_file_in_place(tmp_path) -> None:
    path = tmp_path / "report.md"
    path.write_text("raw file")
    existing = Content(
        id=41,
        source_type=ContentSource.FILE_UPLOAD,
        source_id="file:existing",
        title="Old",
        markdown_content="# Old",
        content_hash="old",
        status=ContentStatus.COMPLETED,
        metadata_json={"file_sha256": hashlib.sha256(b"raw file").hexdigest()},
    )
    router = MagicMock()
    router.parse = AsyncMock(return_value=_document())
    db = MagicMock()
    service = FileContentIngestionService(router=router, db=db)
    service._find_duplicate = MagicMock(return_value=existing)  # type: ignore[method-assign]

    with patch("src.services.indexing.index_content"):
        result = await service.ingest_file(path, force_reprocess=True)

    assert result is existing
    assert existing.id == 41
    assert existing.source_id == "file:existing"
    assert existing.markdown_content == "# Updated"
    assert existing.metadata_json["file_sha256"] == hashlib.sha256(b"raw file").hexdigest()
    assert existing.canonical_id is None
    db.add.assert_not_called()
