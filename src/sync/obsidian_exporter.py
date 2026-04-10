"""Obsidian vault exporter for the newsletter aggregator knowledge base.

Exports digests, summaries, insights, content stubs, Neo4j entities,
and theme MOCs as Obsidian-compatible markdown files with YAML frontmatter,
wikilinks, and incremental manifest-based sync.

Design decisions:
- D3: Reuses existing generate_digest_markdown() / generate_summary_markdown()
- D4: Neo4j entities queried via bolt driver directly
- D8: Vault path validated for safety (symlinks, traversal)
- D9: Atomic manifest writes via SyncManifest
- D11: Streaming DB queries with yield_per(500)
"""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine

from src.sync.obsidian_frontmatter import (
    build_frontmatter,
    compute_content_hash,
    slugify_filename,
)
from src.sync.obsidian_manifest import SyncManifest

logger = logging.getLogger(__name__)

_STREAM_BATCH_SIZE = 500


def _safe_segment(value: str) -> str:
    """Sanitize a single path segment for the vault.

    Strips separators and traversal characters; falls back to ``unknown``
    if nothing safe remains.
    """
    if not value:
        return "unknown"
    cleaned = value.strip()
    for ch in ("/", "\\", "..", "\n", "\r", "\0"):
        cleaned = cleaned.replace(ch, "")
    return cleaned or "unknown"


@dataclass
class ContentTypeStats:
    """Export statistics for a single content type."""

    created: int = 0
    updated: int = 0
    skipped: int = 0


@dataclass
class ExportSummary:
    """Summary of an Obsidian vault export run."""

    digests: ContentTypeStats = field(default_factory=ContentTypeStats)
    summaries: ContentTypeStats = field(default_factory=ContentTypeStats)
    insights: ContentTypeStats = field(default_factory=ContentTypeStats)
    content_stubs: ContentTypeStats = field(default_factory=ContentTypeStats)
    entities: ContentTypeStats = field(default_factory=ContentTypeStats)
    themes: ContentTypeStats = field(default_factory=ContentTypeStats)
    topics: ContentTypeStats = field(default_factory=ContentTypeStats)
    cleaned: int = 0
    elapsed_seconds: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result: dict[str, Any] = {}
        for name in (
            "digests",
            "summaries",
            "insights",
            "content_stubs",
            "entities",
            "themes",
            "topics",
        ):
            stats: ContentTypeStats = getattr(self, name)
            result[name] = {
                "created": stats.created,
                "updated": stats.updated,
                "skipped": stats.skipped,
            }
        if self.cleaned > 0:
            result["cleaned"] = self.cleaned
        result["elapsed_seconds"] = round(self.elapsed_seconds, 2)
        if self.warnings:
            result["warnings"] = self.warnings
        return result


@dataclass
class ExportOptions:
    """Options controlling what gets exported."""

    since: datetime | None = None
    include_entities: bool = True
    include_themes: bool = True
    include_topics: bool = True
    clean: bool = False
    dry_run: bool = False
    max_entities: int = 10000


def validate_vault_path(vault_path: str | Path) -> Path:
    """Validate and resolve vault path for safety.

    Rejects symlinks pointing outside the user home tree and
    paths containing traversal segments after resolution.

    Args:
        vault_path: User-provided vault path.

    Returns:
        Resolved absolute Path.

    Raises:
        ValueError: If path is unsafe.
    """
    path = Path(vault_path).resolve()

    # Check for symlink to outside user's home
    raw = Path(vault_path).expanduser()
    if raw.is_symlink():
        target = raw.resolve()
        home = Path.home()
        if not target.is_relative_to(home):
            raise ValueError(
                f"Vault path is a symlink pointing outside home directory: {raw} -> {target}"
            )

    # Check the original string for traversal (before resolution flattens it)
    original = str(vault_path)
    if ".." in original.split("/") or ".." in original.split("\\"):
        raise ValueError(f"Vault path contains directory traversal segments: {vault_path}")

    return path


