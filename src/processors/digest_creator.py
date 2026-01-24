"""Digest generator for creating multi-audience newsletter digests."""

import json
import time
from datetime import datetime

from anthropic import Anthropic

from src.config import settings
from src.config.models import ModelConfig, ModelStep, Provider
from src.models.content import Content, ContentStatus
from src.models.digest import (
    Digest,
    DigestData,
    DigestRequest,
    DigestSection,
    DigestStatus,
    DigestType,
)
from src.models.summary import Summary
from src.models.theme import ThemeAnalysisRequest, ThemeData
from src.processors.theme_analyzer import ThemeAnalyzer
from src.storage.database import get_db
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
    Creates structured digests from newsletter themes.

    Supports daily and weekly digests with multi-audience formatting.
    """

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        model: str | None = None,
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
        self.provider_used: Provider | None = None
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.model_version: str | None = None

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

        # 2. Get content items for source references
        contents = await self._fetch_contents(request.period_start, request.period_end)

        logger.info(f"Found {len(contents)} content items")

        # 2b. Fetch summaries for content items
        content_ids = [c["id"] for c in contents]

        with get_db() as db:
            summaries = (
                db.query(Summary).filter(Summary.content_id.in_(content_ids)).all()
                if content_ids
                else []
            )

        logger.info(f"Fetched {len(summaries)} summaries for {len(contents)} content items")

        # Check for missing summaries
        summary_content_ids = {s.content_id for s in summaries if s.content_id}
        missing_content_ids = [c["id"] for c in contents if c["id"] not in summary_content_ids]

        if missing_content_ids:
            logger.warning(
                f"{len(missing_content_ids)} content items do not have summaries yet. "
                f"They will be skipped. Run content summarization first."
            )

        # 3. Check token budget and determine if hierarchical digest is needed
        needs_hierarchy, budget_info = await self._check_token_budget(
            contents=contents,
            themes=theme_result.themes,
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
                themes=theme_result.themes,
                batches=batches,
                summaries=summaries,
            )

        else:
            # Single digest - existing flow (sources fit in budget)
            logger.info(f"Creating single digest ({len(contents)} items fit in budget)")

            digest_content = await self._generate_digest_content(
                request=request,
                themes=theme_result.themes,
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
                model_used=self.model,
                model_version=self.model_version,
            )

        # 5. Set processing time
        processing_time = time.time() - start_time
        digest.processing_time_seconds = processing_time

        # 6. Enrich with markdown content and theme tags
        digest = self._enrich_digest_data(digest)

        logger.info(
            f"Digest created successfully in {processing_time:.2f}s "
            f"({theme_result.newsletter_count} content items)"
        )

        return digest

    async def _check_token_budget(
        self,
        contents: list[dict],
        themes: list[ThemeData],
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

        # Fetch summaries for more accurate token estimation
        summaries = []
        try:
            content_ids = [c["id"] for c in contents]
            with get_db() as db:
                summaries = db.query(Summary).filter(Summary.content_id.in_(content_ids)).all()
            logger.debug(f"Loaded {len(summaries)} summaries for token estimation")
        except Exception as e:
            logger.warning(f"Failed to load summaries for token estimation: {e}")
            summaries = []

        # Estimate tokens for all content (including summaries)
        # Note: TokenCounter.estimate_newsletter_batch_tokens works with content dicts too
        estimated_tokens = counter.estimate_newsletter_batch_tokens(
            newsletters=contents,  # Works with content dicts
            themes=themes,
            summaries=summaries,
        )

        # Add content_budget key for clearer naming
        budget["content_budget"] = budget.get("newsletter_budget", budget.get("total", 0))
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

        Flow:
        1. For each batch, create sub-digest and save to DB
        2. Combine all sub-digests into parent digest
        3. Save parent with child references

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
        sub_digest_ids = []

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
                    model_used=self.model,
                    model_version=self.model_version,
                )

                # Save to database immediately
                with get_db() as db:
                    # Convert to dict, removing fields that aren't in DB model yet
                    sub_digest_dict = sub_digest.model_dump()
                    # Remove fields that will be added by database
                    sub_digest_dict.pop("processing_time_seconds", None)

                    db_sub_digest = Digest(**sub_digest_dict)
                    db_sub_digest.status = DigestStatus.COMPLETED
                    db_sub_digest.completed_at = datetime.utcnow()

                    db.add(db_sub_digest)
                    db.commit()
                    db.refresh(db_sub_digest)
                    sub_digest_ids.append(db_sub_digest.id)

                logger.info(
                    f"Sub-digest {i}/{len(batches)} created successfully (ID: {db_sub_digest.id})"
                )

            except Exception as e:
                logger.error(f"Failed to create sub-digest {i}/{len(batches)}: {e}")
                # Clean up any sub-digests created so far
                if sub_digest_ids:
                    logger.warning(f"Cleaning up {len(sub_digest_ids)} sub-digests due to error")
                    with get_db() as db:
                        db.query(Digest).filter(Digest.id.in_(sub_digest_ids)).delete(
                            synchronize_session=False
                        )
                        db.commit()
                raise Exception(f"Hierarchical digest creation failed: {e}")

        # Combine sub-digests into parent digest
        logger.info(f"Combining {len(sub_digest_ids)} sub-digests into parent digest")
        combined_digest = await self._combine_sub_digests(
            request=request,
            sub_digest_ids=sub_digest_ids,
            contents=contents,
        )

        # Set hierarchy metadata
        combined_digest.is_combined = True
        combined_digest.child_digest_ids = sub_digest_ids
        combined_digest.source_digest_count = len(sub_digest_ids)

        logger.info(
            f"Hierarchical digest created successfully with {len(sub_digest_ids)} "
            f"sub-digests (IDs: {sub_digest_ids})"
        )

        return combined_digest

    async def _combine_sub_digests(
        self,
        request: DigestRequest,
        sub_digest_ids: list[int],
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
            sub_digest_ids: List of sub-digest database IDs
            contents: Full list of all content items (for sources)

        Returns:
            Combined digest data

        Raises:
            Exception: If all providers fail
        """
        logger.info(f"Combining {len(sub_digest_ids)} sub-digests via LLM synthesis")

        # Load sub-digests from database
        with get_db() as db:
            sub_digests = db.query(Digest).filter(Digest.id.in_(sub_digest_ids)).all()

        if len(sub_digests) != len(sub_digest_ids):
            raise ValueError(
                f"Expected {len(sub_digest_ids)} sub-digests, found {len(sub_digests)}"
            )

        # Build combination prompt
        prompt = self._build_combination_prompt(
            request=request,
            sub_digests=sub_digests,
        )

        # Call LLM with provider failover (same pattern as _generate_digest_content)
        providers = self.model_config.get_providers_for_model(self.model)
        last_error = None

        for provider_config in providers:
            # Only use Anthropic providers for now (Claude models)
            if provider_config.provider != Provider.ANTHROPIC:
                continue

            try:
                logger.info(
                    f"Attempting combination with provider: {provider_config.provider.value}"
                )

                client = Anthropic(api_key=provider_config.api_key)
                provider_model_id = self.model_config.get_provider_model_id(
                    self.model, provider_config.provider
                )

                response = client.messages.create(
                    model=provider_model_id,
                    max_tokens=12000,
                    temperature=0.4,
                    messages=[{"role": "user", "content": prompt}],
                )

                # Parse response (same format as regular digest)
                raw_content = response.content[0].text.strip()
                logger.debug(f"Received LLM response: {raw_content[:200]}...")

                # Try to extract JSON from markdown code blocks if present
                if "```json" in raw_content:
                    start = raw_content.find("```json") + 7
                    end = raw_content.find("```", start)
                    raw_content = raw_content[start:end].strip()
                elif "```" in raw_content:
                    start = raw_content.find("```") + 3
                    end = raw_content.find("```", start)
                    raw_content = raw_content[start:end].strip()

                digest_json = json.loads(raw_content)

                # Convert sections to DigestSection objects
                strategic_insights = [
                    DigestSection(**section)
                    for section in digest_json.get("strategic_insights", [])
                ]
                technical_developments = [
                    DigestSection(**section)
                    for section in digest_json.get("technical_developments", [])
                ]
                emerging_trends = [
                    DigestSection(**section) for section in digest_json.get("emerging_trends", [])
                ]

                # Build combined digest
                combined_digest = DigestData(
                    digest_type=request.digest_type,  # DAILY or WEEKLY, not SUB_DIGEST
                    period_start=request.period_start,
                    period_end=request.period_end,
                    title=digest_json["title"],
                    executive_overview=digest_json["executive_overview"],
                    strategic_insights=strategic_insights,
                    technical_developments=technical_developments,
                    emerging_trends=emerging_trends,
                    actionable_recommendations=digest_json["actionable_recommendations"],
                    sources=self._build_sources(contents),
                    newsletter_count=len(contents),
                    agent_framework=self.framework,
                    model_used=self.model,
                    model_version=self.model_version,
                )

                logger.info(
                    f"Successfully combined sub-digests using {provider_config.provider.value}"
                )
                self.provider_used = provider_config.provider

                return combined_digest

            except Exception as e:
                last_error = e
                logger.error(
                    f"Provider {provider_config.provider.value} failed during combination: {e}"
                )
                continue

        # All providers failed - fallback to first sub-digest with warning
        logger.error(f"All providers failed during combination. Last error: {last_error}")
        logger.warning("Falling back to first sub-digest as combined digest (degraded mode)")

        # Convert first sub-digest to DigestData
        first_sub = sub_digests[0]
        fallback_digest = DigestData(
            digest_type=request.digest_type,  # Use original type, not SUB_DIGEST
            period_start=request.period_start,
            period_end=request.period_end,
            title=first_sub.title.replace(f" - Part 1 of {len(sub_digests)}", ""),
            executive_overview=first_sub.executive_overview,
            strategic_insights=[DigestSection(**s) for s in first_sub.strategic_insights],
            technical_developments=[DigestSection(**s) for s in first_sub.technical_developments],
            emerging_trends=[DigestSection(**s) for s in first_sub.emerging_trends],
            actionable_recommendations=first_sub.actionable_recommendations,
            sources=self._build_sources(contents),
            newsletter_count=len(contents),
            agent_framework=self.framework,
            model_used=self.model,
            model_version=self.model_version,
        )

        return fallback_digest

    def _build_combination_prompt(
        self,
        request: DigestRequest,
        sub_digests: list[Digest],
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
## Sub-Digest {i} ({sub.newsletter_count} newsletters)

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
- Creates coherent narrative spanning all newsletters
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

    def _format_sections_for_prompt(self, sections: list[dict]) -> str:
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
            formatted.append(f"{i}. {section.get('title', 'Untitled')}")

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
                error_msg = f"Error with provider {provider_config.provider.value}: {e!s}"
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

        return f"""You are creating an AI/technology content digest for technical leaders at Comcast.

# Time Period
{request.digest_type.value.title()} digest covering: {period_desc}

# Analyzed Themes ({theme_count} total)

{themes_context}

# Content Analyzed

{contents_context}

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

- **Relevant Links**: When newsletters include research papers, documentation, or other resources:
  - Include the actual URL in your detail points where relevant (e.g., "See research paper: https://arxiv.org/...")
  - Reference the link title and source newsletter ID for context
  - Make it easy for readers to access the original sources directly
  - Example: "BGE-M3 embeddings paper (https://arxiv.org/abs/2402.03216) from [42] demonstrates 15% improvement"

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

    async def _fetch_contents(
        self,
        start_date: datetime,
        end_date: datetime,
        status_filter: list[ContentStatus] | None = None,
    ) -> list[dict]:
        """
        Fetch content records for the time period.

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
                    "url": c.source_url,
                    "source_type": c.source_type.value,
                }
                for c in contents
            ]

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

    def _create_empty_digest(self, request: DigestRequest) -> DigestData:
        """Create an empty digest when no content found."""
        return DigestData(
            digest_type=request.digest_type,
            period_start=request.period_start,
            period_end=request.period_end,
            title=f"{request.digest_type.value.title()} Digest - No Content",
            executive_overview="No content was published during this period.",
            newsletter_count=0,
            agent_framework=self.framework,
            model_used=self.model,
        )
