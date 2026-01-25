"""Tests for DigestTextPreparer."""

from unittest.mock import MagicMock

import pytest

from src.processors.digest_text_preparer import WORDS_PER_MINUTE, DigestTextPreparer


class TestDigestTextPreparerInitialization:
    """Tests for DigestTextPreparer initialization."""

    def test_default_initialization(self):
        """Test default initialization without SSML."""
        preparer = DigestTextPreparer()
        assert preparer.use_ssml is False

    def test_initialization_with_ssml_enabled(self):
        """Test initialization with SSML enabled."""
        preparer = DigestTextPreparer(use_ssml=True)
        assert preparer.use_ssml is True

    def test_initialization_with_ssml_disabled(self):
        """Test explicit SSML disabled initialization."""
        preparer = DigestTextPreparer(use_ssml=False)
        assert preparer.use_ssml is False


class TestBasicPrepare:
    """Tests for basic prepare() functionality."""

    def test_empty_string_returns_empty(self):
        """Test empty string input returns empty string."""
        preparer = DigestTextPreparer()
        assert preparer.prepare("") == ""

    def test_whitespace_only_returns_empty(self):
        """Test whitespace-only input returns empty string."""
        preparer = DigestTextPreparer()
        assert preparer.prepare("   ") == ""
        assert preparer.prepare("\n\n") == ""
        assert preparer.prepare("\t\t") == ""

    def test_plain_text_unchanged(self):
        """Test plain text without markdown passes through."""
        preparer = DigestTextPreparer()
        text = "This is plain text without any markdown."
        result = preparer.prepare(text)
        assert "This is plain text without any markdown" in result

    def test_preserves_paragraphs(self):
        """Test paragraph structure is preserved."""
        preparer = DigestTextPreparer()
        text = "First paragraph.\n\nSecond paragraph."
        result = preparer.prepare(text)
        assert "First paragraph" in result
        assert "Second paragraph" in result


class TestHeadingProcessing:
    """Tests for heading conversion."""

    def test_h1_heading_without_ssml(self):
        """Test H1 heading conversion without SSML."""
        preparer = DigestTextPreparer(use_ssml=False)
        result = preparer.prepare("# Main Heading")
        assert "Main Heading." in result
        # No SSML tags
        assert "<break" not in result

    def test_h2_heading_without_ssml(self):
        """Test H2 heading conversion without SSML."""
        preparer = DigestTextPreparer(use_ssml=False)
        result = preparer.prepare("## Sub Heading")
        assert "Sub Heading." in result

    def test_h3_heading_without_ssml(self):
        """Test H3 heading conversion without SSML."""
        preparer = DigestTextPreparer(use_ssml=False)
        result = preparer.prepare("### Third Level")
        assert "Third Level." in result

    def test_heading_with_ssml(self):
        """Test heading conversion with SSML breaks."""
        preparer = DigestTextPreparer(use_ssml=True)
        result = preparer.prepare("# Main Heading")
        assert "Main Heading." in result
        assert '<break time="' in result

    def test_heading_preserves_existing_punctuation(self):
        """Test heading with existing punctuation."""
        preparer = DigestTextPreparer()
        result = preparer.prepare("# Is This a Question?")
        assert "Is This a Question?" in result
        # Should not double punctuation
        assert "?." not in result

    def test_multiple_headings(self):
        """Test multiple headings in document."""
        preparer = DigestTextPreparer()
        text = "# First\n\nContent here.\n\n## Second\n\nMore content."
        result = preparer.prepare(text)
        assert "First." in result
        assert "Second." in result
        assert "Content here" in result


class TestListProcessing:
    """Tests for list conversion."""

    def test_unordered_list_without_ssml(self):
        """Test unordered list conversion without SSML."""
        preparer = DigestTextPreparer(use_ssml=False)
        text = "- First item\n- Second item\n- Third item"
        result = preparer.prepare(text)
        assert "First item" in result
        assert "Second item" in result
        assert "Third item" in result
        # Bullets should be removed
        assert "- " not in result

    def test_unordered_list_with_asterisk(self):
        """Test unordered list with asterisk markers."""
        preparer = DigestTextPreparer()
        text = "* Item one\n* Item two"
        result = preparer.prepare(text)
        assert "Item one" in result
        assert "Item two" in result
        assert "* " not in result

    def test_numbered_list_without_ssml(self):
        """Test numbered list conversion without SSML."""
        preparer = DigestTextPreparer(use_ssml=False)
        text = "1. First item\n2. Second item\n3. Third item"
        result = preparer.prepare(text)
        assert "1. First item" in result
        assert "2. Second item" in result
        assert "3. Third item" in result

    def test_list_with_ssml(self):
        """Test list conversion with SSML breaks."""
        preparer = DigestTextPreparer(use_ssml=True)
        text = "- Item one\n- Item two"
        result = preparer.prepare(text)
        assert "Item one" in result
        assert '<break time="200ms"/>' in result


