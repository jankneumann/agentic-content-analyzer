"""Contract tests for the pure Obsidian clip parser and normalizer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.ingestion.obsidian_parser import (
    ClipParseLimits,
    ObsidianClipError,
    canonical_url_digest,
    canonicalize_source_url,
    normalize_obsidian_markdown,
    parse_obsidian_clip,
    redact_source_url,
)


def _note(frontmatter: str, body: str = "# Captured article\n") -> bytes:
    return f"---\n{frontmatter.rstrip()}\n---\n{body}".encode()


def _assert_code(expected: str, note: bytes, *, limits: ClipParseLimits | None = None) -> None:
    with pytest.raises(ObsidianClipError) as error:
        parse_obsidian_clip(note, limits=limits)
    assert error.value.code == expected
    assert "example.test" not in str(error.value)


def test_parse_valid_clip_maps_metadata_strips_frontmatter_and_normalizes_body() -> None:
    parsed = parse_obsidian_clip(
        _note(
            """
source_url: https://EXAMPLE.test:443/article?utm_source=clipper&topic=ai
captured_at: 2026-08-02T09:15:00+02:00
capture_client: obsidian-web-clipper
content_type_hint: article
ignored_template_field: not-persisted
""",
            "# Notes\nSee [[Research#Finding|the finding]].\n",
        )
    )

    assert parsed.metadata.source_url == (
        "https://EXAMPLE.test:443/article?utm_source=clipper&topic=ai"
    )
    assert parsed.metadata.captured_at == datetime(
        2026, 8, 2, 9, 15, tzinfo=timezone(timedelta(hours=2))
    )
    assert parsed.metadata.capture_client == "obsidian-web-clipper"
    assert parsed.metadata.content_type_hint == "article"
    assert parsed.metadata.model_extra is None
    assert parsed.markdown == "# Notes\nSee the finding.\n"
    assert parsed.canonical_url == "https://example.test/article?topic=ai"
    assert parsed.source_origin == "https://example.test"
    assert len(parsed.canonical_url_digest) == 64


def test_parse_clip_applies_closed_optional_defaults() -> None:
    parsed = parse_obsidian_clip(
        _note(
            """
