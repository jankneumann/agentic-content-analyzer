from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.contracts.workflow_models import ContentQuery, SummarizationRequest
from src.models.content import ContentStatus
from src.models.jobs import ResourceReference
from src.workflows.summarization import SummarizationWorkflow


@pytest.mark.asyncio
async def test_summarization_dispatches_children_and_attaches_batch_result() -> None:
    operations = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(resource=None)),
        update_progress=AsyncMock(),
        attach_resource=AsyncMock(),
        attach_result=AsyncMock(),
        attach_completion=AsyncMock(),
    )
    dispatcher = AsyncMock(return_value={"completed_ids": [7, 9], "failed_ids": []})
    workflow = SummarizationWorkflow(operation_service=operations, child_dispatcher=dispatcher)

    result = await workflow.execute("41", SummarizationRequest(content_ids=[9, 7, 9]))

    dispatcher.assert_awaited_once_with([9, 7], parent_operation_id=41, force=False)
    assert result == {"content_ids": [9, 7], "completed_ids": [7, 9], "failed_ids": []}
    operations.attach_completion.assert_awaited_once_with(
        "41",
        result=result,
        resource=ResourceReference(type="summary_batch", id="41", url="/api/v1/operations/41"),
        message="Summarization complete",
    )


@pytest.mark.asyncio
async def test_summarization_requires_exactly_one_selection() -> None:
    workflow = SummarizationWorkflow(
        operation_service=SimpleNamespace(), child_dispatcher=AsyncMock()
    )

    with pytest.raises(ValueError, match="exactly one"):
        await workflow.execute("1", SummarizationRequest())


@pytest.mark.asyncio
async def test_summarization_does_not_complete_while_children_are_pending() -> None:
    operations = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(resource=None)),
        update_progress=AsyncMock(),
        attach_resource=AsyncMock(),
        attach_result=AsyncMock(),
        attach_completion=AsyncMock(),
    )
    dispatcher = AsyncMock(
        return_value={
            "deferred": True,
            "child_operation_ids": [101, 102],
            "completed_ids": [],
            "failed_ids": [],
        }
    )
    workflow = SummarizationWorkflow(operation_service=operations, child_dispatcher=dispatcher)

    result = await workflow.execute("42", SummarizationRequest(content_ids=[1, 2]))

    assert result["deferred"] is True
    operations.attach_resource.assert_not_awaited()
    operations.attach_result.assert_not_awaited()
    operations.attach_completion.assert_not_awaited()


@pytest.mark.asyncio
async def test_summarization_query_uses_pending_and_parsed_defaults() -> None:
    operations = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(resource=None)),
        update_progress=AsyncMock(),
        attach_resource=AsyncMock(),
        attach_result=AsyncMock(),
        attach_completion=AsyncMock(),
    )
    query_service = SimpleNamespace(resolve=Mock(return_value=[4]))
    workflow = SummarizationWorkflow(
        operation_service=operations,
        query_service=query_service,
        child_dispatcher=AsyncMock(return_value={"completed_ids": [4], "failed_ids": []}),
    )

    await workflow.execute("43", SummarizationRequest(query=ContentQuery()))

    resolved_query = query_service.resolve.call_args.args[0]
    assert resolved_query.statuses == [ContentStatus.PENDING, ContentStatus.PARSED]


@pytest.mark.asyncio
async def test_summarization_reuses_checkpointed_query_ids_on_reentry() -> None:
    first_result = {
        "content_ids": [1, 2],
        "deferred": True,
        "child_operation_ids": [101, 102],
        "completed_ids": [],
        "failed_ids": [],
    }
    operations = SimpleNamespace(
        get=AsyncMock(
            side_effect=[
                SimpleNamespace(resource=None, result=None),
                SimpleNamespace(resource=None, result=first_result),
            ]
        ),
        update_progress=AsyncMock(),
        attach_resource=AsyncMock(),
        attach_result=AsyncMock(),
        attach_completion=AsyncMock(),
    )
    query_service = SimpleNamespace(resolve=Mock(side_effect=[[1, 2], [9]]))
    dispatcher = AsyncMock(
        side_effect=[
            {key: value for key, value in first_result.items() if key != "content_ids"},
            {
                "deferred": False,
                "child_operation_ids": [101, 102],
                "completed_ids": [1, 2],
                "failed_ids": [],
            },
        ]
    )
    workflow = SummarizationWorkflow(
        operation_service=operations,
        query_service=query_service,
        child_dispatcher=dispatcher,
    )
    request = SummarizationRequest(query=ContentQuery())

    await workflow.execute("44", request)
    result = await workflow.execute("44", request)

    assert result["completed_ids"] == [1, 2]
    assert query_service.resolve.call_count == 1
    dispatcher.assert_awaited_with(
        [1, 2],
        parent_operation_id=44,
        force=False,
        existing_child_operation_ids=[101, 102],
    )


@pytest.mark.asyncio
async def test_summarization_empty_query_completes_without_children() -> None:
    operations = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(resource=None, result=None)),
        update_progress=AsyncMock(),
        attach_resource=AsyncMock(),
        attach_result=AsyncMock(),
        attach_completion=AsyncMock(),
    )
    dispatcher = AsyncMock()
    workflow = SummarizationWorkflow(
        operation_service=operations,
        query_service=SimpleNamespace(resolve=Mock(return_value=[])),
        child_dispatcher=dispatcher,
    )

    result = await workflow.execute("45", SummarizationRequest(query=ContentQuery()))

    assert result == {"content_ids": [], "completed_ids": [], "failed_ids": []}
    dispatcher.assert_not_awaited()
    operations.attach_completion.assert_awaited_once()


@pytest.mark.asyncio
async def test_summarization_resource_reentry_repairs_result_without_new_children() -> None:
    checkpoint = {
        "content_ids": [7],
        "deferred": True,
        "child_operation_ids": [101],
        "completed_ids": [],
        "failed_ids": [],
    }
    operations = SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(
                resource=ResourceReference(
                    type="summary_batch",
                    id="46",
                    url="/api/v1/operations/46",
                ),
                result=checkpoint,
            )
        ),
        update_progress=AsyncMock(),
        attach_result=AsyncMock(),
        attach_completion=AsyncMock(),
    )
    dispatcher = AsyncMock(
        return_value={
            "deferred": False,
            "child_operation_ids": [101],
            "completed_ids": [7],
            "failed_ids": [],
        }
    )
    workflow = SummarizationWorkflow(operation_service=operations, child_dispatcher=dispatcher)

    result = await workflow.execute("46", SummarizationRequest(content_ids=[7]))

    assert result["completed_ids"] == [7]
    dispatcher.assert_awaited_once_with(
        [7],
        parent_operation_id=46,
        force=False,
        existing_child_operation_ids=[101],
    )
    operations.attach_completion.assert_awaited_once()
