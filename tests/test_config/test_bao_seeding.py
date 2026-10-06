"""Tests for OpenBao seeding script (scripts/bao_seed_newsletter.py).

Covers spec scenarios openbao-secrets.9 through .13 (seeding, shared keys,
AppRole, DB engine, dry run) plus error paths, and the ``--with-session-roles``
workstation/worker policies (change ship-workstation-and-worker-approle-policies).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

# Import functions under test
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import bao_seed_newsletter
from bao_seed_newsletter import (
    APP_ROLE,
    READ_POLICY,
    WORKER_POLICY,
    WORKSTATION_POLICY,
    WORKSTATION_ROLE,
    read_policy_hcl,
    seed_approle,
    seed_db_engine,
    seed_secrets,
    seed_session_roles,
    seed_shared_keys,
    worker_policy_hcl,
    workstation_policy_hcl,
)


@pytest.fixture
def secrets_file(tmp_path: Path) -> Path:
    """Create a temporary .secrets.yaml."""
    secrets = {
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "OPENAI_API_KEY": "sk-test",
        "NEO4J_PASSWORD": "neo4j-pass",
    }
    path = tmp_path / ".secrets.yaml"
    path.write_text(yaml.dump(secrets))
    return path


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock hvac client."""
    client = MagicMock()
    client.is_authenticated.return_value = True
    return client


# =========================================================================
# Seeding (spec .9)
# =========================================================================


class TestSeedSecrets:
    """Verify secret seeding from .secrets.yaml."""

    def test_seeds_all_string_values(self, mock_client: MagicMock, secrets_file: Path) -> None:
        """spec .9: Write all secrets to secret/newsletter/."""
        result = seed_secrets(mock_client, secrets_file, "secret", "newsletter")

        mock_client.secrets.kv.v2.create_or_update_secret.assert_called_once()
        call_kwargs = mock_client.secrets.kv.v2.create_or_update_secret.call_args
        assert call_kwargs.kwargs["path"] == "newsletter"
        assert len(result) == 3

    def test_dry_run_no_write(self, mock_client: MagicMock, secrets_file: Path) -> None:
        """spec .13: Dry run doesn't write to OpenBao."""
        result = seed_secrets(None, secrets_file, "secret", "newsletter", dry_run=True)

        assert len(result) == 3
        # mock_client shouldn't be called at all (client is None in dry run)

    def test_missing_file_exits(self, mock_client: MagicMock, tmp_path: Path) -> None:
        """spec .9 error: Missing .secrets.yaml exits with error."""
        missing = tmp_path / "nonexistent.yaml"
        with pytest.raises(SystemExit):
            seed_secrets(mock_client, missing, "secret", "newsletter")


# =========================================================================
# Shared Keys (spec .10)
# =========================================================================


