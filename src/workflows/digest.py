"""Durable digest creation workflow."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.orm import Session

from src.contracts.workflow_models import (
    ContentQuery as WorkflowContentQuery,
    DigestCreateRequest,
    ThemeAnalysisRequest as WorkflowThemeRequest,
)
from src.models.digest import Digest, DigestRequest, DigestStatus, DigestType
from src.models.jobs import ResourceReference
from src.models.query import ContentQuery, ResolvedContentSet, SelectionPolicy
from src.processors.digest_creator import DigestCreator
from src.services.content_set_resolver import ContentSetResolver
from src.services.operation_service import OperationService
from src.storage.database import get_db
from src.workflows.resource import recover_owned_resource
from src.workflows.theme_analysis import ThemeAnalysisWorkflow


class DigestWorkflow:
    """Persist exactly one digest from one resolved content snapshot."""

    def __init__(
        self,
        *,
        operation_service: OperationService | Any | None = None,
        resolver: ContentSetResolver | Any | None = None,
        theme_workflow: ThemeAnalysisWorkflow | Any | None = None,
        creator: DigestCreator | Any | None = None,
        session_factory: Callable[[], AbstractContextManager[Session]] = get_db,
    ) -> None:
        self.operations = operation_service or OperationService()
        self.resolver = resolver or ContentSetResolver()
        self.theme_workflow = theme_workflow or ThemeAnalysisWorkflow()
        self.creator = creator or DigestCreator()
        self.session_factory = session_factory

    async def execute(self, operation_id: str | int, request: DigestCreateRequest) -> Digest:
        existing = await self._existing(operation_id)
        if existing is not None and existing.status not in {
            DigestStatus.GENERATING,
            DigestStatus.FAILED,
        }:
            await self._attach_result(operation_id, existing)
            return existing
        if existing is None:
            query_data = request.query.model_dump(mode="python") if request.query else {}
            if query_data.get("start_date") is None:
                query_data["start_date"] = request.period_start
            if query_data.get("end_date") is None:
                query_data["end_date"] = request.period_end
            query = ContentQuery.model_validate(query_data)
            resolved = self.resolver.resolve(query)
        else:
            resolved = self.resolver.resolve(
                SelectionPolicy.model_validate(existing.selection_policy)
            )
            if (
                resolved.fingerprint != existing.selection_fingerprint
                or list(resolved.content_ids) != existing.source_content_ids
                or list(resolved.summary_ids) != existing.source_summary_ids
            ):
                raise ValueError("Persisted digest selection changed before retry")
            query = ContentQuery.model_validate(resolved.policy.model_dump(mode="python"))

        if existing is None:
            with self.session_factory() as db:
                record = Digest(
                    operation_id=int(operation_id),
                    digest_type=DigestType(request.digest_type),
                    period_start=request.period_start,
                    period_end=request.period_end,
                    title=f"Generating {request.digest_type} digest...",
                    executive_overview="",
                    strategic_insights=[],
                    technical_developments=[],
                    emerging_trends=[],
                    actionable_recommendations={},
                    sources=[],
                    newsletter_count=len(resolved.content_ids),
                    status=DigestStatus.GENERATING,
                    agent_framework="pending",
                    model_used="pending",
                    source_content_ids=list(resolved.content_ids),
                    source_summary_ids=list(resolved.summary_ids),
                    selection_fingerprint=resolved.fingerprint,
                    selection_policy=resolved.policy.model_dump(mode="json"),
                )
                db.add(record)
                db.commit()
                db.refresh(record)
                record_id = cast(int, record.id)
            await self.operations.attach_resource(
                operation_id,
                ResourceReference(
                    type="digest", id=str(record_id), url=f"/api/v1/digests/{record_id}"
                ),
            )
        else:
            record_id = cast(int, existing.id)
            with self.session_factory() as db:
                loaded = db.get(Digest, record_id)
                if loaded is None:
                    raise RuntimeError("Attached digest resource does not exist")
                record = loaded
                record.status = DigestStatus.GENERATING
                record.review_notes = None
                db.commit()

        try:
            await self.operations.update_progress(operation_id, 20, "Analyzing digest themes")
            workflow_query = WorkflowContentQuery.model_validate(query.model_dump(mode="json"))
            theme_result = await self.theme_workflow.analyze_persisted(
                WorkflowThemeRequest(query=workflow_query, max_themes=15),
                resolved_set=resolved,
            )
            await self.operations.update_progress(operation_id, 50, "Generating digest")
            data = await self.creator.create_digest(
                DigestRequest(
                    digest_type=DigestType(request.digest_type),
                    period_start=request.period_start,
                    period_end=request.period_end,
                    include_historical_context=request.include_historical_context,
                ),
                resolved,
                themes=theme_result.themes,
            )
            self._validate_provenance(data, resolved)
            with self.session_factory() as db:
                loaded = db.get(Digest, record_id)
                if loaded is None:
                    raise RuntimeError(f"Reserved digest {record_id} disappeared")
                record = loaded
                self._apply(record, data)
                db.commit()
                db.refresh(record)
        except Exception as exc:
            with self.session_factory() as db:
                failed = db.get(Digest, record_id)
                if failed is not None:
                    failed.status = DigestStatus.FAILED
                    failed.review_notes = str(exc)
                    db.commit()
            raise
        await self._attach_result(operation_id, record)
        return cast(Digest, record)

    @staticmethod
    def _validate_provenance(data: Any, resolved: ResolvedContentSet) -> None:
        if (
            list(data.source_content_ids or []) != list(resolved.content_ids)
            or list(data.source_summary_ids) != list(resolved.summary_ids)
            or data.selection_fingerprint != resolved.fingerprint
            or SelectionPolicy.model_validate(data.selection_policy) != resolved.policy
        ):
            raise ValueError("Digest provenance does not match resolved selection")

    @staticmethod
    def _apply(record: Digest, data: Any) -> None:
        record.title = data.title
        record.executive_overview = data.executive_overview
        record.strategic_insights = [
            item.model_dump(mode="json") for item in data.strategic_insights
        ]
        record.technical_developments = [
            item.model_dump(mode="json") for item in data.technical_developments
        ]
        record.emerging_trends = [item.model_dump(mode="json") for item in data.emerging_trends]
        record.actionable_recommendations = data.actionable_recommendations
        record.sources = data.sources
        record.newsletter_count = data.newsletter_count
        record.status = DigestStatus.PENDING_REVIEW
        record.completed_at = datetime.now(UTC)
        record.agent_framework = data.agent_framework
        record.model_used = data.model_used
        record.model_version = data.model_version
        record.token_usage = data.token_usage
        record.processing_time_seconds = (
            int(data.processing_time_seconds) if data.processing_time_seconds else None
        )
        record.markdown_content = data.markdown_content
        record.theme_tags = data.theme_tags
        record.source_content_ids = data.source_content_ids
        record.source_summary_ids = data.source_summary_ids
        record.selection_fingerprint = data.selection_fingerprint
        record.selection_policy = data.selection_policy
        record.historical_context = data.historical_context
        record.is_combined = data.is_combined
        record.child_digest_ids = data.child_digest_ids
        record.source_digest_count = data.source_digest_count

    async def _existing(self, operation_id: str | int) -> Digest | None:
        return await recover_owned_resource(
            operations=self.operations,
            session_factory=self.session_factory,
            model=Digest,
            operation_id=operation_id,
            resource_type="digest",
            resource_url=lambda record_id: f"/api/v1/digests/{record_id}",
        )

    async def _attach_result(self, operation_id: str | int, record: Digest) -> None:
        await self.operations.attach_result(
            operation_id,
            {"digest_id": record.id, "selection_fingerprint": record.selection_fingerprint},
        )
        await self.operations.update_progress(operation_id, 100, "Digest complete")
