"""Browser-profile directories never reach a backup or a sync.

A Playwright persistent profile holds live session cookies. These tests populate a
real profile directory INSIDE a backed-up or synced root — the case where an
operator points an artifact path or a local bucket at ``$HOME`` or ``~/.aca`` —
and assert on what actually comes out: the member list of the tar stream that the
backup's own argv produces, and the files that actually land on the sync target.
Asserting on the argv alone would prove only that an option was passed, not that
``tar`` honoured it.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.config import browser_profiles
from src.config.settings import Settings
from src.services.backup import engine as engine_module, stores
from src.services.backup.engine import BackupEngine
from src.services.backup.executor import CommandResult, PipelineResult, Stage
from src.services.backup.models import StoreName, StoreOutcome
from src.services.backup.preflight import PreflightReport
from src.services.file_storage import LocalFileStorage
from src.sync.file_syncer import FileRef, FileSyncer

TAR_AVAILABLE = shutil.which("tar") is not None
requires_tar = pytest.mark.skipif(not TAR_AVAILABLE, reason="tar binary not installed")

COOKIE_BYTES = b"auth_token=not-a-real-cookie"


def populate_profile(profile_root: Path, site: str = "x") -> Path:
    """A profile directory shaped like Chromium's, with a cookie database."""
    cookie_file = profile_root / site / "Default" / "Cookies"
    cookie_file.parent.mkdir(parents=True, exist_ok=True)
    cookie_file.write_bytes(COOKIE_BYTES)
    return cookie_file


def settings_for(artifact_root: Path | str, profiles_dir: Path | str) -> SimpleNamespace:
    return SimpleNamespace(
        image_storage_path=str(artifact_root),
        podcast_storage_path=str(artifact_root),
        audio_digest_storage_path=str(artifact_root),
        browser_profiles_dir=str(profiles_dir),
    )


def tar_members(stage: Stage) -> list[str]:
    """Run the plan's own argv (no shell) and list the archive it streamed."""
    completed = subprocess.run(list(stage.argv), capture_output=True, check=True)
    with tarfile.open(fileobj=io.BytesIO(completed.stdout)) as archive:
        return archive.getnames()


# ------------------------------------------------------------------ the helper


class TestBrowserProfilesDir:
    def test_default_is_under_the_users_aca_directory(self) -> None:
        assert Settings(_env_file=None).browser_profiles_dir == "~/.aca/browser-profiles"
        resolved = browser_profiles.browser_profiles_dir(SimpleNamespace())
        assert resolved == Path.home() / ".aca" / "browser-profiles"

    def test_setting_overrides_the_default(self, tmp_path: Path) -> None:
        settings = SimpleNamespace(browser_profiles_dir=str(tmp_path / "profiles"))
        assert browser_profiles.excluded_roots(settings) == ((tmp_path / "profiles").resolve(),)

    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("home/u/.aca/browser-profiles/x/Cookies", True),
            (".aca/browser-profiles", True),
            ("/abs/.aca/browser-profiles", True),
            ("home/u/xaca/browser-profiles/Cookies", False),
            ("home/u/.aca/browser-profiles-old/Cookies", False),
            ("home/u/.aca/other", False),
        ],
    )
    def test_pattern_matches_whole_components_only(self, path: str, expected: bool) -> None:
        assert browser_profiles.matches_excluded_pattern(path) is expected


# ------------------------------------------------------- the artifacts tarball


