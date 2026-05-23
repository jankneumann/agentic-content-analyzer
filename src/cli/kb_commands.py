"""CLI commands for the knowledge base.

Provides ``aca kb`` command group for compiling, listing, showing,
querying, and linting topics in the knowledge base.

Read commands (list, show, index, query) route through the HTTP API when
the active profile targets a remote backend, so they reflect production
data instead of the local DB. Under a local profile — or with an explicit
``--direct`` — they call the KnowledgeBaseService directly. Write/build
commands (compile, lint) remain direct-only and are refused under a remote
profile by ``guard_remote_backend``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from src.cli.output import (
    guard_remote_backend,
    is_direct_mode,
    is_json_mode,
    is_remote_backend,
    output_result,
)

if TYPE_CHECKING:
    from src.cli.api_client import ApiClient

app = typer.Typer(help="Knowledge base management.")


def _get_db() -> Any:
    """Open a synchronous DB session (returns the get_db context manager)."""
    from src.storage.database import get_db

    return get_db()


def _route_to_api() -> bool:
    """True when reads should go over HTTP to the remote backend.

    Under a remote profile the local DB is the wrong data source (split-brain),
    so read commands fetch from the prod API instead. An explicit ``--direct``
    opts back out — and is then refused by ``guard_remote_backend`` rather than
    silently hitting local data.
    """
    return is_remote_backend() and not is_direct_mode()


@contextmanager
def _api_client() -> Iterator[ApiClient]:
    """Yield an ApiClient and always close it."""
    from src.cli.api_client import get_api_client

    client = get_api_client()
    try:
        yield client
    finally:
        client.close()


# ---------------------------------------------------------------------------
# compile
# ---------------------------------------------------------------------------


@app.command("compile")
def compile_kb(
    full: Annotated[
        bool,
        typer.Option(
            "--full",
            help="Recompile all active topics regardless of last_compiled_at.",
        ),
    ] = False,
    topic: Annotated[
        str | None,
        typer.Option("--topic", "-t", help="Recompile a single topic by slug."),
    ] = None,
) -> None:
    """Compile the knowledge base from theme analyses, summaries, and content."""
    guard_remote_backend("kb compile")
    from src.services.knowledge_base import (
        KBCompileLockError,
        KnowledgeBaseService,
    )

    console = Console()

    async def _run() -> dict:
        with _get_db() as db:
            service = KnowledgeBaseService(db)
            if full:
                result = await service.compile_full()
            elif topic:
                result = await service.compile_topic(topic)
            else:
                result = await service.compile()
            return result.to_dict()

    try:
        summary = asyncio.run(_run())
    except KBCompileLockError as exc:
        if is_json_mode():
            output_result({"error": str(exc), "code": "compile_in_progress"}, success=False)
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc
    except Exception as exc:
        if is_json_mode():
            output_result({"error": str(exc)}, success=False)
        else:
            console.print(f"[red]Compile failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    if is_json_mode():
        output_result(summary)
        return

    console.print(
        f"[green]Compile complete:[/green] "
        f"found={summary['topics_found']} "
        f"compiled={summary['topics_compiled']} "
        f"skipped={summary['topics_skipped']} "
        f"failed={summary['topics_failed']}"
    )
    if summary["merge_candidates"]:
        console.print(f"[yellow]Merge candidates:[/yellow] {len(summary['merge_candidates'])}")


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@app.command("list")
def list_topics(
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Filter by category."),
    ] = None,
    trend: Annotated[
        str | None,
        typer.Option("--trend", help="Filter by trend (emerging, growing, etc.)."),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option("--status", help="Filter by status (active, draft, stale, archived)."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum number of topics to show."),
    ] = 50,
) -> None:
    """List topics in the knowledge base."""
    console = Console()

    if _route_to_api():
        with _api_client() as client:
            rows = client.kb_list_topics(category=category, trend=trend, status=status, limit=limit)
        topic_dicts = [
            {
                "slug": r.get("slug"),
                "name": r.get("name"),
                "category": r.get("category"),
                "trend": r.get("trend"),
                "status": r.get("status"),
                "mention_count": r.get("mention_count", 0),
                "relevance_score": r.get("relevance_score", 0.0),
                "article_version": None,
                "last_compiled_at": r.get("last_compiled_at"),
            }
            for r in rows
        ]
    else:
        guard_remote_backend("kb list")
        from src.models.topic import Topic, TopicStatus

        with _get_db() as db:
            query = db.query(Topic)
            # Default to ACTIVE topics unless --status is given
            if status:
                query = query.filter(Topic.status == status)
            else:
                query = query.filter(Topic.status == TopicStatus.ACTIVE)
            if category:
                query = query.filter(Topic.category == category)
            if trend:
                query = query.filter(Topic.trend == trend)

            topics = query.order_by(Topic.relevance_score.desc().nullslast()).limit(limit).all()

            topic_dicts = [
                {
                    "slug": t.slug,
                    "name": t.name,
                    "category": t.category,
                    "trend": t.trend,
                    "status": str(t.status),
                    "mention_count": t.mention_count,
                    "relevance_score": t.relevance_score,
                    "article_version": t.article_version,
                    "last_compiled_at": (
                        t.last_compiled_at.isoformat() if t.last_compiled_at else None
                    ),
                }
                for t in topics
            ]

    if is_json_mode():
        output_result({"topics": topic_dicts, "count": len(topic_dicts)})
        return

    if not topic_dicts:
        console.print("[yellow]No topics found.[/yellow]")
        return

    table = Table(title=f"Knowledge Base Topics ({len(topic_dicts)})")
    table.add_column("Slug", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Category")
    table.add_column("Trend")
    table.add_column("Status")
    table.add_column("Mentions", justify="right")
    table.add_column("Relevance", justify="right")

    for t in topic_dicts:
        table.add_row(
            t["slug"],
            t["name"],
            t["category"] or "",
            t["trend"] or "",
            t["status"],
            str(t["mention_count"]),
            f"{t['relevance_score']:.2f}",
        )

    console.print(table)


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------


@app.command("show")
def show_topic(
    slug: Annotated[str, typer.Argument(help="Topic slug.")],
) -> None:
    """Show a topic's compiled article and metadata."""
    console = Console()

    if _route_to_api():
        import httpx

        try:
            with _api_client() as client:
                topic_dict = client.kb_get_topic(slug)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                if is_json_mode():
                    output_result({"error": f"Topic not found: {slug}"}, success=False)
                else:
                    console.print(f"[red]Topic not found:[/red] {slug}")
                raise typer.Exit(1) from exc
            raise
    else:
        guard_remote_backend("kb show")
        from src.models.topic import Topic

        with _get_db() as db:
            topic = db.query(Topic).filter_by(slug=slug).first()
            if topic is None:
                if is_json_mode():
                    output_result({"error": f"Topic not found: {slug}"}, success=False)
                else:
                    console.print(f"[red]Topic not found:[/red] {slug}")
                raise typer.Exit(1)

            topic_dict = {
                "slug": topic.slug,
                "name": topic.name,
                "category": topic.category,
                "status": str(topic.status),
                "trend": topic.trend,
                "summary": topic.summary,
                "article_md": topic.article_md,
                "article_version": topic.article_version,
                "relevance_score": topic.relevance_score,
                "novelty_score": topic.novelty_score,
                "mention_count": topic.mention_count,
                "source_content_ids": topic.source_content_ids,
                "related_topic_ids": topic.related_topic_ids,
                "last_compiled_at": (
                    topic.last_compiled_at.isoformat() if topic.last_compiled_at else None
                ),
                "compilation_model": topic.compilation_model,
            }

    if is_json_mode():
        output_result(topic_dict)
        return

    console.print(f"\n[bold cyan]{topic_dict['name']}[/bold cyan]")
    console.print(f"  slug: {topic_dict['slug']}")
    console.print(f"  status: {topic_dict['status']}")
    console.print(f"  category: {topic_dict['category']}")
    console.print(f"  trend: {topic_dict['trend']}")
    console.print(f"  version: {topic_dict['article_version']}")
    console.print(
        f"  scores: relevance={topic_dict['relevance_score']:.2f}, "
        f"novelty={topic_dict['novelty_score']:.2f}, "
        f"mentions={topic_dict['mention_count']}"
    )
    console.print()
    if topic_dict["article_md"]:
        console.print(topic_dict["article_md"])
    else:
        console.print("[yellow](no compiled article yet)[/yellow]")


