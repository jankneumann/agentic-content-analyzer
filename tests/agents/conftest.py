"""Isolation fixture for legacy agent unit tests with no PostgreSQL service."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from src.contracts.operation_context import OperationContext, bind_operation_context


@pytest.fixture(autouse=True)
def bind_agent_unit_operation() -> Iterator[None]:
    context = OperationContext(
        schema_version=1,
        operation_id="9001",
        root_operation_id="9001",
        parent_operation_id=None,
        traceparent="00-11111111111111111111111111111111-2222222222222222-01",
        tracestate=None,
        trace_id="11111111111111111111111111111111",
        span_id="2222222222222222",
        claim_generation="0",
        attempt_number="1",
        entrypoint="test.agent",
        service_name="aca-test",
        service_instance_id="test-1",
        environment="test",
        release_revision="test",
        stage="submit",
        resource_kind=None,
        resource_key=None,
    )
    with bind_operation_context(context):
        yield
