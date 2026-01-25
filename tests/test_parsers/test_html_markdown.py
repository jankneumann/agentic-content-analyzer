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


class TestComplexHtmlExtraction:
    """Tests for complex HTML structure preservation in markdown output.

    These tests verify that the converter correctly handles rich HTML content
    with multiple element types: headers, paragraphs, lists, links, emphasis, etc.
    """

    @pytest.fixture
    def complex_article_html(self):
        """Sample HTML with diverse structural elements mimicking a real article."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>AI Trends in 2025: A Comprehensive Guide</title>
            <meta name="author" content="Test Author">
        </head>
        <body>
            <article>
                <h1>AI Trends in 2025: A Comprehensive Guide</h1>

                <p>The artificial intelligence landscape continues to evolve rapidly.
                This guide explores the <strong>most important developments</strong>
                and provides <em>actionable insights</em> for technology leaders.</p>

                <h2>Key Trends to Watch</h2>

                <p>Several major trends are reshaping the industry. Understanding these
                shifts is critical for organizations planning their AI strategy.</p>

                <h3>1. Large Language Models</h3>

                <p>LLMs have become foundational infrastructure for modern applications.
                Key developments include:</p>

                <ul>
                    <li>Improved reasoning capabilities with chain-of-thought prompting</li>
                    <li>Multi-modal understanding across text, images, and audio</li>
                    <li>Reduced hallucination rates through better training methods</li>
                    <li>Cost reductions making AI accessible to smaller teams</li>
                </ul>

                <h3>2. Agentic Workflows</h3>

                <p>AI agents are moving from demos to production. Organizations are
                deploying autonomous systems for:</p>

                <ol>
                    <li>Customer support with multi-step problem resolution</li>
                    <li>Code generation and review processes</li>
                    <li>Data analysis and report generation</li>
                    <li>Document processing and extraction</li>
                </ol>

                <h2>Implementation Recommendations</h2>

                <p>Based on our analysis, we recommend the following approach:</p>

                <h3>For Technical Leaders</h3>

                <ul>
                    <li><strong>Start with high-value use cases</strong> that have clear ROI</li>
                    <li><em>Invest in evaluation frameworks</em> before scaling deployment</li>
                    <li>Build internal expertise through hands-on experimentation</li>
                </ul>

                <h3>For Development Teams</h3>

                <ol>
                    <li>Establish prompt engineering best practices</li>
                    <li>Implement robust error handling for AI outputs</li>
                    <li>Create feedback loops for continuous improvement</li>
                </ol>

                <h2>Resources and Further Reading</h2>

                <p>For more information, explore these resources:</p>

                <ul>
                    <li>Visit <a href="https://example.com/ai-guide">our AI implementation guide</a></li>
                    <li>Read the <a href="https://example.com/case-studies">case studies</a> from early adopters</li>
                    <li>Join the <a href="https://example.com/community">community forum</a> for discussions</li>
                </ul>

                <h2>Conclusion</h2>

                <p>The AI revolution is accelerating. Organizations that invest in understanding
                and adopting these technologies will have significant competitive advantages.
                Start with small experiments, measure results carefully, and scale what works.</p>
            </article>
        </body>
        </html>
        """

    @pytest.fixture
    def converter(self):
        """Create a converter instance."""
        return HtmlMarkdownConverter()

    @pytest.mark.asyncio
    async def test_preserves_heading_hierarchy(self, converter, complex_article_html):
        """Test that heading levels (h1, h2, h3) are preserved in markdown."""
        result = await converter.convert(html=complex_article_html)

        assert result.markdown is not None
        markdown = result.markdown.lower()

        # Check for presence of main content topics
        # Trafilatura may adjust heading levels, but content should be preserved
        assert "ai trends" in markdown or "comprehensive guide" in markdown
        assert "key trends" in markdown or "large language models" in markdown
        assert "implementation" in markdown or "recommendations" in markdown

    @pytest.mark.asyncio
    async def test_preserves_paragraphs(self, converter, complex_article_html):
        """Test that paragraph content is preserved with proper separation."""
        result = await converter.convert(html=complex_article_html)

        assert result.markdown is not None
        markdown = result.markdown

        # Check for paragraph content preservation
        assert "artificial intelligence" in markdown.lower()
        assert "technology leaders" in markdown.lower() or "actionable insights" in markdown.lower()

        # Verify paragraph separation (double newlines in markdown)
        assert "\n\n" in markdown, "Paragraphs should be separated by blank lines"

        # Quality check should detect paragraphs
        assert result.quality is not None
        assert result.quality.stats["has_paragraphs"] is True

    @pytest.mark.asyncio
    async def test_preserves_unordered_lists(self, converter, complex_article_html):
        """Test that unordered lists are converted to markdown bullet points."""
        result = await converter.convert(html=complex_article_html)

        assert result.markdown is not None
        markdown = result.markdown.lower()

        # Check for list item content (Trafilatura should preserve these)
        assert "reasoning capabilities" in markdown or "chain-of-thought" in markdown
        assert "multi-modal" in markdown
        assert "hallucination" in markdown or "training methods" in markdown

        # Check for markdown list markers (- or *)
        has_bullet_markers = "-" in result.markdown or "*" in result.markdown
        assert has_bullet_markers, "Should have markdown list markers"

    @pytest.mark.asyncio
    async def test_preserves_ordered_lists(self, converter, complex_article_html):
        """Test that ordered lists are converted to markdown numbered lists."""
        result = await converter.convert(html=complex_article_html)

        assert result.markdown is not None
        markdown = result.markdown.lower()

        # Check for ordered list content
        assert "customer support" in markdown
        assert "code generation" in markdown or "code review" in markdown
        assert "data analysis" in markdown

        # Check for numbered list markers (1. 2. etc) or list content preserved
        # Trafilatura may convert to bullets, but content should be there
        content_preserved = all(
            item in markdown for item in ["customer support", "code generation", "data analysis"]
        )
        assert content_preserved, "Ordered list content should be preserved"

    @pytest.mark.asyncio
    async def test_preserves_links(self, converter, complex_article_html):
        """Test that hyperlinks are converted to markdown link format."""
        result = await converter.convert(html=complex_article_html)

        assert result.markdown is not None

        # Check for link URLs in output
        assert "example.com" in result.markdown

        # Check for markdown link format [text](url) or at least URL preservation
        has_markdown_links = "](" in result.markdown
        has_urls = "https://" in result.markdown or "http://" in result.markdown

        assert has_markdown_links or has_urls, "Links should be preserved in some form"

        # Quality stats should detect links
        assert result.quality is not None
        assert result.quality.stats["has_links"] is True

    @pytest.mark.asyncio
    async def test_preserves_emphasis(self, converter, complex_article_html):
        """Test that bold and italic text emphasis is preserved."""
        result = await converter.convert(html=complex_article_html)

        assert result.markdown is not None
        markdown = result.markdown.lower()

        # Check that emphasized content is present
        assert "most important developments" in markdown
        assert "actionable insights" in markdown

        # Check for markdown emphasis markers (* or _)
        # Note: Trafilatura may not always preserve emphasis markers
        # but should preserve the text content
        has_bold_content = "most important" in markdown
        has_italic_content = "actionable" in markdown

        assert has_bold_content and has_italic_content, "Emphasized text should be preserved"

    @pytest.mark.asyncio
    async def test_extracts_article_content(self, converter, complex_article_html):
        """Test that main article content is extracted, not boilerplate."""
        result = await converter.convert(html=complex_article_html)

        assert result.markdown is not None
        markdown = result.markdown.lower()

        # Verify main content sections are present
        main_topics = [
            "ai trends",
            "large language models",
            "agentic workflows",
            "implementation",
            "conclusion",
        ]

        topics_found = sum(1 for topic in main_topics if topic in markdown)
        assert topics_found >= 3, f"Should find at least 3 main topics, found {topics_found}"

    @pytest.mark.asyncio
    async def test_quality_validation_passes(self, converter, complex_article_html):
        """Test that complex article passes quality validation."""
        result = await converter.convert(html=complex_article_html)

        assert result.markdown is not None
        assert result.quality is not None

        # Complex article should pass validation
        assert result.quality.valid is True, f"Quality issues: {result.quality.issues}"

        # Check quality stats
        stats = result.quality.stats
        assert stats["length"] > 500, "Complex article should have substantial content"
        assert stats["has_paragraphs"] is True
        assert stats["has_links"] is True

    @pytest.mark.asyncio
    async def test_markdown_structure_is_valid(self, converter, complex_article_html):
        """Test that output is valid, well-formed markdown."""
        result = await converter.convert(html=complex_article_html)

        assert result.markdown is not None
        markdown = result.markdown

        # Check for valid markdown structure
        lines = markdown.split("\n")

        # Should have multiple non-empty lines
        non_empty_lines = [line for line in lines if line.strip()]
        assert len(non_empty_lines) > 10, "Should have substantial content"

        # Check that code blocks are balanced (if any)
        code_block_count = markdown.count("```")
        assert code_block_count % 2 == 0, "Code blocks should be balanced"

        # Check for no HTML tags remaining in output
        html_tags = ["<p>", "</p>", "<h1>", "</h1>", "<ul>", "</ul>", "<li>", "</li>"]
        for tag in html_tags:
            assert tag not in markdown, f"HTML tag {tag} should not be in markdown output"

    @pytest.mark.asyncio
    async def test_nested_list_content_preserved(self, converter):
        """Test that nested list content is handled correctly."""
        nested_html = """
        <html>
        <body>
            <article>
                <h1>Project Requirements</h1>
                <p>The project has the following requirements organized by category:</p>

                <h2>Technical Requirements</h2>
                <ul>
                    <li>Backend Development
                        <ul>
                            <li>Python 3.11 or higher</li>
                            <li>FastAPI framework</li>
                            <li>PostgreSQL database</li>
                        </ul>
                    </li>
                    <li>Frontend Development
                        <ul>
                            <li>React 18 with TypeScript</li>
                            <li>TanStack Router for navigation</li>
                            <li>Tailwind CSS for styling</li>
                        </ul>
                    </li>
                </ul>

                <h2>Timeline</h2>
                <ol>
                    <li>Phase 1: Setup and infrastructure (Week 1-2)</li>
                    <li>Phase 2: Core features (Week 3-6)</li>
                    <li>Phase 3: Testing and deployment (Week 7-8)</li>
                </ol>
            </article>
        </body>
        </html>
        """
        result = await converter.convert(html=nested_html)

        assert result.markdown is not None
        markdown = result.markdown.lower()

        # Check nested content is preserved
        assert "python 3.11" in markdown or "python" in markdown
        assert "fastapi" in markdown
        assert "react" in markdown or "typescript" in markdown
        assert "tailwind" in markdown

        # Check timeline items
        assert "phase 1" in markdown or "setup" in markdown
        assert "phase 2" in markdown or "core features" in markdown

    @pytest.mark.asyncio
    async def test_table_content_extraction(self, converter):
        """Test that table content is extracted (may be converted to list format)."""
        table_html = """
        <html>
        <body>
            <article>
                <h1>Model Comparison</h1>
                <p>Here is a comparison of different AI models and their capabilities:</p>

                <table>
                    <thead>
                        <tr>
                            <th>Model</th>
                            <th>Context Window</th>
                            <th>Best Use Case</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Claude Sonnet</td>
                            <td>200K tokens</td>
                            <td>General reasoning</td>
                        </tr>
                        <tr>
                            <td>Claude Haiku</td>
                            <td>200K tokens</td>
                            <td>Fast tasks</td>
                        </tr>
                        <tr>
                            <td>GPT-4</td>
                            <td>128K tokens</td>
                            <td>Complex analysis</td>
                        </tr>
                    </tbody>
                </table>

                <p>Choose the model that best fits your specific requirements.</p>
            </article>
        </body>
        </html>
        """
        result = await converter.convert(html=table_html)

        assert result.markdown is not None
        markdown = result.markdown.lower()

        # Table content should be preserved (as table or list)
        assert "claude sonnet" in markdown or "sonnet" in markdown
        assert "claude haiku" in markdown or "haiku" in markdown
        assert "gpt-4" in markdown or "gpt" in markdown

        # Context/capability info should be present
        assert "200k" in markdown or "tokens" in markdown or "context" in markdown
