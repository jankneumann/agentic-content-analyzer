"""Pure, bounded parsing for Obsidian Web Clipper Markdown notes.

The filesystem scanner owns safe file access.  This module accepts only the bytes
already read by that boundary and performs no I/O, URL fetching, rendering, logging,
or persistence.
"""

from __future__ import annotations

import hashlib
import ipaddress
import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml
from pydantic import BaseModel, ConfigDict
from yaml.events import AliasEvent
from yaml.nodes import Node

DEFAULT_CAPTURE_CLIENT = "obsidian-web-clipper"
DEFAULT_CONTENT_TYPE_HINT = "other"

_CAPTURE_CLIENTS = frozenset({DEFAULT_CAPTURE_CLIENT})
_CONTENT_TYPE_HINTS = frozenset({"article", "thread", "video", "paper", "other"})
_TRACKING_QUERY_NAMES = frozenset({"fbclid", "gclid"})
_RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
_WIKILINK = re.compile(r"(!?)\[\[([^\]\r\n]+)\]\]")
_CALLOUT = re.compile(
    r"^(?P<indent>[ \t]*)>[ \t]*\[!(?P<kind>[A-Za-z0-9_-]+)\][+-]?"
    r"(?:[ \t]+(?P<title>.*?))?[ \t]*(?P<newline>\r?\n)?$"
)
_INLINE_CODE = re.compile(r"(`+)(.*?)\1")
_FENCE = re.compile(r"^\s*(?P<fence>`{3,}|~{3,})")
_INVALID_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")

_ERROR_MESSAGES = {
    "invalid_encoding": "Clip must be valid UTF-8",
    "note_too_large": "Clip exceeds the configured byte limit",
    "missing_frontmatter": "Clip must start with YAML frontmatter",
    "invalid_frontmatter": "Clip frontmatter is not terminated",
    "frontmatter_too_large": "Clip frontmatter exceeds the configured byte limit",
    "frontmatter_not_mapping": "Clip frontmatter must be a mapping",
    "yaml_invalid": "Clip frontmatter is invalid YAML",
    "yaml_custom_tag": "Clip frontmatter contains a custom YAML tag",
    "yaml_unsupported_type": "Clip frontmatter contains an unsupported YAML value",
    "yaml_duplicate_key": "Clip frontmatter contains a duplicate YAML key",
    "yaml_node_limit": "Clip frontmatter exceeds the YAML node limit",
    "yaml_depth_limit": "Clip frontmatter exceeds the YAML depth limit",
    "yaml_alias_limit": "Clip frontmatter exceeds the YAML alias limit",
    "yaml_string_limit": "Clip frontmatter exceeds the YAML string limit",
    "missing_required_metadata": "Clip is missing required metadata",
    "invalid_url": "Clip source URL is invalid",
    "invalid_captured_at": "Clip capture timestamp is invalid",
    "invalid_capture_client": "Clip capture client is unsupported",
    "invalid_content_type_hint": "Clip content type hint is unsupported",
    "body_too_large": "Normalized clip body exceeds the configured character limit",
}


class ObsidianClipError(ValueError):
    """A stable, input-redacted parser failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(_ERROR_MESSAGES.get(code, "Clip parsing failed"))


@dataclass(frozen=True)
class ClipParseLimits:
    """Hard parser ceilings applied before untrusted data is retained."""

    max_note_bytes: int = 1_048_576
    max_frontmatter_bytes: int = 16_384
    max_yaml_nodes: int = 256
    max_yaml_depth: int = 16
    max_yaml_aliases: int = 8
    max_yaml_string_chars: int = 4_096
    max_body_chars: int = 1_000_000
    max_url_chars: int = 2_048

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if value < 0:
                raise ValueError(f"{name} must be non-negative")


class ObsidianClipMetadata(BaseModel):
    """Closed metadata retained from accepted clip frontmatter."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    source_url: str
    captured_at: datetime
    capture_client: Literal["obsidian-web-clipper"] = DEFAULT_CAPTURE_CLIENT
    content_type_hint: Literal["article", "thread", "video", "paper", "other"] = (
        DEFAULT_CONTENT_TYPE_HINT
    )


@dataclass(frozen=True)
class ParsedObsidianClip:
    """Validated metadata and authoritative normalized Markdown."""

    metadata: ObsidianClipMetadata
    markdown: str
    canonical_url: str
    canonical_url_digest: str
    source_origin: str


