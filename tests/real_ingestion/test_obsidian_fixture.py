"""Offline Obsidian fixture invariants independent of the PostgreSQL drive."""

from __future__ import annotations

from src.config.sources import ObsidianVaultSource
from src.ingestion.obsidian_parser import ObsidianClipError, parse_obsidian_clip
from tests.fixtures.sources.library import SOURCE_FIXTURES
from tests.fixtures.sources.obsidian import create_temporary_obsidian_vault
from tests.real_ingestion.harness import PR_TIER_KEYS, reject_external_fixture_network


def test_obsidian_fixture_is_exact_public_command_and_pr_tier_member() -> None:
    fixture = SOURCE_FIXTURES["obsidian_vault"]

    assert fixture.command == {
        "kind": "obsidian_vault",
        "source_key": "src_0123456789abcdef0123",
        "force_reprocess": False,
    }
    assert "configured_sources" not in fixture.command
    assert "configured_source_version" not in fixture.command
    assert "vault_path" not in fixture.command
    assert "ingest_folder" not in fixture.command
    assert "obsidian_vault" in PR_TIER_KEYS


def test_temporary_vault_has_bounded_valid_invalid_changed_and_duplicate_clips(
    tmp_path,
) -> None:
    vault = create_temporary_obsidian_vault(tmp_path)
    source = ObsidianVaultSource.model_validate(vault.source_config())

    valid = parse_obsidian_clip(vault.valid_clip.read_bytes())
    changed_before = parse_obsidian_clip(vault.changed_clip.read_bytes())
    duplicate = parse_obsidian_clip(vault.duplicate_clip.read_bytes())
    try:
        parse_obsidian_clip(vault.invalid_clip.read_bytes())
    except ObsidianClipError as exc:
        assert exc.code == "missing_required_metadata"
    else:  # pragma: no cover - exact failure is the fixture contract
        raise AssertionError("invalid fixture unexpectedly parsed")

    vault.write_changed_version()
    changed_after = parse_obsidian_clip(vault.changed_clip.read_bytes())

    assert source.max_files == 8
    assert source.max_entries == 16
    assert changed_before.markdown != changed_after.markdown
    assert valid.canonical_url == duplicate.canonical_url
    assert valid.markdown != duplicate.markdown


def test_obsidian_fixture_network_policy_allows_loopback_and_rejects_external() -> None:
    calls = []

    def connect(_socket, address):
        calls.append(address)
        return "connected"

    assert reject_external_fixture_network(connect, object(), ("127.0.0.1", 5432)) == "connected"
    assert calls == [("127.0.0.1", 5432)]

    try:
        reject_external_fixture_network(connect, object(), ("fixture.invalid", 443))
    except AssertionError as exc:
        assert str(exc) == "Obsidian fixture attempted external network access"
    else:  # pragma: no cover - explicit policy contract
        raise AssertionError("external fixture network was unexpectedly allowed")
