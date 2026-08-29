"""Shared correlation lifecycle for non-HTTP operational entrypoints.

The module deliberately accepts only an entrypoint name and bounded stage.  It
never captures function arguments, command lines, environment values, or return
payloads.  This keeps CLI, MCP, scheduler, agent, maintenance, backup, and
operator-script roots useful without turning telemetry into a credential sink.
"""

from __future__ import annotations

import ast
import asyncio
import fcntl
import fnmatch
import hashlib
import inspect
import json
import os
import secrets
from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from typing import Any, Literal, ParamSpec, Protocol, TypeVar, cast

import yaml

from src.contracts.operation_context import (
    OperationContext,
    OperationStage,
    bind_operation_context,
    get_current_operation_context,
)
from src.queue.worker import TelemetryLifecycle, create_telemetry_lifecycle
from src.telemetry import get_provider
from src.telemetry.operation_spans import operation_span
from src.telemetry.safety import TelemetryMasker

_P = ParamSpec("_P")
_T = TypeVar("_T")
_Outcome = Literal["succeeded", "partial", "permanent_failure"]
_DEFAULT_BOOTSTRAP_DIRECTORY = Path("/srv/aca/bootstrap-audit")
_SPOOL_NAME = "events.jsonl"
_CHECKPOINT_NAME = "events.imported"
_LOCK_NAME = "events.lock"
_GENESIS = b"aca-bootstrap-audit-v1"
_ASYNCIO_TO_THREAD = asyncio.to_thread
_BOOTSTRAP_IMPORT_ADVISORY_LOCK = 2_104_711_918
_ACTIVE_PROCESS_SCOPE: ContextVar[OperationalScope | None] = ContextVar(
    "operational_process_scope", default=None
)
_OWNED_HELPERS = "exact helper set owned by the instrumented frozen boundary"
_INVENTORY_OWNERSHIP_SNAPSHOTS: dict[str, tuple[str, int, str]] = {
    "src/api/**": (
        "fafc7cbcd8319128cd0879d0bcd80fae10df3a9c4fd6799472ef35a8058890c8",
        67,
        _OWNED_HELPERS,
    ),
    "src/services/operation_service.py": (
        "d706b5bf1eec99f405a29085a6730789493f08e516c4ae8c0fe3b2aa9afb99a5",
        1,
        _OWNED_HELPERS,
    ),
    "src/queue/**": (
        "3afc41311dbf6fa273d14d70da11f0ebc2eda05148088ce7d68be6807d7948f8",
        5,
        _OWNED_HELPERS,
    ),
    "src/cli/main.py": (
        "f9ce59d1cb1354e108bbac25272aef6320153415db6c4b9b5264d710cf1577af",
        1,
        _OWNED_HELPERS,
    ),
    "src/cli/__main__.py": (
        "266545773b96a40791f36540136124340bf8409a6bc71e95f14b96bc490d8bb0",
        1,
        _OWNED_HELPERS,
    ),
    "src/cli/*_commands.py": (
        "bbbe2d724849f4631f9d1ad86311bd946c5a876000f6048cbd44eb67a6c3dc73",
        28,
        _OWNED_HELPERS,
    ),
    "src/mcp_tools/**": (
        "80a109ed330f2b2d5ca90896bdb27811f57cfcf5a7af9446d392fa040faeba4b",
        8,
        _OWNED_HELPERS,
    ),
    "src/agents/**": (
        "fccb37cdc0ad2aa6372ae6235aaab74f810a320cd8cfac3d46139bb258e0c9a5",
        26,
        _OWNED_HELPERS,
    ),
    "src/tasks/**": (
        "2ffacdcec18588eb5b404ae1ded1530adaa1c5701201635c3893ffb1b0a83de4",
        1,
        _OWNED_HELPERS,
    ),
    "src/agents/scheduler/**": (
        "e11f919ed81659aa5d427ebf8a10e8a726c746a9e613c42969aebab2c57e1662",
        2,
        _OWNED_HELPERS,
    ),
    "src/ingestion/**": (
        "91cb7e16089ebef0ef5667fe19c612d8f2509360dd88920101623a052b69a64f",
        30,
        _OWNED_HELPERS,
    ),
    "src/parsers/**": (
        "24b6bd5cdfecba23896a49c2c677ad071bb7f4530aeeb4cf399f7c17e85b4f25",
        9,
        _OWNED_HELPERS,
    ),
    "src/processors/**": (
        "9ff52ed01ec50753d54033d35dff21a157a95c440be8146c07190e032a3cdbaf",
        8,
        _OWNED_HELPERS,
    ),
    "src/pipeline/**": (
        "8589fff69da75a8f6d3cdbc35b82005ed2ffc0873efc6322cebea918d8494468",
        1,
        _OWNED_HELPERS,
    ),
    "src/workflows/**": (
        "4000b93f560bbaf5ca9d779a97872aa4e96a5bb6ff1cc8478b59f9ea7225be6a",
        8,
        _OWNED_HELPERS,
    ),
    "src/delivery/**": (
        "a19b8665cd4ffc2440c46e648ae3bf265b92231ba1cb54655b2c20947f529daf",
        7,
        _OWNED_HELPERS,
    ),
    "src/services/cloud_stt/**": (
        "bc81e78ec2d8d780bb7dbf5081014ba36abcddf889f249ebb829105f24565ffb",
        8,
        _OWNED_HELPERS,
    ),
    "src/storage/**": (
        "21512b6cb6b69b7241c9483da921934d692f1221e304a1d5532234b090a0a3cb",
        11,
        _OWNED_HELPERS,
    ),
    "src/services/backup/**": (
        "d0035234bb8fa840374eef89fb7d6dd8f1df5285db8b3c988005436c054cef73",
        7,
        _OWNED_HELPERS,
    ),
    "src/release_smoke/**": (
        "26dcdb0a9442b827fd9c67196d84c80a4143d260677da18307c95ece18b975da",
        6,
        _OWNED_HELPERS,
    ),
    "src/clients/**": (
        "eac60acba9b4b6b117e59bb309083bc46d03b9fcd4124bf9a486f543771075fc",
        1,
        _OWNED_HELPERS,
    ),
    "src/telemetry/providers/**": (
        "72c668768bc047f1780ca3221dc624591862da9719a6b78ab8e55661820ab816",
        7,
        _OWNED_HELPERS,
    ),
    "src/storage/providers/**": (
        "0b529a66439d2133d36bcbdeba802bbdd20a365c2ad7cdc3c553d45007a840aa",
        8,
        _OWNED_HELPERS,
    ),
}


