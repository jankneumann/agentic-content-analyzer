"""CLI commands for direct content editing.

Provides non-interactive edit capabilities for content, summaries,
digests, and podcast scripts. Complements the interactive review
workflow (aca review revise) with programmatic editing.

Usage:
    aca edit content <id> --title "New Title" --markdown @file.md
    aca edit summary <content-id> --executive-summary "New summary"
    aca edit digest <id> --title "New Title" --executive-overview "..."
    aca edit digest-section <id> <section> --feedback "Make it shorter"
    aca edit script-section <id> <index> --feedback "More engaging intro"
    aca edit script-section <id> <index> --dialogue @dialogue.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from src.cli.output import is_json_mode, output_result

app = typer.Typer(help="Edit content, summaries, digests, and scripts.")


def _read_value(value: str) -> str:
    """Read value from string or file (prefixed with @).

    Args:
        value: The value string. If starts with '@', reads from file.
               Use '@-' to read from stdin.

    Returns:
        The resolved value string.
    """
    if value.startswith("@"):
        path = value[1:]
        if path == "-":
            return sys.stdin.read()
        return Path(path).read_text()
    return value


# ---------------------------------------------------------------------------
# Content editing
# ---------------------------------------------------------------------------


@app.command("content")
def edit_content(
    content_id: Annotated[int, typer.Argument(help="Content item ID")],
    title: Annotated[str | None, typer.Option(help="New title")] = None,
    markdown: Annotated[
        str | None,
        typer.Option(help="New markdown body (use @file.md to read from file)"),
    ] = None,
    author: Annotated[str | None, typer.Option(help="New author")] = None,
    publication: Annotated[str | None, typer.Option(help="New publication")] = None,
    status: Annotated[str | None, typer.Option(help="New status")] = None,
) -> None:
    """Update fields on a content item."""
    from src.models.content import ContentStatus, ContentUpdate
    from src.services.content_service import ContentService
    from src.storage.database import get_db

    update_data: dict[str, Any] = {}
    if title is not None:
        update_data["title"] = title
    if markdown is not None:
        update_data["markdown_content"] = _read_value(markdown)
    if author is not None:
        update_data["author"] = author
    if publication is not None:
        update_data["publication"] = publication
    if status is not None:
        update_data["status"] = ContentStatus(status)

    if not update_data:
        typer.echo("No fields specified. Use --help to see options.", err=True)
        raise typer.Exit(1)

    with get_db() as db:
        service = ContentService(db)
        result = service.update(content_id, ContentUpdate(**update_data))
        if result is None:
            typer.echo(f"Content {content_id} not found.", err=True)
            raise typer.Exit(1)

    if is_json_mode():
        output_result(
            {
                "id": result.id,
                "title": result.title,
                "status": str(result.status),
                "updated_fields": list(update_data.keys()),
            }
        )
    else:
        typer.echo(f"Updated content {content_id}: {', '.join(update_data.keys())}")


# ---------------------------------------------------------------------------
# Summary editing
# ---------------------------------------------------------------------------


@app.command("summary")
def edit_summary(
    content_id: Annotated[int, typer.Argument(help="Content item ID")],
    executive_summary: Annotated[
        str | None,
        typer.Option("--executive-summary", help="New executive summary"),
    ] = None,
    key_themes: Annotated[
        str | None,
        typer.Option("--key-themes", help='JSON array of themes, e.g., \'["RAG","LLM"]\''),
    ] = None,
    strategic_insights: Annotated[
        str | None,
        typer.Option("--strategic-insights", help="JSON array of insights"),
    ] = None,
    technical_details: Annotated[
        str | None,
        typer.Option("--technical-details", help="JSON array of details"),
    ] = None,
    actionable_items: Annotated[
        str | None,
        typer.Option("--actionable-items", help="JSON array of items"),
    ] = None,
    markdown_content: Annotated[
        str | None,
        typer.Option("--markdown", help="New markdown (use @file.md)"),
    ] = None,
    feedback: Annotated[
        str | None,
        typer.Option("--feedback", help="Re-summarize with AI feedback"),
    ] = None,
) -> None:
    """Update a summary or re-summarize with AI feedback.

    Use --feedback to trigger AI re-summarization with guidance.
    Other flags perform direct field updates.
    """
    from src.models.summary import Summary
    from src.storage.database import get_db

    # AI-assisted re-summarization
    if feedback is not None:
        from src.models.content import Content, ContentStatus
        from src.processors.summarizer import ContentSummarizer

        with get_db() as db:
            content = db.query(Content).filter(Content.id == content_id).first()
            if not content:
                typer.echo(f"Content {content_id} not found.", err=True)
                raise typer.Exit(1)

            meta = content.metadata_json or {}
            meta["revision_feedback"] = feedback
            content.metadata_json = meta
            content.status = ContentStatus.PARSED
            db.query(Summary).filter(Summary.content_id == content_id).delete()
            db.commit()

        summarizer = ContentSummarizer()
        success = summarizer.summarize_content(content_id)
        if not success:
            typer.echo(f"Re-summarization failed for content {content_id}.", err=True)
            raise typer.Exit(1)

        if is_json_mode():
            with get_db() as db:
                s = db.query(Summary).filter(Summary.content_id == content_id).first()
                output_result(
                    {
                        "id": s.id if s else None,
                        "content_id": content_id,
                        "action": "re-summarized",
                        "feedback": feedback,
                    }
                )
        else:
            typer.echo(f"Re-summarized content {content_id} with feedback.")
        return

    # Direct field updates
    with get_db() as db:
        summary = db.query(Summary).filter(Summary.content_id == content_id).first()
        if not summary:
            typer.echo(f"No summary found for content {content_id}.", err=True)
            raise typer.Exit(1)

        updated: list[str] = []
        if executive_summary is not None:
            summary.executive_summary = _read_value(executive_summary)
            updated.append("executive_summary")
        if key_themes is not None:
            summary.key_themes = json.loads(key_themes)
            updated.append("key_themes")
        if strategic_insights is not None:
            summary.strategic_insights = json.loads(strategic_insights)
            updated.append("strategic_insights")
        if technical_details is not None:
            summary.technical_details = json.loads(technical_details)
            updated.append("technical_details")
        if actionable_items is not None:
            summary.actionable_items = json.loads(actionable_items)
            updated.append("actionable_items")
        if markdown_content is not None:
            summary.markdown_content = _read_value(markdown_content)
            updated.append("markdown_content")

        if not updated:
            typer.echo("No fields specified. Use --help to see options.", err=True)
            raise typer.Exit(1)

        db.commit()

    if is_json_mode():
        output_result({"content_id": content_id, "updated_fields": updated})
    else:
        typer.echo(f"Updated summary for content {content_id}: {', '.join(updated)}")


# ---------------------------------------------------------------------------
# Digest editing
# ---------------------------------------------------------------------------


@app.command("digest")
def edit_digest(
    digest_id: Annotated[int, typer.Argument(help="Digest ID")],
    title: Annotated[str | None, typer.Option(help="New title")] = None,
    executive_overview: Annotated[
        str | None,
        typer.Option("--executive-overview", help="New overview (use @file.md)"),
    ] = None,
    markdown: Annotated[
        str | None,
        typer.Option(help="New full markdown (use @file.md)"),
    ] = None,
) -> None:
    """Directly update digest fields."""
    from src.models.digest import Digest
    from src.storage.database import get_db

    with get_db() as db:
        digest = db.query(Digest).filter(Digest.id == digest_id).first()
        if not digest:
            typer.echo(f"Digest {digest_id} not found.", err=True)
            raise typer.Exit(1)

        updated: list[str] = []
        if title is not None:
            digest.title = title
            updated.append("title")
        if executive_overview is not None:
            digest.executive_overview = _read_value(executive_overview)
            updated.append("executive_overview")
        if markdown is not None:
            digest.markdown_content = _read_value(markdown)
            updated.append("markdown_content")

        if not updated:
            typer.echo("No fields specified. Use --help to see options.", err=True)
            raise typer.Exit(1)

        digest.revision_count += 1
        db.commit()

    if is_json_mode():
        output_result({"digest_id": digest_id, "updated_fields": updated})
    else:
        typer.echo(f"Updated digest {digest_id}: {', '.join(updated)}")


@app.command("digest-section")
def edit_digest_section(
    digest_id: Annotated[int, typer.Argument(help="Digest ID")],
    section: Annotated[
        str,
        typer.Argument(
            help="Section: title, executive_overview, strategic_insights, "
            "technical_developments, emerging_trends, actionable_recommendations"
        ),
    ],
    feedback: Annotated[
        str | None,
        typer.Option(help="AI revision feedback (natural language)"),
    ] = None,
    content: Annotated[
        str | None,
        typer.Option(
            help="Direct replacement content (JSON for list/dict sections, text for string)"
        ),
    ] = None,
) -> None:
    """Edit a digest section with direct replacement or AI-assisted revision.

    Use --feedback for AI revision, --content for direct replacement.
    """
    import asyncio

    if feedback and content:
        typer.echo("Specify either --feedback or --content, not both.", err=True)
        raise typer.Exit(1)

    if not feedback and not content:
        typer.echo("Specify --feedback or --content. Use --help for options.", err=True)
        raise typer.Exit(1)

    if content is not None:
        # Direct replacement
        from src.services.review_service import ReviewService

        service = ReviewService()
        value = _read_value(content)
        # Try JSON parse for structured sections
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = value

        try:
            asyncio.run(service.apply_revision(digest_id, section, parsed))
        except Exception as e:
            typer.echo(f"Failed: {e}", err=True)
            raise typer.Exit(1)

        if is_json_mode():
            output_result({"digest_id": digest_id, "section": section, "action": "replaced"})
        else:
            typer.echo(f"Updated {section} on digest {digest_id}.")
    else:
        # AI-assisted revision
        from src.services.review_service import ReviewService

        service = ReviewService()
        session_id = f"cli-edit-{digest_id}"

        try:
            ctx = asyncio.run(service.start_revision_session(digest_id, session_id, "cli-editor"))
            prompt = f"Please revise the '{section}' section. Feedback: {feedback}"
            result = asyncio.run(service.process_revision_turn(ctx, prompt, [], session_id))
            if result and result.get("revised_content"):
                asyncio.run(service.apply_revision(digest_id, section, result["revised_content"]))
        except Exception as e:
            typer.echo(f"Revision failed: {e}", err=True)
            raise typer.Exit(1)

        if is_json_mode():
            output_result(
                {
                    "digest_id": digest_id,
                    "section": section,
                    "action": "ai_revised",
                }
            )
        else:
            typer.echo(f"AI-revised {section} on digest {digest_id}.")


# ---------------------------------------------------------------------------
# Podcast script editing
# ---------------------------------------------------------------------------


@app.command("script-section")
def edit_script_section(
    script_id: Annotated[int, typer.Argument(help="Podcast script ID")],
    section_index: Annotated[int, typer.Argument(help="Section index (0-based)")],
    feedback: Annotated[
        str | None,
        typer.Option(help="AI revision feedback (natural language)"),
    ] = None,
    dialogue: Annotated[
        str | None,
        typer.Option(help="Direct dialogue replacement (JSON array, use @file.json)"),
    ] = None,
) -> None:
    """Edit a podcast script section with AI feedback or direct replacement.

    Use --feedback for AI revision, --dialogue for direct replacement.
    """
    import asyncio

    from src.models.podcast import DialogueTurn, ScriptRevisionRequest
    from src.services.script_review_service import ScriptReviewService

    if feedback and dialogue:
        typer.echo("Specify either --feedback or --dialogue, not both.", err=True)
        raise typer.Exit(1)

    if not feedback and not dialogue:
        typer.echo("Specify --feedback or --dialogue. Use --help for options.", err=True)
        raise typer.Exit(1)

    service = ScriptReviewService()

    if dialogue is not None:
        raw = _read_value(dialogue)
        turns = [DialogueTurn(**t) for t in json.loads(raw)]
        request = ScriptRevisionRequest(
            script_id=script_id,
            section_index=section_index,
            feedback="Direct replacement via CLI",
            replacement_dialogue=turns,
        )
    else:
        request = ScriptRevisionRequest(
            script_id=script_id,
            section_index=section_index,
            feedback=feedback,  # type: ignore[arg-type]
        )

    try:
        result = asyncio.run(service.revise_section(request))
    except Exception as e:
        typer.echo(f"Failed: {e}", err=True)
        raise typer.Exit(1)

    if is_json_mode():
        output_result(
            {
                "script_id": result.id,
                "section_index": section_index,
                "revision_count": result.revision_count,
                "action": "dialogue_replaced" if dialogue else "ai_revised",
            }
        )
    else:
        action = "replaced dialogue" if dialogue else "AI-revised"
        typer.echo(f"Section {section_index} of script {script_id}: {action}.")
