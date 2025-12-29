"""Digest generator for creating multi-audience newsletter digests."""

import json
import time
from datetime import datetime, timedelta
from typing import Optional

from anthropic import Anthropic

from src.config import settings
from src.config.models import ModelConfig, ModelStep, Provider
from src.models.digest import DigestData, DigestRequest, DigestSection, DigestType
from src.models.newsletter import Newsletter
from src.models.theme import ThemeAnalysisRequest, ThemeData
from src.processors.theme_analyzer import ThemeAnalyzer
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DigestCreator:
    """
    Creates structured digests from newsletter themes.

    Supports daily and weekly digests with multi-audience formatting.
    """

    def __init__(
        self,
        model_config: Optional[ModelConfig] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize digest creator.

        Args:
            model_config: Model configuration (defaults to settings.get_model_config())
            model: Optional model override (defaults to DIGEST_CREATION step model)
        """
        # Get model config from settings if not provided
        if model_config is None:
            model_config = settings.get_model_config()

        self.model_config = model_config

        # Get model for digest creation step (or use override)
        self.model = model or model_config.get_model_for_step(ModelStep.DIGEST_CREATION)

        # Determine framework based on model family
        model_family = model_config.get_family(self.model)
        self.framework = model_family.value

        # Track usage for cost calculation
        self.provider_used: Optional[Provider] = None
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.model_version: Optional[str] = None

        logger.info(f"Initialized DigestCreator with {self.model}")

    async def create_digest(
        self,
        request: DigestRequest,
    ) -> DigestData:
        """
        Create a digest for the specified time period.

        Args:
            request: Digest generation request

        Returns:
            Generated digest
        """
        start_time = time.time()
        logger.info(
            f"Creating {request.digest_type.value} digest "
            f"from {request.period_start} to {request.period_end}"
        )

        # 1. Run theme analysis for the period
        theme_request = ThemeAnalysisRequest(
            start_date=request.period_start,
            end_date=request.period_end,
            max_themes=15,  # Get enough themes to work with
            relevance_threshold=0.3,
        )

        analyzer = ThemeAnalyzer(model_config=self.model_config)
        theme_result = await analyzer.analyze_themes(
            theme_request,
            include_historical_context=request.include_historical_context,
        )

        if theme_result.newsletter_count == 0:
            logger.warning("No newsletters found in period")
            return self._create_empty_digest(request)

        logger.info(
            f"Analyzed {theme_result.newsletter_count} newsletters, "
            f"found {theme_result.total_themes} themes"
        )

        # 2. Get newsletters for source references
        newsletters = await self._fetch_newsletters(
            request.period_start,
            request.period_end
        )

        # 3. Generate digest content using LLM
        digest_content = await self._generate_digest_content(
            request=request,
            themes=theme_result.themes,
            newsletters=newsletters,
        )

        # 4. Build final digest
        processing_time = time.time() - start_time

        digest = DigestData(
            digest_type=request.digest_type,
            period_start=request.period_start,
            period_end=request.period_end,
            title=digest_content["title"],
            executive_overview=digest_content["executive_overview"],
            strategic_insights=digest_content["strategic_insights"],
            technical_developments=digest_content["technical_developments"],
            emerging_trends=digest_content["emerging_trends"],
            actionable_recommendations=digest_content["actionable_recommendations"],
            sources=self._build_sources(newsletters),
            newsletter_count=theme_result.newsletter_count,
            agent_framework=self.framework,
            model_used=self.model,
            model_version=self.model_version,
            processing_time_seconds=processing_time,
        )

        logger.info(
            f"Digest created successfully in {processing_time:.2f}s "
            f"({theme_result.newsletter_count} newsletters)"
        )

        return digest

    async def _generate_digest_content(
        self,
        request: DigestRequest,
        themes: list[ThemeData],
        newsletters: list[dict],
    ) -> dict:
        """Generate digest content using LLM."""
        logger.info("Generating digest content with LLM...")

        # Build context from themes
        themes_context = self._build_themes_context(themes)

        # Build newsletter list for reference
        newsletters_context = self._build_newsletters_context(newsletters)

        # Construct prompt
        prompt = self._build_digest_prompt(
            request=request,
            themes_context=themes_context,
            newsletters_context=newsletters_context,
            theme_count=len(themes),
        )

        # Call LLM with provider failover
        try:
            providers = self.model_config.get_providers_for_model(self.model)
        except ValueError as e:
            logger.error(f"No providers configured for model {self.model}: {e}")
            raise RuntimeError(f"No providers available for digest generation: {e}")

        # Filter for Anthropic-compatible providers
        anthropic_providers = [p for p in providers if p.provider == Provider.ANTHROPIC]

        if not anthropic_providers:
            logger.error(f"No Anthropic-compatible providers for model {self.model}")
            raise RuntimeError("No Anthropic providers available for digest generation")

        # Try each provider in order
        response = None
        last_error = None

        for provider_config in anthropic_providers:
            try:
                logger.info(f"Trying provider: {provider_config.provider.value}")
                client = Anthropic(api_key=provider_config.api_key)

                # Get provider-specific model ID for API call
                provider_model_id = self.model_config.get_provider_model_id(
                    self.model, provider_config.provider
                )

                response = client.messages.create(
                    model=provider_model_id,
                    max_tokens=12000,  # Longer for full digest
                    temperature=0.4,  # Slightly higher for narrative flow
                    messages=[{"role": "user", "content": prompt}],
                )

                # Track provider and token usage
                self.provider_used = provider_config.provider
                self.input_tokens = response.usage.input_tokens
                self.output_tokens = response.usage.output_tokens
                self.model_version = self.model_config.get_model_version(
                    self.model, self.provider_used
                )

                break  # Success

            except Exception as e:
                error_msg = f"Error with provider {provider_config.provider.value}: {str(e)}"
                logger.error(error_msg)
                last_error = str(e)
                continue

        if response is None:
            error_msg = f"All providers failed. Last error: {last_error}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Calculate actual cost
        cost = self.model_config.calculate_cost(
            model_id=self.model,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            provider=self.provider_used,
        )

        logger.info(
            f"Digest generation completed, "
            f"tokens: {self.input_tokens + self.output_tokens}, "
            f"cost: ${cost:.4f}, "
            f"provider: {self.provider_used.value}"
        )

        # Parse response
        try:
            response_text = response.content[0].text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])
                if response_text.startswith("json"):
                    response_text = response_text[4:].strip()

            digest_json = json.loads(response_text)

            # Convert sections to DigestSection objects
            digest_json["strategic_insights"] = [
                DigestSection(**section) for section in digest_json["strategic_insights"]
            ]
            digest_json["technical_developments"] = [
                DigestSection(**section) for section in digest_json["technical_developments"]
            ]
            digest_json["emerging_trends"] = [
                DigestSection(**section) for section in digest_json["emerging_trends"]
            ]

            return digest_json

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse digest JSON: {e}")
            logger.debug(f"Response: {response_text[:500]}")
            # Return minimal digest
            return {
                "title": f"{request.digest_type.value.title()} Digest",
                "executive_overview": "Digest generation encountered an error.",
                "strategic_insights": [],
                "technical_developments": [],
                "emerging_trends": [],
                "actionable_recommendations": {},
            }

    def _build_themes_context(self, themes: list[ThemeData]) -> str:
        """Build context string from themes."""
        context_parts = []

        for i, theme in enumerate(themes, 1):
            continuity = (
                f"\nContinuity: {theme.continuity_text}"
                if theme.continuity_text
                else ""
            )

            context_parts.append(
                f"{i}. {theme.name} ({theme.category.value}, {theme.trend.value})\n"
                f"   Relevance: {theme.relevance_score:.2f} "
                f"(Strategic: {theme.strategic_relevance:.2f}, "
                f"Tactical: {theme.tactical_relevance:.2f})\n"
                f"   Description: {theme.description}\n"
                f"   Key Points:\n"
                + "\n".join(f"   • {point}" for point in theme.key_points[:3])
                + continuity
            )

        return "\n\n".join(context_parts)

    def _build_newsletters_context(self, newsletters: list[dict]) -> str:
        """Build context string from newsletters with database ID references."""
        context_parts = []

        for newsletter in newsletters[:10]:  # Limit to avoid token overflow
            date = newsletter["published_date"].strftime("%Y-%m-%d")
            newsletter_id = newsletter["id"]
            context_parts.append(
                f"[{newsletter_id}] {newsletter['publication']} - {newsletter['title']} ({date})"
            )

        return "\n".join(context_parts)

    def _build_digest_prompt(
        self,
        request: DigestRequest,
        themes_context: str,
        newsletters_context: str,
        theme_count: int,
    ) -> str:
        """Build prompt for digest generation."""
        period_desc = (
            f"{request.period_start.strftime('%Y-%m-%d')} to "
            f"{request.period_end.strftime('%Y-%m-%d')}"
        )

        digest_type_guidance = {
            DigestType.DAILY: (
                "Focus on immediate insights and actionable items. "
                "Be concise but comprehensive. Highlight what's most important today."
            ),
            DigestType.WEEKLY: (
                "Provide broader context and trend analysis. "
                "Connect themes across the week. Identify patterns and shifts."
            ),
        }

        return f"""You are creating an AI/technology newsletter digest for technical leaders at Comcast.

# Time Period
{request.digest_type.value.title()} digest covering: {period_desc}

# Analyzed Themes ({theme_count} total)

{themes_context}

# Newsletters Analyzed

{newsletters_context}

# Your Task

Create a structured digest with multi-audience formatting. The audience ranges from CTO-level executives to individual developers.

{digest_type_guidance[request.digest_type]}

# Output Format

Provide a JSON response with:

```json
{{
  "title": "Concise digest title with date",
  "executive_overview": "2-3 paragraph overview for senior leadership. What matters most and why. What decisions need attention. Written for busy executives.",

  "strategic_insights": [
    {{
      "title": "Strategic Insight Title",
      "summary": "2-3 sentence summary of the insight [18][23]",
      "details": [
        "Specific point about business impact [18]",
        "Decision implications for leadership [23]",
        "Strategic considerations [18][24]"
      ],
      "themes": ["Related Theme 1", "Related Theme 2"],
      "continuity": "Historical context if available (from theme continuity)"
    }}
  ],

  "technical_developments": [
    {{
      "title": "Technical Development Title",
      "summary": "2-3 sentence summary for developers/practitioners [23][25]",
      "details": [
        "Technical details and implementation insights [23]",
        "How-to guidance or best practices [25]",
        "Tools, frameworks, or approaches mentioned [23][25]"
      ],
      "themes": ["Related Theme 1"],
      "continuity": "Historical context if available"
    }}
  ],

  "emerging_trends": [
    {{
      "title": "Emerging Trend Title",
      "summary": "2-3 sentence summary of what's new [24][26]",
      "details": [
        "Why this is emerging now [24]",
        "Potential impact or implications [26]",
        "What to watch for [24][26]"
      ],
      "themes": ["Related Theme 1"],
      "continuity": "Historical context showing how this evolved"
    }}
  ],

  "actionable_recommendations": {{
    "for_leadership": [
      "Specific strategic action",
      "Decision or investment to consider",
      "Risk to monitor"
    ],
    "for_teams": [
      "Tactical implementation",
      "Process or practice to adopt",
      "Capability to build"
    ],
    "for_individuals": [
      "Skill to develop",
      "Technology to learn",
      "Resource to explore"
    ]
  }}
}}
```

# Guidelines

- **Source Citations**: Use database ID references [18], [23], etc. throughout all content
  - IDs are the actual newsletter database IDs shown in brackets above (e.g., [18] = newsletter ID 18)
  - Add citations to summaries and detail points showing which newsletters support each claim
  - Use multiple citations [18][23] when a point draws from multiple sources
  - These IDs enable cross-digest traceability and interactive revision tool use
  - This provides transparency and traceability for all insights

- **Executive Overview**: Focus on "what matters and why" for decision-makers
- **Strategic Insights**: Limit to {request.max_strategic_insights} most important
  - CTO-level business impact and implications
  - Connect to Comcast's enterprise AI/data initiatives
  - Include continuity from historical context where relevant
  - Add source citations [18][23] to summary and each detail point
- **Technical Developments**: Limit to {request.max_technical_developments} most significant
  - Practitioner-level details and implementation guidance
  - Concrete tools, frameworks, techniques mentioned
  - Best practices and lessons learned
  - Add source citations [23][25] to summary and each detail point
- **Emerging Trends**: Limit to {request.max_emerging_trends} most noteworthy
  - New or rapidly evolving topics
  - MUST include historical continuity showing how they emerged
  - Future implications
  - Add source citations [24][26] to summary and each detail point
- **Actionable Recommendations**: Specific, role-based actions
  - Leadership: Strategic decisions, investments, risks
  - Teams: Implementations, processes, capabilities
  - Individuals: Skills, learning, tools

- Use professional but accessible tone
- Be specific - avoid generic statements
- Include continuity text from themes to show evolution
- Cross-reference themes where relevant
- Focus on what's actionable and decision-worthy

Provide ONLY the JSON, no other text."""

    async def _fetch_newsletters(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict]:
        """Fetch newsletters for the time period."""
        with get_db() as db:
            newsletters = (
                db.query(Newsletter)
                .filter(
                    Newsletter.published_date >= start_date,
                    Newsletter.published_date <= end_date,
                )
                .order_by(Newsletter.published_date.desc())
                .all()
            )

            return [
                {
                    "id": n.id,
                    "title": n.title,
                    "publication": n.publication,
                    "published_date": n.published_date,
                    "url": n.url,
                }
                for n in newsletters
            ]

    def _build_sources(self, newsletters: list[dict]) -> list[dict]:
        """Build sources list for digest."""
        return [
            {
                "title": n["title"],
                "publication": n["publication"],
                "date": n["published_date"].strftime("%Y-%m-%d"),
                "url": n.get("url"),
            }
            for n in newsletters
        ]

    def _create_empty_digest(self, request: DigestRequest) -> DigestData:
        """Create an empty digest when no newsletters found."""
        return DigestData(
            digest_type=request.digest_type,
            period_start=request.period_start,
            period_end=request.period_end,
            title=f"{request.digest_type.value.title()} Digest - No Content",
            executive_overview="No newsletters were published during this period.",
            newsletter_count=0,
            agent_framework=self.framework,
            model_used=self.model,
        )