def _bounded_identifier(value: str, *, maximum: int, field: str) -> str:
    candidate = value.strip()
    if not candidate or len(candidate) > maximum:
        raise ValueError(f"{field} must contain 1-{maximum} characters")
    if any(ord(character) < 32 or ord(character) == 127 for character in candidate):
        raise ValueError(f"{field} contains control characters")
    return candidate


def _plain_lifecycle_value(value: Any, *, fallback: str, maximum: int) -> str:
    """Accept only bounded plain strings from potentially mocked/configured settings."""
    if isinstance(value, str) and 0 < len(value) <= maximum:
        return value
    return fallback


def _context_for(
    *,
    operation_id: int,
    entrypoint: str,
    stage: OperationStage,
    lifecycle: TelemetryLifecycle,
    parent_context: OperationContext | None,
) -> OperationContext:
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    if parent_context is not None:
        trace_id = parent_context.trace_id
        span_id = parent_context.span_id
    operation = str(operation_id)
    return OperationContext(
        schema_version=1,
        operation_id=operation,
        root_operation_id=(
            parent_context.root_operation_id if parent_context is not None else operation
        ),
        parent_operation_id=(parent_context.operation_id if parent_context is not None else None),
        traceparent=f"00-{trace_id}-{span_id}-01",
        tracestate=parent_context.tracestate if parent_context is not None else None,
        trace_id=trace_id,
        span_id=span_id,
        claim_generation="0",
        attempt_number="1",
        entrypoint=entrypoint,
        service_name=lifecycle.service_name,
        service_instance_id=_plain_lifecycle_value(
            lifecycle.service_instance_id,
            fallback="unknown-instance",
            maximum=128,
        ),
        environment=_plain_lifecycle_value(
            getattr(lifecycle.settings, "environment", None),
            fallback="development",
            maximum=32,
        ),
        release_revision=_plain_lifecycle_value(
            lifecycle.release_revision,
            fallback="unknown",
            maximum=64,
        ),
        stage=stage,
        resource_kind=None,
        resource_key=None,
    )


def _context_with_provider_identity(context: OperationContext, span: Any) -> OperationContext:
    try:
        actual = span.get_span_context()
        if not actual.is_valid:
            return context
        trace_id = format(actual.trace_id, "032x")
        span_id = format(actual.span_id, "016x")
        trace_flags = format(int(actual.trace_flags), "02x")
    except (AttributeError, TypeError, ValueError):
        return context
    values = context.model_dump(mode="python")
    values.update(
        trace_id=trace_id,
        span_id=span_id,
        traceparent=f"00-{trace_id}-{span_id}-{trace_flags}",
    )
    return OperationContext.model_validate(values)


class DurableOperationStore(Protocol):
    async def reserve(self, *, entrypoint: str, parent_context: OperationContext | None) -> int: ...

    async def activate(self, context: OperationContext) -> None: ...

    async def finish(
        self,
        context: OperationContext,
        *,
        outcome: _Outcome,
        telemetry_delivery_state: str,
        diagnostic_codes: tuple[str, ...],
    ) -> None: ...


class PostgresDurableOperationStore:
    """Canonical queue/attempt projection for directly executed operational work."""

    async def reserve(self, *, entrypoint: str, parent_context: OperationContext | None) -> int:
        from src.queue.setup import _queue_connection

        parent_id = int(parent_context.operation_id) if parent_context is not None else None
        async with _queue_connection() as connection:
            operation_id = await connection.fetchval(
                """
                INSERT INTO pgqueuer_jobs (
                    entrypoint, payload, status, created_at, execute_after,
                    started_at, heartbeat_at, parent_job_id, claim_generation,
                    claim_protocol_version
                )
                VALUES (
                    $1, '{"schema_version":1,"kind":"operational"}'::jsonb,
                    'in_progress', NOW(), NOW(), NOW(), NOW(), $2, 0, 2
                )
                RETURNING id
                """,
                entrypoint,
                parent_id,
            )
        if operation_id is None:
            raise RuntimeError("unable to reserve durable operational root")
        return int(operation_id)

    async def activate(self, context: OperationContext) -> None:
        from src.queue.setup import _queue_connection

        serialized = json.dumps(context.model_dump(mode="json"), separators=(",", ":"))
        async with _queue_connection() as connection, connection.transaction():
            updated = await connection.execute(
                """
                UPDATE pgqueuer_jobs
                SET root_job_id = $2,
                    submission_context = $3::jsonb,
                    submission_traceparent = $4,
                    submission_tracestate = $5,
                    trace_id = $6,
                    submission_span_id = $7
                WHERE id = $1 AND status = 'in_progress'
                """,
                int(context.operation_id),
                int(context.root_operation_id),
                serialized,
                context.traceparent,
                context.tracestate,
                context.trace_id,
                context.span_id,
            )
            inserted = await connection.fetchval(
                """
                INSERT INTO operation_observation_attempts (
                    operation_id, claim_generation, attempt_number, trace_id,
                    root_span_id, langfuse_observation_id, service_name,
                    service_instance_id, environment, release_revision, started_at
                )
                VALUES ($1, 0, 1, $2, $3, NULL, $4, $5, $6, $7, NOW())
                ON CONFLICT (operation_id, claim_generation) DO NOTHING
                RETURNING operation_id
                """,
                int(context.operation_id),
                context.trace_id,
                context.span_id,
                context.service_name,
                context.service_instance_id,
                context.environment,
                context.release_revision,
            )
        if not updated.endswith(" 1") or inserted is None:
            raise RuntimeError("unable to activate durable operational evidence")

    async def finish(
        self,
        context: OperationContext,
        *,
        outcome: _Outcome,
        telemetry_delivery_state: str,
        diagnostic_codes: tuple[str, ...],
    ) -> None:
        from src.queue.setup import _queue_connection

        status = "failed" if outcome == "permanent_failure" else "completed"
        async with _queue_connection() as connection, connection.transaction():
            attempt = await connection.execute(
                """
                UPDATE operation_observation_attempts
                SET completed_at = NOW(), terminal_stage = $2, outcome = $3,
                    retryable = FALSE, telemetry_delivery_state = $4,
                    diagnostic_codes = $5::operation_diagnostic_code[]
                WHERE operation_id = $1 AND claim_generation = 0
                  AND completed_at IS NULL
                """,
                int(context.operation_id),
                str(context.stage),
                outcome,
                telemetry_delivery_state,
                list(diagnostic_codes),
            )
            job = await connection.execute(
                """
                UPDATE pgqueuer_jobs
                SET status = $2, completed_at = NOW(), heartbeat_at = NOW(),
                    error = CASE WHEN $2 = 'failed' THEN 'operational.entrypoint_failed' ELSE NULL END
                WHERE id = $1 AND status = 'in_progress'
                """,
                int(context.operation_id),
                status,
            )
        if not attempt.endswith(" 1") or not job.endswith(" 1"):
            raise RuntimeError("unable to persist terminal operational evidence")

    async def lookup(self, operation_id: int) -> dict[str, Any] | None:
        from src.queue.setup import _queue_connection

        async with _queue_connection() as connection:
            row = await connection.fetchrow(
                """
                SELECT job.id AS operation_id, job.status, job.entrypoint,
                       job.root_job_id AS root_operation_id, job.parent_job_id,
                       attempt.trace_id, attempt.root_span_id,
                       attempt.outcome, attempt.telemetry_delivery_state,
                       attempt.diagnostic_codes
                FROM pgqueuer_jobs AS job
                JOIN operation_observation_attempts AS attempt
                  ON attempt.operation_id = job.id AND attempt.claim_generation = 0
                WHERE job.id = $1
                """,
                operation_id,
            )
        return dict(row) if row is not None else None


