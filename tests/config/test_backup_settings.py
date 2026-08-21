"""Provider-neutral backup settings: resolution, deprecation mapping, masking.

Every test passes ``_env_file=None`` — settings tests that don't will silently pick
up the developer's real ``.env`` and pass or fail for reasons unrelated to the code
under test.

The point of this surface is that *no* backup, restore, health, or alerting path reads
a `railway_*` name. A freshness check that no longer depends on Railway must not keep
reading a setting named after it — so the legacy names map forward through the same
validator rather than being read directly.
"""

from __future__ import annotations

import logging

import pytest
from pydantic import SecretStr

from src.config.settings import Settings


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


# ----------------------------------------------------------------- target settings


class TestBackupTargetSettings:
    def test_target_fields_are_exposed(self) -> None:
        settings = _settings(
            backup_s3_endpoint="https://acct.r2.cloudflarestorage.com",
            backup_s3_bucket="aca-backups",
            backup_s3_region="auto",
            backup_s3_access_key_id="AKIAEXAMPLE",
            backup_s3_secret_access_key="s3cr3t",
        )
        assert settings.backup_s3_endpoint == "https://acct.r2.cloudflarestorage.com"
        assert settings.backup_s3_bucket == "aca-backups"
        assert settings.backup_s3_region == "auto"

    def test_credentials_are_secretstr(self) -> None:
        settings = _settings(
            backup_s3_access_key_id="AKIAEXAMPLE",
            backup_s3_secret_access_key="s3cr3t",
        )
        assert isinstance(settings.backup_s3_access_key_id, SecretStr)
        assert isinstance(settings.backup_s3_secret_access_key, SecretStr)
        assert settings.backup_s3_access_key_id.get_secret_value() == "AKIAEXAMPLE"
        assert settings.backup_s3_secret_access_key.get_secret_value() == "s3cr3t"

    def test_credentials_do_not_leak_through_repr(self) -> None:
        settings = _settings(backup_s3_secret_access_key="hunter2-hunter2")
        assert "hunter2-hunter2" not in repr(settings.backup_s3_secret_access_key)
        assert "hunter2-hunter2" not in str(settings.backup_s3_secret_access_key)

    def test_prefix_defaults_to_aca(self) -> None:
        assert _settings().backup_s3_prefix == "aca"

    def test_target_defaults_are_unset_not_railway_shaped(self) -> None:
        """Rule 4 — adding these settings must not change behavior for existing
        deployments, so nothing defaults to a live endpoint or bucket."""
        settings = _settings()
        assert settings.backup_s3_endpoint is None
        assert settings.backup_s3_bucket is None
        assert settings.backup_s3_access_key_id is None
        assert settings.backup_s3_secret_access_key is None

    def test_r2_endpoint_needs_no_protocol_change(self) -> None:
        """R2, AWS S3 and MinIO differ only in the value of these fields."""
        r2 = _settings(
            backup_s3_endpoint="https://acct.r2.cloudflarestorage.com",
            backup_s3_region="auto",
            backup_s3_bucket="b",
        )
        aws = _settings(backup_s3_region="us-east-1", backup_s3_bucket="b")
        assert r2.backup_s3_endpoint is not None
        assert aws.backup_s3_endpoint is None
        # Same declared type, same code path — no R2-specific branch anywhere.
        assert type(r2.backup_s3_bucket) is type(aws.backup_s3_bucket)


# ------------------------------------------------------------- deprecation mapping


