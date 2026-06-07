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


class TestVideoFpsAndOffsets:
    """fps + start/end offset passthrough via VideoMetadata (yt-route.5/8)."""

    @staticmethod
    def _mock_response():
        resp = MagicMock()
        resp.candidates = [MagicMock()]
        resp.candidates[0].content.parts = [MagicMock(text="x" * 200)]
        resp.usage_metadata = MagicMock(prompt_token_count=100, candidates_token_count=50)
        return resp

    @pytest.mark.asyncio
    async def test_fps_and_offsets_in_video_metadata(self, router):
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}),
            patch("google.genai.Client") as mock_client_class,
        ):
            client = MagicMock()
            mock_client_class.return_value = client
            client.models.generate_content.return_value = self._mock_response()

            await router.generate_with_video(
                model="gemini-2.5-flash",
                system_prompt="sys",
                user_prompt="usr",
                video_url="https://www.youtube.com/watch?v=abc",
                media_resolution="low",
                fps=0.1,
                start_offset="0s",
                end_offset="2700s",
            )

            _, kwargs = client.models.generate_content.call_args
            video_part = kwargs["contents"][0]
            assert video_part.file_data.file_uri == "https://www.youtube.com/watch?v=abc"
            assert video_part.video_metadata.fps == pytest.approx(0.1)
            assert video_part.video_metadata.start_offset == "0s"
            assert video_part.video_metadata.end_offset == "2700s"

    @pytest.mark.asyncio
    async def test_no_fps_omits_video_metadata(self, router):
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}),
            patch("google.genai.Client") as mock_client_class,
        ):
            client = MagicMock()
            mock_client_class.return_value = client
            client.models.generate_content.return_value = self._mock_response()

            await router.generate_with_video(
                model="gemini-2.5-flash",
                system_prompt="sys",
                user_prompt="usr",
                video_url="https://www.youtube.com/watch?v=abc",
            )
            _, kwargs = client.models.generate_content.call_args
            assert kwargs["contents"][0].video_metadata is None


class TestGenerateWithGrounding:
    """Google Search grounding path for long videos (yt-route.7)."""

    @pytest.mark.asyncio
    async def test_rejects_non_gemini(self, router):
        with pytest.raises(ValueError, match="only supports Gemini models"):
            await router.generate_with_grounding(
                model="claude-sonnet-4-5",
                system_prompt="s",
                user_prompt="p",
            )

    @pytest.mark.asyncio
    async def test_builds_google_search_tool(self, router):
        resp = MagicMock()
        resp.candidates = [MagicMock()]
        resp.candidates[0].content.parts = [MagicMock(text="grounded summary " * 20)]
        resp.usage_metadata = MagicMock(prompt_token_count=80, candidates_token_count=40)

        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}),
            patch("google.genai.Client") as mock_client_class,
        ):
            client = MagicMock()
            mock_client_class.return_value = client
            client.models.generate_content.return_value = resp

            result = await router.generate_with_grounding(
                model="gemini-2.5-flash",
                system_prompt="sys",
                user_prompt="summarize https://www.youtube.com/watch?v=abc",
            )

            assert result.text
            _, kwargs = client.models.generate_content.call_args
            tools = kwargs["config"].tools
            assert tools and tools[0].google_search is not None
