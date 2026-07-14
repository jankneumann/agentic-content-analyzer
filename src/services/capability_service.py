"""Registry-derived capability document shared by every public interface."""

from __future__ import annotations

from typing import get_args

from src.contracts.workflow_models import (
    COMMAND_FIELD_SCHEMAS,
    CapabilityDocument,
    CapabilityField,
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

    def get_capabilities(self) -> CapabilityDocument:
        source_commands = []
        for descriptor in self.registry:
            field_schema = COMMAND_FIELD_SCHEMAS[descriptor.key]
            required = set(field_schema["required"])
            fields = [
                _capability_field(name, schema, name in required)
                for name, schema in field_schema["properties"].items()
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
