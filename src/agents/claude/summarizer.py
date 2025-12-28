"""Claude SDK implementation for newsletter summarization."""

import json
import time
from typing import Any

from anthropic import Anthropic

from src.agents.base import AgentResponse, SummarizationAgent
from src.models.newsletter import Newsletter
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ClaudeAgent(SummarizationAgent):
    """Newsletter summarization using Claude SDK."""

    def __init__(self, model: str = "claude-haiku-4-5-20251001", api_key: str = "") -> None:
        """
        Initialize Claude agent.

        Args:
            model: Claude model to use (default: claude-haiku-4-5-20251001)
            api_key: Anthropic API key
        """
        super().__init__(model=model, api_key=api_key)
        self.client = Anthropic(api_key=api_key)
        logger.info(f"Initialized Claude agent with model: {model}")

    def summarize_newsletter(self, newsletter: Newsletter) -> AgentResponse:
        """
        Summarize a newsletter using Claude.

        Args:
            newsletter: Newsletter to summarize

        Returns:
            AgentResponse with SummaryData
        """
        logger.info(f"Summarizing newsletter: {newsletter.title}")
        start_time = time.time()

        try:
            # Create prompt
            prompt = self._create_summary_prompt(newsletter)

            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0.0,  # Deterministic for consistent summaries
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract response
            response_text = response.content[0].text
            logger.debug(f"Claude response: {response_text[:200]}...")

            # Parse JSON response
            try:
                summary_dict = json.loads(response_text)
            except json.JSONDecodeError as e:
                # Try to extract JSON from markdown code blocks
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    json_str = response_text[json_start:json_end].strip()
                    summary_dict = json.loads(json_str)
                elif "```" in response_text:
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    json_str = response_text[json_start:json_end].strip()
                    summary_dict = json.loads(json_str)
                else:
                    raise e

            # Validate and create SummaryData
            summary_data = self._validate_summary_data(summary_dict, newsletter.id)

            # Add processing metadata
            processing_time = time.time() - start_time
            summary_data.processing_time_seconds = processing_time
            summary_data.token_usage = response.usage.input_tokens + response.usage.output_tokens

            logger.info(
                f"Summarized in {processing_time:.2f}s, "
                f"tokens: {summary_data.token_usage}"
            )

            return AgentResponse(
                success=True,
                data=summary_data,
                metadata={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "processing_time": processing_time,
                },
            )

        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse Claude response as JSON: {e}"
            logger.error(error_msg)
            logger.error(f"Raw response: {response_text}")
            return AgentResponse(success=False, error=error_msg)

        except Exception as e:
            error_msg = f"Error during summarization: {str(e)}"
            logger.error(error_msg)
            return AgentResponse(success=False, error=error_msg)

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