class _YamlBoundError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _BoundedSafeLoader(yaml.SafeLoader):
    """SafeLoader with composition-time node, depth, alias, and tag bounds."""

    yaml_implicit_resolvers: ClassVar = {
        key: [resolver for resolver in resolvers if resolver[0] != "tag:yaml.org,2002:timestamp"]
        for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }

    _ALLOWED_TAGS = frozenset(
        {
            "tag:yaml.org,2002:null",
            "tag:yaml.org,2002:bool",
            "tag:yaml.org,2002:int",
            "tag:yaml.org,2002:float",
            "tag:yaml.org,2002:str",
            "tag:yaml.org,2002:seq",
            "tag:yaml.org,2002:map",
        }
    )

    def __init__(self, stream: str, limits: ClipParseLimits) -> None:
        self._limits = limits
        self._node_count = 0
        self._depth = 0
        self._alias_count = 0
        super().__init__(stream)

    def compose_node(self, parent: Node | None, index: int | None) -> Node:
        if self.check_event(AliasEvent):
            self._alias_count += 1
            if self._alias_count > self._limits.max_yaml_aliases:
                raise _YamlBoundError("yaml_alias_limit")
            node = super().compose_node(parent, index)
            if node is None:
                raise _YamlBoundError("yaml_invalid")
            return node

        self._depth += 1
        if self._depth > self._limits.max_yaml_depth:
            self._depth -= 1
            raise _YamlBoundError("yaml_depth_limit")
        try:
            node = super().compose_node(parent, index)
            if node is None:
                raise _YamlBoundError("yaml_invalid")
            self._node_count += 1
            if self._node_count > self._limits.max_yaml_nodes:
                raise _YamlBoundError("yaml_node_limit")
            if node.tag not in self._ALLOWED_TAGS:
                code = (
                    "yaml_unsupported_type"
                    if node.tag.startswith("tag:yaml.org,2002:")
                    else "yaml_custom_tag"
                )
                raise _YamlBoundError(code)
            return node
        finally:
            self._depth -= 1

    def construct_mapping(self, node: Node, deep: bool = False) -> dict[Any, Any]:
        pairs: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in pairs
            except TypeError as exc:
                raise _YamlBoundError("yaml_unsupported_type") from exc
            if duplicate:
                raise _YamlBoundError("yaml_duplicate_key")
            pairs[key] = self.construct_object(value_node, deep=deep)
        return pairs


def parse_obsidian_clip(
    note_bytes: bytes,
    *,
    limits: ClipParseLimits | None = None,
) -> ParsedObsidianClip:
    """Parse validated clip bytes without touching external resources."""

    active_limits = limits or ClipParseLimits()
    if not isinstance(note_bytes, bytes):
        raise TypeError("note_bytes must be bytes")
    if len(note_bytes) > active_limits.max_note_bytes:
        raise ObsidianClipError("note_too_large")
    try:
        text = note_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise ObsidianClipError("invalid_encoding") from None

    frontmatter, body = _split_frontmatter(text, active_limits)
    raw_metadata = _load_frontmatter(frontmatter, active_limits)
    metadata, canonical = _validate_metadata(raw_metadata, active_limits)
    markdown = normalize_obsidian_markdown(body)
    if len(markdown) > active_limits.max_body_chars:
        raise ObsidianClipError("body_too_large")
    return ParsedObsidianClip(
        metadata=metadata,
        markdown=markdown,
        canonical_url=canonical,
        canonical_url_digest=hashlib.sha256(canonical.encode()).hexdigest(),
        source_origin=_origin_from_canonical(canonical),
    )


