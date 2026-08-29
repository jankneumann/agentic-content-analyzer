"""Contract tests for the immutable runtime operation context boundary."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from src.contracts.operation_context import (
    OperationOutcome,
    OperationStage,
    bind_operation_context,
    extract_w3c_context,
    get_current_operation_context,
    inject_w3c_context,
    parse_operation_context,
)
from src.contracts.workflow_models import parse_operation_context_envelope

SIGNED_BIGINT_MAX = 9_223_372_036_854_775_807
CLAIM_GENERATION_MAX = SIGNED_BIGINT_MAX - 1
ROOT = Path(__file__).resolve().parents[2]


def valid_context() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "operation_id": str(SIGNED_BIGINT_MAX),
        "root_operation_id": "1",
        "parent_operation_id": None,
        "traceparent": "00-11111111111111111111111111111111-2222222222222222-01",
        "tracestate": "vendor=value",
        "trace_id": "11111111111111111111111111111111",
        "span_id": "2222222222222222",
        "claim_generation": str(CLAIM_GENERATION_MAX),
        "attempt_number": str(SIGNED_BIGINT_MAX),
        "entrypoint": "api.submit",
        "service_name": "api",
        "service_instance_id": "instance-1",
        "environment": "test",
        "release_revision": "a" * 40,
        "stage": "submit",
        "resource_kind": None,
        "resource_key": "😀" * 128,
    }


def assert_all_python_validators_accept(payload: dict[str, Any]) -> None:
    runtime = parse_operation_context(payload)
    generated = parse_operation_context_envelope(payload)
    assert runtime.model_dump(mode="json") == generated.model_dump(mode="json")


def assert_all_python_validators_reject(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        parse_operation_context(payload)
    with pytest.raises(ValidationError):
        parse_operation_context_envelope(payload)


def test_signed_bigint_and_claim_generation_boundaries_match_generated_validator() -> None:
    assert_all_python_validators_accept(valid_context())
    invalid_payloads = (
        {**valid_context(), "operation_id": str(SIGNED_BIGINT_MAX + 1)},
        {**valid_context(), "root_operation_id": str(SIGNED_BIGINT_MAX + 1)},
        {**valid_context(), "claim_generation": str(CLAIM_GENERATION_MAX + 1)},
        {**valid_context(), "attempt_number": str(SIGNED_BIGINT_MAX + 1)},
        {**valid_context(), "operation_id": "9" * 100_000},
        {**valid_context(), "claim_generation": "9" * 100_000},
    )
    for payload in invalid_payloads:
        assert_all_python_validators_reject(payload)


@pytest.mark.parametrize("schema_version", [1, 1.0])
def test_json_numeric_schema_version_parity_accepts_one(schema_version: int | float) -> None:
    assert_all_python_validators_accept({**valid_context(), "schema_version": schema_version})


@pytest.mark.parametrize("schema_version", [True, "1"])
def test_json_numeric_schema_version_parity_rejects_aliases(schema_version: object) -> None:
    assert_all_python_validators_reject({**valid_context(), "schema_version": schema_version})


@pytest.mark.parametrize(
    "changes",
    [
        {"trace_id": "0" * 32, "traceparent": f"00-{'0' * 32}-2222222222222222-01"},
        {"span_id": "0" * 16, "traceparent": f"00-{'1' * 32}-{'0' * 16}-01"},
        {"traceparent": "00-33333333333333333333333333333333-2222222222222222-01"},
        {"traceparent": "00-11111111111111111111111111111111-3333333333333333-01"},
        {"traceparent": "00-" + "1" * 10_000},
        {"tracestate": "vendor=value,vendor=duplicate"},
        {"tracestate": "Vendor=value"},
        {"tracestate": "vendor=value="},
        {"tracestate": "vendor=" + "x" * 257},
        {"tracestate": "a=b," * 32 + "z=y"},
        {"tracestate": "vendor=" + "x" * 513},
        {"attempt_number": "1"},
    ],
)
def test_composite_w3c_and_generation_mismatches_are_rejected(changes: dict[str, Any]) -> None:
    assert_all_python_validators_reject({**valid_context(), **changes})


def test_unicode_bounds_are_measured_in_code_points() -> None:
    for field, maximum in {
        "entrypoint": 160,
        "service_name": 100,
        "service_instance_id": 128,
        "environment": 32,
        "release_revision": 64,
        "resource_kind": 64,
        "resource_key": 128,
    }.items():
        assert_all_python_validators_accept({**valid_context(), field: "😀" * maximum})
        assert_all_python_validators_reject({**valid_context(), field: "😀" * (maximum + 1)})


def test_every_nullable_key_is_required_and_unknown_keys_are_rejected() -> None:
    payload = valid_context()
    payload.pop("tracestate")
    assert_all_python_validators_reject(payload)
    assert_all_python_validators_reject({**valid_context(), "unexpected": True})


def test_runtime_context_is_immutable_and_json_round_trips() -> None:
    context = parse_operation_context(valid_context())
    with pytest.raises(ValidationError):
        context.stage = OperationStage.FETCH  # type: ignore[misc]
    assert parse_operation_context(json.loads(context.model_dump_json())) == context


def test_stage_and_outcome_vocabularies_round_trip() -> None:
    assert [item.value for item in OperationStage] == [
        "submit", "queue_wait", "claim", "fetch", "discover", "metadata", "transcript",
        "extract", "parse", "filter", "deduplicate", "model", "fallback", "persist",
        "index", "graph", "deliver", "backup", "restore", "alert", "cleanup", "flush",
    ]
    assert [item.value for item in OperationOutcome] == [
        "succeeded", "partial", "skipped_policy", "skipped_duplicate", "filtered",
        "retryable_failure", "permanent_failure", "cancelled",
    ]
    for value in [*OperationStage, *OperationOutcome]:
        assert type(value)(json.loads(json.dumps(value))) is value


def test_context_binding_is_nested_and_restores_prior_value() -> None:
    outer = parse_operation_context(valid_context())
    inner_payload = deepcopy(valid_context())
    inner_payload.update(operation_id="2", stage="fetch")
    inner = parse_operation_context(inner_payload)
    assert get_current_operation_context() is None
    with bind_operation_context(outer):
        assert get_current_operation_context() is outer
        with bind_operation_context(inner):
            assert get_current_operation_context() is inner
        assert get_current_operation_context() is outer
    assert get_current_operation_context() is None


def test_w3c_injection_and_extraction_round_trip() -> None:
    context = parse_operation_context(valid_context())
    carrier = inject_w3c_context(context, {"existing": "preserved"})
    assert carrier == {
        "existing": "preserved",
        "traceparent": context.traceparent,
        "tracestate": context.tracestate,
    }
    extracted = extract_w3c_context(carrier)
    assert extracted is not None
    assert extracted.trace_id == context.trace_id
    assert extracted.parent_span_id == context.span_id
    assert extracted.trace_flags == "01"
    assert extracted.tracestate == context.tracestate


@pytest.mark.parametrize(
    "carrier",
    [
        {},
        {"traceparent": f"00-{'0' * 32}-2222222222222222-01"},
        {"traceparent": f"00-{'1' * 32}-{'0' * 16}-01"},
        {"traceparent": "00-" + "1" * 10_000},
        {
            "traceparent": "00-11111111111111111111111111111111-2222222222222222-01",
            "tracestate": "vendor=value,vendor=duplicate",
        },
    ],
)
def test_w3c_extraction_discards_malformed_untrusted_carriers(carrier: dict[str, str]) -> None:
    assert extract_w3c_context(carrier) is None


def test_checked_in_typescript_validator_covers_runtime_parity_rules() -> None:
    source = (ROOT / "openspec/contracts/content-workflows/generated/types.ts").read_text(
        encoding="utf-8"
    )
    for rule in (
        "parseOperationContextEnvelope",
        "SIGNED_BIGINT_MAX",
        "CLAIM_GENERATION_MAX",
        "carrier[1] !== context.trace_id || carrier[2] !== context.span_id",
        "isValidTracestate",
        "BigInt(context.attempt_number) !== BigInt(context.claim_generation) + 1n",
        "Array.from(value).length",
    ):
        assert rule in source
