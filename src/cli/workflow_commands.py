"""Canonical durable workflow commands backed exclusively by the HTTP API."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, cast

import httpx
import typer
from click import Choice
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from src.clients.workflow_api_client import ProblemError, WorkflowApiClient
from src.contracts.workflow_models import (
    COMMAND_FIELD_SCHEMAS,
    ContentReconciliationRequest,
    IngestionHistoryItem,
    IngestionOutcome,
    OperationHandle,
    OperationStatus,
    Problem,
    TerminalOperationStatus,
)

ingest_app = typer.Typer(help="Submit a canonical ingestion operation.", no_args_is_help=True)
summarize_app = typer.Typer(help="Submit summarization operations.", no_args_is_help=True)
theme_app = typer.Typer(help="Submit theme analysis operations.", no_args_is_help=True)
digest_app = typer.Typer(help="Submit digest operations.", no_args_is_help=True)
pipeline_app = typer.Typer(help="Submit pipeline operations.", no_args_is_help=True)
podcast_script_app = typer.Typer(help="Submit podcast script operations.", no_args_is_help=True)
podcast_audio_app = typer.Typer(help="Submit podcast audio operations.", no_args_is_help=True)
audio_digest_app = typer.Typer(help="Submit audio digest operations.", no_args_is_help=True)
operations_app = typer.Typer(help="Observe and control durable operations.", no_args_is_help=True)


@dataclass(frozen=True)
class WorkflowCliState:
    json_output: bool
    client_factory: Callable[[], WorkflowApiClient]


def default_client_factory() -> WorkflowApiClient:
    from src.config.settings import get_settings

    settings = get_settings()
    return WorkflowApiClient(
        settings.api_base_url,
        admin_key=settings.admin_api_key,
        timeout=float(settings.api_timeout),
        follow_redirects=os.environ.get("ACA_RELEASE_SMOKE") != "1",
    )


def get_state(ctx: typer.Context) -> WorkflowCliState:
    root = ctx.find_root()
    if isinstance(root.obj, WorkflowCliState):
        return root.obj
    return WorkflowCliState(json_output=False, client_factory=default_client_factory)


def _emit_model(ctx: typer.Context, model: Any) -> None:
    state = get_state(ctx)
    if state.json_output:
        typer.echo(model.model_dump_json(exclude_none=True))
        return
    if isinstance(model, OperationHandle):
        typer.echo(f"{model.operation_type} {model.operation_id}: {model.status}")
        typer.echo(f"Progress: {model.progress}% - {model.message}")
        if model.resource:
            typer.echo(
                f"Resource: {model.resource.type} {model.resource.id} ({model.resource.url})"
            )
        return
    Console().print(model.model_dump(mode="json", exclude_none=True))


def _validation_problem(exc: ValidationError) -> Problem:
    return Problem(
        type="https://aca.rotkohl.ai/problems/validation_error",
        title="Unprocessable Entity",
        status=422,
        detail="Request validation failed",
        code="validation_error",
        errors=[
            {
                "path": list(error.get("loc", ())),
                "code": str(error.get("type", "validation_error")),
                "message": str(error.get("msg", "Invalid value")),
            }
            for error in exc.errors()
        ],
    )


def _run(ctx: typer.Context, action: Callable[[WorkflowApiClient], Any]) -> Any:
    state = get_state(ctx)
    try:
        with state.client_factory() as client:
            return action(client)
    except ProblemError as exc:
        if state.json_output:
            typer.echo(exc.problem.model_dump_json(exclude_none=True))
        else:
            typer.echo(f"{exc.problem.title}: {exc.problem.detail}", err=True)
            if exc.problem.code:
                typer.echo(f"Code: {exc.problem.code}", err=True)
        raise typer.Exit(1) from exc
    except ValidationError as exc:
        problem = _validation_problem(exc)
        if state.json_output:
            typer.echo(problem.model_dump_json(exclude_none=True))
        else:
            typer.echo(f"{problem.title}: {problem.detail}", err=True)
            for error in problem.errors or []:
                path = ".".join(str(part) for part in error["path"])
                typer.echo(f"{path}: {error['message']}", err=True)
        raise typer.Exit(2) from exc
    except (OSError, httpx.HTTPError) as exc:
        typer.echo(f"Workflow API unavailable: {exc}", err=True)
        raise typer.Exit(1) from exc


def _submit_and_maybe_wait(
    ctx: typer.Context,
    submit: Callable[[WorkflowApiClient], OperationHandle],
    *,
    wait: bool,
    timeout: float,
    on_waited: Callable[[typer.Context, OperationHandle], None] | None = None,
) -> None:
    def action(client: WorkflowApiClient) -> OperationHandle:
        handle = submit(client)
        if wait:
            if not get_state(ctx).json_output:
                typer.echo(f"Waiting for {handle.operation_id}...", err=True)
            handle = client.wait_operation(handle.operation_id, timeout_seconds=timeout)
        return handle

    handle = _run(ctx, action)
    _emit_model(ctx, handle)
    if wait and on_waited is not None:
        on_waited(ctx, handle)
    if handle.status in {"failed", "cancelled"}:
        raise typer.Exit(1)


def _emit_pipeline_wait_summary(ctx: typer.Context, handle: OperationHandle) -> None:
    if handle.status != "completed" or not isinstance(handle.result, dict):
        return
    summary = handle.result.get("ingestion_summary")
    if not isinstance(summary, dict):
        return
    outcome = summary.get("outcome")
    if outcome == "partial":
        typer.echo(
            "Warning: pipeline ingestion completed with partial source results.",
            err=True,
        )
    elif outcome == "zero_items" and not get_state(ctx).json_output:
        typer.echo("Pipeline ingestion completed with zero items.")


def _parse_ingest_args(kind: str, args: list[str]) -> dict[str, Any]:
    schema = COMMAND_FIELD_SCHEMAS[kind]
    properties: Mapping[str, Mapping[str, Any]] = schema["properties"]
    required = set(schema.get("required", ())) - {"kind"}
    payload: dict[str, Any] = {"kind": kind}
    positionals: list[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        if not token.startswith("--"):
            positionals.append(token)
            index += 1
            continue
        raw_name = token[2:]
        negative = raw_name.startswith("no-")
        field = (raw_name[3:] if negative else raw_name).replace("-", "_")
        field_schema = properties.get(field)
        if field_schema is None or field in {"kind", "configured_sources"}:
            raise typer.BadParameter(f"Unknown option --{raw_name} for {kind.replace('_', '-')}")
        if field_schema.get("type") == "boolean":
            payload[field] = not negative
            index += 1
            continue
        if negative:
            raise typer.BadParameter(f"--no-{raw_name[3:]} is only valid for boolean fields")
        index += 1
        if index >= len(args):
            raise typer.BadParameter(f"Option --{raw_name} requires a value")
        value: Any = args[index]
        if field_schema.get("type") == "integer":
            try:
                value = int(value)
            except ValueError as exc:
                raise typer.BadParameter(f"--{raw_name} requires an integer") from exc
        elif field_schema.get("type") == "array":
            value = [item for item in value.split(",") if item]
        payload[field] = value
        index += 1

    positional_field = {
        "url": "url",
        "scholar_paper": "identifier",
        "arxiv_paper": "identifier",
    }.get(kind)
    if kind == "files":
        if not positionals:
            raise typer.BadParameter("files requires at least one path")
        payload["paths"] = positionals
    elif positional_field:
        if len(positionals) != 1:
            raise typer.BadParameter(f"{kind.replace('_', '-')} requires one {positional_field}")
        payload[positional_field] = positionals[0]
    elif positionals:
        raise typer.BadParameter(f"Unexpected argument: {positionals[0]}")
    missing = required.difference(payload)
    if missing and kind != "files":
        raise typer.BadParameter(f"Missing required option(s): {', '.join(sorted(missing))}")
    return payload


def _make_ingest_command(kind: str) -> Callable[..., None]:
    def command(
        ctx: typer.Context,
        wait: Annotated[bool, typer.Option("--wait/--no-wait")] = False,
        timeout: Annotated[float, typer.Option("--timeout", min=0)] = 300.0,
        idempotency_key: Annotated[str | None, typer.Option("--idempotency-key")] = None,
    ) -> None:
        """Submit this source's typed ingestion command."""
        payload = _parse_ingest_args(kind, list(ctx.args))

        def submit(client: WorkflowApiClient) -> OperationHandle:
            if kind == "files":
                paths = payload.pop("paths")
                payload["upload_ids"] = [client.upload(Path(path)).id for path in paths]
            return client.submit_ingestion(payload, idempotency_key=idempotency_key)

        _submit_and_maybe_wait(ctx, submit, wait=wait, timeout=timeout)

    command.__name__ = f"ingest_{kind}"
    return command


