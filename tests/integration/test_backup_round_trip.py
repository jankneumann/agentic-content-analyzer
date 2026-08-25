"""Round-trip verification: seed → backup → encrypt → upload → download → decrypt
→ restore → compare.

This is the test the previous arrangement could not have had, and its absence is
why that arrangement stayed broken. A test asserting "the backup job is
scheduled" would have passed against a job that produced nothing for its entire
existence. The only claim worth making is that a backup **restores**, and the only
way to make it is to restore one.

Everything runs against local containers — a MinIO instance from the compose
`test` profile and a scratch Postgres database. No production database, bucket or
secret store is contacted, which is Hard Constraint 1 of this change.

Skips cleanly when the prerequisites are absent, so `pytest` stays green on a
machine without Docker. It is not skipped in CI, where the compose stack runs:

    docker compose --profile test up -d postgres minio-test
    pytest tests/integration/test_backup_round_trip.py -v
"""

from __future__ import annotations

# This file drives the real pipeline on purpose, so it invokes host binaries by
# name (they are resolved from the operator's PATH, exactly as in production) and
# builds SQL for throwaway databases whose names it generates itself. Both are the
# point of the test rather than an oversight.
# ruff: noqa: S607, S608 -- integration test drives rclone/age/pg_restore from PATH and builds table-name SQL from test constants
import json
import os
import shutil
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REQUIRED_BINARIES = ("pg_dump", "pg_restore", "psql", "age", "age-keygen", "rclone", "tar")


def _missing_binaries() -> list[str]:
    return [name for name in REQUIRED_BINARIES if shutil.which(name) is None]


def _minio_endpoint() -> str:
    port = os.environ.get("MINIO_TEST_PORT", "9100")
    return os.environ.get("MINIO_TEST_ENDPOINT", f"http://localhost:{port}")


def _source_database_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")


def _reachable(endpoint: str) -> bool:
    import urllib.error
    import urllib.request

    try:
        urllib.request.urlopen(f"{endpoint}/minio/health/live", timeout=3)  # noqa: S310
    except urllib.error.HTTPError:
        return True  # responded, which is all we need to know
    except Exception:
        return False
    return True


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        bool(_missing_binaries()),
        reason=f"round trip needs host binaries: {', '.join(_missing_binaries())}",
    ),
    pytest.mark.skipif(
        not _source_database_url(),
        reason="round trip needs TEST_DATABASE_URL or DATABASE_URL",
    ),
    pytest.mark.skipif(
        not _reachable(_minio_endpoint()),
        reason="round trip needs the compose `test` profile: docker compose --profile test up -d minio-test",
    ),
]


