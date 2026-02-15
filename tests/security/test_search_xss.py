from src.services.search import _generate_highlight, SearchType

def test_generate_highlight_xss_protection():
    """
    Test that _generate_highlight returns ESCAPED HTML when query terms are empty.
    This ensures Stored XSS protection.
    """
    # Malicious content with XSS payload
    xss_payload = "<script>alert('XSS')</script>"
    text = f"Some normal text {xss_payload} more text"

    # Empty query terms (e.g. searching for stopwords or single chars that get filtered)
    query_terms = []

    # The implementation should return the snippet ESCAPED
    result = _generate_highlight(text, query_terms, SearchType.HYBRID)

    # The payload must be escaped
    assert xss_payload not in result
    assert "&lt;script&gt;" in result