for _kind in COMMAND_FIELD_SCHEMAS:
    ingest_app.command(
        _kind.replace("_", "-"),
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )(_make_ingest_command(_kind))


def _parse_history_timestamp(value: str | None, option: str) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise typer.BadParameter(f"{option} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise typer.BadParameter(f"{option} must include a timezone")
    return parsed.astimezone(UTC)


def _emit_ingestion_history_table(items: list[IngestionHistoryItem]) -> None:
    table = Table("Operation", "Command", "Status", "Outcome", "Ingested", "Failed", "Created")
    for item in items:
        table.add_row(
            item.operation_id,
            item.command_key,
            item.operation_status,
            item.outcome,
            "-" if item.items_ingested is None else str(item.items_ingested),
            "-" if item.items_failed is None else str(item.items_failed),
            item.created_at.isoformat(),
        )
    Console().print(table)


@ingest_app.command("history")
def ingest_history(
    ctx: typer.Context,
    command_key: Annotated[str | None, typer.Option("--command-key")] = None,
    configured_source_key: Annotated[
        str | None,
        typer.Option("--configured-source-key"),
    ] = None,
    outcome: Annotated[
        str | None,
        typer.Option(
            "--outcome",
            click_type=Choice(
                ["success", "zero_items", "partial", "failed", "cancelled", "unknown"]
            ),
        ),
    ] = None,
    history_status: Annotated[
        str | None,
        typer.Option(
            "--status",
            click_type=Choice(["completed", "failed", "cancelled"]),
        ),
    ] = None,
    parent_operation_id: Annotated[str | None, typer.Option("--parent-operation-id")] = None,
    created_after: Annotated[str | None, typer.Option("--created-after")] = None,
    created_before: Annotated[str | None, typer.Option("--created-before")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 50,
    cursor: Annotated[str | None, typer.Option("--cursor")] = None,
    all_pages: Annotated[bool, typer.Option("--all")] = False,
    max_pages: Annotated[int, typer.Option("--max-pages", min=1, max=100)] = 20,
) -> None:
    """List compact terminal ingestion history."""

    filters = {
        "command_key": command_key,
        "configured_source_key": configured_source_key,
        "outcome": cast(IngestionOutcome, outcome),
        "status": cast(TerminalOperationStatus, history_status),
        "parent_operation_id": parent_operation_id,
        "created_after": _parse_history_timestamp(created_after, "--created-after"),
        "created_before": _parse_history_timestamp(created_before, "--created-before"),
        "limit": limit,
        "cursor": cursor,
    }
    if all_pages:
        traversal = _run(
            ctx,
            lambda client: client.collect_ingestion_history(
                **filters,
                max_pages=max_pages,
            ),
        )
        if get_state(ctx).json_output:
            typer.echo(
                json.dumps(
                    {
                        "data": [
                            item.model_dump(mode="json", exclude_none=True)
                            for item in traversal.data
                        ],
                        "next_cursor": traversal.next_cursor,
                        "truncated": traversal.truncated,
                    }
                )
            )
        else:
            _emit_ingestion_history_table(traversal.data)
            if traversal.truncated:
                typer.echo(
                    f"Traversal truncated; continue with --cursor {traversal.next_cursor}",
                    err=True,
                )
        return

    page = _run(ctx, lambda client: client.list_ingestion_history(**filters))
    if get_state(ctx).json_output:
        _emit_model(ctx, page)
        return
    _emit_ingestion_history_table(page.data)
    if page.next_cursor is not None:
        typer.echo(f"More results; continue with --cursor {page.next_cursor}", err=True)


def _json_object(value: str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter("Expected a JSON object") from exc
    if not isinstance(parsed, dict):
        raise typer.BadParameter("Expected a JSON object")
    return parsed


def _common_submit(
    ctx: typer.Context,
    method: str,
    payload: dict[str, Any],
    wait: bool,
    timeout: float,
    idempotency_key: str | None,
) -> None:
    _submit_and_maybe_wait(
        ctx,
        lambda client: getattr(client, method)(payload, idempotency_key=idempotency_key),
        wait=wait,
        timeout=timeout,
    )


@summarize_app.command("run")
def summarize_run(
    ctx: typer.Context,
    content_id: Annotated[list[int] | None, typer.Option("--content-id")] = None,
    query_json: Annotated[str | None, typer.Option("--query-json")] = None,
    force_reprocess: Annotated[bool, typer.Option("--force-reprocess")] = False,
    wait: Annotated[bool, typer.Option("--wait/--no-wait")] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=0)] = 300.0,
    idempotency_key: Annotated[str | None, typer.Option("--idempotency-key")] = None,
) -> None:
    payload = {
        "content_ids": content_id,
        "query": _json_object(query_json),
        "force_reprocess": force_reprocess,
    }
    _common_submit(ctx, "submit_summarization", payload, wait, timeout, idempotency_key)


@theme_app.command("create")
def theme_create(
    ctx: typer.Context,
    query_json: Annotated[str, typer.Option("--query-json")] = "{}",
    max_themes: Annotated[int, typer.Option("--max-themes", min=1, max=50)] = 10,
    wait: Annotated[bool, typer.Option("--wait/--no-wait")] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=0)] = 300.0,
    idempotency_key: Annotated[str | None, typer.Option("--idempotency-key")] = None,
) -> None:
    _common_submit(
        ctx,
        "submit_theme_analysis",
        {"query": _json_object(query_json), "max_themes": max_themes},
        wait,
        timeout,
        idempotency_key,
    )


