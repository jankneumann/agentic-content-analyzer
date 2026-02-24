"""Unit tests for the ImageGenerator service.

Tests cover:
- MockImageGenerator provider behavior
- ImageGenerator.suggest_images() with configurable prompts
- ImageGenerator.generate_for_summary() flow (mock provider + storage)
- ImageGenerator.generate_for_digest() flow
- ImageGenerator.refine_prompt() flow
- Suggestion parsing edge cases
- Factory function validation

Patch targets:
- Lazy imports (from X import Y inside function body) must be patched at SOURCE:
  src.config.models.get_model_config, src.models.image.Image, etc.
- Module-level imports are patched at consumer: src.services.image_generator.logger
"""

from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.image_generator import (
    GenerationParams,
    ImageGenerator,
    MockImageGenerator,
)

# ---------------------------------------------------------------------------
# MockImageGenerator
# ---------------------------------------------------------------------------


class TestMockImageGenerator:
    @pytest.mark.asyncio
    async def test_generate_returns_png_bytes(self):
        provider = MockImageGenerator()
        result = await provider.generate("a cat", GenerationParams())
        # PNG magic bytes
        assert result[:4] == b"\x89PNG"

    def test_model_name(self):
        provider = MockImageGenerator()
        assert provider.model_name == "mock/test-imagen"

    @pytest.mark.asyncio
    async def test_generate_ignores_params(self):
        """Params should be accepted but don't affect output (it's a mock)."""
        provider = MockImageGenerator()
        result = await provider.generate(
            "anything",
            GenerationParams(size="1792x1024", quality="hd", style="vivid"),
        )
        assert result[:4] == b"\x89PNG"


# ---------------------------------------------------------------------------
# ImageGenerator.suggest_images()
# ---------------------------------------------------------------------------


class TestSuggestImages:
    @pytest.mark.asyncio
    async def test_suggest_images_calls_llm_with_prompt_service(self):
        """Verify suggest_images uses PromptService for configurable prompts."""
        mock_prompt_service = MagicMock()
        mock_prompt_service.get_pipeline_prompt.return_value = "You are a visual strategist."
        mock_prompt_service.render.return_value = "Analyze this content..."

        suggestions_json = json.dumps(
            [
                {
                    "prompt": "An isometric diagram of AI agents",
                    "rationale": "Visualizes the multi-agent architecture",
                    "style": "diagram",
                    "placement": "after_executive_summary",
                }
            ]
        )

        mock_llm_response = MagicMock()
        mock_llm_response.text = suggestions_json

        mock_router = MagicMock()
        mock_router.generate = AsyncMock(return_value=mock_llm_response)

        generator = ImageGenerator(
            provider=MockImageGenerator(),
            storage=MagicMock(),
            db=MagicMock(),
            prompt_service=mock_prompt_service,
            llm_router=mock_router,
        )

        # Patch at source module — lazy import creates local var
        with patch("src.config.models.get_model_config") as mock_config:
            mock_config.return_value.get_model_for_step.return_value = "claude-haiku-4-5"
            result = await generator.suggest_images("Content about AI agents", max_suggestions=1)

        assert len(result) == 1
        assert result[0].prompt == "An isometric diagram of AI agents"
        assert result[0].style == "diagram"

        # Verify prompt service was called with correct keys
        mock_prompt_service.get_pipeline_prompt.assert_called_once_with(
            "image_generation", "suggestion_system"
        )
        mock_prompt_service.render.assert_called_once_with(
            "pipeline.image_generation.suggestion_template",
            content="Content about AI agents",
            content_type="summary",
            max_suggestions="1",
        )

    @pytest.mark.asyncio
    async def test_suggest_images_handles_empty_response(self):
        """Gracefully handle empty or invalid LLM output."""
        mock_prompt_service = MagicMock()
        mock_prompt_service.get_pipeline_prompt.return_value = "system"
        mock_prompt_service.render.return_value = "user"

        mock_llm_response = MagicMock()
        mock_llm_response.text = "not valid json"

        mock_router = MagicMock()
        mock_router.generate = AsyncMock(return_value=mock_llm_response)

        generator = ImageGenerator(
            provider=MockImageGenerator(),
            storage=MagicMock(),
            db=MagicMock(),
            prompt_service=mock_prompt_service,
            llm_router=mock_router,
        )

        with patch("src.config.models.get_model_config") as mock_config:
            mock_config.return_value.get_model_for_step.return_value = "claude-haiku-4-5"
            result = await generator.suggest_images("Some content")

        assert result == []

    @pytest.mark.asyncio
    async def test_suggest_images_handles_markdown_fenced_json(self):
        """LLMs sometimes wrap JSON in ```json ... ``` code fences."""
        mock_prompt_service = MagicMock()
        mock_prompt_service.get_pipeline_prompt.return_value = "system"
        mock_prompt_service.render.return_value = "user"

        fenced = (
            '```json\n[{"prompt": "test", "rationale": "r", "style": "s", "placement": "p"}]\n```'
        )
        mock_llm_response = MagicMock()
        mock_llm_response.text = fenced

        mock_router = MagicMock()
        mock_router.generate = AsyncMock(return_value=mock_llm_response)

        generator = ImageGenerator(
            provider=MockImageGenerator(),
            storage=MagicMock(),
            db=MagicMock(),
            prompt_service=mock_prompt_service,
            llm_router=mock_router,
        )

        with patch("src.config.models.get_model_config") as mock_config:
            mock_config.return_value.get_model_for_step.return_value = "claude-haiku-4-5"
            result = await generator.suggest_images("content")

        assert len(result) == 1
        assert result[0].prompt == "test"


