"""Tests for HtmlMarkdownConverter."""

import pytest

from src.parsers.html_markdown import (
    HtmlMarkdownConverter,
    convert_html_to_markdown,
    validate_markdown_quality,
)


class TestValidateMarkdownQuality:
    """Tests for validate_markdown_quality function."""

    def test_valid_markdown(self):
        """Test validation passes for well-structured markdown."""
        markdown = """# Introduction

This is a paragraph with enough content to pass the length check. We need to make
sure this has at least 200 characters to satisfy the default threshold.

## Section Two

- Item one with more detailed description
- Item two with additional context
- Item three with extended information

Check out [this link](https://example.com) for more detailed information.
"""
        result = validate_markdown_quality(markdown)

        assert result.valid is True
        assert result.issues == []
        assert result.stats["has_headings"] is True
        assert result.stats["has_paragraphs"] is True
        assert result.stats["has_links"] is True

    def test_empty_content(self):
        """Test validation fails for empty content."""
        result = validate_markdown_quality(None)

        assert result.valid is False
        assert "No content extracted" in result.issues

        result = validate_markdown_quality("")
        assert result.valid is False

    def test_short_content(self):
        """Test validation fails for content below threshold."""
        result = validate_markdown_quality("Short text", min_length=200)

        assert result.valid is False
        assert any("too short" in issue for issue in result.issues)

    def test_custom_threshold(self):
        """Test custom minimum length threshold."""
        # Include structure to pass the "no structure" check
        short_text = "# Heading\n\nSome longer content here."
        result = validate_markdown_quality(short_text, min_length=30)

        assert result.valid is True
        assert result.stats["has_headings"] is True

    def test_unmatched_code_blocks(self):
        """Test detection of unmatched code blocks."""
        markdown = """# Code Example

```python
def hello():
    pass

Missing closing fence above.
"""
        result = validate_markdown_quality(markdown)

        assert result.valid is False
        assert any("Unmatched code blocks" in issue for issue in result.issues)

    def test_balanced_code_blocks(self):
        """Test balanced code blocks pass validation."""
        markdown = """# Code Example

```python
def hello():
    pass
```

More text here with enough content to pass length check easily.
"""
        result = validate_markdown_quality(markdown)

        assert result.stats["code_blocks"] == 1
        assert "Unmatched code blocks" not in result.issues


class TestHtmlMarkdownConverter:
    """Tests for HtmlMarkdownConverter class."""

    @pytest.fixture
    def converter(self):
        """Create a converter instance."""
        return HtmlMarkdownConverter()

    @pytest.fixture
    def sample_html(self):
        """Sample HTML content for testing."""
        return """
        <html>
        <head><title>Test Article</title></head>
        <body>
        <h1>Introduction to AI</h1>
        <p>Artificial intelligence is transforming the world. Here are the key points:</p>
        <ul>
        <li>Machine learning enables pattern recognition</li>
        <li>Deep learning powers modern AI systems</li>
        <li>Large language models understand natural language</li>
        </ul>
        <h2>Code Example</h2>
        <pre><code>def hello():
            print("Hello, World!")
        </code></pre>
        <p>Learn more at <a href="https://example.com">our website</a>.</p>
        </body>
        </html>
        """

    @pytest.mark.asyncio
    async def test_convert_html_to_markdown(self, converter, sample_html):
        """Test basic HTML to markdown conversion."""
        result = await converter.convert(html=sample_html)

        assert result.markdown is not None
        assert result.method == "trafilatura"
        # Trafilatura extracts main content - check for key content
        assert "artificial intelligence" in result.markdown.lower()
        assert result.quality is not None

    @pytest.mark.asyncio
    async def test_convert_preserves_structure(self, converter, sample_html):
        """Test that conversion preserves key document elements."""
        result = await converter.convert(html=sample_html)

        assert result.markdown is not None
        # Check for code block (Trafilatura preserves these)
        assert "```" in result.markdown or "def hello" in result.markdown
        # Check for links
        assert "example.com" in result.markdown

    @pytest.mark.asyncio
    async def test_convert_requires_input(self, converter):
        """Test that either url or html must be provided."""
        result = await converter.convert()

        assert result.markdown is None
        assert result.method == "failed"
        assert "must be provided" in result.error

    @pytest.mark.asyncio
    async def test_convert_empty_html(self, converter):
        """Test handling of empty HTML."""
        result = await converter.convert(html="")

        assert result.method in ["trafilatura", "failed"]
        # Empty input should fail quality check
        if result.quality:
            assert result.quality.valid is False

    @pytest.mark.asyncio
    async def test_batch_convert(self, converter, sample_html):
        """Test batch conversion of multiple items."""
        items = [
            {"html": sample_html},
            {"html": "<p>Short content</p>"},
        ]

        results = await converter.batch_convert(items, max_concurrent=2)

        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[0]["method"] == "trafilatura"

    @pytest.mark.asyncio
    async def test_batch_convert_handles_failures(self, converter):
        """Test batch conversion handles individual failures gracefully."""
        items = [
            {"html": "<h1>Valid content with enough text to pass</h1><p>More content here.</p>"},
            {},  # Invalid - no url or html
        ]

        results = await converter.batch_convert(items)

        assert len(results) == 2
        # Second item should have failed
        assert results[1]["success"] is False


class TestConvertHtmlToMarkdown:
    """Tests for the convenience function."""

    def test_basic_conversion(self):
        """Test synchronous conversion helper."""
        html = """
        <html>
        <body>
        <h1>Test Heading</h1>
        <p>This is a test paragraph with enough content to demonstrate the conversion.</p>
        <p>Trafilatura extracts the main body content from HTML documents.</p>
        </body>
        </html>
        """
        result = convert_html_to_markdown(html=html)

        assert result is not None
        # Trafilatura extracts content but may strip headings
        assert "test paragraph" in result.lower() or "trafilatura" in result.lower()

    def test_empty_input(self):
        """Test empty input returns empty string."""
        result = convert_html_to_markdown(html="")

        assert result == ""

    def test_none_input(self):
        """Test None input returns empty string."""
        result = convert_html_to_markdown(html=None)

        assert result == ""
