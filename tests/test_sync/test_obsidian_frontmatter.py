"""Tests for obsidian_frontmatter module.

Covers: build_frontmatter(), slugify_filename(), compute_content_hash(),
sanitize_tag().
"""

from datetime import datetime, timezone

import pytest

from src.sync.obsidian_frontmatter import (
    build_frontmatter,
    compute_content_hash,
    sanitize_tag,
    slugify_filename,
)


class TestSanitizeTag:
    """Tag sanitization for YAML safety."""

    def test_clean_tag_passes_through(self) -> None:
        assert sanitize_tag("machine learning") == "machine learning"

    def test_strips_colons(self) -> None:
        assert sanitize_tag("key: value") == "key value"

    def test_strips_newlines(self) -> None:
        assert sanitize_tag("line1\nline2") == "line1 line2"

    def test_strips_yaml_separator(self) -> None:
        assert sanitize_tag("---danger") == "danger"

    def test_strips_leading_hash(self) -> None:
        assert sanitize_tag("#hashtag") == "hashtag"

    def test_empty_after_sanitization(self) -> None:
        assert sanitize_tag("---") == ""
        assert sanitize_tag(":::") == ""

    def test_whitespace_only(self) -> None:
        assert sanitize_tag("   ") == ""


class TestBuildFrontmatter:
    """YAML frontmatter generation."""

    def test_basic_frontmatter(self) -> None:
        result = build_frontmatter(aca_id="digest-1", aca_type="digest")
        assert result.startswith("---\n")
        assert result.endswith("---\n")
        assert "generator: aca" in result
        assert 'aca_id: "digest-1"' in result
        assert "aca_type: digest" in result

    def test_with_date_datetime(self) -> None:
        dt = datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc)
        result = build_frontmatter(aca_id="d-1", aca_type="digest", date=dt)
        assert "date: 2026-04-03" in result

    def test_with_date_string(self) -> None:
        result = build_frontmatter(aca_id="d-1", aca_type="digest", date="2026-04-03T00:00:00")
        assert "date: 2026-04-03" in result

    def test_with_tags(self) -> None:
        result = build_frontmatter(aca_id="d-1", aca_type="digest", tags=["ai", "ml"])
        assert "tags: [ai, ml]" in result

    def test_tags_sanitized(self) -> None:
        result = build_frontmatter(aca_id="d-1", aca_type="digest", tags=["ai", "key:value", "---"])
        # "---" becomes empty and is omitted; "key:value" becomes "keyvalue"
        assert "tags:" in result
        assert "---" not in result.split("tags:")[1].split("\n")[0]

    def test_with_content_hash(self) -> None:
        result = build_frontmatter(aca_id="d-1", aca_type="digest", content_hash="sha256:abc123")
        assert 'content_hash: "sha256:abc123"' in result

    def test_extra_string_field(self) -> None:
        result = build_frontmatter(aca_id="d-1", aca_type="digest", source_type="gmail")
        assert 'source_type: "gmail"' in result

    def test_extra_numeric_field(self) -> None:
        result = build_frontmatter(aca_id="i-1", aca_type="insight", confidence=0.85)
        assert "confidence: 0.85" in result

    def test_extra_list_field(self) -> None:
        result = build_frontmatter(aca_id="d-1", aca_type="digest", sources=["a", "b"])
        assert 'sources: ["a", "b"]' in result

    def test_none_extra_fields_omitted(self) -> None:
        result = build_frontmatter(aca_id="d-1", aca_type="digest", author=None)
        assert "author" not in result


class TestSlugifyFilename:
    """Filename generation with date prefix and slugification."""

    def test_basic_slug(self) -> None:
        dt = datetime(2026, 4, 3, tzinfo=timezone.utc)
        result = slugify_filename("Daily AI Digest", dt)
        assert result == "2026-04-03-daily-ai-digest.md"

    def test_string_date(self) -> None:
        result = slugify_filename("My Title", "2026-04-03")
        assert result == "2026-04-03-my-title.md"

    def test_no_date(self) -> None:
        result = slugify_filename("Untitled Note")
        assert result == "untitled-note.md"

    def test_entity_no_date_prefix(self) -> None:
        result = slugify_filename("OpenAI", None, "entity")
        assert result == "OpenAI.md"

    def test_entity_preserves_casing(self) -> None:
        result = slugify_filename("Transformer Architecture", None, "entity")
        assert result == "Transformer Architecture.md"

    def test_special_characters_removed(self) -> None:
        dt = datetime(2026, 4, 3, tzinfo=timezone.utc)
        result = slugify_filename("AI & ML: What's Next?", dt)
        assert ":" not in result
        assert "&" not in result
        assert "?" not in result

    def test_empty_title_fallback(self) -> None:
        result = slugify_filename("", None)
        assert result == "untitled.md"

    def test_unicode_handled(self) -> None:
        result = slugify_filename("Über AI Résumé", None)
        assert "uber" in result.lower()


class TestComputeContentHash:
    """Content hash computation."""

    def test_produces_sha256_prefix(self) -> None:
        result = compute_content_hash("hello world")
        assert result.startswith("sha256:")
        assert len(result) == 7 + 64  # "sha256:" + 64 hex chars

    def test_deterministic(self) -> None:
        content = "---\ngenerator: aca\n---\n# Title\nBody"
        assert compute_content_hash(content) == compute_content_hash(content)

    def test_different_content_different_hash(self) -> None:
        assert compute_content_hash("content A") != compute_content_hash("content B")

    def test_excludes_content_hash_line(self) -> None:
        content_without = "---\ngenerator: aca\n---\n# Title"
        content_with = '---\ngenerator: aca\ncontent_hash: "sha256:old"\n---\n# Title'
        assert compute_content_hash(content_without) == compute_content_hash(content_with)
