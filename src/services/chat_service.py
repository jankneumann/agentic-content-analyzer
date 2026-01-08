"""Multi-provider chat service with streaming support.

This service provides a unified interface for chat completions across multiple LLM providers:
- Anthropic (Claude)
- OpenAI (GPT)
- Google (Gemini)

Usage:
    from src.services.chat_service import ChatService
    from src.config.models import get_model_config

    chat_service = ChatService(get_model_config())

    async for chunk, metadata in chat_service.generate_response(
        messages=[{"role": "user", "content": "Hello!"}],
        model="claude-sonnet-4-5",
        system_prompt="You are a helpful assistant."
    ):
        if metadata:
            print(f"Finished: {metadata}")
        else:
            print(chunk, end="")
"""

import os
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from src.config.models import (
    MODEL_REGISTRY,
    ModelConfig,
    ModelFamily,
    Provider,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ChatMetadata:
    """Metadata returned after chat completion."""

    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    processing_time_ms: int
    cost_usd: float | None = None


class ChatService:
    """Multi-provider chat service with streaming support."""

    def __init__(self, model_config: ModelConfig):
        """Initialize the chat service.

        Args:
            model_config: Model configuration for provider routing and pricing
        """
        self.model_config = model_config

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        model: str,
        system_prompt: str | None = None,
    ) -> AsyncGenerator[tuple[str, ChatMetadata | None], None]:
        """Generate a streaming response from the LLM.

        Args:
            messages: List of message dicts with "role" and "content" keys
            model: Model ID (e.g., "claude-sonnet-4-5", "gpt-5.2", "gemini-2.0-flash")
            system_prompt: Optional system prompt

        Yields:
            Tuples of (content_chunk, metadata_or_none)
            - Content chunks have metadata=None
            - Final yield has empty content and full metadata
        """
        start_time = time.time()
        provider = self._get_provider_for_model(model)

        logger.info(f"Starting chat with model={model}, provider={provider.value}")

        try:
            if provider == Provider.ANTHROPIC:
                async for chunk, meta in self._stream_anthropic(
                    messages, model, system_prompt, start_time
                ):
                    yield chunk, meta
            elif provider == Provider.OPENAI:
                async for chunk, meta in self._stream_openai(
                    messages, model, system_prompt, start_time
                ):
                    yield chunk, meta
            elif provider == Provider.GOOGLE_AI:
                async for chunk, meta in self._stream_google(
                    messages, model, system_prompt, start_time
                ):
                    yield chunk, meta
            else:
                raise ValueError(f"Unsupported provider: {provider}")
        except Exception as e:
            logger.error(f"Chat error with {provider.value}: {e}")
            raise

    def _get_provider_for_model(self, model: str) -> Provider:
        """Get the provider for a model based on its family.

        Args:
            model: Model ID

        Returns:
            Provider enum value

        Raises:
            ValueError: If model not found in registry
        """
        model_info = MODEL_REGISTRY.get(model)
        if not model_info:
            raise ValueError(f"Unknown model: {model}. Available: {list(MODEL_REGISTRY.keys())}")

        # Map family to default provider
        family_to_provider = {
            ModelFamily.CLAUDE: Provider.ANTHROPIC,
            ModelFamily.GEMINI: Provider.GOOGLE_AI,
            ModelFamily.GPT: Provider.OPENAI,
        }

        return family_to_provider[model_info.family]

    async def _stream_anthropic(
        self,
        messages: list[dict[str, str]],
        model: str,
        system_prompt: str | None,
        start_time: float,
    ) -> AsyncGenerator[tuple[str, ChatMetadata | None], None]:
        """Stream response from Anthropic API.

        Uses synchronous streaming wrapped for async compatibility.
        """
        from anthropic import Anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        client = Anthropic(api_key=api_key)

        # Get provider-specific model ID
        provider_model_id = self.model_config.get_provider_model_id(model, Provider.ANTHROPIC)

        # Format messages for Anthropic
        formatted_messages = self._format_messages_anthropic(messages)

        logger.debug(
            f"Anthropic request: model={provider_model_id}, messages={len(formatted_messages)}"
        )

        # Use streaming
        with client.messages.stream(
            model=provider_model_id,
            max_tokens=4096,
            system=system_prompt or "",
            messages=formatted_messages,
        ) as stream:
            for text in stream.text_stream:
                yield text, None

            # Get final message for metadata
            response = stream.get_final_message()

        # Calculate metadata
        processing_time_ms = int((time.time() - start_time) * 1000)
        cost = self.model_config.calculate_cost(
            model,
            response.usage.input_tokens,
            response.usage.output_tokens,
            Provider.ANTHROPIC,
        )

        metadata = ChatMetadata(
            model=model,
            provider=Provider.ANTHROPIC.value,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            processing_time_ms=processing_time_ms,
            cost_usd=cost,
        )

        yield "", metadata

    async def _stream_openai(
        self,
        messages: list[dict[str, str]],
        model: str,
        system_prompt: str | None,
        start_time: float,
    ) -> AsyncGenerator[tuple[str, ChatMetadata | None], None]:
        """Stream response from OpenAI Chat Completions API."""
        from openai import AsyncOpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        client = AsyncOpenAI(api_key=api_key)

        # Get provider-specific model ID
        provider_model_id = self.model_config.get_provider_model_id(model, Provider.OPENAI)

        # Format messages for OpenAI
        formatted_messages = self._format_messages_openai(messages, system_prompt)

        logger.debug(
            f"OpenAI request: model={provider_model_id}, messages={len(formatted_messages)}"
        )

        # Track usage for final metadata
        input_tokens = 0
        output_tokens = 0

        stream = await client.chat.completions.create(
            model=provider_model_id,
            messages=formatted_messages,
            stream=True,
            stream_options={"include_usage": True},
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content, None
            if chunk.usage:
                input_tokens = chunk.usage.prompt_tokens
                output_tokens = chunk.usage.completion_tokens

        # Calculate metadata
        processing_time_ms = int((time.time() - start_time) * 1000)
        cost = self.model_config.calculate_cost(
            model,
            input_tokens,
            output_tokens,
            Provider.OPENAI,
        )

        metadata = ChatMetadata(
            model=model,
            provider=Provider.OPENAI.value,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            processing_time_ms=processing_time_ms,
            cost_usd=cost,
        )

        yield "", metadata

    async def _stream_google(
        self,
        messages: list[dict[str, str]],
        model: str,
        system_prompt: str | None,
        start_time: float,
    ) -> AsyncGenerator[tuple[str, ChatMetadata | None], None]:
        """Stream response from Google Generative AI API."""
        import google.generativeai as genai

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")

        genai.configure(api_key=api_key)

        # Get provider-specific model ID
        provider_model_id = self.model_config.get_provider_model_id(model, Provider.GOOGLE_AI)

        # Create model with system instruction
        gen_model = genai.GenerativeModel(
            provider_model_id,
            system_instruction=system_prompt if system_prompt else None,
        )

        # Format messages for Google
        history = self._format_messages_google(messages[:-1])  # All but last
        last_message = messages[-1]["content"] if messages else ""

        logger.debug(f"Google request: model={provider_model_id}, history={len(history)}")

        # Start chat and send message
        chat = gen_model.start_chat(history=history)
        response = await chat.send_message_async(last_message, stream=True)

        async for chunk in response:
            if chunk.text:
                yield chunk.text, None

        # Get usage metadata
        # Note: Google's API may not provide token counts in all cases
        input_tokens = (
            getattr(response.usage_metadata, "prompt_token_count", 0)
            if hasattr(response, "usage_metadata")
            else 0
        )
        output_tokens = (
            getattr(response.usage_metadata, "candidates_token_count", 0)
            if hasattr(response, "usage_metadata")
            else 0
        )

        # Calculate metadata
        processing_time_ms = int((time.time() - start_time) * 1000)
        cost = (
            self.model_config.calculate_cost(
                model,
                input_tokens,
                output_tokens,
                Provider.GOOGLE_AI,
            )
            if input_tokens > 0
            else None
        )

        metadata = ChatMetadata(
            model=model,
            provider=Provider.GOOGLE_AI.value,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            processing_time_ms=processing_time_ms,
            cost_usd=cost,
        )

        yield "", metadata

    def _format_messages_anthropic(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Format messages for Anthropic API.

        Anthropic uses role: "user" | "assistant" format.
        System messages are handled separately.
        """
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Skip system messages (handled separately)
            if role == "system":
                continue

            # Map roles
            if role in ("user", "assistant"):
                formatted.append({"role": role, "content": content})
            else:
                # Treat unknown roles as user
                formatted.append({"role": "user", "content": content})

        return formatted

    def _format_messages_openai(
        self, messages: list[dict[str, str]], system_prompt: str | None
    ) -> list[dict[str, Any]]:
        """Format messages for OpenAI Chat Completions API.

        OpenAI uses role: "system" | "user" | "assistant" format.
        """
        formatted = []

        # Add system message first
        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role in ("user", "assistant", "system"):
                formatted.append({"role": role, "content": content})
            else:
                formatted.append({"role": "user", "content": content})

        return formatted

    def _format_messages_google(self, messages: list[dict[str, str]]) -> list[dict[str, Any]]:
        """Format messages for Google Generative AI API.

        Google uses role: "user" | "model" format with parts array.
        """
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Map roles
            if role == "assistant":
                role = "model"
            elif role not in ("user", "model"):
                role = "user"

            formatted.append(
                {
                    "role": role,
                    "parts": [{"text": content}],
                }
            )

        return formatted
