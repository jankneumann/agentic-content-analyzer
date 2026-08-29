"""The backup engine: outcomes, silent-success defences, manifest, canary.

Every test here mocks the two execution seams (`run_pipeline`, `run_command`), so
no test contacts a database, a bucket, or a secret store — Hard Constraint 1 is a
property of the design, not of a promise.

Most of this file exists for one reason. The backup this change replaces reported
nothing and produced nothing for as long as it existed. The failure mode that
matters is not "the backup errored"; it is "the backup said it worked". So the
assertions are mostly about the paths where something goes wrong quietly.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from src.services.backup import engine as engine_module, target as target_module
from src.services.backup.engine import BackupEngine, BackupPreflightError
from src.services.backup.executor import CommandResult, PipelineResult
from src.services.backup.models import (
    FAIL_SIZE_MISMATCH,
    FAIL_STAGE_EXIT,
    RetentionTier,
    StoreName,
    StoreOutcome,
    StoreResult,
    retention_tier_for,
)

DIGEST = "a" * 64


def make_settings(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "environment": "production",
        "database_url": "postgresql://u:p@db.internal:5432/newsletters",
        "graphdb_provider": "neo4j",
        "graphdb_mode": "cloud",  # skipped, so the default run has one of each outcome
        "neo4j_database": "neo4j",
        "image_storage_path": "data/images",
        "podcast_storage_path": "data/podcasts",
        "audio_digest_storage_path": "data/audio-digests",
        "bao_addr": None,
        "bao_token": None,
        "backup_s3_endpoint": "https://acct.r2.cloudflarestorage.com",
        "backup_s3_bucket": "aca-backups",
        "backup_s3_region": "auto",
        "backup_s3_prefix": "aca",
        "backup_s3_access_key_id": "AKIAEXAMPLE",
        "backup_s3_secret_access_key": "r2-secret",
        "backup_age_recipient": "age1qqqqexamplerecipient",
        "backup_age_identity_path": None,
        "backup_monitoring_enabled": True,
        "backup_staleness_hours": 48,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def ok_pipeline(size: int = 4096) -> PipelineResult:
    return PipelineResult(
        stage_status=(("pg_dump", 0), ("tee", 0), ("age", 0), ("rclone", 0)),
        bytes_streamed=size,
        checksum_sha256=DIGEST,
    )


class Harness:
    """Records what the engine did, so tests assert on behavior not call order."""

    def __init__(self, *, pipeline: Any = None, size: int | None = 4096) -> None:
        self.pipelines: list[list[Any]] = []
        self.commands: list[list[str]] = []
        self.uploaded_text: dict[str, str] = {}
        self._pipeline = pipeline or (lambda stages, **_: ok_pipeline())
        self._size = size

    def run_pipeline(self, stages: Any, **kwargs: Any) -> PipelineResult:
        self.pipelines.append(list(stages))
        return self._pipeline(stages, **kwargs)

    def run_command(self, argv: Any, **kwargs: Any) -> CommandResult:
        argv = list(argv)
        self.commands.append(argv)
        if argv[:2] == ["rclone", "size"]:
            body = json.dumps({"count": 1, "bytes": self._size})
            return CommandResult(tuple(argv), 0, stdout=body)
        if argv[:2] == ["rclone", "rcat"]:
            self.uploaded_text[argv[2]] = str(kwargs.get("stdin_text") or "")
            return CommandResult(tuple(argv), 0)
        if argv[:2] == ["rclone", "lsjson"]:
            return CommandResult(tuple(argv), 0, stdout="[]")
        return CommandResult(tuple(argv), 0)

    @property
    def manifest(self) -> dict[str, Any] | None:
        for key, body in self.uploaded_text.items():
            if key.endswith("latest.json"):
                return json.loads(body)
        return None


@pytest.fixture
def harness() -> Any:
    def _make(**kwargs: Any) -> Harness:
        return Harness(**kwargs)

    return _make


def artifact_dirs(tmp_path: Any) -> dict[str, object]:
    """Settings overrides pointing the artifact stores at real directories.

    `plan_artifacts` stats the configured paths and skips when none exist, so a
    test that injects a failing `tar` stage needs the directories to be present
    or the stage never runs and the injected failure is unreachable.
    """
    names = (
        ("image_storage_path", "images"),
        ("podcast_storage_path", "podcasts"),
        ("audio_digest_storage_path", "audio-digests"),
    )
    overrides: dict[str, object] = {}
    for key, name in names:
        directory = tmp_path / name
        directory.mkdir(parents=True, exist_ok=True)
        overrides[key] = str(directory)
    return overrides


def run_engine(harness: Harness, settings: Any, *, now: datetime | None = None) -> Any:
    with (
        patch.object(engine_module, "run_pipeline", harness.run_pipeline),
        patch("src.services.backup.target.run_command", harness.run_command),
        patch.object(engine_module, "check_run_prerequisites", _preflight_ok),
    ):
        return BackupEngine(settings, now=now or datetime(2026, 8, 21, 3, 0, tzinfo=UTC)).run()


def _preflight_ok(*_args: Any, **_kwargs: Any) -> Any:
    from src.services.backup.preflight import PreflightReport

    return PreflightReport()


# ------------------------------------------------------------- per-store outcomes


class TestPerStoreOutcomes:
    def test_each_store_reports_its_own_outcome(self, harness: Any) -> None:
        h = harness()
        result = run_engine(h, make_settings())
        by_store = {s.store: s for s in result.stores}
        assert by_store[StoreName.POSTGRES].outcome is StoreOutcome.SUCCEEDED
        # cloud graph db and unconfigured OpenBao are honest skips, not failures
        assert by_store[StoreName.GRAPHDB].outcome is StoreOutcome.SKIPPED
        assert by_store[StoreName.OPENBAO].outcome is StoreOutcome.SKIPPED

    def test_openbao_when_configured_is_captured(self, harness: Any) -> None:
        h = harness()
        settings = make_settings(bao_addr="https://bao.internal:8200", bao_token="tkn")
        result = run_engine(h, settings)
        openbao = next(s for s in result.stores if s.store is StoreName.OPENBAO)
        assert openbao.outcome is StoreOutcome.SUCCEEDED
        assert openbao.artifact_key is not None
        assert openbao.artifact_key.endswith("openbao.snap.age")

    def test_a_failing_store_does_not_silently_pass(self, harness: Any) -> None:
        def failing(stages: Any, **_: Any) -> PipelineResult:
            first = stages[0].name
            if first == "pg_dump":
                return PipelineResult(stage_status=(("pg_dump", 2), ("rclone", 0)))
            return ok_pipeline()

        h = harness(pipeline=failing)
        result = run_engine(h, make_settings())
        postgres = next(s for s in result.stores if s.store is StoreName.POSTGRES)
        assert postgres.outcome is StoreOutcome.FAILED
        assert result.exit_code != 0

    def test_stores_that_succeeded_are_still_recorded_when_another_fails(
        self, harness: Any, tmp_path: Any
    ) -> None:
        def failing(stages: Any, **_: Any) -> PipelineResult:
            if stages[0].name == "tar":
                return PipelineResult(stage_status=(("tar", 1),))
            return ok_pipeline()

        h = harness(pipeline=failing)
        result = run_engine(h, make_settings(**artifact_dirs(tmp_path)))
        by_store = {s.store: s.outcome for s in result.stores}
        assert by_store[StoreName.ARTIFACTS] is StoreOutcome.FAILED
        assert by_store[StoreName.POSTGRES] is StoreOutcome.SUCCEEDED

    def test_a_non_required_failure_still_exits_non_zero(self, harness: Any, tmp_path: Any) -> None:
        """`succeeded` (manifest-worthy) and `exit_code` (operator-visible) are
        deliberately different questions. A failing artifacts store does not
        invalidate the Postgres backup, but it must not be reported as fine."""

        def failing(stages: Any, **_: Any) -> PipelineResult:
            if stages[0].name == "tar":
                return PipelineResult(stage_status=(("tar", 1),))
            return ok_pipeline()

        h = harness(pipeline=failing)
        result = run_engine(h, make_settings(**artifact_dirs(tmp_path)))
        assert result.succeeded is True
        assert result.exit_code == 1


# ------------------------------------------------------ silent-success defences


class TestPipelineStageStatus:
    def test_a_mid_pipe_failure_is_not_masked_by_the_last_stage(self, harness: Any) -> None:
        """A6.1 — a shell pipeline reports the LAST stage's status. pg_dump dying
        halfway still yields zero from rclone, and a truncated ciphertext uploads."""

        def masked(stages: Any, **_: Any) -> PipelineResult:
            if stages[0].name == "pg_dump":
                return PipelineResult(
                    stage_status=(("pg_dump", 2), ("age", 0), ("rclone", 0)),
                    bytes_streamed=17,
                    checksum_sha256=DIGEST,
                )
            return ok_pipeline()

        h = harness(pipeline=masked)
        result = run_engine(h, make_settings())
        postgres = next(s for s in result.stores if s.store is StoreName.POSTGRES)
        assert postgres.outcome is StoreOutcome.FAILED
        assert postgres.reason == FAIL_STAGE_EXIT

    def test_no_manifest_is_written_when_a_required_store_fails(self, harness: Any) -> None:
        def masked(stages: Any, **_: Any) -> PipelineResult:
            if stages[0].name == "pg_dump":
                return PipelineResult(stage_status=(("pg_dump", 2), ("rclone", 0)))
            return ok_pipeline()

        h = harness(pipeline=masked)
        run_engine(h, make_settings())
        assert h.manifest is None

    def test_a_missing_digest_fails_the_store(self, harness: Any) -> None:
        """No digest means nothing to verify the artifact against later. Recording
        it as succeeded would put an unverifiable object in the manifest."""

        def no_digest(stages: Any, **_: Any) -> PipelineResult:
            if stages[0].name == "pg_dump":
                return PipelineResult(
                    stage_status=(("pg_dump", 0), ("rclone", 0)),
                    bytes_streamed=4096,
                    checksum_sha256=None,
                )
            return ok_pipeline()

        h = harness(pipeline=no_digest)
        result = run_engine(h, make_settings())
        postgres = next(s for s in result.stores if s.store is StoreName.POSTGRES)
        assert postgres.outcome is StoreOutcome.FAILED


class TestSizeReadBack:
    def test_a_size_mismatch_marks_the_store_failed(self, harness: Any) -> None:
        """A successful upload of a TRUNCATED stream is still a successful upload."""
        h = harness(size=1)  # target reports 1 byte; the pipeline streamed 4096
        result = run_engine(h, make_settings())
        postgres = next(s for s in result.stores if s.store is StoreName.POSTGRES)
        assert postgres.outcome is StoreOutcome.FAILED
        assert postgres.reason == FAIL_SIZE_MISMATCH

    def test_an_unreadable_size_marks_the_store_failed(self, harness: Any) -> None:
        h = harness(size=None)
        result = run_engine(h, make_settings())
        postgres = next(s for s in result.stores if s.store is StoreName.POSTGRES)
        assert postgres.outcome is StoreOutcome.FAILED

    def test_the_size_is_actually_read_back_from_the_target(self, harness: Any) -> None:
        h = harness()
        run_engine(h, make_settings())
        assert any(argv[:2] == ["rclone", "size"] for argv in h.commands)


# ------------------------------------------------------------------- read-only


class TestBackupMakesNoMutations:
    def test_no_delete_operation_is_ever_constructed(self, harness: Any) -> None:
        h = harness()
        run_engine(h, make_settings())
        every_argv = [" ".join(map(str, argv)) for argv in h.commands]
        for stages in h.pipelines:
            every_argv.extend(" ".join(stage.argv) for stage in stages)
        forbidden = ("delete", "purge", "deletefile", "rmdir", "--rm", "drop")
        for line in every_argv:
            lowered = line.lower()
            assert not any(word in lowered.split() for word in forbidden), line

    def test_the_only_declared_write_is_the_falkordb_snapshot(self) -> None:
        from src.services.backup.stores import plan_all

        settings = make_settings(graphdb_provider="falkordb")
        writers = [p.store for p in plan_all(settings) if p.writes_snapshot]
        assert writers == [StoreName.GRAPHDB]

    def test_no_source_store_receives_a_write_verb(self, harness: Any) -> None:
        h = harness(pipeline=lambda stages, **_: ok_pipeline())
        run_engine(h, make_settings(bao_addr="https://b", bao_token="t"))
        for stages in h.pipelines:
            dump_stage = stages[0]
            joined = " ".join(dump_stage.argv).lower()
            for verb in ("insert", "update", "truncate", "restore", "flushall"):
                assert verb not in joined


# --------------------------------------------------------------------- manifest


class TestManifest:
    def test_manifest_records_environment_timestamps_and_stores(self, harness: Any) -> None:
        h = harness()
        run_engine(h, make_settings())
        manifest = h.manifest
        assert manifest is not None
        assert manifest["environment"] == "production"
        assert manifest["completed_at"].endswith("Z")
        assert manifest["started_at"].endswith("Z")
        postgres = next(s for s in manifest["stores"] if s["store"] == "postgres")
        assert postgres["bytes"] == 4096
        assert postgres["checksum_sha256"] == DIGEST
        assert postgres["artifact_key"].endswith("postgres.dump.age")

    def test_manifest_conforms_to_the_published_contract(self, harness: Any) -> None:
        from pathlib import Path

        from jsonschema import FormatChecker
        from jsonschema.validators import validator_for

        schema_path = (
            Path(__file__).resolve().parents[2]
            / "openspec"
            / "contracts"
            / "backup"
            / "schemas"
            / "backup-manifest.schema.json"
        )
        schema = json.loads(schema_path.read_text())
        h = harness()
        run_engine(h, make_settings())
        validator_for(schema)(schema, format_checker=FormatChecker()).validate(h.manifest)

    def test_manifest_contains_no_credentials(self, harness: Any) -> None:
        h = harness()
        run_engine(h, make_settings())
        body = json.dumps(h.manifest)
        for secret in ("r2-secret", "AKIAEXAMPLE", "postgresql://", "@db.internal"):
            assert secret not in body

    def test_manifest_key_is_environment_scoped(self, harness: Any) -> None:
        """A6.3 — with a fixed key under a shared prefix, a staging run overwrites
        the production freshness signal, and production can stop backing up
        entirely while /ready still reports ok."""
        h = harness()
        run_engine(h, make_settings())
        keys = [k for k in h.uploaded_text if k.endswith("latest.json")]
        assert keys == ["backup:aca-backups/aca/manifests/production/latest.json"]

    def test_two_environments_do_not_overwrite_each_other(self, harness: Any) -> None:
        prod = harness()
        run_engine(prod, make_settings(environment="production"))
        staging = harness()
        run_engine(staging, make_settings(environment="staging"))
        assert set(prod.uploaded_text) & set(staging.uploaded_text) == set()

    def test_recorded_environment_matches_the_key_segment(self, harness: Any) -> None:
        h = harness()
        run_engine(h, make_settings(environment="staging"))
        key = next(k for k in h.uploaded_text if k.endswith("latest.json"))
        assert "/manifests/staging/" in key
        assert h.manifest is not None
        assert h.manifest["environment"] == "staging"

    def test_manifest_is_the_only_unencrypted_object(self, harness: Any) -> None:
        h = harness()
        run_engine(h, make_settings())
        for key in h.uploaded_text:
            assert key.endswith("latest.json") or key.endswith(".age")


# ---------------------------------------------------------------------- canary


class TestCanary:
    def test_the_run_writes_the_canary_through_the_same_encryption_path(self, harness: Any) -> None:
        """A canary placed by hand proves a human once ran `age` correctly. This one
        proves the pipeline that wrote today's backups produces readable output."""
        h = harness()
        run_engine(h, make_settings())
        canary_pipelines = [p for p in h.pipelines if p[0].name == "canary"]
        assert len(canary_pipelines) == 1
        assert [stage.name for stage in canary_pipelines[0]] == ["canary", "age", "rclone"]

    def test_no_canary_is_written_for_a_failed_run(self, harness: Any) -> None:
        def failing(stages: Any, **_: Any) -> PipelineResult:
            if stages[0].name == "pg_dump":
                return PipelineResult(stage_status=(("pg_dump", 1),))
            return ok_pipeline()

        h = harness(pipeline=failing)
        run_engine(h, make_settings())
        assert not [p for p in h.pipelines if p[0].name == "canary"]


