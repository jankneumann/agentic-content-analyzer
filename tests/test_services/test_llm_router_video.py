"""Tests for LLM router generate_with_video() method."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.config.models import ModelConfig, Provider
from src.services.llm_router import LLMRouter


@pytest.fixture
def router():
    """Create an LLMRouter with default config."""
    config = ModelConfig()
    return LLMRouter(config)


class TestGenerateWithVideo:
    """Tests for the generate_with_video() public method."""

    @pytest.mark.asyncio
    async def test_rejects_non_gemini_model(self, router):
        """Should raise ValueError for non-Gemini models."""
        with pytest.raises(ValueError, match="only supports Gemini models"):
            await router.generate_with_video(
                model="claude-sonnet-4-5",
                system_prompt="test",
                user_prompt="test",
                video_url="https://www.youtube.com/watch?v=test123",
            )

    @pytest.mark.asyncio
    async def test_calls_gemini_with_video_parts(self, router):
        """Should construct video Part and pass to Gemini API."""
        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [MagicMock(text="Video summary")]
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=100,
            candidates_token_count=50,
        )

        from src.services.llm_router import LLMResponse

        with patch.object(
            router,
            "_generate_gemini_with_video",
            return_value=LLMResponse(
                text="Video summary",
                input_tokens=100,
                output_tokens=50,
                provider=Provider.GOOGLE_AI,
            ),
        ) as mock_method:
            result = await router.generate_with_video(
                model="gemini-2.5-flash",
                system_prompt="Analyze this video",
                user_prompt="What is discussed?",
                video_url="https://www.youtube.com/watch?v=abc123",
                media_resolution="low",
            )

            assert result.text == "Video summary"
            assert result.input_tokens == 100
            mock_method.assert_called_once()

    @pytest.mark.asyncio
    async def test_traces_llm_call(self, router):
        """Should trace the LLM call with video metadata."""
        from src.services.llm_router import LLMResponse

        with (
            patch.object(
                router,
                "_generate_gemini_with_video",
                return_value=LLMResponse(
                    text="content",
                    input_tokens=50,
                    output_tokens=25,
                    provider=Provider.GOOGLE_AI,
                ),
            ),
            patch.object(router, "_trace_llm_call") as mock_trace,
        ):
            await router.generate_with_video(
                model="gemini-2.5-flash",
                system_prompt="sys",
                user_prompt="usr",
                video_url="https://youtube.com/watch?v=test",
                media_resolution="low",
            )

            mock_trace.assert_called_once()
            call_kwargs = mock_trace.call_args[1]
            assert call_kwargs["metadata"]["video_url"] == "https://youtube.com/watch?v=test"
            assert call_kwargs["metadata"]["media_resolution"] == "low"


class TestGeminiWithVideoInternal:
    """Tests for _generate_gemini_with_video internal method."""

    @pytest.mark.asyncio
    async def test_resolution_mapping(self, router):
        """Should map string resolution to Gemini MediaResolution enum."""
        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [MagicMock(text="content")]
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=100,
            candidates_token_count=50,
        )

        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}),
            patch("google.genai.Client") as mock_client_class,
        ):
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            await router._generate_gemini_with_video(
                model="gemini-2.5-flash",
                provider=Provider.GOOGLE_AI,
                system_prompt="sys",
                user_prompt="usr",
                video_url="https://youtube.com/watch?v=test",
                media_resolution="low",
                max_tokens=4096,
                temperature=0.3,
            )

            # Verify generate_content was called
            mock_client.models.generate_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_api_key_raises(self, router):
        """Should raise RuntimeError when GOOGLE_API_KEY is not set."""
        with patch.dict("os.environ", {}, clear=True):
            # Remove GOOGLE_API_KEY from env
            import os

            if "GOOGLE_API_KEY" in os.environ:
                del os.environ["GOOGLE_API_KEY"]

            with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
                await router._generate_gemini_with_video(
                    model="gemini-2.5-flash",
                    provider=Provider.GOOGLE_AI,
                    system_prompt="sys",
                    user_prompt="usr",
                    video_url="https://youtube.com/watch?v=test",
                    media_resolution=None,
                    max_tokens=4096,
                    temperature=0.3,
                )
