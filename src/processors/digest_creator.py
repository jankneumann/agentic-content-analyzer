"""Digest generator for creating multi-audience content digests."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

from src.telemetry.decorators import observe

if TYPE_CHECKING:
    from src.models.query import ResolvedContentSet

from src.config import settings
from src.config.models import ModelConfig, ModelStep, Provider
from src.models.digest import (
    DigestData,
    DigestRequest,
    DigestSection,
    DigestType,
)
from src.models.summary import Summary
from src.models.theme import ThemeAnalysisRequest, ThemeData
from src.processors.provenance import ExactContentSetLoader, ProvenanceViolationError
from src.processors.theme_analyzer import ThemeAnalyzer
from src.services.llm_router import LLMRouter
from src.services.prompt_service import PromptService
from src.utils.digest_markdown import (
    extract_digest_theme_tags,
    extract_source_content_ids,
    generate_digest_markdown,
)
from src.utils.logging import get_logger
from src.utils.token_counter import TokenCounter

logger = get_logger(__name__)


class DigestCreator:
    """
    Creates structured digests from content themes.

    Supports daily and weekly digests with multi-audience formatting.
    """

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        model: str | None = None,
        prompt_service: PromptService | None = None,
        content_loader: ExactContentSetLoader | None = None,
        llm_router: LLMRouter | None = None,
    ):
        """
        Initialize digest creator.

        Args:
            model_config: Model configuration (defaults to settings.get_model_config())
            model: Optional model override (defaults to DIGEST_CREATION step model)
            prompt_service: Optional PromptService for configurable prompts
        """
        # Get model config from settings if not provided
        if model_config is None:
            model_config = settings.get_model_config()

        self.model_config = model_config

        # Get model for digest creation step (or use override)
        self.model = model or model_config.get_model_for_step(ModelStep.DIGEST_CREATION)
        self.model_used = self.model
        self.prompt_service = prompt_service or PromptService()
        self.content_loader = content_loader or ExactContentSetLoader()
        self.llm_router = llm_router or LLMRouter(model_config)

        # Determine framework based on model family
        model_family = model_config.get_family(self.model)
        self.framework = model_family.value

        # Track usage for cost calculation
        self.provider_used: Provider | None = None
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.model_version: str | None = None

        logger.info(f"Initialized DigestCreator with {self.model}")

    @observe()
    async def create_digest(
        self,
        request: DigestRequest,
        resolved_set: ResolvedContentSet,
        *,
        themes: list[ThemeData] | None = None,
    ) -> DigestData:
        """
        Create a digest for the specified time period.

        Args:
            request: Digest generation request

        Returns:
            Generated digest
        """
        start_time = time.time()
        self.model_used = self.model
        self.provider_used = None
        self.input_tokens = 0
        self.output_tokens = 0
        self.model_version = None
        logger.info(
            f"Creating {request.digest_type.value} digest "
            f"from {request.period_start} to {request.period_end}"
        )

        loaded_items = self.content_loader.load(resolved_set)
        contents = [
            {
                "id": item.content.id,
                "title": item.content.title,
                "publication": item.content.publication,
                "published_date": resolved_item.selection_date,
                "url": item.content.source_url,
                "source_type": item.content.source_type.value,
            }
            for item, resolved_item in zip(loaded_items, resolved_set.items, strict=True)
        ]
        summaries = [item.summary for item in loaded_items]

        if not contents:
            logger.warning("No content found in period")
            return self._create_empty_digest(request, resolved_set)

        if themes is None:
            theme_request = ThemeAnalysisRequest(
                start_date=request.period_start,
                end_date=request.period_end,
                max_themes=15,
                relevance_threshold=0.3,
            )
            analyzer = ThemeAnalyzer(
                model_config=self.model_config,
                prompt_service=self.prompt_service,
                content_loader=self.content_loader,
                llm_router=self.llm_router,
            )
            theme_result = await analyzer.analyze_themes(
                theme_request,
                resolved_set,
                include_historical_context=request.include_historical_context,
            )
            themes = theme_result.themes

        self._validate_theme_provenance(themes, resolved_set)
        logger.info("Creating digest from %s exact content/summary pairs", len(contents))

        # 3. Check token budget and determine if hierarchical digest is needed
        needs_hierarchy, budget_info = await self._check_token_budget(
            contents=contents,
            themes=themes,
            summaries=summaries,
        )

        # 4. Create digest (hierarchical or single, based on token budget)
        if needs_hierarchy:
            logger.info(
                f"Sources exceed token budget ({len(contents)} items, "
                f"{budget_info['content_budget']} token budget). "
                f"Creating hierarchical digest..."
            )

            # Batch content by token budget
            batches = self._batch_contents_by_tokens(
                contents=contents,
                token_budget=budget_info["content_budget"],
            )

            # Create hierarchical digest (sub-digests + combination)
            digest = await self._create_hierarchical_digest(
                request=request,
                contents=contents,
                themes=themes,
                batches=batches,
                summaries=summaries,
            )

        else:
            # Single digest - existing flow (sources fit in budget)
            logger.info(f"Creating single digest ({len(contents)} items fit in budget)")

            digest_content = await self._generate_digest_content(
                request=request,
                themes=themes,
                contents=contents,
                summaries=summaries,
            )

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
                sources=self._build_sources(contents),
                newsletter_count=len(contents),  # Content count
                agent_framework=self.framework,
                model_used=self.model_used,
                model_version=self.model_version,
            )

        # 5. Set processing time
        processing_time = time.time() - start_time
        digest.processing_time_seconds = processing_time
        digest.source_content_ids = list(resolved_set.content_ids)
        digest.source_summary_ids = list(resolved_set.summary_ids)
        digest.selection_policy = resolved_set.policy.model_dump(mode="json")
        digest.selection_fingerprint = resolved_set.fingerprint
        digest.newsletter_count = resolved_set.eligible_content_count

        # 6. Enrich with markdown content and theme tags
        digest = self._enrich_digest_data(digest)

        logger.info(
            f"Digest created successfully in {processing_time:.2f}s "
            f"({resolved_set.eligible_content_count} content items)"
        )

        return digest

    async def _check_token_budget(
        self,
        contents: list[dict],
        themes: list[ThemeData],
        summaries: list[Summary],
    ) -> tuple[bool, dict]:
        """
        Check if contents fit in token budget.

        Args:
            contents: List of content dicts
            themes: List of theme data

        Returns:
            Tuple of (needs_hierarchy, budget_info)
            - needs_hierarchy: True if contents exceed budget
            - budget_info: Dict with token budget breakdown
        """
        logger.debug("Checking token budget for contents and themes")

        # Get first provider for this model
        try:
            providers = self.model_config.get_providers_for_model(self.model)
            provider = providers[0].provider if providers else Provider.ANTHROPIC
        except ValueError:
            logger.warning("No providers found, using ANTHROPIC as default")
            provider = Provider.ANTHROPIC

        # Initialize token counter
        counter = TokenCounter(self.model_config, self.model)

        # Calculate token budget
        budget = counter.calculate_token_budget(
            model_id=self.model,
            provider=provider,
            context_window_percentage=0.5,  # Use 50% of context window
        )

        # Estimate tokens for all content (including summaries)
        estimated_tokens = counter.estimate_content_batch_tokens(
            contents=contents,
            themes=themes,
            summaries=summaries,
        )

        # Use content_budget from token counter
        if "content_budget" not in budget:
            budget["content_budget"] = budget.get("total", 0)
        needs_hierarchy = estimated_tokens > budget["content_budget"]

        logger.info(
            f"Token budget check: {estimated_tokens} tokens estimated, "
            f"{budget['content_budget']} budget available. "
            f"Needs hierarchy: {needs_hierarchy}"
        )

        return needs_hierarchy, budget

    def _enrich_digest_data(self, digest: DigestData) -> DigestData:
        """
        Enrich digest data with markdown_content, theme_tags, and source_content_ids.

        Args:
            digest: DigestData object to enrich

        Returns:
            Enriched DigestData with additional fields populated
        """
        # Convert to dict for enrichment
        digest_dict = digest.model_dump()

        # Generate markdown content
        if not digest_dict.get("markdown_content"):
            digest_dict["markdown_content"] = generate_digest_markdown(digest_dict)

        # Extract theme tags
        if not digest_dict.get("theme_tags"):
            digest_dict["theme_tags"] = extract_digest_theme_tags(digest_dict)

        # Extract source content IDs
        if not digest_dict.get("source_content_ids"):
            digest_dict["source_content_ids"] = extract_source_content_ids(digest_dict)

        # Create new DigestData with enriched fields
        return DigestData(**digest_dict)

    def _batch_contents_by_tokens(
        self,
        contents: list[dict],
        token_budget: int,
    ) -> list[list[dict]]:
        """
        Batch contents to fit token budget.

        Uses greedy algorithm: add content items to batch until budget exceeded,
        then start new batch.

        Args:
            contents: List of content dicts (ordered chronologically)
            token_budget: Maximum tokens allowed per batch

        Returns:
            List of content batches (each batch is a list of content dicts)
        """

        logger.info(f"Batching {len(contents)} content items with {token_budget} token budget")

        counter = TokenCounter(self.model_config, self.model)
        batches: list[list[dict]] = []
        current_batch: list[dict] = []
        current_tokens = 0

        for content in contents:
            # Estimate tokens for this content item
            c_text = f"{content.get('publication', '')} - {content.get('title', '')}"
            c_tokens = counter.estimate_text_tokens(c_text)

            # Check if adding this content item would exceed budget
            if current_batch and current_tokens + c_tokens > token_budget:
                # Save current batch and start new one
                batches.append(current_batch)
                logger.debug(
                    f"Batch {len(batches)} complete: {len(current_batch)} content items, "
                    f"{current_tokens} tokens"
                )
                current_batch = [content]
                current_tokens = c_tokens
            else:
                # Add to current batch
                current_batch.append(content)
                current_tokens += c_tokens

        # Add final batch if not empty
        if current_batch:
            batches.append(current_batch)
            logger.debug(
                f"Batch {len(batches)} complete: {len(current_batch)} content items, "
                f"{current_tokens} tokens"
            )

        logger.info(f"Created {len(batches)} batches from {len(contents)} content items")

        # Log warning if single content item exceeds budget
        for i, batch in enumerate(batches):
            if len(batch) == 1:
                c = batch[0]
                logger.warning(
                    f"Batch {i + 1} contains single content item that may exceed budget: "
                    f"{c.get('publication')} - {c.get('title')}"
                )

        return batches

    async def _create_hierarchical_digest(
        self,
        request: DigestRequest,
        contents: list[dict],
        themes: list[ThemeData],
        batches: list[list[dict]],
        summaries: list[Summary],
    ) -> DigestData:
        """
        Create hierarchical digest from content batches.

        Sub-digests are transient generation data. The workflow owns persistence
        and reserves exactly one final digest resource.

        Args:
            request: Digest generation request
            contents: Full list of all content items
            themes: Theme analysis results
            batches: List of content batches (from _batch_contents_by_tokens)

        Returns:
            Combined parent digest with hierarchical metadata

        Raises:
            Exception: If sub-digest creation or combination fails
        """
        logger.info(
            f"Creating hierarchical digest with {len(batches)} sub-digests "
            f"from {len(contents)} content items"
        )
        sub_digests: list[DigestData] = []

        # Create sub-digests for each batch
        for i, batch in enumerate(batches, 1):
            logger.info(f"Creating sub-digest {i}/{len(batches)} with {len(batch)} content items")

            try:
                # Get summaries for this batch
                batch_ids = {c["id"] for c in batch}
                batch_summaries = [s for s in summaries if s.content_id in batch_ids]

                # Generate digest content for this batch
                digest_content = await self._generate_digest_content(
                    request=request,
                    themes=themes,
                    contents=batch,
                    summaries=batch_summaries,
                )

                # Create sub-digest with title suffix
                sub_digest = DigestData(
                    digest_type=DigestType.SUB_DIGEST,
                    period_start=request.period_start,
                    period_end=request.period_end,
                    title=f"{digest_content['title']} - Part {i} of {len(batches)}",
                    executive_overview=digest_content["executive_overview"],
                    strategic_insights=digest_content["strategic_insights"],
                    technical_developments=digest_content["technical_developments"],
                    emerging_trends=digest_content["emerging_trends"],
                    actionable_recommendations=digest_content["actionable_recommendations"],
                    sources=self._build_sources(batch),
                    newsletter_count=len(batch),
                    agent_framework=self.framework,
                    model_used=self.model_used,
                    model_version=self.model_version,
                )

                sub_digests.append(sub_digest)
                logger.info("Sub-digest %s/%s generated", i, len(batches))

            except Exception as e:
                logger.error(f"Failed to create sub-digest {i}/{len(batches)}: {e}")
                raise Exception(f"Hierarchical digest creation failed: {e}")

        # Combine sub-digests into parent digest
        logger.info(f"Combining {len(sub_digests)} sub-digests into parent digest")
        combined_digest = await self._combine_sub_digests(
            request=request,
            sub_digests=sub_digests,
            contents=contents,
        )

        # Set hierarchy metadata
        combined_digest.is_combined = True
        combined_digest.child_digest_ids = []
        combined_digest.source_digest_count = len(sub_digests)

        logger.info(f"Hierarchical digest created successfully with {len(sub_digests)} sub-digests")

        return combined_digest

    async def _combine_sub_digests(
        self,
        request: DigestRequest,
        sub_digests: list[DigestData],
        contents: list[dict],
    ) -> DigestData:
        """
        Combine multiple sub-digests into single digest via LLM synthesis.

        Uses LLM to:
        - De-duplicate similar insights across sub-digests
        - Re-prioritize based on full dataset
        - Create coherent narrative spanning all content items
        - Preserve source citations from all sub-digests

        Args:
            request: Original digest request
            sub_digests: Transient sub-digest generation results
            contents: Full list of all content items (for sources)

        Returns:
            Combined digest data

        Raises:
            Exception: If all providers fail
        """
        logger.info(f"Combining {len(sub_digests)} sub-digests via LLM synthesis")

        # Build combination prompt
        prompt = self._build_combination_prompt(
            request=request,
            sub_digests=sub_digests,
        )

        try:
            digest_json = await self._route_json(prompt, max_tokens=12000, temperature=0.4)
            return DigestData(
                digest_type=request.digest_type,
                period_start=request.period_start,
                period_end=request.period_end,
                title=digest_json["title"],
                executive_overview=digest_json["executive_overview"],
                strategic_insights=[
                    DigestSection(**section)
                    for section in digest_json.get("strategic_insights", [])
                ],
                technical_developments=[
                    DigestSection(**section)
                    for section in digest_json.get("technical_developments", [])
                ],
                emerging_trends=[
                    DigestSection(**section) for section in digest_json.get("emerging_trends", [])
                ],
                actionable_recommendations=digest_json["actionable_recommendations"],
                sources=self._build_sources(contents),
                newsletter_count=len(contents),
                agent_framework=self.framework,
                model_used=self.model_used,
                model_version=self.model_version,
            )
        except Exception as exc:
            logger.error("Digest combination failed through LLMRouter: %s", exc)
            logger.warning("Falling back to first sub-digest as combined digest (degraded mode)")

        # Convert first sub-digest to DigestData
        first_sub = sub_digests[0]
        fallback_digest = DigestData(
            digest_type=request.digest_type,  # Use original type, not SUB_DIGEST
            period_start=request.period_start,
            period_end=request.period_end,
            title=first_sub.title.replace(f" - Part 1 of {len(sub_digests)}", ""),
            executive_overview=first_sub.executive_overview,
            strategic_insights=first_sub.strategic_insights,
            technical_developments=first_sub.technical_developments,
            emerging_trends=first_sub.emerging_trends,
            actionable_recommendations=first_sub.actionable_recommendations,
            sources=self._build_sources(contents),
            newsletter_count=len(contents),
            agent_framework=self.framework,
            model_used=self.model_used,
            model_version=self.model_version,
        )

        return fallback_digest

    def _build_combination_prompt(
        self,
        request: DigestRequest,
        sub_digests: list[DigestData],
    ) -> str:
        """
        Build prompt for combining sub-digests.

        Args:
            request: Original digest request
            sub_digests: List of sub-digest database objects

        Returns:
            Prompt string for LLM
        """
        # Build summaries of each sub-digest
        sub_digest_summaries = []
        for i, sub in enumerate(sub_digests, 1):
            sub_digest_summaries.append(
                f"""