# --------------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def age_keypair(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, Path]:
    """A throwaway keypair. Never reuses the real one — see BACKUP_RESTORE.md."""
    directory = tmp_path_factory.mktemp("age")
    identity = directory / "identity.txt"
    subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
    recipient = subprocess.run(
        ["age-keygen", "-y", str(identity)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return recipient, identity


@pytest.fixture
def bucket(backup_settings_base: dict[str, Any]) -> Iterator[str]:
    """A uniquely named bucket per test, created and removed via rclone.

    Unique because a shared bucket lets one test pass against another's artifact,
    which is the specific way a round-trip test can lie.
    """
    name = f"aca-roundtrip-{uuid.uuid4().hex[:12]}"
    env = _rclone_env(backup_settings_base)
    subprocess.run(["rclone", "mkdir", f"backup:{name}"], check=True, env=env)
    try:
        yield name
    finally:
        subprocess.run(["rclone", "purge", f"backup:{name}"], check=False, env=env)


@pytest.fixture(scope="module")
def backup_settings_base(age_keypair: tuple[str, Path]) -> dict[str, Any]:
    recipient, identity = age_keypair
    return {
        "environment": "test",
        "backup_s3_endpoint": _minio_endpoint(),
        "backup_s3_region": "us-east-1",
        "backup_s3_prefix": "aca",
        "backup_s3_access_key_id": os.environ.get("MINIO_TEST_ROOT_USER", "minio-test-user"),
        "backup_s3_secret_access_key": os.environ.get(
            "MINIO_TEST_ROOT_PASSWORD", "minio-test-password"
        ),
        "backup_age_recipient": recipient,
        "backup_age_identity_path": str(identity),
        "backup_monitoring_enabled": True,
        "backup_staleness_hours": 48,
    }


def _rclone_env(base: dict[str, Any]) -> dict[str, str]:
    from src.services.backup.target import TargetConfig

    config = TargetConfig(
        endpoint=base["backup_s3_endpoint"],
        bucket="placeholder",
        region=base["backup_s3_region"],
        prefix=base["backup_s3_prefix"],
        access_key_id=base["backup_s3_access_key_id"],
        secret_access_key=base["backup_s3_secret_access_key"],
    )
    return {**os.environ, **config.rclone_env()}


@pytest.fixture
def seeded_database() -> Iterator[tuple[str, str, list[tuple[int, str]]]]:
    """A scratch database holding known rows, plus an empty restore target."""
    admin_url = _source_database_url()
    assert admin_url is not None
    suffix = uuid.uuid4().hex[:12]
    source_db = f"aca_rt_src_{suffix}"
    target_db = f"aca_rt_dst_{suffix}"

    rows = [(1, "alpha"), (2, "bravo"), (3, "charlie — ünïcode ✓")]

    _psql(admin_url, f'CREATE DATABASE "{source_db}"')
    _psql(admin_url, f'CREATE DATABASE "{target_db}"')
    source_url = _swap_database(admin_url, source_db)
    target_url = _swap_database(admin_url, target_db)
    try:
        _psql(source_url, "CREATE TABLE round_trip (id integer PRIMARY KEY, label text NOT NULL)")
        for row_id, label in rows:
            _psql(
                source_url,
                f"INSERT INTO round_trip (id, label) VALUES ({row_id}, $lbl${label}$lbl$)",
            )
        yield source_url, target_url, rows
    finally:
        for name in (source_db, target_db):
            _psql(admin_url, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)', check=False)


def _psql(url: str, statement: str, *, check: bool = True) -> str:
    result = subprocess.run(
        ["psql", url, "-v", "ON_ERROR_STOP=1", "-t", "-A", "-c", statement],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(f"psql failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _swap_database(url: str, database: str) -> str:
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", "", ""))


def _settings(base: dict[str, Any], **overrides: Any) -> SimpleNamespace:
    from pydantic import SecretStr

    values = {**base, **overrides}
    values["backup_s3_access_key_id"] = SecretStr(str(values["backup_s3_access_key_id"]))
    values["backup_s3_secret_access_key"] = SecretStr(str(values["backup_s3_secret_access_key"]))
    values.setdefault("graphdb_provider", "neo4j")
    values.setdefault("graphdb_mode", "cloud")  # skipped, keeps the round trip focused
    values.setdefault("bao_addr", None)
    values.setdefault("bao_token", None)
    return SimpleNamespace(**values)


# ------------------------------------------------------------------ round trip


class TestBackupRoundTrip:
    def test_a_backup_is_produced_and_restores_to_matching_data(
        self,
        backup_settings_base: dict[str, Any],
        bucket: str,
        seeded_database: tuple[str, str, list[tuple[int, str]]],
        tmp_path: Path,
    ) -> None:
        """The claim worth making, made end to end against real tools."""
        from src.services.backup.engine import BackupEngine

        source_url, target_url, rows = seeded_database
        settings = _settings(
            backup_settings_base,
            backup_s3_bucket=bucket,
            database_url=source_url,
            image_storage_path=str(tmp_path / "images"),
            podcast_storage_path=str(tmp_path / "podcasts"),
            audio_digest_storage_path=str(tmp_path / "audio"),
        )
        (tmp_path / "images").mkdir()
        (tmp_path / "images" / "orphan.png").write_bytes(b"referenced by no database row")

        result = BackupEngine(settings).run()

        assert result.succeeded, [(str(s.store), str(s.outcome), s.reason) for s in result.stores]
        postgres = next(s for s in result.stores if str(s.store) == "postgres")
        assert postgres.artifact_key is not None
        assert postgres.bytes and postgres.bytes > 0
        assert postgres.checksum_sha256 is not None

        # --- restore into the empty target -------------------------------
        env = _rclone_env(backup_settings_base)
        ciphertext = tmp_path / "postgres.dump.age"
        plaintext = tmp_path / "postgres.dump"
        subprocess.run(
            ["rclone", "copyto", f"backup:{bucket}/{postgres.artifact_key}", str(ciphertext)],
            check=True,
            env=env,
        )
        subprocess.run(
            [
                "age",
                "--decrypt",
                "--identity",
                backup_settings_base["backup_age_identity_path"],
                "--output",
                str(plaintext),
                str(ciphertext),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "pg_restore",
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
                "--format=custom",
                "--dbname",
                target_url,
                str(plaintext),
            ],
            check=True,
            capture_output=True,
        )

        # --- compare ------------------------------------------------------
        restored = _psql(target_url, "SELECT id, label FROM round_trip ORDER BY id")
        assert [
            (int(line.split("|")[0]), line.split("|", 1)[1])
            for line in restored.splitlines()
            if line
        ] == rows

    def test_the_uploaded_artifact_is_ciphertext_not_plaintext(
        self,
        backup_settings_base: dict[str, Any],
        bucket: str,
        seeded_database: tuple[str, str, list[tuple[int, str]]],
        tmp_path: Path,
    ) -> None:
        """A bucket-credential leak must not be a PII leak."""
        from src.services.backup.engine import BackupEngine

        source_url, _, _ = seeded_database
        settings = _settings(
            backup_settings_base,
            backup_s3_bucket=bucket,
            database_url=source_url,
            image_storage_path=str(tmp_path / "images"),
            podcast_storage_path=str(tmp_path / "images"),
            audio_digest_storage_path=str(tmp_path / "images"),
        )
        (tmp_path / "images").mkdir()

        result = BackupEngine(settings).run()
        postgres = next(s for s in result.stores if str(s.store) == "postgres")
        assert postgres.artifact_key is not None

        raw = tmp_path / "raw.bin"
        subprocess.run(
            ["rclone", "copyto", f"backup:{bucket}/{postgres.artifact_key}", str(raw)],
            check=True,
            env=_rclone_env(backup_settings_base),
        )
        head = raw.read_bytes()[:64]
        assert head.startswith(b"age-encryption.org/")
        assert b"PGDMP" not in raw.read_bytes()[:4096]  # the pg_dump custom-format magic

    def test_the_manifest_is_readable_without_the_identity(
        self,
        backup_settings_base: dict[str, Any],
        bucket: str,
        seeded_database: tuple[str, str, list[tuple[int, str]]],
        tmp_path: Path,
    ) -> None:
        """The freshness reader holds no decryption identity, so the manifest must
        be the one object on the target that is not encrypted."""
        from src.services.backup import manifest_reader
        from src.services.backup.engine import BackupEngine
        from src.services.backup.manifest_reader import BackupFreshnessStatus

        source_url, _, _ = seeded_database
        settings = _settings(
            backup_settings_base,
            backup_s3_bucket=bucket,
            database_url=source_url,
            image_storage_path=str(tmp_path / "images"),
            podcast_storage_path=str(tmp_path / "images"),
            audio_digest_storage_path=str(tmp_path / "images"),
        )
        (tmp_path / "images").mkdir()

        BackupEngine(settings).run()

        raw = tmp_path / "latest.json"
        subprocess.run(
            ["rclone", "copyto", f"backup:{bucket}/aca/manifests/test/latest.json", str(raw)],
            check=True,
            env=_rclone_env(backup_settings_base),
        )
        document = json.loads(raw.read_text())
        assert document["environment"] == "test"
        assert document["overall_outcome"] in {"succeeded", "partial"}

        # And the shared reader agrees, through its real S3 path.
        no_identity = _settings(
            backup_settings_base,
            backup_s3_bucket=bucket,
            backup_age_identity_path=None,
        )
        manifest_reader.reset_cache()
        freshness = manifest_reader.read_freshness(no_identity, use_cache=False)
        assert freshness.status in {
            BackupFreshnessStatus.OK,
            BackupFreshnessStatus.PARTIAL,
        }

    def test_verify_confirms_the_canary_decrypts(
        self,
        backup_settings_base: dict[str, Any],
        bucket: str,
        seeded_database: tuple[str, str, list[tuple[int, str]]],
        tmp_path: Path,
    ) -> None:
        from src.services.backup.engine import BackupEngine

        source_url, _, _ = seeded_database
        settings = _settings(
            backup_settings_base,
            backup_s3_bucket=bucket,
            database_url=source_url,
            image_storage_path=str(tmp_path / "images"),
            podcast_storage_path=str(tmp_path / "images"),
            audio_digest_storage_path=str(tmp_path / "images"),
        )
        (tmp_path / "images").mkdir()

        BackupEngine(settings).run()
        verified = BackupEngine(settings).verify()

        assert verified.canary_present is True
        assert verified.canary_decrypted is True
        assert verified.ok is True

    def test_verify_reports_an_absent_canary_before_any_run(
        self,
        backup_settings_base: dict[str, Any],
        bucket: str,
    ) -> None:
        """Distinct from a decryption failure. Conflating them tells an operator
        their key is wrong when the truth is that no backup has ever run."""
        from src.services.backup.engine import BackupEngine

        settings = _settings(backup_settings_base, backup_s3_bucket=bucket)
        verified = BackupEngine(settings).verify()

        assert verified.canary_present is False
        assert verified.canary_decrypted is None
        assert verified.ok is False

    def test_a_wrong_identity_is_a_decryption_failure_not_an_absent_canary(
        self,
        backup_settings_base: dict[str, Any],
        bucket: str,
        seeded_database: tuple[str, str, list[tuple[int, str]]],
        tmp_path: Path,
    ) -> None:
        from src.services.backup.engine import BackupEngine

        source_url, _, _ = seeded_database
        settings = _settings(
            backup_settings_base,
            backup_s3_bucket=bucket,
            database_url=source_url,
            image_storage_path=str(tmp_path / "images"),
            podcast_storage_path=str(tmp_path / "images"),
            audio_digest_storage_path=str(tmp_path / "images"),
        )
        (tmp_path / "images").mkdir()
        BackupEngine(settings).run()

        wrong_identity = tmp_path / "wrong-identity.txt"
        subprocess.run(["age-keygen", "-o", str(wrong_identity)], check=True, capture_output=True)
        verified = BackupEngine(
            _settings(
                backup_settings_base,
                backup_s3_bucket=bucket,
                backup_age_identity_path=str(wrong_identity),
            )
        ).verify()

        assert verified.canary_present is True
        assert verified.canary_decrypted is False
        assert verified.ok is False

    def test_no_production_system_is_contacted(self, backup_settings_base: dict[str, Any]) -> None:
        """Hard Constraint 1, asserted rather than assumed."""
        endpoint = str(backup_settings_base["backup_s3_endpoint"])
        assert "localhost" in endpoint or "127.0.0.1" in endpoint
        source = _source_database_url() or ""
        assert "localhost" in source or "127.0.0.1" in source