def _period_payload(period: str, period_start: str, period_end: str) -> dict[str, Any]:
    return {"period": period, "period_start": period_start, "period_end": period_end}


@digest_app.command("create")
def digest_create(
    ctx: typer.Context,
    digest_type: Annotated[str, typer.Option("--type", click_type=Choice(["daily", "weekly"]))],
    period_start: Annotated[str, typer.Option("--period-start")],
    period_end: Annotated[str, typer.Option("--period-end")],
    query_json: Annotated[str | None, typer.Option("--query-json")] = None,
    include_historical_context: Annotated[
        bool, typer.Option("--historical-context/--no-historical-context")
    ] = True,
    wait: Annotated[bool, typer.Option("--wait/--no-wait")] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=0)] = 300.0,
    idempotency_key: Annotated[str | None, typer.Option("--idempotency-key")] = None,
) -> None:
    payload = {
        "digest_type": digest_type,
        "period_start": period_start,
        "period_end": period_end,
        "query": _json_object(query_json),
        "include_historical_context": include_historical_context,
    }
    _common_submit(ctx, "submit_digest", payload, wait, timeout, idempotency_key)


@pipeline_app.command("run")
def pipeline_run(
    ctx: typer.Context,
    period: Annotated[str, typer.Option("--period", click_type=Choice(["daily", "weekly"]))],
    period_start: Annotated[str, typer.Option("--period-start")],
    period_end: Annotated[str, typer.Option("--period-end")],
    source: Annotated[list[str] | None, typer.Option("--source")] = None,
    continue_on_source_error: Annotated[
        bool, typer.Option("--continue-on-source-error/--fail-on-source-error")
    ] = True,
    wait: Annotated[bool, typer.Option("--wait/--no-wait")] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=0)] = 300.0,
    idempotency_key: Annotated[str | None, typer.Option("--idempotency-key")] = None,
) -> None:
    payload = _period_payload(period, period_start, period_end) | {
        "sources": source,
        "continue_on_source_error": continue_on_source_error,
    }
    _submit_and_maybe_wait(
        ctx,
        lambda client: client.submit_pipeline(payload, idempotency_key=idempotency_key),
        wait=wait,
        timeout=timeout,
        on_waited=_emit_pipeline_wait_summary,
    )


