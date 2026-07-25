"""Schema loading and validation for the pinned gen-eval evaluation contract.

Every function here is pure: it reads vendored JSON and returns a list of human-
readable error strings. No gen-eval import, no subprocess, no network — so contract
validation produces a definite verdict whether or not an evaluation runner exists.

Schemas are loaded through ``importlib.resources`` from this package, mirroring
``src/release_smoke/evidence.py``. The durable copies under
``openspec/contracts/cli-gen-eval/`` are byte-identical and are the source of truth
for review; ``tests/cli_gen_eval/test_contract.py`` enforces the parity.
"""

from __future__ import annotations

import json
from functools import cache
from importlib.resources import files
from typing import Any, Literal, cast

import jsonschema

from src.cli_gen_eval import CONTRACT_VERSION

SchemaKind = Literal["descriptor", "scenario", "report"]

_SCHEMA_FILES: dict[str, str] = {
    "descriptor": "interface-descriptor.schema.json",
    "scenario": "scenario.schema.json",
    "report": "eval-report.schema.json",
}

# Categories that submit or control durable work. Kept here rather than in the gate so
# the contract layer can reject a mis-categorized scenario without a runner present.
MUTATING_CATEGORIES = frozenset({"workflow-submission", "operation-control"})
READ_ONLY_CATEGORIES = frozenset({"plumbing", "discovery", "validation"})
KNOWN_CATEGORIES = MUTATING_CATEGORIES | READ_ONLY_CATEGORIES


class ContractError(RuntimeError):
    """Raised when the vendored contract itself is unusable."""


@cache
def schema(kind: SchemaKind) -> dict[str, Any]:
    """Return the vendored JSON Schema for ``kind``.

    Raises ContractError when the schema is missing, unparseable, or annotated with a
    contract version other than the pin — a stale vendored schema must not silently
    validate against current artifacts.
    """
    try:
        filename = _SCHEMA_FILES[kind]
    except KeyError:
        raise ContractError(f"unknown schema kind {kind!r}") from None

    resource = files("src.cli_gen_eval.schemas").joinpath(filename)
    try:
        document = cast(dict[str, Any], json.loads(resource.read_text(encoding="utf-8")))
    except FileNotFoundError as exc:
        raise ContractError(f"vendored schema {filename} is missing") from exc
    except ValueError as exc:
        raise ContractError(f"vendored schema {filename} is not valid JSON: {exc}") from exc

    annotated = document.get("x-gen-eval-contract-version")
    if annotated != CONTRACT_VERSION:
        raise ContractError(
            f"vendored schema {filename} declares contract version {annotated!r} "
            f"but the pin is {CONTRACT_VERSION!r}; regenerate with "
            f"scripts/generate_gen_eval_contract_schemas.py"
        )
    return document


def _location(error: jsonschema.ValidationError) -> str:
    return ".".join(str(part) for part in error.absolute_path) or "<root>"


def _schema_errors(document: object, kind: SchemaKind) -> list[str]:
    validator_cls = jsonschema.validators.validator_for(schema(kind))
    validator = validator_cls(schema(kind))
    return [
        f"{_location(error)}: {error.message}"
        for error in sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    ]


def validate_descriptor(document: object) -> list[str]:
    """Validate an interface descriptor. Returns [] when valid."""
    return _schema_errors(document, "descriptor")


def validate_scenario(document: object) -> list[str]:
    """Validate one scenario, including repository-specific category rules."""
    errors = _schema_errors(document, "scenario")
    if not isinstance(document, dict):
        return errors

    category = document.get("category")
    if isinstance(category, str) and category not in KNOWN_CATEGORIES:
        errors.append(
            f"category: {category!r} is not one of the declared categories "
            f"{sorted(KNOWN_CATEGORIES)}"
        )
    return errors


def validate_report(document: object) -> list[str]:
    """Validate an evaluation report against the pinned report schema.

    Schema conformance only. Sufficiency rules — minimum scenario counts, empty
    ``unevaluated_interfaces``, pass-rate threshold — belong to the report validator,
    because they depend on which categories were selected for the run.
    """
    return _schema_errors(document, "report")


def is_mutating(category: str) -> bool:
    """Whether scenarios in ``category`` submit or control durable work."""
    return category in MUTATING_CATEGORIES
