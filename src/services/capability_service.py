"""Registry-derived capability document shared by every public interface."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from typing import get_args
from urllib.parse import urlsplit

from src.config.sources import SourcesConfig, source_key
from src.contracts.workflow_models import (
    COMMAND_FIELD_SCHEMAS,
    CapabilityDocument,
    CapabilityField,
    ConfiguredSource,
    ConfiguredSourcePage,
    OperationType,
    ResourceReference,
    SourceCapability,
)
from src.ingestion.registry import SOURCE_REGISTRY, SourceRegistry

CONTRACT_VERSION = "2.0.0"
TRANSPORT_ORDER = ("cli", "http", "mcp", "frontend")


class CapabilityService:
    def __init__(self, registry: SourceRegistry = SOURCE_REGISTRY) -> None:
        self.registry = registry

    def get_capabilities(self, *, limit: int = 50, cursor: str | None = None) -> CapabilityDocument:
        start = _decode_cursor(cursor)
        descriptors = list(self.registry)
        page = descriptors[start : start + limit]
        source_commands = []
        for descriptor in page:
            field_schema = COMMAND_FIELD_SCHEMAS[descriptor.key]
            required = set(field_schema["required"])
            fields = [
                _capability_field(name, schema, name in required)
                for name, schema in field_schema["properties"].items()
                if name != "configured_sources"
            ]
            source_commands.append(
                SourceCapability(
                    key=descriptor.key,
                    display_name=descriptor.display_name,
                    emitted_sources=sorted(source.value for source in descriptor.emitted_sources),
                    scheduled=descriptor.scheduled,
                    transports=[
                        transport
                        for transport in TRANSPORT_ORDER
                        if transport in descriptor.transports
                    ],
                    supports_force=descriptor.options.supports_force,
                    supports_date_range=descriptor.options.supports_date_range,
                    supports_preview=descriptor.options.supports_preview,
                    requires_identifier=descriptor.options.requires_identifier,
                    fields=fields,
                )
            )
        resource_annotation = ResourceReference.model_fields["type"].annotation
        return CapabilityDocument(
            contract_version=CONTRACT_VERSION,
            source_commands=source_commands,
            operation_types=list(get_args(OperationType)),
            resource_types=list(get_args(resource_annotation)),
            next_cursor=_next_cursor(start, limit, len(descriptors)),
        )

    def list_configured_sources(
        self,
        config: SourcesConfig,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> ConfiguredSourcePage:
        start = _decode_cursor(cursor)
        configured: list[ConfiguredSource] = []
        for source in config.sources:
            descriptor = self.registry.descriptor_for_config(source)
            raw_key = source_key(source)
            data = _public_configuration(source.model_dump(mode="json"))
            configured.append(
                ConfiguredSource(
                    key=f"src_{hashlib.sha256(raw_key.encode()).hexdigest()[:20]}",
                    command_key=descriptor.key,
                    source_type=source.type,
                    name=None,
                    enabled=source.enabled,
                    origin=source.origin,
                    configuration=data,
                )
            )
        configured.sort(key=lambda source: (source.command_key, source.key))
        return ConfiguredSourcePage(
            data=configured[start : start + limit],
            next_cursor=_next_cursor(start, limit, len(configured)),
        )


def _capability_field(
    name: str,
    schema: dict,
    required: bool,
) -> CapabilityField:
    constraints = {
        key: schema[key]
        for key in (
            "minimum",
            "maximum",
            "minLength",
            "maxLength",
            "minItems",
            "maxItems",
            "pattern",
            "uniqueItems",
        )
        if key in schema
    }
    schema_type = schema.get("type", "object")
    if isinstance(schema_type, list):
        schema_type = next((item for item in schema_type if item != "null"), "null")
    enum = schema.get("enum")
    if enum is None and "const" in schema:
        enum = [str(schema["const"])]
    return CapabilityField(
        name=name,
        type=schema_type,
        required=required,
        description=schema.get("description"),
        format=schema.get("format"),
        enum=enum,
        default=schema.get("default"),
        constraints=constraints,
    )


def _decode_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        offset = int(payload["offset"])
        if offset < 0:
            raise ValueError
        return offset
    except (
        binascii.Error,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
    ) as exc:
        raise ValueError("Invalid capability cursor") from exc


def _next_cursor(start: int, limit: int, total: int) -> str | None:
    offset = start + limit
    if offset >= total:
        return None
    raw = json.dumps({"offset": offset}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


_PUBLIC_CONFIG_FIELDS = frozenset(
    {
        "days_back",
        "enabled",
        "extract_pdf",
        "include_deleted",
        "max_entries",
        "max_pdf_pages",
        "max_results",
        "max_threads",
        "min_citation_count",
        "origin",
        "pdf_extraction",
        "provider",
        "recency_filter",
        "request_delay",
        "sort_by",
        "stt_provider",
        "transcribe",
        "type",
        "visibility",
    }
)


def _public_configuration(value: dict) -> dict:
    """Project an explicit safe allowlist for agent-facing discovery."""
    public = {key: value[key] for key in _PUBLIC_CONFIG_FIELDS if key in value}
    url = value.get("url")
    if isinstance(url, str):
        hostname = urlsplit(url).hostname
        if hostname:
            public["host"] = hostname
    return public
