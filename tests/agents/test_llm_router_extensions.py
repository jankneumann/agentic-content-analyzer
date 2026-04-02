"""Tests for LLMRouter agentic extensions — reflection, planning, memory, cost limit.

Covers Tasks 2.1-2.6:
- Reflection (enable_reflection, reflection_prompt)
- Planning (generate_with_planning)
- Memory context injection
- Cost limit enforcement
- Backward compatibility (new params are optional)

Spec scenarios: agentic-analysis.18, agentic-analysis.19, agentic-analysis.29.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.llm_router import LLMResponse, LLMRouter, ToolDefinition


@pytest.fixture
def mock_model_config():
    config = MagicMock()
    config.get_family.return_value = MagicMock(value="anthropic")
    config.get_model_version.return_value = "test-v1"
    config.get_provider_model_id.return_value = "test-model"
    return config


@pytest.fixture
def router(mock_model_config):
    return LLMRouter(mock_model_config)


@pytest.fixture
def sample_tools():
    return [
        ToolDefinition(
            name="search",
            description="Search for content",
            parameters={"type": "object", "properties": {"query": {"type": "string"}}},
        )
    ]


@pytest.fixture
def mock_tool_executor():
    return AsyncMock(return_value="tool result")


@pytest.fixture
def mock_response():
    return LLMResponse(
        text="test response",
        input_tokens=100,
        output_tokens=50,
    )


# =============================================================================
# Backward Compatibility (agentic-analysis.29)
# =============================================================================


class TestBackwardCompatibility:
    """Existing callers without new params should work identically."""

    @pytest.mark.asyncio
    async def test_generate_with_tools_no_new_params(self, router, sample_tools, mock_tool_executor):
        """Calling without new params should work as before."""
        with patch.object(router, "_generate_anthropic_with_tools", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = LLMResponse(text="result", input_tokens=10, output_tokens=5)
            with patch.object(router, "resolve_provider") as mock_resolve:
                from src.config.models import Provider
                mock_resolve.return_value = Provider.ANTHROPIC
                with patch.object(router, "_trace_llm_call"):
                    response = await router.generate_with_tools(
                        model="claude-sonnet-4-5",
                        system_prompt="test",
                        user_prompt="test",
                        tools=sample_tools,
                        tool_executor=mock_tool_executor,
                    )
            assert response.text == "result"

    def test_new_params_have_defaults(self):
        """All new params should have default values."""
        import inspect
        sig = inspect.signature(LLMRouter.generate_with_tools)
        new_params = ["enable_reflection", "reflection_prompt", "memory_context", "cost_limit"]
        for param_name in new_params:
            param = sig.parameters[param_name]
            assert param.default is not inspect.Parameter.empty, f"{param_name} has no default"


# =============================================================================
# Reflection (agentic-analysis.18)
# =============================================================================


class TestReflection:
    @pytest.mark.asyncio
    async def test_reflect_on_response_satisfactory(self, router):
        """When reflection says satisfactory, original text is kept."""
        with patch.object(router, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = LLMResponse(
                text="REFLECTION: SATISFACTORY",
                input_tokens=20,
                output_tokens=10,
            )
            from src.config.models import Provider
            original = LLMResponse(text="original answer", input_tokens=100, output_tokens=50)
            result = await router._reflect_on_response(
                model="test", provider=Provider.ANTHROPIC,
                system_prompt="", response=original,
                reflection_prompt=None, max_tokens=8192, temperature=0.7,
            )
            assert result.text == "original answer"
            # Tokens should include both original and reflection
            assert result.input_tokens == 120
            assert result.output_tokens == 60

    @pytest.mark.asyncio
    async def test_reflect_on_response_improved(self, router):
        """When reflection provides improvements, updated text is used."""
        with patch.object(router, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = LLMResponse(
                text="improved answer with more detail",
                input_tokens=20,
                output_tokens=30,
            )
            from src.config.models import Provider
            original = LLMResponse(text="original answer", input_tokens=100, output_tokens=50)
            result = await router._reflect_on_response(
                model="test", provider=Provider.ANTHROPIC,
                system_prompt="", response=original,
                reflection_prompt=None, max_tokens=8192, temperature=0.7,
            )
            assert result.text == "improved answer with more detail"

    @pytest.mark.asyncio
    async def test_custom_reflection_prompt(self, router):
        """Custom reflection prompt should be passed to the model."""
        with patch.object(router, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = LLMResponse(
                text="REFLECTION: SATISFACTORY", input_tokens=10, output_tokens=5
            )
            from src.config.models import Provider
            original = LLMResponse(text="answer", input_tokens=50, output_tokens=25)
            await router._reflect_on_response(
                model="test", provider=Provider.ANTHROPIC,
                system_prompt="", response=original,
                reflection_prompt="Check for technical accuracy only.",
                max_tokens=8192, temperature=0.7,
            )
            call_args = mock_gen.call_args
            assert "Check for technical accuracy only." in call_args.kwargs["user_prompt"]


# =============================================================================
# Memory Context Injection (agentic-analysis.18)
# =============================================================================


class TestMemoryContextInjection:
    @pytest.mark.asyncio
    async def test_memory_context_appended_to_system_prompt(self, router, sample_tools, mock_tool_executor):
        """Memory entries should be injected into the system prompt."""
        memory_entries = [
            MagicMock(content="AI agents are trending in enterprise"),
            MagicMock(content="RAG systems are maturing"),
        ]

        with patch.object(router, "_generate_anthropic_with_tools", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = LLMResponse(text="result", input_tokens=10, output_tokens=5)
            with patch.object(router, "resolve_provider") as mock_resolve:
                from src.config.models import Provider
                mock_resolve.return_value = Provider.ANTHROPIC
                with patch.object(router, "_trace_llm_call"):
                    await router.generate_with_tools(
                        model="claude-sonnet-4-5",
                        system_prompt="You are an analyst.",
                        user_prompt="What's trending?",
                        tools=sample_tools,
                        tool_executor=mock_tool_executor,
                        memory_context=memory_entries,
                    )

            # Check that memory was injected into system prompt
            call_args = mock_gen.call_args
            system_prompt_arg = call_args[0][2]  # positional: model, provider, system_prompt
            assert "AI agents are trending" in system_prompt_arg
            assert "RAG systems are maturing" in system_prompt_arg
            assert "Prior Knowledge" in system_prompt_arg

    @pytest.mark.asyncio
    async def test_no_memory_context_unchanged(self, router, sample_tools, mock_tool_executor):
        """Without memory_context, system prompt should be unchanged."""
        with patch.object(router, "_generate_anthropic_with_tools", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = LLMResponse(text="result", input_tokens=10, output_tokens=5)
            with patch.object(router, "resolve_provider") as mock_resolve:
                from src.config.models import Provider
                mock_resolve.return_value = Provider.ANTHROPIC
                with patch.object(router, "_trace_llm_call"):
                    await router.generate_with_tools(
                        model="claude-sonnet-4-5",
                        system_prompt="You are an analyst.",
                        user_prompt="What's trending?",
                        tools=sample_tools,
                        tool_executor=mock_tool_executor,
                    )
            call_args = mock_gen.call_args
            system_prompt_arg = call_args[0][2]
            assert "Prior Knowledge" not in system_prompt_arg


# =============================================================================
# Cost Limit (agentic-analysis.18, agentic-analysis.21)
# =============================================================================


class TestCostLimit:
    def test_estimate_cost_sonnet(self):
        """Cost estimation for claude-sonnet tier."""
        cost = LLMRouter._estimate_cost(1_000_000, 1_000_000, "claude-sonnet-4-5")
        assert cost == pytest.approx(18.0, rel=0.1)  # $3 input + $15 output

    def test_estimate_cost_haiku(self):
        cost = LLMRouter._estimate_cost(1_000_000, 1_000_000, "claude-haiku-4-5")
        assert cost == pytest.approx(1.5, rel=0.1)  # $0.25 + $1.25

    def test_estimate_cost_unknown_model_defaults_to_sonnet(self):
        cost = LLMRouter._estimate_cost(1_000_000, 1_000_000, "unknown-model-xyz")
        assert cost == pytest.approx(18.0, rel=0.1)


# =============================================================================
# Planning (agentic-analysis.19)
# =============================================================================


class TestPlanning:
    @pytest.mark.asyncio
    async def test_generate_with_planning_creates_plan(self, router, sample_tools, mock_tool_executor):
        """Planning should first ask model to create a plan, then execute steps."""
        # generate() is called for: 1) planning, 2) revision check after step 1,
        # 3) revision check after step 2 (skipped since it's last step), 4) synthesis
        generate_responses = [
            LLMResponse(text="1. Search for AI trends\n2. Analyze results",
                        input_tokens=50, output_tokens=20),
            LLMResponse(text="NO REVISION NEEDED", input_tokens=10, output_tokens=5),
            LLMResponse(text="Final synthesis of AI trends",
                        input_tokens=30, output_tokens=40),
        ]

        with patch.object(router, "generate", new_callable=AsyncMock,
                          side_effect=generate_responses):
            with patch.object(router, "generate_with_tools", new_callable=AsyncMock) as mock_gwt:
                mock_gwt.return_value = LLMResponse(
                    text="step result", input_tokens=50, output_tokens=25
                )
                result = await router.generate_with_planning(
                    goal="Find AI trends",
                    model="claude-sonnet-4-5",
                    tools=sample_tools,
                    tool_executor=mock_tool_executor,
                )

        assert "synthesis" in result.text.lower() or "trends" in result.text.lower()
        assert result.input_tokens > 0
        assert result.output_tokens > 0

    @pytest.mark.asyncio
    async def test_planning_respects_max_plan_steps(self, router, sample_tools, mock_tool_executor):
        """Plan should be limited to max_plan_steps."""
        async def mock_generate(**kwargs):
            if "planning mode" in kwargs.get("system_prompt", ""):
                return LLMResponse(
                    text="1. Step A\n2. Step B\n3. Step C\n4. Step D\n5. Step E\n6. Step F\n7. Step G",
                    input_tokens=50, output_tokens=20,
                )
            return LLMResponse(text="NO REVISION NEEDED", input_tokens=10, output_tokens=5)

        with patch.object(router, "generate", side_effect=mock_generate):
            with patch.object(router, "generate_with_tools", new_callable=AsyncMock) as mock_gwt:
                mock_gwt.return_value = LLMResponse(text="done", input_tokens=20, output_tokens=10)
                result = await router.generate_with_planning(
                    goal="Test",
                    model="test",
                    tools=sample_tools,
                    tool_executor=mock_tool_executor,
                    max_plan_steps=3,
                )
        # Should have called generate_with_tools at most 3 times (one per step)
        assert mock_gwt.call_count <= 3

    def test_planning_method_signature(self):
        """Verify generate_with_planning has the expected parameters."""
        import inspect
        sig = inspect.signature(LLMRouter.generate_with_planning)
        params = set(sig.parameters.keys())
        expected = {"self", "goal", "model", "tools", "tool_executor", "system_prompt",
                    "provider", "max_tokens", "temperature", "max_plan_steps",
                    "max_iterations_per_step", "max_revisions", "memory_context", "cost_limit"}
        assert expected.issubset(params)
