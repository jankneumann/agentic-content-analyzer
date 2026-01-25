"""Historical context analyzer for theme evolution and continuity."""

import asyncio
import json
from datetime import datetime, timedelta

from anthropic import Anthropic

from src.config import settings
from src.config.models import ModelConfig, ModelStep, Provider
from src.models.theme import HistoricalMention, ThemeData, ThemeEvolution
from src.storage.graphiti_client import GraphitiClient
from src.utils.logging import get_logger

logger = get_logger(__name__)


class HistoricalContextAnalyzer:
    """
    Analyzes historical context and evolution of themes.

    Provides continuity and tracks how themes have developed over time.
    """

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        model: str | None = None,
    ):
        """
        Initialize historical context analyzer.

        Args:
            model_config: Model configuration (defaults to settings.get_model_config())
            model: Optional model override (defaults to HISTORICAL_CONTEXT step model)
        """
        # Get model config from settings if not provided
        if model_config is None:
            model_config = settings.get_model_config()

        self.model_config = model_config

        # Get model for historical context step (or use override)
        self.model = model or model_config.get_model_for_step(ModelStep.HISTORICAL_CONTEXT)

        self.graphiti_client: GraphitiClient | None = None

        # Track usage for cost calculation
        self.provider_used: Provider | None = None
        self.input_tokens: int = 0
        self.output_tokens: int = 0

        logger.info(f"Initialized HistoricalContextAnalyzer with {self.model}")

    async def enrich_themes_with_history(
        self,
        themes: list[ThemeData],
        current_date: datetime,
        lookback_days: int = 90,
    ) -> list[ThemeData]:
        """
        Enrich themes with historical context and evolution.

        Args:
            themes: List of current themes to enrich
            current_date: Current analysis date
            lookback_days: How far back to look for history

        Returns:
            Themes enriched with historical context
        """
        logger.info(f"Enriching {len(themes)} themes with historical context")

        self.graphiti_client = GraphitiClient()

        try:
            # Prepare tasks for concurrent execution
            tasks = []
            for theme in themes:
                logger.debug(f"Queueing history analysis for: {theme.name}")
                tasks.append(
                    self._analyze_theme_evolution(
                        theme_name=theme.name,
                        current_date=current_date,
                        lookback_days=lookback_days,
                    )
                )

            # Execute tasks concurrently
            evolutions = await asyncio.gather(*tasks)

            enriched_themes = []
            for theme, evolution in zip(themes, evolutions, strict=False):
                # Generate continuity text
                continuity = self._generate_continuity_text(
                    theme_name=theme.name,
                    evolution=evolution,
                    current_trend=theme.trend.value,
                )

                # Add to theme
                theme.historical_context = evolution
                theme.continuity_text = continuity

                enriched_themes.append(theme)

            logger.info(f"Enriched {len(enriched_themes)} themes with historical context")
            return enriched_themes

        finally:
            if self.graphiti_client:
                self.graphiti_client.close()

    async def _analyze_theme_evolution(
        self,
        theme_name: str,
        current_date: datetime,
        lookback_days: int,
    ) -> ThemeEvolution:
        """Analyze how a theme has evolved over time."""
        # Get historical mentions
        historical_mentions = await self.graphiti_client.get_historical_theme_mentions(
            theme_name=theme_name,
            before_date=current_date,
            lookback_days=lookback_days,
        )

        if not historical_mentions:
            # No historical data - this is truly new
            return ThemeEvolution(
                theme_name=theme_name,
                first_mention=current_date,
                total_mentions=0,
                mention_frequency="new",
                evolution_summary="This is a new theme, first appearing in this analysis period.",
                previous_discussions=[],
                recent_mentions=[],
            )

        # Build timeline
        timeline = await self.graphiti_client.get_theme_evolution_timeline(
            theme_name=theme_name,
            end_date=current_date,
        )

        # Convert to HistoricalMention objects
        recent_mentions = self._extract_recent_mentions(
            historical_mentions[:5],  # Last 5 mentions
        )

        # Determine first mention
        first_mention = (
            timeline[0]["timestamp"] if timeline else current_date - timedelta(days=lookback_days)
        )

        # Calculate frequency
        total_mentions = len(timeline)
        days_since_first = (current_date - first_mention).days or 1
        mentions_per_week = (total_mentions / days_since_first) * 7

        if mentions_per_week < 0.5:
            frequency = "rare"
        elif mentions_per_week < 1.5:
            frequency = "occasional"
        elif mentions_per_week < 3:
            frequency = "frequent"
        else:
            frequency = "constant"

        # Use LLM to analyze evolution
        (
            evolution_summary,
            previous_discussions,
            stance_change,
        ) = await self._analyze_evolution_with_llm(
            theme_name=theme_name,
            timeline=timeline,
            recent_mentions=historical_mentions[:10],
        )

        return ThemeEvolution(
            theme_name=theme_name,
            first_mention=first_mention,
            total_mentions=total_mentions,
            mention_frequency=frequency,
            evolution_summary=evolution_summary,
            previous_discussions=previous_discussions,
            stance_change=stance_change,
            recent_mentions=recent_mentions,
        )

    def _extract_recent_mentions(
        self,
        mentions: list[dict],
    ) -> list[HistoricalMention]:
        """Convert raw mentions to HistoricalMention objects."""
        historical_mentions = []

        for mention in mentions:
            # Get content details
            timestamp = mention.get("timestamp", datetime.now())

            # Extract context snippet (first 200 chars of content)
            content = mention.get("content", "")
            context = content[:200] + "..." if len(content) > 200 else content

            historical_mentions.append(
                HistoricalMention(
                    date=timestamp,
                    newsletter_id=0,  # Not available from Graphiti directly
                    newsletter_title=mention.get("title", "Unknown"),
                    publication=mention.get("source", "Unknown"),
                    context=context,
                )
            )

        return historical_mentions

    async def _analyze_evolution_with_llm(
        self,
        theme_name: str,
        timeline: list[dict],
        recent_mentions: list[dict],
    ) -> tuple[str, list[str], str | None]:
        """
        Use LLM to analyze how a theme has evolved.

        Returns:
            (evolution_summary, previous_discussions, stance_change)
        """
        if not timeline:
            return (
                "No historical data available.",
                [],
                None,
            )

        # Build context from timeline
        timeline_context = self._build_timeline_context(timeline)

        # Build prompt
        prompt = f"""Analyze how the theme "{theme_name}" has evolved based on historical content mentions.

# Historical Timeline

{timeline_context}

# Your Task

Provide a JSON response with:
1. **evolution_summary**: 1-2 sentence summary of how this theme has evolved
2. **previous_discussions**: List of 2-4 key points from previous discussions (specific insights, not just "discussed")
3. **stance_change**: How the stance/sentiment has changed over time (or null if consistent)

# Output Format

```json
{{
  "evolution_summary": "Brief summary of evolution",
  "previous_discussions": [
    "Specific insight 1",
    "Specific insight 2",
    "Specific insight 3"
  ],
  "stance_change": "How sentiment/stance changed, or null"
}}
```

# Guidelines

- Focus on how the discussion has changed, not just that it occurred
- Identify shifts in perspective, new developments, or changing priorities
- Be specific about what changed and when
- If stance has been consistent, set stance_change to null

Provide ONLY the JSON, no other text."""

        # Call LLM with provider failover
        try:
            providers = self.model_config.get_providers_for_model(self.model)
        except ValueError as e:
            logger.error(f"No providers configured for model {self.model}: {e}")
            return ("No provider available.", [], None)

        # Filter for Anthropic-compatible providers
        anthropic_providers = [p for p in providers if p.provider == Provider.ANTHROPIC]

        if not anthropic_providers:
            logger.error(f"No Anthropic-compatible providers for model {self.model}")
            return ("No provider available.", [], None)

        # Try each provider in order
        response = None
        for provider_config in anthropic_providers:
            try:
                logger.debug(f"Trying provider: {provider_config.provider.value}")
                client = Anthropic(api_key=provider_config.api_key)

                response = client.messages.create(
                    model=self.model,
                    max_tokens=1500,
                    temperature=0.3,
                    messages=[{"role": "user", "content": prompt}],
                )

                # Track provider and token usage
                self.provider_used = provider_config.provider
                self.input_tokens = response.usage.input_tokens
                self.output_tokens = response.usage.output_tokens

                break  # Success

            except Exception as e:
                logger.error(f"Error with provider {provider_config.provider.value}: {e}")
                continue

        if response is None:
            logger.error("All providers failed for evolution analysis")
            return ("Provider error.", [], None)

        # Parse response
        try:
            response_text = response.content[0].text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])
                if response_text.startswith("json"):
                    response_text = response_text[4:].strip()

            result = json.loads(response_text)

            return (
                result.get("evolution_summary", "Theme has evolved over time."),
                result.get("previous_discussions", []),
                result.get("stance_change"),
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse evolution analysis: {e}")
            return (
                "Unable to analyze evolution.",
                [],
                None,
            )

    def _build_timeline_context(self, timeline: list[dict]) -> str:
        """Build timeline context for LLM."""
        if not timeline:
            return "No historical mentions found."

        context_parts = []
        for i, mention in enumerate(timeline[-10:], 1):  # Last 10 mentions
            date = mention.get("timestamp", "Unknown date")
            if isinstance(date, datetime):
                date = date.strftime("%Y-%m-%d")

            title = mention.get("title", "Unknown")
            content = mention.get("content", "")[:200]  # First 200 chars

            context_parts.append(f"{i}. {date} - {title}\n   {content}...")

        return "\n\n".join(context_parts)

    def _generate_continuity_text(
        self,
        theme_name: str,
        evolution: ThemeEvolution,
        current_trend: str,
    ) -> str:
        """Generate human-readable continuity text."""
        if evolution.total_mentions == 0:
            return f"**New Theme**: {theme_name} is appearing for the first time."

        # Calculate time since first mention
        days_since = (datetime.now() - evolution.first_mention).days

        if days_since < 7:
            time_ref = "this week"
        elif days_since < 30:
            time_ref = "this month"
        elif days_since < 90:
            time_ref = f"{days_since // 30} months ago"
        else:
            time_ref = f"{days_since // 30} months ago"

        # Build continuity text
        if current_trend == "emerging":
            return (
                f"**Emerging Theme**: First discussed {time_ref}, "
                f"{theme_name} is gaining traction. "
                f"{evolution.evolution_summary}"
            )
        elif current_trend == "growing":
            return (
                f"**Growing Theme**: Previously discussed {time_ref} "
                f"({evolution.mention_frequency} mentions), "
                f"{theme_name} is increasing in prominence. "
                f"{evolution.evolution_summary}"
            )
        elif current_trend == "established":
            return (
                f"**Established Theme**: Consistently discussed since {time_ref} "
                f"({evolution.total_mentions} mentions), "
                f"{theme_name} remains a core topic. "
                f"{evolution.evolution_summary}"
            )
        elif current_trend == "declining":
            return (
                f"**Declining Theme**: Previously frequent {time_ref}, "
                f"{theme_name} is appearing less often. "
                f"{evolution.evolution_summary}"
            )
        else:
            return (
                f"**Recurring Theme**: Discussed {evolution.total_mentions} times since {time_ref}. "
                f"{evolution.evolution_summary}"
            )
