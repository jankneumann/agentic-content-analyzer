"""Unit tests for URL auto-routing classification.

``classify_url`` is a pure, network-free function, so these tests are plain
table-driven assertions — no fixtures, no I/O.
"""

import pytest

from src.ingestion.url_router import (
    RouteKind,
    classify_url,
    looks_like_feed_url,
    route_to_source,
)
from src.models.content import ContentSource


class TestClassifyUrl:
    """Behaviour of :func:`classify_url`."""

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            # --- YouTube videos (win over playlist context) ---
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", RouteKind.YOUTUBE_VIDEO),
            ("https://youtu.be/dQw4w9WgXcQ", RouteKind.YOUTUBE_VIDEO),
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", RouteKind.YOUTUBE_VIDEO),
            ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", RouteKind.YOUTUBE_VIDEO),
            (
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc123",
                RouteKind.YOUTUBE_VIDEO,
            ),
            ("https://youtu.be/dQw4w9WgXcQ?t=42", RouteKind.YOUTUBE_VIDEO),
            # --- YouTube playlists (list, no video id) ---
            ("https://www.youtube.com/playlist?list=PLabc123def456", RouteKind.YOUTUBE_PLAYLIST),
            ("https://youtube.com/playlist?list=PLxyz", RouteKind.YOUTUBE_PLAYLIST),
            # --- Feeds ---
            ("https://example.com/feed", RouteKind.RSS_FEED),
            ("https://example.com/feed/", RouteKind.RSS_FEED),
            ("https://example.com/rss", RouteKind.RSS_FEED),
            ("https://example.com/atom", RouteKind.RSS_FEED),
            ("https://example.com/blog/rss.xml", RouteKind.RSS_FEED),
            ("https://example.com/feed.xml", RouteKind.RSS_FEED),
            ("https://example.com/atom.xml", RouteKind.RSS_FEED),
            ("https://example.com/index.xml", RouteKind.RSS_FEED),
            ("https://example.com/posts.atom", RouteKind.RSS_FEED),
            ("https://example.com/blog.rss", RouteKind.RSS_FEED),
            ("https://blog.example.com/?feed=rss2", RouteKind.RSS_FEED),
            ("https://www.blogger.com/feeds/123/posts/default", RouteKind.RSS_FEED),
            ("https://newsletter.substack.com/feed", RouteKind.RSS_FEED),
            # --- Generic web pages ---
            ("https://example.com/2026/06/some-article", RouteKind.WEBPAGE),
            ("https://example.com/", RouteKind.WEBPAGE),
            ("https://example.com", RouteKind.WEBPAGE),
            ("https://newsletter.substack.com/p/some-post", RouteKind.WEBPAGE),
            # A sitemap is XML but not a feed — must NOT be misrouted.
            ("https://example.com/sitemap.xml", RouteKind.WEBPAGE),
            # "feed" as a substring of a real article slug must not trigger.
            ("https://example.com/how-to-feed-your-cat", RouteKind.WEBPAGE),
        ],
    )
    def test_classify_url(self, url: str, expected: RouteKind) -> None:
        assert classify_url(url) == expected

    def test_substack_root_is_webpage_not_feed(self) -> None:
        # The Substack domain itself is a site, only /feed is the feed.
        assert classify_url("https://newsletter.substack.com") == RouteKind.WEBPAGE

    def test_non_youtube_host_with_list_param_is_not_playlist(self) -> None:
        # A ?list= param on a non-YouTube host must not be treated as a playlist.
        assert classify_url("https://example.com/items?list=PLabc") == RouteKind.WEBPAGE


class TestLooksLikeFeedUrl:
    """Direct checks of the feed heuristic."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/feed",
            "https://example.com/feeds/posts/default",
            "https://example.com/blog/atom.xml",
            "https://example.com/?feed=atom",
        ],
    )
    def test_positive(self, url: str) -> None:
        assert looks_like_feed_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/sitemap.xml",
            "https://example.com/article",
            "https://example.com/",
            "https://example.com/feedback",  # not a feed segment
        ],
    )
    def test_negative(self, url: str) -> None:
        assert looks_like_feed_url(url) is False


class TestRouteToSource:
    """Mapping from RouteKind to the storage-level ContentSource."""

    def test_mapping(self) -> None:
        assert route_to_source(RouteKind.YOUTUBE_VIDEO) == ContentSource.YOUTUBE
        assert route_to_source(RouteKind.YOUTUBE_PLAYLIST) == ContentSource.YOUTUBE
        assert route_to_source(RouteKind.RSS_FEED) == ContentSource.RSS
        assert route_to_source(RouteKind.WEBPAGE) == ContentSource.WEBPAGE

    def test_all_kinds_mapped(self) -> None:
        # Guard against a new RouteKind being added without a mapping.
        for kind in RouteKind:
            assert isinstance(route_to_source(kind), ContentSource)
