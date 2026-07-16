"""MCP composition root for canonical content workflows."""

from __future__ import annotations

import json
import os
import secrets
from asyncio import run
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.mcp import content, ingestion, knowledge, operations, review, runtime, workflows
from src.mcp.toolsets import CANONICAL_TOOL_NAMES, register_toolsets

mcp = FastMCP(
    "Newsletter Aggregator",
    instructions=(
        "Use get_capabilities to discover ingestion fields and workflow operations. "
        "Mutations return durable operation handles; use get_operation_status or "
        "wait_for_operation to observe completion."
    ),
)
register_toolsets(mcp)

# Import-compatible public functions. Registration remains owned by bounded modules.
for _module in (ingestion, content, workflows, review, operations, knowledge):
    for _name in getattr(_module, "TOOLS", ()):
        globals()[_name.__name__] = _name


# These sync imports are not registered as MCP tools. They preserve the old Python
# helper surface for internal callers while the protocol surface returns native data.
def get_content_references(content_id: int, direction: str = "outgoing") -> str:
    from src.models.content_reference import ContentReference, ResolutionStatus
    from src.storage.database import get_db

    with get_db() as db:
        query = db.query(ContentReference)
        if direction == "incoming":
            query = query.filter(
                ContentReference.target_content_id == content_id,
                ContentReference.resolution_status == ResolutionStatus.RESOLVED,
            )
        else:
            query = query.filter(ContentReference.source_content_id == content_id)
        references = query.all()
    rows = [
        {
            key: getattr(reference, key, None)
            for key in (
                "id",
                "reference_type",
                "external_id",
                "external_id_type",
                "external_url",
                "resolution_status",
                "target_content_id",
                "confidence",
            )
        }
        for reference in references
    ]
    return json.dumps({"references": rows, "count": len(rows), "direction": direction}, default=str)


def extract_references(
    after: str | None = None,
    before: str | None = None,
    source: str | None = None,
    dry_run: bool = False,
    batch_size: int = 50,
) -> str:
    from src.models.content import Content
    from src.services.reference_extractor import ReferenceExtractor
    from src.storage.database import get_db

    extractor = ReferenceExtractor()
    with get_db() as db:
        query = db.query(Content).order_by(Content.ingested_at.asc())
        if after:
            query = query.filter(Content.ingested_at >= after)
        if before:
            query = query.filter(Content.ingested_at <= before)
        if source:
            query = query.filter(Content.source_type == source)
        contents = query.limit(batch_size + 1).all()
        has_more = len(contents) > batch_size
        contents = contents[:batch_size]
        count = 0
        per_content = []
        for item in contents:
            references = extractor.extract_from_content(item, db)
            count += (
                len(references)
                if dry_run
                else extractor.store_references(item.id, references, db)
                if references
                else 0
            )
            per_content.append({"content_id": item.id, "references_found": len(references)})
    return json.dumps(
        {
            "references_extracted": count,
            "content_processed": len(contents),
            "has_more": has_more,
            "per_content": per_content,
        }
    )


def resolve_references(batch_size: int = 100) -> str:
    from src.models.content_reference import ContentReference, ResolutionStatus
    from src.services.reference_resolver import ReferenceResolver
    from src.storage.database import get_db

    with get_db() as db:
        resolved = ReferenceResolver(db).resolve_batch(batch_size)
        remaining = (
            db.query(ContentReference)
            .filter(ContentReference.resolution_status == ResolutionStatus.UNRESOLVED)
            .count()
        )
    return json.dumps(
        {
            "resolved_count": int(resolved),
            "still_unresolved_count": int(remaining),
            "has_more": remaining > 0,
        }
    )


def ingest_reference(reference_id: int) -> str:
    from src.config.settings import get_settings
    from src.models.content_reference import ContentReference, ResolutionStatus
    from src.services.reference_auto_ingest import AutoIngestTrigger
    from src.storage.database import get_db

    with get_db() as db:
        reference = db.get(ContentReference, reference_id)
        if reference is None:
            return json.dumps({"error": f"Reference {reference_id} not found"})
        if reference.resolution_status == ResolutionStatus.RESOLVED:
            return json.dumps(
                {
                    "status": "already_resolved",
                    "target_content_id": reference.target_content_id,
                }
            )
        if not reference.external_id or not reference.external_id_type:
            return json.dumps({"error": "Reference has no structured ID for ingestion"})
        content = run(
            AutoIngestTrigger(
                db=db,
                enabled=True,
                max_depth=get_settings().reference_auto_ingest_max_depth,
            ).maybe_ingest(reference)
        )
        return json.dumps(
            {
                "status": "ingested" if content else "ingestion_failed",
                "content_id": getattr(content, "id", None),
            }
        )


_strict_http_mode = runtime.strict_http_mode
_validate_strict_http_config_or_exit = runtime.validate_strict_http_config_or_exit


def _get_api_client() -> Any | None:
    """Compatibility hook returning the shared client in configured HTTP mode."""
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return runtime.create_workflow_client()
    return None


class AdminKeyAuthMiddleware:
    """Protect remote MCP transports with the configured admin key."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        from src.config import get_settings

        settings = get_settings()
        if settings.is_development and not settings.admin_api_key:
            await self.app(scope, receive, send)
            return
        supplied = dict(scope.get("headers", [])).get(b"x-admin-key", b"").decode()
        if settings.admin_api_key and secrets.compare_digest(supplied, settings.admin_api_key):
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 4401})
            return
        body = json.dumps({"error": "Authentication required"}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"content-length", str(len(body)).encode()],
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="aca-mcp")
    parser.add_argument(
        "--strict-http",
        action="store_true",
        help="Require complete HTTP configuration and disable in-process mode.",
    )
    args, _ = parser.parse_known_args()
    if args.strict_http:
        os.environ["ACA_MCP_STRICT_HTTP"] = "1"
    runtime.validate_strict_http_config_or_exit()

    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "stdio":
        mcp.run()
        return

    import uvicorn

    if transport == "sse":
        app = mcp.sse_app()
    elif transport == "streamable-http":
        app = mcp.streamable_http_app()
    else:
        raise ValueError(f"Unknown MCP transport: {transport}")
    app.add_middleware(AdminKeyAuthMiddleware)
    uvicorn.run(
        app,
        host=os.environ.get("MCP_HOST", "0.0.0.0"),  # noqa: S104
        port=int(os.environ.get("MCP_PORT", "8100")),
    )


__all__ = ["CANONICAL_TOOL_NAMES", "mcp", "main", *CANONICAL_TOOL_NAMES]


if __name__ == "__main__":
    main()
