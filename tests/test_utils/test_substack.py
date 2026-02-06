from src.utils.substack import extract_substack_canonical_url, normalize_substack_url


def test_normalize_substack_url_strips_tracking() -> None:
    url = "https://example.substack.com/p/test-post?utm_source=newsletter&utm_campaign=foo"
    assert normalize_substack_url(url) == "https://example.substack.com/p/test-post"


def test_normalize_substack_url_rejects_non_substack() -> None:
    assert normalize_substack_url("https://example.com/p/test-post") is None


def test_extract_substack_canonical_url_prefers_source_url() -> None:
    url = "https://news.substack.com/p/hello-world"
    link = "https://other.substack.com/p/ignored"
    assert extract_substack_canonical_url(links=[link], source_url=url) == url
