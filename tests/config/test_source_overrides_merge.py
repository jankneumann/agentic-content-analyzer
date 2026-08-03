"""Tests for source natural-key derivation and the DB-override merge.

Covers spec scenarios under "Natural-Key Source Identity" and "Source
Resolution Precedence and Merge" (design decisions D2, D3).
"""

import pytest

import src.config.sources as source_config
from src.config.sources import (
    BlogSource,
    SourcesConfig,
    merge_source_overrides,
    source_key,
)


class TestSourceKey:
    """Natural-key derivation: <type>:<locator>."""

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            (
                {"type": "blog", "url": "https://www.normaltech.ai/"},
                "blog:https://www.normaltech.ai/",
            ),
            ({"type": "rss", "url": "https://x.com/feed"}, "rss:https://x.com/feed"),
            (
                {"type": "substack", "url": "https://s.substack.com"},
                "substack:https://s.substack.com",
            ),
            ({"type": "podcast", "url": "https://p.com/rss"}, "podcast:https://p.com/rss"),
            ({"type": "youtube_rss", "url": "https://yt/feed"}, "youtube_rss:https://yt/feed"),
            ({"type": "youtube_playlist", "id": "PL123"}, "youtube_playlist:PL123"),
            ({"type": "youtube_channel", "channel_id": "UC9"}, "youtube_channel:UC9"),
            ({"type": "gmail", "query": "label:ai"}, "gmail:label:ai"),
            ({"type": "scholar", "query": "llm agents"}, "scholar:llm agents"),
        ],
    )
    def test_locator_per_type(self, source, expected):
        assert source_key(source) == expected

    def test_accepts_pydantic_model(self):
        assert source_key(BlogSource(url="https://b.com")) == "blog:https://b.com"

    def test_missing_type_raises(self):
        with pytest.raises(ValueError, match="no 'type'"):
            source_key({"url": "https://b.com"})

    def test_unkeyable_source_raises(self):
        with pytest.raises(ValueError, match="no locator"):
            source_key({"type": "blog"})  # no url, no name

    def test_obsidian_vault_key_uses_vault_id_and_not_private_path(self):
        first = source_config.ObsidianVaultSource(
            vault_id="personal",
            vault_path="/srv/mount-a/private-vault",
            ingest_folder="Inbox",
        )
        moved = source_config.ObsidianVaultSource(
            vault_id="personal",
            vault_path="/srv/mount-b/private-vault",
            ingest_folder="Clips",
        )

        assert source_key(first) == "obsidian_vault:personal"
        assert source_key(moved) == "obsidian_vault:personal"
        assert "mount" not in source_key(first)


def _yaml_config(*sources: dict) -> SourcesConfig:
    return SourcesConfig(sources=list(sources))


class TestMergeSourceOverrides:
    """Pure merge semantics (design decision D3)."""

    def test_empty_overrides_returns_config_unchanged(self):
        cfg = _yaml_config({"type": "blog", "url": "https://a.com"})
        merged = merge_source_overrides(cfg, [])
        assert len(merged.sources) == 1
        assert merged.sources[0].origin == "yaml"

    def test_db_override_adds_new_source(self):
        cfg = _yaml_config({"type": "blog", "url": "https://a.com"})
        overrides = [
            {
                "source_key": "blog:https://www.normaltech.ai/",
                "config": {"type": "blog", "url": "https://www.normaltech.ai/"},
                "enabled": True,
            }
        ]
        merged = merge_source_overrides(cfg, overrides)
        urls = {s.url for s in merged.get_blog_sources()}  # type: ignore[attr-defined]
        assert "https://www.normaltech.ai/" in urls
        added = next(
            s for s in merged.sources if getattr(s, "url", None) == "https://www.normaltech.ai/"
        )
        assert added.origin == "db"

    def test_db_override_replaces_yaml_twin(self):
        cfg = _yaml_config({"type": "blog", "url": "https://a.com", "max_entries": 5})
        overrides = [
            {
                "source_key": "blog:https://a.com",
                "config": {"type": "blog", "url": "https://a.com", "max_entries": 99},
                "enabled": True,
            }
        ]
        merged = merge_source_overrides(cfg, overrides)
        assert len(merged.sources) == 1
        assert merged.sources[0].max_entries == 99
        assert merged.sources[0].origin == "db"

    def test_disabled_override_shadows_yaml_source(self):
        cfg = _yaml_config(
            {"type": "blog", "url": "https://a.com"},
            {"type": "blog", "url": "https://keep.com"},
        )
        overrides = [
            {
                "source_key": "blog:https://a.com",
                "config": {"type": "blog", "url": "https://a.com"},
                "enabled": False,
            }
        ]
        merged = merge_source_overrides(cfg, overrides)
        # The disabled source stays visible (so it can be re-enabled)...
        urls = {getattr(s, "url", None) for s in merged.sources}
        assert urls == {"https://a.com", "https://keep.com"}
        disabled = next(s for s in merged.sources if getattr(s, "url", None) == "https://a.com")
        assert disabled.enabled is False
        # ...but is excluded from ingestion (per-type getters filter on enabled).
        active = {s.url for s in merged.get_blog_sources()}  # type: ignore[attr-defined]
        assert active == {"https://keep.com"}

    def test_obsidian_override_replaces_path_server_side_without_changing_identity(self):
        cfg = _yaml_config(
            {
                "type": "obsidian_vault",
                "vault_id": "personal",
                "vault_path": "/srv/yaml/private-vault",
                "ingest_folder": "Inbox",
            }
        )
        overrides = [
            {
                "source_key": "obsidian_vault:personal",
                "config": {
                    "type": "obsidian_vault",
                    "vault_id": "personal",
                    "vault_path": "/srv/db/private-vault",
                    "ingest_folder": "Clips",
                },
                "enabled": True,
            }
        ]

        merged = merge_source_overrides(cfg, overrides)
        resolved = merged.get_obsidian_vault_sources()

        assert len(resolved) == 1
        assert resolved[0].vault_path == "/srv/db/private-vault"
        assert resolved[0].ingest_folder == "Clips"
        assert resolved[0].origin == "db"
        assert source_key(resolved[0]) == "obsidian_vault:personal"
