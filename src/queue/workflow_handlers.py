"""Typed queue handlers for canonical durable operations."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from src.ingestion.registry import SOURCE_REGISTRY, SourceRegistry
from src.models.jobs import (
    JobStatus,
    OperationType,
    ResourceReference,
    ResourceType,
    normalize_operation_payload,
)
from src.models.query import ResolvedContentSet, compute_selection_fingerprint
from src.services.operation_service import OperationService

WorkflowHandler = Callable[[int, dict[str, Any]], Awaitable["WorkflowHandlerOutcome"]]
Sleep = Callable[[float], Awaitable[None]]


class WorkflowHandlerError(RuntimeError):
    """Controlled workflow failure whose diagnostic is safe to persist."""


class WorkflowExecutionError(WorkflowHandlerError):
    """A canonical workflow failed during application execution."""


class WorkflowResourceError(WorkflowHandlerError):
    """A resource-producing workflow did not attach its persisted resource."""


@dataclass(frozen=True)
class WorkflowHandlerOutcome:
    """Transport-neutral outcome used by the registry lifecycle guard."""

    resource_id: str | None = None
    deferred: bool = False
    checkpoint: dict[str, Any] = field(default_factory=dict)
    progress: int = 20
    message: str = "Waiting for child operations"


@dataclass(frozen=True)
class _HandlerBinding:
    handler: WorkflowHandler
    resource_type: ResourceType | None


class WorkflowHandlerRegistry:
    """Exhaustive typed mapping from operation contracts to worker handlers."""

    def __init__(self, *, operation_service: OperationService | Any | None = None) -> None:
        self.operations = operation_service or OperationService()
        self._bindings: dict[OperationType, _HandlerBinding] = {}

    @property
    def operation_types(self) -> frozenset[OperationType]:
        return frozenset(self._bindings)

    def register(
        self,
        operation_type: OperationType,
        handler: WorkflowHandler,
        *,
        resource_type: ResourceType | None = None,
    ) -> None:
        if operation_type in self._bindings:
            raise ValueError(f"Operation type '{operation_type.value}' already has a handler")
        self._bindings[operation_type] = _HandlerBinding(handler, resource_type)

    def validate_complete(self) -> None:
        missing = set(OperationType).difference(self._bindings)
        if missing:
            names = ", ".join(sorted(operation_type.value for operation_type in missing))
            raise ValueError(f"Missing workflow handlers: {names}")

    async def dispatch(
        self,
        operation_type: OperationType,
        operation_id: int,
        payload: dict[str, Any],
    ) -> None:
        try:
            binding = self._bindings[operation_type]
        except KeyError as exc:
            raise ValueError(f"No handler for operation type '{operation_type.value}'") from exc

        if await self.operations.checkpoint_cancellation(operation_id) is not None:
            return

        outcome = await binding.handler(operation_id, payload)
        handle = await self.operations.get(operation_id)
        if outcome.deferred:
            if handle.status is JobStatus.IN_PROGRESS:
                await self.operations.defer(
                    operation_id,
                    checkpoint=outcome.checkpoint,
                    progress=outcome.progress,
                    message=outcome.message,
                )
            elif handle.status is not JobStatus.QUEUED:
                raise WorkflowExecutionError(
                    f"Deferred {operation_type.value} operation {operation_id} "
                    f"is in unexpected state {handle.status.value}"
                )
            return

        if await self.operations.checkpoint_cancellation(operation_id) is not None:
            return
        if binding.resource_type is not None:
            self._validate_resource(operation_type, operation_id, binding, outcome, handle.resource)

    def worker_handler(self, operation_type: OperationType) -> Callable[..., Awaitable[None]]:
        async def handle(operation_id: int, payload: dict[str, Any]) -> None:
            normalized = normalize_operation_payload(operation_type.value, payload)
            if normalized.operation_type is not operation_type:
                raise WorkflowExecutionError(
                    f"Entrypoint '{operation_type.value}' received "
                    f"'{normalized.operation_type.value}' payload"
                )
            await self.dispatch(operation_type, operation_id, normalized.input)

        return handle

    @staticmethod
    def _validate_resource(
        operation_type: OperationType,
        operation_id: int,
        binding: _HandlerBinding,
        outcome: WorkflowHandlerOutcome,
        attached: ResourceReference | None,
    ) -> None:
        expected_id = outcome.resource_id
        if expected_id is None:
            raise WorkflowResourceError(
                f"{operation_type.value} operation {operation_id} did not return a resource ID"
            )
        if attached is None or attached.type != binding.resource_type or attached.id != expected_id:
            actual = "none" if attached is None else f"{attached.type}/{attached.id}"
            raise WorkflowResourceError(
                f"{operation_type.value} operation {operation_id} expected "
                f"{binding.resource_type}/{expected_id}, attached {actual}"
            )


class _CanonicalHandlers:
    def __init__(
        self,
        *,
        operations: OperationService | Any,
        ingestion_service: Any | None,
        source_registry: SourceRegistry | Any,
        workflow_overrides: Mapping[OperationType, Any],
        sleep: Sleep,
    ) -> None:
        self.operations = operations
        self._ingestion_service = ingestion_service
        self.sources = source_registry
        self.workflow_overrides = workflow_overrides
        self.sleep = sleep

    def bind(self, registry: WorkflowHandlerRegistry) -> None:
        registry.register(OperationType.INGESTION_EXECUTE, self.ingestion)
        registry.register(
            OperationType.SUMMARIZATION_RUN,
            self.summarization,
            resource_type="summary_batch",
        )
        registry.register(
            OperationType.THEME_ANALYSIS_CREATE,
            self.theme_analysis,
            resource_type="theme_analysis",
        )
        registry.register(OperationType.DIGEST_CREATE, self.digest, resource_type="digest")
        registry.register(OperationType.PIPELINE_RUN, self.pipeline, resource_type="digest")
        registry.register(
            OperationType.PODCAST_SCRIPT_CREATE,
            self.podcast_script,
            resource_type="podcast_script",
        )
        registry.register(
            OperationType.PODCAST_AUDIO_CREATE,
            self.podcast_audio,
            resource_type="podcast",
        )
        registry.register(
            OperationType.AUDIO_DIGEST_CREATE,
            self.audio_digest,
            resource_type="audio_digest",
        )

    async def ingestion(self, operation_id: int, payload: dict[str, Any]) -> WorkflowHandlerOutcome:
        from pydantic import ValidationError

        from src.contracts.workflow_models import IngestionResult

        command = self.sources.parse_command(payload)
        descriptor = self.sources.get(command.kind)
        policy = descriptor.retry_policy
        response = None
        for attempt in range(1, policy.max_attempts + 1):
            try:
                response = await asyncio.to_thread(self._ingestion().execute, command)
                break
            except Exception as exc:
                status_code = _status_code(exc)
                retryable = status_code in policy.retryable_status_codes
                if not retryable:
                    raise WorkflowExecutionError(
                        _ingestion_diagnostic(descriptor.key, exc, attempt)
                    ) from exc
                if attempt >= policy.max_attempts:
                    raise WorkflowExecutionError(
                        _ingestion_diagnostic(descriptor.key, exc, attempt)
                    ) from exc
                delay = min(
                    policy.base_delay_seconds * (2 ** (attempt - 1)),
                    policy.max_delay_seconds,
                )
                await self.operations.update_progress(
                    operation_id,
                    10,
                    f"Source {descriptor.key} rate limited; retrying attempt {attempt + 1}",
                )
                await self.sleep(delay)

        if response is None:
            raise WorkflowExecutionError(f"Ingestion '{descriptor.key}' produced no response")
        if response.status == "error":
            raise WorkflowExecutionError(
                f"Ingestion '{descriptor.key}' failed: "
                f"{response.model_dump(mode='json').get('errors', [])}"
            )
        details = dict(response.details)
        try:
            result = IngestionResult(
                command_key=details["command_key"],
                resolved_route=details["resolved_route"],
                emitted_sources=details["emitted_sources"],
                items_ingested=response.items_ingested,
                content_ids=details["content_ids"],
                warnings=[warning.message for warning in response.warnings] or None,
                details=details,
            ).model_dump(mode="json")
        except (KeyError, ValidationError) as exc:
            raise WorkflowExecutionError(
                f"Ingestion '{descriptor.key}' returned an invalid canonical result"
            ) from exc
        await self.operations.attach_result(operation_id, result)
        await self.operations.update_progress(operation_id, 100, "Ingestion complete")
        return WorkflowHandlerOutcome()

    async def summarization(
        self, operation_id: int, payload: dict[str, Any]
    ) -> WorkflowHandlerOutcome:
        from src.contracts.workflow_models import SummarizationRequest

        result = await self._workflow(OperationType.SUMMARIZATION_RUN).execute(
            operation_id,
            SummarizationRequest.model_validate(payload),
        )
        deferred = result.get("deferred") is True
        return WorkflowHandlerOutcome(
            resource_id=None if deferred else str(operation_id),
            deferred=deferred,
            checkpoint=result if deferred else {},
            message="Waiting for summary operations",
        )

    async def theme_analysis(
        self, operation_id: int, payload: dict[str, Any]
    ) -> WorkflowHandlerOutcome:
        from src.contracts.workflow_models import ThemeAnalysisRequest

        record = await self._workflow(OperationType.THEME_ANALYSIS_CREATE).execute(
            operation_id,
            ThemeAnalysisRequest.model_validate(payload),
        )
        return WorkflowHandlerOutcome(resource_id=str(record.id))

    async def digest(self, operation_id: int, payload: dict[str, Any]) -> WorkflowHandlerOutcome:
        from src.contracts.workflow_models import DigestCreateRequest

        normalized = dict(payload)
        serialized_selection = normalized.pop("resolved_set", None)
        if "request" in normalized:
            request_payload = normalized.pop("request")
            if normalized:
                raise WorkflowExecutionError("Pipeline digest payload has unexpected fields")
        else:
            request_payload = normalized
        resolved = _resolved_set(serialized_selection)
        record = await self._workflow(OperationType.DIGEST_CREATE).execute(
            operation_id,
            DigestCreateRequest.model_validate(request_payload),
            resolved_set=resolved,
        )
        return WorkflowHandlerOutcome(resource_id=str(record.id))

    async def pipeline(self, operation_id: int, payload: dict[str, Any]) -> WorkflowHandlerOutcome:
        from src.contracts.workflow_models import PipelineRequest

        result = await self._workflow(OperationType.PIPELINE_RUN).execute(
            operation_id,
            PipelineRequest.model_validate(payload),
        )
        deferred = result.get("deferred") is True
        return WorkflowHandlerOutcome(
            resource_id=None if deferred else _required_result_id(result, "digest_id"),
            deferred=deferred,
            checkpoint=result if deferred else {},
            message=f"Waiting for pipeline {result.get('stage', 'child')} operations",
        )

    async def podcast_script(
        self, operation_id: int, payload: dict[str, Any]
    ) -> WorkflowHandlerOutcome:
        from src.contracts.workflow_models import PodcastScriptRequest

        record = await self._workflow(OperationType.PODCAST_SCRIPT_CREATE).execute(
            operation_id,
            PodcastScriptRequest.model_validate(payload),
        )
        return WorkflowHandlerOutcome(resource_id=str(record.id))

    async def podcast_audio(
        self, operation_id: int, payload: dict[str, Any]
    ) -> WorkflowHandlerOutcome:
        from src.contracts.workflow_models import PodcastAudioRequest

        record = await self._workflow(OperationType.PODCAST_AUDIO_CREATE).execute(
            operation_id,
            PodcastAudioRequest.model_validate(payload),
        )
        return WorkflowHandlerOutcome(resource_id=str(record.id))

    async def audio_digest(
        self, operation_id: int, payload: dict[str, Any]
    ) -> WorkflowHandlerOutcome:
        from src.contracts.workflow_models import AudioDigestRequest

        record = await self._workflow(OperationType.AUDIO_DIGEST_CREATE).execute(
            operation_id,
            AudioDigestRequest.model_validate(payload),
        )
        return WorkflowHandlerOutcome(resource_id=str(record.id))

    def _ingestion(self) -> Any:
        if self._ingestion_service is None:
            from src.ingestion.service import IngestionService

            self._ingestion_service = IngestionService(registry=self.sources)
        return self._ingestion_service

    def _workflow(self, operation_type: OperationType) -> Any:
        override = self.workflow_overrides.get(operation_type)
        if override is not None:
            return override
        if operation_type is OperationType.SUMMARIZATION_RUN:
            from src.workflows.summarization import SummarizationWorkflow

            return SummarizationWorkflow(operation_service=self.operations)
        if operation_type is OperationType.THEME_ANALYSIS_CREATE:
            from src.workflows.theme_analysis import ThemeAnalysisWorkflow

            return ThemeAnalysisWorkflow(operation_service=self.operations)
        if operation_type is OperationType.DIGEST_CREATE:
            from src.workflows.digest import DigestWorkflow

            return DigestWorkflow(operation_service=self.operations)
        if operation_type is OperationType.PIPELINE_RUN:
            from src.workflows.pipeline import PipelineWorkflow

            return PipelineWorkflow(operation_service=self.operations)
        if operation_type is OperationType.PODCAST_SCRIPT_CREATE:
            from src.workflows.podcast_script import PodcastScriptWorkflow

            return PodcastScriptWorkflow(operation_service=self.operations)
        if operation_type is OperationType.PODCAST_AUDIO_CREATE:
            from src.workflows.podcast_audio import PodcastAudioWorkflow

            return PodcastAudioWorkflow(operation_service=self.operations)
        if operation_type is OperationType.AUDIO_DIGEST_CREATE:
            from src.workflows.audio_digest import AudioDigestWorkflow

            return AudioDigestWorkflow(operation_service=self.operations)
        raise ValueError(f"No workflow implementation for '{operation_type.value}'")


def build_workflow_handler_registry(
    *,
    operation_service: OperationService | Any | None = None,
    ingestion_service: Any | None = None,
    source_registry: SourceRegistry | Any = SOURCE_REGISTRY,
    workflow_overrides: Mapping[OperationType, Any] | None = None,
    sleep: Sleep = asyncio.sleep,
) -> WorkflowHandlerRegistry:
    """Build and validate the one registry used by every canonical worker."""

    operations = operation_service or OperationService()
    registry = WorkflowHandlerRegistry(operation_service=operations)
    _CanonicalHandlers(
        operations=operations,
        ingestion_service=ingestion_service,
        source_registry=source_registry,
        workflow_overrides=workflow_overrides or {},
        sleep=sleep,
    ).bind(registry)
    registry.validate_complete()
    return registry


def register_canonical_workflow_handlers(register_handler: Callable[[str], Callable]) -> None:
    """Validate and bridge typed handlers into the legacy worker callable map."""

    registry = build_workflow_handler_registry()
    for operation_type in OperationType:
        register_handler(operation_type.value)(registry.worker_handler(operation_type))


def _status_code(exc: Exception) -> int | None:
    direct = getattr(exc, "status_code", None)
    if isinstance(direct, int):
        return direct
    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    return response_status if isinstance(response_status, int) else None


def _ingestion_diagnostic(source: str, exc: Exception, attempts: int) -> str:
    status_code = _status_code(exc)
    status = f"HTTP {status_code}" if status_code is not None else type(exc).__name__
    suffix = "attempt" if attempts == 1 else "attempts"
    return f"Ingestion '{source}' failed after {attempts} {suffix} ({status}): {exc}"


def _required_result_id(result: Mapping[str, Any], key: str) -> str:
    value = result.get(key)
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise WorkflowResourceError(f"Workflow result requires '{key}'")
    return str(value)


def _resolved_set(serialized: Any | None) -> ResolvedContentSet | None:
    if serialized is None:
        return None
    resolved = ResolvedContentSet.model_validate(serialized)
    content_ids = list(resolved.content_ids)
    summary_ids = list(resolved.summary_ids)
    expected = compute_selection_fingerprint(resolved.policy, content_ids, summary_ids)
    if (
        resolved.fingerprint != expected
        or len(set(content_ids)) != len(content_ids)
        or len(set(summary_ids)) != len(summary_ids)
    ):
        raise WorkflowExecutionError("Serialized resolved_set failed provenance validation")
    return resolved
