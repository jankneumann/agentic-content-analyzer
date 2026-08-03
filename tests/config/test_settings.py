from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config.settings import Settings


def test_obsidian_worker_policy_defaults_fail_closed() -> None:
    settings = Settings(_env_file=None)

    assert settings.get_obsidian_allowed_roots() == ()
    assert settings.obsidian_compatible_worker is False


def test_obsidian_allowed_roots_are_deployment_owned_absolute_paths(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    settings = Settings(
        _env_file=None,
        obsidian_allowed_roots=f" {first} , {second} ",
        obsidian_compatible_worker=True,
    )

    assert settings.get_obsidian_allowed_roots() == (first, second)
    assert settings.obsidian_compatible_worker is True


@pytest.mark.parametrize(
    "value",
    [
        "relative/path",
        "/",
        "/approved,,/also-approved",
        "/approved,/approved",
        "/approved/../private",
        "/approved\\private",
        "/approved\x00/private",
    ],
)
def test_obsidian_allowed_roots_reject_ambiguous_or_non_absolute_policy(value: str) -> None:
    with pytest.raises(ValidationError, match="obsidian_allowed_roots"):
        Settings(_env_file=None, obsidian_allowed_roots=value)


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


def test_workflow_alerting_defaults_off_with_finite_delivery_policy() -> None:
    settings = Settings(_env_file=None)

    assert settings.workflow_alert_sink == "noop"
    assert settings.workflow_alert_webhook_endpoint is None
    assert settings.workflow_alert_webhook_secret is None
    assert settings.workflow_alert_diagnostic_origin is None
    assert settings.get_workflow_alert_allowed_hosts() == ()
    assert settings.workflow_alert_timeout_seconds == 10
    assert settings.workflow_alert_lease_seconds == 60
    assert settings.workflow_alert_max_attempts == 5
    assert settings.workflow_alert_base_backoff_seconds == 30
    assert settings.workflow_alert_max_backoff_seconds == 3600
    assert settings.workflow_alert_max_retry_after_seconds == 3600
    assert settings.workflow_alert_delivery_max_age_seconds == 604_800
    assert settings.workflow_alert_retention_days == 30
    assert settings.workflow_alert_exhausted_retention_days == 90
    assert settings.workflow_alert_batch_size == 50


def test_workflow_alert_webhook_requires_trusted_complete_configuration() -> None:
    with pytest.raises(ValidationError, match="WORKFLOW_ALERT_WEBHOOK_ENDPOINT"):
        Settings(
            _env_file=None,
            environment="production",
            configured_source_key_secret="configured-source-secret-for-alert-tests",
            workflow_alert_sink="webhook",
        )


def test_workflow_alert_webhook_accepts_safe_production_policy() -> None:
    secret = "workflow-alert-hmac-secret-must-stay-private"
    settings = Settings(
        _env_file=None,
        environment="production",
        configured_source_key_secret="configured-source-secret-for-alert-tests",
        workflow_alert_sink="webhook",
        workflow_alert_webhook_endpoint="https://alerts.example.com/v1/workflows",
        workflow_alert_webhook_secret=secret,
        workflow_alert_diagnostic_origin="https://ops.example.com",
        workflow_alert_allowed_hosts="alerts.example.com",
    )

    assert settings.workflow_alert_webhook_endpoint == "https://alerts.example.com/v1/workflows"
    assert settings.workflow_alert_diagnostic_origin == "https://ops.example.com"
    assert settings.get_workflow_alert_allowed_hosts() == ("alerts.example.com",)
    assert settings.workflow_alert_webhook_secret is not None
    assert settings.workflow_alert_webhook_secret.get_secret_value() == secret
    assert secret not in repr(settings)
    assert secret not in str(settings.model_dump())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("workflow_alert_timeout_seconds", 0),
        ("workflow_alert_timeout_seconds", 31),
        ("workflow_alert_lease_seconds", 9),
        ("workflow_alert_lease_seconds", 901),
        ("workflow_alert_max_attempts", 0),
        ("workflow_alert_max_attempts", 21),
        ("workflow_alert_base_backoff_seconds", 0),
        ("workflow_alert_base_backoff_seconds", 3601),
        ("workflow_alert_max_backoff_seconds", 0),
        ("workflow_alert_max_backoff_seconds", 86_401),
        ("workflow_alert_max_retry_after_seconds", 0),
        ("workflow_alert_max_retry_after_seconds", 86_401),
        ("workflow_alert_delivery_max_age_seconds", 59),
        ("workflow_alert_delivery_max_age_seconds", 604_801),
        ("workflow_alert_retention_days", 0),
        ("workflow_alert_retention_days", 3651),
        ("workflow_alert_exhausted_retention_days", 0),
        ("workflow_alert_exhausted_retention_days", 3651),
        ("workflow_alert_batch_size", 0),
        ("workflow_alert_batch_size", 501),
    ],
)
def test_workflow_alert_policy_rejects_out_of_bounds_values(field: str, value: int) -> None:
    with pytest.raises(ValidationError, match=field):
        Settings(_env_file=None, **{field: value})


