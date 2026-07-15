"""Durable theme-analysis workflow."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.orm import Session

from src.contracts.workflow_models import ThemeAnalysisRequest as WorkflowThemeRequest
from src.models.jobs import ResourceReference
from src.models.query import ContentQuery, ResolvedContentSet, SelectionPolicy
from src.models.theme import (
    AnalysisStatus,
    ThemeAnalysis,
    ThemeAnalysisRequest,
    ThemeAnalysisResult,
)
from src.processors.theme_analyzer import ThemeAnalyzer
from src.services.content_set_resolver import ContentSetResolver
from src.services.operation_service import OperationService
from src.storage.database import get_db
from src.workflows.resource import recover_owned_resource


class ThemeAnalysisWorkflow:
    """Resolve once, analyze the exact snapshot, and persist its lifecycle."""

    def __init__(
        self,
        *,
        operation_service: OperationService | Any | None = None,
        resolver: ContentSetResolver | Any | None = None,
        analyzer: ThemeAnalyzer | Any | None = None,
        session_factory: Callable[[], AbstractContextManager[Session]] = get_db,
    ) -> None:
        self.operations = operation_service or OperationService()
        self.resolver = resolver or ContentSetResolver()
        self.analyzer = analyzer or ThemeAnalyzer()
        self.session_factory = session_factory

    async def analyze(
        self,
        request: WorkflowThemeRequest,
        *,
        resolved_set: ResolvedContentSet | None = None,
    ) -> ThemeAnalysisResult:
        resolved = resolved_set or self.resolver.resolve(
            ContentQuery.model_validate(request.query.model_dump(mode="python"))
        )
        start = resolved.policy.start_date or datetime.now(UTC)
        end = resolved.policy.end_date or datetime.now(UTC)
        return cast(
            ThemeAnalysisResult,
            await self.analyzer.analyze_themes(
                ThemeAnalysisRequest(
                    start_date=start,
                    end_date=end,
                    max_themes=request.max_themes,
                ),
                resolved,
            ),
        )

    async def execute(
        self,
        operation_id: str | int,
        request: WorkflowThemeRequest,
    ) -> ThemeAnalysis:
        existing = await self._existing(operation_id)
        if existing is not None and existing.status == AnalysisStatus.COMPLETED:
            await self._attach_result(operation_id, existing)
            return existing
        if existing is None:
            query = ContentQuery.model_validate(request.query.model_dump(mode="python"))
            resolved = self.resolver.resolve(query)
        else:
            resolved = self.resolver.resolve(
                SelectionPolicy.model_validate(existing.selection_policy)
            )
            if (
                resolved.fingerprint != existing.selection_fingerprint
                or list(resolved.content_ids) != existing.content_ids
                or list(resolved.summary_ids) != existing.summary_ids
            ):
                raise ValueError("Persisted theme selection changed before retry")
        if existing is None:
            record_id = self._reserve(resolved, operation_id=int(operation_id))
            await self._attach_resource(operation_id, record_id)
        else:
            record_id = cast(int, existing.id)
            with self.session_factory() as db:
                loaded = db.get(ThemeAnalysis, record_id)
                if loaded is None:
                    raise RuntimeError("Attached theme analysis resource does not exist")
                record = loaded
                record.status = AnalysisStatus.RUNNING
                record.error_message = None
                db.commit()

        try:
            await self.operations.update_progress(operation_id, 20, "Analyzing themes")
            record, _ = await self._run_and_persist(request, resolved, record_id)
        except Exception as exc:
            self._mark_failed(record_id, exc)
            raise
        await self._attach_result(operation_id, record)
        return record

    async def analyze_persisted(
        self,
        request: WorkflowThemeRequest,
        *,
        resolved_set: ResolvedContentSet,
    ) -> ThemeAnalysisResult:
        """Run an internal theme analysis while retaining its provenance record."""

        record_id = self._reserve(resolved_set, operation_id=None)
        try:
            _, result = await self._run_and_persist(request, resolved_set, record_id)
            return result
        except Exception as exc:
            self._mark_failed(record_id, exc)
            raise

    def _reserve(
        self,
        resolved: ResolvedContentSet,
        *,
        operation_id: int | None,
    ) -> int:
        start = resolved.policy.start_date or datetime.now(UTC)
        end = resolved.policy.end_date or datetime.now(UTC)
        with self.session_factory() as db:
            record = ThemeAnalysis(
                operation_id=operation_id,
                status=AnalysisStatus.RUNNING,
                start_date=start,
                end_date=end,
                content_count=len(resolved.content_ids),
                content_ids=list(resolved.content_ids),
                summary_ids=list(resolved.summary_ids),
                selection_fingerprint=resolved.fingerprint,
                selection_policy=resolved.policy.model_dump(mode="json"),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return cast(int, record.id)

    async def _run_and_persist(
        self,
        request: WorkflowThemeRequest,
        resolved: ResolvedContentSet,
        record_id: int,
    ) -> tuple[ThemeAnalysis, ThemeAnalysisResult]:
        result = await self.analyze(request, resolved_set=resolved)
        if (
            list(result.content_ids) != list(resolved.content_ids)
            or list(result.summary_ids) != list(resolved.summary_ids)
            or result.selection_fingerprint != resolved.fingerprint
            or SelectionPolicy.model_validate(result.selection_policy) != resolved.policy
        ):
            raise ValueError("Theme analysis provenance does not match resolved selection")
        with self.session_factory() as db:
            loaded = db.get(ThemeAnalysis, record_id)
            if loaded is None:
                raise RuntimeError(f"Reserved theme analysis {record_id} disappeared")
            loaded.status = AnalysisStatus.COMPLETED
            loaded.themes = [theme.model_dump(mode="json") for theme in result.themes]
            loaded.total_themes = result.total_themes
            loaded.emerging_themes_count = result.emerging_themes_count
            loaded.top_theme = result.top_theme
            loaded.agent_framework = result.agent_framework
            loaded.model_used = result.model_used
            loaded.model_version = result.model_version
            loaded.processing_time_seconds = result.processing_time_seconds  # type: ignore[assignment]
            loaded.token_usage = result.token_usage
            loaded.cross_theme_insights = result.cross_theme_insights
            db.commit()
            db.refresh(loaded)
            return cast(ThemeAnalysis, loaded), result

    def _mark_failed(self, record_id: int, exc: Exception) -> None:
        with self.session_factory() as db:
            failed = db.get(ThemeAnalysis, record_id)
            if failed is not None:
                failed.status = AnalysisStatus.FAILED
                failed.error_message = str(exc)
                db.commit()

    async def _existing(self, operation_id: str | int) -> ThemeAnalysis | None:
        return await recover_owned_resource(
            operations=self.operations,
            session_factory=self.session_factory,
            model=ThemeAnalysis,
            operation_id=operation_id,
            resource_type="theme_analysis",
            resource_url=lambda record_id: f"/api/v1/themes/analysis/{record_id}",
        )

    async def _attach_resource(self, operation_id: str | int, record_id: int) -> None:
        await self.operations.attach_resource(
            operation_id,
            ResourceReference(
                type="theme_analysis",
                id=str(record_id),
                url=f"/api/v1/themes/analysis/{record_id}",
            ),
        )

    async def _attach_result(self, operation_id: str | int, record: ThemeAnalysis) -> None:
        await self.operations.attach_result(
            operation_id,
            {"theme_analysis_id": record.id, "selection_fingerprint": record.selection_fingerprint},
        )
        await self.operations.update_progress(operation_id, 100, "Theme analysis complete")