# ---------------------------------------------------------------------------
# index
# ---------------------------------------------------------------------------


@app.command("index")
def show_index(
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Show category-specific index."),
    ] = None,
) -> None:
    """Show the master KB index (or a category index)."""
    console = Console()

    index_type = f"category_{category}" if category else "master"

    if _route_to_api():
        with _api_client() as client:
            data = client.kb_index(category)
        content = data.get("content") or ""
        if not content:
            if is_json_mode():
                output_result(
                    {
                        "index_type": data.get("index_type", index_type),
                        "content": "",
                        "exists": False,
                    }
                )
            else:
                console.print(
                    f"[yellow]No index found for type:[/yellow] {data.get('index_type', index_type)}\n"
                    "Run [bold]aca kb compile[/bold] first."
                )
            return
        result = {
            "index_type": data.get("index_type", index_type),
            "content": content,
            "generated_at": data.get("generated_at"),
            "exists": True,
        }
    else:
        guard_remote_backend("kb index")
        from src.models.topic import KBIndex

        with _get_db() as db:
            index = db.query(KBIndex).filter_by(index_type=index_type).first()
            if index is None:
                if is_json_mode():
                    output_result({"index_type": index_type, "content": "", "exists": False})
                else:
                    console.print(
                        f"[yellow]No index found for type:[/yellow] {index_type}\n"
                        "Run [bold]aca kb compile[/bold] first."
                    )
                return

            result = {
                "index_type": index.index_type,
                "content": index.content,
                "generated_at": index.generated_at.isoformat(),
                "exists": True,
            }

    if is_json_mode():
        output_result(result)
    else:
        console.print(result["content"])


