#!/usr/bin/env python3
"""Validate and generate canonical workflow contract models."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import pprint
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import yaml
from jsonschema.validators import validator_for

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "openspec/contracts/content-workflows"
OPENAPI = CONTRACTS / "openapi/v1.yaml"
EVENT_SCHEMA = CONTRACTS / "events/operation.progress.schema.json"
EVENT_SCHEMAS = tuple(sorted((CONTRACTS / "events").glob("*.schema.json")))
DATABASE_SCHEMA = CONTRACTS / "db/schema.sql"
PYTHON_OUTPUT = CONTRACTS / "generated/models.py"
RUNTIME_PYTHON_OUTPUT = ROOT / "src/contracts/workflow_models.py"
TYPESCRIPT_OUTPUT = CONTRACTS / "generated/types.ts"
RUNTIME_TYPESCRIPT_OUTPUT = ROOT / "web/src/generated/workflow-contracts.ts"


def _ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def _literal(values: list[Any], *, language: str) -> str:
    if language == "python":
        rendered = ", ".join(repr(value) for value in values)
        return f"Literal[{rendered}]"
    return " | ".join(json.dumps(value) for value in values)


def _enum_values(schema: dict[str, Any], schemas: dict[str, Any]) -> list[Any]:
    if "$ref" in schema:
        schema = schemas[_ref_name(schema["$ref"])]
    return cast(list[Any], schema["enum"])


def _python_type(schema: dict[str, Any], *, field_name: str | None = None) -> str:
    if "$ref" in schema:
        return _ref_name(schema["$ref"])
    if "const" in schema:
        return _literal([schema["const"]], language="python")
    if "enum" in schema:
        values = schema["enum"]
        if field_name == "operation_type":
            return "OperationType"
        if field_name == "status" and set(values) == {
            "queued",
            "in_progress",
            "completed",
            "failed",
            "cancelled",
        }:
            return "OperationStatus"
        return _literal(values, language="python")
    if "anyOf" in schema:
        return " | ".join(
            dict.fromkeys(_python_type(part, field_name=field_name) for part in schema["anyOf"])
        )
    if "oneOf" in schema and not schema.get("type") and not schema.get("properties"):
        return " | ".join(
            dict.fromkeys(_python_type(part, field_name=field_name) for part in schema["oneOf"])
        )

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        return " | ".join(
            dict.fromkeys(
                _python_type({**schema, "type": item}, field_name=field_name)
                for item in schema_type
            )
        )
    if schema_type == "null":
        return "None"
    if schema_type == "string":
        if schema.get("format") == "date-time":
            return "datetime"
        if schema.get("format") == "uri":
            return "AnyUrl"
        if schema.get("format") == "uuid":
            return "UUID"
        return "str"
    if schema_type == "integer":
        return "int"
    if schema_type == "number":
        return "float"
    if schema_type == "boolean":
        return "bool"
    if schema_type == "array":
        return f"list[{_python_type(schema.get('items', {}))}]"
    if schema_type == "object" or "additionalProperties" in schema:
        additional = schema.get("additionalProperties")
        value_type = _python_type(additional) if isinstance(additional, dict) else "Any"
        return f"dict[str, {value_type}]"
    return "Any"


def _python_scalar_alias(name: str, schema: dict[str, Any]) -> str:
    if name == "TraceId":
        return (
            'Annotated[str, Field(pattern=r"^[0-9a-f]{32}$"), '
            "AfterValidator(_reject_zero_identifier)]"
        )
    if name == "SpanId":
        return (
            'Annotated[str, Field(pattern=r"^[0-9a-f]{16}$"), '
            "AfterValidator(_reject_zero_identifier)]"
        )
    if "enum" in schema:
        return _literal(schema["enum"], language="python")
    base = _python_type({key: value for key, value in schema.items() if key != "pattern"})
    constraints: list[str] = []
    for source, target in (
        ("minimum", "ge"),
        ("maximum", "le"),
        ("minLength", "min_length"),
        ("maxLength", "max_length"),
    ):
        if source in schema:
            constraints.append(f"{target}={schema[source]!r}")
    pattern = schema.get("pattern")
    # Pydantic's Rust regex engine does not support JSON Schema look-arounds.
    # Composite identifier checks are emitted by the semantic-validator phase.
    if pattern and "(?" not in pattern:
        constraints.append(f"pattern={pattern!r}")
    return f"Annotated[{base}, Field({', '.join(constraints)})]" if constraints else base


def _typescript_scalar_alias(name: str, schema: dict[str, Any]) -> str:
    if name in {
        "TraceId",
        "SpanId",
        "OperationId",
        "Int64NonNegativeString",
        "ClaimGenerationString",
        "Int64PositiveString",
    }:
        return f'Brand<string, "{name}">'
    if "enum" in schema:
        return _literal(schema["enum"], language="typescript")
    return _typescript_type(schema)


def _python_semantic_support() -> list[str]:
    return r"""TRACEPARENT_PATTERN = re.compile(r"^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$")
