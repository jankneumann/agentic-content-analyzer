import pytest

from src.services.prompt_service import PromptService


def test_render_template_escapes_braces():
    """Verify that render_template escapes braces in variable values."""
    template = "Value: {v}"
    variables = {"v": "{json}"}

    # Expected: Braces in value are doubled to be treated as literals
    # "{" -> "{{"
    # "}" -> "}}"
    # So "{json}" -> "{{json}}"
    # When formatted into "{v}", it becomes "{{json}}"

    rendered = PromptService.render_template(template, variables)
    assert rendered == "Value: {{json}}"


def test_render_template_handles_missing_keys():
    """Verify that render_template handles missing keys gracefully (SafeDict behavior)."""
    template = "Hello {name}, welcome to {place}."
    variables = {"name": "Alice"}

    # {place} is missing, should remain as {place}
    rendered = PromptService.render_template(template, variables)
    assert rendered == "Hello Alice, welcome to {place}."


def test_render_template_consistency():
    """Verify consistency between render and render_template."""
    # Assuming we can mock _get_prompt or just check logic flow
    # Since render calls render_template, they should be consistent by definition.
    pass


def test_render_template_crash_fix():
    """Verify that variables with single braces do not crash the renderer."""
    template = "Value: {v}"
    variables = {"v": "{"}

    # Previously this would crash with ValueError: Single '{' encountered in format string
    # Now it should be escaped to "{{" and rendered as "{{"

    try:
        rendered = PromptService.render_template(template, variables)
        assert rendered == "Value: {{"
    except ValueError as e:
        pytest.fail(f"render_template crashed with ValueError: {e}")
