"""Capability discovery and durable operation observation/control tools."""

from __future__ import annotations

from typing import Any

from src.config.sources import load_sources_config
from src.contracts.workflow_models import OperationHandle, OperationPage
from src.mcp import runtime
from src.services.capability_service import CapabilityService
from src.services.operation_service import OperationService


def _in_process_capabilities(*, limit: int, cursor: str | None) -> dict[str, Any]:
    return runtime.native_dict(CapabilityService().get_capabilities(limit=limit, cursor=cursor))


@runtime.tool_boundary
async def get_capabilities(limit: int = 50, cursor: str | None = None) -> dict[str, Any]:
    """Discover source fields, operations, resources, and transport support."""
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        client = runtime.create_workflow_client()
        try:
            return runtime.native_dict(client.get_capabilities(limit=limit, cursor=cursor))
        finally:
            client.close()
    return _in_process_capabilities(limit=limit, cursor=cursor)


@runtime.tool_boundary
async def list_configured_sources(limit: int = 50, cursor: str | None = None) -> dict[str, Any]:
    """List safe configured-source projections without secrets or raw locators."""
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        client = runtime.create_workflow_client()
        try:
            return runtime.native_dict(client.list_configured_sources(limit=limit, cursor=cursor))
        finally:
            client.close()
    return runtime.native_dict(
        CapabilityService().list_configured_sources(
            load_sources_config(), limit=limit, cursor=cursor
        )
    )


@runtime.tool_boundary
async def list_operations(limit: int = 50, cursor: str | None = None) -> dict[str, Any]:
    """List durable operations using an opaque cursor."""
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        client = runtime.create_workflow_client()
        try:
            return runtime.native_dict(client.list_operations(limit=limit, cursor=cursor))
        finally:
            client.close()
    page = await OperationService().list(limit=limit, cursor=cursor)
    return runtime.native_dict(OperationPage.model_validate(page.model_dump(mode="json")))


@runtime.tool_boundary
async def get_operation_status(operation_id: str, wait_seconds: int = 0) -> dict[str, Any]:
    """Get the latest operation snapshot, optionally with a bounded wait."""
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        client = runtime.create_workflow_client()
        try:
            return runtime.native_dict(
                client.get_operation(operation_id, wait_seconds=wait_seconds)
            )
        finally:
            client.close()
    service = OperationService()
    handle = (
        await service.wait(operation_id, timeout_seconds=wait_seconds)
        if wait_seconds
        else await service.get(operation_id)
    )
    return runtime.native_dict(OperationHandle.model_validate(handle.model_dump(mode="json")))


@runtime.tool_boundary
async def wait_for_operation(
    operation_id: str,
    timeout_seconds: float = 300,
    poll_interval: float = 0.5,
) -> dict[str, Any]:
    """Wait for terminal state while preserving a bounded agent call."""
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        client = runtime.create_workflow_client()
        try:
            return runtime.native_dict(
                client.wait_operation(
                    operation_id,
                    timeout_seconds=timeout_seconds,
                    poll_interval=poll_interval,
                )
            )
        finally:
            client.close()
    handle = await OperationService(poll_interval=poll_interval).wait(
        operation_id,
        timeout_seconds=timeout_seconds,
    )
    return runtime.native_dict(OperationHandle.model_validate(handle.model_dump(mode="json")))


@runtime.tool_boundary
async def retry_operation(operation_id: str) -> dict[str, Any]:
    """Retry a failed or cancelled durable operation."""
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        client = runtime.create_workflow_client()
        try:
            return runtime.native_dict(client.retry_operation(operation_id))
        finally:
            client.close()
    handle = await OperationService().retry(operation_id)
    return runtime.native_dict(OperationHandle.model_validate(handle.model_dump(mode="json")))


@runtime.tool_boundary
async def cancel_operation(operation_id: str) -> dict[str, Any]:
    """Request safe cancellation for a cancellable durable operation."""
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        client = runtime.create_workflow_client()
        try:
            return runtime.native_dict(client.cancel_operation(operation_id))
        finally:
            client.close()
    handle = await OperationService().cancel(operation_id)
    return runtime.native_dict(OperationHandle.model_validate(handle.model_dump(mode="json")))


TOOLS = (
    get_capabilities,
    list_configured_sources,
    list_operations,
    get_operation_status,
    wait_for_operation,
    retry_operation,
    cancel_operation,
)