# -------------------------------------------------------------------- tiering


class TestRetentionTierAtWriteTime:
    @pytest.mark.parametrize(
        ("run_date", "expected"),
        [
            (date(2026, 8, 1), RetentionTier.MONTHLY),  # first of month
            (date(2026, 3, 1), RetentionTier.MONTHLY),  # 1st AND a Sunday
            (date(2026, 8, 23), RetentionTier.WEEKLY),  # Sunday
            (date(2026, 8, 21), RetentionTier.DAILY),  # Friday
        ],
    )
    def test_promotion_rule(self, run_date: date, expected: RetentionTier) -> None:
        assert retention_tier_for(run_date) is expected

    def test_a_run_belongs_to_exactly_one_tier(self) -> None:
        """A5 — the tier is a key SEGMENT, so overlapping tiers would duplicate every
        artifact and make lifecycle expiry ambiguous."""
        assert retention_tier_for(date(2026, 3, 1)) is RetentionTier.MONTHLY

    def test_the_tier_appears_in_the_artifact_key_and_the_manifest(self, harness: Any) -> None:
        h = harness()
        result = run_engine(h, make_settings(), now=datetime(2026, 8, 23, 3, 0, tzinfo=UTC))
        postgres = next(s for s in result.stores if s.store is StoreName.POSTGRES)
        assert postgres.artifact_key is not None
        assert "/weekly/" in postgres.artifact_key
        assert h.manifest is not None
        assert h.manifest["retention_tier"] == "weekly"

    def test_the_artifact_key_embeds_an_iso_utc_stamp(self, harness: Any) -> None:
        h = harness()
        result = run_engine(h, make_settings(), now=datetime(2026, 8, 21, 3, 4, 5, tzinfo=UTC))
        postgres = next(s for s in result.stores if s.store is StoreName.POSTGRES)
        assert postgres.artifact_key is not None
        assert "2026-08-21T030405Z" in postgres.artifact_key


