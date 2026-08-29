"""Shared correlation lifecycle for non-HTTP operational entrypoints.

The module deliberately accepts only an entrypoint name and bounded stage.  It
never captures function arguments, command lines, environment values, or return
payloads.  This keeps CLI, MCP, scheduler, agent, maintenance, backup, and
operator-script roots useful without turning telemetry into a credential sink.
"""

from __future__ import annotations

import asyncio
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
_GENESIS = b"aca-bootstrap-audit-v1"
_ASYNCIO_TO_THREAD = asyncio.to_thread
_ACTIVE_PROCESS_SCOPE: ContextVar[OperationalScope | None] = ContextVar(
    "operational_process_scope", default=None
)


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
                (
                    context.stage.value
                    if isinstance(context.stage, OperationStage)
                    else context.stage
                ),
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

    try:
        async with _queue_connection() as connection:
            return await lifecycle.shutdown(connection, flush=flush)
    except Exception:
        return await lifecycle.shutdown(None, flush=flush)


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
                flush_succeeded = await scope.aclose(outcome="succeeded")
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
            flush_succeeded = scope.close(outcome="succeeded")
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

    def append(
        self,
        *,
        entrypoint: str,
        outcome: _Outcome,
        diagnostic_code: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        records = self.verify(required=False)
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
        records = self.verify(required=True)
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


def validate_frozen_entrypoint_inventory(
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
