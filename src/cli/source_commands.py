"""CLI commands for ingestion source override management.

In HTTP mode (default), commands call the backend API via httpx.
In direct mode (--direct flag or API unreachable), commands call the
SourceOverrideService directly against the local database.

Database overrides merge on top of the sources.d/ YAML defaults via
load_sources_config(), keyed by the natural key '<type>:<locator>'.

Usage:
    aca sources list
    aca sources list --type blog
    aca sources add blog --url https://www.normaltech.ai/ --name "Normal Tech"
    aca sources remove "blog:https://www.normaltech.ai/"
    aca sources enable "blog:https://www.normaltech.ai/"
    aca sources disable "blog:https://www.normaltech.ai/"
"""

from __future__ import annotations

import json as _json
from typing import Annotated, Any

import httpx
import typer

from src.cli.output import guard_remote_backend, is_direct_mode, is_json_mode, output_result

app = typer.Typer(
    name="sources",
    help="Manage ingestion source overrides (DB-backed, merged over YAML).",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_config(
    source_type: str,
    *,
    url: str | None,
    id_: str | None,
    query: str | None,
    channel_id: str | None,
    name: str | None,
    tags: list[str] | None,
    max_entries: int | None,
    link_selector: str | None,
    link_pattern: str | None,
    content_filter_strategy: str | None,
    set_kv: list[str] | None,
    json_blob: str | None,
) -> dict[str, Any]:
    """Assemble a source config dict from CLI options.

    Starts from the optional ``--json`` blob, layers the typed options on top
    (None values dropped), then the generic ``--set KEY=VALUE`` escape hatch.
    Always stamps ``type``.
    """
    config: dict[str, Any] = {}

    if json_blob:
        try:
            parsed = _json.loads(json_blob)
        except _json.JSONDecodeError as exc:
            raise typer.BadParameter(f"--json is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise typer.BadParameter("--json must be a JSON object")
        config.update(parsed)

    typed: dict[str, Any] = {
        "url": url,
        "id": id_,
        "query": query,
        "channel_id": channel_id,
        "name": name,
        "tags": tags or None,
        "max_entries": max_entries,
        "link_selector": link_selector,
        "link_pattern": link_pattern,
        "content_filter_strategy": content_filter_strategy,
    }
    for field, value in typed.items():
        if value is not None:
            config[field] = value

    for item in set_kv or []:
        if "=" not in item:
            raise typer.BadParameter(f"--set expects KEY=VALUE, got {item!r}")
        k, v = item.split("=", 1)
        config[k.strip()] = _coerce_scalar(v)

    config["type"] = source_type
    return config


def _coerce_scalar(value: str) -> Any:
    """Best-effort coerce a --set value: JSON first, else raw string."""
    try:
        return _json.loads(value)
    except _json.JSONDecodeError:
        return value


def _require_public_source_key(key: str) -> None:
    """Fail closed when a private Obsidian natural key reaches the CLI boundary."""

    from src.services.source_override_service import (
        PublicSourceKeyError,
        validate_public_source_key,
    )

    try:
        validate_public_source_key(key)
    except PublicSourceKeyError as exc:
        _fail(str(exc))


def _print_mutation(data: dict[str, Any]) -> None:
    """Render an add/enable/disable result (source_key + version + enabled)."""
    if is_json_mode():
        output_result(data)
        return
    key = data.get("source_key")
    version = data.get("version")
    enabled = data.get("enabled")
    typer.echo(f"  Source {key} (v{version}, enabled={enabled})")


# ---------------------------------------------------------------------------
# Direct-mode implementations
# ---------------------------------------------------------------------------


def _list_sources_direct(source_type: str | None) -> None:
    """List the merged YAML + DB-override view directly."""
    guard_remote_backend("sources list")
    from src.config.settings import get_settings
    from src.config.sources import source_key as derive_source_key
    from src.services.source_override_service import public_source_key

    config = get_settings().get_sources_config()
    rows: list[dict[str, Any]] = []
    for s in config.sources:
        if source_type and s.type != source_type:
            continue
        try:
            skey = public_source_key(s) if s.type == "obsidian_vault" else derive_source_key(s)
        except ValueError:
            skey = None
        rows.append(
            {
                "type": s.type,
                "source_key": skey,
                "name": None if s.type == "obsidian_vault" else s.name,
                "enabled": s.enabled,
                "origin": getattr(s, "origin", "yaml"),
            }
        )

    _render_source_list(rows)


def _add_source_direct(config: dict[str, Any], description: str | None) -> None:
    """Upsert a source override directly via the service."""
    guard_remote_backend("sources add")
    from src.services.source_override_service import (
        SourceOverrideError,
        SourceOverrideService,
        public_source_key,
    )
    from src.storage.database import get_db

    try:
        with get_db() as db:
            row = SourceOverrideService(db).upsert(config, description=description)
            data = {
                "source_key": public_source_key(row),
                "version": row.version,
                "origin": "db",
                "enabled": row.enabled,
            }
    except SourceOverrideError as exc:
        _fail(str(exc))
        return

    _print_mutation(data)


def _remove_source_direct(key: str) -> None:
    """Delete a source override directly via the service."""
    _require_public_source_key(key)
    guard_remote_backend("sources remove")
    from src.services.source_override_service import SourceOverrideService
    from src.storage.database import get_db

    with get_db() as db:
        deleted_key = SourceOverrideService(db).delete(key)

    if deleted_key is None:
        _fail(f"No source override found for '{key}'")
        return

    if is_json_mode():
        output_result({"source_key": deleted_key, "deleted": True})
        return
    typer.echo(f"  Removed source override {deleted_key}")


def _set_enabled_direct(key: str, enabled: bool) -> None:
    """Enable/disable a source directly via the service."""
    _require_public_source_key(key)
    action = "sources enable" if enabled else "sources disable"
    guard_remote_backend(action)
    from src.config.settings import get_settings
    from src.config.sources import source_key as derive_source_key
    from src.services.source_override_service import (
        SourceOverrideError,
        SourceOverrideService,
        public_source_key,
    )
    from src.storage.database import get_db

    try:
        with get_db() as db:
            service = SourceOverrideService(db)
            fallback = None
            if service.get(key) is None:
                fallback = _resolve_fallback_config(
                    key,
                    get_settings().get_sources_config(),
                    derive_source_key,
                )
            row = service.set_enabled(key, enabled, fallback_config=fallback)
            data = {
                "source_key": public_source_key(row),
                "version": row.version,
                "origin": "db",
                "enabled": row.enabled,
            }
    except SourceOverrideError as exc:
        _fail(str(exc))
        return

    _print_mutation(data)


def _resolve_fallback_config(
    key: str, config: Any, derive_source_key: Any
) -> dict[str, Any] | None:
    """Find the YAML source matching ``key`` and return its config dict."""
    from src.services.source_override_service import public_source_key

    for s in config.sources:
        try:
            candidate_key = (
                public_source_key(s) if s.type == "obsidian_vault" else derive_source_key(s)
            )
            if candidate_key == key:
                data = s.model_dump()
                data.pop("origin", None)
                return data
        except ValueError:
            continue
    return None


def _render_source_list(rows: list[dict[str, Any]]) -> None:
    """Render a list of source rows (JSON or table)."""
    if is_json_mode():
        output_result({"sources": rows, "total": len(rows)})
        return

    if not rows:
        typer.echo("No sources configured.")
        return

    typer.echo()
    typer.echo(typer.style("  Configured Sources", bold=True))
    typer.echo()
    for r in rows:
        type_display = typer.style(r["type"], fg=typer.colors.MAGENTA)
        key_display = typer.style(r.get("source_key") or "-", fg=typer.colors.CYAN)
        enabled = r.get("enabled", True)
        status = (
            typer.style("enabled", fg=typer.colors.GREEN)
            if enabled
            else typer.style("disabled", fg=typer.colors.RED)
        )
        origin_display = typer.style(r.get("origin", "yaml"), dim=True)
        name = r.get("name") or ""
        typer.echo(f"  [{type_display}] {key_display}  {status}  ({origin_display})")
        if name:
            typer.echo(f"    {typer.style(name, dim=True)}")
    typer.echo()
    typer.echo(f"  Total: {len(rows)} source(s)")


def _fail(message: str) -> None:
    """Emit an error message and exit non-zero (JSON-aware)."""
    if is_json_mode():
        output_result({"error": message}, success=False)
    else:
        typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("list")
def list_sources(
    source_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="Filter by source type (e.g., 'blog', 'rss')"),
    ] = None,
) -> None:
    """List configured sources (merged YAML + database overrides).

    Columns: type, key, name, enabled, origin.
    """
    if is_direct_mode():
        return _list_sources_direct(source_type)

    try:
        from src.cli.api_client import get_api_client

        client = get_api_client()
        params: dict[str, Any] = {}
        if source_type:
            params["source_type"] = source_type
        data = client.list_sources(**params)

        if is_json_mode():
            output_result(data)
            return

        rows = [
            {
                "type": s.get("type"),
                "source_key": s.get("source_key"),
                "name": s.get("name"),
                "enabled": s.get("enabled", True),
                "origin": s.get("origin", "yaml"),
            }
            for s in data.get("sources", [])
            if not source_type or s.get("type") == source_type
        ]
        _render_source_list(rows)
    except httpx.ConnectError:
        if not is_json_mode():
            typer.echo("Backend unavailable -- running directly...", err=True)
        _list_sources_direct(source_type)


