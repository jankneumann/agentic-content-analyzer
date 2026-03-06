from src.api.shared_routes import _md_to_html


def test_markdown_xss_raw_html():
    """Test that raw HTML tags are escaped."""
    raw_html = "<script>alert('xss')</script>"
    rendered = _md_to_html(raw_html)

    # Before fix, this would fail (it returns raw script tags)
    # After fix, this should pass (it returns escaped script tags)
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_markdown_xss_javascript_link():
    """Test that javascript: links are not rendered as clickable links."""
    js_link = "[click me](javascript:alert('xss'))"
    rendered = _md_to_html(js_link)

    # We expect it to NOT be a link, or at least not execute JS
    # MarkdownIt default behavior for javascript: links seems to be ignoring them as links?
    # But let's ensure no <a href="javascript:..."> is generated.
    assert 'href="javascript:' not in rendered


def test_markdown_xss_data_uri():
    """Test that data: URIs are not rendered as clickable links if dangerous."""
    data_link = "[click me](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)"
    rendered = _md_to_html(data_link)

    assert 'href="data:' not in rendered
