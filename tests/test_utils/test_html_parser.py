"""Tests for HTML parsing utilities."""

import pytest

from src.utils.html_parser import (
    clean_html,
    extract_links,
    html_to_text,
    remove_tracking_params,
)


def test_html_to_text():
    """Test HTML to text conversion."""
    html = """
    <html>
        <body>
            <h1>Title</h1>
            <p>First paragraph.</p>
            <p>Second paragraph.</p>
            <script>alert('test');</script>
        </body>
    </html>
    """

    text = html_to_text(html)
    assert "Title" in text
    assert "First paragraph" in text
    assert "Second paragraph" in text
    assert "alert" not in text  # Script should be removed


def test_extract_links():
    """Test link extraction from HTML."""
    html = """
    <html>
        <body>
            <a href="https://example.com/article">Article</a>
            <a href="http://test.com">Test</a>
            <a href="mailto:test@example.com">Email</a>
            <a href="javascript:void(0)">JS Link</a>
            <a href="#anchor">Anchor</a>
        </body>
    </html>
    """

    links = extract_links(html)
    assert "https://example.com/article" in links
    assert "http://test.com" in links
    assert len(links) == 2  # Only http/https links


def test_extract_links_with_duplicates():
    """Test that duplicate links are removed."""
    html = """
    <a href="https://example.com">Link 1</a>
    <a href="https://example.com">Link 2</a>
    <a href="https://test.com">Link 3</a>
    """

    links = extract_links(html)
    assert len(links) == 2
    assert "https://example.com" in links
    assert "https://test.com" in links


def test_clean_html():
    """Test HTML cleaning."""
    html = """
    <html>
        <body>
            <p>Content</p>
            <script>alert('bad');</script>
            <style>.test { color: red; }</style>
            <img src="pixel.gif" width="1" height="1">
        </body>
    </html>
    """

    cleaned = clean_html(html)
    assert "<p>Content</p>" in cleaned
    assert "<script>" not in cleaned
    assert "<style>" not in cleaned
    # Tracking pixel should be removed
    assert 'width="1"' not in cleaned


def test_remove_tracking_params():
    """Test removal of tracking parameters."""
    url = "https://example.com/article?utm_source=newsletter&utm_campaign=test&foo=bar"
    cleaned = remove_tracking_params(url)

    assert "utm_source" not in cleaned
    assert "utm_campaign" not in cleaned
    assert "foo=bar" in cleaned  # Non-tracking param preserved


def test_remove_tracking_params_no_params():
    """Test URL without parameters."""
    url = "https://example.com/article"
    cleaned = remove_tracking_params(url)
    assert cleaned == url


def test_html_to_text_empty():
    """Test HTML to text with empty input."""
    assert html_to_text("") == ""
    assert html_to_text(None) == ""


def test_extract_links_empty():
    """Test link extraction with empty input."""
    assert extract_links("") == []
    assert extract_links(None) == []
