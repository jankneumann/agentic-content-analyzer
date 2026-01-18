"""Claude SDK implementation for newsletter summarization."""

import json
import time
from typing import TYPE_CHECKING, Any

from anthropic import Anthropic, AnthropicBedrock, AnthropicVertex

from src.agents.base import AgentResponse, SummarizationAgent
from src.config.models import ModelConfig, ModelStep, Provider, ProviderConfig
from src.models.newsletter import Newsletter
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.models.content import Content

logger = get_logger(__name__)


class ClaudeAgent(SummarizationAgent):
    """Newsletter summarization using Claude SDK."""

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

    def _get_client(self, provider_config: ProviderConfig) -> Any:
        """
        Create the appropriate Anthropic client based on the provider configuration.

        Args:
            provider_config: Provider configuration details

        Returns:
            Instantiated client (Anthropic, AnthropicBedrock, or AnthropicVertex)

        Raises:
            ValueError: If the provider is not supported
        """
        if provider_config.provider == Provider.ANTHROPIC:
            return Anthropic(api_key=provider_config.api_key)

        elif provider_config.provider == Provider.AWS_BEDROCK:
            # For AWS Bedrock, credentials are typically handled via environment variables
            # (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION) or IAM roles.
            # ProviderConfig might supply region if not in env.
            kwargs = {}
            if provider_config.region:
                kwargs["aws_region"] = provider_config.region

            return AnthropicBedrock(**kwargs)

        elif provider_config.provider == Provider.GOOGLE_VERTEX:
            # For Vertex AI, authentication is typically handled via Application Default Credentials (ADC)
            # or 'gcloud auth application-default login'.
            # Project ID and region are needed.
            kwargs = {}
            if provider_config.region:
                kwargs["region"] = provider_config.region
            if provider_config.project_id:
                kwargs["project_id"] = provider_config.project_id

            return AnthropicVertex(**kwargs)

        else:
            raise ValueError(f"Unsupported provider for ClaudeAgent: {provider_config.provider}")

    def summarize_newsletter(self, newsletter: Newsletter) -> AgentResponse:
        """
        Summarize a newsletter using Claude SDK with provider failover.

        Args:
            newsletter: Newsletter to summarize

        Returns:
            AgentResponse with SummaryData
        """
        logger.info(f"Summarizing newsletter: {newsletter.title}")
        start_time = time.time()

        # Get providers for this model (in priority order)
        try:
            providers = self.model_config.get_providers_for_model(self.model)
        except ValueError as e:
            return AgentResponse(success=False, error=str(e))

        # Filter for Anthropic-compatible providers (Anthropic, AWS Bedrock, Vertex AI)
        compatible_providers = [
            p for p in providers
            if p.provider in (Provider.ANTHROPIC, Provider.AWS_BEDROCK, Provider.GOOGLE_VERTEX)
        ]

        if not compatible_providers:
            error_msg = f"No Anthropic-compatible providers (Anthropic, Bedrock, Vertex) configured for model {self.model}"
            logger.error(error_msg)
            return AgentResponse(success=False, error=error_msg)

        # Try each provider in order (failover support)
        last_error = None
        for provider_config in compatible_providers:
            try:
                logger.info(f"Trying provider: {provider_config.provider.value}")

                # Create client for this provider
                client = self._get_client(provider_config)

                # Get provider-specific model ID for API call
                provider_model_id = self.model_config.get_provider_model_id(
                    self.model, provider_config.provider
                )

                # Create prompt
                prompt = self._create_summary_prompt(newsletter)

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

                # Validate and create SummaryData
                summary_data = self._validate_summary_data(summary_dict, newsletter.id)

                # Add processing metadata
                processing_time = time.time() - start_time
                summary_data.processing_time_seconds = processing_time
                summary_data.token_usage = self.input_tokens + self.output_tokens

                # Calculate actual cost
                cost = self.calculate_cost()

                logger.info(
                    f"Summarized in {processing_time:.2f}s, "
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

    def summarize_content(self, content: "Content") -> AgentResponse:
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
        compatible_providers = [
            p for p in providers
            if p.provider in (Provider.ANTHROPIC, Provider.AWS_BEDROCK, Provider.GOOGLE_VERTEX)
        ]

        if not compatible_providers:
            error_msg = f"No Anthropic-compatible providers configured for model {self.model}"
            logger.error(error_msg)
            return AgentResponse(success=False, error=error_msg)

        # Try each provider in order (failover support)
        last_error = None
        for provider_config in compatible_providers:
            try:
                logger.info(f"Trying provider: {provider_config.provider.value}")

                # Create client for this provider
                client = self._get_client(provider_config)

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

    def summarize_newsletter_with_feedback(
        self, newsletter: Newsletter, feedback_context: str
    ) -> AgentResponse:
        """
        Regenerate a summary with user feedback to guide improvements.

        Args:
            newsletter: Newsletter to summarize
            feedback_context: Formatted feedback and context selections from user

        Returns:
            AgentResponse with SummaryData
        """
        logger.info(f"Regenerating summary with feedback: {newsletter.title}")
        start_time = time.time()

        # Get providers for this model (in priority order)
        try:
            providers = self.model_config.get_providers_for_model(self.model)
        except ValueError as e:
            return AgentResponse(success=False, error=str(e))

        # Filter for Anthropic-compatible providers
        compatible_providers = [
            p for p in providers
            if p.provider in (Provider.ANTHROPIC, Provider.AWS_BEDROCK, Provider.GOOGLE_VERTEX)
        ]

        if not compatible_providers:
            error_msg = f"No Anthropic-compatible providers configured for model {self.model}"
            logger.error(error_msg)
            return AgentResponse(success=False, error=error_msg)

        # Try each provider in order (failover support)
        last_error = None
        for provider_config in compatible_providers:
            try:
                logger.info(f"Trying provider: {provider_config.provider.value}")

                # Create client for this provider
                client = self._get_client(provider_config)

                # Get provider-specific model ID for API call
                provider_model_id = self.model_config.get_provider_model_id(
                    self.model, provider_config.provider
                )

                # Create prompt with feedback
                prompt = self._create_feedback_prompt(newsletter, feedback_context)

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

                # Validate and create SummaryData
                summary_data = self._validate_summary_data(summary_dict, newsletter.id)

                # Add processing metadata
                processing_time = time.time() - start_time
                summary_data.processing_time_seconds = processing_time
                summary_data.token_usage = self.input_tokens + self.output_tokens

                # Calculate actual cost
                cost = self.calculate_cost()

                logger.info(
                    f"Regenerated with feedback in {processing_time:.2f}s, "
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

    def _create_feedback_prompt(self, newsletter: Newsletter, feedback_context: str) -> str:
        """
        Create the summarization prompt with user feedback incorporated.

        Args:
            newsletter: Newsletter to summarize
            feedback_context: Formatted feedback and context from user

        Returns:
            Formatted prompt string with feedback instructions
        """
        # Use text content, fall back to HTML if needed
        content = newsletter.raw_text or newsletter.raw_html or ""

        prompt = f"""You are an expert at summarizing AI and technology newsletters for technical leaders and developers at Comcast.

Your audience ranges from CTOs needing strategic insights to individual developers seeking actionable best practices.

A previous summary was generated for this newsletter. The user has provided feedback to improve it.

**User Feedback and Context:**
{feedback_context}

Please regenerate the summary incorporating this feedback.

**Newsletter Details:**
- Title: {newsletter.title}
- Publication: {newsletter.publication}
- Date: {newsletter.published_date}

**Content:**
{content[:15000]}  # Limit to ~15K chars to avoid token limits

**Required Output (JSON format):**
{{
    "executive_summary": "2-3 sentence summary capturing the essence and why it matters",
    "key_themes": ["theme1", "theme2", "theme3"],  # 3-5 main topics/themes
    "strategic_insights": ["insight1", "insight2"],  # CTO-level implications
    "technical_details": ["detail1", "detail2"],  # Developer-focused specifics
    "actionable_items": ["action1", "action2"],  # What readers should do
    "notable_quotes": ["quote1", "quote2"],  # Important quotes or data points
    "relevant_links": [  # Links to referenced resources for deeper reading
        {{"title": "Resource Title", "url": "https://..."}},
        {{"title": "Another Resource", "url": "https://..."}}
    ],
    "relevance_scores": {{
        "cto_leadership": 0.0-1.0,  # How relevant for C-level
        "technical_teams": 0.0-1.0,  # How relevant for dev teams
        "individual_developers": 0.0-1.0  # How relevant for individuals
    }}
}}

Focus on:
- Incorporating the user's feedback and suggestions
- Strategic implications for AI/Data leadership
- Actionable technical insights
- Trends and patterns in the AI/tech landscape
- Practical applications for enterprise settings
- Best practices and recommendations
- Extract links to referenced papers, articles, or resources (arxiv, research blogs, documentation, etc.)

Provide ONLY the JSON output, no additional commentary."""

        return prompt
