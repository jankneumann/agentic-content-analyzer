"""Shared MCP transport selection, native result, and error boundaries."""

from __future__ import annotations

import os
import sys
from collections.abc import Awaitable, Callable
from enum import StrEnum
from functools import wraps
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import BaseModel, ValidationError

from src.clients.workflow_api_client import ProblemError, WorkflowApiClient
from src.contracts.workflow_models import Problem
from src.services.operation_service import OperationConflictError, OperationNotFoundError

if TYPE_CHECKING:
    from mcp.shared.exceptions import McpError


class TransportMode(StrEnum):
    HTTP = "http"
    IN_PROCESS = "in_process"


def strict_http_mode() -> bool:
    return os.environ.get("ACA_MCP_STRICT_HTTP", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def transport_mode() -> TransportMode:
    """Resolve one global mode and never silently mix transports."""
    base_url = os.environ.get("ACA_API_BASE_URL", "").strip()
    admin_key = os.environ.get("ACA_ADMIN_KEY", "").strip()
    if base_url and admin_key:
        return TransportMode.HTTP
    if strict_http_mode():
        raise configuration_error("Strict HTTP mode requires ACA_API_BASE_URL and ACA_ADMIN_KEY")
    if base_url or admin_key:
        missing = "ACA_ADMIN_KEY" if base_url else "ACA_API_BASE_URL"
        print(
            f"aca-mcp: partial HTTP config; {missing} is not set. Using in-process mode.",
            file=sys.stderr,
        )
    return TransportMode.IN_PROCESS


def create_workflow_client() -> WorkflowApiClient:
    """Create the transport-neutral client shared with the CLI."""
    base_url = os.environ.get("ACA_API_BASE_URL", "").strip()
    admin_key = os.environ.get("ACA_ADMIN_KEY", "").strip()
    if not base_url or not admin_key:
        raise configuration_error("HTTP mode is not fully configured")
    return WorkflowApiClient(base_url=base_url, admin_key=admin_key)


def native(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, list):
        return [native(item) for item in value]
    if isinstance(value, tuple):
        return [native(item) for item in value]
    if isinstance(value, dict):
        return {key: native(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "__dict__"):
        return {key: native(item) for key, item in vars(value).items() if not key.startswith("_")}
    return str(value)


def native_dict(value: Any) -> dict[str, Any]:
    result = native(value)
    if not isinstance(result, dict):
        raise TypeError("Expected an object result")
    return result


def configuration_error(message: str) -> McpError:
    return protocol_error(
        "mcp_http_configuration_error",
        message,
        title="MCP HTTP configuration error",
        status=500,
    )


def protocol_error(
    code: str,
    message: str,
    *,
    title: str = "Tool execution failed",
    status: int = 500,
    errors: list[dict[str, Any]] | None = None,
) -> McpError:
    problem = Problem(
        type=f"https://aca.example/problems/{code}",
        title=title,
        status=status,
        detail=message,
        code=code,
        errors=errors,
    )
    return problem_error(problem)


def problem_error(problem: Problem) -> McpError:
    from mcp.shared.exceptions import McpError
    from mcp.types import ErrorData

    problem_data = problem.model_dump(mode="json", exclude_none=True)
    return McpError(
        ErrorData(
            code=-32000,
            message=problem.detail,
            data={
                "code": problem.code or "http_problem",
                "problem": problem_data,
            },
        )
    )


def tool_boundary[**P, T](
    function: Callable[P, Awaitable[T]],
) -> Callable[P, Awaitable[T]]:
    """Translate application and HTTP failures into MCP protocol errors."""

    @wraps(function)
    async def guarded(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return await function(*args, **kwargs)
        except ProblemError as exc:
            raise problem_error(exc.problem) from exc
        except ValidationError as exc:
            raise protocol_error(
                "validation_error",
                "Invalid tool input",
                title="Validation failed",
                status=422,
                errors=[dict(error) for error in exc.errors()],
            ) from exc
        except OperationNotFoundError as exc:
            raise protocol_error(
                "operation_not_found", str(exc), title="Operation not found", status=404
            ) from exc
        except OperationConflictError as exc:
            raise protocol_error(
                "operation_conflict", str(exc), title="Operation conflict", status=409
            ) from exc
        except TimeoutError as exc:
            raise protocol_error(
                "operation_timeout", str(exc), title="Operation timed out", status=504
            ) from exc
        except ValueError as exc:
            raise protocol_error(
                "validation_error", str(exc), title="Validation failed", status=422
            ) from exc
        except httpx.HTTPError as exc:
            raise protocol_error(
                "upstream_http_error", str(exc), title="Upstream HTTP error", status=502
            ) from exc
        except RuntimeError as exc:
            raise protocol_error("tool_execution_error", str(exc)) from exc

    return guarded


def request_json(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> Any:
    """Use the shared workflow client's authenticated HTTP transport."""
    client = create_workflow_client()
    try:
        return client.request_json(method, path, params=params, json=json)
    finally:
        client.close()


def validate_strict_http_config_or_exit() -> None:
    """Fail before serving tools when strict mode has incomplete config."""
    if not strict_http_mode():
        return
    try:
        transport_mode()
    except McpError as exc:
        print(f"aca-mcp: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