@app.command("add")
def add_source(
    source_type: Annotated[str, typer.Argument(help="Source type (e.g., 'blog', 'rss')")],
    url: Annotated[str | None, typer.Option("--url", help="Source URL")] = None,
    id_: Annotated[
        str | None, typer.Option("--id", help="Identifier (e.g. YouTube playlist id)")
    ] = None,
    query: Annotated[
        str | None, typer.Option("--query", help="Query string (gmail/scholar)")
    ] = None,
    channel_id: Annotated[
        str | None, typer.Option("--channel-id", help="YouTube channel id")
    ] = None,
    name: Annotated[str | None, typer.Option("--name", help="Human-readable name")] = None,
    tag: Annotated[list[str] | None, typer.Option("--tag", help="Tag (repeatable)")] = None,
    max_entries: Annotated[
        int | None, typer.Option("--max-entries", help="Max entries to ingest")
    ] = None,
    link_selector: Annotated[
        str | None, typer.Option("--link-selector", help="Blog link CSS selector")
    ] = None,
    link_pattern: Annotated[
        str | None, typer.Option("--link-pattern", help="Blog link regex pattern")
    ] = None,
    content_filter_strategy: Annotated[
        str | None,
        typer.Option("--content-filter-strategy", help="none|keyword|llm|keyword+llm"),
    ] = None,
    set_kv: Annotated[
        list[str] | None,
        typer.Option("--set", help="Generic KEY=VALUE field (repeatable)"),
    ] = None,
    json_blob: Annotated[
        str | None,
        typer.Option("--json", help="Full per-type field set as a JSON object"),
    ] = None,
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Optional human note")
    ] = None,
) -> None:
    """Add or update a source override.

    Builds a source config from the options and upserts it by natural key.
    """
    config = _build_config(
        source_type,
        url=url,
        id_=id_,
        query=query,
        channel_id=channel_id,
        name=name,
        tags=tag,
        max_entries=max_entries,
        link_selector=link_selector,
        link_pattern=link_pattern,
        content_filter_strategy=content_filter_strategy,
        set_kv=set_kv,
        json_blob=json_blob,
    )

    if is_direct_mode():
        return _add_source_direct(config, description)

    try:
        from src.cli.api_client import get_api_client

        client = get_api_client()
        data = client.add_source(config, description=description)
        _print_mutation(data)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            detail = _extract_detail(exc)
            _fail(detail)
        else:
            raise
    except httpx.ConnectError:
        if not is_json_mode():
            typer.echo("Backend unavailable -- running directly...", err=True)
        _add_source_direct(config, description)


