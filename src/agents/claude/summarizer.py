"""Claude SDK implementation for content summarization."""

import json
import time
from typing import Any

from anthropic import Anthropic

from src.agents.base import AgentResponse, SummarizationAgent
from src.config.models import ModelConfig, ModelStep, Provider, ProviderConfig
from src.models.content import Content
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ClaudeAgent(SummarizationAgent):
    """Content summarization using Claude SDK."""

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        step: ModelStep = ModelStep.SUMMARIZATION,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """
        Initialize Claude agent.

        Args:
            model_config: Model configuration instance (required unless api_key provided)
            step: Pipeline step (default: SUMMARIZATION)
            model: Optional model override (for backward compatibility)
            api_key: Optional API key override (for backward compatibility)
        """
        # Backward compatibility: create minimal ModelConfig if api_key provided
        if model_config is None and api_key:
            model_config = ModelConfig()
            model_config.add_provider(ProviderConfig(provider=Provider.ANTHROPIC, api_key=api_key))

        if model_config is None:
            raise ValueError("Either model_config or api_key must be provided")

        super().__init__(model_config=model_config, step=step, model=model, api_key=api_key)
        logger.info(f"Initialized Claude agent with model: {self.model}")

    def summarize_content(self, content: Content) -> AgentResponse:
        """
        Summarize content from the unified Content model using Claude SDK.

        This method uses Content's markdown_content which is already in optimal
        format for LLM consumption, improving summarization quality.

        Args:
            content: Content to summarize

        Returns:
            AgentResponse with SummaryData
        """
        source_type_str = content.source_type.value if content.source_type else "unknown"
        logger.info(f"Summarizing content: {content.title} (source: {source_type_str})")
        start_time = time.time()

        # Get providers for this model (in priority order)
        try:
            providers = self.model_config.get_providers_for_model(self.model)
        except ValueError as e:
            return AgentResponse(success=False, error=str(e))

        # Filter for Anthropic-compatible providers
        anthropic_providers = [p for p in providers if p.provider == Provider.ANTHROPIC]

        if not anthropic_providers:
            error_msg = f"No Anthropic-compatible providers configured for model {self.model}"
            logger.error(error_msg)
            return AgentResponse(success=False, error=error_msg)

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

                # Create prompt using Content model
                prompt = self._create_content_prompt(content)

                # Call Claude API with provider-specific model ID
                response = client.messages.create(
                    model=provider_model_id,
                    max_tokens=4096,
                    temperature=0.0,  # Deterministic for consistent summaries
                    messages=[{"role": "user", "content": prompt}],
                )

                # Track provider and token usage for cost calculation
                self.provider_used = provider_config.provider
                self.input_tokens = response.usage.input_tokens
                self.output_tokens = response.usage.output_tokens
                self.model_version = self.model_config.get_model_version(
                    self.model, self.provider_used
                )

                # Extract response
                response_text = response.content[0].text
                logger.debug(f"Claude response: {response_text[:200]}...")

                # Parse JSON response
                summary_dict = self._extract_json_from_response(response_text)

                # Validate and create SummaryData with content_id
                summary_data = self._validate_summary_data(
                    summary_dict,
                    content_id=content.id,
                )

                # Add processing metadata
                processing_time = time.time() - start_time
                summary_data.processing_time_seconds = processing_time
                summary_data.token_usage = self.input_tokens + self.output_tokens

                # Calculate actual cost
                cost = self.calculate_cost()

                logger.info(
                    f"Summarized content in {processing_time:.2f}s, "
                    f"tokens: {summary_data.token_usage}, "
                    f"cost: ${cost:.4f}, "
                    f"provider: {self.provider_used.value}"
                )

                return AgentResponse(
                    success=True,
                    data=summary_data,
                    metadata={
                        "input_tokens": self.input_tokens,
                        "output_tokens": self.output_tokens,
                        "processing_time": processing_time,
                        "provider": self.provider_used.value,
                        "cost_usd": cost,
                        "content_id": content.id,
                        "source_type": source_type_str,
                    },
                )

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
        return AgentResponse(success=False, error=final_error)

    def _extract_json_from_response(self, response_text: str) -> dict[str, Any]:
        """
        Extract JSON from Claude response, handling markdown code blocks.

        Args:
            response_text: Raw response text

        Returns:
            Parsed JSON dictionary
        """
        # Try direct parse first
        try:
            return json.loads(response_text)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code blocks
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
            return json.loads(json_str)  # type: ignore[no-any-return]
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
            return json.loads(json_str)  # type: ignore[no-any-return]

        raise json.JSONDecodeError("Could not extract JSON from response", response_text, 0)

    def summarize_content_with_feedback(
        self, content: Content, feedback_context: str | None
    ) -> AgentResponse:
        """
        Regenerate a content summary with user feedback to guide improvements.

        Args:
            content: Content to summarize
            feedback_context: Formatted feedback and context selections from user

        Returns:
            AgentResponse with SummaryData
        """
        source_type_str = content.source_type.value if content.source_type else "unknown"
        logger.info(
            f"Regenerating content with feedback: {content.title} (source: {source_type_str})"
        )
        start_time = time.time()

        # Get providers for this model (in priority order)
        try:
            providers = self.model_config.get_providers_for_model(self.model)
        except ValueError as e:
            return AgentResponse(success=False, error=str(e))

        # Filter for Anthropic-compatible providers
        anthropic_providers = [p for p in providers if p.provider == Provider.ANTHROPIC]

        if not anthropic_providers:
            error_msg = f"No Anthropic-compatible providers configured for model {self.model}"
            logger.error(error_msg)
            return AgentResponse(success=False, error=error_msg)

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

                # Create prompt with feedback
                prompt = self._create_content_feedback_prompt(content, feedback_context)

                # Call Claude API with provider-specific model ID
                response = client.messages.create(
                    model=provider_model_id,
                    max_tokens=4096,
                    temperature=0.0,  # Deterministic for consistent summaries
                    messages=[{"role": "user", "content": prompt}],
                )

                # Track provider and token usage for cost calculation
                self.provider_used = provider_config.provider
                self.input_tokens = response.usage.input_tokens
                self.output_tokens = response.usage.output_tokens
                self.model_version = self.model_config.get_model_version(
                    self.model, self.provider_used
                )

                # Extract response
                response_text = response.content[0].text
                logger.debug(f"Claude response: {response_text[:200]}...")

                # Parse JSON response
                summary_dict = self._extract_json_from_response(response_text)

                # Validate and create SummaryData with content_id
                summary_data = self._validate_summary_data(
                    summary_dict,
                    content_id=content.id,
                )

                # Add processing metadata
                processing_time = time.time() - start_time
                summary_data.processing_time_seconds = processing_time
                summary_data.token_usage = self.input_tokens + self.output_tokens

                # Calculate actual cost
                cost = self.calculate_cost()

                logger.info(
                    f"Regenerated content with feedback in {processing_time:.2f}s, "
                    f"tokens: {summary_data.token_usage}, "
                    f"cost: ${cost:.4f}, "
                    f"provider: {self.provider_used.value}"
                )

                return AgentResponse(
                    success=True,
                    data=summary_data,
                    metadata={
                        "input_tokens": self.input_tokens,
                        "output_tokens": self.output_tokens,
                        "processing_time": processing_time,
                        "provider": self.provider_used.value,
                        "cost_usd": cost,
                    },
                )

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
        return AgentResponse(success=False, error=final_error)

    def _create_content_feedback_prompt(
        self, content: Content, feedback_context: str | None
    ) -> str:
        """
        Create the summarization prompt with user feedback incorporated for Content.

        Args:
            content: Content to summarize
            feedback_context: Formatted feedback and context from user

        Returns:
            Formatted prompt string with feedback instructions
        """
        # Use markdown_content which is in optimal format for LLM consumption
        text_content = content.markdown_content or content.raw_content or ""

        feedback_section = ""
        if feedback_context:
            feedback_section = f"""
A previous summary was generated for this content. The user has provided feedback to improve it.

**User Feedback and Context:**
{feedback_context}

Please regenerate the summary incorporating this feedback.
"""

        prompt = f"""You are an expert at summarizing AI and technology content for technical leaders and developers at Comcast.

Your audience ranges from CTOs needing strategic insights to individual developers seeking actionable best practices.
{feedback_section}
**Content Details:**
- Title: {content.title}
- Publication: {content.publication or "Unknown"}
- Source: {content.source_type.value if content.source_type else "Unknown"}

**Content:**
{text_content[:15000]}

**Required Output (JSON format):**
{{
    "executive_summary": "2-3 sentence summary capturing the essence and why it matters",
    "key_themes": ["theme1", "theme2", "theme3"],
    "strategic_insights": ["insight1", "insight2"],
    "technical_details": ["detail1", "detail2"],
    "actionable_items": ["action1", "action2"],
    "notable_quotes": ["quote1", "quote2"],
    "relevant_links": [
        {{"title": "Resource Title", "url": "https://..."}},
        {{"title": "Another Resource", "url": "https://..."}}
    ],
    "relevance_scores": {{
        "cto_leadership": 0.0-1.0,
        "technical_teams": 0.0-1.0,
        "individual_developers": 0.0-1.0
    }}
}}

Focus on:
- Strategic implications for AI/Data leadership
- Actionable technical insights
- Trends and patterns in the AI/tech landscape
- Practical applications for enterprise settings
- Best practices and recommendations
- Extract links to referenced papers, articles, or resources

Provide ONLY the JSON output, no additional commentary."""

        return prompt
