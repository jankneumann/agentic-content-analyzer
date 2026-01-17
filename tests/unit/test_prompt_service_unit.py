import pytest
from unittest.mock import MagicMock
from src.services.prompt_service import PromptService

class TestPromptServiceUnit:
    def teardown_method(self):
        """Reset the cache after each test to ensure isolation."""
        PromptService._CACHED_DEFAULTS = None

    def test_prompt_service_loads_defaults(self):
        """Test that PromptService loads default prompts from YAML."""
        # Use a fresh PromptService to trigger loading
        PromptService._CACHED_DEFAULTS = None
        service = PromptService()

        # Check that defaults are loaded
        assert service._defaults is not None
        assert "chat" in service._defaults
        assert "pipeline" in service._defaults

        # Check that caching works
        assert PromptService._CACHED_DEFAULTS is not None

        # Check second instantiation uses cache
        service2 = PromptService()
        assert service2._defaults is PromptService._CACHED_DEFAULTS

    def test_prompt_service_returns_override_when_set(self):
        """Test that PromptService returns override when available."""
        mock_db = MagicMock()
        mock_override = MagicMock()
        mock_override.value = "Overridden Prompt"
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_override

        service = PromptService(mock_db)
        prompt = service.get_chat_prompt("summary")

        assert prompt == "Overridden Prompt"

    def test_prompt_service_returns_default_when_no_override(self):
        """Test that PromptService returns default when no override exists."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        service = PromptService(mock_db)
        prompt = service.get_chat_prompt("summary")

        # We assume the default prompt is not "Overridden Prompt" and is a string
        assert isinstance(prompt, str)
        assert len(prompt) > 0