@app.command("remove")
def remove_source(
    key: Annotated[
        str,
        typer.Argument(help="Public source key (opaque src_* key for private sources)"),
    ],
) -> None:
    """Remove a source override by its public management key."""
    _require_public_source_key(key)
    if is_direct_mode():
        return _remove_source_direct(key)

    try:
        from src.cli.api_client import get_api_client

        client = get_api_client()
        data = client.remove_source(key)

        if is_json_mode():
            output_result(data)
            return
        typer.echo(f"  Removed source override {data.get('source_key')}")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            _fail(f"No source override found for '{key}'")
        else:
            raise
    except httpx.ConnectError:
        if not is_json_mode():
            typer.echo("Backend unavailable -- running directly...", err=True)
        _remove_source_direct(key)


@app.command("enable")
def enable_source(
    key: Annotated[
        str,
        typer.Argument(help="Public source key (opaque src_* key for private sources)"),
    ],
) -> None:
    """Enable a source by its public management key."""
    _toggle_source(key, enabled=True)


@app.command("disable")
def disable_source(
    key: Annotated[
        str,
        typer.Argument(help="Public source key (opaque src_* key for private sources)"),
    ],
) -> None:
    """Disable a source by its public management key."""
    _toggle_source(key, enabled=False)


def _toggle_source(key: str, *, enabled: bool) -> None:
    """Shared enable/disable implementation."""
    _require_public_source_key(key)
    if is_direct_mode():
        return _set_enabled_direct(key, enabled)

    try:
        from src.cli.api_client import get_api_client

        client = get_api_client()
        data = client.set_source_enabled(key, enabled)
        _print_mutation(data)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            _fail(f"No source found for '{key}'")
        else:
            raise
    except httpx.ConnectError:
        if not is_json_mode():
            typer.echo("Backend unavailable -- running directly...", err=True)
        _set_enabled_direct(key, enabled)


def _extract_detail(exc: httpx.HTTPStatusError) -> str:
    """Pull a human message out of an HTTP error response."""
    try:
        body = exc.response.json()
        if isinstance(body, dict) and "detail" in body:
            return str(body["detail"])
    except Exception:
        pass
    return f"request failed with status {exc.response.status_code}"