def create_durable_operation_store() -> DurableOperationStore:
    return PostgresDurableOperationStore()


class OperationalFlushError(RuntimeError):
    """A successful command could not durably flush its telemetry evidence."""


async def shutdown_process_telemetry(lifecycle: TelemetryLifecycle) -> bool:
    """Flush with a stable thread bridge, then persist terminal health evidence."""

    async def flush() -> None:
        from src.telemetry import shutdown_telemetry

        await _ASYNCIO_TO_THREAD(shutdown_telemetry)

    from src.queue.setup import _queue_connection

    flush_succeeded = await lifecycle.shutdown(None, flush=flush)
    try:
        async with _queue_connection() as connection:
            await lifecycle.heartbeat(connection)
    except Exception:
        lifecycle.record_export_failure("telemetry.health_write_failed")
    return flush_succeeded


class OperationalScope:
    """One durable operation while process telemetry is owned only at the outer edge."""

    def __init__(
        self,
        entrypoint: str,
        *,
        stage: OperationStage | str,
        service_name: str,
        lifecycle_kind: Literal["long_running", "short_lived"] = "short_lived",
    ) -> None:
        self.entrypoint = _bounded_identifier(entrypoint, maximum=160, field="entrypoint")
        self.stage = OperationStage(stage)
        self.lifecycle: TelemetryLifecycle | None
        self._parent_context = get_current_operation_context()
        self._process_owner = _ACTIVE_PROCESS_SCOPE.get()
        self._borrowed_context = self._parent_context is not None and self._process_owner is None
        self._owns_process = self._parent_context is None and self._process_owner is None
        if self._process_owner is not None:
            self.lifecycle = self._process_owner.lifecycle
        elif self._borrowed_context:
            self.lifecycle = None
        else:
            self.lifecycle = create_telemetry_lifecycle(
                service_name=_bounded_identifier(service_name, maximum=100, field="service_name"),
                lifecycle_kind=lifecycle_kind,
            )
            configured_required = getattr(self.lifecycle.settings, "observability_required", False)
            if not isinstance(configured_required, bool):
                self.lifecycle.required = False
        self._store = create_durable_operation_store()
        self._stack: ExitStack | None = None
        self._process_token: Token[OperationalScope | None] | None = None
        self.context: OperationContext | None = None

    def open(self) -> OperationContext:
        """Reserve durable identity, start the provider span, then allow side effects."""
        if self._stack is not None:
            raise RuntimeError("operational scope is already open")
        if self._borrowed_context:
            assert self._parent_context is not None
            values = self._parent_context.model_dump(mode="python")
            values["stage"] = self.stage
            context = OperationContext.model_validate(values)
            stack = ExitStack()
            stack.enter_context(bind_operation_context(context))
            stack.enter_context(
                operation_span(
                    get_provider(),
                    f"operation.{self.entrypoint}",
                    context=context,
                    stage=self.stage,
                    attributes={"entrypoint": self.entrypoint},
                )
            )
            self.context = context
            self._stack = stack
            return context

        assert self.lifecycle is not None
        if self._owns_process:
            self.lifecycle.initialize(app=None)
        operation_id = _run_awaitable_sync(
            self._store.reserve(
                entrypoint=self.entrypoint,
                parent_context=self._parent_context,
            )
        )
        context = _context_for(
            operation_id=operation_id,
            entrypoint=self.entrypoint,
            stage=self.stage,
            lifecycle=self.lifecycle,
            parent_context=self._parent_context,
        )
        stack = ExitStack()
        try:
            span = stack.enter_context(
                operation_span(
                    get_provider(),
                    f"operation.{self.entrypoint}",
                    context=context,
                    stage=self.stage,
                    attributes={"entrypoint": self.entrypoint},
                )
            )
            context = _context_with_provider_identity(context, span)
            _run_awaitable_sync(self._store.activate(context))
            stack.enter_context(bind_operation_context(context))
        except BaseException:
            stack.close()
            raise
        if self._owns_process:
            self._process_token = _ACTIVE_PROCESS_SCOPE.set(self)
        self.context = context
        self._stack = stack
        return context

    async def aclose(self, *, outcome: _Outcome = "succeeded") -> bool:
        """Close one operation and flush only when this scope owns the process."""
        self._close_stack()
        return await self._finish(outcome=outcome)

    async def _finish(self, *, outcome: _Outcome) -> bool:
        if self._borrowed_context:
            return True
        assert self.context is not None
        assert self.lifecycle is not None
        timeout_seconds = max(
            0.001,
            float(getattr(self.lifecycle.settings, "telemetry_flush_timeout_seconds", 5.0)),
        )
        try:
            try:
                async with asyncio.timeout(timeout_seconds):
                    flush_succeeded = True
                    if self._owns_process:
                        flush_succeeded = await shutdown_process_telemetry(self.lifecycle)
                    try:
                        await self._store.finish(
                            self.context,
                            outcome=outcome,
                            telemetry_delivery_state=(
                                "delivered" if flush_succeeded else "degraded"
                            ),
                            diagnostic_codes=(
                                () if flush_succeeded else ("telemetry.flush_failed",)
                            ),
                        )
                    except (TimeoutError, asyncio.CancelledError):
                        raise
                    except Exception as exc:
                        self._fallback_exit_evidence(
                            outcome=outcome,
                            diagnostic_code="telemetry.database_unavailable",
                        )
                        raise OperationalFlushError(
                            "terminal evidence database unavailable"
                        ) from exc
                    return flush_succeeded
            except TimeoutError as exc:
                self._fallback_exit_evidence(
                    outcome=outcome,
                    diagnostic_code="telemetry.exit_deadline_exceeded",
                )
                raise OperationalFlushError("telemetry exit deadline exceeded") from exc
        finally:
            self._reset_process_scope()

    def _fallback_exit_evidence(self, *, outcome: _Outcome, diagnostic_code: str) -> None:
        assert self.context is not None
        try:
            BootstrapAuditSpool(_bootstrap_directory()).append(
                entrypoint=self.context.entrypoint,
                outcome=outcome,
                diagnostic_code=diagnostic_code,
                metadata={"operation_id": self.context.operation_id},
            )
        except Exception:
            pass

    def _close_stack(self) -> None:
        """Exit context bindings in the context that created their tokens."""
        stack, self._stack = self._stack, None
        if stack is not None:
            stack.close()

    def _reset_process_scope(self) -> None:
        token, self._process_token = self._process_token, None
        if token is not None:
            _ACTIVE_PROCESS_SCOPE.reset(token)

    def close(self, *, outcome: _Outcome = "succeeded") -> bool:
        self._close_stack()
        self._reset_process_scope()
        return _run_awaitable_sync(self._finish(outcome=outcome))


