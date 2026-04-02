"""Provider-agnostic LLM implementation for content summarization.

Routes through LLMRouter to support any configured provider (Anthropic, Google AI,
OpenAI, Bedrock, Vertex, Azure) instead of hardcoding Anthropic SDK calls.
"""

import json
import time
from typing import Any

from src.agents.base import AgentResponse, SummarizationAgent
from src.config.models import ModelConfig, ModelStep, Provider, ProviderConfig
from src.models.content import Content
from src.services.llm_router import LLMResponse, LLMRouter
from src.services.prompt_service import PromptService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class LLMSummarizationAgent(SummarizationAgent):
    """Content summarization using any configured LLM provider via LLMRouter."""

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        step: ModelStep = ModelStep.SUMMARIZATION,
        model: str | None = None,
        api_key: str | None = None,
        prompt_service: PromptService | None = None,
    ) -> None:
        """
        Initialize summarization agent.

        Args:
            model_config: Model configuration instance (required unless api_key provided)
            step: Pipeline step (default: SUMMARIZATION)
            model: Optional model override (for backward compatibility)
            api_key: Optional API key override (for backward compatibility)
            prompt_service: Optional PromptService for configurable prompts
        """
        # Backward compatibility: create minimal ModelConfig if api_key provided
        if model_config is None and api_key:
            model_config = ModelConfig()
            model_config.add_provider(ProviderConfig(provider=Provider.ANTHROPIC, api_key=api_key))

        if model_config is None:
            raise ValueError("Either model_config or api_key must be provided")

        super().__init__(
            model_config=model_config,
            step=step,
            model=model,
            api_key=api_key,
            prompt_service=prompt_service,
        )

        # Create LLMRouter for provider-agnostic generation
        self.router = LLMRouter(model_config)

        logger.info("Initialized LLMSummarizationAgent with model: %s", self.model)

    def summarize_content(self, content: Content) -> AgentResponse:
        """
        Summarize content using any configured LLM provider.

        Args:
            content: Content to summarize

        Returns:
            AgentResponse with SummaryData
        """
        source_type_str = content.source_type.value if content.source_type else "unknown"
        logger.info("Summarizing content: %s (source: %s)", content.title, source_type_str)

        prompt = self._create_content_prompt(content)
        system_prompt = self.prompt_service.get_pipeline_prompt("summarization")

        return self._generate_summary(
            system_prompt=system_prompt,
            user_prompt=prompt,
            content=content,
            source_type_str=source_type_str,
        )

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

        prompt = self._create_content_feedback_prompt(content, feedback_context)
        system_prompt = self.prompt_service.get_pipeline_prompt("summarization")

        return self._generate_summary(
            system_prompt=system_prompt,
            user_prompt=prompt,
            content=content,
            source_type_str=source_type_str,
        )

    def _generate_summary(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        content: Content,
        source_type_str: str,
    ) -> AgentResponse:
        """Generate a summary via LLMRouter (shared logic for both methods).

        Args:
            system_prompt: System prompt for the LLM
            user_prompt: User prompt with content
            content: Content being summarized (for metadata)
            source_type_str: Source type string for logging

        Returns:
            AgentResponse with SummaryData
        """
        start_time = time.time()

        try:
            llm_response: LLMResponse = self.router.generate_sync(
                model=self.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=4096,
                temperature=0.0,  # Deterministic for consistent summaries
            )
        except Exception as e:
            error_msg = f"LLM generation failed: {e!s}"
            logger.error(error_msg)
            return AgentResponse(success=False, error=error_msg)

        # Track provider and token usage for cost calculation
        self.provider_used = llm_response.provider
        self.input_tokens = llm_response.input_tokens
        self.output_tokens = llm_response.output_tokens
        self.model_version = llm_response.model_version

        try:
            # Parse JSON response
            response_text = llm_response.text
            logger.debug("LLM response: %s...", response_text[:200])

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

            provider_name = self.provider_used.value if self.provider_used else "unknown"
            logger.info(
                f"Summarized content in {processing_time:.2f}s, "
                f"tokens: {summary_data.token_usage}, "
                f"cost: ${cost:.4f}, "
                f"provider: {provider_name}"
            )

            return AgentResponse(
                success=True,
                data=summary_data,
                metadata={
                    "input_tokens": self.input_tokens,
                    "output_tokens": self.output_tokens,
                    "processing_time": processing_time,
                    "provider": provider_name,
                    "cost_usd": cost,
                    "content_id": content.id,
                    "source_type": source_type_str,
                },
            )

        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse response as JSON: {e}"
            logger.error(error_msg)
            return AgentResponse(success=False, error=error_msg)

        except Exception as e:
            error_msg = f"Error processing LLM response: {e!s}"
            logger.error(error_msg)
            return AgentResponse(success=False, error=error_msg)

    def _extract_json_from_response(self, response_text: str) -> dict[str, Any]:
        """
        Extract JSON from LLM response, handling markdown code blocks.

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

        return self.prompt_service.render(
            "pipeline.summarization.feedback_template",
            feedback_section=feedback_section,
            title=content.title,
            publication=content.publication or "Unknown",
            source_type=content.source_type.value if content.source_type else "Unknown",
            text_content=text_content[:15000],
        )


# Backward-compatible alias
ClaudeAgent = LLMSummarizationAgent
