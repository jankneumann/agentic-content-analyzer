"""Tests for BlogSource configuration, including optional RSS fallback."""

from __future__ import annotations

from src.config.sources import BlogSource, SourcesConfig


class TestBlogSource:
    def test_defaults_leave_rss_url_unset(self) -> None:
        source = BlogSource(url="https://example.com/blog")
        assert source.type == "blog"
        assert source.url == "https://example.com/blog"
        assert source.rss_url is None
        assert source.link_selector is None
        assert source.request_delay == 1.0

    def test_optional_rss_url_is_accepted(self) -> None:
        source = BlogSource(
            url="https://news.example.com/ai/",
            name="Example AI",
            rss_url="https://news.example.com/feed/",
            tags=["ai"],
        )
        assert source.rss_url == "https://news.example.com/feed/"
        assert source.name == "Example AI"

    def test_sources_config_loads_rss_url_from_mapping(self) -> None:
        config = SourcesConfig(
            sources=[
                {
                    "type": "blog",
                    "name": "SPA Blog",
                    "url": "https://spa.example/news",
                    "rss_url": "https://spa.example/rss.xml",
                },
                {
                    "type": "blog",
                    "name": "Disabled",
                    "url": "https://spa.example/old",
                    "enabled": False,
                },
            ]
        )
        blogs = config.get_blog_sources()
        assert len(blogs) == 1
        assert blogs[0].name == "SPA Blog"
        assert blogs[0].rss_url == "https://spa.example/rss.xml"
