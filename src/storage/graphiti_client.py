"""Graphiti knowledge graph client for entity extraction and temporal tracking."""
# mypy: disable-error-code="no-any-return,no-untyped-def"

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from graphiti_core import Graphiti
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.anthropic_client import AnthropicClient, LLMConfig
from graphiti_core.nodes import EpisodeType

from src.config import settings
from src.models.content import Content
from src.models.summary import Summary
from src.storage.graph_provider import (
    GraphBackendUnavailableError,
    GraphDBProvider,
    get_graph_provider,
)
from src.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class GraphitiClient:
    """Client for managing content knowledge graph with Graphiti.

    Use the async factory method `create()` to construct instances:

        client = await GraphitiClient.create()
        # or with explicit provider:
        client = await GraphitiClient.create(provider=my_provider)
    """

    def __init__(
        self,
        provider: GraphDBProvider,
        graphiti: Graphiti,
    ) -> None:
        """Private constructor. Use GraphitiClient.create() instead."""
        self.provider = provider
        self.graphiti = graphiti

    @classmethod
    async def create(
        cls,
        provider: GraphDBProvider | None = None,
        anthropic_api_key: str = "",
        openai_api_key: str = "",
    ) -> GraphitiClient:
        """Async factory — constructs Graphiti with provider and runs index setup.

        Args:
            provider: Graph database provider (default: from settings via get_graph_provider())
            anthropic_api_key: Anthropic API key for LLM (default: from settings)
            openai_api_key: OpenAI API key for embeddings (default: from settings)

        Returns:
            Initialized GraphitiClient ready for use.

        Raises:
            GraphBackendUnavailableError: If the graph backend is unreachable.
        """
        provider = provider or get_graph_provider()

        # Verify backend is reachable
        if not await provider.health_check():
            raise GraphBackendUnavailableError(
                "Graph backend is not reachable. Check your graphdb_provider configuration."
            )

        anthropic_key = anthropic_api_key or settings.anthropic_api_key
        openai_key = openai_api_key or settings.openai_api_key

        # Create graphiti-core driver from provider
        graph_driver = provider.create_graphiti_driver()

        # Initialize LLM client with Claude
        llm_client = AnthropicClient(
            config=LLMConfig(api_key=anthropic_key, model="claude-haiku-4-5-20251001")
        )

        # Initialize embedder with OpenAI
        embedder = OpenAIEmbedder(config=OpenAIEmbedderConfig(api_key=openai_key))

        # Initialize cross-encoder (reranker) with OpenAI
        cross_encoder = OpenAIRerankerClient(
            config=LLMConfig(api_key=openai_key, model="gpt-4o-mini")
        )

        # Initialize Graphiti with driver
        graphiti = Graphiti(
            graph_driver=graph_driver,
            llm_client=llm_client,
            embedder=embedder,
            cross_encoder=cross_encoder,
        )

        # Build indices and constraints (idempotent, ~50ms)
        await graphiti.build_indices_and_constraints()

        logger.info(
            "Initialized Graphiti client "
            "(LLM: claude-haiku-4-5, Embedder: text-embedding-3-small, "
            "SEMAPHORE_LIMIT: %s)",
            os.environ.get("SEMAPHORE_LIMIT", "default"),
        )

        return cls(provider=provider, graphiti=graphiti)

    def close(self) -> None:
        """Close graph provider connection (sync)."""
        self.provider.close()
        logger.info("Closed Graphiti client connection")

    async def add_content_summary(
        self,
        content: Content,
        summary: Summary,
    ) -> str:
        """Add a content summary to the knowledge graph as an episode."""
        logger.info(f"Adding content to knowledge graph: {content.title}")

        episode_content = self._create_content_episode(content, summary)
        reference_time = content.published_date or datetime.now()

        source_type = content.source_type.value if content.source_type else "unknown"
        episode_id = await self.graphiti.add_episode(
            name=f"{content.publication or content.author}: {content.title}",
            episode_body=episode_content,
            source_description=f"Content from {source_type}",
            reference_time=reference_time,
            source=EpisodeType.text,
        )

        logger.info(f"Added episode {episode_id} for content {content.id} ({content.title})")
        return str(episode_id)

    def _create_content_episode(self, content: Content, summary: Summary) -> str:
        """Create structured episode content from Content and Summary."""
        source_type = content.source_type.value if content.source_type else "unknown"
        sections: list[str] = [
            f"# {content.title}",
            "",
            f"**Source:** {source_type}",
            f"**Publication:** {content.publication or 'Unknown'}",
            f"**Author:** {content.author or 'Unknown'}",
            f"**Date:** {content.published_date.isoformat() if content.published_date else 'Unknown'}",
            "",
            "## Executive Summary",
            summary.executive_summary or "",
            "",
        ]

        if summary.key_themes:
            sections.extend(["## Key Themes", ""])
            for theme in summary.key_themes:
                sections.append(f"- {theme}")
            sections.append("")

        if summary.strategic_insights:
            sections.extend(["## Strategic Insights", ""])
            for insight in summary.strategic_insights:
                sections.append(f"- {insight}")
            sections.append("")

        if summary.technical_details:
            sections.extend(["## Technical Details", ""])
            for detail in summary.technical_details:
                sections.append(f"- {detail}")
            sections.append("")

        return "\n".join(sections)

    async def search_related_concepts(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for entities and relationships related to a query."""
        logger.info(f"Searching knowledge graph for: {query}")

        results = await self.graphiti.search(
            query=query,
            num_results=limit,
        )

        logger.info(f"Found {len(results)} results for query: {query}")
        return results

    async def get_temporal_context(
        self,
        concepts: list[str],
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Get temporal context for concepts within a date range."""
        logger.info(
            f"Getting temporal context for {len(concepts)} concepts from {start_date} to {end_date}"
        )

        all_results = []
        search_tasks = [self.graphiti.search(query=concept, num_results=50) for concept in concepts]
        search_results_list = await asyncio.gather(*search_tasks)

        for results in search_results_list:
            filtered = [
                r
                for r in results
                if start_date <= r.get("reference_time", datetime.now()) <= end_date
            ]
            all_results.extend(filtered)

        logger.info(f"Found {len(all_results)} temporal entities")
        return all_results

    async def get_contents_in_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Get all content episodes within a date range from the graph."""
        logger.info(f"Fetching content from {start_date} to {end_date}")

        records = await self.provider.execute_query(
            """
            MATCH (e:Episode)
            WHERE e.valid_at >= $start_date AND e.valid_at <= $end_date
            RETURN e.uuid as episode_id, e.name as title, e.content as content,
                   e.valid_at as timestamp, e.source_description as source
            ORDER BY e.valid_at DESC
            """,
            {"start_date": start_date, "end_date": end_date},
        )

        episodes = [
            {
                "episode_id": r["episode_id"],
                "title": r["title"],
                "content": r["content"],
                "timestamp": r["timestamp"],
                "source": r["source"],
            }
            for r in records
        ]

        logger.info(f"Found {len(episodes)} content episodes")
        return episodes

    # Backwards compatibility alias
    async def get_newsletters_in_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Backwards compatibility alias for get_contents_in_range."""
        return await self.get_contents_in_range(start_date, end_date)

    async def extract_themes_from_range(
        self,
        start_date: datetime,
        end_date: datetime,
        query: str = "AI and technology themes, trends, and topics",
    ) -> list[dict[str, Any]]:
        """Extract common themes from content items in a date range."""
        logger.info(f"Extracting themes from content between {start_date} and {end_date}")

        results = await self.graphiti.search(
            query=query,
            num_results=100,
        )

        logger.info(f"Found {len(results)} potential theme elements")
        return results

    async def add_theme_analysis_episode(
        self,
        result: Any,
    ) -> str | None:
        """Write a completed theme analysis to the knowledge graph as an episode."""
        if not result.themes:
            logger.info("No themes to write to knowledge graph")
            return None

        lines = [
            f"# Theme Analysis — {result.analysis_date.strftime('%Y-%m-%d')}",
            "",
            f"**Period:** {result.start_date.strftime('%Y-%m-%d')} to {result.end_date.strftime('%Y-%m-%d')}",
            f"**Content Analyzed:** {result.content_count}",
            f"**Total Themes:** {result.total_themes}",
            f"**Emerging Themes:** {result.emerging_themes_count}",
            "",
        ]

        for theme in result.themes:
            t = (
                theme
                if isinstance(theme, dict)
                else theme.model_dump()
                if hasattr(theme, "model_dump")
                else theme
            )
            name = (
                t.get("name", "Unknown") if isinstance(t, dict) else getattr(t, "name", "Unknown")
            )
            category = t.get("category", "") if isinstance(t, dict) else getattr(t, "category", "")
            trend = t.get("trend", "") if isinstance(t, dict) else getattr(t, "trend", "")
            description = (
                t.get("description", "") if isinstance(t, dict) else getattr(t, "description", "")
            )
            key_points = (
                t.get("key_points", []) if isinstance(t, dict) else getattr(t, "key_points", [])
            )
            relevance = (
                t.get("relevance_score", 0)
                if isinstance(t, dict)
                else getattr(t, "relevance_score", 0)
            )

            lines.append(f"## {name}")
            lines.append(
                f"**Category:** {category} | **Trend:** {trend} | **Relevance:** {relevance:.2f}"
            )
            lines.append(f"{description}")
            if key_points:
                lines.append("")
                for point in key_points[:5]:
                    lines.append(f"- {point}")
            lines.append("")

        if result.cross_theme_insights:
            lines.append("## Cross-Theme Insights")
            for insight in result.cross_theme_insights:
                lines.append(f"- {insight}")
            lines.append("")

        episode_body = "\n".join(lines)

        episode_id = await self.graphiti.add_episode(
            name=f"Theme Analysis: {result.analysis_date.strftime('%Y-%m-%d')}",
            episode_body=episode_body,
            source_description="Automated theme analysis result",
            reference_time=result.analysis_date,
            source=EpisodeType.text,
        )

        logger.info(f"Added theme analysis episode {episode_id}")
        return str(episode_id)

    async def get_entity_facts(
        self,
        entity_names: list[str],
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get facts about specific entities from the knowledge graph."""
        logger.info(f"Fetching facts for {len(entity_names)} entities")

        all_facts = []
        for entity_name in entity_names:
            results = await self.graphiti.search(
                query=entity_name,
                num_results=limit,
            )
            all_facts.extend(results)

        logger.info(f"Retrieved {len(all_facts)} facts")
        return all_facts

    async def get_historical_theme_mentions(
        self,
        theme_name: str,
        before_date: datetime,
        lookback_days: int = 90,
    ) -> list[dict[str, Any]]:
        """Get historical mentions of a theme before a given date."""
        logger.info(
            f"Fetching historical mentions of '{theme_name}' "
            f"(before {before_date}, lookback: {lookback_days} days)"
        )

        start_date = before_date - timedelta(days=lookback_days)

        # Use provider to query episodes mentioning the theme
        mentions = await self.provider.execute_query(
            """
            MATCH (e:Episode)
            WHERE e.valid_at >= $start_date
              AND e.valid_at < $before_date
              AND (toLower(e.name) CONTAINS toLower($theme_name)
                   OR toLower(e.content) CONTAINS toLower($theme_name))
            RETURN e.uuid as episode_id, e.name as title, e.content as content,
                   e.valid_at as timestamp, e.source_description as source
            ORDER BY e.valid_at DESC
            LIMIT 20
            """,
            {
                "theme_name": theme_name,
                "start_date": start_date,
                "before_date": before_date,
            },
        )

        # Also use Graphiti semantic search for related content
        semantic_results = await self.graphiti.search(
            query=theme_name,
            num_results=30,
        )

        # Filter semantic results by date
        filtered_semantic = [
            r
            for r in semantic_results
            if "reference_time" in r and start_date <= r["reference_time"] < before_date
        ]

        logger.info(
            f"Found {len(mentions)} direct mentions and {len(filtered_semantic)} semantic matches"
        )

        return mentions + filtered_semantic

    async def get_theme_evolution_timeline(
        self,
        theme_name: str,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Get complete timeline of a theme's evolution."""
        logger.info(f"Building evolution timeline for '{theme_name}'")

        timeline = await self.provider.execute_query(
            """
            MATCH (e:Episode)
            WHERE e.valid_at <= $end_date
              AND (toLower(e.name) CONTAINS toLower($theme_name)
                   OR toLower(e.content) CONTAINS toLower($theme_name))
            RETURN e.uuid as episode_id, e.name as title, e.content as content,
                   e.valid_at as timestamp, e.source_description as source
            ORDER BY e.valid_at ASC
            """,
            {"theme_name": theme_name, "end_date": end_date},
        )

        logger.info(f"Found {len(timeline)} mentions in timeline")
        return timeline

    def get_previous_analyses(
        self,
        before_date: datetime,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get previous theme analyses from database (PostgreSQL, not graph)."""
        from src.models.theme import ThemeAnalysis
        from src.storage.database import get_db

        logger.info(f"Fetching previous theme analyses before {before_date}")

        with get_db() as db:
            analyses = (
                db.query(ThemeAnalysis)
                .filter(ThemeAnalysis.analysis_date < before_date)
                .order_by(ThemeAnalysis.analysis_date.desc())
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": a.id,
                    "analysis_date": a.analysis_date,
                    "start_date": a.start_date,
                    "end_date": a.end_date,
                    "themes": a.themes,
                    "total_themes": a.total_themes,
                }
                for a in analyses
            ]

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.close()