TRACESTATE_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_*/-]{0,255}$")


def _reject_zero_identifier(value: str) -> str:
    if not value.strip("0"):
        raise ValueError("W3C trace and span identifiers must be non-zero")
    return value


def _validate_schema_version_one(value: Any) -> int:
    if isinstance(value, bool) or type(value) not in (int, float) or value != 1:
        raise ValueError("schema_version must be the JSON number 1")
    return 1


def _is_valid_tracestate(value: str) -> bool:
    if not 1 <= len(value) <= 512:
        return False
    members = value.split(",")
    if not 1 <= len(members) <= 32:
        return False
    keys: set[str] = set()
    for member in members:
        if "=" not in member:
            return False
        key, member_value = member.split("=", 1)
        if TRACESTATE_KEY_PATTERN.fullmatch(key) is None or key in keys:
            return False
        if not 1 <= len(member_value) <= 256:
            return False
        if any(not 0x21 <= ord(char) <= 0x7E or char in ",=" for char in member_value):
            return False
        keys.add(key)
    return True""".splitlines()


def _typescript_semantic_support(stages: list[Any]) -> list[str]:
    rendered_stages = ", ".join(json.dumps(stage) for stage in stages)
    return f"""
export const SIGNED_BIGINT_MAX = 9223372036854775807n;
export const CLAIM_GENERATION_MAX = 9223372036854775806n;
const CANONICAL_DECIMAL = /^(0|[1-9][0-9]*)$/;
const TRACE_ID = /^[0-9a-f]{{32}}$/;
const SPAN_ID = /^[0-9a-f]{{16}}$/;
const AUTHORITY_FINGERPRINT = /^[0-9a-f]{{64}}$/;
const TRACEPARENT = /^00-([0-9a-f]{{32}})-([0-9a-f]{{16}})-[0-9a-f]{{2}}$/;
const TRACESTATE_KEY = /^[a-z0-9][a-z0-9_*/-]{{0,255}}$/;
const OPERATION_STAGES = new Set<string>([{rendered_stages}]);
const CONTEXT_KEYS = new Set([
  "schema_version", "operation_id", "root_operation_id", "parent_operation_id",
  "traceparent", "tracestate", "trace_id", "span_id", "claim_generation",
  "attempt_number", "entrypoint", "service_name", "service_instance_id",
  "environment", "release_revision", "authority_fingerprint", "ownership_epoch",
  "stage", "resource_kind", "resource_key",
]);
const codePointLength = (value: string): number => Array.from(value).length;

function isBoundedDecimal(value: string, minimum: bigint, maximum: bigint): boolean {{
  return value.length <= 19 && CANONICAL_DECIMAL.test(value)
    && BigInt(value) >= minimum && BigInt(value) <= maximum;
}}

export function isOperationId(value: string): value is OperationId {{
  return isBoundedDecimal(value, 1n, SIGNED_BIGINT_MAX);
}}
export function isClaimGenerationString(value: string): value is ClaimGenerationString {{
  return isBoundedDecimal(value, 0n, CLAIM_GENERATION_MAX);
}}
export function isInt64PositiveString(value: string): value is Int64PositiveString {{
  return isBoundedDecimal(value, 1n, SIGNED_BIGINT_MAX);
}}
export function isInt64NonNegativeString(value: string): value is Int64NonNegativeString {{
  return isBoundedDecimal(value, 0n, SIGNED_BIGINT_MAX);
}}
export function isTraceId(value: string): value is TraceId {{
  return TRACE_ID.test(value) && value !== "0".repeat(32);
}}
export function isSpanId(value: string): value is SpanId {{
  return SPAN_ID.test(value) && value !== "0".repeat(16);
}}