# ------------------------------------------------------------------- preflight


class TestRunPreflight:
    def test_run_aborts_naming_each_missing_binary_before_touching_a_store(
        self, harness: Any
    ) -> None:
        """A6.4 — the preflight was originally attached only to `verify`, which the
        timer never invokes. Discovering a missing `age` after pg_dump has read a
        production database is a preflight that did not happen."""
        h = harness()
        missing = {"age", "rclone"}
        with (
            patch.object(engine_module, "run_pipeline", h.run_pipeline),
            patch("src.services.backup.target.run_command", h.run_command),
            patch("shutil.which", lambda name: None if name in missing else f"/usr/bin/{name}"),
            pytest.raises(BackupPreflightError) as caught,
        ):
            BackupEngine(make_settings()).run()

        assert set(caught.value.report.missing_binaries) >= missing
        assert h.pipelines == []  # nothing was contacted
        assert h.commands == []

    def test_run_preflight_never_requires_the_decryption_identity(self) -> None:
        """The gx-10 host holds the recipient and must NOT hold the identity — a
        host compromise otherwise decrypts every backup that host produced."""
        from src.services.backup.preflight import check_run_prerequisites
        from src.services.backup.stores import plan_all

        settings = make_settings(backup_age_identity_path=None)
        report = check_run_prerequisites(
            settings, plan_all(settings), which=lambda name: f"/usr/bin/{name}"
        )
        assert report.ok is True

    def test_missing_recipient_aborts_before_any_upload(self, harness: Any) -> None:
        h = harness()
        settings = make_settings(backup_age_recipient=None)
        with (
            patch.object(engine_module, "run_pipeline", h.run_pipeline),
            patch("src.services.backup.target.run_command", h.run_command),
            patch("shutil.which", lambda name: f"/usr/bin/{name}"),
            pytest.raises(BackupPreflightError) as caught,
        ):
            BackupEngine(settings).run()

        assert "BACKUP_AGE_RECIPIENT" in caught.value.report.missing_settings
        assert h.uploaded_text == {}
        assert h.pipelines == []

    def test_preflight_names_only_binaries_this_run_will_invoke(self) -> None:
        """A deployment with no OpenBao must not be told to install `bao`. Naming
        irrelevant prerequisites is how a preflight becomes noise."""
        from src.services.backup.preflight import required_binaries
        from src.services.backup.stores import plan_all

        settings = make_settings(bao_addr=None, bao_token=None)
        assert "bao" not in required_binaries(plan_all(settings))
        with_bao = make_settings(bao_addr="https://b", bao_token="t")
        assert "bao" in required_binaries(plan_all(with_bao))


