"""Tests for HuggingFacePapersSource configuration model."""

from __future__ import annotations

from src.config.sources import HuggingFacePapersSource, SourcesConfig


class TestHuggingFacePapersSource:
    def test_default_values(self):
        source = HuggingFacePapersSource(type="huggingface_papers")
        assert source.url == "https://huggingface.co/papers"
        assert source.request_delay == 1.0
        assert source.enabled is True

    def test_custom_values(self):
        source = HuggingFacePapersSource(
            type="huggingface_papers",
            name="HF Daily Papers",
            url="https://huggingface.co/papers",
            request_delay=2.0,
            tags=["ai", "papers"],
            max_entries=50,
        )
        assert source.name == "HF Daily Papers"
        assert source.url == "https://huggingface.co/papers"
        assert source.request_delay == 2.0
        assert source.tags == ["ai", "papers"]
        assert source.max_entries == 50

    def test_sources_config_get_huggingface_papers_sources(self):
        config = SourcesConfig(
            sources=[
                {
                    "type": "huggingface_papers",
                    "name": "A",
                    "url": "https://huggingface.co/papers",
                },
                {
                    "type": "huggingface_papers",
                    "name": "B",
                    "url": "https://huggingface.co/papers",
                    "enabled": False,
                },
                {"type": "rss", "url": "https://example.com/feed"},
            ]
        )
        hf_sources = config.get_huggingface_papers_sources()
        assert len(hf_sources) == 1
        assert hf_sources[0].name == "A"

    def test_discriminated_union_includes_huggingface_papers(self):
        """HuggingFacePapersSource is included in the Source discriminated union."""
        config = SourcesConfig(
            sources=[
                {
                    "type": "huggingface_papers",
                    "url": "https://huggingface.co/papers",
                }
            ]
        )
        assert len(config.sources) == 1
        assert isinstance(config.sources[0], HuggingFacePapersSource)

    def test_disabled_sources_excluded(self):
        """Disabled sources are not returned by getter."""
        config = SourcesConfig(
            sources=[
                {
                    "type": "huggingface_papers",
                    "name": "Disabled",
                    "url": "https://huggingface.co/papers",
                    "enabled": False,
                },
            ]
        )
        assert len(config.get_huggingface_papers_sources()) == 0

    def test_sources_config_loads_yaml(self):
        """Config loads from sources.d/ directory including HF papers source."""
        from pathlib import Path

        from src.config.sources import load_sources_directory

        sources_dir = Path("sources.d")
        if not sources_dir.is_dir():
            pytest.skip("sources.d/ directory not available")

        config = load_sources_directory(sources_dir)
        hf_sources = config.get_huggingface_papers_sources()
        assert len(hf_sources) >= 1
        assert hf_sources[0].type == "huggingface_papers"