function isValidTracestate(value: string): boolean {{
  if (value.length < 1 || value.length > 512) return false;
  const members = value.split(",");
  if (members.length < 1 || members.length > 32) return false;
  const keys = new Set<string>();
  return members.every((member) => {{
    const separator = member.indexOf("=");
    if (separator < 1) return false;
    const key = member.slice(0, separator);
    const memberValue = member.slice(separator + 1);
    if (!TRACESTATE_KEY.test(key) || keys.has(key) || memberValue.length < 1 || memberValue.length > 256) return false;
    for (const char of memberValue) {{
      const code = char.charCodeAt(0);
      if (code < 0x21 || code > 0x7e || char === "," || char === "=") return false;
    }}
    keys.add(key);
    return true;
  }});
}}

/** Mandatory semantic ingress validator; structural validation alone is insufficient. */
export function parseOperationContextEnvelope(value: unknown): OperationContextEnvelope {{
  if (typeof value !== "object" || value === null || Array.isArray(value)) {{
    throw new TypeError("operation context must be an object");
  }}
  const context = value as Record<string, unknown>;
  const keys = Object.keys(context);
  if (keys.length !== CONTEXT_KEYS.size || keys.some((key) => !CONTEXT_KEYS.has(key))) {{
    throw new TypeError("operation context keys do not match schema version 1");
  }}
  const boundedString = (field: string, minimum: number, maximum: number): string => {{
    const item = context[field];
    if (typeof item !== "string" || codePointLength(item) < minimum || codePointLength(item) > maximum) {{
      throw new TypeError(`${{field}} is outside its string bounds`);
    }}
    return item;
  }};
  if (context.schema_version !== 1) throw new TypeError("schema_version must be 1");
  if (typeof context.operation_id !== "string" || !isOperationId(context.operation_id)) throw new TypeError("invalid operation_id");
  if (typeof context.root_operation_id !== "string" || !isOperationId(context.root_operation_id)) throw new TypeError("invalid root_operation_id");
  if (context.parent_operation_id !== null && (typeof context.parent_operation_id !== "string" || !isOperationId(context.parent_operation_id))) throw new TypeError("invalid parent_operation_id");
  if (typeof context.trace_id !== "string" || !isTraceId(context.trace_id)) throw new TypeError("invalid trace_id");
  if (typeof context.span_id !== "string" || !isSpanId(context.span_id)) throw new TypeError("invalid span_id");
  const carrier = typeof context.traceparent === "string" ? TRACEPARENT.exec(context.traceparent) : null;
  if (carrier === null || carrier[1] !== context.trace_id || carrier[2] !== context.span_id) throw new TypeError("invalid or mismatched traceparent");
  if (context.tracestate !== null && (typeof context.tracestate !== "string" || !isValidTracestate(context.tracestate))) throw new TypeError("invalid tracestate");
  if (typeof context.claim_generation !== "string" || !isClaimGenerationString(context.claim_generation)) throw new TypeError("invalid claim_generation");
  if (context.attempt_number !== null && (typeof context.attempt_number !== "string" || !isInt64PositiveString(context.attempt_number) || BigInt(context.attempt_number) !== BigInt(context.claim_generation) + 1n)) throw new TypeError("invalid attempt_number");
  boundedString("entrypoint", 1, 160);
  boundedString("service_name", 1, 100);
  boundedString("service_instance_id", 1, 128);
  boundedString("environment", 1, 32);
  boundedString("release_revision", 1, 64);
  if (context.authority_fingerprint !== null && (typeof context.authority_fingerprint !== "string" || !AUTHORITY_FINGERPRINT.test(context.authority_fingerprint))) throw new TypeError("invalid authority_fingerprint");
  if (context.ownership_epoch !== null && (typeof context.ownership_epoch !== "string" || !isInt64NonNegativeString(context.ownership_epoch))) throw new TypeError("invalid ownership_epoch");
  if (context.stage !== null && (typeof context.stage !== "string" || !OPERATION_STAGES.has(context.stage))) throw new TypeError("invalid stage");
  if (context.resource_kind !== null && (typeof context.resource_kind !== "string" || codePointLength(context.resource_kind) > 64)) throw new TypeError("invalid resource_kind");
  if (context.resource_key !== null && (typeof context.resource_key !== "string" || codePointLength(context.resource_key) > 128)) throw new TypeError("invalid resource_key");
  return context as unknown as OperationContextEnvelope;
}}""".strip().splitlines()


def _python_default(schema: dict[str, Any], *, required: bool) -> tuple[str, list[str]]:
    constraints: list[str] = []
    for source, target in (
        ("minimum", "ge"),
        ("maximum", "le"),
        ("minLength", "min_length"),
        ("maxLength", "max_length"),
        ("minItems", "min_length"),
        ("maxItems", "max_length"),
        ("pattern", "pattern"),
    ):
        if source in schema:
            constraints.append(f"{target}={schema[source]!r}")

    if required and "const" in schema:
        default = repr(schema["const"])
    elif required:
        default = "..."
    elif "default" in schema:
        default = repr(schema["default"])
    else:
        default = "None"
    return default, constraints


def _object_parts(schema: dict[str, Any]) -> tuple[str, dict[str, Any], set[str]]:
    bases: list[str] = []
    properties: dict[str, Any] = dict(schema.get("properties", {}))
    required = set(schema.get("required", []))
    for part in schema.get("allOf", []):
        if "$ref" in part:
            bases.append(_ref_name(part["$ref"]))
        else:
            properties.update(part.get("properties", {}))
            required.update(part.get("required", []))
    if bases:
        base = bases[0]
    elif schema.get("additionalProperties") is True:
        base = "ExtensibleModel"
    else:
        base = "StrictModel"
    return base, properties, required


def _render_python(spec: dict[str, Any], digest: str) -> str:
    schemas = spec["components"]["schemas"]
    operation = schemas["OperationHandle"]["properties"]
    operation_types = operation["operation_type"]["enum"]
    operation_statuses = _enum_values(operation["status"], schemas)
    scalar_aliases = [
        (name, schema)
        for name, schema in schemas.items()
        if not schema.get("properties")
        and not schema.get("allOf")
        and not schema.get("oneOf")
        and ("type" in schema or "enum" in schema)
        and name not in {"OperationStatus", "OperationType"}
    ]
    lines = [
        '"""Generated from contracts/openapi/v1.yaml; do not edit."""',
        "",
        "from __future__ import annotations",
        "",
        "import re",
        "from datetime import datetime",
        "from typing import Annotated, Any, Literal",
        "from uuid import UUID",
        "",
        "from pydantic import (",
        "    AfterValidator,",
        "    AnyUrl,",
        "    BaseModel,",
        "    ConfigDict,",
        "    Field,",
        "    field_validator,",
        "    model_validator,",
        ")",
        "",
        f'CONTRACT_SHA256 = "{digest}"',
        "",
        *_python_semantic_support(),
        "",
        f"OperationStatus = {_literal(operation_statuses, language='python')}",
        f"OperationType = {_literal(operation_types, language='python')}",
        *[f"{name} = {_python_scalar_alias(name, schema)}" for name, schema in scalar_aliases],
        "",
        "",
        "class StrictModel(BaseModel):",
        '    model_config = ConfigDict(extra="forbid")',
        "",
        "",
        "class ExtensibleModel(BaseModel):",
        '    model_config = ConfigDict(extra="allow")',
        "",
        "",
        "COMMAND_FIELD_SCHEMAS: dict[str, dict[str, Any]] = "
        + pprint.pformat(_command_field_schemas(spec), sort_dicts=False, width=100),
    ]

    aliases: list[tuple[str, dict[str, Any]]] = []
    for name, schema in schemas.items():
        is_alias = (
            "oneOf" in schema
            and not schema.get("type")
            and not schema.get("properties")
            and not schema.get("allOf")
        )
        if is_alias:
            aliases.append((name, schema))
            continue
        if not (schema.get("type") == "object" or schema.get("properties") or schema.get("allOf")):
            continue

        base, properties, required = _object_parts(schema)
        lines.extend(["", "", f"class {name}({base}):"])
        if not properties:
            lines.append("    pass")
            continue
        for field_name, field_schema in properties.items():
            field_type = _python_type(field_schema, field_name=field_name)
            is_required = field_name in required
            if not is_required and "default" not in field_schema and "None" not in field_type:
                field_type = f"{field_type} | None"
            default, constraints = _python_default(field_schema, required=is_required)
            if is_required and constraints:
                constraint_args = ", ".join(constraints)
                lines.append(f"    {field_name}: Annotated[{field_type}, Field({constraint_args})]")
            elif is_required and "const" in field_schema:
                lines.append(f"    {field_name}: {field_type} = {default}")
            elif is_required:
                lines.append(f"    {field_name}: {field_type}")
            elif constraints:
                value = f"Field({default}, {', '.join(constraints)})"
                lines.append(f"    {field_name}: {field_type} = {value}")
            else:
                lines.append(f"    {field_name}: {field_type} = {default}")

        schema_version = properties.get("schema_version", {})
        if schema_version.get("const") == 1:
            lines.extend(
                [
                    "",
                    '    @field_validator("schema_version", mode="before")',
                    "    @classmethod",
                    f"    def validate_{name.lower()}_schema_version(cls, value: Any) -> int:",
                    "        return _validate_schema_version_one(value)",
                ]
            )
        if name == "OperationContextEnvelope":
            lines.extend(
                [
                    "",
                    '    @model_validator(mode="after")',
                    "    def validate_semantic_context(self) -> OperationContextEnvelope:",
                    "        match = TRACEPARENT_PATTERN.fullmatch(self.traceparent)",
                    "        if match is None:",
                    '            raise ValueError("traceparent must be canonical W3C version 00")',
                    '        _, carrier_trace_id, carrier_parent_id, _ = self.traceparent.split("-")',
                    "        if carrier_trace_id != self.trace_id or carrier_parent_id != self.span_id:",
                    '            raise ValueError("traceparent identifiers must match trace_id and span_id")',
                    "        if self.tracestate is not None and not _is_valid_tracestate(self.tracestate):",
                    '            raise ValueError("tracestate must use the bounded W3C simple-key subset")',
                    "        if self.attempt_number is not None and int(self.attempt_number) != int(self.claim_generation) + 1:",
                    '            raise ValueError("attempt_number must equal claim_generation + 1")',
                    "        return self",
                ]
            )
        if name == "OperationAttemptSummary":
            lines.extend(
                [
                    "",
                    '    @model_validator(mode="after")',
                    "    def validate_attempt_number(self) -> OperationAttemptSummary:",
                    "        if int(self.attempt_number) != int(self.claim_generation) + 1:",
                    '            raise ValueError("attempt_number must equal claim_generation + 1")',
                    "        return self",
                ]
            )

    for name, schema in aliases:
        union = _python_type(schema)
        discriminator = schema.get("discriminator", {}).get("propertyName")
        lines.extend(["", ""])
        if discriminator:
            lines.extend(
                [
                    f"{name} = Annotated[",
                    f"    {union},",
                    f'    Field(discriminator="{discriminator}"),',
                    "]",
                ]
            )
        else:
            lines.append(f"{name} = {union}")
    lines.extend(
        [
            "",
            "",
            "def parse_operation_context_envelope(value: Any) -> OperationContextEnvelope:",
            '    """Validate structure and all cross-field operation-context invariants."""',
            "    return OperationContextEnvelope.model_validate(value)",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _command_field_schemas(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    schemas = spec["components"]["schemas"]
    mapping = schemas["IngestCommand"]["discriminator"]["mapping"]

    def resolve(schema: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        properties: dict[str, Any] = {}
        required: list[str] = []
        for part in schema.get("allOf", [schema]):
            if "$ref" in part:
                part_properties, part_required = resolve(schemas[_ref_name(part["$ref"])])
            else:
                part_properties = dict(part.get("properties", {}))
                part_required = list(part.get("required", []))
            properties.update(part_properties)
            required.extend(name for name in part_required if name not in required)
        return properties, required

    result: dict[str, dict[str, Any]] = {}
    for key, ref in mapping.items():
        properties, required = resolve(schemas[_ref_name(ref)])
        properties = {
            name: schema for name, schema in properties.items() if not schema.get("x-internal")
        }
        required = [name for name in required if name in properties]
        result[key] = {"properties": properties, "required": required}
    return result


def _typescript_type(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        return _ref_name(schema["$ref"])
    if "const" in schema:
        return _literal([schema["const"]], language="typescript")
    if "enum" in schema:
        return _literal(schema["enum"], language="typescript")
    if "anyOf" in schema:
        return " | ".join(dict.fromkeys(_typescript_type(part) for part in schema["anyOf"]))
    if "oneOf" in schema and not schema.get("type") and not schema.get("properties"):
        return " | ".join(dict.fromkeys(_typescript_type(part) for part in schema["oneOf"]))

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        return " | ".join(
            dict.fromkeys(_typescript_type({**schema, "type": item}) for item in schema_type)
        )
    if schema_type == "null":
        return "null"
    if schema_type == "string":
        return "string"
    if schema_type in {"integer", "number"}:
        return "number"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "array":
        return f"Array<{_typescript_type(schema.get('items', {}))}>"
    if schema_type == "object" or "additionalProperties" in schema:
        additional = schema.get("additionalProperties")
        value_type = _typescript_type(additional) if isinstance(additional, dict) else "unknown"
        return f"Record<string, {value_type}>"
    return "unknown"


def _render_typescript(spec: dict[str, Any], digest: str) -> str:
    schemas = spec["components"]["schemas"]
    operation = schemas["OperationHandle"]["properties"]
    operation_statuses = _enum_values(operation["status"], schemas)
    scalar_aliases = [
        (name, schema)
        for name, schema in schemas.items()
        if not schema.get("properties")
        and not schema.get("allOf")
        and not schema.get("oneOf")
        and ("type" in schema or "enum" in schema)
        and name not in {"OperationStatus", "OperationType"}
    ]
    lines = [
        "// Generated from contracts/openapi/v1.yaml; do not edit.",
        f'export const CONTRACT_SHA256 = "{digest}" as const;',
        "",
        f"export type OperationStatus = {_literal(operation_statuses, language='typescript')};",
        f"export type OperationType = {_literal(operation['operation_type']['enum'], language='typescript')};",
        "type Brand<Value, Name extends string> = Value & { readonly __brand: Name };",
        *[
            f"export type {name} = {_typescript_scalar_alias(name, schema)};"
            for name, schema in scalar_aliases
        ],
        *_typescript_semantic_support(schemas["OperationStage"]["enum"]),
    ]

    aliases: list[tuple[str, dict[str, Any]]] = []
    for name, schema in schemas.items():
        is_alias = (
            "oneOf" in schema
            and not schema.get("type")
            and not schema.get("properties")
            and not schema.get("allOf")
        )
        if is_alias:
            aliases.append((name, schema))
            continue
        if not (schema.get("type") == "object" or schema.get("properties") or schema.get("allOf")):
            continue

        base, properties, required = _object_parts(schema)
        extends = f" extends {base}" if base not in {"StrictModel", "ExtensibleModel"} else ""
        lines.extend(["", f"export interface {name}{extends} {{"])
        if schema.get("additionalProperties") is True:
            lines.append("  [key: string]: unknown;")
        for field_name, field_schema in properties.items():
            if field_schema.get("x-internal"):
                continue
            optional = "" if field_name in required else "?"
            lines.append(f"  {field_name}{optional}: {_typescript_type(field_schema)};")
        lines.append("}")

    for name, schema in aliases:
        lines.extend(["", f"export type {name} = {_typescript_type(schema)};"])
    return "\n".join(lines).rstrip() + "\n"


def _validated_contract() -> dict[str, Any]:
    spec = cast(dict[str, Any], yaml.safe_load(OPENAPI.read_text()))
    if spec.get("openapi") != "3.1.0":
        raise ValueError("canonical workflow contract must use OpenAPI 3.1.0")
    if not isinstance(spec.get("paths"), dict) or not spec["paths"]:
        raise ValueError("canonical workflow contract must declare paths")
    schemas = spec.get("components", {}).get("schemas")
    if not isinstance(schemas, dict) or not schemas:
        raise ValueError("canonical workflow contract must declare component schemas")

    def validate_refs(node: Any) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if ref is not None:
                if not ref.startswith("#/components/"):
                    raise ValueError(f"unsupported non-local OpenAPI reference: {ref}")
                target: Any = spec
                for token in ref.removeprefix("#/").split("/"):
                    target = target[token.replace("~1", "/").replace("~0", "~")]
            for value in node.values():
                validate_refs(value)
        elif isinstance(node, list):
            for value in node:
                validate_refs(value)

    validate_refs(spec)
    for name, schema in schemas.items():
        try:
            validator_for(schema).check_schema(schema)
        except Exception as exc:
            raise ValueError(f"invalid component schema {name}: {exc}") from exc
    for event_path in EVENT_SCHEMAS:
        event_schema = json.loads(event_path.read_text())
        try:
            validator_for(event_schema).check_schema(event_schema)
        except Exception as exc:
            raise ValueError(f"invalid event schema {event_path.name}: {exc}") from exc

    context_event = json.loads((CONTRACTS / "events/operation-context-v1.schema.json").read_text())
    context_openapi = schemas["OperationContextEnvelope"]
    if set(context_event["required"]) != set(context_openapi["required"]):
        raise ValueError("operation context required fields drift between OpenAPI and events")

    nullable = {
        "parent_operation_id",
        "tracestate",
        "attempt_number",
        "authority_fingerprint",
        "ownership_epoch",
        "stage",
        "resource_kind",
        "resource_key",
    }

    def permits_null(schema: dict[str, Any]) -> bool:
        schema_type = schema.get("type")
        return (
            schema_type == "null"
            or (isinstance(schema_type, list) and "null" in schema_type)
            or any(permits_null(part) for part in schema.get("oneOf", []))
        )

    for field in context_event["properties"]:
        event_nullable = permits_null(context_event["properties"][field])
        openapi_nullable = permits_null(context_openapi["properties"][field])
        if event_nullable != (field in nullable) or openapi_nullable != (field in nullable):
            raise ValueError(f"operation context nullability drift for {field}")

    sql = DATABASE_SCHEMA.read_text()
    for required_fragment in (
        "submission_context JSONB NULL",
        "operation_observation_attempts",
        "telemetry_process_health",
        "ck_pgqueuer_jobs_context_identity",
        "ck_audit_log_trace_id",
        "ck_workflow_terminal_events_trace_id",
        "environment_ownership",
    ):
        if required_fragment not in sql:
            raise ValueError(f"database observability contract missing {required_fragment}")
    return spec


def _format_python(source: str) -> str:
    ruff = shutil.which("ruff")
    if ruff is None:
        raise RuntimeError(
            "ruff is required for deterministic Python generation; install it or add it to PATH"
        )
    result = subprocess.run(
        [ruff, "format", "--stdin-filename", str(PYTHON_OUTPUT), "-"],
        input=source,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout


def _diff(path: Path, expected: str) -> str:
    actual = path.read_text() if path.exists() else ""
    return "".join(
        difflib.unified_diff(
            actual.splitlines(keepends=True),
            expected.splitlines(keepends=True),
            fromfile=str(path),
            tofile=f"generated:{path}",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail when generated files drift")
    args = parser.parse_args()

    spec = _validated_contract()
    # Path.read_text() applies universal newline translation, keeping the
    # generated contract identity stable across Git CRLF checkouts.
    digest = hashlib.sha256(OPENAPI.read_text().encode()).hexdigest()
    outputs = {
        PYTHON_OUTPUT: _format_python(_render_python(spec, digest)),
        RUNTIME_PYTHON_OUTPUT: _format_python(_render_python(spec, digest)),
        TYPESCRIPT_OUTPUT: _render_typescript(spec, digest),
        RUNTIME_TYPESCRIPT_OUTPUT: _render_typescript(spec, digest),
    }
    if args.check:
        drift = {path: _diff(path, content) for path, content in outputs.items()}
        drift = {path: diff for path, diff in drift.items() if diff}
        if drift:
            for diff in drift.values():
                print(diff, end="")
            return 1
        print("workflow contracts are valid and generated files are current")
        return 0

    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        print(f"generated {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
