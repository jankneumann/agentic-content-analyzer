"""Independently deployed capture clients must speak the canonical ingestions contract."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from src.contracts.workflow_models import IngestCommand

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = TypeAdapter(IngestCommand)

# JSON/JS `"kind": "url"` / `kind: 'url'`, markdown `kind: url`, query `kind=url`.
KIND_URL_RE = re.compile(
    r"""["']?kind["']?\s*:\s*["']url["']"""
    r"""|kind:\s*url\b"""
    r"""|kind=url\b"""
)

# User-facing / in-repo clients that operators actually run. Archived OpenSpec
# snapshots and retirement registries may still name the old path.
LIVE_CLIENT_PATHS = (
    ROOT / "docs/MOBILE_CAPTURE.md",
    ROOT / "docs/CONTENT_CAPTURE.md",
    ROOT / "docs/API_CONSUMERS.md",
    ROOT / "shortcuts/README.md",
    ROOT / "extension/README.md",
    ROOT / "extension/popup.js",
    ROOT / "src/templates/shortcut.html",
    ROOT / "src/templates/save.html",
    ROOT / "openspec/specs/content-capture/spec.md",
)


def test_legacy_shortcut_body_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ADAPTER.validate_python({"url": "https://example.com/article", "source": "ios_shortcut"})


def test_legacy_save_url_body_without_kind_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(
            {
                "url": "https://example.com/article",
                "title": "Article",
                "excerpt": "selected",
                "source": "chrome_extension",
            }
        )


def test_client_supplied_html_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(
            {
                "kind": "url",
                "url": "https://example.com/article",
                "html": "<html></html>",
            }
        )


def test_canonical_url_command_is_accepted() -> None:
    command = ADAPTER.validate_python(
        {"kind": "url", "url": "https://example.com/article", "notes": "selected"}
    )
    assert command.kind == "url"
    assert str(command.url).rstrip("/") == "https://example.com/article"


@pytest.mark.parametrize("path", LIVE_CLIENT_PATHS, ids=lambda p: str(p.relative_to(ROOT)))
def test_live_capture_clients_do_not_instruct_retired_mutations(path: Path) -> None:
    text = path.read_text()
    assert path.is_file()
    # Mentions of the retired paths are allowed only as "do not use" / 404 docs.
    if "/api/v1/content/save-url" in text:
        assert "retired" in text.lower() or "404" in text
    if "/api/v1/content/save-page" in text:
        assert "retired" in text.lower() or "404" in text
    assert KIND_URL_RE.search(text), f"{path} must instruct kind=url"


def test_extension_posts_ingestions_not_save_url() -> None:
    source = (ROOT / "extension/popup.js").read_text()
    assert "/api/v1/ingestions" in source
    assert "/api/v1/content/save-url" not in source
    assert "/api/v1/content/save-page" not in source
    assert "X-Admin-Key" in source
    assert "Authorization" not in source or "Bearer" not in source
    assert "captureFullPage" not in source
    assert "outerHTML" not in source
