"""Tests for LLMRouter dynamic routing integration.

Tests cover:
- Step parameter routing (dynamic dispatch)
- Backward compatibility (no step → no routing)
- Routing decision logging
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.models import ModelConfig, ModelStep, RoutingConfig, RoutingMode
from src.services.complexity_router import ComplexityRouter, RoutingDecisionInfo
from src.services.llm_router import LLMResponse, LLMRouter


@pytest.fixture
def model_config():
    return ModelConfig()


@pytest.fixture
def mock_complexity_router():
    router = MagicMock(spec=ComplexityRouter)
    router.classify.return_value = RoutingDecisionInfo(
        step="summarization",
        complexity_score=0.3,
        threshold=0.5,
        model_selected="claude-haiku-4-5",
        strong_model="claude-sonnet-4-5",
        weak_model="claude-haiku-4-5",
        prompt_hash="abc123",
    )
    return router


class TestBackwardCompatibility:
    """Spec scenario 5: no step → no routing logic, no routing_decisions row."""

    @pytest.mark.asyncio
    async def test_no_step_uses_explicit_model(self, model_config):
        """Without step parameter, uses the explicitly provided model."""
        router = LLMRouter(model_config)

        with patch.object(router, '_generate_anthropic', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = LLMResponse(text="response", input_tokens=10, output_tokens=5)

            response = await router.generate(
                model="claude-sonnet-4-5",
                system_prompt="test",
                user_prompt="test prompt",
            )

            assert response.text == "response"
            # _generate_anthropic was called with the original model
            call_args = mock_gen.call_args
            assert call_args[0][0] == "claude-sonnet-4-5"

    @pytest.mark.asyncio
    async def test_no_step_does_not_log_routing_decision(self, model_config):
        """Without step, no routing decision should be logged."""
        router = LLMRouter(model_config)

        with patch.object(router, '_generate_anthropic', new_callable=AsyncMock) as mock_gen, \
             patch.object(router, '_log_routing_decision') as mock_log:
            mock_gen.return_value = LLMResponse(text="response", input_tokens=10, output_tokens=5)

            await router.generate(
                model="claude-sonnet-4-5",
                system_prompt="test",
                user_prompt="test",
            )

            mock_log.assert_not_called()


class TestDynamicRouting:
    """Spec scenario 3: dynamic routing selects model based on complexity."""

    @pytest.mark.asyncio
    async def test_dynamic_routing_overrides_model(self, model_config, mock_complexity_router):
        """When dynamic routing is enabled, the model may be overridden."""
        # Enable dynamic routing for summarization
        model_config._routing_configs["summarization"] = RoutingConfig(
            step="summarization",
            mode=RoutingMode.DYNAMIC,
            enabled=True,
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
            threshold=0.5,
        )

        router = LLMRouter(model_config, complexity_router=mock_complexity_router)

        with patch.object(router, '_generate_anthropic', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = LLMResponse(text="response", input_tokens=10, output_tokens=5)

            await router.generate(
                model="claude-sonnet-4-5",  # Original model
                system_prompt="test",
                user_prompt="test prompt",
                step=ModelStep.SUMMARIZATION,
            )

            # Complexity router was called
            mock_complexity_router.classify.assert_called_once()
            # Model was overridden to weak (complexity_score 0.3 < threshold 0.5)
            call_args = mock_gen.call_args
            assert call_args[0][0] == "claude-haiku-4-5"

    @pytest.mark.asyncio
    async def test_fixed_mode_ignores_complexity_router(self, model_config, mock_complexity_router):
        """When mode is fixed, complexity router is not called."""
        router = LLMRouter(model_config, complexity_router=mock_complexity_router)

        with patch.object(router, '_generate_anthropic', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = LLMResponse(text="response", input_tokens=10, output_tokens=5)

            await router.generate(
                model="claude-sonnet-4-5",
                system_prompt="test",
                user_prompt="test",
                step=ModelStep.SUMMARIZATION,
            )

            # Complexity router should NOT be called (mode is fixed)
            mock_complexity_router.classify.assert_not_called()

    @pytest.mark.asyncio
    async def test_disabled_dynamic_ignores_complexity_router(self, model_config, mock_complexity_router):
        """When enabled=False, complexity router is not called even if mode=dynamic."""
        model_config._routing_configs["summarization"] = RoutingConfig(
            step="summarization",
            mode=RoutingMode.DYNAMIC,
            enabled=False,  # Disabled
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
            threshold=0.5,
        )

        router = LLMRouter(model_config, complexity_router=mock_complexity_router)

        with patch.object(router, '_generate_anthropic', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = LLMResponse(text="response", input_tokens=10, output_tokens=5)

            await router.generate(
                model="claude-sonnet-4-5",
                system_prompt="test",
                user_prompt="test",
                step=ModelStep.SUMMARIZATION,
            )

            mock_complexity_router.classify.assert_not_called()


class TestRoutingDecisionLogging:
    """Spec scenario 16: routing decisions are logged to the database."""

    @pytest.mark.asyncio
    async def test_logs_routing_decision(self, model_config, mock_complexity_router):
        """Dynamic routing logs decision via _log_routing_decision."""
        model_config._routing_configs["summarization"] = RoutingConfig(
            step="summarization",
            mode=RoutingMode.DYNAMIC,
            enabled=True,
            strong_model="claude-sonnet-4-5",
            weak_model="claude-haiku-4-5",
            threshold=0.5,
        )

        router = LLMRouter(model_config, complexity_router=mock_complexity_router)

        with patch.object(router, '_generate_anthropic', new_callable=AsyncMock) as mock_gen, \
             patch.object(router, '_log_routing_decision') as mock_log:
            mock_gen.return_value = LLMResponse(text="response", input_tokens=10, output_tokens=5)

            await router.generate(
                model="claude-sonnet-4-5",
                system_prompt="test",
                user_prompt="test",
                step=ModelStep.SUMMARIZATION,
            )

            # Routing decision was logged
            mock_log.assert_called_once()
            decision = mock_log.call_args[0][0]
            assert decision.step == "summarization"
            assert decision.model_selected == "claude-haiku-4-5"