class TestSeedSharedKeys:
    """Verify shared key seeding with merge semantics."""

    def test_merge_preserves_other_projects(self, mock_client: MagicMock) -> None:
        """spec .10: Newsletter wins on conflict, other keys preserved."""
        # Existing shared secrets from coordinator
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {
                "data": {
                    "ANTHROPIC_API_KEY": "old-coordinator-key",
                    "COORDINATOR_ONLY_KEY": "coord-value",
                }
            }
        }

        secrets = {
            "ANTHROPIC_API_KEY": "new-newsletter-key",
            "OPENAI_API_KEY": "openai-key",
        }

        seed_shared_keys(
            mock_client,
            secrets,
            ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"],
            "secret",
        )

        written = mock_client.secrets.kv.v2.create_or_update_secret.call_args
        merged_data = written.kwargs["secret"]

        # Newsletter value wins
        assert merged_data["ANTHROPIC_API_KEY"] == "new-newsletter-key"
        # Coordinator key preserved
        assert merged_data["COORDINATOR_ONLY_KEY"] == "coord-value"
        # New newsletter key added
        assert merged_data["OPENAI_API_KEY"] == "openai-key"

    def test_dry_run_no_write(self, mock_client: MagicMock) -> None:
        """spec .13: Shared key dry run doesn't write."""
        secrets = {"KEY": "value"}
        seed_shared_keys(mock_client, secrets, ["KEY"], "secret", dry_run=True)
        mock_client.secrets.kv.v2.create_or_update_secret.assert_not_called()

    def test_missing_keys_warns(
        self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """spec .10: Missing keys produce a warning."""
        secrets = {"KEY_A": "value"}
        seed_shared_keys(mock_client, secrets, ["KEY_A", "MISSING_KEY"], "secret", dry_run=True)
        captured = capsys.readouterr()
        assert "MISSING_KEY" in captured.err


# =========================================================================
# AppRole Creation (spec .11)
# =========================================================================


class TestSeedAppRole:
    """Verify AppRole and policy creation."""

    def test_creates_policy_and_role(self, mock_client: MagicMock) -> None:
        """spec .11: Creates newsletter-read policy and newsletter-app role."""
        mock_client.sys.list_auth_methods.return_value = {"approle/": {}}
        mock_client.auth.approle.read_role_id.return_value = {"data": {"role_id": "test-role-id"}}

        seed_approle(mock_client, "secret", "newsletter", 3600)

        mock_client.sys.create_or_update_policy.assert_called_once()
        policy_call = mock_client.sys.create_or_update_policy.call_args
        assert policy_call.kwargs["name"] == "newsletter-read"
        assert "newsletter" in policy_call.kwargs["policy"]
        assert "shared" in policy_call.kwargs["policy"]

        mock_client.auth.approle.create_or_update_approle.assert_called_once()

    def test_dry_run_no_write(self, mock_client: MagicMock) -> None:
        """spec .13: AppRole dry run doesn't create anything."""
        seed_approle(None, "secret", "newsletter", 3600, dry_run=True)


# =========================================================================
# Database Engine (spec .12)
# =========================================================================


class TestSeedDbEngine:
    """Verify database secrets engine configuration."""

    def test_configures_postgres(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """spec .12: Configures newsletter-postgres with 1h TTL."""
        monkeypatch.setenv(
            "POSTGRES_DSN",
            "postgresql://user:pass@localhost:5432/newsletters",
        )
        mock_client.sys.list_mounted_secrets_engines.return_value = {"database/": {}}

        seed_db_engine(mock_client)

        mock_client.secrets.database.create_role.assert_called_once()
        role_call = mock_client.secrets.database.create_role.call_args
        assert role_call.kwargs["name"] == "newsletter-app"
        assert role_call.kwargs["default_ttl"] == "1h"
        assert role_call.kwargs["max_ttl"] == "24h"

    def test_missing_dsn_exits(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """spec .12 error: No POSTGRES_DSN exits."""
        monkeypatch.delenv("POSTGRES_DSN", raising=False)
        with pytest.raises(SystemExit):
            seed_db_engine(mock_client)


# =========================================================================
# Failure Cases (spec .9 error paths)
# =========================================================================


class TestSeedingFailures:
    """Verify error handling in seeding operations."""

    def test_vault_write_failure(self, mock_client: MagicMock, secrets_file: Path) -> None:
        """Vault write permission denied raises."""
        mock_client.secrets.kv.v2.create_or_update_secret.side_effect = Exception(
            "permission denied"
        )
        with pytest.raises(Exception, match="permission denied"):
            seed_secrets(mock_client, secrets_file, "secret", "newsletter")

    def test_shared_read_failure_creates_new(self, mock_client: MagicMock) -> None:
        """If shared path doesn't exist yet, create from scratch."""
        mock_client.secrets.kv.v2.read_secret_version.side_effect = Exception("not found")
        secrets = {"KEY": "value"}
        seed_shared_keys(mock_client, secrets, ["KEY"], "secret")

        # Should still write despite read failure
        mock_client.secrets.kv.v2.create_or_update_secret.assert_called_once()
        written = mock_client.secrets.kv.v2.create_or_update_secret.call_args
        assert written.kwargs["secret"] == {"KEY": "value"}


# =========================================================================
# Session-credential policies and AppRoles (--with-session-roles)
# =========================================================================

_BLOCK = re.compile(r'path\s+"([^"]+)"\s*\{\s*capabilities\s*=\s*\[([^\]]*)\]\s*\}')
DATA_PATH = "secret/data/newsletter"


def _capabilities(hcl: str) -> dict[str, set[str]]:
    """Parse the flat ``path { capabilities = [...] }`` HCL this script emits."""
    parsed: dict[str, set[str]] = {}
    for path, caps in _BLOCK.findall(hcl):
        parsed.setdefault(path, set()).update(c.strip().strip('"') for c in caps.split(",") if c)
    # Every block must have been understood: no stray, unparsed rules.
    assert len(_BLOCK.findall(hcl)) == hcl.count("path "), hcl
    return parsed


def _allowed(policies: list[str], path: str, capability: str) -> bool:
    """OpenBao ACL check for exact (non-glob) paths: union of the policies' grants."""
    return any(capability in _capabilities(hcl).get(path, set()) for hcl in policies)


# KV v2 operations -> (API path, required capability).
_KV_OPS = {
    "read": (DATA_PATH, "read"),
    "patch": (DATA_PATH, "patch"),
    "overwrite": (DATA_PATH, "update"),
    "create": (DATA_PATH, "create"),
    "delete_latest": (DATA_PATH, "delete"),
    "delete_versions": ("secret/delete/newsletter", "update"),
    "destroy": ("secret/destroy/newsletter", "update"),
    "delete_metadata": ("secret/metadata/newsletter", "delete"),
    "list": ("secret/metadata/newsletter", "list"),
    "read_metadata": ("secret/metadata/newsletter", "read"),
    "read_shared": ("secret/data/shared", "read"),
}


class FakeBao:
    """In-memory stand-in for the hvac client surface the seed script uses."""

    class _Sys:
        def __init__(self) -> None:
            self.policies: dict[str, str] = {}
            self.auth_methods: dict[str, dict] = {}
            self.writes: list[str] = []

        def read_policy(self, name: str) -> dict:
            if name not in self.policies:
                raise RuntimeError("InvalidPath")
            return {"name": name, "rules": self.policies[name]}

        def create_or_update_policy(self, name: str, policy: str) -> None:
            self.writes.append(name)
            self.policies[name] = policy

        def list_auth_methods(self) -> dict:
            return self.auth_methods

        def enable_auth_method(self, method_type: str) -> None:
            self.auth_methods[f"{method_type}/"] = {}

    class _AppRole:
        def __init__(self) -> None:
            self.roles: dict[str, dict] = {}

        def create_or_update_approle(self, role_name: str, **kwargs: object) -> None:
            self.roles[role_name] = dict(kwargs)

        def read_role(self, role_name: str) -> dict:
            if role_name not in self.roles:
                raise RuntimeError("InvalidPath")
            return {"data": dict(self.roles[role_name])}

        def read_role_id(self, role_name: str) -> dict:
            return {"data": {"role_id": f"role-id-{role_name}"}}

    def __init__(self) -> None:
        self.sys = self._Sys()
        self.auth = MagicMock()
        self.auth.approle = self._AppRole()
        self.secrets = MagicMock()

    def role_policies(self, role: str) -> list[str]:
        return [self.sys.policies[p] for p in self.auth.approle.roles[role]["token_policies"]]


class TestPolicyHcl:
    """The pure HCL builders grant exactly the documented capabilities."""

    def test_workstation_is_patch_only(self) -> None:
        caps = _capabilities(workstation_policy_hcl("secret", "newsletter"))
        assert caps == {DATA_PATH: {"patch"}}

    def test_worker_is_read_and_patch(self) -> None:
        caps = _capabilities(worker_policy_hcl("secret", "newsletter"))
        assert caps == {DATA_PATH: {"read", "patch"}}

    def test_read_policy_unchanged(self) -> None:
        assert read_policy_hcl("secret", "newsletter") == (
            'path "secret/data/newsletter" {\n  capabilities = ["read"]\n}\n'
            'path "secret/data/shared" {\n  capabilities = ["read"]\n}\n'
        )

    @pytest.mark.parametrize("builder", [workstation_policy_hcl, worker_policy_hcl])
    def test_no_destructive_or_enumerating_capability(self, builder) -> None:  # type: ignore[no-untyped-def]
        hcl = builder("secret", "newsletter")
        for forbidden in ("delete", "destroy", "list", "create", "update", "sudo", "deny"):
            assert f'"{forbidden}"' not in hcl
        assert "*" not in hcl  # no globs: one exact path
        assert "metadata" not in hcl

    def test_honours_custom_mount_and_path(self) -> None:
        caps = _capabilities(workstation_policy_hcl("/kv/", "/apps/news/"))
        assert caps == {"kv/data/apps/news": {"patch"}}

    def test_builders_are_deterministic(self) -> None:
        assert workstation_policy_hcl("secret", "newsletter") == workstation_policy_hcl(
            "secret", "newsletter"
        )
        assert worker_policy_hcl("secret", "newsletter") == worker_policy_hcl(
            "secret", "newsletter"
        )


class TestSeedSessionRoles:
    """``--with-session-roles`` seeds the workstation and worker roles."""

    def test_workstation_role_patch_allowed_read_delete_denied(self) -> None:
        bao = FakeBao()
        seed_session_roles(bao, "secret", "newsletter", 3600)

        policies = bao.role_policies(WORKSTATION_ROLE)
        assert _allowed(policies, *_KV_OPS["patch"])
        for op in _KV_OPS.keys() - {"patch"}:
            assert not _allowed(policies, *_KV_OPS[op]), op

    def test_worker_role_read_and_patch_allowed_delete_denied(self) -> None:
        bao = FakeBao()
        seed_session_roles(bao, "secret", "newsletter", 3600)

        assert bao.auth.approle.roles[APP_ROLE]["token_policies"] == [
            READ_POLICY,
            WORKER_POLICY,
        ]
        policies = bao.role_policies(APP_ROLE)
        for op in ("read", "patch", "read_shared"):
            assert _allowed(policies, *_KV_OPS[op]), op
        for op in _KV_OPS.keys() - {"read", "patch", "read_shared"}:
            assert not _allowed(policies, *_KV_OPS[op]), op

    def test_workstation_role_has_short_token_ttls(self) -> None:
        bao = FakeBao()
        seed_session_roles(bao, "secret", "newsletter", 3600)

        role = bao.auth.approle.roles[WORKSTATION_ROLE]
        assert role["token_policies"] == [WORKSTATION_POLICY]
        assert role["token_ttl"] == "900s"
        assert role["token_max_ttl"] == "3600s"
        assert role["secret_id_ttl"] == "2160h"

    def test_enables_approle_auth_when_missing(self) -> None:
        bao = FakeBao()
        seed_session_roles(bao, "secret", "newsletter", 3600)
        assert "approle/" in bao.sys.auth_methods

    def test_rerun_leaves_policies_unchanged(self, capsys: pytest.CaptureFixture[str]) -> None:
        bao = FakeBao()
        seed_session_roles(bao, "secret", "newsletter", 3600)
        first_policies = dict(bao.sys.policies)
        first_roles = {k: dict(v) for k, v in bao.auth.approle.roles.items()}
        writes_after_first = len(bao.sys.writes)
        capsys.readouterr()

        seed_session_roles(bao, "secret", "newsletter", 3600)

        assert bao.sys.policies == first_policies
        assert bao.auth.approle.roles == first_roles
        assert len(bao.sys.writes) == writes_after_first  # no policy rewritten
        out = capsys.readouterr().out
        for name in (WORKSTATION_POLICY, WORKER_POLICY, READ_POLICY):
            assert f"Policy {name}: unchanged" in out

    def test_plain_approle_rerun_keeps_worker_policy(self) -> None:
        bao = FakeBao()
        seed_session_roles(bao, "secret", "newsletter", 3600)

        seed_approle(bao, "secret", "newsletter", 3600)

        assert WORKER_POLICY in bao.auth.approle.roles[APP_ROLE]["token_policies"]

    def test_plain_approle_does_not_add_worker_policy(self) -> None:
        bao = FakeBao()
        seed_approle(bao, "secret", "newsletter", 3600)
        assert bao.auth.approle.roles[APP_ROLE]["token_policies"] == [READ_POLICY]
        assert WORKER_POLICY not in bao.sys.policies

    def test_prints_role_ids_and_commands_never_secret_ids(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bao = FakeBao()
        seed_session_roles(bao, "secret", "newsletter", 3600)
        out = capsys.readouterr().out

        assert f"Role ID: role-id-{WORKSTATION_ROLE}" in out
        assert f"Role ID: role-id-{APP_ROLE}" in out
        assert f"auth/approle/role/{WORKSTATION_ROLE}/secret-id" in out
        assert "-wrap-ttl=" in out
        # The script only prints commands; it never mints or reads a secret_id.
        assert not bao.secrets.mock_calls

    def test_dry_run_performs_no_client_calls(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = MagicMock()
        seed_session_roles(client, "secret", "newsletter", 3600, dry_run=True)

        assert client.mock_calls == []
        out = capsys.readouterr().out
        assert WORKSTATION_POLICY in out and WORKER_POLICY in out and WORKSTATION_ROLE in out
        assert '"patch"' in out


class TestMainSessionRolesFlag:
    """CLI wiring for ``--with-session-roles``."""

    def test_dry_run_never_builds_a_client(
        self,
        secrets_file: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def _no_client() -> None:
            raise AssertionError("dry run must not contact OpenBao")

        monkeypatch.setattr(bao_seed_newsletter, "_get_client", _no_client)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "bao_seed_newsletter.py",
                "--dry-run",
                "--with-session-roles",
                "--secrets-path",
                str(secrets_file),
            ],
        )

        bao_seed_newsletter.main()

        out = capsys.readouterr().out
        assert f"Would create AppRole '{WORKSTATION_ROLE}'" in out
        assert f"Would create AppRole '{APP_ROLE}'" in out
        # Secret values from .secrets.yaml never reach stdout.
        assert "sk-ant-test" not in out and "neo4j-pass" not in out

    def test_session_roles_replace_plain_approle_step(
        self,
        secrets_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        bao = FakeBao()
        monkeypatch.setattr(bao_seed_newsletter, "_get_client", lambda: bao)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "bao_seed_newsletter.py",
                "--with-approle",
                "--with-session-roles",
                "--secrets-path",
                str(secrets_file),
            ],
        )

        bao_seed_newsletter.main()

        assert set(bao.auth.approle.roles) == {APP_ROLE, WORKSTATION_ROLE}
        assert bao.auth.approle.roles[APP_ROLE]["token_policies"] == [READ_POLICY, WORKER_POLICY]