def test_workflow_alert_policy_rejects_inverted_backoff_and_retention() -> None:
    with pytest.raises(ValidationError, match="workflow_alert_max_backoff_seconds"):
        Settings(
            _env_file=None,
            workflow_alert_base_backoff_seconds=120,
            workflow_alert_max_backoff_seconds=60,
        )

    with pytest.raises(ValidationError, match="workflow_alert_exhausted_retention_days"):
        Settings(
            _env_file=None,
            workflow_alert_retention_days=91,
            workflow_alert_exhausted_retention_days=90,
        )


def test_workflow_alert_lease_includes_five_second_transport_safety_margin() -> None:
    with pytest.raises(ValidationError, match="five-second transport safety margin"):
        Settings(
            _env_file=None,
            workflow_alert_timeout_seconds=10,
            workflow_alert_lease_seconds=14,
        )

    settings = Settings(
        _env_file=None,
        workflow_alert_timeout_seconds=10,
        workflow_alert_lease_seconds=15,
    )
    assert settings.workflow_alert_lease_seconds == 15


@pytest.mark.parametrize(
    ("endpoint", "origin", "allowed_hosts", "expected"),
    [
        (
            "http://alerts.example.com/hook",
            "https://ops.example.com",
            "alerts.example.com",
            "HTTPS",
        ),
        (
            "https://user:password@alerts.example.com/hook",
            "https://ops.example.com",
            "alerts.example.com",
            "credentials",
        ),
        (
            "https://alerts.example.com/hook?token=secret",
            "https://ops.example.com",
            "alerts.example.com",
            "query or fragment",
        ),
        (
            "https://alerts.example.com:invalid/hook",
            "https://ops.example.com",
            "alerts.example.com",
            "port",
        ),
        (
            "https://alerts.example.com/hook",
            "https://ops.example.com/base",
            "alerts.example.com",
            "origin",
        ),
        (
            "https://alerts.example.com/hook",
            "https://ops.example.com",
            "other.example.com",
            "allowlist",
        ),
        (
            "https://127.0.0.1/hook",
            "https://ops.example.com",
            "127.0.0.1",
            "public",
        ),
        (
            "https://169.254.169.254/latest/meta-data",
            "https://ops.example.com",
            "169.254.169.254",
            "public",
        ),
    ],
)
def test_workflow_alert_webhook_rejects_unsafe_production_configuration(
    endpoint: str,
    origin: str,
    allowed_hosts: str,
    expected: str,
) -> None:
    with pytest.raises(ValidationError, match=expected):
        Settings(
            _env_file=None,
            environment="production",
            configured_source_key_secret="configured-source-secret-for-alert-tests",
            workflow_alert_sink="webhook",
            workflow_alert_webhook_endpoint=endpoint,
            workflow_alert_diagnostic_origin=origin,
            workflow_alert_allowed_hosts=allowed_hosts,
        )


def test_workflow_alert_webhook_allows_http_loopback_sink_with_https_diagnostic_origin() -> None:
    settings = Settings(
        _env_file=None,
        environment="development",
        workflow_alert_sink="webhook",
        workflow_alert_webhook_endpoint="http://127.0.0.1:9080/hook",
        workflow_alert_diagnostic_origin="https://127.0.0.1:8000",
        workflow_alert_allowed_hosts="127.0.0.1",
    )

    assert settings.get_workflow_alert_allowed_hosts() == ("127.0.0.1",)


def test_workflow_alert_diagnostic_origin_requires_https_in_development() -> None:
    with pytest.raises(ValidationError, match="diagnostic origin must use HTTPS"):
        Settings(
            _env_file=None,
            environment="development",
            workflow_alert_sink="webhook",
            workflow_alert_webhook_endpoint="http://127.0.0.1:9080/hook",
            workflow_alert_diagnostic_origin="http://127.0.0.1:8000",
            workflow_alert_allowed_hosts="127.0.0.1",
        )


def test_workflow_alert_host_allowlist_is_normalized_and_rejects_wildcards() -> None:
    settings = Settings(
        _env_file=None,
        workflow_alert_allowed_hosts=" Alerts.Example.COM,backup.example.com,alerts.example.com ",
    )
    assert settings.get_workflow_alert_allowed_hosts() == (
        "alerts.example.com",
        "backup.example.com",
    )

    with pytest.raises(ValidationError, match="workflow_alert_allowed_hosts"):
        Settings(_env_file=None, workflow_alert_allowed_hosts="*.example.com")