def canonicalize_source_url(
    source_url: str,
    *,
    max_length: int = 2_048,
    tracking_query_names: frozenset[str] = _TRACKING_QUERY_NAMES,
) -> str:
    """Return deterministic HTTP(S) identity while removing tracking data."""

    if (
        not isinstance(source_url, str)
        or not source_url
        or len(source_url) > max_length
        or any(ord(character) <= 32 or ord(character) == 127 for character in source_url)
        or _INVALID_PERCENT.search(source_url)
    ):
        raise ObsidianClipError("invalid_url")
    try:
        parsed = urlsplit(source_url)
        scheme = parsed.scheme.lower()
        if scheme not in {"http", "https"} or not parsed.netloc:
            raise ObsidianClipError("invalid_url")
        if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
            raise ObsidianClipError("invalid_url")
        hostname = parsed.hostname
        port = parsed.port
    except (UnicodeError, ValueError):
        raise ObsidianClipError("invalid_url") from None
    if not hostname:
        raise ObsidianClipError("invalid_url")

    normalized_host = _normalize_hostname(hostname)
    if not normalized_host:
        raise ObsidianClipError("invalid_url")
    display_host = f"[{normalized_host}]" if ":" in normalized_host else normalized_host
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = display_host if port is None or default_port else f"{display_host}:{port}"

    try:
        query_pairs = parse_qsl(
            parsed.query,
            keep_blank_values=True,
            strict_parsing=False,
            encoding="utf-8",
            errors="strict",
        )
    except (UnicodeDecodeError, ValueError):
        raise ObsidianClipError("invalid_url") from None
    lowered_tracking = {name.lower() for name in tracking_query_names}
    retained = [
        (key, value)
        for key, value in query_pairs
        if not key.lower().startswith("utm_") and key.lower() not in lowered_tracking
    ]
    query = urlencode(sorted(retained), doseq=True)
    canonical = urlunsplit((scheme, netloc, parsed.path, query, ""))
    if len(canonical) > max_length:
        raise ObsidianClipError("invalid_url")
    return canonical


def canonical_url_digest(
    source_url: str,
    *,
    max_length: int = 2_048,
    tracking_query_names: frozenset[str] = _TRACKING_QUERY_NAMES,
) -> str:
    """Hash canonical URL identity for private persistence and comparisons."""

    canonical = canonicalize_source_url(
        source_url,
        max_length=max_length,
        tracking_query_names=tracking_query_names,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def redact_source_url(source_url: str, *, max_length: int = 2_048) -> str:
    """Return only the normalized URL origin permitted in diagnostics."""

    return _origin_from_canonical(canonicalize_source_url(source_url, max_length=max_length))


def normalize_obsidian_markdown(markdown: str) -> str:
    """Normalize supported Obsidian constructs without interpreting active content."""

    if not isinstance(markdown, str):
        raise TypeError("markdown must be a string")
    output: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    for line in markdown.splitlines(keepends=True):
        fence = _FENCE.match(line)
        if fence is not None:
            marker = fence.group("fence")
            if fence_character is None:
                fence_character = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_character and len(marker) >= fence_length:
                fence_character = None
                fence_length = 0
            output.append(line)
            continue
        if fence_character is not None:
            output.append(line)
            continue
        output.append(_normalize_markdown_line(line))
    return "".join(output)


def _split_frontmatter(text: str, limits: ClipParseLimits) -> tuple[str, str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise ObsidianClipError("missing_frontmatter")
    closing_index = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.rstrip("\r\n") == "---"),
        None,
    )
    if closing_index is None:
        raise ObsidianClipError("invalid_frontmatter")
    frontmatter = "".join(lines[1:closing_index])
    if len(frontmatter.encode("utf-8")) > limits.max_frontmatter_bytes:
        raise ObsidianClipError("frontmatter_too_large")
    return frontmatter, "".join(lines[closing_index + 1 :])


def _load_frontmatter(frontmatter: str, limits: ClipParseLimits) -> dict[str, Any]:
    loader = _BoundedSafeLoader(frontmatter, limits)
    try:
        loaded = loader.get_single_data()
    except _YamlBoundError as exc:
        raise ObsidianClipError(exc.code) from None
    except yaml.YAMLError:
        raise ObsidianClipError("yaml_invalid") from None
    finally:
        loader.dispose()
    if not isinstance(loaded, dict):
        raise ObsidianClipError("frontmatter_not_mapping")
    _validate_yaml_values(loaded, limits, ancestors=set())
    return loaded


def _validate_yaml_values(
    value: Any,
    limits: ClipParseLimits,
    *,
    ancestors: set[int],
) -> None:
    if isinstance(value, str):
        if len(value) > limits.max_yaml_string_chars:
            raise ObsidianClipError("yaml_string_limit")
        return
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ObsidianClipError("yaml_unsupported_type")
        return
    if not isinstance(value, (dict, list)):
        raise ObsidianClipError("yaml_unsupported_type")

    identity = id(value)
    if identity in ancestors:
        raise ObsidianClipError("yaml_unsupported_type")
    nested_ancestors = {*ancestors, identity}
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ObsidianClipError("yaml_unsupported_type")
            _validate_yaml_values(key, limits, ancestors=nested_ancestors)
            _validate_yaml_values(child, limits, ancestors=nested_ancestors)
    else:
        for child in value:
            _validate_yaml_values(child, limits, ancestors=nested_ancestors)