def _run_awaitable_sync[T](awaitable: Awaitable[T]) -> T:
    """Run a bounded async close from a synchronous command boundary."""

    async def resolve() -> T:
        return await awaitable

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(resolve())

    result: list[T] = []
    failure: list[BaseException] = []

    def run() -> None:
        try:
            result.append(asyncio.run(resolve()))
        except BaseException as exc:  # pragma: no cover - defensive thread bridge
            failure.append(exc)

    import threading

    thread = threading.Thread(target=run, name="aca-operational-flush", daemon=False)
    thread.start()
    thread.join()
    if failure:
        raise failure[0]
    return result[0]


def operational_entrypoint(
    entrypoint: str,
    *,
    stage: OperationStage | str,
    service_name: str = "aca-operational",
    result_outcome: Callable[[Any], _Outcome] | None = None,
) -> Callable[[Callable[_P, _T]], Callable[_P, _T]]:
    """Decorate a sync or async non-HTTP entrypoint without capturing arguments."""

    def decorate(function: Callable[_P, _T]) -> Callable[_P, _T]:
        if inspect.iscoroutinefunction(function):

            @wraps(function)
            async def async_guarded(*args: _P.args, **kwargs: _P.kwargs) -> Any:
                scope = OperationalScope(
                    entrypoint,
                    stage=stage,
                    service_name=service_name,
                )
                scope.open()
                try:
                    result = await cast(Callable[_P, Awaitable[Any]], function)(*args, **kwargs)
                except BaseException:
                    try:
                        await scope.aclose(outcome="permanent_failure")
                    except BaseException:
                        pass
                    raise
                outcome = result_outcome(result) if result_outcome is not None else "succeeded"
                flush_succeeded = await scope.aclose(outcome=outcome)
                if not flush_succeeded:
                    raise OperationalFlushError(f"telemetry flush failed for {entrypoint}")
                return result

            cast(Any, async_guarded).__aca_operational_entrypoint__ = (
                entrypoint,
                OperationStage(stage).value,
                service_name,
            )
            return cast(Callable[_P, _T], async_guarded)

        @wraps(function)
        def guarded(*args: _P.args, **kwargs: _P.kwargs) -> Any:
            scope = OperationalScope(
                entrypoint,
                stage=stage,
                service_name=service_name,
            )
            scope.open()
            try:
                result = function(*args, **kwargs)
            except BaseException:
                try:
                    scope.close(outcome="permanent_failure")
                except BaseException:
                    pass
                raise
            outcome = result_outcome(result) if result_outcome is not None else "succeeded"
            flush_succeeded = scope.close(outcome=outcome)
            if not flush_succeeded:
                raise OperationalFlushError(f"telemetry flush failed for {entrypoint}")
            return result

        cast(Any, guarded).__aca_operational_entrypoint__ = (
            entrypoint,
            OperationStage(stage).value,
            service_name,
        )
        return cast(Callable[_P, _T], guarded)

    return decorate


