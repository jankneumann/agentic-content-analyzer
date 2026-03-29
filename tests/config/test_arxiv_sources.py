"""Tests for ArxivSource configuration model."""

from __future__ import annotations

from src.config.sources import ArxivSource, SourcesConfig


class TestArxivSource:
    def test_default_values(self):
        source = ArxivSource(type="arxiv")
        assert source.categories == []
        assert source.search_query is None
        assert source.sort_by == "submittedDate"
        assert source.pdf_extraction is True
        assert source.max_pdf_pages == 80
        assert source.enabled is True

    def test_custom_values(self):
        source = ArxivSource(
            type="arxiv",
            name="AI Research",
            categories=["cs.AI", "cs.LG"],
            search_query="transformer attention",
            sort_by="relevance",
            pdf_extraction=False,
            max_pdf_pages=50,
            tags=["ai"],
        )
        assert source.name == "AI Research"
        assert source.categories == ["cs.AI", "cs.LG"]
        assert source.search_query == "transformer attention"
        assert source.sort_by == "relevance"
        assert source.pdf_extraction is False
        assert source.max_pdf_pages == 50
        assert source.tags == ["ai"]

    def test_sources_config_get_arxiv_sources(self):
        config = SourcesConfig(
            sources=[
                {"type": "arxiv", "name": "A", "categories": ["cs.AI"]},
                {"type": "arxiv", "name": "B", "enabled": False},
                {"type": "rss", "url": "https://example.com/feed"},
            ]
        )
        arxiv_sources = config.get_arxiv_sources()
        assert len(arxiv_sources) == 1
        assert arxiv_sources[0].name == "A"

    def test_discriminated_union_includes_arxiv(self):
        """ArxivSource is included in the Source discriminated union."""
        config = SourcesConfig(sources=[{"type": "arxiv", "categories": ["cs.AI"]}])
        assert len(config.sources) == 1
        assert isinstance(config.sources[0], ArxivSource)
