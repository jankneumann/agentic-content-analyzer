"""Digest revision processor with AI-powered interactive refinement."""

import json
from typing import Any

from anthropic import Anthropic
from sqlalchemy.orm import joinedload

from src.config.models import ModelConfig, ModelStep, Provider
from src.models.content import Content
from src.models.digest import Digest
from src.models.revision import RevisionContext, RevisionResult
from src.models.summary import Summary
from src.models.theme import ThemeAnalysis
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DigestReviser:
    """AI agent for interactive digest refinement.

    Uses Claude SDK with tool use for on-demand newsletter content fetching.
    Designed for both CLI and future web UI integration.
    """

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        model: str | None = None,
    ) -> None:
        """
        Initialize digest reviser.

        Args:
            model_config: Model configuration (defaults to global config)
            model: Optional model override (uses DIGEST_REVISION step by default)
        """
        from src.config import settings

        # Get model config from settings if not provided
        if model_config is None:
            model_config = settings.get_model_config()

        self.model_config = model_config

        # Use configured model for digest revision, or override
        self.model = model or self.model_config.get_model_for_step(ModelStep.DIGEST_REVISION)

        # Provider tracking (for cost calculation)
        self.provider_used: Provider | None = None
        self.input_tokens: int = 0
        self.output_tokens: int = 0

        logger.info(f"Initialized DigestReviser with model: {self.model}")

    async def load_context(self, digest_id: int) -> RevisionContext:
        """Load condensed context for revision (token-optimized).

        Loads:
        - Digest from database (full content)
        - Content summaries (condensed, already summarized)
        - Theme analysis (if available)
        - Content IDs for on-demand fetching via tools

        Args:
            digest_id: Digest ID to load

        Returns:
            RevisionContext with all necessary data

        Raises:
            ValueError: If digest not found
        """
        logger.info(f"Loading context for digest {digest_id}")

        with get_db() as db:
            # Load digest
            digest = db.query(Digest).filter_by(id=digest_id).first()

            if not digest:
                raise ValueError(f"Digest {digest_id} not found")

            # Load summaries for the period with eager loading of content relationship
            # to prevent DetachedInstanceError when accessing summary.content
            summaries = (
                db.query(Summary)
                .options(joinedload(Summary.content))
                .join(Content, Summary.content_id == Content.id)
                .filter(
                    Content.published_date >= digest.period_start,
                    Content.published_date <= digest.period_end,
                )
                .order_by(Content.published_date.desc())
                .all()
            )

            # Extract content IDs for on-demand fetching
            content_ids = [summary.content_id for summary in summaries if summary.content_id]

            logger.info(
                f"Loaded digest {digest_id} with {len(summaries)} summaries, "
                f"{len(content_ids)} content items available for on-demand fetching"
            )

            # Load theme analysis for the period
            # We look for an analysis that covers the exact same period
            theme_analysis = (
                db.query(ThemeAnalysis)
                .filter(
                    ThemeAnalysis.start_date == digest.period_start,
                    ThemeAnalysis.end_date == digest.period_end,
                )
                .order_by(ThemeAnalysis.analysis_date.desc())
                .first()
            )

            if theme_analysis:
                logger.info(f"Loaded theme analysis from {theme_analysis.analysis_date}")
            else:
                logger.info("No matching theme analysis found")

            return RevisionContext(
                digest=digest,
                summaries=summaries,
                theme_analysis=theme_analysis,
                content_ids=content_ids,
            )

    async def revise_section(
        self,
        context: RevisionContext,
        user_request: str,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> RevisionResult:
        """Process revision request with LLM (with tool use).

        Uses Anthropic SDK's tool use pattern to enable on-demand newsletter fetching.

        Args:
            context: Revision context (digest + summaries + newsletter IDs)
            user_request: User's revision request
            conversation_history: Previous turns in the conversation (optional)

        Returns:
            RevisionResult with revised content and explanation

        Raises:
            ValueError: If no Anthropic providers configured
            Exception: If all providers fail
        """
        logger.info(f"Processing revision request: {user_request[:100]}...")

        # Get providers for this model (in priority order)
        try:
            providers = self.model_config.get_providers_for_model(self.model)
        except ValueError as e:
            raise ValueError(f"No providers configured for model {self.model}: {e}")

        # Filter for Anthropic-compatible providers
        anthropic_providers = [p for p in providers if p.provider == Provider.ANTHROPIC]

        if not anthropic_providers:
            raise ValueError(f"No Anthropic-compatible providers configured for model {self.model}")

        # Try each provider in order (failover support)
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

                # Build messages with context and conversation history
                messages = self._build_messages(context, user_request, conversation_history)

                # Define tools for on-demand fetching
                tools = self._get_tool_definitions()

                # Tool use loop (Anthropic SDK pattern)
                tools_used = []
                max_iterations = 5  # Prevent infinite loops
                iteration = 0

                while iteration < max_iterations:
                    iteration += 1

                    # Call Claude API with tool use enabled
                    response = client.messages.create(
                        model=provider_model_id,
                        max_tokens=8000,
                        temperature=0.0,  # Deterministic for consistent revisions
                        tools=tools,
                        messages=messages,
                    )

                    # Track token usage
                    self.provider_used = provider_config.provider
                    self.input_tokens += response.usage.input_tokens
                    self.output_tokens += response.usage.output_tokens

                    # Check if tool use is needed
                    if response.stop_reason != "tool_use":
                        # Final response ready
                        break

                    # Process tool calls
                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            logger.info(f"LLM called tool: {block.name}")
                            tools_used.append(block.name)

                            # Handle tool call
                            tool_output = await self._handle_tool_call(
                                block.name, block.input, context
                            )

                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": tool_output,
                                }
                            )

                    # Continue conversation with tool results (Anthropic SDK pattern)
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({"role": "user", "content": tool_results})

                # Parse final response
                result = self._parse_revision_result(response, context)
                result.tools_used = tools_used

                logger.info(
                    f"Revision complete. Section: {result.section_modified}, "
                    f"Tools used: {tools_used}, "
                    f"Tokens: {self.input_tokens}/{self.output_tokens}"
                )

                return result

            except json.JSONDecodeError as e:
                error_msg = f"Failed to parse response as JSON: {e}"
                logger.error(f"{error_msg} (provider: {provider_config.provider.value})")
                last_error = error_msg
                continue  # Try next provider

            except Exception as e:
                error_msg = f"Error with provider {provider_config.provider.value}: {e!s}"
                logger.error(error_msg)
                last_error = str(e)
                continue  # Try next provider

        # All providers failed
        final_error = f"All providers failed. Last error: {last_error}"
        logger.error(final_error)
        raise Exception(final_error)

    async def _handle_tool_call(
        self, tool_name: str, tool_input: dict[str, Any], context: RevisionContext
    ) -> str:
        """Handle LLM tool calls during revision.

        Args:
            tool_name: Name of the tool being called
            tool_input: Tool input parameters
            context: Revision context with content IDs

        Returns:
            Tool result as string
        """
        if tool_name == "fetch_content":
            content_id = tool_input.get("content_id")

            if not content_id:
                return "Error: content_id is required"

            if context.content_ids is None or content_id not in context.content_ids:
                return f"Error: Content {content_id} not in current digest period"

            # Fetch from database
            with get_db() as db:
                content = db.query(Content).filter_by(id=content_id).first()

                if not content:
                    return f"Error: Content {content_id} not found"

                # Return condensed version (limit to 5K chars to avoid token overflow)
                text = content.markdown_content or content.raw_content or ""
                content_parts = [
                    f"Title: {content.title}",
                    f"Publication: {content.publication or 'Unknown'}",
                    f"Date: {content.published_date.strftime('%Y-%m-%d') if content.published_date else 'Unknown'}",
                    "",
                    "Content:",
                    text[:5000],
                ]

                if len(text) > 5000:
                    content_parts.append("\n[Content truncated to 5000 characters]")

                return "\n".join(content_parts)

        elif tool_name == "search_content":
            query = tool_input.get("query", "").lower()

            if not query:
                return "Error: query is required"

            # Search across summaries in context
            results = []
            for summary in context.summaries:
                # Get content for this summary
                content = summary.content
                if not content:
                    continue

                # Check executive summary
                if query in summary.executive_summary.lower():
                    results.append(f"- {content.title}: {summary.executive_summary[:200]}...")
                    continue

                # Check key themes
                if any(query in theme.lower() for theme in summary.key_themes):
                    results.append(
                        f"- {content.title} (Theme: {', '.join(summary.key_themes[:3])})"
                    )
                    continue

                # Check strategic insights
                for insight in summary.strategic_insights:
                    if query in str(insight).lower():
                        results.append(f"- {content.title}: {str(insight)[:150]}...")
                        break

            if not results:
                return f"No content found matching '{query}'"

            return f"Found {len(results)} content items matching '{query}':\n\n" + "\n".join(
                results[:5]  # Top 5 results
            )

        else:
            return f"Error: Unknown tool '{tool_name}'"

    def _get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions for Claude SDK.

        Returns:
            List of tool definitions in Anthropic SDK format
        """
        return [
            {
                "name": "fetch_content",
                "description": (
                    "Retrieve full content of a specific item when you need "
                    "detailed information beyond the summary. Use when the user asks "
                    "for specific details, quotes, or technical information."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "content_id": {
                            "type": "integer",
                            "description": "ID of the content item to fetch",
                        }
                    },
                    "required": ["content_id"],
                },
            },
            {
                "name": "search_content",
                "description": (
                    "Search across all content for specific topics or keywords. "
                    "Use when you need to find which content items discuss a particular "
                    "topic or concept."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "Search query (e.g., 'RAG architecture', 'LLM pricing')"
                            ),
                        }
                    },
                    "required": ["query"],
                },
            },
        ]

    def _build_messages(
        self,
        context: RevisionContext,
        user_request: str,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Build messages for Claude API with context and history.

        Args:
            context: Revision context
            user_request: Current user request
            conversation_history: Previous turns (optional)

        Returns:
            List of messages in Anthropic SDK format
        """
        messages = []

        # If conversation history exists, include it
        if conversation_history:
            messages.extend(conversation_history)

        # Build context prompt
        context_text = context.to_llm_context()

        # Build user message with context and request
        user_message = f"""You are helping to revise a newsletter digest. Your role is to improve the digest based on user feedback while maintaining quality standards.

{context_text}

---

## REVISION REQUEST

{user_request}

## INSTRUCTIONS

1. Analyze the user's request carefully
2. Use tools to fetch additional details if needed (fetch_newsletter_content, search_newsletters)
3. Make the requested revision while maintaining:
   - Professional but accessible tone
   - Strategic perspective with tactical grounding
   - Multi-audience balance (CTO-level + developer tactics)
   - Data-driven insights with specific metrics
4. Respond with a JSON object containing:
   - "section_modified": Which section you changed (e.g., "executive_overview", "strategic_insights")
   - "revised_content": The new content for that section
   - "explanation": Brief explanation of what you changed and why
   - "confidence_score": How confident you are in this revision (0.0-1.0)

Example response format:
```json
{{
  "section_modified": "executive_overview",
  "revised_content": "New executive overview text...",
  "explanation": "Made the summary more concise by focusing on the top 3 themes...",
  "confidence_score": 0.95
}}
```
"""

        messages.append({"role": "user", "content": user_message})

        return messages

    def _parse_revision_result(self, response: Any, context: RevisionContext) -> RevisionResult:
        """Parse Claude response into RevisionResult.

        Args:
            response: Claude API response
            context: Revision context

        Returns:
            RevisionResult with parsed data
        """
        # Extract response text
        response_text = ""
        for block in response.content:
            if block.type == "text":
                response_text += block.text

        logger.debug(f"Response text: {response_text[:500]}...")

        # Parse JSON response
        result_dict = self._extract_json_from_response(response_text)

        # Validate required fields
        required_fields = ["section_modified", "revised_content", "explanation"]
        for field in required_fields:
            if field not in result_dict:
                raise ValueError(f"Missing required field '{field}' in response")

        return RevisionResult(
            revised_content=result_dict["revised_content"],
            section_modified=result_dict["section_modified"],
            explanation=result_dict["explanation"],
            confidence_score=result_dict.get("confidence_score", 1.0),
        )

    def _extract_json_from_response(self, response_text: str) -> dict[str, Any]:
        """Extract JSON from Claude response, handling markdown code blocks.

        Args:
            response_text: Raw response text

        Returns:
            Parsed JSON dictionary
        """
        # Try direct parse first
        try:
            parsed: dict[str, Any] = json.loads(response_text)
            return parsed
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code blocks
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
            parsed = json.loads(json_str)
            return parsed
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
            parsed = json.loads(json_str)
            return parsed

        raise json.JSONDecodeError("Could not extract JSON from response", response_text, 0)

    async def apply_revision(
        self,
        digest: Digest,
        section: str,
        new_content: Any,
        increment_count: bool = True,
    ) -> Digest:
        """Update specific section of digest.

        Args:
            digest: Digest to update
            section: Section name to modify
            new_content: New content for the section
            increment_count: Whether to increment revision_count

        Returns:
            Updated digest (not saved to database yet)

        Raises:
            ValueError: If section name is invalid
        """
        logger.info(f"Applying revision to section: {section}")

        # Map section names to digest fields
        section_mapping = {
            "title": "title",
            "executive_overview": "executive_overview",
            "strategic_insights": "strategic_insights",
            "technical_developments": "technical_developments",
            "emerging_trends": "emerging_trends",
            "actionable_recommendations": "actionable_recommendations",
        }

        if section not in section_mapping:
            raise ValueError(
                f"Invalid section '{section}'. Valid sections: {list(section_mapping.keys())}"
            )

        # Update the field
        setattr(digest, section_mapping[section], new_content)

        # Increment revision count
        if increment_count:
            digest.revision_count += 1

        logger.info(f"Updated {section}, revision count: {digest.revision_count}")

        return digest

    def calculate_cost(self) -> float:
        """Calculate cost based on token usage.

        Returns:
            Total cost in USD
        """
        if not self.provider_used:
            return 0.0

        return self.model_config.calculate_cost(
            self.model,
            self.input_tokens,
            self.output_tokens,
            self.provider_used,
        )
