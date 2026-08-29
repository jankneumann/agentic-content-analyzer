"""Closed, safe sink adapters for external workflow alerts."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import math
import socket
import ssl
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from ipaddress import ip_address
from typing import Literal, Protocol
from urllib.parse import urlparse

import httpcore
import httpx
from httpcore._backends.auto import AutoBackend
from httpcore._backends.base import SOCKET_OPTION, AsyncNetworkBackend, AsyncNetworkStream

from src.clients.operational_observability import operational_entrypoint
from src.contracts.workflow_alert_models import WorkflowAlertEnvelopeV1
from src.utils.logging import get_logger

logger = get_logger(__name__)

SinkDisposition = Literal["success", "retry", "permanent"]
AddressResolver = Callable[[str, int], Awaitable[Sequence[str]]]
Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class SinkDeliveryResult:
    """Closed transport result; response content and exceptions never cross the boundary."""

    disposition: SinkDisposition
    error_code: str | None = None
    retry_after_seconds: int | None = None


class AlertSink(Protocol):
    async def deliver(
        self,
        envelope: WorkflowAlertEnvelopeV1,
        *,
        idempotency_key: str,
    ) -> SinkDeliveryResult: ...


class NoopAlertSink:
    """Default-off sink that performs no external work."""

    @operational_entrypoint("alert.noop_delivery", stage="alert", service_name="aca-alert")
    async def deliver(
        self,
        envelope: WorkflowAlertEnvelopeV1,
        *,
        idempotency_key: str,
    ) -> SinkDeliveryResult:
        del envelope, idempotency_key
        return SinkDeliveryResult(disposition="success")


async def _resolve_addresses(host: str, port: int) -> tuple[str, ...]:
    loop = asyncio.get_running_loop()
    records = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return tuple(sorted({record[4][0] for record in records}))


def _validate_addresses(addresses: Sequence[str], *, allow_private_addresses: bool) -> str | None:
    if not addresses:
        return "dns_resolution_failed"
    for value in addresses:
        try:
            address = ip_address(value)
        except ValueError:
            return "dns_resolution_failed"
        if not allow_private_addresses and not address.is_global:
            return "address_not_allowed"
        if allow_private_addresses and (address.is_unspecified or address.is_multicast):
            return "address_not_allowed"
    return None


class _PolicyNetworkBackend(AsyncNetworkBackend):
    """Resolve, validate, then connect to the exact approved address.

    TLS still receives the original hostname from httpcore, preserving normal
    certificate validation while removing the DNS-rebinding gap between an
    application preflight lookup and the socket connection.
    """

    def __init__(
        self,
        *,
        resolver: AddressResolver,
        allowed_hosts: Sequence[str],
        allow_private_addresses: bool,
        delegate: AsyncNetworkBackend | None = None,
    ) -> None:
        self._resolver = resolver
        self._allowed_hosts = frozenset(host.lower().rstrip(".") for host in allowed_hosts)
        self._allow_private_addresses = allow_private_addresses
        self._delegate = delegate or AutoBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,  # noqa: ASYNC109 - required httpcore interface
        local_address: str | None = None,
        socket_options: Iterable[SOCKET_OPTION] | None = None,
    ) -> AsyncNetworkStream:
        normalized_host = host.lower().rstrip(".")
        if normalized_host not in self._allowed_hosts:
            raise httpcore.ConnectError("host_not_allowed")
        try:
            addresses = await self._resolver(normalized_host, port)
        except Exception as exc:
            raise httpcore.ConnectError("dns_resolution_failed") from exc
        error_code = _validate_addresses(
            addresses,
            allow_private_addresses=self._allow_private_addresses,
        )
        if error_code is not None:
            raise httpcore.ConnectError(error_code)
        return await self._delegate.connect_tcp(
            addresses[0],
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,  # noqa: ASYNC109 - required httpcore interface
        socket_options: Iterable[SOCKET_OPTION] | None = None,
    ) -> AsyncNetworkStream:
        del path, timeout, socket_options
        raise httpcore.ConnectError("unix_socket_not_allowed")

    async def sleep(self, seconds: float) -> None:
        await self._delegate.sleep(seconds)


class _PinnedAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    """HTTPX transport whose socket backend enforces the outbound policy."""

    def __init__(self, network_backend: AsyncNetworkBackend) -> None:
        super().__init__(trust_env=False, retries=0)
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(),
            retries=0,
            network_backend=network_backend,
        )


class WebhookAlertSink:
    """HTTPS webhook adapter with explicit SSRF and response bounds."""

    def __init__(
        self,
        *,
        endpoint: str,
        allowed_hosts: Sequence[str],
        secret: str | None,
        timeout_seconds: int,
        max_retry_after_seconds: int,
        client: httpx.AsyncClient | None = None,
        resolver: AddressResolver | None = None,
        allow_private_addresses: bool = False,
        max_response_bytes: int = 65_536,
        clock: Clock | None = None,
    ) -> None:
        if not 1 <= timeout_seconds <= 30:
            raise ValueError("timeout_seconds is outside the supported range")
        if not 1 <= max_retry_after_seconds <= 86_400:
            raise ValueError("max_retry_after_seconds is outside the supported range")
        if not 0 <= max_response_bytes <= 1_048_576:
            raise ValueError("max_response_bytes is outside the supported range")
        self._endpoint = endpoint
        self._allowed_hosts = frozenset(host.lower().rstrip(".") for host in allowed_hosts)
        self._secret = secret.encode() if secret is not None else None
        self._timeout_seconds = timeout_seconds
        self._max_retry_after_seconds = max_retry_after_seconds
        self._client = client
        self._resolver = resolver or _resolve_addresses
        self._allow_private_addresses = allow_private_addresses
        self._max_response_bytes = max_response_bytes
        self._clock = clock or (lambda: datetime.now(UTC))

    @operational_entrypoint("alert.webhook_delivery", stage="alert", service_name="aca-alert")
    async def deliver(
        self,
        envelope: WorkflowAlertEnvelopeV1,
        *,
        idempotency_key: str,
    ) -> SinkDeliveryResult:
        endpoint_error = await self._validate_destination()
        if endpoint_error is not None:
            logger.warning("workflow alert webhook rejected", extra={"error_code": endpoint_error})
            return SinkDeliveryResult(disposition="permanent", error_code=endpoint_error)
        if (
            not idempotency_key
            or len(idempotency_key) > 160
            or any(ord(character) < 33 or ord(character) > 126 for character in idempotency_key)
        ):
            return SinkDeliveryResult(disposition="permanent", error_code="invalid_delivery_key")

        body = json.dumps(
            envelope.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
            "User-Agent": "aca-workflow-alerts/1",
        }
        if self._secret is not None:
            signature = hmac.new(self._secret, body, hashlib.sha256).hexdigest()
            headers["X-Workflow-Alert-Signature"] = f"sha256={signature}"

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout_seconds),
            follow_redirects=False,
            trust_env=False,
            transport=_PinnedAsyncHTTPTransport(
                _PolicyNetworkBackend(
                    resolver=self._resolver,
                    allowed_hosts=self._allowed_hosts,
                    allow_private_addresses=self._allow_private_addresses,
                )
            ),
        )
        try:
            request = client.build_request("POST", self._endpoint, content=body, headers=headers)
            response = await client.send(request, stream=True, follow_redirects=False)
            try:
                oversized = await self._response_is_oversized(response)
                if oversized:
                    return SinkDeliveryResult(disposition="retry", error_code="response_too_large")
                return self._classify_response(response)
            finally:
                await response.aclose()
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout):
            logger.warning("workflow alert webhook retry", extra={"error_code": "timeout"})
            return SinkDeliveryResult(disposition="retry", error_code="timeout")
        except httpx.ConnectError:
            logger.warning(
                "workflow alert webhook retry",
                extra={"error_code": "connection_error"},
            )
            return SinkDeliveryResult(disposition="retry", error_code="connection_error")
        except httpx.TransportError:
            logger.warning("workflow alert webhook retry", extra={"error_code": "transport_error"})
            return SinkDeliveryResult(disposition="retry", error_code="transport_error")
        finally:
            if owns_client:
                await client.aclose()

    async def _validate_destination(self) -> str | None:
        try:
            parsed = urlparse(self._endpoint)
            port = parsed.port
        except ValueError:
            return "unsafe_endpoint"
        allowed_schemes = {"http", "https"} if self._allow_private_addresses else {"https"}
        if (
            parsed.scheme not in allowed_schemes
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            return "unsafe_endpoint"
        host = parsed.hostname.lower().rstrip(".")
        if host not in self._allowed_hosts:
            return "host_not_allowed"
        try:
            addresses = await self._resolver(
                host, port or (443 if parsed.scheme == "https" else 80)
            )
        except Exception:
            return "dns_resolution_failed"
        return _validate_addresses(
            addresses,
            allow_private_addresses=self._allow_private_addresses,
        )

    async def _response_is_oversized(self, response: httpx.Response) -> bool:
        declared = response.headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > self._max_response_bytes:
                    return True
            except ValueError:
                return True
        received = 0
        async for chunk in response.aiter_bytes():
            received += len(chunk)
            if received > self._max_response_bytes:
                return True
        return False

    def _classify_response(self, response: httpx.Response) -> SinkDeliveryResult:
        status = response.status_code
        if 200 <= status < 300:
            return SinkDeliveryResult(disposition="success")
        if status in {408, 429}:
            return SinkDeliveryResult(
                disposition="retry",
                error_code=f"http_{status}",
                retry_after_seconds=self._parse_retry_after(response.headers.get("retry-after")),
            )
        if 500 <= status < 600:
            return SinkDeliveryResult(disposition="retry", error_code="http_5xx")
        if 400 <= status < 500:
            return SinkDeliveryResult(disposition="permanent", error_code="http_4xx")
        if 300 <= status < 400:
            return SinkDeliveryResult(disposition="permanent", error_code="redirect_rejected")
        return SinkDeliveryResult(disposition="permanent", error_code="unexpected_status")

    def _parse_retry_after(self, value: str | None) -> int | None:
        if value is None:
            return None
        try:
            seconds = int(value)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
            except (TypeError, ValueError, OverflowError):
                return None
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=UTC)
            seconds = math.ceil((retry_at - self._clock()).total_seconds())
        return max(0, min(seconds, self._max_retry_after_seconds))
