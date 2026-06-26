"""Regression: with batch disabled (the default), Gemini stays synchronous.

Phase 0 adds the batch machinery but wires NO pipeline call-site into it, so the
synchronous behavior must be byte-for-byte unchanged. These are the golden
guards that keep it that way until a phase explicitly opts a step in.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from src.config.models import ModelConfig, ModelStep, Provider
from src.services.llm_router import LLMRouter


def test_all_steps_sync_by_default():
    """Out of the box, no step defers to batch."""
    config = ModelConfig()
    for step in ModelStep:
        assert config.is_batch_enabled(step) is False, step


def test_global_off_overrides_per_step_batch():
    """Even if every step is mapped to 'batch', the global switch keeps them sync."""
    config = ModelConfig()
    config._batch_config = {
        "enabled": False,  # global kill-switch wins
        "flush_max_requests": 50,
        "flush_max_wait_minutes": 60,
        "fallback_on_expire": True,
        "execution": {s.value: "batch" for s in ModelStep},
    }
    for step in ModelStep:
        assert config.is_batch_enabled(step) is False, step


@pytest.mark.asyncio
async def test_sync_gemini_path_never_touches_batches():
    """The synchronous generate path calls generate_content, not client.batches."""
    router = LLMRouter(ModelConfig())

    mock_response = MagicMock()
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content.parts = [MagicMock(text="sync answer")]
    mock_response.usage_metadata = MagicMock(prompt_token_count=10, candidates_token_count=3)

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with (
        patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}),
        patch("google.genai.Client", return_value=mock_client),
    ):
        resp = await router._generate_gemini(
            "gemini-2.5-flash-lite",
            Provider.GOOGLE_AI,
            system_prompt="sys",
            user_prompt="user",
            max_tokens=100,
            temperature=0.0,
        )

    assert resp.text == "sync answer"
    mock_client.models.generate_content.assert_called_once()
    # The batch API must be completely untouched on the synchronous path.
    mock_client.batches.create.assert_not_called()
    mock_client.batches.get.assert_not_called()
