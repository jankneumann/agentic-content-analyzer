"""Graphiti knowledge graph client for entity extraction and temporal tracking."""

import os
from datetime import datetime, timedelta
from typing import Any

from graphiti_core import Graphiti
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.anthropic_client import AnthropicClient, LLMConfig
from graphiti_core.nodes import EpisodeType
from neo4j import GraphDatabase

from src.config import settings
from src.models.newsletter import Newsletter
from src.models.summary import NewsletterSummary
from src.utils.logging import get_logger

logger = get_logger(__name__)


class GraphitiClient:
    """Client for managing newsletter knowledge graph with Graphiti."""

    def __init__(
        self,
        neo4j_uri: str = "",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "newsletter_password",
        anthropic_api_key: str = "",
        openai_api_key: str = "",
    ) -> None:
        """
        Initialize Graphiti client.

        Uses Claude (Anthropic) for entity extraction and OpenAI for embeddings.

        Args:
            neo4j_uri: Neo4j connection URI (default: from settings)
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            anthropic_api_key: Anthropic API key for LLM (default: from settings)
            openai_api_key: OpenAI API key for embeddings (default: from settings)
        """
        self.neo4j_uri = neo4j_uri or settings.neo4j_uri
        self.anthropic_api_key = anthropic_api_key or settings.anthropic_api_key
        self.openai_api_key = openai_api_key or settings.openai_api_key

        # Initialize Neo4j driver
        self.driver = GraphDatabase.driver(self.neo4j_uri, auth=(neo4j_user, neo4j_password))

        # Initialize LLM client with Claude
        llm_client = AnthropicClient(
            config=LLMConfig(api_key=self.anthropic_api_key, model="claude-haiku-4-5-20251001")
        )

        # Initialize embedder with OpenAI
        embedder = OpenAIEmbedder(
            config=OpenAIEmbedderConfig(
                api_key=self.openai_api_key,
            )
        )

        # Initialize cross-encoder (reranker) with OpenAI
        cross_encoder = OpenAIRerankerClient(
            config=LLMConfig(
                api_key=self.openai_api_key,
                model="gpt-4o-mini",  # Use a smaller model for reranking
            )
        )

        # Initialize Graphiti with custom clients
        # Concurrency is controlled by SEMAPHORE_LIMIT environment variable
        self.graphiti = Graphiti(
            self.neo4j_uri,
            neo4j_user,
            neo4j_password,
            llm_client=llm_client,
            embedder=embedder,
            cross_encoder=cross_encoder,
        )

        logger.info(
            f"Initialized Graphiti client connected to {self.neo4j_uri} "
            f"(LLM: claude-haiku-4-5, Embedder: text-embedding-3-small, "
            f"SEMAPHORE_LIMIT: {os.environ.get('SEMAPHORE_LIMIT', 'default')})"
        )

    def close(self) -> None:
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
            logger.info("Closed Graphiti client connection")

    async def add_newsletter_summary(
        self,
        newsletter: Newsletter,
        summary: NewsletterSummary,
    ) -> str:
        """
        Add a newsletter summary to the knowledge graph.

        Extracts entities, relationships, and concepts from the summary
        and stores them as a timestamped episode in Graphiti.

        Args:
            newsletter: Newsletter object
            summary: Newsletter summary object

        Returns:
            Episode ID in Graphiti
        """
        logger.info(f"Adding newsletter to knowledge graph: {newsletter.title}")

        # Create structured episode content with section headers
        episode_content = self._create_episode_content(newsletter, summary)

        # Use newsletter published date as episode timestamp
        reference_time = newsletter.published_date or datetime.now()

        # Add episode to Graphiti
        episode_id = await self.graphiti.add_episode(
            name=f"{newsletter.publication or newsletter.sender}: {newsletter.title}",
            episode_body=episode_content,
            source_description=f"Newsletter from {newsletter.sender}",
            reference_time=reference_time,
            source=EpisodeType.text,
        )

        logger.info(
            f"Added episode {episode_id} for newsletter {newsletter.id} ({newsletter.title})"
        )

        return episode_id

    async def search_related_concepts(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search for entities and relationships related to a query.

        Args:
            query: Search query (concept, topic, or theme)
            limit: Maximum number of results

        Returns:
            List of relevant entities and relationships
        """
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
        """
        Get temporal context for concepts within a date range.

        Useful for analyzing how concepts evolved over time across
        multiple newsletters.

        Args:
            concepts: List of concepts to track
            start_date: Start of time range
            end_date: End of time range

        Returns:
            List of temporal entities and relationships
        """
        logger.info(
            f"Getting temporal context for {len(concepts)} concepts from {start_date} to {end_date}"
        )

        # Search for each concept and filter by time
        all_results = []
        for concept in concepts:
            results = await self.graphiti.search(
                query=concept,
                num_results=50,  # Get more to filter by time
            )

            # Filter by time range
            filtered = [
                r
                for r in results
                if start_date <= r.get("reference_time", datetime.now()) <= end_date
            ]

            all_results.extend(filtered)

        logger.info(f"Found {len(all_results)} temporal entities")
        return all_results

    async def get_newsletters_in_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """
        Get all newsletter episodes within a date range from Graphiti.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of newsletter episodes with their content
        """
        logger.info(f"Fetching newsletters from {start_date} to {end_date}")

        # Use Neo4j directly to query episodes in time range
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e:Episode)
                WHERE e.valid_at >= $start_date AND e.valid_at <= $end_date
                RETURN e.uuid as episode_id, e.name as title, e.content as content,
                       e.valid_at as timestamp, e.source_description as source
                ORDER BY e.valid_at DESC
                """,
                start_date=start_date,
                end_date=end_date,
            )

            episodes = [
                {
                    "episode_id": record["episode_id"],
                    "title": record["title"],
                    "content": record["content"],
                    "timestamp": record["timestamp"],
                    "source": record["source"],
                }
                for record in result
            ]

        logger.info(f"Found {len(episodes)} newsletter episodes")
        return episodes

    async def extract_themes_from_range(
        self,
        start_date: datetime,
        end_date: datetime,
        query: str = "AI and technology themes, trends, and topics",
    ) -> list[dict[str, Any]]:
        """
        Extract common themes from newsletters in a date range.

        Uses Graphiti's semantic search to find related concepts and entities
        across multiple newsletter episodes.

        Args:
            start_date: Start of date range
            end_date: End of date range
            query: Search query for theme extraction

        Returns:
            List of related entities, facts, and themes
        """
        logger.info(f"Extracting themes from newsletters between {start_date} and {end_date}")

        # Search for broad AI/tech themes
        results = await self.graphiti.search(
            query=query,
            num_results=100,  # Get many results for comprehensive analysis
        )

        logger.info(f"Found {len(results)} potential theme elements")
        return results

    async def get_entity_facts(
        self,
        entity_names: list[str],
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get facts about specific entities from the knowledge graph.

        Useful for understanding what the newsletters say about specific
        topics, companies, or concepts.

        Args:
            entity_names: List of entity names to query
            limit: Maximum facts per entity

        Returns:
            List of facts about the entities
        """
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
        """
        Get historical mentions of a theme before a given date.

        Args:
            theme_name: Theme to search for
            before_date: Only return mentions before this date
            lookback_days: How far back to look (default: 90 days)

        Returns:
            List of historical mentions with context
        """
        logger.info(
            f"Fetching historical mentions of '{theme_name}' "
            f"(before {before_date}, lookback: {lookback_days} days)"
        )

        start_date = before_date - timedelta(days=lookback_days)

        # Use Neo4j to query episodes mentioning the theme
        with self.driver.session() as session:
            result = session.run(
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
                theme_name=theme_name,
                start_date=start_date,
                before_date=before_date,
            )

            mentions = [
                {
                    "episode_id": record["episode_id"],
                    "title": record["title"],
                    "content": record["content"],
                    "timestamp": record["timestamp"],
                    "source": record["source"],
                }
                for record in result
            ]

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

        # Combine results (prioritize direct mentions)
        return mentions + filtered_semantic

    async def get_theme_evolution_timeline(
        self,
        theme_name: str,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """
        Get complete timeline of a theme's evolution.

        Args:
            theme_name: Theme to track
            end_date: End of timeline

        Returns:
            Chronological list of theme mentions with metadata
        """
        logger.info(f"Building evolution timeline for '{theme_name}'")

        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e:Episode)
                WHERE e.valid_at <= $end_date
                  AND (toLower(e.name) CONTAINS toLower($theme_name)
                       OR toLower(e.content) CONTAINS toLower($theme_name))
                RETURN e.uuid as episode_id, e.name as title, e.content as content,
                       e.valid_at as timestamp, e.source_description as source
                ORDER BY e.valid_at ASC
                """,
                theme_name=theme_name,
                end_date=end_date,
            )

            timeline = [
                {
                    "episode_id": record["episode_id"],
                    "title": record["title"],
                    "content": record["content"],
                    "timestamp": record["timestamp"],
                    "source": record["source"],
                }
                for record in result
            ]

        logger.info(f"Found {len(timeline)} mentions in timeline")
        return timeline

    def get_previous_analyses(
        self,
        before_date: datetime,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get previous theme analyses from database.

        Useful for tracking how themes have been identified over time.

        Args:
            before_date: Get analyses before this date
            limit: Maximum number of analyses to return

        Returns:
            List of previous theme analyses
        """
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

    def _create_episode_content(
        self,
        newsletter: Newsletter,
        summary: NewsletterSummary,
    ) -> str:
        """
        Create structured episode content from newsletter summary.

        Uses clear section headers so the LLM understands context during
        entity extraction. Sections are marked with [SECTION_TYPE] headers.

        Args:
            newsletter: Newsletter object
            summary: Summary object

        Returns:
            Formatted episode content with section markers
        """
        sections = []

        # Executive summary
        if summary.executive_summary:
            sections.append(f"[EXECUTIVE_SUMMARY]\n{summary.executive_summary}")

        # Key themes
        if summary.key_themes:
            themes_text = "; ".join(summary.key_themes)
            sections.append(f"[KEY_THEMES]\n{themes_text}")

        # Strategic insights (for CTO/leadership)
        if summary.strategic_insights:
            insights_text = " ".join(summary.strategic_insights)
            sections.append(f"[STRATEGIC_INSIGHTS]\n{insights_text}")

        # Technical details (for developers)
        if summary.technical_details:
            details_text = " ".join(summary.technical_details)
            sections.append(f"[TECHNICAL_DETAILS]\n{details_text}")

        # Actionable items
        if summary.actionable_items:
            actions_text = " ".join(summary.actionable_items)
            sections.append(f"[ACTIONABLE_ITEMS]\n{actions_text}")

        # Notable quotes and data points
        if summary.notable_quotes:
            quotes_text = " ".join(summary.notable_quotes)
            sections.append(f"[NOTABLE_DATA]\n{quotes_text}")

        return "\n\n".join(sections)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.close()
