from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import TypeAdapter, ValidationError

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
