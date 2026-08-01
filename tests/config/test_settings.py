from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.config.settings import Settings


def test_configured_source_key_secret_uses_dedicated_secret_without_repr_leak() -> None:
    settings = Settings(
        _env_file=None,
        configured_source_key_secret="dedicated-configured-source-secret",
        app_secret_key="application-secret-fallback-value",
        admin_api_key="admin-secret-fallback-value-long-enough",
    )

    assert settings.get_configured_source_key_secret() == "dedicated-configured-source-secret"
    assert "dedicated-configured-source-secret" not in repr(settings)


def test_configured_source_key_secret_forbids_authentication_secret_fallbacks() -> None:
    settings = Settings(
        _env_file=None,
        configured_source_key_secret=None,
        app_secret_key="application-secret-fallback-value",
        admin_api_key="admin-secret-fallback-value-long-enough",
    )

    with pytest.raises(RuntimeError, match="CONFIGURED_SOURCE_KEY_SECRET"):
        settings.get_configured_source_key_secret()


def test_configured_source_key_secret_fails_closed_without_signing_material() -> None:
    settings = Settings(
        _env_file=None,
        configured_source_key_secret=None,
        app_secret_key=None,
        admin_api_key=None,
    )

    with pytest.raises(RuntimeError, match="CONFIGURED_SOURCE_KEY_SECRET"):
        settings.get_configured_source_key_secret()


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_deployed_environment_requires_configured_source_key_secret(environment: str) -> None:
    with pytest.raises(ValidationError, match="CONFIGURED_SOURCE_KEY_SECRET"):
        Settings(
            _env_file=None,
            environment=environment,
            configured_source_key_secret=None,
        )


def test_configured_source_key_secret_rejects_short_dedicated_value() -> None:
    secret = "a-sensitive-short-secret"
    with pytest.raises(ValidationError, match="configured_source_key_secret") as exc_info:
        Settings(
            _env_file=None,
            configured_source_key_secret=secret,
        )

    assert secret not in str(exc_info.value)


def test_operation_cursor_signing_key_prefers_dedicated_secret_without_repr_leak() -> None:
    settings = Settings(
        _env_file=None,
        operation_cursor_signing_key="dedicated-operation-cursor-secret",
        app_secret_key="application-secret-fallback-value",
        admin_api_key="admin-secret-fallback-value-long-enough",
    )

    assert settings.get_operation_cursor_signing_key() == "dedicated-operation-cursor-secret"
    assert "dedicated-operation-cursor-secret" not in repr(settings)


@pytest.mark.parametrize(
    ("app_secret_key", "admin_api_key", "expected"),
    [
        (
            "application-secret-fallback-value",
            "admin-secret-fallback-value-long-enough",
            "application-secret-fallback-value",
        ),
        (
            None,
            "admin-secret-fallback-value-long-enough",
            "admin-secret-fallback-value-long-enough",
        ),
    ],
)
def test_operation_cursor_signing_key_uses_only_approved_auth_fallbacks(
    app_secret_key: str | None,
    admin_api_key: str | None,
    expected: str,
) -> None:
    settings = Settings(
        _env_file=None,
        operation_cursor_signing_key=None,
        app_secret_key=app_secret_key,
        admin_api_key=admin_api_key,
        configured_source_key_secret="configured-source-secret-must-not-be-used",
    )

    assert settings.get_operation_cursor_signing_key() == expected


def test_operation_cursor_signing_key_fails_closed_without_strong_material() -> None:
    settings = Settings(
        _env_file=None,
        operation_cursor_signing_key=None,
        app_secret_key="short",
        admin_api_key=None,
        configured_source_key_secret="configured-source-secret-must-not-be-used",
    )

    with pytest.raises(RuntimeError, match="OPERATION_CURSOR_SIGNING_KEY"):
        settings.get_operation_cursor_signing_key()


def test_operation_retention_defaults_are_finite_and_bounded() -> None:
    settings = Settings(_env_file=None)

    assert settings.job_retention_days == 30
    assert settings.failed_job_retention_days == 90
    assert settings.job_retention_interval_seconds == 3600
    assert settings.job_retention_batch_size == 100


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("job_retention_days", 0),
        ("job_retention_days", 3651),
        ("failed_job_retention_days", 0),
        ("failed_job_retention_days", 3651),
        ("job_retention_interval_seconds", 59),
        ("job_retention_interval_seconds", 86_401),
        ("job_retention_batch_size", 0),
        ("job_retention_batch_size", 1001),
    ],
)
def test_operation_retention_rejects_out_of_bounds_values(field: str, value: int) -> None:
    with pytest.raises(ValidationError, match=field):
        Settings(_env_file=None, **{field: value})


def test_failed_retention_cannot_be_shorter_than_completed_retention() -> None:
    with pytest.raises(ValidationError, match="failed_job_retention_days"):
        Settings(
            _env_file=None,
            job_retention_days=91,
            failed_job_retention_days=90,
        )


def test_content_reconciliation_policy_defaults_are_safe_and_bounded() -> None:
    settings = Settings(_env_file=None)

    assert settings.content_reconciliation_stale_seconds == 3600
    assert settings.content_reconciliation_max_retries == 3
    assert settings.content_reconciliation_batch_size == 50
    assert settings.content_reconciliation_lock_timeout_ms == 250
    assert settings.content_reconciliation_statement_timeout_ms == 5000
    assert settings.content_reconciliation_apply_enabled is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("content_reconciliation_stale_seconds", 59),
        ("content_reconciliation_stale_seconds", 604_801),
        ("content_reconciliation_max_retries", -1),
        ("content_reconciliation_max_retries", 21),
        ("content_reconciliation_batch_size", 0),
        ("content_reconciliation_batch_size", 101),
        ("content_reconciliation_lock_timeout_ms", 0),
        ("content_reconciliation_lock_timeout_ms", 5001),
        ("content_reconciliation_statement_timeout_ms", 99),
        ("content_reconciliation_statement_timeout_ms", 30_001),
    ],
)
def test_content_reconciliation_policy_rejects_out_of_bounds_values(
    field: str,
    value: int,
) -> None:
    with pytest.raises(ValidationError, match=field):
        Settings(_env_file=None, **{field: value})


def test_content_reconciliation_statement_timeout_cannot_be_shorter_than_lock_timeout() -> None:
    with pytest.raises(
        ValidationError,
        match="content_reconciliation_statement_timeout_ms",
    ):
        Settings(
            _env_file=None,
            content_reconciliation_lock_timeout_ms=5000,
            content_reconciliation_statement_timeout_ms=4999,
        )
