"""Tests for PromptService with render(), versioning, and list_all improvements."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.prompt_service import PromptService, SafeDict


class TestSafeDict:
    """Tests for SafeDict used in template rendering."""

    def test_known_key(self):
        d = SafeDict(name="Alice")
        assert d["name"] == "Alice"

    def test_missing_key_returns_placeholder(self):
        d = SafeDict()
        assert d["missing"] == "{missing}"

    def test_format_map_with_safe_dict(self):
        template = "Hello {name}, you have {count} items."
        result = template.format_map(SafeDict(name="Bob"))
        assert result == "Hello Bob, you have {count} items."

    def test_format_map_all_present(self):
        template = "Hello {name}, you have {count} items."
        result = template.format_map(SafeDict(name="Bob", count="5"))
        assert result == "Hello Bob, you have 5 items."

    def test_format_map_none_present(self):
        template = "Hello {name}."
        result = template.format_map(SafeDict())
        assert result == "Hello {name}."


class TestPromptServiceRender:
    """Tests for PromptService.render() method."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        PromptService.clear_cache()
        yield
        PromptService.clear_cache()

    @patch.object(PromptService, "_load_defaults")
    def test_render_with_variables(self, mock_load):
        mock_load.return_value = {
            "pipeline": {
                "podcast_script": {
                    "length_brief": "Generate a {duration} minute script for {period}."
                }
            }
        }
        service = PromptService()
        result = service.render(
            "pipeline.podcast_script.length_brief",
            duration="5",
            period="daily",
        )
        assert result == "Generate a 5 minute script for daily."

    @patch.object(PromptService, "_load_defaults")
    def test_render_with_missing_variables(self, mock_load):
        mock_load.return_value = {
            "pipeline": {"test": {"system": "Hello {name}, period is {period}."}}
        }
        service = PromptService()
        result = service.render("pipeline.test.system", name="Alice")
        assert result == "Hello Alice, period is {period}."

    @patch.object(PromptService, "_load_defaults")
    def test_render_no_variables(self, mock_load):
        mock_load.return_value = {"pipeline": {"test": {"system": "Static prompt text."}}}
        service = PromptService()
        result = service.render("pipeline.test.system")
        assert result == "Static prompt text."

    @patch.object(PromptService, "_load_defaults")
    def test_render_missing_key(self, mock_load):
        mock_load.return_value = {"pipeline": {}}
        service = PromptService()
        result = service.render("pipeline.nonexistent.system")
        assert result == ""

    @patch.object(PromptService, "_load_defaults")
    def test_render_with_double_braces(self, mock_load):
        """Ensure double braces (JSON format) in prompts survive rendering."""
        mock_load.return_value = {
            "pipeline": {"test": {"system": 'Output: {{"key": "value"}} with {name}'}}
        }
        service = PromptService()
        result = service.render("pipeline.test.system", name="test")
        assert result == 'Output: {"key": "value"} with test'


class TestPromptServiceVersioning:
    """Tests for version auto-increment behavior."""

    def test_set_override_creates_version_1(self):
        """New override should start at version 1."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        service = PromptService.__new__(PromptService)
        service.db = mock_db
        service._defaults = {}

        service.set_override("test.key", "value")

        # Verify the PromptOverride was created with version=1
        add_call = mock_db.add.call_args
        override = add_call[0][0]
        assert override.version == 1
        assert override.key == "test.key"
        assert override.value == "value"

    def test_set_override_increments_version(self):
        """Updating existing override should increment version."""
        existing = MagicMock()
        existing.version = 3

        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = existing

        service = PromptService.__new__(PromptService)
        service.db = mock_db
        service._defaults = {}

        service.set_override("test.key", "new value", description="updated prompt")

        assert existing.value == "new value"
        assert existing.version == 4
        assert existing.description == "updated prompt"

    def test_set_override_without_db_raises(self):
        """set_override without DB session should raise ValueError."""
        service = PromptService.__new__(PromptService)
        service.db = None
        service._defaults = {}

        with pytest.raises(ValueError, match="Database session required"):
            service.set_override("test.key", "value")


class TestPromptServiceListAll:
    """Tests for list_all_prompts with non-system prompt names."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        PromptService.clear_cache()
        yield
        PromptService.clear_cache()

    @patch.object(PromptService, "_load_defaults")
    def test_list_all_includes_variants(self, mock_load):
        mock_load.return_value = {
            "chat": {"summary": {"system": "Chat prompt"}},
            "pipeline": {
                "podcast_script": {
                    "system": "System prompt",
                    "length_brief": "Brief prompt",
                    "length_standard": "Standard prompt",
                }
            },
        }
        service = PromptService()
        prompts = service.list_all_prompts()

        keys = [p["key"] for p in prompts]
        assert "chat.summary.system" in keys
        assert "pipeline.podcast_script.system" in keys
        assert "pipeline.podcast_script.length_brief" in keys
        assert "pipeline.podcast_script.length_standard" in keys

    @patch.object(PromptService, "_load_defaults")
    def test_list_all_prompt_structure(self, mock_load):
        mock_load.return_value = {"pipeline": {"test": {"system": "Test prompt"}}}
        service = PromptService()
        prompts = service.list_all_prompts()

        assert len(prompts) == 1
        p = prompts[0]
        assert p["key"] == "pipeline.test.system"
        assert p["category"] == "pipeline"
        assert p["step"] == "test"
        assert p["name"] == "system"
        assert p["default"] == "Test prompt"
        assert p["override"] is None
        assert p["has_override"] is False
        assert p["version"] is None
        assert p["description"] is None


class TestPromptServiceGetDefault:
    """Tests for get_default method."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        PromptService.clear_cache()
        yield
        PromptService.clear_cache()

    @patch.object(PromptService, "_load_defaults")
    def test_get_default_returns_yaml_value(self, mock_load):
        mock_load.return_value = {"pipeline": {"test": {"system": "Default prompt"}}}
        service = PromptService()
        assert service.get_default("pipeline.test.system") == "Default prompt"

    @patch.object(PromptService, "_load_defaults")
    def test_get_default_missing_key(self, mock_load):
        mock_load.return_value = {"pipeline": {}}
        service = PromptService()
        assert service.get_default("pipeline.missing.system") == ""