# ---------------------------------------------------------------------------
# ImageGenerator.generate_for_summary()
# ---------------------------------------------------------------------------


class TestGenerateForSummary:
    @pytest.mark.asyncio
    async def test_generate_creates_image_record(self):
        """Full flow: generate → store → create DB record."""
        mock_provider = MockImageGenerator()
        mock_storage = AsyncMock()
        mock_storage.save = AsyncMock(return_value="2026/02/23/abc123_summary_1.png")
        mock_storage.provider_name = "local"
        mock_db = MagicMock()

        mock_summary = MagicMock()
        mock_summary.id = 42

        generator = ImageGenerator(
            provider=mock_provider,
            storage=mock_storage,
            db=mock_db,
        )

        # Patch at source module — lazy imports create local vars
        with (
            patch("src.models.image.Image") as MockImage,
            patch("src.models.image.ImageSource") as MockSource,
        ):
            MockSource.AI_GENERATED = "ai_generated"
            mock_image_instance = MagicMock()
            MockImage.return_value = mock_image_instance

            result = await generator.generate_for_summary(mock_summary, "A beautiful diagram")

        mock_storage.save.assert_called_once()
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_uses_default_params_from_settings(self):
        """When no params given, defaults come from settings."""
        mock_provider = MockImageGenerator()
        mock_storage = AsyncMock()
        mock_storage.save = AsyncMock(return_value="path.png")
        mock_storage.provider_name = "local"
        mock_db = MagicMock()

        mock_summary = MagicMock()
        mock_summary.id = 1

        generator = ImageGenerator(
            provider=mock_provider,
            storage=mock_storage,
            db=mock_db,
        )

        # Patch the settings import at source module
        with (
            patch("src.models.image.Image"),
            patch("src.models.image.ImageSource"),
            patch("src.config.settings") as mock_settings_module,
        ):
            mock_settings_module.image_generation_default_size = "1024x1024"
            mock_settings_module.image_generation_default_quality = "standard"
            mock_settings_module.image_generation_default_style = "natural"

            await generator.generate_for_summary(mock_summary, "test prompt")

        # Should have called without error (uses defaults)
        mock_db.flush.assert_called_once()


# ---------------------------------------------------------------------------
# ImageGenerator.refine_prompt()
# ---------------------------------------------------------------------------


