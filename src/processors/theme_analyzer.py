"""Theme analysis processor for multi-content analysis."""

import json
import time
from datetime import datetime

from src.config.models import ModelConfig, ModelStep, Provider, get_model_config
from src.models.query import ResolvedContentSet
from src.models.theme import (
    ThemeAnalysisRequest,
    ThemeAnalysisResult,
    ThemeCategory,
    ThemeData,
    ThemeTrend,
)
from src.processors.historical_context import HistoricalContextAnalyzer
from src.processors.provenance import ExactContentSetLoader
from src.services.llm_router import LLMRouter
from src.services.prompt_service import PromptService
from src.storage.graph_provider import GraphBackendUnavailableError
from src.storage.graphiti_client import GraphitiClient
from src.telemetry.decorators import observe
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ThemeAnalyzer:
    """
    Analyzes themes across multiple content items using knowledge graph and LLM.

    Supports multiple providers (Claude, OpenAI) and optionally Gemini Flash for large context.
    """

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        use_large_context: bool = False,
        model_override: str | None = None,
        prompt_service: PromptService | None = None,
        content_loader: ExactContentSetLoader | None = None,
        llm_router: LLMRouter | None = None,
    ) -> None:
        """
        Initialize theme analyzer.

        Args:
            model_config: Model configuration (defaults to settings.get_model_config())
            use_large_context: If True, use large context model (Gemini Flash)
            model_override: Optional model name override
            prompt_service: Optional PromptService for configurable prompts
        """
        self.use_large_context = use_large_context

        # Get model config from settings if not provided
        if model_config is None:
            model_config = get_model_config()

        self.model_config = model_config

        # Get model for theme analysis step (or use override)
        self.model = model_override or model_config.get_model_for_step(ModelStep.THEME_ANALYSIS)
        self.model_used = self.model

        # Initialize LLM router
        self.llm_router = llm_router or LLMRouter(model_config)
        self.content_loader = content_loader or ExactContentSetLoader()
        self.prompt_service = prompt_service or PromptService()

        # Determine framework based on model family
        model_family = model_config.get_family(self.model)
        self.framework = model_family.value  # "claude", "gemini", "gpt"

        if use_large_context:
            # If large context requested but model not set to Gemini, warn but proceed
            if self.framework != "gemini":
                logger.warning(
                    "Large context analysis requested. Ensure a Gemini Flash model "
                    "is configured for optimal performance."
                )

        self.graphiti_client: GraphitiClient | None = None
        self._graphiti_unavailable: bool = False

        # Track usage for cost calculation
        self.provider_used: Provider | None = None
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.model_version: str | None = None

        logger.info(f"Initialized ThemeAnalyzer with {self.framework} ({self.model})")

    async def _get_client(self) -> GraphitiClient | None:
        """Lazy-initialize the GraphitiClient, returning None if unavailable."""
        if self._graphiti_unavailable:
            return None
        if self.graphiti_client is None:
            try:
                self.graphiti_client = await GraphitiClient.create()
            except GraphBackendUnavailableError:
                logger.warning("Graph backend unavailable, skipping graph enrichment")
                self._graphiti_unavailable = True
                return None
        return self.graphiti_client

    @observe()
    async def analyze_themes(
        self,
        request: ThemeAnalysisRequest,
        resolved_set: ResolvedContentSet,
        include_historical_context: bool = True,
    ) -> ThemeAnalysisResult:
        """
        Analyze themes across content items in a date range.

        Args:
            request: Theme analysis request parameters
            include_historical_context: If True, enrich themes with historical context

        Returns:
            Theme analysis results
        """
        start_time = time.time()
        logger.info(f"Starting theme analysis from {request.start_date} to {request.end_date}")

        try:
            # The workflow resolves once. Processors load only those exact persisted pairs.
            loaded_items = self.content_loader.load(resolved_set)
            selection_dates = {item.content_id: item.selection_date for item in resolved_set.items}
            contents = [
                {
                    "id": item.content.id,
                    "title": item.content.title,
                    "publication": item.content.publication,
                    "published_date": selection_dates[item.content.id],
                    "source_type": item.content.source_type.value,
                }
                for item in loaded_items
            ]
            summaries = [
                {
                    "id": item.summary.id,
                    "content_id": item.summary.content_id,
                    "executive_summary": item.summary.executive_summary,
                    "key_themes": item.summary.key_themes or [],
                    "theme_tags": item.summary.theme_tags or [],
                    "strategic_insights": item.summary.strategic_insights or [],
                    "technical_details": item.summary.technical_details or [],
                }
                for item in loaded_items
            ]

            if len(contents) < request.min_newsletters:
                logger.warning(
                    f"Only found {len(contents)} content items, "
                    f"minimum required: {request.min_newsletters}"
                )
                return ThemeAnalysisResult(
                    start_date=request.start_date,
                    end_date=request.end_date,
                    content_count=len(contents),
                    content_ids=list(resolved_set.content_ids),
                    summary_ids=list(resolved_set.summary_ids),
                    selection_fingerprint=resolved_set.fingerprint,
                    selection_policy=resolved_set.policy.model_dump(mode="json"),
                    model_used=self.model_used,
                    agent_framework=self.framework,
                )

            logger.info(f"Analyzing {len(contents)} content items")

            # Graph-wide period retrieval is intentionally excluded here: it can
            # introduce facts from content outside the immutable selection.
            graphiti_themes: list[dict] = []

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
                    model_config=self.model_config,
                    prompt_service=self.prompt_service,
                    llm_router=self.llm_router,
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
                content_count=len(contents),
                content_ids=[c["id"] for c in contents],
                summary_ids=list(resolved_set.summary_ids),
                selection_fingerprint=resolved_set.fingerprint,
                selection_policy=resolved_set.policy.model_dump(mode="json"),
                themes=themes,
                total_themes=len(themes),
                emerging_themes_count=len([t for t in themes if t.trend == ThemeTrend.EMERGING]),
                top_theme=themes[0].name if themes else None,
                processing_time_seconds=processing_time,
                model_used=self.model_used,
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

        # Get system prompt from configuration
        system_prompt = self.prompt_service.get_pipeline_prompt("theme_analysis")
        user_prompt = prompt

        # Call LLM for analysis with provider failover
        start_time = time.time()

        # Get providers for this model (in priority order)
        try:
            providers = self.model_config.get_providers_for_model(self.model)
        except ValueError as e:
            logger.error(f"No providers configured for model {self.model}: {e}")
            return []

        # Filter supported providers
        supported_providers = [
            p
            for p in providers
            if p.provider
            in [
                Provider.ANTHROPIC,
                Provider.AWS_BEDROCK,
                Provider.GOOGLE_VERTEX,
                Provider.MICROSOFT_AZURE,
                Provider.OPENAI,
                Provider.GOOGLE_AI,
            ]
        ]

        if not supported_providers:
            logger.error(f"No supported providers for model {self.model}")
            return []

        # Try each provider in order (failover support)
        response_text = None
        last_error = None

        for provider_config in supported_providers:
            try:
                logger.info(f"Trying provider: {provider_config.provider.value}")

                # LLMRouter resolves credentials from environment variables
                # (ANTHROPIC_API_KEY, AWS_REGION, etc.) — not from provider_config.api_key.
                # Only the provider enum is needed for routing.
                response = await self.llm_router.generate(
                    model=self.model,
                    provider=provider_config.provider,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=8000 if "claude" in self.model else 4000,
                    temperature=0.3,
                    step=ModelStep.THEME_ANALYSIS,
                )

                # Track provider and token usage
                self.provider_used = response.provider
                self.input_tokens = response.input_tokens
                self.output_tokens = response.output_tokens
                self.model_version = response.model_version
                self.model_used = response.selected_model or self.model

                response_text = response.text

                # Success - break out of failover loop
                break

            except Exception as e:
                error_msg = f"Error with provider {provider_config.provider.value}: {e!s}"
                logger.error(error_msg)
                last_error = str(e)
                continue  # Try next provider

        if response_text is None:
            logger.error(f"All providers failed. Last error: {last_error}")
            return []

        llm_time = time.time() - start_time

        # Calculate actual cost
        cost = self.model_config.calculate_cost(
            model_id=self.model_used,
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
            response_text,
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
                all_themes = list(dict.fromkeys(themes + theme_tags))

                context_parts.append(
                    f"## {content.get('publication', 'Unknown')} - {content['title']}\n"
                    f"Content ID: {content_id}\n"
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
        """Build prompt for LLM theme extraction from configurable template."""
        return self.prompt_service.render(
            "pipeline.theme_analysis.user_template",
            summary_context=summary_context,
            graphiti_context=graphiti_context,
            max_themes=str(max_themes),
            relevance_threshold=str(relevance_threshold),
        )

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
                available = {content["id"]: content for content in contents}
                requested_ids = theme_dict.get("content_ids", [])
                content_ids = list(
                    dict.fromkeys(
                        content_id for content_id in requested_ids if content_id in available
                    )
                )
                selected_dates = [
                    available[content_id]["published_date"] for content_id in content_ids
                ]
                fallback_date = contents[0]["published_date"] if contents else datetime.now()
                first_date = min(selected_dates, default=fallback_date)
                last_date = max(selected_dates, default=fallback_date)

                theme = ThemeData(
                    name=theme_dict["name"],
                    description=theme_dict["description"],
                    category=ThemeCategory(theme_dict["category"]),
                    mention_count=len(content_ids),
                    content_ids=content_ids,
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
