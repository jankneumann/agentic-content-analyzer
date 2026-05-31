"""Tests for the Railway secret-sync allowlist loader (`src/config/deploy_secrets.py`)."""

from __future__ import annotations

import pytest

from src.config.deploy_secrets import (
    DeploySecretsError,
    SecretMapping,
    load_mapping,
)


def _write(tmp_path, text: str):
    p = tmp_path / "railway_secrets.yaml"
    p.write_text(text)
    return p


def test_simple_and_rename_entries(tmp_path):
    path = _write(
        tmp_path,
        """
services:
  api:
    secrets:
      - ANTHROPIC_API_KEY
      - local: NEON_DATABASE_URL
        railway: DATABASE_URL
""",
    )
    mapping = load_mapping(path)
    assert set(mapping) == {"api"}
    secrets = mapping["api"].secrets
    assert SecretMapping("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY") in secrets
    # Rename: local key pushed under a different Railway name.
    assert SecretMapping("NEON_DATABASE_URL", "DATABASE_URL") in secrets


def test_extends_inherits_parent_secrets(tmp_path):
    path = _write(
        tmp_path,
        """
services:
  api:
    secrets:
      - ANTHROPIC_API_KEY
  worker:
    extends: api
    secrets:
      - WORKER_ONLY_KEY
""",
    )
    mapping = load_mapping(path)
    worker_locals = {s.local for s in mapping["worker"].secrets}
    assert worker_locals == {"ANTHROPIC_API_KEY", "WORKER_ONLY_KEY"}


def test_missing_file_raises(tmp_path):
    with pytest.raises(DeploySecretsError, match="not found"):
        load_mapping(tmp_path / "does-not-exist.yaml")


def test_missing_services_key_raises(tmp_path):
    path = _write(tmp_path, "foo: bar\n")
    with pytest.raises(DeploySecretsError, match="top-level 'services'"):
        load_mapping(path)


def test_unknown_extends_parent_raises(tmp_path):
    path = _write(
        tmp_path,
        """
services:
  worker:
    extends: nope
    secrets: []
""",
    )
    with pytest.raises(DeploySecretsError, match="extends unknown service"):
        load_mapping(path)


def test_duplicate_railway_target_raises(tmp_path):
    path = _write(
        tmp_path,
        """
services:
  api:
    secrets:
      - local: A
        railway: DATABASE_URL
      - local: B
        railway: DATABASE_URL
""",
    )
    with pytest.raises(DeploySecretsError, match="duplicate Railway target"):
        load_mapping(path)


def test_non_string_local_raises(tmp_path):
    path = _write(
        tmp_path,
        """
services:
  api:
    secrets:
      - local: 123
""",
    )
    with pytest.raises(DeploySecretsError, match="non-empty string 'local'"):
        load_mapping(path)


def test_secrets_must_be_list(tmp_path):
    path = _write(
        tmp_path,
        """
services:
  api:
    secrets:
      not: a-list
""",
    )
    with pytest.raises(DeploySecretsError, match="'secrets' must be a list"):
        load_mapping(path)
