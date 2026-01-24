"""Theme analysis processor for multi-newsletter analysis."""

import json
import time
from datetime import datetime

from anthropic import Anthropic

from src.config import settings
from src.config.models import ModelConfig, ModelStep, Provider
from src.models.content import Content, ContentStatus
from src.models.summary import Summary
from src.models.theme import (
    ThemeAnalysisRequest,
    ThemeAnalysisResult,
    ThemeCategory,
    ThemeData,
    ThemeTrend,
)
from src.processors.historical_context import HistoricalContextAnalyzer
from src.storage.database import get_db
from src.storage.graphiti_client import GraphitiClient
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ThemeAnalyzer:
    """
    Analyzes themes across multiple newsletters using knowledge graph and LLM.

    Supports Claude (primary) and optionally Gemini Flash for large context.
    """

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        use_large_context: bool = False,
        model_override: str | None = None,
    ) -> None:
        """
        Initialize theme analyzer.

        Args:
            model_config: Model configuration (defaults to settings.get_model_config())
            use_large_context: If True, use large context model (Gemini Flash)
            model_override: Optional model name override
        """
        self.use_large_context = use_large_context

        # Get model config from settings if not provided
        if model_config is None:
            model_config = settings.get_model_config()

        self.model_config = model_config

        # Get model for theme analysis step (or use override)
        self.model = model_override or model_config.get_model_for_step(ModelStep.THEME_ANALYSIS)

        # Determine framework based on model family
        model_family = model_config.get_family(self.model)
        self.framework = model_family.value  # "claude", "gemini", "gpt"

        if use_large_context:
            # TODO: Add Gemini Flash support in future
            logger.warning(
                "Large context model (Gemini) not yet implemented, "
                "using configured theme analysis model"
            )

        self.graphiti_client: GraphitiClient | None = None

        # Track usage for cost calculation
        self.provider_used: Provider | None = None
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.model_version: str | None = None

        logger.info(f"Initialized ThemeAnalyzer with {self.framework} ({self.model})")

    async def analyze_themes(
        self,
        request: ThemeAnalysisRequest,
        include_historical_context: bool = True,
    ) -> ThemeAnalysisResult:
        """
        Analyze themes across newsletters in a date range.

        Args:
            request: Theme analysis request parameters
            include_historical_context: If True, enrich themes with historical context

        Returns:
            Theme analysis results
        """
        start_time = time.time()
        logger.info(f"Starting theme analysis from {request.start_date} to {request.end_date}")

        # Initialize Graphiti client
        self.graphiti_client = GraphitiClient()

        try:
            # 1. Fetch content from database for the date range (unified Content model)
            contents = await self._fetch_contents(request.start_date, request.end_date)

            if len(contents) < request.min_newsletters:
                logger.warning(
                    f"Only found {len(contents)} content items, "
                    f"minimum required: {request.min_newsletters}"
                )
                return ThemeAnalysisResult(
                    start_date=request.start_date,
                    end_date=request.end_date,
                    newsletter_count=0,
                    model_used=self.model,
                    agent_framework=self.framework,
                )

            logger.info(f"Analyzing {len(contents)} content items")

            # 2. Get summaries for content items
            content_ids = [c["id"] for c in contents]
            summaries = await self._fetch_summaries(content_ids)

            # 3. Query Graphiti for themes and entities
            graphiti_themes = await self.graphiti_client.extract_themes_from_range(
                start_date=request.start_date,
                end_date=request.end_date,
            )

            # 4. Use LLM to analyze and extract structured themes
            themes = await self._extract_themes_with_llm(
                contents=contents,
                summaries=summaries,
                graphiti_themes=graphiti_themes,
                max_themes=request.max_themes,
                relevance_threshold=request.relevance_threshold,
            )

            # 5. Enrich with historical context (NEW)
            if include_historical_context and themes:
                logger.info("Enriching themes with historical context...")
                context_analyzer = HistoricalContextAnalyzer(
                    model_config=self.model_config, model=self.model
                )
                themes = await context_analyzer.enrich_themes_with_history(
                    themes=themes,
                    current_date=request.end_date,
                    lookback_days=90,
                )
                logger.info("Historical context enrichment complete")

            # 6. Build result
            processing_time = time.time() - start_time

            result = ThemeAnalysisResult(
                start_date=request.start_date,
                end_date=request.end_date,
                newsletter_count=len(contents),
                newsletter_ids=[c["id"] for c in contents],  # Now content IDs
                themes=themes,
                total_themes=len(themes),
                emerging_themes_count=len([t for t in themes if t.trend == ThemeTrend.EMERGING]),
                top_theme=themes[0].name if themes else None,
                processing_time_seconds=processing_time,
                model_used=self.model,
                model_version=self.model_version,
                agent_framework=self.framework,
            )

            logger.info(
                f"Theme analysis complete: {len(themes)} themes found in {processing_time:.2f}s"
            )

            return result

        finally:
            if self.graphiti_client:
                self.graphiti_client.close()

    async def _fetch_contents(
        self,
        start_date: datetime,
        end_date: datetime,
        status_filter: list[ContentStatus] | None = None,
    ) -> list[dict]:
        """
        Fetch content records from database for date range.

        Uses the unified Content model instead of Newsletter.

        Args:
            start_date: Period start date
            end_date: Period end date
            status_filter: Optional list of content statuses to include
                          (default: COMPLETED only)

        Returns:
            List of content dicts with standard fields
        """
        if status_filter is None:
            status_filter = [ContentStatus.COMPLETED]

        with get_db() as db:
            contents = (
                db.query(Content)
                .filter(
                    Content.published_date >= start_date,
                    Content.published_date <= end_date,
                    Content.status.in_(status_filter),
                )
                .order_by(Content.published_date.desc())
                .all()
            )

            return [
                {
                    "id": c.id,
                    "title": c.title,
                    "publication": c.publication,
                    "published_date": c.published_date,
                    "source_type": c.source_type.value,
                }
                for c in contents
            ]

    async def _fetch_summaries(
        self,
        content_ids: list[int],
    ) -> list[dict]:
        """Fetch summaries for content items by content_id."""
        if not content_ids:
            return []

        with get_db() as db:
            summaries = db.query(Summary).filter(Summary.content_id.in_(content_ids)).all()

            logger.info(f"Found {len(summaries)} summaries for {len(content_ids)} content items")

            return [
                {
                    "content_id": s.content_id,
                    "executive_summary": s.executive_summary,
                    "key_themes": s.key_themes or [],
                    "theme_tags": s.theme_tags or [],
                    "strategic_insights": s.strategic_insights or [],
                    "technical_details": s.technical_details or [],
                }
                for s in summaries
            ]

    async def _extract_themes_with_llm(
        self,
        contents: list[dict],
        summaries: list[dict],
        graphiti_themes: list[dict],
        max_themes: int,
        relevance_threshold: float,
    ) -> list[ThemeData]:
        """
        Use LLM to extract and analyze themes from content data.

        This is the core intelligence - analyzes summaries and Graphiti data
        to identify common themes, trends, and insights.
        """
        logger.info("Analyzing themes with LLM...")

        # Build context from summaries
        summary_context = self._build_summary_context(contents, summaries)

        # Build context from Graphiti
        graphiti_context = self._build_graphiti_context(graphiti_themes)

        # Construct prompt for theme extraction
        prompt = self._build_theme_extraction_prompt(
            summary_context=summary_context,
            graphiti_context=graphiti_context,
            max_themes=max_themes,
            relevance_threshold=relevance_threshold,
        )

        # Call LLM for analysis with provider failover
        start_time = time.time()

        # Get providers for this model (in priority order)
        try:
            providers = self.model_config.get_providers_for_model(self.model)
        except ValueError as e:
            logger.error(f"No providers configured for model {self.model}: {e}")
            return []

        # Filter for Anthropic-compatible providers (for now, only Anthropic)
        # TODO: Add support for other providers (AWS Bedrock, Vertex AI, Azure, OpenAI)
        anthropic_providers = [p for p in providers if p.provider == Provider.ANTHROPIC]

        if not anthropic_providers:
            logger.error(f"No Anthropic-compatible providers for model {self.model}")
            return []

        # Try each provider in order (failover support)
        response = None
        last_error = None

        for provider_config in anthropic_providers:
            try:
                logger.info(f"Trying provider: {provider_config.provider.value}")

                # Create client for this provider
                client = Anthropic(api_key=provider_config.api_key)

                # Get provider-specific model ID for API call
                provider_model_id = self.model_config.get_provider_model_id(
                    self.model, provider_config.provider
                )

                response = client.messages.create(
                    model=provider_model_id,
                    max_tokens=8000,
                    temperature=0.3,  # Lower temperature for more consistent analysis
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                )

                # Track provider and token usage for cost calculation
                self.provider_used = provider_config.provider
                self.input_tokens = response.usage.input_tokens
                self.output_tokens = response.usage.output_tokens
                self.model_version = self.model_config.get_model_version(
                    self.model, self.provider_used
                )

                # Success - break out of failover loop
                break

            except Exception as e:
                error_msg = f"Error with provider {provider_config.provider.value}: {e!s}"
                logger.error(error_msg)
                last_error = str(e)
                continue  # Try next provider

        if response is None:
            logger.error(f"All providers failed. Last error: {last_error}")
            return []

        llm_time = time.time() - start_time

        # Calculate actual cost
        cost = self.model_config.calculate_cost(
            model_id=self.model,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            provider=self.provider_used,
        )

        logger.info(
            f"LLM analysis completed in {llm_time:.2f}s, "
            f"tokens: {self.input_tokens + self.output_tokens}, "
            f"cost: ${cost:.4f}, "
            f"provider: {self.provider_used.value}"
        )

        # Parse response
        themes = self._parse_theme_response(
            response.content[0].text,
            contents,
        )

        # Filter by relevance threshold
        themes = [t for t in themes if t.relevance_score >= relevance_threshold]

        # Sort by relevance
        themes.sort(key=lambda t: t.relevance_score, reverse=True)

        # Limit to max themes
        themes = themes[:max_themes]

        logger.info(f"Extracted {len(themes)} themes (after filtering and limiting)")

        return themes

    def _build_summary_context(
        self,
        contents: list[dict],
        summaries: list[dict],
    ) -> str:
        """Build context string from content summaries."""
        # Build lookup map by content_id
        summary_by_id = {s["content_id"]: s for s in summaries if s.get("content_id")}

        context_parts = []
        matched_count = 0

        for content in contents:
            content_id = content["id"]
            summary = summary_by_id.get(content_id)

            if summary:
                matched_count += 1
                # Combine key_themes and theme_tags for comprehensive coverage
                themes = summary.get("key_themes", []) or []
                theme_tags = summary.get("theme_tags", []) or []
                all_themes = list(set(themes + theme_tags))

                context_parts.append(
                    f"## {content.get('publication', 'Unknown')} - {content['title']}\n"
                    f"Date: {content['published_date'].strftime('%Y-%m-%d')}\n"
                    f"Source: {content.get('source_type', 'unknown')}\n\n"
                    f"Summary: {summary['executive_summary']}\n\n"
                    f"Key Themes: {', '.join(all_themes) if all_themes else 'None'}\n\n"
                    f"Strategic Insights:\n"
                    + "\n".join(f"- {i}" for i in (summary.get("strategic_insights") or []))
                    + "\n"
                )

        logger.info(
            f"Built context from {matched_count}/{len(contents)} content items with summaries"
        )

        return "\n\n".join(context_parts)

    def _build_graphiti_context(self, graphiti_themes: list[dict]) -> str:
        """Build context string from Graphiti knowledge graph data."""
        if not graphiti_themes:
            return "No knowledge graph data available for this time range."

        # Extract key information from Graphiti results
        context_parts = ["Knowledge Graph Insights:"]

        # Group by entity/concept (simplified)
        for item in graphiti_themes[:30]:  # Limit to avoid token overflow
            if isinstance(item, dict):
                # Extract relevant fields (structure may vary)
                name = item.get("name", item.get("entity_name", "Unknown"))
                fact = item.get("fact", item.get("content", ""))

                if fact:
                    context_parts.append(f"- {name}: {fact}")

        return "\n".join(context_parts)

    def _build_theme_extraction_prompt(
        self,
        summary_context: str,
        graphiti_context: str,
        max_themes: int,
        relevance_threshold: float,
    ) -> str:
        """Build prompt for LLM theme extraction."""
        return f"""You are an AI analyst specializing in technology trends for enterprise technical leaders at Comcast.

Analyze the following newsletter summaries and knowledge graph insights to identify the most important themes, trends, and topics.

# Newsletter Summaries

{summary_context}

# {graphiti_context}

# Your Task

Extract up to {max_themes} distinct themes from these newsletters. For each theme:

1. **Identify the theme** - What is the core topic or trend?
2. **Categorize it** - Choose from: ml_ai, devops_infra, data_engineering, business_strategy, tools_products, research_academia, security, other
3. **Assess the trend** - Is it: emerging (new, recent), growing (increasing mentions), established (consistent), declining, or one_off?
4. **Score its relevance** (0-1 scale):
   - Overall relevance to Comcast technical audience
   - Strategic relevance (CTO-level decisions)
   - Tactical relevance (developer/practitioner)
   - Novelty (how new vs. established)
   - Cross-functional impact (affects multiple teams)
5. **Find related themes** - What other themes connect to this one?
6. **Extract key points** - 2-4 bullet points about what newsletters say about this theme

# Output Format

Respond with a JSON array of themes. Each theme should have this structure:

```json
[
  {{
    "name": "Theme Name",
    "description": "Brief 1-2 sentence description",
    "category": "ml_ai",
    "mention_count": 3,
    "trend": "emerging",
    "relevance_score": 0.85,
    "strategic_relevance": 0.9,
    "tactical_relevance": 0.7,
    "novelty_score": 0.8,
    "cross_functional_impact": 0.75,
    "related_themes": ["Related Theme 1", "Related Theme 2"],
    "key_points": [
      "Key insight 1",
      "Key insight 2",
      "Key insight 3"
    ]
  }}
]
```

# Guidelines

- Focus on themes relevant to enterprise AI/data/engineering teams
- Prioritize strategic significance over tactical details
- Look for cross-cutting themes that appear in multiple newsletters
- Identify emerging trends that leaders should know about
- Only include themes with relevance_score >= {relevance_threshold}
- Be specific - "RAG Architecture Evolution" not just "AI"
- Limit to {max_themes} most important themes

Provide ONLY the JSON array, no other text."""

    def _parse_theme_response(
        self,
        response_text: str,
        contents: list[dict],
    ) -> list[ThemeData]:
        """Parse LLM response into ThemeData objects."""
        try:
            # Extract JSON from response (may have markdown code blocks)
            response_text = response_text.strip()
            if response_text.startswith("```"):
                # Remove markdown code block
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])
                if response_text.startswith("json"):
                    response_text = response_text[4:]

            themes_json = json.loads(response_text)

            themes = []
            for theme_dict in themes_json:
                # Map content mentions (simplified - using mention_count)
                mention_count = theme_dict.get("mention_count", 1)
                content_ids = [c["id"] for c in contents[:mention_count]]

                # Estimate dates
                first_date = contents[-1]["published_date"] if contents else datetime.now()
                last_date = contents[0]["published_date"] if contents else datetime.now()

                theme = ThemeData(
                    name=theme_dict["name"],
                    description=theme_dict["description"],
                    category=ThemeCategory(theme_dict["category"]),
                    mention_count=mention_count,
                    newsletter_ids=content_ids,  # TODO: Rename field to content_ids in ThemeData
                    first_seen=first_date,
                    last_seen=last_date,
                    trend=ThemeTrend(theme_dict["trend"]),
                    relevance_score=theme_dict["relevance_score"],
                    strategic_relevance=theme_dict["strategic_relevance"],
                    tactical_relevance=theme_dict["tactical_relevance"],
                    novelty_score=theme_dict["novelty_score"],
                    cross_functional_impact=theme_dict["cross_functional_impact"],
                    related_themes=theme_dict.get("related_themes", []),
                    key_points=theme_dict.get("key_points", []),
                )
                themes.append(theme)

            return themes

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse theme response as JSON: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            return []
        except Exception as e:
            logger.error(f"Error parsing theme response: {e}", exc_info=True)
            return []
