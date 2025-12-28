"""Claude SDK implementation for newsletter summarization."""

import json
import time
from typing import Any, Optional

from anthropic import Anthropic

from src.agents.base import AgentResponse, SummarizationAgent
from src.config.models import ModelConfig, ModelStep, Provider, ProviderConfig
from src.models.newsletter import Newsletter
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ClaudeAgent(SummarizationAgent):
    """Newsletter summarization using Claude SDK."""

    def __init__(
        self,
        model_config: Optional[ModelConfig] = None,
        step: ModelStep = ModelStep.SUMMARIZATION,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
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
            model_config.add_provider(
                ProviderConfig(provider=Provider.ANTHROPIC, api_key=api_key)
            )

        if model_config is None:
            raise ValueError("Either model_config or api_key must be provided")

        super().__init__(model_config=model_config, step=step, model=model, api_key=api_key)
        logger.info(f"Initialized Claude agent with model: {self.model}")

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

        # Filter for Anthropic-compatible providers (Anthropic, AWS Bedrock, etc.)
        # For now, only support direct Anthropic API
        # TODO: Add AWS Bedrock, Vertex AI, Azure support
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
                error_msg = f"Error with provider {provider_config.provider.value}: {str(e)}"
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
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code blocks
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
            return json.loads(json_str)
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
            return json.loads(json_str)

        raise json.JSONDecodeError(f"Could not extract JSON from response", response_text, 0)