## Sub-Digest {i} ({sub.newsletter_count} content items)

**Executive Overview:**
{sub.executive_overview}

**Strategic Insights:** {len(sub.strategic_insights)} insights
{self._format_sections_for_prompt(sub.strategic_insights[:3])}

**Technical Developments:** {len(sub.technical_developments)} developments
{self._format_sections_for_prompt(sub.technical_developments[:3])}

**Emerging Trends:** {len(sub.emerging_trends)} trends
{self._format_sections_for_prompt(sub.emerging_trends[:2])}
"""
            )

        return f"""You are synthesizing {len(sub_digests)} sub-digests into a single comprehensive digest.

# Time Period
{request.digest_type.value.title()} digest covering {request.period_start.date()} to {request.period_end.date()}

# Sub-Digests to Combine
{"".join(sub_digest_summaries)}

# Your Task
Synthesize these sub-digests into a single comprehensive digest that:
- De-duplicates similar insights across sub-digests
- Re-prioritizes insights based on full dataset
- Creates coherent narrative spanning all content items
- Preserves source citations from all sub-digests
- Limits to {request.max_strategic_insights} strategic insights, {request.max_technical_developments} technical developments, {request.max_emerging_trends} emerging trends

# Output Format
Return a JSON object with the following structure:

{{
  "title": "Engaging title for the combined digest",
  "executive_overview": "2-3 sentence high-level summary",
  "strategic_insights": [
    {{
      "title": "Insight title",
      "summary": "2-3 sentence summary",
      "details": ["detail 1", "detail 2"],
      "themes": ["theme1", "theme2"],
      "continuity": "Historical context (optional)"
    }}
  ],
  "technical_developments": [
    {{
      "title": "Development title",
      "summary": "2-3 sentence summary",
      "details": ["detail 1", "detail 2"],
      "themes": ["theme1", "theme2"]
    }}
  ],
  "emerging_trends": [
    {{
      "title": "Trend title",
      "summary": "2-3 sentence summary",
      "details": ["detail 1", "detail 2"],
      "themes": ["theme1", "theme2"]
    }}
  ],
  "actionable_recommendations": {{
    "CTO/VP Engineering": ["recommendation 1", "recommendation 2"],
    "Team Leads": ["recommendation 1", "recommendation 2"],
    "Individual Contributors": ["recommendation 1", "recommendation 2"]
  }}
}}

