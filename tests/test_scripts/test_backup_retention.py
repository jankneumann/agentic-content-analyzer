"""Retention applier and the shipped scheduling units.

The retention applier is the only tool in this repository that can be pointed at
the backup target with authority over its lifecycle configuration. A lifecycle
rule with a wrong prefix deletes BACKUPS rather than data, and unlike a bad
migration there is nothing to roll back to. So the dry-run default is tested as a
behavior, not assumed from an argparse flag.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
import yaml

from scripts.backup_retention import (
    DIALECTS,
    POLICY_PATH,
    build_rules,
    load_policy,
    main,
    render,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_DIR = REPO_ROOT / "deploy" / "backup"


@pytest.fixture(scope="module")
def policy() -> dict[str, Any]:
    return load_policy()


def settings() -> SimpleNamespace:
    return SimpleNamespace(
        backup_s3_bucket="aca-backups",
        backup_s3_prefix="aca",
        backup_s3_endpoint="https://acct.r2.cloudflarestorage.com",
        backup_s3_region="auto",
        backup_s3_access_key_id="AKIAEXAMPLE",
        backup_s3_secret_access_key="r2-secret",
    )


# ------------------------------------------------------------------- the policy


class TestCommittedTieredPolicy:
    def test_the_policy_is_committed_and_parses(self, policy: dict[str, Any]) -> None:
        assert POLICY_PATH.exists()
        assert policy["schema_version"] == 1

    def test_it_declares_seven_daily_four_weekly_twelve_monthly(
        self, policy: dict[str, Any]
    ) -> None:
        by_name = {tier["name"]: tier for tier in policy["tiers"]}
        assert by_name["daily"]["retain_days"] == 7
        assert by_name["weekly"]["retain_days"] == 28  # four weeks
        assert by_name["monthly"]["retain_days"] == 365  # twelve months

    def test_tiers_match_the_promotion_rule_that_writes_them(self, policy: dict[str, Any]) -> None:
        """The tier is a key segment chosen at write time. A policy naming a tier
        nothing writes would expire nothing; a written tier the policy omits would
        be kept forever."""
        from src.services.backup.models import RetentionTier

        assert {tier["name"] for tier in policy["tiers"]} == {
            str(member) for member in RetentionTier
        }

    def test_the_manifest_is_excluded_from_expiry(self, policy: dict[str, Any]) -> None:
        """An expired manifest reports `no_history`, which is indistinguishable from
        a backup that never ran — the freshness check would lie in the
        safe-looking direction."""
        assert any(item["prefix_suffix"] == "manifests/" for item in policy["exclusions"])


class TestRuleRendering:
    @pytest.mark.parametrize("dialect", DIALECTS)
    def test_both_provider_dialects_are_emitted(self, policy: dict[str, Any], dialect: str) -> None:
        rules = build_rules(policy, prefix="aca", dialect=dialect)
        assert rules
        assert all(rule["Status"] == "Enabled" for rule in rules)

    @pytest.mark.parametrize("dialect", DIALECTS)
    def test_rules_filter_by_prefix_and_never_by_tag(
        self, policy: dict[str, Any], dialect: str
    ) -> None:
        """A5 — R2 supports no tag filters, so a tag-based rule would silently apply
        to nothing there while appearing to work on AWS."""
        for rule in build_rules(policy, prefix="aca", dialect=dialect):
            assert "Prefix" in rule["Filter"]
            assert "Tag" not in rule["Filter"]
            assert "And" not in rule["Filter"]

    def test_expiry_policy_is_identical_across_dialects(self, policy: dict[str, Any]) -> None:
        def expiries(dialect: str) -> dict[str, int]:
            return {
                rule["Filter"]["Prefix"]: rule["Expiration"]["Days"]
                for rule in build_rules(policy, prefix="aca", dialect=dialect)
                if "Expiration" in rule
            }

        assert expiries("r2") == expiries("aws")

    def test_aws_additionally_aborts_incomplete_uploads(self, policy: dict[str, Any]) -> None:
        """AWS charges for incomplete multipart uploads indefinitely; R2 does not.
        An addition, not a change, so the expiry policy stays identical."""
        aws_ids = {rule["ID"] for rule in build_rules(policy, prefix="aca", dialect="aws")}
        r2_ids = {rule["ID"] for rule in build_rules(policy, prefix="aca", dialect="r2")}
        assert aws_ids - r2_ids == {"aca-backup-abort-incomplete-uploads"}

    def test_each_tier_gets_its_own_prefix_scoped_rule(self, policy: dict[str, Any]) -> None:
        prefixes = {
            rule["Filter"]["Prefix"] for rule in build_rules(policy, prefix="aca", dialect="r2")
        }
        assert prefixes == {"aca/daily/", "aca/weekly/", "aca/monthly/"}

    def test_the_prefix_is_honored(self, policy: dict[str, Any]) -> None:
        rules = build_rules(policy, prefix="other-prefix", dialect="r2")
        assert all(rule["Filter"]["Prefix"].startswith("other-prefix/") for rule in rules)

    def test_an_unknown_dialect_is_refused(self, policy: dict[str, Any]) -> None:
        with pytest.raises(ValueError, match="unknown dialect"):
            build_rules(policy, prefix="aca", dialect="azure")

    def test_a_rule_covering_the_manifest_prefix_is_refused(self) -> None:
        """The guard, exercised: a policy whose tier prefix swallows the manifest is
        rejected rather than rendered."""
        bad_policy = {
            "schema_version": 1,
            "tiers": [{"name": "everything", "prefix_suffix": "", "retain_days": 7}],
            "exclusions": [{"prefix_suffix": "manifests/", "reason": "x"}],
        }
        with pytest.raises(ValueError, match="excluded prefix"):
            render(bad_policy, prefix="aca", dialect="r2")


# ------------------------------------------------------------------- dry run


class TestDryRunByDefault:
    def test_without_apply_nothing_is_modified(self, capsys: Any) -> None:
        with (
            patch("src.config.settings.get_settings", settings),
            patch("scripts.backup_retention.apply_rules") as apply_rules,
        ):
            exit_code = main([])

        assert exit_code == 0
        apply_rules.assert_not_called()
        assert "DRY RUN" in capsys.readouterr().out

    def test_the_dry_run_reports_the_rules_it_would_set(self, capsys: Any) -> None:
        with patch("src.config.settings.get_settings", settings):
            main([])
        out = capsys.readouterr().out
        payload = json.loads(out[out.index("{") :])
        assert {rule["ID"] for rule in payload["Rules"]} == {
            "aca-backup-daily",
            "aca-backup-weekly",
            "aca-backup-monthly",
        }

    def test_apply_is_required_to_modify_the_target(self) -> None:
        with (
            patch("src.config.settings.get_settings", settings),
            patch("scripts.backup_retention.apply_rules") as apply_rules,
        ):
            exit_code = main(["--apply"])

        assert exit_code == 0
        apply_rules.assert_called_once()

    def test_apply_without_a_bucket_refuses(self) -> None:
        no_bucket = SimpleNamespace(**{**vars(settings()), "backup_s3_bucket": None})
        with (
            patch("src.config.settings.get_settings", lambda: no_bucket),
            patch("scripts.backup_retention.apply_rules") as apply_rules,
        ):
            exit_code = main(["--apply"])

        assert exit_code == 1
        apply_rules.assert_not_called()

    def test_the_applier_issues_no_delete_call(self) -> None:
        """It sets provider-side EXPIRY policy. The provider does the expiring, and
        keeps doing it while gx-10 is down. Nothing here deletes an object."""
        source = (REPO_ROOT / "scripts" / "backup_retention.py").read_text()
        code = "\n".join(line for line in source.splitlines() if not line.strip().startswith("#"))
        for forbidden in ("delete_object", "delete_objects", "delete_bucket"):
            assert forbidden not in code


# ------------------------------------------------------------- shipped units


def _directives(text: str) -> str:
    """Only the executable directives.

    The units carry substantial comments explaining WHY they are host-level rather
    than pg_cron, and those comments necessarily name the mechanisms being
    rejected. Asserting over raw text would force the explanation out of the file
    to satisfy the test, which is exactly backwards.
    """
    return "\n".join(
        line for line in text.splitlines() if line.strip() and not line.strip().startswith("#")
    )


@pytest.fixture(scope="module")
def service() -> str:
    return (DEPLOY_DIR / "aca-backup.service").read_text()


@pytest.fixture(scope="module")
def timer() -> str:
    return (DEPLOY_DIR / "aca-backup.timer").read_text()


class TestSchedulingUnits:
    def test_both_units_are_shipped(self) -> None:
        assert (DEPLOY_DIR / "aca-backup.service").exists()
        assert (DEPLOY_DIR / "aca-backup.timer").exists()

    def test_the_service_invokes_the_backup_command(self, service: str) -> None:
        assert "aca backup run" in service

    def test_the_timer_declares_a_schedule(self, timer: str) -> None:
        assert "OnCalendar=" in timer

    def test_the_service_runs_as_a_dedicated_unprivileged_user(self, service: str) -> None:
        assert "User=aca-backup" in service
        assert "User=root" not in service

    def test_configuration_comes_through_the_applications_own_settings_path(
        self, service: str
    ) -> None:
        """D13 — so the scheduled backup cannot drift from application config."""
        assert "Environment=PROFILE=" in service
        assert "EnvironmentFile=" in service

    def test_no_database_scheduler_or_superuser_is_required(self, service: str) -> None:
        """The whole reason this is a host timer: pg_cron needs an extension, a
        superuser, and `mc` inside the database image. None of that exists here."""
        lowered = _directives(service).lower()
        for forbidden in ("pg_cron", "cron.schedule", "superuser", "docker exec"):
            assert forbidden not in lowered

    def test_the_units_contain_no_literal_secret(self, service: str, timer: str) -> None:
        for text in (service, timer):
            for marker in ("SECRET_ACCESS_KEY=", "ACCESS_KEY_ID=", "PASSWORD=", "TOKEN="):
                assert marker not in _directives(text)

    def test_the_units_never_invoke_a_delete_operation(self, service: str, timer: str) -> None:
        """Hard Constraint 2 — there is no unattended deletion path, and this is
        where an unattended one would have to live."""
        for text in (service, timer):
            lowered = _directives(text).lower()
            for forbidden in ("rclone delete", "rclone purge", "--delete", "rm -rf", "aws s3 rm"):
                assert forbidden not in lowered

    def test_the_service_never_receives_the_decryption_identity(self, service: str) -> None:
        """Client-side encryption is pointless if the host that encrypts also holds
        the key that decrypts: compromising it would then yield the plaintext of
        every backup it ever produced."""
        directives = _directives(service)
        assert "BACKUP_AGE_IDENTITY_PATH" not in directives
        assert "backup_age_identity" not in directives.lower()

    def test_the_env_template_documents_the_same_exclusion(self) -> None:
        template = (DEPLOY_DIR / "aca-backup.env.example").read_text()
        settings_lines = [
            line
            for line in template.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert not any(line.startswith("BACKUP_AGE_IDENTITY_PATH") for line in settings_lines)
        assert any(line.startswith("BACKUP_AGE_RECIPIENT") for line in settings_lines)

    def test_the_env_template_ships_no_real_credential(self) -> None:
        template = (DEPLOY_DIR / "aca-backup.env.example").read_text()
        for line in template.splitlines():
            if "=" in line and not line.strip().startswith("#"):
                value = line.split("=", 1)[1]
                assert "<" in value or value in ("auto", "aca", "aca-backups") or not value

    def test_the_timer_catches_up_after_downtime(self, timer: str) -> None:
        """Without Persistent=true a host that was off at 03:00 skips the day
        silently, with the freshness check the only thing that would ever notice."""
        assert "Persistent=true" in timer

    def test_the_retention_policy_is_not_wired_into_the_timer(self) -> None:
        """Retention is provider-side. A scheduled process with delete rights over
        the backup target is the single most dangerous component such a system can
        have, so there deliberately is not one."""
        for name in ("aca-backup.service", "aca-backup.timer"):
            assert "backup_retention" not in _directives((DEPLOY_DIR / name).read_text())


def test_policy_yaml_is_valid_yaml() -> None:
    assert isinstance(yaml.safe_load(POLICY_PATH.read_text()), dict)