@podcast_script_app.command("create")
def podcast_script_create(
    ctx: typer.Context,
    digest_id: Annotated[int, typer.Option("--digest-id", min=1)],
    length: Annotated[
        str, typer.Option("--length", click_type=Choice(["brief", "standard", "extended"]))
    ] = "standard",
    enable_web_search: Annotated[bool, typer.Option("--web-search/--no-web-search")] = True,
    focus_topic: Annotated[list[str] | None, typer.Option("--focus-topic")] = None,
    custom_instructions: Annotated[str | None, typer.Option("--custom-instructions")] = None,
    wait: Annotated[bool, typer.Option("--wait/--no-wait")] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=0)] = 300.0,
    idempotency_key: Annotated[str | None, typer.Option("--idempotency-key")] = None,
) -> None:
    payload = {
        "digest_id": digest_id,
        "length": length,
        "enable_web_search": enable_web_search,
        "custom_focus_topics": focus_topic,
        "custom_instructions": custom_instructions,
    }
    _common_submit(ctx, "submit_podcast_script", payload, wait, timeout, idempotency_key)


@podcast_audio_app.command("create")
def podcast_audio_create(
    ctx: typer.Context,
    script_id: Annotated[int, typer.Option("--script-id", min=1)],
    voice_provider: Annotated[
        str,
        typer.Option(
            "--voice-provider",
            click_type=Choice(["elevenlabs", "google_tts", "aws_polly", "openai_tts"]),
        ),
    ] = "openai_tts",
    alex_voice: Annotated[
        str, typer.Option("--alex-voice", click_type=Choice(["alex_male", "alex_female"]))
    ] = "alex_male",
    sam_voice: Annotated[
        str, typer.Option("--sam-voice", click_type=Choice(["sam_male", "sam_female"]))
    ] = "sam_female",
    wait: Annotated[bool, typer.Option("--wait/--no-wait")] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=0)] = 300.0,
    idempotency_key: Annotated[str | None, typer.Option("--idempotency-key")] = None,
) -> None:
    payload = {
        "script_id": script_id,
        "voice_provider": voice_provider,
        "alex_voice": alex_voice,
        "sam_voice": sam_voice,
    }
    _common_submit(ctx, "submit_podcast_audio", payload, wait, timeout, idempotency_key)


