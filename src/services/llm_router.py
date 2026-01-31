"""Multi-provider LLM routing for pipeline processors.

This module provides a unified interface for routing LLM calls to different providers
with support for:
- Explicit provider selection (or automatic inference from model family)
- Simple text generation
- Function calling / tool use (agentic loops)
- Provider failover

Usage:
    from src.services.llm_router import LLMRouter, ToolDefinition

    router = LLMRouter(model_config)

    # Simple generation (auto-selects provider based on model family)
    response = await router.generate(
        model="gemini-2.5-flash",
        system_prompt="You are a helpful assistant.",
        user_prompt="Hello!",
    )

    # Explicit provider selection
    response = await router.generate(
        model="claude-sonnet-4-5",
        provider=Provider.AWS_BEDROCK,  # Use Bedrock instead of Anthropic
        system_prompt="...",
        user_prompt="...",
    )

    # With tools
    tools = [
        ToolDefinition(
            name="get_weather",
            description="Get weather for a location",
            parameters={
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        )
    ]
    response = await router.generate_with_tools(
        model="gemini-2.5-flash",
        system_prompt="...",
        user_prompt="...",
        tools=tools,
        tool_executor=my_tool_executor,
    )
"""

import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

from src.config.models import ModelConfig, ModelFamily, Provider
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ToolDefinition:
    """Provider-agnostic tool definition."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema format


@dataclass
class ToolCall:
    """A tool call from the model."""

    name: str
    arguments: dict[str, Any]
    id: str | None = None  # Provider-specific call ID


@dataclass
class LLMResponse:
    """Response from an LLM generation."""

    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    provider: Provider | None = None
    model_version: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_response: Any = None  # Provider-specific response for advanced usage


# Type alias for tool executor function
ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[str]]


class LLMRouter:
    """Route LLM calls to appropriate providers based on model and provider selection.

    This class provides a unified interface for:
    - Explicit provider selection (or automatic inference from model family)
    - Converting tool definitions to provider-specific formats
    - Handling agentic loops with tool use
    - Provider failover support
    """

    # Default provider mapping by model family
    DEFAULT_PROVIDERS: ClassVar[dict[ModelFamily, Provider]] = {
        ModelFamily.CLAUDE: Provider.ANTHROPIC,
        ModelFamily.GEMINI: Provider.GOOGLE_AI,
        ModelFamily.GPT: Provider.OPENAI,
    }

    def __init__(self, model_config: ModelConfig):
        """Initialize the router.

        Args:
            model_config: Model configuration for provider info and pricing
        """
        self.model_config = model_config

    def get_family(self, model: str) -> ModelFamily:
        """Get the model family for routing.

        Args:
            model: Model ID (e.g., "gemini-2.5-flash", "claude-sonnet-4-5")

        Returns:
            ModelFamily enum
        """
        model_info = self.model_config.get_model_info(model)
        return model_info.family

    def get_default_provider(self, model: str) -> Provider:
        """Get the default provider for a model based on its family.

        Args:
            model: Model ID

        Returns:
            Provider enum
        """
        family = self.get_family(model)
        return self.DEFAULT_PROVIDERS[family]

    def resolve_provider(self, model: str, provider: Provider | None = None) -> Provider:
        """Resolve the provider to use for a model.

        If provider is explicitly specified, validates it's available for the model.
        Otherwise, returns the default provider for the model's family.

        Args:
            model: Model ID
            provider: Optional explicit provider

        Returns:
            Provider to use

        Raises:
            ValueError: If specified provider doesn't support the model
        """
        if provider is None:
            return self.get_default_provider(model)

        # Validate that the model is available on the specified provider
        try:
            self.model_config.get_provider_model_config(model, provider)
            return provider
        except ValueError as e:
            raise ValueError(
                f"Model '{model}' is not available on provider '{provider.value}'. "
                f"Available providers: {self.get_available_providers(model)}"
            ) from e

    def get_available_providers(self, model: str) -> list[Provider]:
        """Get all providers that support a model.

        Args:
            model: Model ID

        Returns:
            List of available providers
        """
        from src.config.models import PROVIDER_MODEL_CONFIGS

        return [prov for (mid, prov) in PROVIDER_MODEL_CONFIGS.keys() if mid == model]

    def get_provider_model_id(self, model: str, provider: Provider | None = None) -> str:
        """Get the provider-specific model ID for API calls.

        Args:
            model: General model ID
            provider: Optional explicit provider (defaults to family default)

        Returns:
            Provider-specific model ID
        """
        resolved_provider = self.resolve_provider(model, provider)
        return self.model_config.get_provider_model_id(model, resolved_provider)

    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        provider: Provider | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a simple text response (no tools).

        Args:
            model: Model ID (e.g., "claude-sonnet-4-5", "gemini-2.5-flash")
            system_prompt: System instructions
            user_prompt: User message
            provider: Optional explicit provider. If None, uses family default.
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            LLMResponse with generated text

        Example:
            # Use default provider (Anthropic for Claude)
            response = await router.generate("claude-sonnet-4-5", ...)

            # Explicit provider (AWS Bedrock for Claude)
            response = await router.generate("claude-sonnet-4-5", provider=Provider.AWS_BEDROCK, ...)
        """
        import time

        resolved_provider = self.resolve_provider(model, provider)
        logger.info(f"Generating with model={model}, provider={resolved_provider.value}")

        start_time = time.monotonic()

        if resolved_provider == Provider.GOOGLE_AI:
            response = await self._generate_gemini(
                model, resolved_provider, system_prompt, user_prompt, max_tokens, temperature
            )
        elif resolved_provider in (
            Provider.ANTHROPIC,
            Provider.AWS_BEDROCK,
            Provider.GOOGLE_VERTEX,
        ):
            response = await self._generate_anthropic(
                model, resolved_provider, system_prompt, user_prompt, max_tokens, temperature
            )
        elif resolved_provider in (Provider.OPENAI, Provider.MICROSOFT_AZURE):
            response = await self._generate_openai(
                model, resolved_provider, system_prompt, user_prompt, max_tokens, temperature
            )
        else:
            raise ValueError(f"Unsupported provider: {resolved_provider}")

        duration_ms = (time.monotonic() - start_time) * 1000
        self._trace_llm_call(
            model=model,
            provider=resolved_provider.value,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=response,
            duration_ms=duration_ms,
            max_tokens=max_tokens,
        )

        return response

    async def generate_with_tools(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        tools: list[ToolDefinition],
        tool_executor: ToolExecutor,
        provider: Provider | None = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        max_iterations: int = 20,
    ) -> LLMResponse:
        """Generate with tool use in an agentic loop.

        The model can call tools multiple times before generating a final response.

        Args:
            model: Model ID
            system_prompt: System instructions
            user_prompt: User message
            tools: List of tool definitions
            tool_executor: Async function to execute tools: (name, args) -> result
            provider: Optional explicit provider. If None, uses family default.
            max_tokens: Maximum tokens per generation
            temperature: Sampling temperature
            max_iterations: Maximum agentic loop iterations

        Returns:
            LLMResponse with final text and usage stats
        """
        import time

        resolved_provider = self.resolve_provider(model, provider)
        logger.info(f"Generating with tools: model={model}, provider={resolved_provider.value}")

        start_time = time.monotonic()

        if resolved_provider == Provider.GOOGLE_AI:
            response = await self._generate_gemini_with_tools(
                model,
                resolved_provider,
                system_prompt,
                user_prompt,
                tools,
                tool_executor,
                max_tokens,
                temperature,
                max_iterations,
            )
        elif resolved_provider in (
            Provider.ANTHROPIC,
            Provider.AWS_BEDROCK,
            Provider.GOOGLE_VERTEX,
        ):
            response = await self._generate_anthropic_with_tools(
                model,
                resolved_provider,
                system_prompt,
                user_prompt,
                tools,
                tool_executor,
                max_tokens,
                temperature,
                max_iterations,
            )
        elif resolved_provider in (Provider.OPENAI, Provider.MICROSOFT_AZURE):
            response = await self._generate_openai_with_tools(
                model,
                resolved_provider,
                system_prompt,
                user_prompt,
                tools,
                tool_executor,
                max_tokens,
                temperature,
                max_iterations,
            )
        else:
            raise ValueError(f"Unsupported provider: {resolved_provider}")

        duration_ms = (time.monotonic() - start_time) * 1000
        self._trace_llm_call(
            model=model,
            provider=resolved_provider.value,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=response,
            duration_ms=duration_ms,
            max_tokens=max_tokens,
            metadata={"tool_count": len(tools), "max_iterations": max_iterations},
        )

        return response

    # =========================================================================
    # Telemetry
    # =========================================================================

    def _trace_llm_call(
        self,
        *,
        model: str,
        provider: str,
        system_prompt: str,
        user_prompt: str,
        response: LLMResponse,
        duration_ms: float,
        max_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an LLM call to the observability provider.

        Called after each generate() or generate_with_tools() call.
        Uses the lazy singleton from src.telemetry to avoid import-time
        side effects.
        """
        try:
            from src.telemetry import get_provider

            obs = get_provider()
            obs.trace_llm_call(
                model=model,
                provider=provider,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_text=response.text,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                duration_ms=duration_ms,
                max_tokens=max_tokens,
                metadata=metadata,
            )
        except Exception as e:
            # Never let telemetry failures break LLM calls
            logger.debug(f"Telemetry trace failed: {e}")

    # =========================================================================
    # Anthropic / Claude Implementation (Anthropic API, Bedrock, Vertex AI)
    # =========================================================================

    def _get_anthropic_client(self, provider: Provider):
        """Get Anthropic client configured for the specified provider.

        Args:
            provider: Provider to use (ANTHROPIC, AWS_BEDROCK, or GOOGLE_VERTEX)

        Returns:
            Configured Anthropic client
        """
        from anthropic import Anthropic, AnthropicBedrock, AnthropicVertex

        if provider == Provider.ANTHROPIC:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")
            return Anthropic(api_key=api_key)

        elif provider == Provider.AWS_BEDROCK:
            # Uses AWS credentials from environment/config
            region = os.environ.get("AWS_REGION", "us-east-1")
            return AnthropicBedrock(aws_region=region)

        elif provider == Provider.GOOGLE_VERTEX:
            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
            region = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
            if not project_id:
                raise RuntimeError("GOOGLE_CLOUD_PROJECT environment variable not set")
            return AnthropicVertex(project_id=project_id, region=region)

        else:
            raise ValueError(f"Provider {provider} not supported for Anthropic models")

    async def _generate_anthropic(
        self,
        model: str,
        provider: Provider,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Generate with Anthropic-compatible API (Anthropic, Bedrock, Vertex)."""
        client = self._get_anthropic_client(provider)
        provider_model_id = self.get_provider_model_id(model, provider)

        response = client.messages.create(
            model=provider_model_id,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )

        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text = block.text
                break

        return LLMResponse(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            provider=provider,
            model_version=self.model_config.get_model_version(model, provider),
            raw_response=response,
        )

    async def _generate_anthropic_with_tools(
        self,
        model: str,
        provider: Provider,
        system_prompt: str,
        user_prompt: str,
        tools: list[ToolDefinition],
        tool_executor: ToolExecutor,
        max_tokens: int,
        temperature: float,
        max_iterations: int,
    ) -> LLMResponse:
        """Generate with tools using Anthropic-compatible API."""
        client = self._get_anthropic_client(provider)
        provider_model_id = self.get_provider_model_id(model, provider)

        # Convert tools to Anthropic format
        anthropic_tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]

        messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
        total_input_tokens = 0
        total_output_tokens = 0
        tool_call_count = 0

        for iteration in range(max_iterations):
            logger.debug(f"Anthropic agentic loop iteration {iteration + 1}")

            response = client.messages.create(
                model=provider_model_id,
                system=system_prompt,
                messages=messages,
                tools=anthropic_tools,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_call_count += 1
                        result = await tool_executor(block.name, block.input)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            }
                        )

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                # Model finished
                text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text = block.text
                        break

                logger.info(
                    f"Anthropic completed after {iteration + 1} iterations, {tool_call_count} tool calls"
                )

                return LLMResponse(
                    text=text,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    provider=provider,
                    model_version=self.model_config.get_model_version(model, provider),
                    raw_response=response,
                )

        # Hit max iterations
        logger.warning(f"Hit max iterations ({max_iterations})")
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text = block.text
                break

        return LLMResponse(
            text=text,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            provider=provider,
            model_version=self.model_config.get_model_version(model, provider),
            raw_response=response,
        )

    # =========================================================================
    # Google / Gemini Implementation (Google AI Studio)
    # =========================================================================

    async def _generate_gemini(
        self,
        model: str,
        provider: Provider,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Generate with Google Gemini API."""
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY environment variable not set")

        client = genai.Client(api_key=api_key)
        provider_model_id = self.get_provider_model_id(model, provider)

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
            temperature=temperature,
        )

        response = client.models.generate_content(
            model=provider_model_id,
            contents=user_prompt,
            config=config,
        )

        text = ""
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    text = part.text
                    break

        input_tokens = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        output_tokens = (
            response.usage_metadata.candidates_token_count if response.usage_metadata else 0
        )

        return LLMResponse(
            text=text,
            input_tokens=input_tokens or 0,
            output_tokens=output_tokens or 0,
            provider=provider,
            model_version=self.model_config.get_model_version(model, provider),
            raw_response=response,
        )

    async def _generate_gemini_with_tools(
        self,
        model: str,
        provider: Provider,
        system_prompt: str,
        user_prompt: str,
        tools: list[ToolDefinition],
        tool_executor: ToolExecutor,
        max_tokens: int,
        temperature: float,
        max_iterations: int,
    ) -> LLMResponse:
        """Generate with tools using Google Gemini API."""
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY environment variable not set")

        client = genai.Client(api_key=api_key)
        provider_model_id = self.get_provider_model_id(model, provider)

        # Convert tools to Gemini format
        tool_declarations = [
            types.FunctionDeclaration(
                name=t.name,
                description=t.description,
                parameters_json_schema=t.parameters,
            )
            for t in tools
        ]
        gemini_tools = types.Tool(function_declarations=tool_declarations)

        contents = [types.Content(role="user", parts=[types.Part.from_text(user_prompt)])]

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[gemini_tools],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            max_output_tokens=max_tokens,
            temperature=temperature,
        )

        total_input_tokens = 0
        total_output_tokens = 0
        tool_call_count = 0

        for iteration in range(max_iterations):
            logger.debug(f"Gemini agentic loop iteration {iteration + 1}")

            response = client.models.generate_content(
                model=provider_model_id,
                contents=contents,
                config=config,
            )

            if response.usage_metadata:
                total_input_tokens += response.usage_metadata.prompt_token_count or 0
                total_output_tokens += response.usage_metadata.candidates_token_count or 0

            if response.function_calls:
                function_response_parts = []
                for fc in response.function_calls:
                    tool_call_count += 1
                    logger.debug(f"Gemini tool call: {fc.name}({fc.args})")
                    result = await tool_executor(fc.name, fc.args or {})
                    function_response_parts.append(
                        types.Part.from_function_response(
                            name=fc.name,
                            response={"result": result},
                        )
                    )

                contents.append(response.candidates[0].content)
                contents.append(types.Content(role="tool", parts=function_response_parts))
            else:
                # Model finished
                text = ""
                if response.candidates and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, "text") and part.text:
                            text = part.text
                            break

                logger.info(
                    f"Gemini completed after {iteration + 1} iterations, {tool_call_count} tool calls"
                )

                return LLMResponse(
                    text=text,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    provider=provider,
                    model_version=self.model_config.get_model_version(model, provider),
                    raw_response=response,
                )

        # Hit max iterations
        logger.warning(f"Hit max iterations ({max_iterations})")
        text = ""
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    text = part.text
                    break

        return LLMResponse(
            text=text,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            provider=provider,
            model_version=self.model_config.get_model_version(model, provider),
            raw_response=response,
        )

    # =========================================================================
    # OpenAI / GPT Implementation (OpenAI API, Azure OpenAI)
    # =========================================================================

    def _get_openai_client(self, provider: Provider):
        """Get OpenAI client configured for the specified provider.

        Args:
            provider: Provider to use (OPENAI or MICROSOFT_AZURE)

        Returns:
            Configured AsyncOpenAI client
        """
        from openai import AsyncAzureOpenAI, AsyncOpenAI

        if provider == Provider.OPENAI:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY environment variable not set")
            return AsyncOpenAI(api_key=api_key)

        elif provider == Provider.MICROSOFT_AZURE:
            api_key = os.environ.get("AZURE_OPENAI_API_KEY")
            endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
            api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
            if not api_key or not endpoint:
                raise RuntimeError(
                    "AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT environment variables required"
                )
            return AsyncAzureOpenAI(
                api_key=api_key,
                azure_endpoint=endpoint,
                api_version=api_version,
            )

        else:
            raise ValueError(f"Provider {provider} not supported for OpenAI models")

    async def _generate_openai(
        self,
        model: str,
        provider: Provider,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Generate with OpenAI-compatible API (OpenAI, Azure)."""
        client = self._get_openai_client(provider)
        provider_model_id = self.get_provider_model_id(model, provider)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = await client.chat.completions.create(
            model=provider_model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        text = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        return LLMResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            provider=provider,
            model_version=self.model_config.get_model_version(model, provider),
            raw_response=response,
        )

    async def _generate_openai_with_tools(
        self,
        model: str,
        provider: Provider,
        system_prompt: str,
        user_prompt: str,
        tools: list[ToolDefinition],
        tool_executor: ToolExecutor,
        max_tokens: int,
        temperature: float,
        max_iterations: int,
    ) -> LLMResponse:
        """Generate with tools using OpenAI-compatible API."""
        client = self._get_openai_client(provider)
        provider_model_id = self.get_provider_model_id(model, provider)

        # Convert tools to OpenAI format
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        total_input_tokens = 0
        total_output_tokens = 0
        tool_call_count = 0

        for iteration in range(max_iterations):
            logger.debug(f"OpenAI agentic loop iteration {iteration + 1}")

            response = await client.chat.completions.create(
                model=provider_model_id,
                messages=messages,
                tools=openai_tools,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            if response.usage:
                total_input_tokens += response.usage.prompt_tokens
                total_output_tokens += response.usage.completion_tokens

            choice = response.choices[0]

            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                # Process tool calls
                messages.append(choice.message)

                for tool_call in choice.message.tool_calls:
                    tool_call_count += 1
                    import json

                    args = json.loads(tool_call.function.arguments)
                    logger.debug(f"OpenAI tool call: {tool_call.function.name}({args})")
                    result = await tool_executor(tool_call.function.name, args)

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result,
                        }
                    )
            else:
                # Model finished
                text = choice.message.content or ""
                logger.info(
                    f"OpenAI completed after {iteration + 1} iterations, {tool_call_count} tool calls"
                )

                return LLMResponse(
                    text=text,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    provider=provider,
                    model_version=self.model_config.get_model_version(model, provider),
                    raw_response=response,
                )

        # Hit max iterations
        logger.warning(f"Hit max iterations ({max_iterations})")
        text = response.choices[0].message.content or ""

        return LLMResponse(
            text=text,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            provider=provider,
            model_version=self.model_config.get_model_version(model, provider),
            raw_response=response,
        )
