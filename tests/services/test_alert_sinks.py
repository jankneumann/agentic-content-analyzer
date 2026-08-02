"""Security and response-policy tests for workflow alert sinks."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

import httpcore
import httpx
import pytest

from src.contracts.workflow_alert_models import WorkflowAlertEnvelopeV1
from src.services.alert_sinks import NoopAlertSink, WebhookAlertSink, _PolicyNetworkBackend


def _envelope() -> WorkflowAlertEnvelopeV1:
    return WorkflowAlertEnvelopeV1(
        event_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        event_key="operation:42:claim:0:status:failed",
        occurred_at=datetime(2026, 8, 1, 12, tzinfo=UTC),
        severity="error",
        outcome="failed",
        source_kind="operation",
        workflow_type="ingestion.execute",
        operation_id="42",
        attempt=1,
        diagnostic_url="https://ops.example.com/api/v1/operations/42",
        resource_refs=[],
        source_keys=[],
        counts={"items_failed": 1},
        codes=["operation_failed"],
    )


async def _public_resolver(host: str, port: int) -> tuple[str, ...]:
    assert host == "alerts.example.com"
    assert port == 443
    return ("93.184.216.34",)


@pytest.mark.asyncio
async def test_connection_backend_pins_the_validated_address_not_the_hostname() -> None:
    connected: list[tuple[str, int]] = []
    stream = object()

    class Delegate:
        async def connect_tcp(self, host: str, port: int, **kwargs):
            connected.append((host, port))
            return stream

    backend = _PolicyNetworkBackend(
        resolver=_public_resolver,
        allowed_hosts=("alerts.example.com",),
        allow_private_addresses=False,
        delegate=Delegate(),
    )

    assert await backend.connect_tcp("alerts.example.com", 443) is stream
    assert connected == [("93.184.216.34", 443)]


@pytest.mark.asyncio
async def test_connection_backend_revalidates_dns_at_the_actual_connect_boundary() -> None:
    called = False

    async def rebound(host: str, port: int) -> tuple[str, ...]:
        return ("169.254.169.254",)

    class Delegate:
        async def connect_tcp(self, host: str, port: int, **kwargs):
            nonlocal called
            called = True
            return object()

    backend = _PolicyNetworkBackend(
        resolver=rebound,
        allowed_hosts=("alerts.example.com",),
        allow_private_addresses=False,
        delegate=Delegate(),
    )

    with pytest.raises(httpcore.ConnectError, match="address_not_allowed"):
        await backend.connect_tcp("alerts.example.com", 443)
    assert not called


@pytest.mark.asyncio
async def test_noop_sink_never_makes_a_network_request() -> None:
    result = await NoopAlertSink().deliver(_envelope(), idempotency_key="delivery-key")
    assert result.disposition == "success"
    assert result.error_code is None


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [200, 201, 204, 299])
async def test_webhook_treats_every_2xx_as_success_and_signs_canonical_body(
    status_code: int,
) -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status_code, content=b"ok")

    secret = "a" * 32
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        sink = WebhookAlertSink(
            endpoint="https://alerts.example.com/hook",
            allowed_hosts=("alerts.example.com",),
            secret=secret,
            timeout_seconds=10,
            max_retry_after_seconds=60,
            client=client,
            resolver=_public_resolver,
        )
        result = await sink.deliver(_envelope(), idempotency_key="stable-delivery-key")

    assert result.disposition == "success"
    assert len(requests) == 1
    request = requests[0]
    assert request.headers["Idempotency-Key"] == "stable-delivery-key"
    expected = hmac.new(secret.encode(), request.content, hashlib.sha256).hexdigest()
    assert request.headers["X-Workflow-Alert-Signature"] == f"sha256={expected}"
    assert json.loads(request.content)["event_key"] == "operation:42:claim:0:status:failed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "disposition", "error_code"),
    [
        (408, "retry", "http_408"),
        (429, "retry", "http_429"),
        (500, "retry", "http_5xx"),
        (503, "retry", "http_5xx"),
        (400, "permanent", "http_4xx"),
        (401, "permanent", "http_4xx"),
        (302, "permanent", "redirect_rejected"),
    ],
)
async def test_webhook_uses_closed_response_classes(
    status_code: int,
    disposition: str,
    error_code: str,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, headers={"location": "https://evil.invalid"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await WebhookAlertSink(
            endpoint="https://alerts.example.com/hook",
            allowed_hosts=("alerts.example.com",),
            secret=None,
            timeout_seconds=10,
            max_retry_after_seconds=60,
            client=client,
            resolver=_public_resolver,
        ).deliver(_envelope(), idempotency_key="stable-delivery-key")

    assert result.disposition == disposition
    assert result.error_code == error_code


@pytest.mark.asyncio
async def test_retry_after_supports_delta_and_date_and_is_bounded() -> None:
    now = datetime(2026, 8, 1, 12, tzinfo=UTC)
    headers = iter(
        [
            "9999",
            "Sat, 01 Aug 2026 12:00:42 GMT",
            "not-a-date",
        ]
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": next(headers)})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        sink = WebhookAlertSink(
            endpoint="https://alerts.example.com/hook",
            allowed_hosts=("alerts.example.com",),
            secret=None,
            timeout_seconds=10,
            max_retry_after_seconds=60,
            client=client,
            resolver=_public_resolver,
            clock=lambda: now,
        )
        delta = await sink.deliver(_envelope(), idempotency_key="stable-delivery-key")
        date = await sink.deliver(_envelope(), idempotency_key="stable-delivery-key")
        invalid = await sink.deliver(_envelope(), idempotency_key="stable-delivery-key")

    assert delta.retry_after_seconds == 60
    assert date.retry_after_seconds == 42
    assert invalid.retry_after_seconds is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception", "code"),
    [
        (httpx.ConnectTimeout("secret endpoint timed out"), "timeout"),
        (httpx.ReadTimeout("secret body timed out"), "timeout"),
        (httpx.ConnectError("token=top-secret"), "connection_error"),
    ],
)
async def test_transport_failures_are_retryable_and_logs_are_redacted(
    exception: httpx.TransportError,
    code: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise exception

    caplog.set_level(logging.WARNING)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await WebhookAlertSink(
            endpoint="https://alerts.example.com/hook",
            allowed_hosts=("alerts.example.com",),
            secret=None,
            timeout_seconds=10,
            max_retry_after_seconds=60,
            client=client,
            resolver=_public_resolver,
        ).deliver(_envelope(), idempotency_key="stable-delivery-key")

    assert result.disposition == "retry"
    assert result.error_code == code
    assert "top-secret" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("endpoint", "allowed_hosts", "addresses", "allow_private", "error_code"),
    [
        (
            "http://alerts.example.com/hook",
            ("alerts.example.com",),
            ("93.184.216.34",),
            False,
            "unsafe_endpoint",
        ),
        (
            "https://user:pass@alerts.example.com/hook",
            ("alerts.example.com",),
            ("93.184.216.34",),
            False,
            "unsafe_endpoint",
        ),
        (
            "https://alerts.example.com/hook?secret=x",
            ("alerts.example.com",),
            ("93.184.216.34",),
            False,
            "unsafe_endpoint",
        ),
        (
            "https://alerts.example.com/hook",
            ("other.example.com",),
            ("93.184.216.34",),
            False,
            "host_not_allowed",
        ),
        (
            "https://alerts.example.com/hook",
            ("alerts.example.com",),
            ("127.0.0.1",),
            False,
            "address_not_allowed",
        ),
        (
            "https://alerts.example.com/hook",
            ("alerts.example.com",),
            ("169.254.169.254",),
            False,
            "address_not_allowed",
        ),
        (
            "https://alerts.example.com/hook",
            ("alerts.example.com",),
            ("10.0.0.5",),
            False,
            "address_not_allowed",
        ),
    ],
)
async def test_endpoint_host_and_every_resolved_address_fail_closed(
    endpoint: str,
    allowed_hosts: tuple[str, ...],
    addresses: tuple[str, ...],
    allow_private: bool,
    error_code: str,
) -> None:
    called = False

    async def resolver(host: str, port: int) -> tuple[str, ...]:
        return addresses

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(204)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await WebhookAlertSink(
            endpoint=endpoint,
            allowed_hosts=allowed_hosts,
            secret=None,
            timeout_seconds=10,
            max_retry_after_seconds=60,
            client=client,
            resolver=resolver,
            allow_private_addresses=allow_private,
        ).deliver(_envelope(), idempotency_key="stable-delivery-key")

    assert result.disposition == "permanent"
    assert result.error_code == error_code
    assert not called


@pytest.mark.asyncio
async def test_development_mode_may_explicitly_allow_loopback() -> None:
    async def resolver(host: str, port: int) -> tuple[str, ...]:
        return ("127.0.0.1",)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await WebhookAlertSink(
            endpoint="http://127.0.0.1:9080/hook",
            allowed_hosts=("127.0.0.1",),
            secret=None,
            timeout_seconds=10,
            max_retry_after_seconds=60,
            client=client,
            resolver=resolver,
            allow_private_addresses=True,
        ).deliver(_envelope(), idempotency_key="stable-delivery-key")

    assert result.disposition == "success"


@pytest.mark.asyncio
async def test_response_body_is_bounded_without_logging_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sentinel = "DO-NOT-LOG-THIS-RESPONSE"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=(sentinel * 100).encode())

    caplog.set_level(logging.WARNING)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await WebhookAlertSink(
            endpoint="https://alerts.example.com/hook",
            allowed_hosts=("alerts.example.com",),
            secret=None,
            timeout_seconds=10,
            max_retry_after_seconds=60,
            max_response_bytes=64,
            client=client,
            resolver=_public_resolver,
        ).deliver(_envelope(), idempotency_key="stable-delivery-key")

    assert result.disposition == "retry"
    assert result.error_code == "response_too_large"
    assert sentinel not in caplog.text