@audio_digest_app.command("create")
def audio_digest_create(
    ctx: typer.Context,
    digest_id: Annotated[int, typer.Option("--digest-id", min=1)],
    provider: Annotated[str, typer.Option("--provider")] = "openai",
    voice: Annotated[str, typer.Option("--voice")] = "nova",
    speed: Annotated[float, typer.Option("--speed", min=0.5, max=2.0)] = 1.0,
    wait: Annotated[bool, typer.Option("--wait/--no-wait")] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=0)] = 300.0,
    idempotency_key: Annotated[str | None, typer.Option("--idempotency-key")] = None,
) -> None:
    _common_submit(
        ctx,
        "submit_audio_digest",
        {"digest_id": digest_id, "provider": provider, "voice": voice, "speed": speed},
        wait,
        timeout,
        idempotency_key,
    )


@operations_app.command("list")
def operations_list(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 50,
    cursor: Annotated[str | None, typer.Option("--cursor")] = None,
    operation_status: Annotated[
        str | None,
        typer.Option(
            "--status",
            click_type=Choice(["queued", "in_progress", "completed", "failed", "cancelled"]),
        ),
    ] = None,
    all_pages: Annotated[bool, typer.Option("--all")] = False,
    max_pages: Annotated[int, typer.Option("--max-pages", min=1, max=100)] = 20,
) -> None:
    if all_pages:
        traversal = _run(
            ctx,
            lambda client: client.collect_operations(
                limit=limit,
                cursor=cursor,
                status=cast(OperationStatus, operation_status),
                max_pages=max_pages,
            ),
        )
        if get_state(ctx).json_output:
            typer.echo(
                json.dumps(
                    {
                        "data": [
                            item.model_dump(mode="json", exclude_none=True)
                            for item in traversal.data
                        ],
                        "next_cursor": traversal.next_cursor,
                        "truncated": traversal.truncated,
                    }
                )
            )
        else:
            table = Table("Operation", "Type", "Status", "Progress")
            for item in traversal.data:
                table.add_row(
                    item.operation_id, item.operation_type, item.status, f"{item.progress}%"
                )
            Console().print(table)
            if traversal.truncated:
                typer.echo(
                    f"Traversal truncated; continue with --cursor {traversal.next_cursor}",
                    err=True,
                )
        return
    _emit_model(
        ctx,
        _run(
            ctx,
            lambda client: client.list_operations(
                limit=limit,
                cursor=cursor,
                status=cast(OperationStatus, operation_status),
            ),
        ),
    )