Output only the JSON object, no additional text.
"""

    def _format_sections_for_prompt(self, sections: list[DigestSection] | list[dict]) -> str:
        """
        Format digest sections for inclusion in combination prompt.

        Args:
            sections: List of section dicts

        Returns:
            Formatted string
        """
        if not sections:
            return "(none)"

        formatted = []
        for i, section in enumerate(sections, 1):
            title = section.get("title", "Untitled") if isinstance(section, dict) else section.title
            formatted.append(f"{i}. {title}")

        return "\n".join(formatted)

    async def _generate_digest_content(
        self,
        request: DigestRequest,
        themes: list[ThemeData],
        contents: list[dict],
        summaries: list[Summary],
    ) -> dict:
        """Generate digest content using LLM."""
        logger.info("Generating digest content with LLM...")

        # Build context from themes
        themes_context = self._build_themes_context(themes)

        # Build content list for reference (using summaries)
        contents_context = self._build_contents_context(contents, summaries)

        # Construct prompt
        prompt = self._build_digest_prompt(
            request=request,
            themes_context=themes_context,
            contents_context=contents_context,
            theme_count=len(themes),
        )

        try:
            digest_json = await self._route_json(prompt, max_tokens=12000, temperature=0.4)

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
            # Return minimal digest
            return {
                "title": f"{request.digest_type.value.title()} Digest",
                "executive_overview": "Digest generation encountered an error.",
                "strategic_insights": [],
                "technical_developments": [],
                "emerging_trends": [],
                "actionable_recommendations": {},
            }

    async def _route_json(
        self,
        user_prompt: str,
        *,
        max_tokens: int,
        temperature: float,
    ) -> dict:
        """Route one digest generation call and preserve provider usage metadata."""

        response = await self.llm_router.generate(
            model=self.model,
            system_prompt=self.prompt_service.get_pipeline_prompt("digest_creation"),
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            step=ModelStep.DIGEST_CREATION,
        )
        self.provider_used = response.provider
        self.input_tokens += response.input_tokens
        self.output_tokens += response.output_tokens
        self.model_version = response.model_version
        self.model_used = response.selected_model or self.model
        cost = self.model_config.calculate_cost(
            model_id=self.model_used,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            provider=response.provider,
        )
        logger.info(
            "Digest LLM call completed: model=%s provider=%s tokens=%s cost=$%.4f",
            self.model_used,
            response.provider.value if response.provider else "unknown",
            response.input_tokens + response.output_tokens,
            cost,
        )
        raw_content = response.text.strip()
        if "```json" in raw_content:
            start = raw_content.find("```json") + 7
            end = raw_content.find("```", start)
            raw_content = raw_content[start:end].strip()
        elif raw_content.startswith("```"):
            lines = raw_content.split("\n")
            raw_content = "\n".join(lines[1:-1]).removeprefix("json").strip()
        return json.loads(raw_content)

    def _build_themes_context(self, themes: list[ThemeData]) -> str:
        """Build context string from themes."""
        context_parts = []

        for i, theme in enumerate(themes, 1):
            continuity = f"\nContinuity: {theme.continuity_text}" if theme.continuity_text else ""

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

    def _build_contents_context(self, contents: list[dict], summaries: list[Summary]) -> str:
        """Build context string from content summaries."""
        # Create lookup dict for quick access by content_id
        summaries_by_id = {s.content_id: s for s in summaries if s.content_id}

        context_parts = []

        for content in contents:
            content_id = content["id"]
            summary = summaries_by_id.get(content_id)

            if not summary:
                logger.warning(f"No summary found for content {content_id}, skipping")
                continue

            date = content["published_date"].strftime("%Y-%m-%d")

            # Build rich context from summary
            context = f"""[{content_id}] {content["publication"]} - {content["title"]} ({date})

