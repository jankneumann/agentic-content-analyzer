"""Tests for content hashing and normalization utilities."""

from src.utils.content_hash import (
    generate_content_hash,
    generate_file_hash,
    generate_markdown_hash,
    normalize_content,
    normalize_markdown,
)


class TestNormalizeContent:
    """Tests for raw content normalization."""

    def test_empty_string(self):
        """Empty string returns empty string."""
        assert normalize_content("") == ""

    def test_lowercase_conversion(self):
        """Text is converted to lowercase."""
        assert normalize_content("HELLO World") == "hello world"

    def test_html_tag_removal(self):
        """HTML tags are stripped."""
        assert normalize_content("<p>Hello</p>") == "hello"
        assert normalize_content("<div><span>Test</span></div>") == "test"

    def test_html_entity_decoding(self):
        """Common HTML entities are decoded."""
        result = normalize_content("&amp; &lt; &gt; &quot; &#39;")
        assert "&" in result
        assert "<" in result
        assert ">" in result
        assert '"' in result
        assert "'" in result

    def test_url_removal(self):
        """URLs are removed."""
        result = normalize_content("Visit https://example.com for more")
        assert "https" not in result
        assert "example.com" not in result

    def test_email_removal(self):
        """Email addresses are removed."""
        result = normalize_content("Contact me at test@example.com today")
        assert "@" not in result
        assert "example.com" not in result

    def test_whitespace_normalization(self):
        """Multiple whitespace is collapsed."""
        result = normalize_content("hello    world  test")
        assert result == "hello world test"

    def test_footer_removal(self):
        """Common email footers are removed."""
        result = normalize_content("Content here\nUnsubscribe from this list")
        assert "unsubscribe" not in result


class TestGenerateContentHash:
    """Tests for raw content hash generation."""

    def test_consistent_hash(self):
        """Same content produces same hash."""
        hash1 = generate_content_hash("Hello World")
        hash2 = generate_content_hash("Hello World")
        assert hash1 == hash2

    def test_hash_length(self):
        """Hash is 64 characters (SHA-256 hex)."""
        result = generate_content_hash("Test content")
        assert len(result) == 64

    def test_normalization_applied(self):
        """Hash is based on normalized content."""
        # These should produce the same hash due to normalization
        hash1 = generate_content_hash("HELLO   WORLD")
        hash2 = generate_content_hash("hello world")
        assert hash1 == hash2

    def test_different_content_different_hash(self):
        """Different content produces different hash."""
        hash1 = generate_content_hash("Content A")
        hash2 = generate_content_hash("Content B")
        assert hash1 != hash2

    def test_empty_content(self):
        """Empty content returns consistent hash."""
        hash1 = generate_content_hash("")
        hash2 = generate_content_hash("")
        assert hash1 == hash2


class TestNormalizeMarkdown:
    """Tests for markdown content normalization."""

    def test_empty_string(self):
        """Empty string returns empty string."""
        assert normalize_markdown("") == ""

    def test_trailing_whitespace_removal(self):
        """Trailing whitespace per line is removed."""
        result = normalize_markdown("Line 1   \nLine 2  ")
        assert result == "Line 1\nLine 2"

    def test_list_marker_normalization(self):
        """List markers (-, *, +) are normalized to -."""
        result = normalize_markdown("* Item 1\n+ Item 2\n- Item 3")
        lines = result.split("\n")
        assert all(line.startswith("-") for line in lines if line.strip())

    def test_multiple_blank_lines_collapsed(self):
        """Multiple blank lines are collapsed to single."""
        result = normalize_markdown("Para 1\n\n\n\nPara 2")
        assert "\n\n\n" not in result
        assert result == "Para 1\n\nPara 2"

    def test_preserve_code_indentation(self):
        """Code block indentation is preserved."""
        markdown = "    def foo():\n        pass"
        result = normalize_markdown(markdown)
        # 4-space indentation should be preserved
        assert "    " in result

    def test_preserve_heading_structure(self):
        """Heading structure is preserved."""
        markdown = "# Title\n\n## Section\n\nContent"
        result = normalize_markdown(markdown)
        assert "# Title" in result
        assert "## Section" in result


class TestGenerateMarkdownHash:
    """Tests for markdown hash generation."""

    def test_consistent_hash(self):
        """Same markdown produces same hash."""
        markdown = "# Title\n\nContent here"
        hash1 = generate_markdown_hash(markdown)
        hash2 = generate_markdown_hash(markdown)
        assert hash1 == hash2

    def test_hash_length(self):
        """Hash is 64 characters (SHA-256 hex)."""
        result = generate_markdown_hash("# Test")
        assert len(result) == 64

    def test_whitespace_variations_same_hash(self):
        """Minor whitespace variations produce same hash."""
        hash1 = generate_markdown_hash("# Title  \n\nContent")
        hash2 = generate_markdown_hash("# Title\n\nContent")
        assert hash1 == hash2

    def test_list_marker_variations_same_hash(self):
        """Different list markers produce same hash."""
        hash1 = generate_markdown_hash("* Item 1\n* Item 2")
        hash2 = generate_markdown_hash("- Item 1\n- Item 2")
        assert hash1 == hash2

    def test_different_content_different_hash(self):
        """Different content produces different hash."""
        hash1 = generate_markdown_hash("# Title A")
        hash2 = generate_markdown_hash("# Title B")
        assert hash1 != hash2

    def test_structural_difference_different_hash(self):
        """Structural differences produce different hash."""
        hash1 = generate_markdown_hash("# Title\n\nParagraph")
        hash2 = generate_markdown_hash("## Title\n\nParagraph")
        assert hash1 != hash2


class TestGenerateFileHash:
    """Tests for file hash generation."""

    def test_consistent_hash(self):
        """Same bytes produce same hash."""
        data = b"file content"
        hash1 = generate_file_hash(data)
        hash2 = generate_file_hash(data)
        assert hash1 == hash2

    def test_hash_length(self):
        """Hash is 64 characters (SHA-256 hex)."""
        result = generate_file_hash(b"test")
        assert len(result) == 64

    def test_different_content_different_hash(self):
        """Different bytes produce different hash."""
        hash1 = generate_file_hash(b"content a")
        hash2 = generate_file_hash(b"content b")
        assert hash1 != hash2

    def test_binary_data(self):
        """Works with binary data."""
        # Simulating PDF-like binary content
        binary_data = bytes([0x25, 0x50, 0x44, 0x46, 0x2D])  # %PDF-
        result = generate_file_hash(binary_data)
        assert len(result) == 64

    def test_empty_bytes(self):
        """Empty bytes produce consistent hash."""
        hash1 = generate_file_hash(b"")
        hash2 = generate_file_hash(b"")
        assert hash1 == hash2
        # SHA-256 of empty string is known
        assert hash1 == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