def _validate_metadata(
    raw: dict[str, Any],
    limits: ClipParseLimits,
) -> tuple[ObsidianClipMetadata, str]:
    if "source_url" not in raw or "captured_at" not in raw:
        raise ObsidianClipError("missing_required_metadata")
    source_url = raw["source_url"]
    if not isinstance(source_url, str):
        raise ObsidianClipError("invalid_url")
    canonical = canonicalize_source_url(source_url, max_length=limits.max_url_chars)

    captured_at = _parse_captured_at(raw["captured_at"])
    capture_client = raw.get("capture_client", DEFAULT_CAPTURE_CLIENT)
    if not isinstance(capture_client, str) or capture_client not in _CAPTURE_CLIENTS:
        raise ObsidianClipError("invalid_capture_client")
    content_type_hint = raw.get("content_type_hint", DEFAULT_CONTENT_TYPE_HINT)
    if not isinstance(content_type_hint, str) or content_type_hint not in _CONTENT_TYPE_HINTS:
        raise ObsidianClipError("invalid_content_type_hint")

    metadata = ObsidianClipMetadata.model_validate(
        {
            "source_url": source_url,
            "captured_at": captured_at,
            "capture_client": capture_client,
            "content_type_hint": content_type_hint,
        }
    )
    return metadata, canonical


def _parse_captured_at(value: Any) -> datetime:
    if not isinstance(value, str) or _RFC3339.fullmatch(value) is None:
        raise ObsidianClipError("invalid_captured_at")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        raise ObsidianClipError("invalid_captured_at") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ObsidianClipError("invalid_captured_at")
    return parsed


def _normalize_hostname(hostname: str) -> str:
    try:
        return ipaddress.ip_address(hostname).compressed.lower()
    except ValueError:
        try:
            normalized = hostname.encode("idna").decode("ascii").lower()
        except UnicodeError:
            raise ObsidianClipError("invalid_url") from None
        labels = normalized.split(".")
        if any(
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
            or re.fullmatch(r"[a-z0-9-]+", label) is None
            for label in labels
        ):
            raise ObsidianClipError("invalid_url")
        return normalized


def _origin_from_canonical(canonical_url: str) -> str:
    parsed = urlsplit(canonical_url)
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def _normalize_markdown_line(line: str) -> str:
    callout = _CALLOUT.match(line)
    if callout is not None:
        kind = callout.group("kind").replace("_", " ").replace("-", " ").title()
        title = callout.group("title")
        label = kind if not title else f"{kind} — {title.strip()}"
        line = f"{callout.group('indent')}> **{label}**{callout.group('newline') or ''}"

    output: list[str] = []
    cursor = 0
    for code_span in _INLINE_CODE.finditer(line):
        output.append(_normalize_wikilinks(line[cursor : code_span.start()]))
        output.append(code_span.group(0))
        cursor = code_span.end()
    output.append(_normalize_wikilinks(line[cursor:]))
    return "".join(output)


def _normalize_wikilinks(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        embedded = bool(match.group(1))
        raw_target = match.group(2)
        target, separator, alias = raw_target.partition("|")
        if embedded:
            if separator and alias.strip() and not alias.strip().isdigit():
                return f"[Embedded content: {alias.strip()}]"
            return "[Embedded content]"
        if separator and alias.strip():
            return alias.strip()
        page, heading_separator, heading = target.partition("#")
        page = page.strip()
        heading = heading.strip()
        if heading_separator and page and heading:
            return f"{page} > {heading}"
        return heading or page

    return _WIKILINK.sub(replace, text)


__all__ = [
    "ClipParseLimits",
    "ObsidianClipError",
    "ObsidianClipMetadata",
    "ParsedObsidianClip",
    "canonical_url_digest",
    "canonicalize_source_url",
    "normalize_obsidian_markdown",
    "parse_obsidian_clip",
    "redact_source_url",
]
