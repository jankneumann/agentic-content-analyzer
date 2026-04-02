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
        # --- Agentic extensions (all optional, backward-compatible) ---
        enable_reflection: bool = False,
        reflection_prompt: str | None = None,
        memory_context: list[Any] | None = None,
        cost_limit: float | None = None,
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
            enable_reflection: If True, model reviews its output after tool loop completes.
                If reflection identifies issues, the loop may continue. (agentic-analysis.18)
            reflection_prompt: Custom reflection instruction. Default asks model to review
                quality and completeness of its response.
            memory_context: List of memory entries to inject as context. Appended to
                system prompt as prior knowledge. (agentic-analysis.18)
            cost_limit: Maximum USD cost for this generation. If exceeded, returns
                partial results. Tracks cost via input/output token counts and
                model pricing. (agentic-analysis.18, agentic-analysis.21)

        Returns:
            LLMResponse with final text and usage stats
        """
        import time

        resolved_provider = self.resolve_provider(model, provider)
        logger.info(f"Generating with tools: model={model}, provider={resolved_provider.value}")

        # Inject memory context into system prompt if provided
        if memory_context:
            memory_text = "\n\n## Prior Knowledge (from memory)\n"
            for entry in memory_context:
                content = getattr(entry, "content", str(entry))
                memory_text += f"- {content}\n"
            system_prompt = system_prompt + memory_text

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

        # Cost limit check
        if cost_limit is not None:
            estimated_cost = self._estimate_cost(
                response.input_tokens, response.output_tokens, model
            )
            if estimated_cost > cost_limit:
                logger.warning(
                    f"Cost limit exceeded: ${estimated_cost:.4f} > ${cost_limit:.2f}. "
                    "Returning partial results."
                )
                duration_ms = (time.monotonic() - start_time) * 1000
                self._trace_llm_call(
                    model=model,
                    provider=resolved_provider.value,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response=response,
                    duration_ms=duration_ms,
                    max_tokens=max_tokens,
                    metadata={"tool_count": len(tools), "cost_limit_exceeded": True},
                )
                return response

        # Reflection step (agentic-analysis.18)
        if enable_reflection:
            response = await self._reflect_on_response(
                model=model,
                provider=resolved_provider,
                system_prompt=system_prompt,
                response=response,
                reflection_prompt=reflection_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        duration_ms = (time.monotonic() - start_time) * 1000
        self._trace_llm_call(
            model=model,
            provider=resolved_provider.value,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=response,
            duration_ms=duration_ms,
            max_tokens=max_tokens,
            metadata={"tool_count": len(tools), "max_iterations": max_iterations,
                       "reflection": enable_reflection},
        )

        return response

    async def generate_with_planning(
        self,
        goal: str,
        model: str,
        tools: list[ToolDefinition],
        tool_executor: ToolExecutor,
        system_prompt: str = "",
        provider: Provider | None = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        max_plan_steps: int = 5,
        max_iterations_per_step: int = 10,
        max_revisions: int = 2,
        memory_context: list[Any] | None = None,
        cost_limit: float | None = None,
    ) -> LLMResponse:
        """Generate with an explicit planning phase before tool execution.

        First asks the model to create a step-by-step plan, then executes
        each step via generate_with_tools(). The model can revise the plan
        based on intermediate results. (agentic-analysis.19)

        Args:
            goal: The high-level goal to accomplish
            model: Model ID
            tools: Available tools for each step
            tool_executor: Tool execution function
            system_prompt: System instructions
            provider: Optional explicit provider
            max_tokens: Maximum tokens per generation
            temperature: Sampling temperature
            max_plan_steps: Maximum number of steps in the plan (default 5)
            max_iterations_per_step: Max tool iterations per step (default 10)
            max_revisions: Max times the plan can be revised (default 2)
            memory_context: Memory entries to inject as context
            cost_limit: Total USD cost limit across all steps

        Returns:
            LLMResponse with synthesized results from all plan steps
        """
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost = 0.0
        step_results: list[str] = []

        # Phase 1: Create the plan
        planning_prompt = (
            f"Create a step-by-step plan to accomplish this goal:\n\n{goal}\n\n"
            f"Return a numbered list of up to {max_plan_steps} concrete steps. "
            "Each step should be a specific action that can be accomplished with the available tools. "
            "Format: one step per line, numbered 1-N."
        )

        plan_response = await self.generate(
            model=model,
            system_prompt=system_prompt + (
                "\n\nYou are in planning mode. Create a clear, actionable plan."
            ),
            user_prompt=planning_prompt,
            provider=provider,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        total_input_tokens += plan_response.input_tokens
        total_output_tokens += plan_response.output_tokens

        # Parse plan steps
        plan_text = plan_response.text
        steps = [
            line.strip() for line in plan_text.strip().split("\n")
            if line.strip() and any(line.strip().startswith(f"{i}") for i in range(1, 20))
        ]
        steps = steps[:max_plan_steps]

        if not steps:
            # Fallback: treat the entire response as a single step
            steps = [plan_text.strip()]

        logger.info(f"Planning phase complete: {len(steps)} steps")

        # Phase 2: Execute each step
        revisions_remaining = max_revisions
        step_idx = 0

        while step_idx < len(steps):
            step = steps[step_idx]
            logger.info(f"Executing plan step {step_idx + 1}/{len(steps)}: {step[:80]}...")

            # Cost check before each step
            if cost_limit is not None and total_cost >= cost_limit:
                logger.warning(f"Cost limit reached (${total_cost:.4f}). Returning partial results.")
                break

            remaining_budget = None
            if cost_limit is not None:
                remaining_budget = cost_limit - total_cost

            step_context = ""
            if step_results:
                step_context = "\n\nResults from previous steps:\n" + "\n".join(
                    f"Step {i+1}: {r[:200]}" for i, r in enumerate(step_results)
                )

            step_response = await self.generate_with_tools(
                model=model,
                system_prompt=system_prompt + step_context,
                user_prompt=f"Execute this plan step:\n{step}",
                tools=tools,
                tool_executor=tool_executor,
                provider=provider,
                max_tokens=max_tokens,
                temperature=temperature,
                max_iterations=max_iterations_per_step,
                memory_context=memory_context,
                cost_limit=remaining_budget,
            )

            total_input_tokens += step_response.input_tokens
            total_output_tokens += step_response.output_tokens
            total_cost += self._estimate_cost(
                step_response.input_tokens, step_response.output_tokens, model
            )
            step_results.append(step_response.text)
            step_idx += 1

            # Allow plan revision after each step (if revisions remain)
            if revisions_remaining > 0 and step_idx < len(steps):
                revision_prompt = (
                    f"You completed step {step_idx} with this result:\n{step_response.text[:500]}\n\n"
                    f"Remaining steps:\n" + "\n".join(f"  {s}" for s in steps[step_idx:]) + "\n\n"
                    "Should the remaining plan be revised? Reply 'NO REVISION NEEDED' if the plan is fine, "
                    "or provide a revised numbered list of remaining steps."
                )
                revision_response = await self.generate(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=revision_prompt,
                    provider=provider,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                total_input_tokens += revision_response.input_tokens
                total_output_tokens += revision_response.output_tokens

                if "NO REVISION NEEDED" not in revision_response.text.upper():
                    # Parse revised steps
                    revised = [
                        line.strip() for line in revision_response.text.strip().split("\n")
                        if line.strip() and any(line.strip().startswith(f"{i}") for i in range(1, 20))
                    ]
                    if revised:
                        steps = steps[:step_idx] + revised[:max_plan_steps - step_idx]
                        revisions_remaining -= 1
                        logger.info(f"Plan revised. {revisions_remaining} revisions remaining.")

        # Phase 3: Synthesize results
        synthesis_prompt = (
            f"You executed a {len(step_results)}-step plan for this goal:\n{goal}\n\n"
            "Step results:\n" + "\n".join(
                f"Step {i+1}: {r}" for i, r in enumerate(step_results)
            ) + "\n\nSynthesize these results into a coherent final response."
        )

        synthesis_response = await self.generate(
            model=model,
            system_prompt=system_prompt,
            user_prompt=synthesis_prompt,
            provider=provider,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        total_input_tokens += synthesis_response.input_tokens
        total_output_tokens += synthesis_response.output_tokens

        return LLMResponse(
            text=synthesis_response.text,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            provider=synthesis_response.provider,
            model_version=synthesis_response.model_version,
            raw_response={"plan_steps": len(steps), "step_results": step_results},
        )

    async def _reflect_on_response(
        self,
        model: str,
        provider: Provider,
        system_prompt: str,
        response: LLMResponse,
        reflection_prompt: str | None,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Post-loop reflection: model reviews its own output quality.

        If the reflection identifies issues, the response text is updated
        with the improved version.
        """
        default_reflection = (
            "Review your previous response for:\n"
            "1. Completeness — did you address all aspects of the question?\n"
            "2. Accuracy — are the facts and reasoning sound?\n"
            "3. Quality — is the response well-structured and clear?\n\n"
            "If improvements are needed, provide an improved version. "
            "If the response is satisfactory, reply with 'REFLECTION: SATISFACTORY'."
        )

        reflection_response = await self.generate(
            model=model,
            system_prompt=system_prompt,
            user_prompt=(
                f"Your previous response:\n{response.text}\n\n"
                f"{reflection_prompt or default_reflection}"
            ),
            provider=provider,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        if "REFLECTION: SATISFACTORY" not in reflection_response.text.upper():
            logger.info("Reflection identified improvements, updating response")
            return LLMResponse(
                text=reflection_response.text,
                input_tokens=response.input_tokens + reflection_response.input_tokens,
                output_tokens=response.output_tokens + reflection_response.output_tokens,
                provider=response.provider,
                model_version=response.model_version,
                raw_response=response.raw_response,
            )

        logger.info("Reflection: response satisfactory")
        return LLMResponse(
            text=response.text,
            input_tokens=response.input_tokens + reflection_response.input_tokens,
            output_tokens=response.output_tokens + reflection_response.output_tokens,
            provider=response.provider,
            model_version=response.model_version,
            raw_response=response.raw_response,
        )

    @staticmethod
    def _estimate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
        """Rough cost estimate for a generation call.

        Uses approximate pricing per 1M tokens. This is intentionally
        conservative (overestimates) to avoid exceeding cost limits.
        """
        # Approximate $/1M tokens (input, output) — conservative estimates
        pricing = {
            "claude-opus": (15.0, 75.0),
            "claude-sonnet": (3.0, 15.0),
            "claude-haiku": (0.25, 1.25),
            "gemini-2.5-flash": (0.15, 0.60),
            "gemini-2.5-pro": (1.25, 10.0),
            "gpt-4o": (2.50, 10.0),
            "gpt-4o-mini": (0.15, 0.60),
        }
        # Find best matching pricing tier
        rates = (3.0, 15.0)  # Default to sonnet-tier
        for prefix, p in pricing.items():
            if prefix in model.lower():
                rates = p
                break

        input_cost = (input_tokens / 1_000_000) * rates[0]
        output_cost = (output_tokens / 1_000_000) * rates[1]
        return input_cost + output_cost

    async def generate_with_video(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        video_url: str,
        media_resolution: str | None = None,
        provider: Provider | None = None,
        max_tokens: int = 8192,
        temperature: float = 0.3,
    ) -> LLMResponse:
        """Generate a response using a YouTube video URL as input.

        Only supported with Gemini models. Uses Part.from_uri() to send
        the video reference alongside the text prompt. Gemini processes the
        video natively (audio + visual).

        Args:
            model: Model ID (must be a Gemini model)
            system_prompt: System instructions
            user_prompt: User message
            video_url: YouTube video URL (e.g., https://www.youtube.com/watch?v=...)
            media_resolution: Resolution for video processing (low, medium, high, or None for default)
            provider: Optional explicit provider. If None, uses family default.
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            LLMResponse with generated text

        Raises:
            ValueError: If model is not a Gemini model
        """
        import time

        resolved_provider = self.resolve_provider(model, provider)

        if resolved_provider != Provider.GOOGLE_AI:
            raise ValueError(
                f"generate_with_video() only supports Gemini models (GOOGLE_AI provider), "
                f"got provider={resolved_provider.value} for model={model}"
            )

        logger.info(
            f"Generating with video: model={model}, video_url={video_url}, "
            f"resolution={media_resolution}"
        )

        start_time = time.monotonic()

        response = await self._generate_gemini_with_video(
            model,
            resolved_provider,
            system_prompt,
            user_prompt,
            video_url,
            media_resolution,
            max_tokens,
            temperature,
        )

        duration_ms = (time.monotonic() - start_time) * 1000
        self._trace_llm_call(
            model=model,
            provider=resolved_provider.value,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=response,
            duration_ms=duration_ms,
            max_tokens=max_tokens,
            metadata={"video_url": video_url, "media_resolution": media_resolution},
        )

        return response

    # =========================================================================
    # Synchronous Generation (for sync callers like SummarizationAgent)
    # =========================================================================

    def generate_sync(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        provider: Provider | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a simple text response synchronously (no tools).

        This is the sync counterpart of generate(). It calls the underlying SDK
        clients directly without async wrappers, avoiding nested event loop issues
        when called from sync code running inside an async worker.

        Args:
            model: Model ID (e.g., "claude-sonnet-4-5", "gemini-2.5-flash")
            system_prompt: System instructions
            user_prompt: User message
            provider: Optional explicit provider. If None, uses family default.
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            LLMResponse with generated text
        """
        import time

        resolved_provider = self.resolve_provider(model, provider)
        logger.info(f"Generating (sync) with model={model}, provider={resolved_provider.value}")

        start_time = time.monotonic()

        if resolved_provider == Provider.GOOGLE_AI:
            response = self._generate_gemini_sync(
                model, resolved_provider, system_prompt, user_prompt, max_tokens, temperature
            )
        elif resolved_provider in (
            Provider.ANTHROPIC,
            Provider.AWS_BEDROCK,
            Provider.GOOGLE_VERTEX,
        ):
            response = self._generate_anthropic_sync(
                model, resolved_provider, system_prompt, user_prompt, max_tokens, temperature
            )
        elif resolved_provider in (Provider.OPENAI, Provider.MICROSOFT_AZURE):
            response = self._generate_openai_sync(
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

    def _generate_anthropic_sync(
        self,
        model: str,
        provider: Provider,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Generate synchronously with Anthropic-compatible API."""
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

    def _generate_gemini_sync(
        self,
        model: str,
        provider: Provider,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Generate synchronously with Google Gemini API."""
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

    def _get_openai_sync_client(self, provider: Provider):
        """Get synchronous OpenAI client configured for the specified provider.

        Args:
            provider: Provider to use (OPENAI or MICROSOFT_AZURE)

        Returns:
            Configured sync OpenAI client
        """
        from openai import AzureOpenAI, OpenAI

        if provider == Provider.OPENAI:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY environment variable not set")
            return OpenAI(api_key=api_key)

        elif provider == Provider.MICROSOFT_AZURE:
            api_key = os.environ.get("AZURE_OPENAI_API_KEY")
            endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
            api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
            if not api_key or not endpoint:
                raise RuntimeError(
                    "AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT environment variables required"
                )
            return AzureOpenAI(
                api_key=api_key,
                azure_endpoint=endpoint,
                api_version=api_version,
            )

        else:
            raise ValueError(f"Provider {provider} not supported for OpenAI models")

    def _generate_openai_sync(
        self,
        model: str,
        provider: Provider,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Generate synchronously with OpenAI-compatible API."""
        client = self._get_openai_sync_client(provider)
        provider_model_id = self.get_provider_model_id(model, provider)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = client.chat.completions.create(
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

    async def _generate_gemini_with_video(
        self,
        model: str,
        provider: Provider,
        system_prompt: str,
        user_prompt: str,
        video_url: str,
        media_resolution: str | None,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Generate with Google Gemini API using a YouTube video URL.

        Uses Part.from_uri() to send the video URL alongside the text prompt.
        Gemini processes the video natively (audio + visual).

        Args:
            model: Model ID
            provider: Resolved provider
            system_prompt: System instructions
            user_prompt: User message
            video_url: YouTube video URL
            media_resolution: Resolution for video processing (low, medium, high, or None for default)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
        """
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY environment variable not set")

        client = genai.Client(api_key=api_key)
        provider_model_id = self.get_provider_model_id(model, provider)

        # Map string resolution to Gemini enum
        resolution_map: dict[str, types.MediaResolution] = {
            "low": types.MediaResolution.MEDIA_RESOLUTION_LOW,
            "medium": types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
            "high": types.MediaResolution.MEDIA_RESOLUTION_HIGH,
        }
        resolved_resolution = resolution_map.get((media_resolution or "").lower())

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
            temperature=temperature,
            media_resolution=resolved_resolution,
        )

        # Build content parts: video URI + text prompt
        video_part = types.Part.from_uri(
            file_uri=video_url,
            mime_type="video/mp4",
        )
        contents = [video_part, user_prompt]

        response = client.models.generate_content(
            model=provider_model_id,
            contents=contents,
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