class TestLinkProcessing:
    """Tests for link conversion."""

    def test_link_keeps_text_removes_url(self):
        """Test link text is kept but URL is removed."""
        preparer = DigestTextPreparer()
        text = "Check out [this article](https://example.com/article) for more."
        result = preparer.prepare(text)
        assert "this article" in result
        assert "https://example.com" not in result
        assert "[" not in result
        assert "](" not in result

    def test_multiple_links(self):
        """Test multiple links in text."""
        preparer = DigestTextPreparer()
        text = "[First](https://first.com) and [Second](https://second.com)"
        result = preparer.prepare(text)
        assert "First" in result
        assert "Second" in result
        assert "https://" not in result

    def test_link_with_special_characters(self):
        """Test link with special characters in text."""
        preparer = DigestTextPreparer()
        text = "[AI/ML Guide](https://example.com)"
        result = preparer.prepare(text)
        assert "AI/ML Guide" in result


class TestBoldItalicProcessing:
    """Tests for bold and italic formatting removal."""

    def test_bold_text_keeps_content(self):
        """Test bold markers are removed but text is kept."""
        preparer = DigestTextPreparer()
        text = "This is **important** text."
        result = preparer.prepare(text)
        assert "important" in result
        assert "**" not in result

    def test_italic_text_keeps_content(self):
        """Test italic markers are removed but text is kept."""
        preparer = DigestTextPreparer()
        text = "This is *emphasized* text."
        result = preparer.prepare(text)
        assert "emphasized" in result
        # Check italic asterisks are removed but not affecting text
        assert "*emphasized*" not in result

    def test_nested_bold_italic(self):
        """Test nested bold and italic formatting."""
        preparer = DigestTextPreparer()
        text = "This is ***bold and italic*** text."
        result = preparer.prepare(text)
        assert "bold and italic" in result


class TestCodeBlockProcessing:
    """Tests for code block handling."""

    def test_code_block_replaced_with_announcement(self):
        """Test code blocks are replaced with announcement."""
        preparer = DigestTextPreparer()
        text = "Here is code:\n```python\ndef hello():\n    print('Hello')\n```\nMore text."
        result = preparer.prepare(text)
        assert "Code example omitted" in result
        assert "def hello" not in result
        assert "print" not in result
        assert "More text" in result

    def test_code_block_with_ssml(self):
        """Test code block replacement with SSML."""
        preparer = DigestTextPreparer(use_ssml=True)
        text = "```\ncode here\n```"
        result = preparer.prepare(text)
        assert "Code example omitted" in result
        assert '<break time="200ms"/>' in result

    def test_inline_code_keeps_text(self):
        """Test inline code markers are removed but text is kept."""
        preparer = DigestTextPreparer()
        text = "Use the `print()` function."
        result = preparer.prepare(text)
        assert "print()" in result
        assert "`" not in result


class TestBlockquoteProcessing:
    """Tests for blockquote handling."""

    def test_blockquote_removes_marker(self):
        """Test blockquote > marker is removed."""
        preparer = DigestTextPreparer()
        text = "> This is a quote.\n> It continues here."
        result = preparer.prepare(text)
        assert "This is a quote" in result
        assert "It continues here" in result
        assert ">" not in result

    def test_nested_blockquote(self):
        """Test nested blockquotes."""
        preparer = DigestTextPreparer()
        text = "> Level one\n>> Level two"
        result = preparer.prepare(text)
        assert "Level one" in result
        # Nested quote marker should be handled
        assert "Level two" in result


class TestImageProcessing:
    """Tests for image reference handling."""

    def test_image_with_alt_text(self):
        """Test image with alt text is converted."""
        preparer = DigestTextPreparer()
        text = "![A diagram](https://example.com/image.png)"
        result = preparer.prepare(text)
        assert "Image: A diagram" in result
        assert "https://" not in result

    def test_image_without_alt_text(self):
        """Test image without alt text is removed."""
        preparer = DigestTextPreparer()
        text = "Before ![](https://example.com/image.png) after"
        result = preparer.prepare(text)
        assert "Before" in result
        assert "after" in result
        assert "https://" not in result


class TestHorizontalRuleProcessing:
    """Tests for horizontal rule handling."""

    def test_horizontal_rule_removed(self):
        """Test horizontal rules are handled properly."""
        preparer = DigestTextPreparer()
        text = "Section one.\n\n---\n\nSection two."
        result = preparer.prepare(text)
        assert "Section one" in result
        assert "Section two" in result
        assert "---" not in result

    def test_horizontal_rule_with_ssml(self):
        """Test horizontal rule with SSML break."""
        preparer = DigestTextPreparer(use_ssml=True)
        text = "Before\n\n---\n\nAfter"
        result = preparer.prepare(text)
        assert "Before" in result
        assert "After" in result
        assert '<break time="600ms"/>' in result


