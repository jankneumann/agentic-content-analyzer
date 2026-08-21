"""Store adapters: what each one invokes, and what it must never invoke with.

Assertions are on the constructed argv, never on call position. `call_args_list[2]`
breaks the moment a stage is added and passes for the wrong reason when one is
removed — it asserts an ordering, not a behavior.

Nothing here runs a subprocess. The adapters are pure builders, which is what lets
the credential-leak test enumerate every stage the module can produce and assert a
property over all of them, rather than over the one path a mock happened to take.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.services.backup import stores
from src.services.backup.models import (
    SKIP_MANAGED_PROVIDER,
    SKIP_NOT_CONFIGURED,
    StoreName,
)

SECRETS = (
    "pg-super-secret",
    "falkor-secret",
    "bao-root-token",
    "minio-secret-key",
)


def make_settings(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "database_url": "postgresql://aca_user:pg-super-secret@db.internal:5433/newsletters",
        "graphdb_provider": "neo4j",
        "graphdb_mode": "local",
        "neo4j_database": "neo4j",
        "falkordb_host": "graph.internal",
        "falkordb_port": 6380,
        "falkordb_password": "falkor-secret",
        "image_storage_path": "data/images",
        "podcast_storage_path": "data/podcasts",
        "audio_digest_storage_path": "data/audio-digests",
        "bao_addr": "https://bao.internal:8200",
        "bao_token": "bao-root-token",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestPostgresAdapter:
    def test_produces_a_custom_format_dump(self) -> None:
        plan = stores.plan_postgres(make_settings())
        assert plan.stage is not None
        assert plan.stage.argv[0] == "pg_dump"
        assert "--format=custom" in plan.stage.argv

    def test_connection_details_are_argv_and_password_is_environment(self) -> None:
        """A password in argv is world-readable in /proc for the life of the dump."""
        plan = stores.plan_postgres(make_settings())
        assert plan.stage is not None
        argv = plan.stage.argv
        assert "--host" in argv and "db.internal" in argv
        assert "--port" in argv and "5433" in argv
        assert "--username" in argv and "aca_user" in argv
        assert "--dbname" in argv and "newsletters" in argv
        assert plan.stage.env["PGPASSWORD"] == "pg-super-secret"
        assert not any("pg-super-secret" in part for part in argv)

    def test_percent_encoded_password_is_decoded(self) -> None:
        plan = stores.plan_postgres(
            make_settings(database_url="postgresql://u:p%40ss%2Fword@h:5432/d")
        )
        assert plan.stage is not None
        assert plan.stage.env["PGPASSWORD"] == "p@ss/word"

    def test_unconfigured_database_is_skipped_with_a_named_reason(self) -> None:
        plan = stores.plan_postgres(make_settings(database_url=None))
        assert plan.runnable is False
        assert plan.skip_reason == SKIP_NOT_CONFIGURED


class TestGraphDatabaseAdapter:
    @pytest.mark.parametrize("mode", ["local", "embedded"])
    def test_neo4j_dumps_when_the_filesystem_is_reachable(self, mode: str) -> None:
        plan = stores.plan_graphdb(make_settings(graphdb_provider="neo4j", graphdb_mode=mode))
        assert plan.stage is not None
        assert plan.stage.argv[:3] == ("neo4j-admin", "database", "dump")

    def test_managed_neo4j_is_skipped_explicitly_not_silently(self) -> None:
        """A4 — `neo4j-admin database dump` is impossible against AuraDB. A skip with
        a named reason is honest; an empty dump reported as captured is not."""
        plan = stores.plan_graphdb(make_settings(graphdb_provider="neo4j", graphdb_mode="cloud"))
        assert plan.runnable is False
        assert plan.skip_reason == SKIP_MANAGED_PROVIDER

    def test_falkordb_snapshots_and_declares_the_write(self) -> None:
        plan = stores.plan_graphdb(make_settings(graphdb_provider="falkordb"))
        assert plan.stage is not None
        assert plan.stage.argv[0] == "redis-cli"
        assert "--rdb" in plan.stage.argv
        # The single declared exception to read-only. It writes a snapshot, never
        # application data — stated in code so the exception is auditable.
        assert plan.writes_snapshot is True

    def test_falkordb_password_never_reaches_argv(self) -> None:
        plan = stores.plan_graphdb(make_settings(graphdb_provider="falkordb"))
        assert plan.stage is not None
        assert plan.stage.env["REDISCLI_AUTH"] == "falkor-secret"
        assert not any("falkor-secret" in part for part in plan.stage.argv)
        assert "-a" not in plan.stage.argv

    def test_every_other_store_declares_no_write(self) -> None:
        settings = make_settings()
        for plan in (
            stores.plan_postgres(settings),
            stores.plan_artifacts(settings),
            stores.plan_openbao(settings),
        ):
            assert plan.writes_snapshot is False


class TestArtifactsAdapter:
    def test_captures_every_artifact_directory(self) -> None:
        plan = stores.plan_artifacts(make_settings())
        assert plan.stage is not None
        assert plan.stage.argv[0] == "tar"
        for directory in ("data/images", "data/podcasts", "data/audio-digests"):
            assert directory in plan.stage.argv

    def test_capture_is_wholesale_not_row_driven(self) -> None:
        """Files on disk that no database row references are still the only copy."""
        plan = stores.plan_artifacts(make_settings())
        assert plan.stage is not None
        # tar over the directory — nothing in the invocation consults the database.
        assert not any("select" in part.lower() for part in plan.stage.argv)

    def test_no_directories_is_a_named_skip(self) -> None:
        plan = stores.plan_artifacts(make_settings(), existing=[])
        assert plan.runnable is False
        assert plan.skip_reason == stores.SKIP_NO_ARTIFACT_DIRECTORIES

    def test_duplicate_directories_are_collapsed(self) -> None:
        settings = make_settings(
            podcast_storage_path="data/images",
            audio_digest_storage_path="data/images",
        )
        assert stores.artifact_directories(settings) == ["data/images"]


class TestOpenBaoAdapter:
    def test_streams_a_raft_snapshot(self) -> None:
        plan = stores.plan_openbao(make_settings())
        assert plan.stage is not None
        assert plan.stage.argv == ("bao", "operator", "raft", "snapshot", "save", "-")

    def test_token_travels_by_environment(self) -> None:
        plan = stores.plan_openbao(make_settings())
        assert plan.stage is not None
        assert plan.stage.env["BAO_TOKEN"] == "bao-root-token"
        assert not any("bao-root-token" in part for part in plan.stage.argv)

    def test_secretstr_token_is_unwrapped(self) -> None:
        from pydantic import SecretStr

        plan = stores.plan_openbao(make_settings(bao_token=SecretStr("wrapped-token")))
        assert plan.stage is not None
        assert plan.stage.env["BAO_TOKEN"] == "wrapped-token"

    def test_unconfigured_openbao_is_skipped_not_failed(self) -> None:
        """Not every deployment runs OpenBao. Failing the run for an absent optional
        store trains operators to ignore a red backup."""
        plan = stores.plan_openbao(make_settings(bao_addr=None, bao_token=None))
        assert plan.runnable is False
        assert plan.skip_reason == SKIP_NOT_CONFIGURED
        assert plan.store is StoreName.OPENBAO


class TestNoCredentialReachesArgv:
    """The property, asserted over every stage the module can produce."""

    @pytest.mark.parametrize(
        "settings",
        [
            make_settings(),
            make_settings(graphdb_provider="falkordb"),
            make_settings(graphdb_mode="cloud"),
        ],
        ids=["neo4j-local", "falkordb", "neo4j-cloud"],
    )
    def test_no_secret_appears_in_any_constructed_argv(self, settings: object) -> None:
        for plan in stores.plan_all(settings):
            if plan.stage is None:
                continue
            joined = " ".join(plan.stage.argv)
            for secret in SECRETS:
                assert secret not in joined, f"{secret} leaked into {plan.store} argv"

    def test_no_secret_appears_in_the_target_upload_argv(self) -> None:
        from src.services.backup.target import TargetConfig, upload_stage

        config = TargetConfig(
            endpoint="https://acct.r2.cloudflarestorage.com",
            bucket="aca-backups",
            region="auto",
            prefix="aca",
            access_key_id="AKIAEXAMPLE",
            secret_access_key="minio-secret-key",
        )
        stage = upload_stage(config, "aca/daily/x/postgres.dump.age")
        joined = " ".join(stage.argv)
        assert "minio-secret-key" not in joined
        assert "AKIAEXAMPLE" not in joined
        assert stage.env["RCLONE_CONFIG_BACKUP_SECRET_ACCESS_KEY"] == "minio-secret-key"

    def test_the_age_recipient_is_the_one_thing_allowed_in_argv(self) -> None:
        """It is a PUBLIC key. Routing it through the environment would suggest it
        is a secret and invite someone to do the same with the identity."""
        from src.services.backup.target import encrypt_stage

        stage = encrypt_stage("age1qqqqexamplerecipient")
        assert "age1qqqqexamplerecipient" in stage.argv
        assert stage.env == {}