source_url: http://example.test/story
captured_at: 2026-08-02T07:15:00Z
"""
        )
    )

    assert parsed.metadata.capture_client == "obsidian-web-clipper"
    assert parsed.metadata.content_type_hint == "other"
    assert parsed.metadata.captured_at == datetime(2026, 8, 2, 7, 15, tzinfo=UTC)


@pytest.mark.parametrize(
    ("frontmatter", "code"),
    [
        ("captured_at: 2026-08-02T07:15:00Z", "missing_required_metadata"),
        ("source_url: https://example.test", "missing_required_metadata"),
        (
            "source_url: ftp://example.test/file\ncaptured_at: 2026-08-02T07:15:00Z",
            "invalid_url",
        ),
        (
            "source_url: https://user:secret@example.test/file\ncaptured_at: 2026-08-02T07:15:00Z",
            "invalid_url",
        ),
        (
            "source_url: https://example.test\ncaptured_at: 2026-08-02T07:15:00",
            "invalid_captured_at",
        ),
        (
            "source_url: https://example.test\ncaptured_at: not-a-time",
            "invalid_captured_at",
        ),
        (
            "source_url: https://example.test\ncaptured_at: 2026-08-02T07:15:00Z\n"
            "capture_client: unknown-client",
            "invalid_capture_client",
        ),
        (
            "source_url: https://example.test\ncaptured_at: 2026-08-02T07:15:00Z\n"
            "content_type_hint: executable",
            "invalid_content_type_hint",
        ),
    ],
)
def test_parse_clip_rejects_invalid_contract_fields(frontmatter: str, code: str) -> None:
    _assert_code(code, _note(frontmatter))


def test_parse_clip_rejects_invalid_utf8() -> None:
    _assert_code("invalid_encoding", b"---\nsource_url: https://example.test\n---\n\xff")


def test_parse_clip_requires_frontmatter_at_the_start() -> None:
    _assert_code("missing_frontmatter", b"# No frontmatter\n")


def test_parse_clip_rejects_unclosed_frontmatter() -> None:
    _assert_code("invalid_frontmatter", b"---\nsource_url: https://example.test\n")


def test_parse_clip_rejects_non_mapping_yaml_root() -> None:
    _assert_code("frontmatter_not_mapping", _note("- one\n- two"))


def test_parse_clip_rejects_custom_yaml_tags_without_constructing_them() -> None:
    _assert_code(
        "yaml_custom_tag",
        _note("source_url: !unsafe https://example.test\ncaptured_at: 2026-08-02T07:15:00Z"),
    )


def test_parse_clip_rejects_unsupported_yaml_values() -> None:
    _assert_code(
        "yaml_unsupported_type",
        _note(
            "source_url: https://example.test\n"
            "captured_at: 2026-08-02T07:15:00Z\n"
            "ignored: !!binary SGVsbG8="
        ),
    )


def test_parse_clip_enforces_note_byte_limit_before_decoding() -> None:
    limits = ClipParseLimits(max_note_bytes=32)
    _assert_code("note_too_large", _note("source_url: https://example.test"), limits=limits)


def test_parse_clip_enforces_frontmatter_byte_limit() -> None:
    limits = ClipParseLimits(max_frontmatter_bytes=48)
    _assert_code(
        "frontmatter_too_large",
        _note("source_url: https://example.test\ncaptured_at: 2026-08-02T07:15:00Z"),
        limits=limits,
    )


def test_parse_clip_enforces_yaml_node_limit() -> None:
    limits = ClipParseLimits(max_yaml_nodes=5)
    _assert_code(
        "yaml_node_limit",
        _note(
            "source_url: https://example.test\ncaptured_at: 2026-08-02T07:15:00Z\nignored: value"
        ),
        limits=limits,
    )


def test_parse_clip_enforces_yaml_depth_limit() -> None:
    limits = ClipParseLimits(max_yaml_depth=2)
    _assert_code(
        "yaml_depth_limit",
        _note(
            "source_url: https://example.test\n"
            "captured_at: 2026-08-02T07:15:00Z\n"
            "ignored:\n  nested:\n    deeper: value"
        ),
        limits=limits,
    )


def test_parse_clip_enforces_yaml_alias_limit() -> None:
    limits = ClipParseLimits(max_yaml_aliases=1)
    _assert_code(
        "yaml_alias_limit",
        _note(
            "source_url: https://example.test\n"
            "captured_at: 2026-08-02T07:15:00Z\n"
            "base: &base value\n"
            "first: *base\n"
            "second: *base"
        ),
        limits=limits,
    )


def test_parse_clip_rejects_recursive_yaml_aliases() -> None:
    _assert_code(
        "yaml_unsupported_type",
        _note(
            "source_url: https://example.test\n"
            "captured_at: 2026-08-02T07:15:00Z\n"
            "recursive: &recursive [*recursive]"
        ),
    )


def test_parse_clip_enforces_bounded_strings_even_for_unknown_fields() -> None:
    limits = ClipParseLimits(max_yaml_string_chars=64)
    _assert_code(
        "yaml_string_limit",
        _note(
            "source_url: https://example.test\n"
            "captured_at: 2026-08-02T07:15:00Z\n"
            f"ignored: {'x' * 65}"
        ),
        limits=limits,
    )


def test_parse_clip_enforces_normalized_body_character_limit() -> None:
    limits = ClipParseLimits(max_body_chars=8)
    _assert_code(
        "body_too_large",
        _note(
            "source_url: https://example.test\ncaptured_at: 2026-08-02T07:15:00Z",
            "body-too-long",
        ),
        limits=limits,
    )


def test_normalizer_converts_wikilinks_aliases_and_headings() -> None:
    markdown = (
        "See [[Research Note]], [[Research Note|the note]], and [[Research Note#Key Result]].\n"
    )

    assert normalize_obsidian_markdown(markdown) == (
        "See Research Note, the note, and Research Note > Key Result.\n"
    )


def test_normalizer_converts_callout_marker_to_plain_blockquote() -> None:
    markdown = "> [!WARNING]+ Verify this\n> The clipped claim needs evidence.\n"

    assert normalize_obsidian_markdown(markdown) == (
        "> **Warning — Verify this**\n> The clipped claim needs evidence.\n"
    )


def test_normalizer_makes_embeds_inert_without_exposing_target() -> None:
    markdown = (
        "Diagram: ![[Attachments/private-diagram.png|System diagram]]\nPDF: ![[private.pdf]]\n"
    )

    normalized = normalize_obsidian_markdown(markdown)

    assert normalized == "Diagram: [Embedded content: System diagram]\nPDF: [Embedded content]\n"
    assert "Attachments" not in normalized
    assert "private.pdf" not in normalized


def test_normalizer_preserves_raw_html_macros_dangerous_uri_and_unknown_syntax_as_text() -> None:
    markdown = (
        '<script>window.example = "not executed"</script>\n'
        "javascript:alert(1)\n"
        "data:text/html,example\n"
        "<% template.macro() %>\n"
        "%% unsupported comment %%\n"
    )

    assert normalize_obsidian_markdown(markdown) == markdown


def test_normalizer_does_not_rewrite_fenced_or_inline_code() -> None:
    markdown = "`[[inline]]` and [[outside]]\n```md\n[[fenced]]\n![[embed.pdf]]\n```\n"

    assert normalize_obsidian_markdown(markdown) == (
        "`[[inline]]` and outside\n```md\n[[fenced]]\n![[embed.pdf]]\n```\n"
    )


def test_normalizer_is_idempotent() -> None:
    markdown = "> [!NOTE] Detail\n> See [[Page|label]] and ![[file.pdf]].\n"

    once = normalize_obsidian_markdown(markdown)

    assert normalize_obsidian_markdown(once) == once


def test_canonical_url_normalizes_host_default_port_tracking_query_and_fragment() -> None:
    url = "HTTPS://EXAMPLE.test:443/article?z=last&utm_source=clipper&fbclid=abc&a=first#section"

    assert canonicalize_source_url(url) == "https://example.test/article?a=first&z=last"


def test_canonical_url_keeps_nontracking_query_for_identity_but_redacts_diagnostics() -> None:
    url = "https://example.test:8443/private/story?token=sensitive&view=full"

    canonical = canonicalize_source_url(url)

    assert canonical == "https://example.test:8443/private/story?token=sensitive&view=full"
    assert redact_source_url(url) == "https://example.test:8443"
    assert "token" not in redact_source_url(url)


def test_canonical_url_hash_is_deterministic_for_equivalent_query_order() -> None:
    first = "https://example.test/story?b=2&a=1&utm_campaign=ignored"
    second = "https://EXAMPLE.test:443/story?a=1&b=2"

    assert canonical_url_digest(first) == canonical_url_digest(second)
    assert len(canonical_url_digest(first)) == 64


@pytest.mark.parametrize(
    "url",
    [
        "mailto:person@example.test",
        "https://user@example.test/story",
        "https://example.test:invalid/story",
        "https://exa mple.test/story",
        "https://example.test/\nsecret",
    ],
)
def test_canonical_url_rejects_non_http_credentialed_or_malformed_values(url: str) -> None:
    with pytest.raises(ObsidianClipError) as error:
        canonicalize_source_url(url)
    assert error.value.code == "invalid_url"
    assert url not in str(error.value)


def test_canonical_url_enforces_configured_length_bound() -> None:
    with pytest.raises(ObsidianClipError) as error:
        canonicalize_source_url("https://example.test/" + "x" * 64, max_length=40)
    assert error.value.code == "invalid_url"