# ------------------------------------------------------------- store evidence


class TestStoreResultRefusesUnverifiableSuccess:
    @pytest.mark.parametrize("dropped", ["artifact_key", "size", "checksum_sha256"])
    def test_a_succeeded_store_without_evidence_cannot_be_constructed(self, dropped: str) -> None:
        kwargs: dict[str, Any] = {
            "artifact_key": "aca/daily/x/postgres.dump.age",
            "size": 10,
            "checksum_sha256": DIGEST,
        }
        kwargs[dropped] = None
        with pytest.raises(ValueError, match="missing evidence"):
            StoreResult.succeeded(StoreName.POSTGRES, **kwargs)

    def test_a_non_succeeded_store_must_name_a_reason(self) -> None:
        with pytest.raises(ValueError, match="must name a reason"):
            StoreResult(
                store=StoreName.POSTGRES,
                outcome=StoreOutcome.FAILED,
                required=True,
                reason=None,
            )


# ------------------------------------------------------------ manifest reader


class TestManifestReaderEnvironmentCheck:
    """A8/A6.3 — one reader, and it refuses a manifest that is not about us."""

    @staticmethod
    def _read(document: Any, settings: Any) -> Any:
        from src.services.backup import manifest_reader

        manifest_reader.reset_cache()
        with patch.object(manifest_reader, "_fetch_manifest", lambda _s: document):
            return manifest_reader.read_freshness(
                settings,
                now=datetime(2026, 8, 21, 4, 0, tzinfo=UTC),
                use_cache=False,
            )

    def _manifest(self, **overrides: Any) -> dict[str, Any]:
        base: dict[str, Any] = {
            "schema_version": 1,
            "environment": "production",
            "started_at": "2026-08-21T03:00:00Z",
            "completed_at": "2026-08-21T03:04:00Z",
            "overall_outcome": "succeeded",
            "retention_tier": "daily",
            "stores": [{"store": "postgres", "outcome": "succeeded", "required": True}],
        }
        base.update(overrides)
        return base

    def test_a_matching_environment_is_read(self) -> None:
        from src.services.backup.manifest_reader import BackupFreshnessStatus

        freshness = self._read(self._manifest(), make_settings(environment="production"))
        assert freshness.status is BackupFreshnessStatus.OK

    def test_a_foreign_environment_is_not_evidence_however_fresh(self) -> None:
        from src.services.backup.manifest_reader import BackupFreshnessStatus

        freshness = self._read(
            self._manifest(environment="staging"), make_settings(environment="production")
        )
        assert freshness.status is BackupFreshnessStatus.ENVIRONMENT_MISMATCH

    def test_the_reader_never_invokes_age(self) -> None:
        """The manifest is the one unencrypted object precisely so this path needs
        read access to one key and nothing more. A reader that could decrypt would
        be a reader worth stealing."""
        import inspect

        from src.services.backup import manifest_reader

        lines = inspect.getsource(manifest_reader).splitlines()
        code = [line for line in lines if not line.strip().startswith(("#", '"', "*"))]
        assert not [line for line in code if '"age"' in line or "'age'" in line]
        assert not [line for line in code if "identity" in line and "=" in line]

    def test_the_reader_asks_for_the_environment_scoped_key(self) -> None:
        from src.services.backup.target import manifest_key

        assert manifest_key("aca", "production") == "aca/manifests/production/latest.json"
        assert manifest_key("aca", "staging") != manifest_key("aca", "production")


