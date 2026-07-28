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


def _python_default(schema: dict[str, Any], *, required: bool) -> tuple[str, list[str]]:
    constraints: list[str] = []
    for source, target in (
        ("minimum", "ge"),
        ("maximum", "le"),
        ("minLength", "min_length"),
        ("maxLength", "max_length"),
        ("minItems", "min_length"),
        ("maxItems", "max_length"),
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
        if "enum" in schema
        and not schema.get("properties")
        and not schema.get("allOf")
        and name not in {"OperationStatus", "OperationType"}
    ]
    lines = [
        '"""Generated from contracts/openapi/v1.yaml; do not edit."""',
        "",
        "from __future__ import annotations",
        "",
        "from datetime import datetime",
        "from typing import Annotated, Any, Literal",
        "",
        "from pydantic import AnyUrl, BaseModel, ConfigDict, Field",
        "",
        f'CONTRACT_SHA256 = "{digest}"',
        "",
        f"OperationStatus = {_literal(operation_statuses, language='python')}",
        f"OperationType = {_literal(operation_types, language='python')}",
        *[
            f"{name} = {_literal(schema['enum'], language='python')}"
            for name, schema in scalar_aliases
        ],
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
        if "enum" in schema
        and not schema.get("properties")
        and not schema.get("allOf")
        and name not in {"OperationStatus", "OperationType"}
    ]
    lines = [
        "// Generated from contracts/openapi/v1.yaml; do not edit.",
        f'export const CONTRACT_SHA256 = "{digest}" as const;',
        "",
        f"export type OperationStatus = {_literal(operation_statuses, language='typescript')};",
        f"export type OperationType = {_literal(operation['operation_type']['enum'], language='typescript')};",
        *[
            f"export type {name} = {_literal(schema['enum'], language='typescript')};"
            for name, schema in scalar_aliases
        ],
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
    event_schema = json.loads(EVENT_SCHEMA.read_text())
    validator_for(event_schema).check_schema(event_schema)
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