class ObsidianExporter:
    """Export the newsletter aggregator knowledge base as an Obsidian vault.

    Args:
        engine: SQLAlchemy Engine for PostgreSQL queries.
        neo4j_driver: Optional Neo4j driver for entity export.
        vault_path: Resolved vault directory path.
        options: Export filtering and behavior options.
    """

    def __init__(
        self,
        engine: Engine,
        vault_path: Path,
        *,
        neo4j_driver: Any | None = None,
        options: ExportOptions | None = None,
    ) -> None:
        self._engine = engine
        self._vault_path = vault_path
        self._neo4j_driver = neo4j_driver
        self._options = options or ExportOptions()
        self._manifest = SyncManifest.load(vault_path)
        # Collect all tags across export for MOC generation
        self._all_tags: dict[str, list[tuple[str, str]]] = {}  # tag -> [(filename, aca_type)]
        # Track filenames for wikilink resolution
        self._id_to_filename: dict[str, str] = {}

    def export_all(self) -> ExportSummary:
        """Run the full export pipeline.

        Returns:
            ExportSummary with counts per content type.
        """
        start = time.monotonic()
        summary = ExportSummary()

        # Ensure vault directory exists
        self._vault_path.mkdir(parents=True, exist_ok=True)

        # Phase 1: Export content from PostgreSQL
        summary.digests = self.export_digests()
        summary.summaries = self.export_summaries()
        summary.insights = self.export_insights()
        summary.content_stubs = self.export_content_stubs()

        # Phase 2: Export entities from Neo4j (graceful fallback)
        if self._options.include_entities:
            try:
                summary.entities = self.export_entities()
            except Exception as exc:
                msg = f"WARNING: Neo4j unavailable; entity export skipped ({exc})"
                print(msg, file=sys.stderr)
                summary.warnings.append(msg)
        else:
            logger.debug("Entity export skipped (--no-entities)")

        # Phase 3: Generate theme MOCs
        if self._options.include_themes:
            summary.themes = self.export_theme_mocs()
        else:
            logger.debug("Theme MOC generation skipped (--no-themes)")

        # Phase 3.5: Export KB topics (3-tier vault structure)
        if self._options.include_topics:
            try:
                summary.topics = self.export_topics()
            except Exception as exc:
                msg = f"WARNING: Topic export failed ({exc})"
                logger.warning(msg, exc_info=True)
                summary.warnings.append(msg)
        else:
            logger.debug("Topic export skipped (--no-topics)")

        # Phase 4: Handle cleanup if requested
        if self._options.clean:
            self._cleanup_stale_files(summary)

        # Save manifest
        if not self._options.dry_run:
            self._manifest.save()

        summary.elapsed_seconds = time.monotonic() - start

        logger.info(
            "Obsidian export complete: %.1fs elapsed",
            summary.elapsed_seconds,
        )

        return summary

    def export_digests(self) -> ContentTypeStats:
        """Export digests as Obsidian markdown files."""
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        from src.models.digest import Digest, DigestStatus
        from src.utils.digest_markdown import generate_digest_markdown

        stats = ContentTypeStats()
        folder = "Digests"

        with Session(self._engine) as session:
            stmt = (
                select(Digest)
                .where(
                    Digest.status.in_(
                        [
                            DigestStatus.COMPLETED,
                            DigestStatus.APPROVED,
                            DigestStatus.DELIVERED,
                            DigestStatus.PENDING_REVIEW,
                        ]
                    )
                )
                .order_by(Digest.period_start.desc())
            )

            if self._options.since:
                stmt = stmt.where(Digest.period_start >= self._options.since)

            for digest in session.execute(stmt).scalars().yield_per(_STREAM_BATCH_SIZE):
                try:
                    aca_id = f"digest-{digest.id}"
                    tags = digest.theme_tags or []
                    date = digest.period_start

                    # Generate markdown body
                    if digest.markdown_content:
                        body = digest.markdown_content
                    else:
                        digest_data = {
                            "title": digest.title,
                            "executive_overview": digest.executive_overview,
                            "strategic_insights": digest.strategic_insights,
                            "technical_developments": digest.technical_developments,
                            "emerging_trends": digest.emerging_trends,
                            "actionable_recommendations": digest.actionable_recommendations,
                            "sources": digest.sources,
                            "historical_context": digest.historical_context,
                        }
                        body = generate_digest_markdown(digest_data)

                    # Build related section
                    related = self._build_related_section(digest.source_content_ids or [])

                    # Build frontmatter with placeholder hash
                    fm = build_frontmatter(
                        aca_id=aca_id,
                        aca_type="digest",
                        date=date,
                        tags=tags,
                        content_hash="PLACEHOLDER",
                        digest_type=str(digest.digest_type),
                        period_start=digest.period_start.isoformat() if digest.period_start else "",
                        period_end=digest.period_end.isoformat() if digest.period_end else "",
                    )

                    full_content = fm + body
                    if related:
                        full_content += "\n" + related

                    content_hash = compute_content_hash(full_content)
                    full_content = full_content.replace(
                        '"PLACEHOLDER"',
                        f'"{content_hash}"',
                        1,
                    )

                    result = self._write_note(
                        folder,
                        aca_id,
                        "digest",
                        date,
                        digest.title,
                        full_content,
                        content_hash,
                        tags,
                    )
                    if result == "created":
                        stats.created += 1
                    elif result == "updated":
                        stats.updated += 1
                    else:
                        stats.skipped += 1
                except Exception:
                    logger.warning("Failed to export digest %s", digest.id, exc_info=True)

        return stats

    def export_summaries(self) -> ContentTypeStats:
        """Export summaries as Obsidian markdown files."""
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        from src.models.content import Content
        from src.models.summary import Summary
        from src.utils.summary_markdown import generate_summary_markdown

        stats = ContentTypeStats()
        folder = "Summaries"

        with Session(self._engine) as session:
            stmt = select(Summary).order_by(Summary.created_at.desc())

            if self._options.since:
                stmt = stmt.where(Summary.created_at >= self._options.since)

            for summary in session.execute(stmt).scalars().yield_per(_STREAM_BATCH_SIZE):
                try:
                    aca_id = f"summary-{summary.id}"
                    tags = summary.theme_tags or summary.key_themes or []
                    date = summary.created_at

                    # Get source content info
                    source_type = ""
                    source_url = ""
                    title = f"Summary {summary.id}"
                    content_id = summary.content_id

                    if content_id:
                        content = session.get(Content, content_id)
                        if content:
                            source_type = str(content.source_type) if content.source_type else ""
                            source_url = content.source_url or ""
                            title = content.title or title

                    # Generate markdown body
                    if summary.markdown_content:
                        body = summary.markdown_content
                    else:
                        summary_data = {
                            "executive_summary": summary.executive_summary,
                            "key_themes": summary.key_themes,
                            "strategic_insights": summary.strategic_insights,
                            "technical_details": summary.technical_details,
                            "actionable_items": summary.actionable_items,
                            "notable_quotes": summary.notable_quotes,
                            "relevant_links": summary.relevant_links,
                            "relevance_scores": summary.relevance_scores,
                        }
                        body = generate_summary_markdown(summary_data)

                    # Build related section from content references
                    related = ""
                    if content_id:
                        related = self._build_related_section_for_content(content_id, session)

                    fm = build_frontmatter(
                        aca_id=aca_id,
                        aca_type="summary",
                        date=date,
                        tags=tags,
                        content_hash="PLACEHOLDER",
                        source_type=source_type,
                        source_url=source_url,
                    )

                    full_content = fm + body
                    if related:
                        full_content += "\n" + related

                    content_hash = compute_content_hash(full_content)
                    full_content = full_content.replace(
                        '"PLACEHOLDER"',
                        f'"{content_hash}"',
                        1,
                    )

                    result = self._write_note(
                        folder, aca_id, "summary", date, title, full_content, content_hash, tags
                    )
                    if result == "created":
                        stats.created += 1
                    elif result == "updated":
                        stats.updated += 1
                    else:
                        stats.skipped += 1
                except Exception:
                    logger.warning("Failed to export summary %s", summary.id, exc_info=True)

        return stats

    def export_insights(self) -> ContentTypeStats:
        """Export agent insights as Obsidian markdown files."""
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        from src.models.agent_insight import AgentInsight

        stats = ContentTypeStats()
        folder = "Insights"

        with Session(self._engine) as session:
            stmt = select(AgentInsight).order_by(AgentInsight.created_at.desc())

            if self._options.since:
                stmt = stmt.where(AgentInsight.created_at >= self._options.since)

            for insight in session.execute(stmt).scalars().yield_per(_STREAM_BATCH_SIZE):
                try:
                    aca_id = f"insight-{insight.id}"
                    tags = insight.tags or []
                    date = insight.created_at

                    body = f"# {insight.title}\n\n"
                    body += f"**Type**: {insight.insight_type}\n"
                    body += f"**Confidence**: {insight.confidence:.0%}\n\n"
                    body += insight.content or ""

                    fm = build_frontmatter(
                        aca_id=aca_id,
                        aca_type="insight",
                        date=date,
                        tags=tags,
                        content_hash="PLACEHOLDER",
                        insight_type=str(insight.insight_type),
                        confidence=insight.confidence,
                    )

                    full_content = fm + body
                    content_hash = compute_content_hash(full_content)
                    full_content = full_content.replace(
                        '"PLACEHOLDER"',
                        f'"{content_hash}"',
                        1,
                    )

                    result = self._write_note(
                        folder,
                        aca_id,
                        "insight",
                        date,
                        insight.title,
                        full_content,
                        content_hash,
                        tags,
                    )
                    if result == "created":
                        stats.created += 1
                    elif result == "updated":
                        stats.updated += 1
                    else:
                        stats.skipped += 1
                except Exception:
                    logger.warning("Failed to export insight %s", insight.id, exc_info=True)

        return stats

    def export_content_stubs(self) -> ContentTypeStats:
        """Export minimal content stubs for graph connectivity."""
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        from src.models.content import Content, ContentStatus
        from src.models.content_reference import ContentReference

        stats = ContentTypeStats()
        folder = "Content"

        with Session(self._engine) as session:
            stmt = (
                select(Content)
                .where(
                    Content.status == ContentStatus.COMPLETED,
                )
                .order_by(Content.published_date.desc().nullslast())
            )

            if self._options.since:
                stmt = stmt.where(Content.published_date >= self._options.since)

            for content in session.execute(stmt).scalars().yield_per(_STREAM_BATCH_SIZE):
                try:
                    aca_id = f"content-{content.id}"
                    tags = []
                    date = content.published_date or content.created_at
                    title = content.title or f"Content {content.id}"

                    # Build stub body
                    body = f"# {title}\n\n"
                    if content.source_url:
                        body += f"**Source**: [{content.source_url}]({content.source_url})\n"
                    if content.author:
                        body += f"**Author**: {content.author}\n"
                    if content.publication:
                        body += f"**Publication**: {content.publication}\n"
                    body += "\n"

                    # Find summaries that reference this content (reverse refs)
                    refs = (
                        session.execute(
                            select(ContentReference).where(
                                ContentReference.target_content_id == content.id,
                            )
                        )
                        .scalars()
                        .all()
                    )

                    if refs:
                        body += "## Referenced By\n\n"
                        for ref in refs:
                            src_id = f"content-{ref.source_content_id}"
                            src_filename = self._id_to_filename.get(src_id, "")
                            if src_filename:
                                link_name = Path(src_filename).stem
                                body += f"- [[{link_name}]]\n"

                    fm = build_frontmatter(
                        aca_id=aca_id,
                        aca_type="content_stub",
                        date=date,
                        tags=tags,
                        content_hash="PLACEHOLDER",
                        source_type=str(content.source_type) if content.source_type else "",
                        source_url=content.source_url or "",
                        author=content.author or "",
                        publication=content.publication or "",
                    )

                    full_content = fm + body
                    content_hash = compute_content_hash(full_content)
                    full_content = full_content.replace(
                        '"PLACEHOLDER"',
                        f'"{content_hash}"',
                        1,
                    )

                    result = self._write_note(
                        folder,
                        aca_id,
                        "content_stub",
                        date,
                        title,
                        full_content,
                        content_hash,
                        tags,
                    )
                    if result == "created":
                        stats.created += 1
                    elif result == "updated":
                        stats.updated += 1
                    else:
                        stats.skipped += 1
                except Exception:
                    logger.warning("Failed to export content stub %s", content.id, exc_info=True)

        return stats

    def export_entities(self) -> ContentTypeStats:
        """Export Neo4j entities as Obsidian notes."""
        if self._neo4j_driver is None:
            raise RuntimeError("Neo4j driver not configured")

        stats = ContentTypeStats()
        folder = "Entities"
        limit = self._options.max_entities

        with self._neo4j_driver.session() as neo_session:
            # Query entities with parameterized LIMIT
            result = neo_session.run(
                "MATCH (e:Entity) RETURN e.uuid AS uuid, e.name AS name, "
                "e.entity_type AS entity_type, e.summary AS summary "
                "LIMIT $limit",
                limit=limit,
            )

            for record in result:
                try:
                    uuid = record["uuid"] or ""
                    name = record["name"] or "Unknown"
                    entity_type = record["entity_type"] or ""
                    entity_summary = record["summary"] or ""
                    aca_id = f"entity-{uuid}"

                    # Query relationships for this entity
                    rel_result = neo_session.run(
                        "MATCH (e:Entity {uuid: $uuid})-[r]-(other:Entity) "
                        "RETURN type(r) AS rel_type, other.name AS other_name "
                        "LIMIT 100",
                        uuid=uuid,
                    )
                    relationships = list(rel_result)

                    # Build body
                    body = f"# {name}\n\n"
                    if entity_type:
                        body += f"**Type**: {entity_type}\n\n"

                    if entity_summary:
                        body += "## Facts\n\n"
                        body += f"{entity_summary}\n\n"

                    if relationships:
                        body += "## Relationships\n\n"
                        for rel in relationships:
                            other = rel["other_name"] or "Unknown"
                            rel_type = rel["rel_type"] or "RELATED_TO"
                            body += f"- {rel_type}: [[{other}]]\n"

                    fm = build_frontmatter(
                        aca_id=aca_id,
                        aca_type="entity",
                        tags=[entity_type] if entity_type else [],
                        content_hash="PLACEHOLDER",
                        entity_type=entity_type,
                    )

                    full_content = fm + body
                    content_hash = compute_content_hash(full_content)
                    full_content = full_content.replace(
                        '"PLACEHOLDER"',
                        f'"{content_hash}"',
                        1,
                    )

                    result_action = self._write_note(
                        folder,
                        aca_id,
                        "entity",
                        None,
                        name,
                        full_content,
                        content_hash,
                        [],
                    )
                    if result_action == "created":
                        stats.created += 1
                    elif result_action == "updated":
                        stats.updated += 1
                    else:
                        stats.skipped += 1
                except Exception:
                    logger.warning(
                        "Failed to export entity %s", record.get("uuid", "?"), exc_info=True
                    )

        return stats

    def export_theme_mocs(self) -> ContentTypeStats:
        """Generate Map of Content files per theme tag."""
        stats = ContentTypeStats()
        folder = "Themes"

        if not self._all_tags:
            return stats

        for theme, notes in self._all_tags.items():
            aca_id = f"moc-{theme.lower().replace(' ', '-')}"
            title = f"MOC - {theme}"

            # Group by content type
            by_type: dict[str, list[str]] = {}
            for filename, aca_type in notes:
                type_label = aca_type.replace("_", " ").title() + "s"
                by_type.setdefault(type_label, []).append(filename)

            body = f"# {title}\n\n"
            for type_label in sorted(by_type.keys()):
                body += f"## {type_label}\n\n"
                for filename in sorted(by_type[type_label]):
                    link_name = Path(filename).stem
                    body += f"- [[{link_name}]]\n"
                body += "\n"

            fm = build_frontmatter(
                aca_id=aca_id,
                aca_type="moc",
                tags=[theme],
                content_hash="PLACEHOLDER",
                theme=theme,
                note_count=len(notes),
            )

            full_content = fm + body
            content_hash = compute_content_hash(full_content)
            full_content = full_content.replace(
                '"PLACEHOLDER"',
                f'"{content_hash}"',
                1,
            )

            result = self._write_note(
                folder, aca_id, "moc", None, title, full_content, content_hash, []
            )
            if result == "created":
                stats.created += 1
            elif result == "updated":
                stats.updated += 1
            else:
                stats.skipped += 1

        return stats

    def export_topics(self) -> ContentTypeStats:
        """Export KB topics in the 3-tier ``Category/Topic/_overview.md`` structure.

        Each active topic produces:
        - ``<Category>/<Topic>/_overview.md`` — frontmatter + compiled article
        - ``<Category>/<Topic>/<Source>/<date>-<slug>.md`` — source extract stubs

        Topics are tracked in the manifest by ``aca_id = topic-<slug>`` so
        re-exports respect ``article_version`` for incremental sync.
        """
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        from src.models.content import Content
        from src.models.topic import Topic, TopicStatus

        stats = ContentTypeStats()

        with Session(self._engine) as session:
            stmt = (
                select(Topic)
                .where(Topic.status == TopicStatus.ACTIVE)
                .order_by(Topic.relevance_score.desc().nullslast())
            )

            for topic in session.execute(stmt).scalars().yield_per(_STREAM_BATCH_SIZE):
                try:
                    aca_id = f"topic-{topic.slug}"
                    category_dir = _safe_segment(topic.category or "uncategorized")
                    topic_dir = _safe_segment(topic.slug)
                    rel_path = f"{category_dir}/{topic_dir}/_overview.md"

                    body = self._render_topic_body(topic)
                    fm = build_frontmatter(
                        aca_id=aca_id,
                        aca_type="topic",
                        date=topic.last_compiled_at,
                        tags=[topic.category] if topic.category else [],
                        content_hash="PLACEHOLDER",
                        slug=topic.slug,
                        category=topic.category or "",
                        trend=topic.trend or "",
                        article_version=int(topic.article_version or 1),
                        relevance_score=float(topic.relevance_score or 0.0),
                        mention_count=int(topic.mention_count or 0),
                    )
                    full_content = fm + body

                    content_hash = compute_content_hash(full_content)
                    full_content = full_content.replace(
                        '"PLACEHOLDER"',
                        f'"{content_hash}"',
                        1,
                    )

                    action = self._write_topic_file(
                        rel_path, aca_id, "topic", content_hash, full_content
                    )
                    if action == "created":
                        stats.created += 1
                    elif action == "updated":
                        stats.updated += 1
                    else:
                        stats.skipped += 1

                    # Source extracts (one per content_id)
                    for cid in topic.source_content_ids or []:
                        try:
                            content = session.get(Content, cid)
                            if content is None:
                                continue
                            self._export_topic_source_extract(
                                topic, content, category_dir, topic_dir
                            )
                        except Exception:
                            logger.warning(
                                "Topic source extract failed: topic=%s content=%s",
                                topic.slug,
                                cid,
                                exc_info=True,
                            )

                except Exception:
                    logger.warning("Failed to export topic %s", topic.slug, exc_info=True)

            # Generate category index files at each category folder
            self._generate_topic_category_indices(session)

        return stats

    def _render_topic_body(self, topic: Any) -> str:
        """Render the markdown body of a topic _overview.md file."""
        lines = [f"# {topic.name}", ""]

        if topic.summary:
            lines.append(topic.summary.strip())
            lines.append("")

        if topic.article_md:
            lines.append(topic.article_md.strip())
            lines.append("")
        else:
            lines.append("_(no compiled article yet)_")
            lines.append("")

        if topic.related_topic_ids:
            lines.append("## Related Topics")
            lines.append("")
            from sqlalchemy.orm import Session

            from src.models.topic import Topic as TopicModel

            with Session(self._engine) as session:
                related = (
                    session.query(TopicModel)
                    .filter(TopicModel.id.in_(topic.related_topic_ids))
                    .all()
                )
                for r in related:
                    cat_dir = _safe_segment(r.category or "uncategorized")
                    slug_dir = _safe_segment(r.slug)
                    lines.append(f"- [[../../{cat_dir}/{slug_dir}/_overview|{r.name}]]")
            lines.append("")

        return "\n".join(lines) + "\n"

    def _export_topic_source_extract(
        self,
        topic: Any,
        content: Any,
        category_dir: str,
        topic_dir: str,
    ) -> None:
        """Write a source extract stub linking the topic to a source content."""
        source_label = _safe_segment(str(content.source_type) if content.source_type else "Source")
        date_prefix = (
            content.published_date.strftime("%Y-%m-%d") if content.published_date else "undated"
        )
        slug = slugify_filename(
            content.title or f"content-{content.id}",
            content.published_date,
            "content_stub",
        )
        rel_path = f"{category_dir}/{topic_dir}/{source_label}/{date_prefix}-{slug}"

        body = (
            f"# {content.title or f'Content {content.id}'}\n\n"
            f"**Topic**: [[../_overview|{topic.name}]]\n"
            f"**Source**: {content.source_url or ''}\n\n"
            f"See [[../../../../Summaries/summary-{content.id}]] for the full summary.\n"
        )

        aca_id = f"topic-{topic.slug}-source-{content.id}"
        fm = build_frontmatter(
            aca_id=aca_id,
            aca_type="topic_source",
            date=content.published_date,
            tags=[],
            content_hash="PLACEHOLDER",
            topic_slug=topic.slug,
            content_id=int(content.id),
        )
        full_content = fm + body
        content_hash = compute_content_hash(full_content)
        full_content = full_content.replace(
            '"PLACEHOLDER"',
            f'"{content_hash}"',
            1,
        )

        self._write_topic_file(rel_path, aca_id, "topic_source", content_hash, full_content)

    def _generate_topic_category_indices(self, session: Any) -> None:
        """Write a per-category ``_index.md`` listing topics in that category."""
        from src.models.topic import Topic as TopicModel, TopicStatus

        topics = session.query(TopicModel).filter(TopicModel.status == TopicStatus.ACTIVE).all()
        by_category: dict[str, list[Any]] = {}
        for t in topics:
            by_category.setdefault(t.category or "uncategorized", []).append(t)

        for category, items in by_category.items():
            category_dir = _safe_segment(category)
            rel_path = f"{category_dir}/_index.md"
            lines = [f"# {category}", ""]
            for t in sorted(items, key=lambda x: x.relevance_score or 0.0, reverse=True):
                slug_dir = _safe_segment(t.slug)
                lines.append(f"- [[{slug_dir}/_overview|{t.name}]]")
            body = "\n".join(lines) + "\n"

            aca_id = f"topic-category-index-{category}"
            fm = build_frontmatter(
                aca_id=aca_id,
                aca_type="topic_category_index",
                tags=[],
                content_hash="PLACEHOLDER",
                category=category,
            )
            full_content = fm + body
            content_hash = compute_content_hash(full_content)
            full_content = full_content.replace(
                '"PLACEHOLDER"',
                f'"{content_hash}"',
                1,
            )

            self._write_topic_file(
                rel_path, aca_id, "topic_category_index", content_hash, full_content
            )

    def _write_topic_file(
        self,
        rel_path: str,
        aca_id: str,
        aca_type: str,
        content_hash: str,
        content: str,
    ) -> str:
        """Write a topic file to the vault.

        Unlike ``_write_note()``, this preserves the caller-supplied path
        (needed for the 3-tier ``Category/Topic/_overview.md`` structure)
        and uses the manifest only for change detection.
        """
        # Track for wikilinks
        self._id_to_filename[aca_id] = rel_path

        if not self._manifest.needs_update(aca_id, content_hash):
            self._manifest.mark_current(aca_id)
            return "skipped"

        is_new = aca_id not in self._manifest.entries
        action = "created" if is_new else "updated"

        if self._options.dry_run:
            self._manifest.mark_current(aca_id)
            return action

        file_path = self._vault_path / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

        self._manifest.record(aca_id, rel_path, aca_type, content_hash)
        return action

    # --- Helpers ---

    def _build_related_section(self, source_content_ids: list[int]) -> str:
        """Build a Related section from source content IDs.

        Used by digests which track source_content_ids directly.
        """
        if not source_content_ids:
            return ""

        lines = ["## Related\n"]
        for cid in source_content_ids:
            stub_id = f"content-{cid}"
            filename = self._id_to_filename.get(stub_id, "")
            if filename:
                link_name = Path(filename).stem
                lines.append(f"- Source: [[{link_name}]]")
            else:
                lines.append(f"- Source: [[content-{cid}]]")

        return "\n".join(lines) + "\n"

    def _build_related_section_for_content(self, content_id: int, session: Any) -> str:
        """Build a Related section from ContentReference entries for a content item."""
        from sqlalchemy import select

        from src.models.content import Content
        from src.models.content_reference import ContentReference

        refs = (
            session.execute(
                select(ContentReference).where(
                    ContentReference.source_content_id == content_id,
                )
            )
            .scalars()
            .all()
        )

        if not refs:
            return ""

        type_labels = {
            "cites": "Cites",
            "extends": "Extends",
            "discusses": "Discusses",
            "contradicts": "Contradicts",
            "supplements": "Supplements",
        }

        lines = ["## Related\n"]

        for ref in refs:
            label = type_labels.get(ref.reference_type, ref.reference_type.title())

            if ref.resolution_status == "external" and ref.external_url:
                title = ref.context_snippet or ref.external_url
                lines.append(f"- {label}: [{title}]({ref.external_url})")
            elif ref.target_content_id:
                target_id = f"content-{ref.target_content_id}"
                filename = self._id_to_filename.get(target_id, "")
                if filename:
                    link_name = Path(filename).stem
                    lines.append(f"- {label}: [[{link_name}]]")
                else:
                    # Forward link — may not exist yet
                    target = session.get(Content, ref.target_content_id)
                    if target and target.title:
                        slug = slugify_filename(target.title, target.published_date, "content_stub")
                        link_name = Path(slug).stem
                        lines.append(f"- {label}: [[{link_name}]]")
                    else:
                        lines.append(f"- {label}: [[content-{ref.target_content_id}]]")
            else:
                # Unresolved reference — use forward link
                if ref.external_url:
                    lines.append(f"- {label}: [{ref.external_url}]({ref.external_url})")
                else:
                    snippet = ref.context_snippet or "unknown"
                    lines.append(f"- {label}: [[{snippet}]]")

        return "\n".join(lines) + "\n"

    def _write_note(
        self,
        folder: str,
        aca_id: str,
        aca_type: str,
        date: Any,
        title: str,
        content: str,
        content_hash: str,
        tags: list[str],
    ) -> str:
        """Write a note to the vault, respecting manifest and dry-run.

        Returns:
            'created', 'updated', or 'skipped'.
        """
        # Check if we have a previously assigned filename
        existing_filename = self._manifest.get_filename(aca_id)

        if existing_filename:
            rel_path = existing_filename
        else:
            filename = slugify_filename(title, date, aca_type)
            rel_path = f"{folder}/{filename}"

            # Handle collision
            full_path = self._vault_path / rel_path
            counter = 2
            while full_path.exists() and aca_id not in (
                e.aca_id for e in self._manifest.entries.values() if e.filename == rel_path
            ):
                stem = Path(filename).stem
                rel_path = f"{folder}/{stem}-{counter}.md"
                full_path = self._vault_path / rel_path
                counter += 1

        # Track for wikilinks and MOCs
        self._id_to_filename[aca_id] = rel_path
        for tag in tags:
            if tag:
                self._all_tags.setdefault(tag, []).append((rel_path, aca_type))

        # Check if update needed
        if not self._manifest.needs_update(aca_id, content_hash):
            self._manifest.mark_current(aca_id)
            logger.debug("Skipped %s (unchanged)", aca_id)
            return "skipped"

        is_new = aca_id not in self._manifest.entries
        action = "created" if is_new else "updated"

        if self._options.dry_run:
            logger.debug("Would %s: %s -> %s", action[:-1] + "e", aca_id, rel_path)
            self._manifest.mark_current(aca_id)
            return action

        # Write file
        file_path = self._vault_path / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

        # Update manifest
        self._manifest.record(aca_id, rel_path, aca_type, content_hash)

        logger.debug(
            "%s %s -> %s (hash=%s)",
            action.title(),
            aca_id,
            rel_path,
            content_hash[:20],
        )

        return action

    def _cleanup_stale_files(self, summary: ExportSummary) -> None:
        """Remove managed files that no longer exist in the database."""
        stale = self._manifest.get_stale_entries()

        for entry in stale:
            file_path = self._vault_path / entry.filename

            if not file_path.exists():
                self._manifest.remove(entry.aca_id)
                continue

            # Verify it's a managed file
            try:
                content = file_path.read_text(encoding="utf-8")
                if "generator: aca" not in content[:500]:
                    continue  # Not managed by us
            except (OSError, UnicodeDecodeError):
                continue

            if self._options.dry_run:
                logger.info("Would delete stale: %s", entry.filename)
                summary.cleaned += 1
                continue

            file_path.unlink()
            self._manifest.remove(entry.aca_id)
            summary.cleaned += 1
            logger.info("Deleted stale file: %s", entry.filename)