@requires_tar
class TestArtifactsTarballSkipsBrowserProfiles:
    def test_profiles_in_the_default_layout_under_an_artifact_root(self, tmp_path: Path) -> None:
        """An operator points an artifact path at $HOME: the default layout is
        inside it, and must not be in the tar."""
        home = tmp_path / "home"
        populate_profile(home / ".aca" / "browser-profiles")
        (home / "keep.jpg").write_bytes(b"image")
        (home / ".aca" / "other.txt").write_bytes(b"not a profile")

        plan = stores.plan_artifacts(settings_for(home, home / ".aca" / "browser-profiles"))
        assert plan.stage is not None
        members = tar_members(plan.stage)

        assert not any("browser-profiles" in m for m in members), members
        assert any(m.endswith("home/keep.jpg") for m in members)
        assert any(m.endswith(".aca/other.txt") for m in members)

    def test_a_configured_root_with_an_unrecognisable_name_is_still_excluded(
        self, tmp_path: Path
    ) -> None:
        """The pattern cannot catch this one; the resolved-path check must."""
        artifacts = tmp_path / "artifacts"
        profiles = artifacts / "sessions"
        populate_profile(profiles)
        (artifacts / "sessions-archive").mkdir()
        (artifacts / "sessions-archive" / "keep.mp3").write_bytes(b"audio")

        plan = stores.plan_artifacts(settings_for(artifacts, profiles))
        assert plan.stage is not None
        members = tar_members(plan.stage)

        assert not any("Cookies" in m for m in members), members
        assert not any(m.rstrip("/").endswith("artifacts/sessions") for m in members)
        # Anchored and component-wise: a sibling sharing the prefix is kept.
        assert any(m.endswith("sessions-archive/keep.mp3") for m in members)

    def test_a_symlinked_profiles_setting_is_resolved(self, tmp_path: Path) -> None:
        artifacts = tmp_path / "artifacts"
        real_profiles = artifacts / "state"
        populate_profile(real_profiles)
        link = tmp_path / "profiles-link"
        link.symlink_to(real_profiles, target_is_directory=True)

        plan = stores.plan_artifacts(settings_for(artifacts, link))
        assert plan.stage is not None
        assert not any("Cookies" in m for m in tar_members(plan.stage))

    def test_a_relative_operand_keeps_the_spelling_tar_uses(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        populate_profile(tmp_path / "data" / "state")
        (tmp_path / "data" / "keep.jpg").write_bytes(b"image")

        plan = stores.plan_artifacts(settings_for("./data", tmp_path / "data" / "state"))
        assert plan.stage is not None
        assert "--exclude=./data/state" in plan.stage.argv
        members = tar_members(plan.stage)
        assert not any("Cookies" in m for m in members), members
        assert any(m.endswith("data/keep.jpg") for m in members)

    def test_a_profile_under_another_users_home_is_caught_by_the_pattern(
        self, tmp_path: Path
    ) -> None:
        """`~` expands per user: the backup's service account resolves a different
        home than the operator who logged in. The pattern covers that gap."""
        artifacts = tmp_path / "srv"
        populate_profile(artifacts / "operator" / ".aca" / "browser-profiles")
        (artifacts / "keep.jpg").write_bytes(b"image")

        plan = stores.plan_artifacts(settings_for(artifacts, tmp_path / "service-home" / "p"))
        assert plan.stage is not None
        members = tar_members(plan.stage)
        assert not any("browser-profiles" in m for m in members), members
        assert any(m.endswith("srv/keep.jpg") for m in members)

    def test_an_artifact_directory_inside_the_profiles_root_is_dropped(
        self, tmp_path: Path
    ) -> None:
        profiles = tmp_path / "profiles"
        populate_profile(profiles)
        images = tmp_path / "images"
        images.mkdir()
        (images / "keep.jpg").write_bytes(b"image")
        settings = SimpleNamespace(
            image_storage_path=str(images),
            podcast_storage_path=str(profiles / "x"),
            audio_digest_storage_path=str(profiles),
            browser_profiles_dir=str(profiles),
        )

        plan = stores.plan_artifacts(settings)
        assert plan.stage is not None
        assert str(profiles) not in plan.stage.argv
        assert str(profiles / "x") not in plan.stage.argv
        members = tar_members(plan.stage)
        assert not any("Cookies" in m for m in members)
        assert any(m.endswith("images/keep.jpg") for m in members)

    def test_only_profile_directories_configured_is_a_named_skip(self, tmp_path: Path) -> None:
        profiles = tmp_path / "profiles"
        populate_profile(profiles)
        plan = stores.plan_artifacts(settings_for(profiles, profiles))
        assert plan.runnable is False
        assert plan.skip_reason == stores.SKIP_NO_ARTIFACT_DIRECTORIES


class TestTarArgvShape:
    def test_exclusions_precede_the_operands_and_no_shell_is_involved(self, tmp_path: Path) -> None:
        """GNU tar applies `--exclude` to the operands after it, and the executor
        forbids shell pipelines (a shell reports only the LAST stage's status)."""
        artifacts = tmp_path / "artifacts"
        populate_profile(artifacts / "sessions")
        plan = stores.plan_artifacts(settings_for(artifacts, artifacts / "sessions"))
        assert plan.stage is not None
        argv = list(plan.stage.argv)
        assert argv[0] == "tar"
        assert "sh" not in argv and "-c" not in argv
        operand_at = argv.index(str(artifacts))
        excludes = [i for i, part in enumerate(argv) if part.startswith("--exclude=")]
        assert excludes and max(excludes) < operand_at
        assert f"--exclude={artifacts / 'sessions'}" in argv
        assert "--exclude=.aca/browser-profiles" in argv


# ------------------------------------------------------------- aca backup run


@requires_tar
class TestBackupRunSkipsBrowserProfiles:
    def test_the_artifacts_store_streams_no_profile_file(self, tmp_path: Path) -> None:
        """Drive the real engine; execute the tar stage it hands the pipeline."""
        home = tmp_path / "home"
        populate_profile(home / ".aca" / "browser-profiles")
        (home / "keep.jpg").write_bytes(b"image")

        settings = SimpleNamespace(
            environment="production",
            database_url=None,
            graphdb_provider="neo4j",
            graphdb_mode="cloud",
            bao_addr=None,
            bao_token=None,
            backup_s3_endpoint="https://acct.r2.cloudflarestorage.com",
            backup_s3_bucket="aca-backups",
            backup_s3_region="auto",
            backup_s3_prefix="aca",
            backup_s3_access_key_id="AKIAEXAMPLE",
            backup_s3_secret_access_key="r2-secret",
            backup_age_recipient="age1qqqqexamplerecipient",
            **vars(settings_for(home, home / ".aca" / "browser-profiles")),
        )
        streamed: dict[str, list[str]] = {}

        def run_pipeline(stages: Any, **_kwargs: Any) -> PipelineResult:
            first = stages[0]
            if first.name == "tar":
                streamed["members"] = tar_members(first)
            return PipelineResult(
                stage_status=tuple((s.name, 0) for s in stages),
                bytes_streamed=10,
                checksum_sha256="a" * 64,
            )

        def run_command(argv: Any, **_kwargs: Any) -> CommandResult:
            argv = list(argv)
            if argv[:2] == ["rclone", "size"]:
                return CommandResult(tuple(argv), 0, stdout='{"count": 1, "bytes": 10}')
            return CommandResult(tuple(argv), 0)

        with (
            patch.object(engine_module, "run_pipeline", run_pipeline),
            patch("src.services.backup.target.run_command", run_command),
            patch.object(
                engine_module, "check_run_prerequisites", lambda *_a, **_k: PreflightReport()
            ),
        ):
            result = BackupEngine(settings, now=datetime(2026, 9, 22, 3, 0, tzinfo=UTC)).run()

        artifacts = next(s for s in result.stores if s.store is StoreName.ARTIFACTS)
        assert artifacts.outcome is StoreOutcome.SUCCEEDED
        members = streamed["members"]
        assert any(m.endswith("home/keep.jpg") for m in members)
        assert not any("browser-profiles" in m or "Cookies" in m for m in members), members


# ------------------------------------------------------------------- aca sync


def local_bucket(root: Path, bucket: str = "images") -> LocalFileStorage:
    return LocalFileStorage(base_path=str(root), bucket=bucket)


class TestFileSyncSkipsBrowserProfiles:
    def _syncer(
        self, source_root: Path, target_root: Path, excluded: tuple[Path, ...]
    ) -> FileSyncer:
        return FileSyncer(
            MagicMock(),
            {"images": local_bucket(source_root)},
            {"images": local_bucket(target_root)},
            excluded=excluded,
        )

    def test_a_source_bucket_rooted_at_home_never_copies_the_profile(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        profiles = home / ".aca" / "browser-profiles"
        populate_profile(profiles)
        (home / "2026" / "keep.jpg").parent.mkdir(parents=True)
        (home / "2026" / "keep.jpg").write_bytes(b"image")
        target = tmp_path / "target"

        refs = [
            FileRef("images", "storage_path", "images", "images/2026/keep.jpg"),
            FileRef(
                "images", "storage_path", "images", "images/.aca/browser-profiles/x/Default/Cookies"
            ),
        ]
        stats = self._syncer(home, target, (profiles.resolve(),)).sync_files(refs)

        assert stats.copied == 1
        assert stats.excluded == 1
        assert (target / "2026" / "keep.jpg").exists()
        assert not any(p.name == "Cookies" for p in target.rglob("*"))

    def test_a_configured_root_with_an_unrecognisable_name_is_excluded(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "source"
        profiles = source / "sessions"
        populate_profile(profiles)
        target = tmp_path / "target"
        refs = [FileRef("images", "storage_path", "images", "sessions/x/Default/Cookies")]

        stats = self._syncer(source, target, (profiles.resolve(),)).sync_files(refs)

        assert stats.excluded == 1
        assert stats.copied == 0
        assert not any(p.name == "Cookies" for p in target.rglob("*"))

    def test_a_target_bucket_containing_the_profile_is_never_written_into(
        self, tmp_path: Path
    ) -> None:
        """Sync must not overwrite a live session on the receiving machine either."""
        source = tmp_path / "source"
        populate_profile(source / "sessions")
        target = tmp_path / "target"
        live_cookie = populate_profile(target / "sessions")
        live_cookie.unlink()  # would be recreated by a copy
        refs = [FileRef("images", "storage_path", "images", "sessions/x/Default/Cookies")]

        stats = self._syncer(source, target, ((target / "sessions").resolve(),)).sync_files(refs)

        assert stats.excluded == 1
        assert not live_cookie.exists()

    def test_dry_run_reports_the_exclusion_and_never_counts_the_ref(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        profiles = home / ".aca" / "browser-profiles"
        populate_profile(profiles)
        refs = [
            FileRef("images", "storage_path", "images", "images/.aca/browser-profiles/x/C"),
            FileRef("images", "storage_path", "images", "images/2026/keep.jpg"),
        ]

        stats = self._syncer(home, tmp_path / "t", (profiles.resolve(),)).sync_files(
            refs, dry_run=True
        )

        assert stats.excluded == 1
        assert stats.per_bucket["images"]["would_copy"] == 1
        assert "excluded=1" in stats.summary()

    def test_the_pattern_applies_to_non_local_providers_too(self, tmp_path: Path) -> None:
        source = MagicMock(provider_name="s3", bucket="b")
        target = MagicMock(provider_name="s3", bucket="c")
        syncer = FileSyncer(MagicMock(), {"images": source}, {"images": target}, excluded=())
        refs = [FileRef("images", "storage_path", "images", "u/.aca/browser-profiles/x/C")]

        stats = syncer.sync_files(refs)

        assert stats.excluded == 1
        source.get.assert_not_called()

    def test_default_exclusion_comes_from_settings(self, tmp_path: Path) -> None:
        profiles = tmp_path / "profiles"
        with patch(
            "src.config.settings.get_settings",
            return_value=SimpleNamespace(browser_profiles_dir=str(profiles)),
        ):
            syncer = FileSyncer(MagicMock(), {}, {})
        assert syncer._excluded == (profiles.resolve(),)
