"""Masking of identifier-suffixed credential names.

`SECRET_KEY_PATTERNS` matched `*_KEY`, `*_SECRET`, `*_PASSWORD`, `*_TOKEN` and
`*_CREDENTIAL*`. An S3 access key ID ends in `_ACCESS_KEY_ID`, which matches none of
them — so the new backup credentials would have been *less* protected in diagnostics
than the MinIO ones they replace. That is the gap these tests close.
"""

from __future__ import annotations

import pytest

from src.config.secrets import is_secret_key


@pytest.mark.parametrize(
    "key",
    [
        "BACKUP_S3_ACCESS_KEY_ID",
        "backup_s3_access_key_id",
        "AWS_ACCESS_KEY_ID",
        "SUPABASE_ACCESS_KEY_ID",
        "MINIO_ROOT_PASSWORD",
        "BACKUP_S3_SECRET_ACCESS_KEY",
        "ANTHROPIC_API_KEY",
        "WORKFLOW_ALERT_WEBHOOK_SECRET",
        "GITHUB_TOKEN",
        "SOME_CREDENTIALS_BLOB",
    ],
)
def test_credential_names_are_recognised(key: str) -> None:
    assert is_secret_key(key) is True


@pytest.mark.parametrize(
    "key",
    [
        "BACKUP_S3_ENDPOINT",
        "BACKUP_S3_BUCKET",
        "BACKUP_S3_REGION",
        "BACKUP_S3_PREFIX",
        "BACKUP_AGE_RECIPIENT",
        "BACKUP_STALENESS_HOURS",
        "DATABASE_PROVIDER",
        "ENVIRONMENT",
    ],
)
def test_non_credential_names_are_not_masked(key: str) -> None:
    """Over-matching is its own failure: masking the endpoint or the age *recipient*
    hides the values an operator needs to confirm the right target and key are in use."""
    assert is_secret_key(key) is False


def test_identity_path_is_not_itself_a_secret() -> None:
    """The path is not the key. Masking it makes a misconfigured path undiagnosable."""
    assert is_secret_key("BACKUP_AGE_IDENTITY_PATH") is False