# ------------------------------------------------------------------- verify

AGE_AVAILABLE = shutil.which("age") is not None and shutil.which("age-keygen") is not None


def _which(name: str) -> str:
    resolved = shutil.which(name)
    if resolved is None:  # pragma: no cover - guarded by skipif
        raise RuntimeError(f"required test binary not found: {name}")
    return resolved


@pytest.mark.skipif(not AGE_AVAILABLE, reason="requires the real `age` and `age-keygen`")
class TestVerifyAgainstRealCiphertext:
    """`verify` is the only command that claims a backup can be RESTORED.

    So it is tested against ciphertext a real `age` actually produced. The first
    implementation read the canary through `run_command`'s text path, which decodes
    stdout as strict UTF-8 — age writes raw binary, so the happy path raised
    `UnicodeDecodeError`, and any ciphertext that did decode would not survive being
    re-encoded on the way into `age --decrypt`. Every mock-only test passed. The one
    command whose job is to prove restorability failed on restorable backups.
    """

    @staticmethod
    def _keypair(directory: Path) -> tuple[Path, str]:
        directory.mkdir(parents=True, exist_ok=True)
        identity = directory / "identity.txt"
        generated = subprocess.run(
            [_which("age-keygen"), "-o", str(identity)],
            capture_output=True,
            text=True,
            check=True,
        )
        recipient = ""
        for line in (generated.stderr + generated.stdout).splitlines():
            if "age1" in line:
                recipient = line.split()[-1].strip()
                break
        assert recipient.startswith("age1")
        return identity, recipient

    @staticmethod
    def _encrypt(recipient: str, plaintext: str) -> bytes:
        return subprocess.run(
            [_which("age"), "--encrypt", "--recipient", recipient],
            input=plaintext.encode(),
            capture_output=True,
            check=True,
        ).stdout

    def _verify_with(self, ciphertext: bytes, identity: Path) -> Any:
        from src.services.backup.executor import run_command as real_run_command

        def fake_run_command(argv: Any, **kwargs: Any) -> CommandResult:
            argv = list(argv)
            if argv[:2] == ["rclone", "cat"]:
                # The ONLY stub. `age --decrypt` below runs for real, against these
                # exact bytes, which is the whole point of this test.
                return CommandResult(tuple(argv), 0, stdout_bytes=ciphertext)
            return real_run_command(argv, **kwargs)

        listing = json.dumps(
            [
                {"Name": "canary.txt.age", "Path": "canary.txt.age"},
                {"Name": "latest.json", "Path": "latest.json"},
            ]
        )

        def fake_target_command(argv: Any, **_kwargs: Any) -> CommandResult:
            return CommandResult(tuple(argv), 0, stdout=listing)

        settings = make_settings(backup_age_identity_path=str(identity))
        with (
            patch.object(engine_module, "run_command", fake_run_command),
            patch("src.services.backup.target.run_command", fake_target_command),
            patch.object(engine_module, "check_run_prerequisites", _preflight_ok),
        ):
            return BackupEngine(settings).verify()

    def test_a_real_canary_decrypts(self, tmp_path: Path) -> None:
        identity, recipient = self._keypair(tmp_path / "mine")
        ciphertext = self._encrypt(recipient, target_module.CANARY_PLAINTEXT)
        result = self._verify_with(ciphertext, identity)
        assert result.canary_present is True
        assert result.canary_decrypted is True
        assert result.ok is True

    def test_a_canary_encrypted_to_another_key_is_reported_as_undecryptable(
        self, tmp_path: Path
    ) -> None:
        """A wrong identity must be a clean `False`, not a crash and not a `True`."""
        identity, _ = self._keypair(tmp_path / "mine")
        _, stranger = self._keypair(tmp_path / "other")
        ciphertext = self._encrypt(stranger, target_module.CANARY_PLAINTEXT)
        result = self._verify_with(ciphertext, identity)
        assert result.canary_decrypted is False
        assert result.ok is False

    def test_a_canary_holding_the_wrong_plaintext_does_not_pass(self, tmp_path: Path) -> None:
        identity, recipient = self._keypair(tmp_path / "mine")
        ciphertext = self._encrypt(recipient, "not-the-canary")
        result = self._verify_with(ciphertext, identity)
        assert result.canary_decrypted is False