@contextmanager
def operational_stage(
    name: str,
    *,
    stage: OperationStage | str,
    attributes: Mapping[str, Any] | None = None,
) -> Iterator[Any]:
    """Add a safe nested stage when a validated operation root is already bound."""
    current = get_current_operation_context()
    if current is None:
        yield None
        return
    values = current.model_dump(mode="python")
    values["stage"] = OperationStage(stage)
    context = OperationContext.model_validate(values)
    with operation_span(
        get_provider(),
        _bounded_identifier(name, maximum=160, field="span name"),
        context=context,
        stage=context.stage,
        attributes=attributes,
    ) as span:
        yield span


def install_cli_telemetry(context: Any) -> OperationalScope:
    """Cover every Typer command through the one root callback/close boundary."""
    command = str(getattr(context, "invoked_subcommand", None) or "root")
    scope = OperationalScope(
        f"cli.{command}",
        stage=OperationStage.SUBMIT,
        service_name="aca-cli",
    )
    scope.open()
    context.call_on_close(scope.close)
    return scope


class BootstrapAuditCorruptionError(RuntimeError):
    """The pre-PostgreSQL audit chain cannot be trusted."""


@dataclass(frozen=True, slots=True)
class BootstrapReadiness:
    ready: bool
    diagnostic_code: str | None
    record_count: int