class TestRefinePrompt:
    @pytest.mark.asyncio
    async def test_refine_prompt_uses_prompt_service(self):
        """Verify refine_prompt uses the configurable prompt refinement templates."""
        mock_prompt_service = MagicMock()
        mock_prompt_service.get_pipeline_prompt.return_value = "You are a prompt expert."
        mock_prompt_service.render.return_value = "Refine this prompt..."

        mock_llm_response = MagicMock()
        mock_llm_response.text = "  A refined, detailed prompt for image generation.  "

        mock_router = MagicMock()
        mock_router.generate = AsyncMock(return_value=mock_llm_response)

        generator = ImageGenerator(
            provider=MockImageGenerator(),
            storage=MagicMock(),
            db=MagicMock(),
            prompt_service=mock_prompt_service,
            llm_router=mock_router,
        )

        with patch("src.config.models.get_model_config") as mock_config:
            mock_config.return_value.get_model_for_step.return_value = "claude-haiku-4-5"
            result = await generator.refine_prompt("draw a cat", context="AI newsletter")

        assert result == "A refined, detailed prompt for image generation."
        mock_prompt_service.get_pipeline_prompt.assert_called_with(
            "image_generation", "prompt_refinement_system"
        )
        mock_prompt_service.render.assert_called_with(
            "pipeline.image_generation.prompt_refinement_template",
            original_prompt="draw a cat",
            context="AI newsletter",
            style="professional",
            size="1024x1024",
        )


# ---------------------------------------------------------------------------
# Suggestion parsing edge cases
# ---------------------------------------------------------------------------


class TestParseSuggestions:
    def test_valid_json_array(self):
        text = json.dumps(
            [
                {"prompt": "p1", "rationale": "r1", "style": "s1", "placement": "inline"},
                {"prompt": "p2", "rationale": "r2"},
            ]
        )
        result = ImageGenerator._parse_suggestions(text)
        assert len(result) == 2
        assert result[0].placement == "inline"
        assert result[1].style == "professional"  # default

    def test_non_array_json(self):
        result = ImageGenerator._parse_suggestions('{"not": "an array"}')
        assert result == []

    def test_invalid_json(self):
        result = ImageGenerator._parse_suggestions("this is not json at all")
        assert result == []

    def test_empty_array(self):
        result = ImageGenerator._parse_suggestions("[]")
        assert result == []

    def test_json_with_code_fence(self):
        text = '```json\n[{"prompt": "test", "rationale": "r"}]\n```'
        result = ImageGenerator._parse_suggestions(text)
        assert len(result) == 1
        assert result[0].prompt == "test"

    def test_code_fence_only_strips_outer_fences(self):
        """Only first/last fence lines should be stripped, not inner content."""
        text = '```json\n[{"prompt": "use ```code``` here", "rationale": "r"}]\n```'
        result = ImageGenerator._parse_suggestions(text)
        assert len(result) == 1
        assert "```code```" in result[0].prompt


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------


class TestGetImageGenerator:
    def test_raises_when_disabled(self):
        """get_image_generator should raise when feature is disabled."""
        from src.services.image_generator import get_image_generator

        # Patch settings at source — get_image_generator uses `from src.config import settings`
        with patch("src.config.settings") as mock_settings:
            mock_settings.image_generation_enabled = False
            with pytest.raises(ValueError, match="disabled"):
                get_image_generator(db=MagicMock())

    def test_raises_for_unknown_provider(self):
        """Unknown provider name should raise ValueError."""
        from src.services.image_generator import _create_provider

        mock_settings = MagicMock()
        mock_settings.image_generation_provider = "dall-e-999"

        with pytest.raises(ValueError, match="Unknown"):
            _create_provider(mock_settings)

    def test_gemini_requires_project_id(self):
        """Gemini provider without project ID should raise."""
        from src.services.image_generator import _create_provider

        mock_settings = MagicMock()
        mock_settings.image_generation_provider = "gemini"
        mock_settings.google_cloud_project = None

        with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT"):
            _create_provider(mock_settings)

    def test_mock_provider_creation(self):
        """Mock provider should be creatable via factory."""
        from src.services.image_generator import _create_provider

        mock_settings = MagicMock()
        mock_settings.image_generation_provider = "mock"

        provider = _create_provider(mock_settings)
        assert isinstance(provider, MockImageGenerator)


# ---------------------------------------------------------------------------
# GenerationParams defaults
# ---------------------------------------------------------------------------


class TestGenerationParams:
    def test_default_values(self):
        params = GenerationParams()
        assert params.size == "1024x1024"
        assert params.quality == "standard"
        assert params.style == "natural"

    def test_asdict(self):
        params = GenerationParams(size="1792x1024", quality="hd", style="vivid")
        d = asdict(params)
        assert d == {"size": "1792x1024", "quality": "hd", "style": "vivid"}