**Executive Summary:**
{summary.executive_summary}

**Key Themes:** {", ".join(summary.key_themes or [])}

**Strategic Insights:**
{chr(10).join(f"- {insight}" for insight in (summary.strategic_insights or []))}

**Technical Details:**
{chr(10).join(f"- {detail}" for detail in (summary.technical_details or []))}"""

            # Add relevant links if available
            if summary.relevant_links:
                links_text = chr(10).join(
                    f"- {link.get('title', 'Resource')}: {link.get('url', '')}"
                    for link in summary.relevant_links
                )
                context += f"\n\n**Relevant Links:**\n{links_text}"

            context_parts.append(context.strip())

        return "\n\n---\n\n".join(context_parts)

    def _build_digest_prompt(
        self,
        request: DigestRequest,
        themes_context: str,
        contents_context: str,
        theme_count: int,
    ) -> str:
        """Build prompt for digest generation from configurable template."""
        period_desc = (
            f"{request.period_start.strftime('%Y-%m-%d')} to "
            f"{request.period_end.strftime('%Y-%m-%d')}"
        )

        digest_type_guidance_map = {
            DigestType.DAILY: (
                "Focus on immediate insights and actionable items. "
                "Be concise but comprehensive. Highlight what's most important today."
            ),
            DigestType.WEEKLY: (
                "Provide broader context and trend analysis. "
                "Connect themes across the week. Identify patterns and shifts."
            ),
        }

        return self.prompt_service.render(
            "pipeline.digest_creation.user_template",
            digest_type=request.digest_type.value.title(),
            period_desc=period_desc,
            theme_count=str(theme_count),
            themes_context=themes_context,
            contents_context=contents_context,
            digest_type_guidance=digest_type_guidance_map.get(request.digest_type, ""),
            max_strategic_insights=str(request.max_strategic_insights),
            max_technical_developments=str(request.max_technical_developments),
            max_emerging_trends=str(request.max_emerging_trends),
            max_followup_prompts=str(request.max_followup_prompts),
        )

    def _build_sources(self, contents: list[dict]) -> list[dict]:
        """
        Build sources list for digest.

        Args:
            contents: List of content dicts

        Returns:
            List of source dicts with title, publication, date, url, source_type, and content_id
        """
        sources = []
        for c in contents:
            source = {
                "title": c["title"],
                "publication": c["publication"],
                "date": c["published_date"].strftime("%Y-%m-%d"),
                "url": c.get("url"),
                "source_type": c.get("source_type"),
                "content_id": c.get("id"),
            }
            sources.append(source)
        return sources

    def _create_empty_digest(
        self, request: DigestRequest, resolved_set: ResolvedContentSet
    ) -> DigestData:
        """Create an empty digest when no content found."""
        return DigestData(
            digest_type=request.digest_type,
            period_start=request.period_start,
            period_end=request.period_end,
            title=f"{request.digest_type.value.title()} Digest - No Content",
            executive_overview="No content was published during this period.",
            newsletter_count=0,
            agent_framework=self.framework,
            model_used=self.model_used,
            source_content_ids=[],
            source_summary_ids=[],
            selection_fingerprint=resolved_set.fingerprint,
            selection_policy=resolved_set.policy.model_dump(mode="json"),
        )

    def _validate_theme_provenance(
        self,
        themes: list[ThemeData],
        resolved_set: ResolvedContentSet,
    ) -> None:
        """Reject themes that reference content outside the digest selection."""

        available = set(resolved_set.content_ids)
        outside = sorted(
            {
                content_id
                for theme in themes
                for content_id in theme.content_ids
                if content_id not in available
            }
        )
        if outside:
            raise ProvenanceViolationError(
                f"theme provenance contains content outside resolved set: {outside}"
            )