# ---------------------------------------------------------------------------
# query (Q&A)
# ---------------------------------------------------------------------------


@app.command("query")
def query_kb(
    question: Annotated[str, typer.Argument(help="Question to answer.")],
    file_back: Annotated[
        bool,
        typer.Option(
            "--file-back",
            help="File the answer as a TopicNote on each referenced topic.",
        ),
    ] = False,
) -> None:
    """Answer a question against the compiled KB."""
    console = Console()

    async def _run() -> dict:
        from src.services.kb_qa import KBQAService

        with _get_db() as db:
            service = KBQAService(db)
            return await service.query(question, file_back=file_back)

    try:
        if _route_to_api():
            with _api_client() as client:
                result = client.kb_query(question, file_back=file_back)
        else:
            guard_remote_backend("kb query")
            result = asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as exc:
        if is_json_mode():
            output_result({"error": str(exc)}, success=False)
        else:
            console.print(f"[red]Q&A failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    if is_json_mode():
        output_result(result)
        return

    answer = result.get("answer") or ""
    if not answer:
        console.print(
            "[yellow]No relevant KB content for this question.[/yellow]\n"
            "Try [bold]aca search[/bold] to query raw content instead."
        )
        return

    console.print(f"\n[bold cyan]Answer:[/bold cyan]\n{answer}\n")
    refs = result.get("topics") or []
    if refs:
        console.print(f"[dim]Referenced topics:[/dim] {', '.join(refs)}")
    if result.get("truncated"):
        console.print("[dim](additional topics omitted from context)[/dim]")


# ---------------------------------------------------------------------------
# lint
# ---------------------------------------------------------------------------


@app.command("lint")
def lint_kb(
    fix: Annotated[
        bool,
        typer.Option(
            "--fix",
            help="Apply automatic fixes (e.g., mark stale topics as stale).",
        ),
    ] = False,
) -> None:
    """Run KB health checks and emit a markdown report."""
    guard_remote_backend("kb lint")
    from src.services.kb_health import KBHealthService

    console = Console()

    with _get_db() as db:
        service = KBHealthService(db)
        result = service.lint_fix() if fix else service.lint()

    if is_json_mode():
        output_result(result)
        return

    if "report_md" in result:
        console.print(result["report_md"])
    if fix and "fixed_count" in result:
        console.print(f"\n[green]Fixed:[/green] {result['fixed_count']} topics")