class TestLegacyTargetMapping:
    def test_legacy_only_maps_forward(self) -> None:
        settings = _settings(
            railway_minio_endpoint="https://minio.railway.internal",
            minio_root_user="minio-user",
            minio_root_password="minio-pass",
            railway_backup_bucket="legacy-backups",
        )
        assert settings.backup_s3_endpoint == "https://minio.railway.internal"
        assert settings.backup_s3_bucket == "legacy-backups"
        assert settings.backup_s3_access_key_id is not None
        assert settings.backup_s3_access_key_id.get_secret_value() == "minio-user"
        assert settings.backup_s3_secret_access_key is not None
        assert settings.backup_s3_secret_access_key.get_secret_value() == "minio-pass"

    def test_new_settings_win_over_deprecated(self) -> None:
        settings = _settings(
            backup_s3_endpoint="https://new.example.com",
            railway_minio_endpoint="https://old.example.com",
        )
        assert settings.backup_s3_endpoint == "https://new.example.com"

    def test_new_credentials_win_over_deprecated(self) -> None:
        settings = _settings(
            backup_s3_access_key_id="new-key",
            minio_root_user="old-key",
        )
        assert settings.backup_s3_access_key_id is not None
        assert settings.backup_s3_access_key_id.get_secret_value() == "new-key"

    def test_exactly_one_deprecation_warning_is_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="src.config.settings"):
            _settings(
                railway_minio_endpoint="https://minio.railway.internal",
                minio_root_user="u",
                minio_root_password="p",
                railway_backup_bucket="legacy-backups",
            )
        backup_warnings = [
            record
            for record in caplog.records
            if "backup_s3_" in record.getMessage() and "Deprecated" in record.getMessage()
        ]
        assert len(backup_warnings) == 1
        assert "backup_s3_endpoint" in backup_warnings[0].getMessage()

    def test_no_warning_when_no_legacy_setting_present(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="src.config.settings"):
            _settings(backup_s3_endpoint="https://new.example.com")
        assert not [r for r in caplog.records if "backup_s3_" in r.getMessage()]


# --------------------------------------------------- encryption + monitoring group


class TestBackupEncryptionSettings:
    def test_encryption_fields_are_exposed(self) -> None:
        settings = _settings(
            backup_age_recipient="age1qqqqexamplerecipient",
            backup_age_identity_path="/etc/aca/backup-identity.txt",
        )
        assert settings.backup_age_recipient == "age1qqqqexamplerecipient"
        assert settings.backup_age_identity_path == "/etc/aca/backup-identity.txt"

    def test_encryption_fields_default_unset(self) -> None:
        settings = _settings()
        assert settings.backup_age_recipient is None
        assert settings.backup_age_identity_path is None

    def test_recipient_is_a_public_key_and_not_a_secret(self) -> None:
        """The recipient travels to the gx-10 unit; the identity never does. Typing
        the recipient as SecretStr would mask the one value operators must be able
        to read back to confirm the right key is in use."""
        settings = _settings(backup_age_recipient="age1qqqqexamplerecipient")
        assert not isinstance(settings.backup_age_recipient, SecretStr)


class TestBackupMonitoringSettings:
    def test_monitoring_fields_are_exposed(self) -> None:
        settings = _settings(backup_monitoring_enabled=False, backup_staleness_hours=12)
        assert settings.backup_monitoring_enabled is False
        assert settings.backup_staleness_hours == 12

    def test_staleness_default_matches_the_legacy_setting(self) -> None:
        settings = _settings()
        assert settings.backup_staleness_hours == settings.railway_backup_staleness_hours == 48

    def test_monitoring_enabled_default_matches_the_legacy_setting(self) -> None:
        settings = _settings()
        assert settings.backup_monitoring_enabled == settings.railway_backup_enabled is True

    def test_legacy_monitoring_settings_map_forward(self) -> None:
        settings = _settings(railway_backup_enabled=False, railway_backup_staleness_hours=6)
        assert settings.backup_monitoring_enabled is False
        assert settings.backup_staleness_hours == 6

    def test_new_monitoring_settings_win_over_legacy(self) -> None:
        settings = _settings(
            backup_monitoring_enabled=True,
            backup_staleness_hours=9,
            railway_backup_enabled=False,
            railway_backup_staleness_hours=6,
        )
        assert settings.backup_monitoring_enabled is True
        assert settings.backup_staleness_hours == 9

    def test_monitoring_maps_through_the_same_validator_as_the_target(self) -> None:
        """One validator, so a config setting only legacy names resolves every
        provider-neutral backup field in one pass."""
        settings = _settings(
            railway_minio_endpoint="https://minio.railway.internal",
            railway_backup_enabled=False,
            railway_backup_staleness_hours=6,
        )
        assert settings.backup_s3_endpoint == "https://minio.railway.internal"
        assert settings.backup_monitoring_enabled is False
        assert settings.backup_staleness_hours == 6

    def test_staleness_hours_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            _settings(backup_staleness_hours=0)