class TestSSMLOutput:
    """Tests for SSML output mode."""

    def test_ssml_breaks_in_headings(self):
        """Test SSML breaks are added around headings."""
        preparer = DigestTextPreparer(use_ssml=True)
        result = preparer.prepare("# Heading")
        assert '<break time="' in result

    def test_ssml_breaks_in_lists(self):
        """Test SSML breaks between list items."""
        preparer = DigestTextPreparer(use_ssml=True)
        result = preparer.prepare("- Item 1\n- Item 2")
        assert '<break time="200ms"/>' in result

    def test_no_ssml_when_disabled(self):
        """Test no SSML tags when disabled."""
        preparer = DigestTextPreparer(use_ssml=False)
        text = "# Heading\n\n- List item\n\nParagraph."
        result = preparer.prepare(text)
        assert "<break" not in result
        assert "/>" not in result


class TestDurationEstimation:
    """Tests for duration estimation."""

    def test_duration_empty_text(self):
        """Test duration estimation for empty text."""
        preparer = DigestTextPreparer()
        assert preparer.estimate_duration("") == 0.0
        assert preparer.estimate_duration("   ") == 0.0

    def test_duration_single_word(self):
        """Test duration for single word."""
        preparer = DigestTextPreparer()
        duration = preparer.estimate_duration("Hello")
        # 1 word at 150 WPM = 0.4 seconds
        expected = 1 / (WORDS_PER_MINUTE / 60)
        assert duration == pytest.approx(expected, rel=0.01)

    def test_duration_150_words(self):
        """Test duration for 150 words (should be 60 seconds)."""
        preparer = DigestTextPreparer()
        text = " ".join(["word"] * 150)
        duration = preparer.estimate_duration(text)
        assert duration == pytest.approx(60.0, rel=0.01)

    def test_duration_ignores_ssml_tags(self):
        """Test duration estimation ignores SSML tags."""
        preparer = DigestTextPreparer()
        text_without_ssml = "Hello world"
        text_with_ssml = 'Hello <break time="500ms"/> world'

        duration_without = preparer.estimate_duration(text_without_ssml)
        duration_with = preparer.estimate_duration(text_with_ssml)

        assert duration_without == duration_with

    def test_duration_realistic_text(self):
        """Test duration for realistic paragraph."""
        preparer = DigestTextPreparer()
        # ~30 words = ~12 seconds
        text = (
            "This is a sample paragraph of text that contains roughly thirty words "
            "to test the duration estimation function for realistic content that "
            "might appear in a digest."
        )
        duration = preparer.estimate_duration(text)
        # Should be between 8-16 seconds for ~30 words
        assert 8 < duration < 16


class TestPrepareDigest:
    """Tests for prepare_digest() method."""

    def test_prepare_digest_with_markdown_content(self):
        """Test preparing digest with markdown_content field."""
        preparer = DigestTextPreparer()

        # Create mock digest with markdown_content
        digest = MagicMock()
        digest.id = 1
        digest.markdown_content = "# Test Digest\n\nThis is the content."

        result = preparer.prepare_digest(digest)

        assert "Test Digest." in result
        assert "This is the content" in result

    def test_prepare_digest_fallback_to_fields(self):
        """Test preparing digest falls back to structured fields."""
        preparer = DigestTextPreparer()

        # Create mock digest without markdown_content
        digest = MagicMock()
        digest.id = 2
        digest.markdown_content = None
        digest.title = "Weekly AI Digest"
        digest.executive_overview = "This week saw major developments."
        digest.strategic_insights = [{"title": "AI Growth", "summary": "AI is growing rapidly."}]
        digest.technical_developments = []
        digest.emerging_trends = []

        result = preparer.prepare_digest(digest)

        assert "Weekly AI Digest" in result
        assert "This week saw major developments" in result
        assert "AI Growth" in result

    def test_prepare_digest_with_ssml(self):
        """Test preparing digest with SSML enabled."""
        preparer = DigestTextPreparer(use_ssml=True)

        digest = MagicMock()
        digest.id = 3
        digest.markdown_content = "# Heading\n\nContent here."

        result = preparer.prepare_digest(digest)

        assert '<break time="' in result

    def test_prepare_digest_structured_fields_with_ssml(self):
        """Test structured field fallback with SSML."""
        preparer = DigestTextPreparer(use_ssml=True)

        digest = MagicMock()
        digest.id = 4
        digest.markdown_content = None
        digest.title = "Test Title"
        digest.executive_overview = "Overview text."
        digest.strategic_insights = []
        digest.technical_developments = []
        digest.emerging_trends = []

        result = preparer.prepare_digest(digest)

        assert "Test Title" in result
        assert '<break time="' in result


