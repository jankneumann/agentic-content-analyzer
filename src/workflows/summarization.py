"""Durable summarization batch workflow."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from src.contracts.workflow_models import SummarizationRequest
from src.models.content import ContentStatus
from src.models.jobs import JobStatus, ResourceReference
from src.models.query import ContentQuery
from src.services.content_query import ContentQueryService
from src.services.operation_service import OperationService

ChildDispatcher = Callable[..., Awaitable[dict[str, Any]]]


class SummarizationWorkflow:
    """Normalize one batch selection and attach its durable aggregate result."""

    def __init__(
        self,
        *,
        operation_service: OperationService | Any | None = None,
        child_dispatcher: ChildDispatcher | None = None,
        query_service: ContentQueryService | Any | None = None,
    ) -> None:
        self.operations = operation_service or OperationService()
        self.child_dispatcher = child_dispatcher or self._dispatch_children
        self.query_service = query_service or ContentQueryService()

    async def execute(
        self,
        operation_id: str | int,
        request: SummarizationRequest,
    ) -> dict[str, Any]:
        if (request.content_ids is None) == (request.query is None):
            raise ValueError("Summarization requires exactly one of content_ids or query")
        handle = await self.operations.get(operation_id)
        if handle.resource is not None:
            if handle.resource.type != "summary_batch" or handle.resource.id != str(operation_id):
                raise ValueError("Operation is already attached to another resource")
            if handle.result and handle.result.get("deferred") is not True:
                await self._attach_completion(operation_id, handle.result)
                return handle.result

        existing_result = getattr(handle, "result", None)
        if existing_result and "child_operation_ids" in existing_result:
            content_ids = list(existing_result.get("content_ids", []))
        elif request.query is not None:
            query = ContentQuery.model_validate(request.query.model_dump(mode="python"))
            if not query.statuses:
                query = query.model_copy(
                    update={"statuses": [ContentStatus.PENDING, ContentStatus.PARSED]}
                )
            content_ids = self.query_service.resolve(query)
        else:
            content_ids = list(dict.fromkeys(request.content_ids or []))

        if not content_ids:
            result: dict[str, Any] = {
                "content_ids": [],
                "completed_ids": [],
                "failed_ids": [],
            }
            await self._attach_completion(operation_id, result)
            return result

        await self.operations.update_progress(operation_id, 10, "Dispatching summary items")
        dispatch_options: dict[str, Any] = {
            "parent_operation_id": int(operation_id),
            "force": request.force_reprocess,
        }
        if existing_result and existing_result.get("child_operation_ids"):
            dispatch_options["existing_child_operation_ids"] = existing_result[
                "child_operation_ids"
            ]
        result = await self.child_dispatcher(content_ids, **dispatch_options)
        normalized = {"content_ids": content_ids, **result}
        if normalized.get("deferred") is True:
            return normalized
        await self._attach_completion(operation_id, normalized)
        return normalized

    async def _attach_completion(
        self,
        operation_id: str | int,
        result: dict[str, Any],
    ) -> None:
        await self.operations.attach_completion(
            operation_id,
            result=result,
            resource=ResourceReference(
                type="summary_batch",
                id=str(operation_id),
                url=f"/api/v1/operations/{operation_id}",
            ),
            message="Summarization complete",
        )

    async def _dispatch_children(
        self,
        content_ids: list[int],
        *,
        parent_operation_id: int,
        force: bool,
        existing_child_operation_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        from src.queue.setup import enqueue_queue_job, get_job_status

        if existing_child_operation_ids:
            children = [await get_job_status(child_id) for child_id in existing_child_operation_ids]
            if any(
                child is not None and child.status in {JobStatus.QUEUED, JobStatus.IN_PROGRESS}
                for child in children
            ):
                return {
                    "deferred": True,
                    "child_operation_ids": existing_child_operation_ids,
                    "completed_ids": [],
                    "failed_ids": [],
                }
            completed_ids = [
                content_id
                for content_id, child in zip(content_ids, children, strict=True)
                if child is not None and child.status == JobStatus.COMPLETED
            ]
            failed_ids = [
                content_id
                for content_id, child in zip(content_ids, children, strict=True)
                if child is None or child.status != JobStatus.COMPLETED
            ]
            return {
                "deferred": False,
                "child_operation_ids": existing_child_operation_ids,
                "completed_ids": completed_ids,
                "failed_ids": failed_ids,
            }

        child_ids: list[int] = []
        for content_id in content_ids:
            child_id, _ = await enqueue_queue_job(
                "summarize_content",
                {"content_id": content_id, "force": force},
                parent_job_id=parent_operation_id,
                idempotency_key=f"summary:{parent_operation_id}:{content_id}:{int(force)}",
            )
            child_ids.append(child_id)
        return {
            "deferred": True,
            "child_operation_ids": child_ids,
            "completed_ids": [],
            "failed_ids": [],
        }