class BootstrapAuditSpool:
    """Mode-0600 masked hash-chain used before PostgreSQL is healthy."""

    def __init__(self, directory: str | Path = _DEFAULT_BOOTSTRAP_DIRECTORY) -> None:
        self.directory = Path(directory)
        self.path = self.directory / _SPOOL_NAME
        self.checkpoint_path = self.directory / _CHECKPOINT_NAME
        self.lock_path = self.directory / _LOCK_NAME

    @contextmanager
    def _locked(self, *, exclusive: bool) -> Iterator[None]:
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            os.fchmod(descriptor, 0o600)
            fcntl.flock(descriptor, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def append(
        self,
        *,
        entrypoint: str,
        outcome: _Outcome,
        diagnostic_code: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._locked(exclusive=True):
            return self._append_unlocked(
                entrypoint=entrypoint,
                outcome=outcome,
                diagnostic_code=diagnostic_code,
                metadata=metadata,
            )

    def _append_unlocked(
        self,
        *,
        entrypoint: str,
        outcome: _Outcome,
        diagnostic_code: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        records = self._verify_unlocked(required=False)
        previous_hash = records[-1]["record_hash"] if records else None
        safe_metadata = TelemetryMasker.from_environment().mask(dict(metadata or {}))
        body: dict[str, Any] = {
            "schema_version": 1,
            "occurred_at": datetime.now(UTC).isoformat(),
            "entrypoint": _bounded_identifier(entrypoint, maximum=160, field="entrypoint"),
            "outcome": outcome,
            "diagnostic_code": (
                _bounded_identifier(diagnostic_code, maximum=100, field="diagnostic_code")
                if diagnostic_code is not None
                else None
            ),
            "metadata": safe_metadata,
            "previous_hash": previous_hash,
        }
        body["record_hash"] = _record_hash(body)
        descriptor = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.fchmod(descriptor, 0o600)
            os.write(
                descriptor,
                (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode(),
            )
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return body

    def verify(self, *, required: bool) -> list[dict[str, Any]]:
        with self._locked(exclusive=False):
            return self._verify_unlocked(required=required)

    def _verify_unlocked(self, *, required: bool) -> list[dict[str, Any]]:
        if not self.path.exists():
            if required:
                raise FileNotFoundError(self.path)
            return []
        if self.path.stat().st_mode & 0o077:
            raise BootstrapAuditCorruptionError("bootstrap spool permissions are not 0600")
        records: list[dict[str, Any]] = []
        previous_hash: str | None = None
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
            for line in lines:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("record is not an object")
                claimed_hash = record.get("record_hash")
                if record.get("previous_hash") != previous_hash:
                    raise ValueError("previous hash mismatch")
                if not isinstance(claimed_hash, str) or claimed_hash != _record_hash(record):
                    raise ValueError("record hash mismatch")
                previous_hash = claimed_hash
                records.append(record)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            raise BootstrapAuditCorruptionError("bootstrap spool integrity check failed") from exc
        return records

    def import_records(self, persist: Callable[[dict[str, Any]], Any]) -> int:
        with self._locked(exclusive=True):
            return self._import_records_unlocked(persist)

    def _import_records_unlocked(self, persist: Callable[[dict[str, Any]], Any]) -> int:
        records = self._verify_unlocked(required=True)
        checkpoint = self._read_checkpoint()
        start = 0
        if checkpoint is not None:
            hashes = [str(record["record_hash"]) for record in records]
            if checkpoint not in hashes:
                raise BootstrapAuditCorruptionError(
                    "bootstrap import checkpoint is not in the chain"
                )
            start = hashes.index(checkpoint) + 1
        pending = records[start:]
        for record in pending:
            persist(dict(record))
        if pending:
            self._write_checkpoint(str(pending[-1]["record_hash"]))
        return len(pending)

    def pending_records(self, *, required: bool) -> list[dict[str, Any]]:
        with self._locked(exclusive=False):
            records = self._verify_unlocked(required=required)
            checkpoint = self._read_checkpoint()
            if checkpoint is None:
                return records
            hashes = [str(record["record_hash"]) for record in records]
            if checkpoint not in hashes:
                raise BootstrapAuditCorruptionError(
                    "bootstrap import checkpoint is not in the chain"
                )
            return records[hashes.index(checkpoint) + 1 :]

    def mark_imported(self, record_hash: str) -> None:
        with self._locked(exclusive=True):
            records = self._verify_unlocked(required=True)
            hashes = [str(record["record_hash"]) for record in records]
            if record_hash not in hashes:
                raise BootstrapAuditCorruptionError(
                    "bootstrap import checkpoint is not in the chain"
                )
            current = self._read_checkpoint()
            if current is not None and hashes.index(record_hash) < hashes.index(current):
                return
            self._write_checkpoint(record_hash)

    def readiness(self, *, required: bool) -> BootstrapReadiness:
        try:
            records = self.verify(required=required)
        except FileNotFoundError:
            return BootstrapReadiness(False, "bootstrap.spool_missing", 0)
        except BootstrapAuditCorruptionError:
            return BootstrapReadiness(False, "bootstrap.spool_corrupt", 0)
        return BootstrapReadiness(True, None, len(records))

    def _read_checkpoint(self) -> str | None:
        if not self.checkpoint_path.exists():
            return None
        if self.checkpoint_path.stat().st_mode & 0o077:
            raise BootstrapAuditCorruptionError("bootstrap checkpoint permissions are not 0600")
        value = self.checkpoint_path.read_text(encoding="ascii").strip()
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise BootstrapAuditCorruptionError("bootstrap checkpoint is malformed")
        return value

    def _write_checkpoint(self, record_hash: str) -> None:
        descriptor = os.open(
            self.checkpoint_path,
            os.O_CREAT | os.O_TRUNC | os.O_WRONLY,
            0o600,
        )
        try:
            os.fchmod(descriptor, 0o600)
            os.write(descriptor, (record_hash + "\n").encode("ascii"))
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _record_hash(record: Mapping[str, Any]) -> str:
    body = {key: value for key, value in record.items() if key != "record_hash"}
    previous = body.get("previous_hash")
    seed = bytes.fromhex(previous) if isinstance(previous, str) else _GENESIS
    serialized = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(seed + serialized).hexdigest()


def _bootstrap_directory() -> Path:
    configured = os.environ.get("ACA_BOOTSTRAP_AUDIT_DIR")
    return Path(configured) if configured else _DEFAULT_BOOTSTRAP_DIRECTORY


@dataclass(frozen=True, slots=True)
class BootstrapMaintenanceResult:
    readiness: BootstrapReadiness
    imported_count: int


async def _persist_bootstrap_record(
    connection: Any,
    *,
    record: Mapping[str, Any],
    parent_context: OperationContext | None,
    lifecycle: TelemetryLifecycle,
) -> bool:
    record_hash = str(record["record_hash"])
    existing = await connection.fetchval(
        """
        SELECT id FROM pgqueuer_jobs
        WHERE entrypoint = $1 AND idempotency_key = $2
        ORDER BY id LIMIT 1
        """,
        str(record["entrypoint"]),
        record_hash,
    )
    if existing is not None:
        return False

    trace_id = parent_context.trace_id if parent_context is not None else secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    parent_id = int(parent_context.operation_id) if parent_context is not None else None
    root_id = int(parent_context.root_operation_id) if parent_context is not None else None
    traceparent = f"00-{trace_id}-{span_id}-01"
    payload = json.dumps(
        {
            "schema_version": 1,
            "kind": "bootstrap_audit",
            "record_hash": record_hash,
        },
        separators=(",", ":"),
    )
    operation_id = await connection.fetchval(
        """
        INSERT INTO pgqueuer_jobs (
            entrypoint, payload, status, created_at, execute_after, started_at,
            completed_at, heartbeat_at, parent_job_id, root_job_id,
            claim_generation, claim_protocol_version, idempotency_key,
            submission_traceparent, trace_id, submission_span_id
        )
        VALUES (
            $1, $2::jsonb, 'completed', NOW(), NOW(), NOW(), NOW(), NOW(),
            $3, $4, 0, 2, $5, $6, $7, $8
        )
        RETURNING id
        """,
        str(record["entrypoint"]),
        payload,
        parent_id,
        root_id,
        record_hash,
        traceparent,
        trace_id,
        span_id,
    )
    if operation_id is None:
        raise RuntimeError("unable to persist bootstrap operation")
    canonical_root = root_id or int(operation_id)
    await connection.execute(
        "UPDATE pgqueuer_jobs SET root_job_id = $2 WHERE id = $1",
        int(operation_id),
        canonical_root,
    )
    await connection.execute(
        """
        INSERT INTO operation_observation_attempts (
            operation_id, claim_generation, attempt_number, trace_id,
            root_span_id, service_name, service_instance_id, environment,
            release_revision, started_at, completed_at, terminal_stage,
            outcome, retryable, telemetry_delivery_state, diagnostic_codes
        )
        VALUES (
            $1, 0, 1, $2, $3, $4, $5, $6, $7, NOW(), NOW(), 'persist',
            $8, FALSE, 'delivered', '{}'::operation_diagnostic_code[]
        )
        """,
        int(operation_id),
        trace_id,
        span_id,
        lifecycle.service_name,
        lifecycle.service_instance_id,
        str(lifecycle.settings.environment),
        lifecycle.release_revision,
        str(record["outcome"]),
    )
    return True


async def reconcile_bootstrap_audit(
    settings: Any,
    *,
    maintenance_connection: Any,
) -> BootstrapMaintenanceResult:
    """Import pre-database evidence once and project production readiness."""
    required = str(getattr(settings, "environment", "development")) == "production"
    spool = BootstrapAuditSpool(_bootstrap_directory())
    readiness = spool.readiness(required=required)
    lifecycle = TelemetryLifecycle(
        settings=settings,
        service_name="aca-bootstrap-maintenance",
        lifecycle_kind="short_lived",
        service_instance_id="bootstrap-audit",
    )
    lifecycle.initialized = True
    lifecycle.required = required
    pending: list[dict[str, Any]] = []
    if readiness.ready:
        pending = spool.pending_records(required=required)
        lifecycle.record_export_success()
    else:
        lifecycle.record_export_failure(readiness.diagnostic_code or "bootstrap.spool_unavailable")

    imported = 0
    parent_context = get_current_operation_context()
    try:
        from src.queue.setup import _queue_connection

        async with _queue_connection() as connection, connection.transaction():
            await connection.fetchval(
                "SELECT pg_advisory_xact_lock($1::bigint)",
                _BOOTSTRAP_IMPORT_ADVISORY_LOCK,
            )
            for record in pending:
                imported += int(
                    await _persist_bootstrap_record(
                        connection,
                        record=record,
                        parent_context=parent_context,
                        lifecycle=lifecycle,
                    )
                )
            await lifecycle.heartbeat(connection)
    except Exception:
        lifecycle.record_export_failure("bootstrap.maintenance_write_failed")
        try:
            await lifecycle.heartbeat(maintenance_connection)
        except Exception:
            pass
        return BootstrapMaintenanceResult(readiness, 0)

    if pending:
        spool.mark_imported(str(pending[-1]["record_hash"]))
    return BootstrapMaintenanceResult(readiness, imported)


def bootstrap_entrypoint(entrypoint: str) -> Callable[[Callable[_P, _T]], Callable[_P, _T]]:
    """Record terminal evidence for a command that may run before PostgreSQL."""

    def decorate(function: Callable[_P, _T]) -> Callable[_P, _T]:
        if inspect.iscoroutinefunction(function):

            @wraps(function)
            async def async_guarded(*args: _P.args, **kwargs: _P.kwargs) -> Any:
                try:
                    result = await cast(Callable[_P, Awaitable[Any]], function)(*args, **kwargs)
                except BaseException:
                    BootstrapAuditSpool(_bootstrap_directory()).append(
                        entrypoint=entrypoint,
                        outcome="permanent_failure",
                        diagnostic_code="bootstrap.command_failed",
                    )
                    raise
                BootstrapAuditSpool(_bootstrap_directory()).append(
                    entrypoint=entrypoint,
                    outcome="succeeded",
                )
                return result

            return cast(Callable[_P, _T], async_guarded)

        @wraps(function)
        def guarded(*args: _P.args, **kwargs: _P.kwargs) -> Any:
            try:
                result = function(*args, **kwargs)
            except BaseException:
                BootstrapAuditSpool(_bootstrap_directory()).append(
                    entrypoint=entrypoint,
                    outcome="permanent_failure",
                    diagnostic_code="bootstrap.command_failed",
                )
                raise
            BootstrapAuditSpool(_bootstrap_directory()).append(
                entrypoint=entrypoint,
                outcome="succeeded",
            )
            return result

        return cast(Callable[_P, _T], guarded)

    return decorate


@dataclass(frozen=True, slots=True)
class EntrypointInventoryReport:
    unlisted: tuple[str, ...]
    missing: tuple[str, ...]
    uninstrumented: tuple[str, ...]
    explicit_exclusions_only: bool


def _validate_frozen_entrypoint_inventory_legacy(
    repository: str | Path,
    inventory_path: str | Path,
    *,
    require_declared_paths: bool = True,
) -> EntrypointInventoryReport:
    """Validate exhaustive top-level scripts and explicit, reasoned exclusions."""
    root = Path(repository)
    loaded = yaml.safe_load(Path(inventory_path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("entrypoint inventory must be an object")
    exclusions = loaded.get("explicit_exclusions", [])
    if not isinstance(exclusions, list):
        raise ValueError("explicit_exclusions must be a list")
    excluded_paths: set[str] = set()
    for exclusion in exclusions:
        if not isinstance(exclusion, dict) or not exclusion.get("pattern"):
            raise ValueError("every explicit exclusion requires a pattern")
        if not exclusion.get("reason"):
            raise ValueError("every explicit exclusion requires a reason")
        pattern = str(exclusion["pattern"])
        if pattern.startswith("scripts/"):
            excluded_paths.add(pattern)

    operational = _string_paths(loaded.get("operational_scripts"), "operational_scripts")
    bootstrap_block = loaded.get("bootstrap_operations", {})
    if not isinstance(bootstrap_block, dict):
        raise ValueError("bootstrap_operations must be an object")
    bootstrap = _string_paths(bootstrap_block.get("paths"), "bootstrap_operations.paths")
    declared = set(operational) | set(bootstrap)

    candidates: set[str] = set()
    scripts_directory = root / "scripts"
    if scripts_directory.exists():
        for path in scripts_directory.iterdir():
            relative = path.relative_to(root).as_posix()
            if path.suffix == ".sh" or (
                path.suffix == ".py"
                and "__main__" in path.read_text(encoding="utf-8", errors="ignore")
            ):
                candidates.add(relative)

    unlisted = tuple(sorted(candidates - declared - excluded_paths))
    missing = (
        tuple(sorted(path for path in declared if not (root / path).is_file()))
        if require_declared_paths
        else ()
    )
    uninstrumented: list[str] = []
    if require_declared_paths:
        for declared_path in operational:
            candidate = root / declared_path
            if candidate.is_file() and "operational_entrypoint" not in candidate.read_text(
                encoding="utf-8", errors="ignore"
            ):
                uninstrumented.append(declared_path)
        for declared_path in bootstrap:
            candidate = root / declared_path
            if not candidate.is_file():
                continue
            marker = "bootstrap_audit" if candidate.suffix == ".sh" else "bootstrap_entrypoint"
            if marker not in candidate.read_text(encoding="utf-8", errors="ignore"):
                uninstrumented.append(declared_path)
    return EntrypointInventoryReport(
        unlisted=unlisted,
        missing=missing,
        uninstrumented=tuple(sorted(uninstrumented)),
        explicit_exclusions_only=True,
    )


def _string_paths(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError(f"{field} must be a list")
    if any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{field} contains an invalid path")
    return tuple(cast(Sequence[str], value))


_STRUCTURAL_INSTRUMENTATION_CALLS = frozenset(
    {
        "BootstrapAuditSpool",
        "TelemetryLifecycle",
        "TelemetryMiddleware",
        "bind_operation_context",
        "bootstrap_entrypoint",
        "create_telemetry_lifecycle",
        "install_cli_telemetry",
        "operation_span",
        "operation_stage",
        "operational_entrypoint",
        "operational_stage",
        "observe",
        "setup_telemetry",
        "start_span",
    }
)


def _call_name(node: ast.Call) -> str | None:
    function = node.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return None


def _python_is_structurally_instrumented(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError):
        return False
    return any(
        isinstance(node, ast.Call) and _call_name(node) in _STRUCTURAL_INSTRUMENTATION_CALLS
        for node in ast.walk(tree)
    )


def _shell_is_structurally_instrumented(path: Path) -> bool:
    try:
        executable = "\n".join(
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    except (OSError, UnicodeError):
        return False
    return ("bootstrap_audit" in executable and "trap " in executable and "EXIT" in executable) or (
        "operational_observability" in executable and "python" in executable
    )


def _path_is_structurally_instrumented(path: Path) -> bool:
    if path.suffix == ".py":
        return _python_is_structurally_instrumented(path)
    if path.suffix == ".sh":
        return _shell_is_structurally_instrumented(path)
    return False


def _inventory_groups(loaded: Mapping[str, Any]) -> list[tuple[str, tuple[str, ...]]]:
    groups: list[tuple[str, tuple[str, ...]]] = []
    shared = loaded.get("shared_boundaries", {})
    if not isinstance(shared, dict):
        raise ValueError("shared_boundaries must be an object")
    for name, value in shared.items():
        groups.append((f"shared_boundaries.{name}", _string_paths(value, str(name))))
    for section in (
        "domain_operations",
        "operational_services",
        "operational_scripts",
        "provider_boundaries",
    ):
        groups.append((section, _string_paths(loaded.get(section), section)))
    bootstrap = loaded.get("bootstrap_operations", {})
    if not isinstance(bootstrap, dict):
        raise ValueError("bootstrap_operations must be an object")
    groups.append(
        (
            "bootstrap_operations",
            _string_paths(bootstrap.get("paths"), "bootstrap_operations.paths"),
        )
    )
    return groups


def _pattern_files(root: Path, pattern: str) -> tuple[Path, ...]:
    if pattern.endswith("/**"):
        directory = root / pattern.removesuffix("/**")
        if not directory.is_dir():
            return ()
        return tuple(sorted(path for path in directory.rglob("*") if path.is_file()))
    if any(character in pattern for character in "*?["):
        matches = root.glob(pattern)
        files: set[Path] = set()
        for match in matches:
            if match.is_file():
                files.add(match)
            elif match.is_dir():
                files.update(path for path in match.rglob("*") if path.is_file())
        return tuple(sorted(files))
    candidate = root / pattern
    return (candidate,) if candidate.is_file() else ()


def validate_frozen_entrypoint_inventory(
    repository: str | Path,
    inventory_path: str | Path,
    *,
    require_declared_paths: bool = True,
) -> EntrypointInventoryReport:
    """Parse every frozen boundary and verify executable instrumentation structure."""
    root = Path(repository)
    loaded = yaml.safe_load(Path(inventory_path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("entrypoint inventory must be an object")
    exclusions = loaded.get("explicit_exclusions", [])
    if not isinstance(exclusions, list):
        raise ValueError("explicit_exclusions must be a list")
    excluded: list[str] = []
    for exclusion in exclusions:
        if not isinstance(exclusion, dict) or not exclusion.get("pattern"):
            raise ValueError("every explicit exclusion requires a pattern")
        if not exclusion.get("reason"):
            raise ValueError("every explicit exclusion requires a reason")
        excluded.append(str(exclusion["pattern"]))

    groups = _inventory_groups(loaded)
    declared_patterns = [pattern for _section, patterns in groups for pattern in patterns]
    missing: list[str] = []
    uninstrumented: list[str] = []
    declared_files: set[str] = set()
    if require_declared_paths:
        for _section, patterns in groups:
            for pattern in patterns:
                pattern_files = _pattern_files(root, pattern)
                if not pattern_files:
                    missing.append(pattern)
                declared_files.update(path.relative_to(root).as_posix() for path in pattern_files)
                source_files = tuple(
                    path for path in pattern_files if path.suffix in {".py", ".sh"}
                )
                uncovered = sorted(
                    path.relative_to(root).as_posix()
                    for path in source_files
                    if not _path_is_structurally_instrumented(path)
                )
                if not uncovered:
                    continue
                snapshot = _INVENTORY_OWNERSHIP_SNAPSHOTS.get(pattern)
                digest = hashlib.sha256("\n".join(uncovered).encode()).hexdigest()
                if snapshot is not None:
                    expected_digest, expected_count, reason = snapshot
                    if (
                        reason.strip()
                        and len(uncovered) == expected_count
                        and digest == expected_digest
                    ):
                        continue
                uninstrumented.extend(uncovered)

    candidates: set[str] = set()
    scripts = root / "scripts"
    if scripts.exists():
        for path in scripts.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if path.suffix == ".sh" or (
                path.suffix == ".py"
                and "__main__" in path.read_text(encoding="utf-8", errors="ignore")
            ):
                candidates.add(relative)

    def covered(path: str) -> bool:
        return path in declared_files or any(
            fnmatch.fnmatch(path, pattern) for pattern in declared_patterns
        )

    def explicitly_excluded(path: str) -> bool:
        return any(path == pattern or fnmatch.fnmatch(path, pattern) for pattern in excluded)

    unlisted = tuple(
        sorted(path for path in candidates if not covered(path) and not explicitly_excluded(path))
    )
    return EntrypointInventoryReport(
        unlisted=unlisted,
        missing=tuple(sorted(set(missing))),
        uninstrumented=tuple(sorted(set(uninstrumented))),
        explicit_exclusions_only=True,
    )


def _command_line(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="aca-bootstrap-audit")
    parser.add_argument("entrypoint")
    parser.add_argument("outcome", choices=("succeeded", "partial", "permanent_failure"))
    parser.add_argument("--diagnostic-code")
    args = parser.parse_args(argv)
    BootstrapAuditSpool(_bootstrap_directory()).append(
        entrypoint=args.entrypoint,
        outcome=args.outcome,
        diagnostic_code=args.diagnostic_code,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_command_line())


__all__ = [
    "BootstrapAuditCorruptionError",
    "BootstrapAuditSpool",
    "BootstrapReadiness",
    "EntrypointInventoryReport",
    "OperationalScope",
    "bootstrap_entrypoint",
    "install_cli_telemetry",
    "operational_entrypoint",
    "operational_stage",
    "validate_frozen_entrypoint_inventory",
]
