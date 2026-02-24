"""Tests for image generation prompt configuration.

Verifies that:
- Image generation prompts are present in prompts.yaml
- PromptService can load and render them
- Template variables are properly handled
"""

from __future__ import annotations

from src.services.prompt_service import PromptService


class TestImageGenerationPrompts:
    """Verify image generation prompts exist in the YAML defaults."""

    def setup_method(self):
        """Create a PromptService without DB (defaults only)."""
        PromptService.clear_cache()
        self.service = PromptService()

    def test_suggestion_system_prompt_exists(self):
        prompt = self.service.get_prompt("pipeline.image_generation.suggestion_system")
        assert prompt is not None
        assert "visual content strategist" in prompt.lower()

    def test_suggestion_template_exists(self):
        prompt = self.service.get_prompt("pipeline.image_generation.suggestion_template")
        assert prompt is not None
        assert "{content}" in prompt
        assert "{max_suggestions}" in prompt
        assert "{content_type}" in prompt

    def test_prompt_refinement_system_exists(self):
        prompt = self.service.get_prompt("pipeline.image_generation.prompt_refinement_system")
        assert prompt is not None
        assert "image generation prompts" in prompt.lower()

    def test_prompt_refinement_template_exists(self):
        prompt = self.service.get_prompt("pipeline.image_generation.prompt_refinement_template")
        assert prompt is not None
        assert "{original_prompt}" in prompt
        assert "{context}" in prompt
        assert "{style}" in prompt
        assert "{size}" in prompt

    def test_suggestion_template_renders(self):
        """Template variables should be substituted correctly."""
        rendered = self.service.render(
            "pipeline.image_generation.suggestion_template",
            content="AI agents are changing everything",
            content_type="digest",
            max_suggestions="3",
        )
        assert "AI agents are changing everything" in rendered
        assert "digest" in rendered
        assert "3" in rendered
        # No unrendered variables should remain
        assert "{content}" not in rendered
        assert "{content_type}" not in rendered
        assert "{max_suggestions}" not in rendered

    def test_refinement_template_renders(self):
        rendered = self.service.render(
            "pipeline.image_generation.prompt_refinement_template",
            original_prompt="draw a cat",
            context="AI newsletter about agent patterns",
            style="professional",
            size="1024x1024",
        )
        assert "draw a cat" in rendered
        assert "AI newsletter about agent patterns" in rendered
        assert "{original_prompt}" not in rendered

    def test_prompts_appear_in_list_all(self):
        """Image generation prompts should appear in list_all_prompts()."""
        all_prompts = self.service.list_all_prompts()
        keys = {p["key"] for p in all_prompts}

        assert "pipeline.image_generation.suggestion_system" in keys
        assert "pipeline.image_generation.suggestion_template" in keys
        assert "pipeline.image_generation.prompt_refinement_system" in keys
        assert "pipeline.image_generation.prompt_refinement_template" in keys

    def test_get_pipeline_prompt_convenience(self):
        """PromptService.get_pipeline_prompt() should work for image_generation."""
        prompt = self.service.get_pipeline_prompt("image_generation", "suggestion_system")
        assert prompt is not None
        assert len(prompt) > 50  # Non-trivial prompt
