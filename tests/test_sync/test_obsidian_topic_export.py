"""Tests for KB topic export in ObsidianExporter.

Validates the 3-tier vault structure (Category/Topic/_overview.md),
incremental sync via article_version, source extracts, and category indices.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.sync.obsidian_exporter import ExportOptions, ObsidianExporter, _safe_segment


class TestSafeSegment:
    def test_strips_traversal(self):
        assert ".." not in _safe_segment("../escape")
        assert "/" not in _safe_segment("foo/bar")

    def test_falls_back_for_empty(self):
        assert _safe_segment("") == "unknown"

    def test_preserves_normal_value(self):
        assert _safe_segment("ml_ai") == "ml_ai"


class TestTopicWrite:
    """Tests for the _write_topic_file helper."""

    @pytest.fixture()
    def exporter(self, tmp_path: Path) -> ObsidianExporter:
        vault = tmp_path / "vault"
        vault.mkdir()
        return ObsidianExporter(
            engine=MagicMock(),
            vault_path=vault,
            options=ExportOptions(),
        )

    def test_write_creates_3_tier_path(self, exporter: ObsidianExporter):
        """kb.12: 3-tier vault structure Category/Topic/_overview.md."""
        result = exporter._write_topic_file(
            rel_path="ml_ai/rag-architecture/_overview.md",
            aca_id="topic-rag-architecture",
            aca_type="topic",
            content_hash="sha256:abc",
            content="---\ngenerator: aca\n---\n# RAG\n",
        )
        assert result == "created"
        expected = exporter._vault_path / "ml_ai" / "rag-architecture" / "_overview.md"
        assert expected.exists()

    def test_skips_unchanged(self, exporter: ObsidianExporter):
        """kb.12: incremental sync — unchanged content is skipped."""
        path = "ml_ai/topic-x/_overview.md"
        exporter._write_topic_file(path, "topic-x", "topic", "sha256:111", "v1 body")
        result = exporter._write_topic_file(path, "topic-x", "topic", "sha256:111", "v1 body")
        assert result == "skipped"

    def test_updates_changed(self, exporter: ObsidianExporter):
        """kb.12: changed content_hash triggers an update."""
        path = "ml_ai/topic-y/_overview.md"
        exporter._write_topic_file(path, "topic-y", "topic", "sha256:111", "v1 body")
        result = exporter._write_topic_file(path, "topic-y", "topic", "sha256:222", "v2 body")
        assert result == "updated"
        assert (exporter._vault_path / "ml_ai/topic-y/_overview.md").read_text() == "v2 body"

    def test_dry_run_does_not_write(self, tmp_path: Path):
        """kb.12: dry_run preserves vault but tracks would-be actions."""
        vault = tmp_path / "vault"
        vault.mkdir()
        exporter = ObsidianExporter(
            engine=MagicMock(),
            vault_path=vault,
            options=ExportOptions(dry_run=True),
        )
        result = exporter._write_topic_file(
            "ml_ai/dryrun/_overview.md",
            "topic-dry",
            "topic",
            "sha256:dry",
            "body",
        )
        assert result == "created"
        assert not (vault / "ml_ai/dryrun/_overview.md").exists()


class TestRenderTopicBody:
    @pytest.fixture()
    def exporter(self, tmp_path: Path) -> ObsidianExporter:
        return ObsidianExporter(
            engine=MagicMock(),
            vault_path=tmp_path / "vault",
            options=ExportOptions(),
        )

    def test_renders_minimal_topic(self, exporter: ObsidianExporter):
        topic = MagicMock()
        topic.name = "RAG"
        topic.summary = "Retrieval-augmented generation"
        topic.article_md = "## Body\n\nFull article."
        topic.related_topic_ids = []

        body = exporter._render_topic_body(topic)
        assert "# RAG" in body
        assert "Retrieval-augmented" in body
        assert "Full article" in body
        assert "Related Topics" not in body

    def test_handles_missing_article(self, exporter: ObsidianExporter):
        topic = MagicMock()
        topic.name = "Empty"
        topic.summary = None
        topic.article_md = None
        topic.related_topic_ids = []

        body = exporter._render_topic_body(topic)
        assert "no compiled article" in body
