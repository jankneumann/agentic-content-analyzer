"""Canonical durable ingestion-to-digest pipeline workflow."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any, cast

from src.config import settings as app_settings
from src.config.sources import SourcesConfig
from src.contracts.workflow_models import (
    ContentQuery as WorkflowContentQuery,
    DigestCreateRequest,
    IngestionOutcome,
    IngestionResultV2,
    PipelineIngestionSummary,
    PipelineRequest,
    PipelineSourceIngestionSummary,
    SummarizationRequest,
)
from src.ingestion.registry import SOURCE_REGISTRY, SourceRegistry
from src.models.digest import Digest
from src.models.jobs import OperationHandle, OperationStatus, OperationType
from src.models.query import ContentQuery, ResolvedContentSet, compute_selection_fingerprint
from src.services.content_set_resolver import ContentSetResolver
from src.services.operation_service import OperationService
from src.storage.database import get_db
from src.workflows.digest import validate_digest_provenance


def aggregate_pipeline_ingestion_outcome(
    pipeline_status: str,
    child_outcomes: list[IngestionOutcome],
) -> IngestionOutcome:
    """Apply the committed D2 pipeline/child outcome precedence table."""

    if pipeline_status == "cancelled":
        return "cancelled"
    if pipeline_status == "failed":
        return "failed"
    if pipeline_status != "completed":
        raise ValueError(
            f"Pipeline ingestion summary requires a terminal status, got {pipeline_status}"
        )
    if any(outcome in {"partial", "failed", "cancelled"} for outcome in child_outcomes):
        return "partial"
    if "unknown" in child_outcomes:
        return "unknown"
    if not child_outcomes or all(outcome == "zero_items" for outcome in child_outcomes):
        return "zero_items"
    return "success"


def build_pipeline_ingestion_summary(
    commands: list[dict[str, Any]],
    handles: list[OperationHandle | Any],
    *,
    pipeline_status: str,
) -> PipelineIngestionSummary:
    """Project bounded typed child results without replacing checkpoint authority."""

    source_outcomes: list[IngestionOutcome] = []
    sources: list[PipelineSourceIngestionSummary] = []
    for command, handle in zip(commands, handles, strict=True):
        operation_status = (
            handle.status.value
            if isinstance(handle.status, OperationStatus)
            else str(handle.status)
        )
        if operation_status not in {"completed", "failed", "cancelled"}:
            raise ValueError(
                f"Pipeline ingestion summary requires terminal children, got {operation_status}"
            )

        typed_result: IngestionResultV2 | None = None
        raw_result = handle.result
        if isinstance(raw_result, dict) and raw_result.get("schema_version") == 2:
            try:
                typed_result = IngestionResultV2.model_validate(raw_result)
            except ValueError:
                typed_result = None

        if operation_status == "cancelled":
            outcome: IngestionOutcome = "cancelled"
        elif operation_status == "failed":
            outcome = "failed"
        elif typed_result is None:
            outcome = "unknown"
        else:
            outcome = typed_result.outcome
        source_outcomes.append(outcome)

        if len(sources) < 100:
            sources.append(
                PipelineSourceIngestionSummary(
                    operation_id=str(handle.operation_id),
                    command_key=(
                        typed_result.command_key
                        if typed_result is not None
                        else str(command.get("kind", "unknown"))
                    ),
                    operation_status=operation_status,
                    outcome=outcome,
                    items_ingested=(
                        typed_result.items_ingested if typed_result is not None else None
                    ),
                    items_skipped=(
                        typed_result.items_skipped if typed_result is not None else None
                    ),
                    items_failed=typed_result.items_failed if typed_result is not None else None,
                )
            )

    return PipelineIngestionSummary(
        outcome=aggregate_pipeline_ingestion_outcome(pipeline_status, source_outcomes),
        sources=sources,
        sources_omitted=max(0, len(source_outcomes) - len(sources)),
    )


class PipelineWorkflow:
    """Advance one restart-safe parent-child pipeline by one durable checkpoint."""

    def __init__(
        self,
        *,
        operation_service: OperationService | Any | None = None,
        registry: SourceRegistry = SOURCE_REGISTRY,
        source_config_loader: Callable[[], SourcesConfig] | None = None,
        resolver: ContentSetResolver | Any | None = None,
        digest_loader: Callable[[int], Digest | Any | None] | None = None,
    ) -> None:
        self.operations = operation_service or OperationService()
        self.registry = registry
        self.source_config_loader = source_config_loader or app_settings.get_sources_config
        self.resolver = resolver or ContentSetResolver()
        self.digest_loader = digest_loader or self._load_digest

    async def execute(
        self,
        operation_id: str | int,
        request: PipelineRequest,
    ) -> dict[str, Any]:
        handle = await self.operations.get(operation_id)
        checkpoint = dict(handle.result or {})
        if checkpoint.get("stage") == "completed":
            return await self._repair_completion(operation_id, handle, checkpoint)
        if handle.resource is not None:
            raise RuntimeError("Pipeline completion projection is inconsistent")

        if not checkpoint:
            checkpoint = await self._start_ingestion(operation_id, request)
        checkpoint = await self._ensure_ingestion_children(operation_id, checkpoint)

        source_ids = [int(value) for value in checkpoint["source_operation_ids"]]
        source_children = [await self.operations.get(value) for value in source_ids]
        if self._has_active(source_children):
            return await self._defer(
                operation_id,
                checkpoint,
                progress=10,
                message="Waiting for source operations",
            )

        checkpoint["source_results"] = self._source_results(
            checkpoint["source_commands"], source_children
        )
        ingestion_summary = build_pipeline_ingestion_summary(
            checkpoint["source_commands"],
            source_children,
            pipeline_status="completed",
        )
        checkpoint["schema_version"] = 2
        checkpoint["ingestion_summary"] = ingestion_summary.model_dump(mode="json")
        failed_sources = [
            result for result in checkpoint["source_results"] if result["status"] != "completed"
        ]
        if len(failed_sources) == len(checkpoint["source_results"]):
            checkpoint["ingestion_summary"]["outcome"] = "failed"
            checkpoint.update(
                {
                    "deferred": False,
                    "stage": "failed",
                    "retry_child_operation_ids": [
                        int(result["operation_id"]) for result in failed_sources
                    ],
                }
            )
            await self.operations.attach_result(operation_id, checkpoint)
            raise RuntimeError(
                "Pipeline source ingestion failed because all source ingestion operations failed"
            )
        if ingestion_summary.outcome == "partial" and not request.continue_on_source_error:
            checkpoint["ingestion_summary"]["outcome"] = "failed"
            checkpoint.update(
                {
                    "deferred": False,
                    "stage": "failed",
                    "retry_child_operation_ids": [
                        int(result["operation_id"]) for result in failed_sources
                    ],
                }
            )
            await self.operations.attach_result(operation_id, checkpoint)
            raise RuntimeError("Pipeline source ingestion failed and continuation is disabled")
        checkpoint.pop("retry_child_operation_ids", None)

        summary_id = checkpoint.get("summary_operation_id")
        if summary_id is None and not checkpoint.get("summary_result"):
            content_ids = self._source_content_ids(checkpoint)
            if content_ids:
                summary = await self.operations.submit_child(
                    operation_id,
                    OperationType.SUMMARIZATION_RUN,
                    self._summarization_request(checkpoint).model_dump(mode="json"),
                    idempotency_key=f"pipeline:{operation_id}:summarization",
                )
                checkpoint["summary_operation_id"] = int(summary.operation_id)
                checkpoint.update({"deferred": True, "stage": "summarization"})
                return await self._defer(
                    operation_id,
                    checkpoint,
                    progress=45,
                    message="Waiting for summarization",
                )
            checkpoint["summary_result"] = {
                "content_ids": [],
                "completed_ids": [],
                "failed_ids": [],
            }
            await self.operations.attach_result(operation_id, checkpoint)

        if summary_id is not None:
            summary = await self.operations.get(summary_id)
            if not summary.is_terminal:
                checkpoint.update({"deferred": True, "stage": "summarization"})
                return await self._defer(
                    operation_id,
                    checkpoint,
                    progress=45,
                    message="Waiting for summarization",
                )
            if summary.status is not OperationStatus.COMPLETED:
                checkpoint["ingestion_summary"]["outcome"] = "failed"
                checkpoint.update(
                    {
                        "deferred": False,
                        "stage": "failed",
                        "summary_result": self._operation_result(summary),
                        "retry_child_operation_ids": [int(summary.operation_id)],
                    }
                )
                await self.operations.attach_result(operation_id, checkpoint)
                raise RuntimeError("Pipeline summarization failed")
            checkpoint["summary_result"] = summary.result
            checkpoint.pop("retry_child_operation_ids", None)

        resolved_data = checkpoint.get("resolved_set")
        if resolved_data is None:
            resolved = self.resolver.resolve(self._digest_query(request, checkpoint))
            resolved = self._restrict_resolved(
                resolved,
                self._summarized_content_ids(checkpoint),
            )
            checkpoint["resolved_set"] = resolved.model_dump(mode="json")
            await self.operations.attach_result(operation_id, checkpoint)
        else:
            resolved = ResolvedContentSet.model_validate(resolved_data)

        digest_id = checkpoint.get("digest_operation_id")
        if digest_id is None:
            digest_request = DigestCreateRequest(
                digest_type=request.period,
                period_start=request.period_start,
                period_end=request.period_end,
                query=WorkflowContentQuery.model_validate(
                    {
                        key: value
                        for key, value in resolved.policy.model_dump(mode="json").items()
                        if key in WorkflowContentQuery.model_fields
                    }
                ),
            )
            digest = await self.operations.submit_child(
                operation_id,
                OperationType.DIGEST_CREATE,
                {
                    "request": digest_request.model_dump(mode="json"),
                    "resolved_set": resolved.model_dump(mode="json"),
                },
                idempotency_key=f"pipeline:{operation_id}:digest:{resolved.fingerprint}",
            )
            checkpoint["digest_operation_id"] = int(digest.operation_id)
            checkpoint.update({"deferred": True, "stage": "digest"})
            return await self._defer(
                operation_id,
                checkpoint,
                progress=80,
                message="Waiting for digest creation",
            )

        digest_operation = await self.operations.get(digest_id)
        if not digest_operation.is_terminal:
            checkpoint.update({"deferred": True, "stage": "digest"})
            return await self._defer(
                operation_id,
                checkpoint,
                progress=80,
                message="Waiting for digest creation",
            )
        if digest_operation.status is not OperationStatus.COMPLETED:
            checkpoint["ingestion_summary"]["outcome"] = "failed"
            checkpoint.update(
                {
                    "deferred": False,
                    "stage": "failed",
                    "digest_result": self._operation_result(digest_operation),
                    "retry_child_operation_ids": [int(digest_operation.operation_id)],
                }
            )
            await self.operations.attach_result(operation_id, checkpoint)
            raise RuntimeError("Pipeline digest creation failed")
        if digest_operation.resource is None or digest_operation.resource.type != "digest":
            raise RuntimeError("Completed digest operation has no digest resource")

        persisted_digest_id = int(digest_operation.resource.id)
        persisted = self.digest_loader(persisted_digest_id)
        self._validate_digest(persisted, resolved)
        self._validate_digest_operation(persisted, digest_operation.operation_id)
        checkpoint.update(
            {
                "deferred": False,
                "stage": "completed",
                "digest_id": persisted_digest_id,
                "digest_result": digest_operation.result,
            }
        )
        checkpoint.pop("retry_child_operation_ids", None)
        await self.operations.attach_completion(
            operation_id,
            result=checkpoint,
            resource=digest_operation.resource,
            message="Pipeline complete",
        )
        return checkpoint

    async def _start_ingestion(
        self,
        operation_id: str | int,
        request: PipelineRequest,
    ) -> dict[str, Any]:
        commands = self.registry.plan_scheduled_commands(
            self.source_config_loader(),
            sources=request.sources,
            period_start=request.period_start,
            period_end=request.period_end,
        )
        if not commands:
            raise ValueError("Pipeline has no enabled scheduled sources")

        checkpoint = {
            "deferred": True,
            "stage": "ingestion",
            "source_commands": [command.model_dump(mode="json") for command in commands],
            "source_operation_ids": [],
            "source_results": [],
        }
        await self.operations.attach_result(operation_id, checkpoint)
        return checkpoint

    async def _ensure_ingestion_children(
        self,
        operation_id: str | int,
        checkpoint: dict[str, Any],
    ) -> dict[str, Any]:
        commands = checkpoint["source_commands"]
        child_ids = list(checkpoint.get("source_operation_ids", []))
        for index in range(len(child_ids), len(commands)):
            serialized = commands[index]
            command = self.registry.parse_command(serialized)
            command_kind = str(command.model_dump()["kind"])
            child = await self.operations.submit_child(
                operation_id,
                OperationType.INGESTION_EXECUTE,
                serialized,
                idempotency_key=(
                    f"pipeline:{operation_id}:source:{command_kind}:{index}:"
                    f"{self._fingerprint(serialized)}"
                ),
            )
            child_ids.append(int(child.operation_id))
            checkpoint["source_operation_ids"] = child_ids
            await self.operations.attach_result(operation_id, checkpoint)
        return checkpoint

    def _summarization_request(
        self,
        checkpoint: dict[str, Any],
    ) -> SummarizationRequest:
        return SummarizationRequest(content_ids=self._source_content_ids(checkpoint))

    def _digest_query(
        self,
        request: PipelineRequest,
        checkpoint: dict[str, Any],
    ) -> ContentQuery:
        return self._content_query(request, checkpoint)

    def _content_query(
        self,
        request: PipelineRequest,
        checkpoint: dict[str, Any],
    ) -> ContentQuery:
        return ContentQuery(
            start_date=request.period_start,
            end_date=request.period_end,
            require_summary=True,
        )

    @staticmethod
    def _source_content_ids(checkpoint: dict[str, Any]) -> list[int]:
        content_ids: set[int] = set()
        for source_result in checkpoint.get("source_results", []):
            result = source_result.get("result") or {}
            receipt_content_ids = result.get("content_ids")
            if receipt_content_ids is None:
                receipt_content_ids = (result.get("details") or {}).get("content_ids")
            for content_id in receipt_content_ids or []:
                if isinstance(content_id, int) and content_id > 0:
                    content_ids.add(content_id)
        return sorted(content_ids)

    @classmethod
    def _summarized_content_ids(cls, checkpoint: dict[str, Any]) -> list[int]:
        summary_result = checkpoint.get("summary_result") or {}
        completed = summary_result.get("completed_ids")
        if completed is None:
            return cls._source_content_ids(checkpoint)
        return sorted(
            {
                content_id
                for content_id in completed
                if isinstance(content_id, int) and content_id > 0
            }
        )

    @staticmethod
    def _restrict_resolved(
        resolved: ResolvedContentSet,
        content_ids: list[int],
    ) -> ResolvedContentSet:
        requested = set(content_ids)
        items = tuple(item for item in resolved.items if item.content_id in requested)
        exclusions = tuple(
            exclusion for exclusion in resolved.exclusions if exclusion.content_id in requested
        )
        return ResolvedContentSet(
            policy=resolved.policy,
            items=items,
            exclusions=exclusions,
            fingerprint=compute_selection_fingerprint(
                resolved.policy,
                [item.content_id for item in items],
                [item.summary_id for item in items],
            ),
        )

    async def _defer(
        self,
        operation_id: str | int,
        checkpoint: dict[str, Any],
        *,
        progress: int,
        message: str,
    ) -> dict[str, Any]:
        checkpoint["deferred"] = True
        await self.operations.defer(
            operation_id,
            checkpoint=checkpoint,
            progress=progress,
            message=message,
        )
        return checkpoint

    @staticmethod
    def _has_active(handles: list[OperationHandle | Any]) -> bool:
        return any(
            handle.status in {OperationStatus.QUEUED, OperationStatus.IN_PROGRESS}
            for handle in handles
        )

    async def _repair_completion(
        self,
        operation_id: str | int,
        handle: OperationHandle | Any,
        checkpoint: dict[str, Any],
    ) -> dict[str, Any]:
        digest_id = checkpoint.get("digest_id")
        digest_operation_id = checkpoint.get("digest_operation_id")
        resolved_data = checkpoint.get("resolved_set")
        if digest_id is None or digest_operation_id is None or resolved_data is None:
            raise RuntimeError("Pipeline completion projection is inconsistent")

        digest_operation = await self.operations.get(digest_operation_id)
        child_resource = digest_operation.resource
        if (
            digest_operation.status is not OperationStatus.COMPLETED
            or child_resource is None
            or child_resource.type != "digest"
            or child_resource.id != str(digest_id)
        ):
            raise RuntimeError("Pipeline completion projection is inconsistent")

        resource = handle.resource or child_resource
        if resource.type != "digest" or resource.id != child_resource.id:
            raise RuntimeError("Pipeline completion projection is inconsistent")

        resolved = ResolvedContentSet.model_validate(resolved_data)
        persisted_digest = self.digest_loader(int(digest_id))
        self._validate_digest(persisted_digest, resolved)
        self._validate_digest_operation(persisted_digest, digest_operation_id)
        await self.operations.attach_completion(
            operation_id,
            result=checkpoint,
            resource=resource,
            message="Pipeline complete",
        )
        return checkpoint

    @classmethod
    def _source_results(
        cls,
        commands: list[dict[str, Any]],
        handles: list[OperationHandle | Any],
    ) -> list[dict[str, Any]]:
        return [
            {
                "operation_id": handle.operation_id,
                "source": command["kind"],
                "status": handle.status.value,
                "result": handle.result,
                "problem": cls._problem(handle.problem),
            }
            for command, handle in zip(commands, handles, strict=True)
        ]

    @classmethod
    def _operation_result(cls, handle: OperationHandle | Any) -> dict[str, Any]:
        return {
            "operation_id": handle.operation_id,
            "status": handle.status.value,
            "result": handle.result,
            "problem": cls._problem(handle.problem),
        }

    @staticmethod
    def _problem(problem: Any | None) -> dict[str, Any] | None:
        if problem is None:
            return None
        return cast(dict[str, Any], problem.model_dump(mode="json"))

    @staticmethod
    def _validate_digest(digest: Digest | Any | None, resolved: ResolvedContentSet) -> None:
        if digest is None:
            raise RuntimeError("Completed digest resource does not exist")
        validate_digest_provenance(digest, resolved)

    @staticmethod
    def _validate_digest_operation(
        digest: Digest | Any | None,
        operation_id: str | int,
    ) -> None:
        persisted_operation_id = getattr(digest, "operation_id", operation_id)
        if str(persisted_operation_id) != str(operation_id):
            raise RuntimeError("Pipeline completion projection is inconsistent")

    @staticmethod
    def _fingerprint(value: dict[str, Any]) -> str:
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _load_digest(digest_id: int) -> Digest | None:
        with get_db() as db:
            digest = db.get(Digest, digest_id)
            if digest is not None:
                db.expunge(digest)
            return digest