class TestComplexDocuments:
    """Tests for complex document processing."""

    def test_full_digest_structure(self):
        """Test processing a full digest-like document."""
        preparer = DigestTextPreparer()
        text = """# AI Weekly Digest

## Executive Summary

This week brought significant **advances** in machine learning.

## Key Developments

### LLM Improvements

Large language models continue to improve with:

- Longer context windows
- Better reasoning
- Lower costs

See [this article](https://example.com) for more details.

### Code Examples

```python
model = load_model()
```

## Recommendations

1. Evaluate new models
2. Update infrastructure
3. Train teams
"""
        result = preparer.prepare(text)

        # Check key content is preserved
        assert "AI Weekly Digest" in result
        assert "Executive Summary" in result
        assert "advances" in result
        assert "Longer context windows" in result
        assert "this article" in result
        assert "Code example omitted" in result
        assert "1. Evaluate new models" in result

        # Check markdown is removed
        assert "**" not in result
        assert "[" not in result
        assert "](https://" not in result
        assert "```" not in result

    def test_mixed_content_preservation(self):
        """Test that mixed content types are all processed."""
        preparer = DigestTextPreparer()
        text = """
# Title

> A quote here

- List item

1. Numbered item

**Bold** and *italic* and `code` and [link](url).
"""
        result = preparer.prepare(text)

        assert "Title" in result
        assert "A quote here" in result
        assert "List item" in result
        assert "1. Numbered item" in result
        assert "Bold" in result
        assert "italic" in result
        assert "code" in result
        assert "link" in result

        # All markdown removed
        assert ">" not in result or ">>" not in result
        assert "**" not in result
        assert "*italic*" not in result
        assert "`code`" not in result
        assert "[link]" not in result


class TestEdgeCases:
    """Tests for edge cases."""

    def test_consecutive_headings(self):
        """Test consecutive headings without content between."""
        preparer = DigestTextPreparer()
        text = "# First\n## Second\n### Third"
        result = preparer.prepare(text)
        assert "First" in result
        assert "Second" in result
        assert "Third" in result

    def test_empty_list_items(self):
        """Test empty list items are handled."""
        preparer = DigestTextPreparer()
        text = "- Item one\n-\n- Item three"
        result = preparer.prepare(text)
        assert "Item one" in result
        assert "Item three" in result

    def test_unicode_content(self):
        """Test unicode content is preserved."""
        preparer = DigestTextPreparer()
        text = "# \u4eba\u5de5\u667a\u80fd\u65e5\u62a5\n\nChinese: \u4f60\u597d, Japanese: \u3053\u3093\u306b\u3061\u306f"
        result = preparer.prepare(text)
        assert "\u4eba\u5de5\u667a\u80fd\u65e5\u62a5" in result
        assert "\u4f60\u597d" in result
        assert "\u3053\u3093\u306b\u3061\u306f" in result

    def test_very_long_heading(self):
        """Test very long headings are handled."""
        preparer = DigestTextPreparer()
        long_heading = "A" * 500
        text = f"# {long_heading}"
        result = preparer.prepare(text)
        assert long_heading in result

    def test_special_characters_preserved(self):
        """Test special characters in text are preserved."""
        preparer = DigestTextPreparer()
        text = "Temperature: 98.6F. Cost: $500. Progress: 50%."
        result = preparer.prepare(text)
        assert "98.6F" in result
        assert "$500" in result
        assert "50%" in result

    def test_nested_formatting(self):
        """Test deeply nested formatting."""
        preparer = DigestTextPreparer()
        text = "This is **bold with *nested italic* inside**."
        result = preparer.prepare(text)
        # Should handle gracefully
        assert "bold" in result
        assert "nested" in result


class TestWhitespaceCleanup:
    """Tests for whitespace cleanup."""

    def test_multiple_spaces_normalized(self):
        """Test multiple spaces are normalized to single space."""
        preparer = DigestTextPreparer()
        text = "Too    many     spaces"
        result = preparer.prepare(text)
        assert "  " not in result

    def test_multiple_newlines_normalized(self):
        """Test excessive newlines are normalized."""
        preparer = DigestTextPreparer()
        text = "Paragraph one.\n\n\n\n\nParagraph two."
        result = preparer.prepare(text)
        assert "\n\n\n" not in result

    def test_leading_trailing_whitespace_stripped(self):
        """Test leading/trailing whitespace is stripped."""
        preparer = DigestTextPreparer()
        text = "   Some text   "
        result = preparer.prepare(text)
        assert result == "Some text"
