from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import TypeAdapter, ValidationError

from src.config.sources import GmailSource, ReadwiseSource, RSSSource, SourcesConfig
from src.contracts.workflow_models import (
    IngestCommand,
    UrlIngestCommand as GeneratedUrlIngestCommand,
)
from src.ingestion.commands import UrlIngestCommand
from src.ingestion.registry import SOURCE_REGISTRY
from src.ingestion.service import IngestionService
from src.services.capability_service import CapabilityService

CONTRACT = Path(
    "openspec/changes/unify-content-workflows-agentic-surfaces/contracts/openapi/v1.yaml"
)


def test_capabilities_match_openapi_discriminator_and_fields() -> None:
    document = CapabilityService(SOURCE_REGISTRY).get_capabilities()
    openapi = yaml.safe_load(CONTRACT.read_text())
    schemas = openapi["components"]["schemas"]
    mapping = schemas["IngestCommand"]["discriminator"]["mapping"]

    assert document.contract_version == "2.0.0"
    assert [source.key for source in document.source_commands] == list(mapping)

    for capability in document.source_commands:
        schema_name = mapping[capability.key].rsplit("/", 1)[-1]
        schema = schemas[schema_name]
        properties: dict = {}
        required: set[str] = set()
        for branch in schema.get("allOf", [schema]):
            if "$ref" in branch:
                branch = schemas[branch["$ref"].rsplit("/", 1)[-1]]
            properties.update(branch.get("properties", {}))
            required.update(branch.get("required", []))

        properties.pop("configured_sources", None)
        required.discard("configured_sources")
        assert [field.name for field in capability.fields] == list(properties)
        assert {field.name for field in capability.fields if field.required} == required
        for field in capability.fields:
            schema = properties[field.name]
            assert field.type == schema["type"]
            assert field.format == schema.get("format")
            assert field.enum == (
                schema.get("enum") or ([str(schema["const"])] if "const" in schema else None)
            )
            assert field.default == schema.get("default")
            assert field.constraints == {
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


def test_capabilities_are_registry_derived_and_agent_usable() -> None:
    document = CapabilityService(SOURCE_REGISTRY).get_capabilities()
    url = next(source for source in document.source_commands if source.key == "url")
    identifier = next(source for source in document.source_commands if source.key == "arxiv_paper")

    assert url.emitted_sources == ["rss", "webpage", "youtube"]
    assert url.transports == ["cli", "http", "mcp", "frontend"]
    assert next(field for field in url.fields if field.name == "routing_mode").enum == [
        "auto",
        "webpage",
    ]
    assert next(field for field in identifier.fields if field.name == "identifier").required
    assert url.supports_force
    assert not url.supports_date_range
    assert not url.supports_preview
    assert not url.requires_identifier
    assert identifier.requires_identifier
    assert "ingestion.execute" in document.operation_types
    assert "content" in document.resource_types


def test_runtime_commands_reexport_generated_contract_models() -> None:
    assert UrlIngestCommand is GeneratedUrlIngestCommand
    command = UrlIngestCommand(url="https://example.com/article")
    assert str(command.url) == "https://example.com/article"

    with pytest.raises(ValidationError):
        UrlIngestCommand(url="not a uri")

    with pytest.raises(ValueError, match="kind"):
        IngestionService().execute({"url": "https://example.com/article"})

    parsed = TypeAdapter(IngestCommand).validate_python(
        {"kind": "url", "url": "https://example.com/article"}
    )
    assert isinstance(parsed, UrlIngestCommand)


def test_capability_and_configured_source_discovery_are_safe_cursor_pages() -> None:
    service = CapabilityService(SOURCE_REGISTRY)
    first = service.get_capabilities(limit=1)
    second = service.get_capabilities(limit=1, cursor=first.next_cursor)
    assert first.next_cursor
    assert first.source_commands[0].key != second.source_commands[0].key
    assert all(
        field.name != "configured_sources"
        for capability in service.get_capabilities().source_commands
        for field in capability.fields
    )

    secret = "DO-NOT-DISCLOSE"
    configured = SourcesConfig(
        sources=[
            ReadwiseSource(),
            RSSSource(
                url=f"https://user:pass@example.com/private?token={secret}",
                name=secret,
                tags=[secret],
            ),
            GmailSource(query=f"subject:{secret}"),
        ]
    )
    page = service.list_configured_sources(configured, limit=100)
    serialized = page.model_dump_json()

    assert secret not in serialized
    assert "user:pass" not in serialized
    assert "/private" not in serialized
    assert "subject:" not in serialized
    assert '"name":null' in serialized
    assert "example.com" in serialized
    assert all(source.key.startswith("src_") for source in page.data)
    readwise = next(source for source in page.data if source.source_type == "readwise")
    assert readwise.command_key == "readwise"
    assert "url" not in readwise.configuration
