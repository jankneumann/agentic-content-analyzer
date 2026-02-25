"""Tests for WebSearchSource configuration model and sources.d/websearch.yaml loading.

Covers:
- WebSearchSource model validation (provider, prompt, provider-specific options)
- SourcesConfig.get_websearch_sources() filtering
- Loading websearch.yaml through the standard loader
- Discriminated union integration
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from pydantic import ValidationError

from src.config.sources import (
    SourcesConfig,
    WebSearchSource,
    load_sources_directory,
    load_sources_from_file,
)

# ---------------------------------------------------------------------------
# WebSearchSource model
# ---------------------------------------------------------------------------


class TestWebSearchSourceModel:
    def test_perplexity_source(self):
        src = WebSearchSource(
            provider="perplexity",
            prompt="Latest AI model releases",
            name="AI Weekly",
            tags=["ai"],
        )
        assert src.type == "websearch"
        assert src.provider == "perplexity"
        assert src.prompt == "Latest AI model releases"
        assert src.enabled is True

    def test_grok_source(self):
        src = WebSearchSource(
            provider="grok",
            prompt="AI discussions on X",
            max_threads=30,
        )
        assert src.provider == "grok"
        assert src.max_threads == 30

    def test_perplexity_specific_options(self):
        src = WebSearchSource(
            provider="perplexity",
            prompt="AI news",
            max_results=20,
            recency_filter="day",
            context_size="high",
            domain_filter=["arxiv.org"],
        )
        assert src.max_results == 20
        assert src.recency_filter == "day"
        assert src.context_size == "high"
        assert src.domain_filter == ["arxiv.org"]

    def test_defaults_are_none(self):
        src = WebSearchSource(provider="perplexity", prompt="test")
        assert src.max_results is None
        assert src.max_threads is None
        assert src.recency_filter is None
        assert src.context_size is None
        assert src.domain_filter is None

    def test_invalid_provider_rejected(self):
        with pytest.raises(ValidationError):
            WebSearchSource(provider="bing", prompt="test")

    def test_enabled_false(self):
        src = WebSearchSource(
            provider="perplexity",
            prompt="test",
            enabled=False,
        )
        assert src.enabled is False


# ---------------------------------------------------------------------------
# SourcesConfig.get_websearch_sources()
# ---------------------------------------------------------------------------


class TestGetWebSearchSources:
    def test_returns_websearch_only(self):
        config = SourcesConfig(
            sources=[
                {"type": "rss", "url": "https://feed.com/rss"},
                {"type": "websearch", "provider": "perplexity", "prompt": "AI news"},
                {"type": "websearch", "provider": "grok", "prompt": "X pulse"},
            ]
        )
        ws = config.get_websearch_sources()
        assert len(ws) == 2
        assert all(isinstance(s, WebSearchSource) for s in ws)

    def test_excludes_disabled(self):
        config = SourcesConfig(
            sources=[
                {
                    "type": "websearch",
                    "provider": "perplexity",
                    "prompt": "enabled",
                    "enabled": True,
                },
                {"type": "websearch", "provider": "grok", "prompt": "disabled", "enabled": False},
            ]
        )
        ws = config.get_websearch_sources()
        assert len(ws) == 1
        assert ws[0].prompt == "enabled"

    def test_empty_config(self):
        config = SourcesConfig(sources=[])
        assert config.get_websearch_sources() == []

    def test_no_websearch_sources(self):
        config = SourcesConfig(
            sources=[
                {"type": "rss", "url": "https://example.com/feed"},
            ]
        )
        assert config.get_websearch_sources() == []


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


class TestWebSearchYAMLLoading:
    def test_load_websearch_yaml(self, tmp_path: Path):
        """Load websearch.yaml with perplexity and grok entries."""
        yaml_content = dedent("""\
            defaults:
              type: websearch
              enabled: true

            sources:
              - name: "AI Roundup"
                provider: perplexity
                prompt: "Latest AI news"
                tags: [ai]

              - name: "X Pulse"
                provider: grok
                prompt: "AI on X"
                max_threads: 25
        """)
        (tmp_path / "websearch.yaml").write_text(yaml_content)

        file_config = load_sources_from_file(tmp_path / "websearch.yaml")
        assert len(file_config.sources) == 2
        assert file_config.sources[0]["provider"] == "perplexity"
        assert file_config.sources[1]["max_threads"] == 25

    def test_load_sources_directory_with_websearch(self, tmp_path: Path):
        """Integration: load websearch.yaml from sources.d/ directory."""
        yaml_content = dedent("""\
            defaults:
              type: websearch
              enabled: true

            sources:
              - name: "AI Weekly"
                provider: perplexity
                prompt: "AI model releases this week"
                tags: [ai, weekly]

              - name: "AI Twitter"
                provider: grok
                prompt: "AI on Twitter"
                tags: [ai, social]
                max_threads: 30
        """)
        (tmp_path / "websearch.yaml").write_text(yaml_content)

        config = load_sources_directory(tmp_path)
        assert len(config.sources) == 2

        ws = config.get_websearch_sources()
        assert len(ws) == 2

        perp = [s for s in ws if s.provider == "perplexity"]
        grok = [s for s in ws if s.provider == "grok"]
        assert len(perp) == 1
        assert len(grok) == 1
        assert grok[0].max_threads == 30

    def test_mixed_sources_directory(self, tmp_path: Path):
        """websearch.yaml alongside rss.yaml in same sources.d/."""
        rss_yaml = dedent("""\
            defaults:
              type: rss

            sources:
              - name: "Tech Blog"
                url: "https://techblog.com/rss"
        """)
        ws_yaml = dedent("""\
            defaults:
              type: websearch

            sources:
              - name: "AI Roundup"
                provider: perplexity
                prompt: "AI news"
        """)
        (tmp_path / "rss.yaml").write_text(rss_yaml)
        (tmp_path / "websearch.yaml").write_text(ws_yaml)

        config = load_sources_directory(tmp_path)
        assert len(config.sources) == 2

        rss = config.get_rss_sources()
        ws = config.get_websearch_sources()
        assert len(rss) == 1
        assert len(ws) == 1

    def test_websearch_with_all_perplexity_options(self, tmp_path: Path):
        """Perplexity-specific fields are preserved through load."""
        yaml_content = dedent("""\
            defaults:
              type: websearch

            sources:
              - name: "Deep Search"
                provider: perplexity
                prompt: "Detailed AI research"
                max_results: 50
                recency_filter: month
                context_size: high
                domain_filter:
                  - arxiv.org
                  - github.com
        """)
        (tmp_path / "websearch.yaml").write_text(yaml_content)

        config = load_sources_directory(tmp_path)
        ws = config.get_websearch_sources()
        assert len(ws) == 1

        src = ws[0]
        assert src.max_results == 50
        assert src.recency_filter == "month"
        assert src.context_size == "high"
        assert src.domain_filter == ["arxiv.org", "github.com"]