@operations_app.command("get")
def operations_get(ctx: typer.Context, operation_id: str) -> None:
    _emit_model(ctx, _run(ctx, lambda client: client.get_operation(operation_id)))


@operations_app.command("reconcile-content")
def operations_reconcile_content(
    ctx: typer.Context,
    apply_changes: Annotated[
        bool,
        typer.Option("--apply", help="Apply guarded repairs instead of previewing them."),
    ] = False,
    limit: Annotated[int | None, typer.Option("--limit", min=1, max=100)] = None,
    after_content_id: Annotated[
        int | None,
        typer.Option("--after-content-id", min=1),
    ] = None,
) -> None:
    """Preview or apply one bounded reconciliation page remotely."""
    request = ContentReconciliationRequest(
        apply=apply_changes,
        limit=limit,
        after_content_id=after_content_id,
    )
    report = _run(ctx, lambda client: client.reconcile_content(request))
    _emit_model(ctx, report)
    if apply_changes and any(item.reason == "apply_failed" for item in report.items):
        raise typer.Exit(1)


@operations_app.command("wait")
def operations_wait(
    ctx: typer.Context,
    operation_id: str,
    timeout: Annotated[float, typer.Option("--timeout", min=0)] = 300.0,
) -> None:
    handle = _run(ctx, lambda client: client.wait_operation(operation_id, timeout_seconds=timeout))
    _emit_model(ctx, handle)
    if handle.status in {"failed", "cancelled"}:
        raise typer.Exit(1)


@operations_app.command("retry")
def operations_retry(ctx: typer.Context, operation_id: str) -> None:
    _emit_model(ctx, _run(ctx, lambda client: client.retry_operation(operation_id)))


@operations_app.command("cancel")
def operations_cancel(ctx: typer.Context, operation_id: str) -> None:
    _emit_model(ctx, _run(ctx, lambda client: client.cancel_operation(operation_id)))


def capabilities(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 50,
    cursor: Annotated[str | None, typer.Option("--cursor")] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit the capability contract.")
    ] = False,
) -> None:
    if json_output:
        state = get_state(ctx)
        ctx.find_root().obj = WorkflowCliState(True, state.client_factory)
    _emit_model(ctx, _run(ctx, lambda client: client.get_capabilities(limit=limit, cursor=cursor)))


def configured_sources(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 50,
    cursor: Annotated[str | None, typer.Option("--cursor")] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit the configured-source page.")
    ] = False,
) -> None:
    if json_output:
        state = get_state(ctx)
        ctx.find_root().obj = WorkflowCliState(True, state.client_factory)
    _emit_model(
        ctx, _run(ctx, lambda client: client.list_configured_sources(limit=limit, cursor=cursor))
    )
