from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest


def _backup():
    from src.services.backup import gx10

    return gx10


ACTIVE_RECIPIENT = "age1" + "a" * 58
OLD_RECIPIENT = "age1" + "b" * 58


def _context(backup):
    return backup.MaintenanceCorrelation(operation_id="501", trace_id="5" * 32)


def _components(backup):
    return {
        component: (lambda component=component: f"plain:{component}".encode())
        for component in backup.BackupComponent
    }


def _encrypt(payload: bytes, recipient: str) -> bytes:
    return b"age-encrypted:" + recipient.encode() + b":" + payload


def test_component_inventory_includes_every_required_state_store() -> None:
    backup = _backup()

    assert {str(component) for component in backup.BackupComponent} == {
        "application_postgresql",
        "neo4j",
        "langfuse_postgresql",
        "clickhouse",
        "minio",
        "configuration_metadata",
    }


@pytest.mark.parametrize("recipient", [None, "", "not-age", "age1short"])
def test_missing_or_invalid_age_recipient_fails_before_any_component_runs(
    recipient: str | None,
) -> None:
    backup = _backup()
    produced: list[str] = []

    def producer() -> bytes:
        produced.append("called")
        return b"plaintext"

    controller = backup.GX10BackupController(
        producers={backup.BackupComponent.APPLICATION_POSTGRESQL: producer},
        encrypt=_encrypt,
        store=lambda _name, _payload: None,
    )

    with pytest.raises(backup.EncryptionMaterialError):
        controller.run(
            recipient_catalog=backup.AgeRecipientCatalog(active=recipient, retained=()),
            correlation=_context(backup),
            quota=backup.BackupQuota(limit_bytes=10_000, used_bytes=0),
            started_at=datetime(2026, 8, 29, tzinfo=UTC),
        )

    assert produced == []


def test_each_component_is_encrypted_before_storage_and_checksummed() -> None:
    backup = _backup()
    stored: dict[str, bytes] = {}
    controller = backup.GX10BackupController(
        producers=_components(backup),
        encrypt=_encrypt,
        store=lambda name, payload: stored.__setitem__(name, payload),
    )

    manifest = controller.run(
        recipient_catalog=backup.AgeRecipientCatalog(
            active=ACTIVE_RECIPIENT, retained=(OLD_RECIPIENT,)
        ),
        correlation=_context(backup),
        quota=backup.BackupQuota(limit_bytes=1_000_000, used_bytes=0),
        started_at=datetime(2026, 8, 29, tzinfo=UTC),
    )

    assert manifest.outcome == "succeeded"
    assert len(manifest.components) == 6
    for result in manifest.components:
        payload = stored[result.artifact_name]
        assert payload.startswith(b"age-encrypted:")
        assert b"plain:" in payload
        assert result.outcome == "succeeded"
        assert result.stage == "backup"
        assert result.operation_id == "501"
        assert result.trace_id == "5" * 32
        assert result.checksum_sha256 == hashlib.sha256(payload).hexdigest()
        assert result.encryption_recipient == ACTIVE_RECIPIENT


def test_plaintext_is_never_sent_to_storage() -> None:
    backup = _backup()
    seen: list[bytes] = []
    controller = backup.GX10BackupController(
        producers=_components(backup),
        encrypt=_encrypt,
        store=lambda _name, payload: seen.append(payload),
    )

    controller.run(
        recipient_catalog=backup.AgeRecipientCatalog(active=ACTIVE_RECIPIENT, retained=()),
        correlation=_context(backup),
        quota=backup.BackupQuota(limit_bytes=1_000_000, used_bytes=0),
        started_at=datetime(2026, 8, 29, tzinfo=UTC),
    )

    assert seen
    assert all(payload.startswith(b"age-encrypted:") for payload in seen)


def test_one_component_failure_makes_aggregate_partial_not_success() -> None:
    backup = _backup()
    producers = _components(backup)
    producers[backup.BackupComponent.NEO4J] = lambda: (_ for _ in ()).throw(
        RuntimeError("neo4j unavailable")
    )
    controller = backup.GX10BackupController(
        producers=producers,
        encrypt=_encrypt,
        store=lambda _name, _payload: None,
    )

    manifest = controller.run(
        recipient_catalog=backup.AgeRecipientCatalog(active=ACTIVE_RECIPIENT, retained=()),
        correlation=_context(backup),
        quota=backup.BackupQuota(limit_bytes=1_000_000, used_bytes=0),
        started_at=datetime(2026, 8, 29, tzinfo=UTC),
    )

    assert manifest.outcome == "partial"
    neo4j = next(r for r in manifest.components if r.component is backup.BackupComponent.NEO4J)
    assert neo4j.outcome == "permanent_failure"
    assert neo4j.diagnostic_code == "component_backup_failed"
    assert "unavailable" not in manifest.to_json()


def test_all_component_failures_make_aggregate_failed() -> None:
    backup = _backup()
    controller = backup.GX10BackupController(
        producers={
            component: (lambda: (_ for _ in ()).throw(RuntimeError("nope")))
            for component in backup.BackupComponent
        },
        encrypt=_encrypt,
        store=lambda _name, _payload: None,
    )

    manifest = controller.run(
        recipient_catalog=backup.AgeRecipientCatalog(active=ACTIVE_RECIPIENT, retained=()),
        correlation=_context(backup),
        quota=backup.BackupQuota(limit_bytes=1_000_000, used_bytes=0),
        started_at=datetime(2026, 8, 29, tzinfo=UTC),
    )

    assert manifest.outcome == "permanent_failure"


def test_quota_exhaustion_is_a_component_failure_and_never_calls_store() -> None:
    backup = _backup()
    stored: list[str] = []
    controller = backup.GX10BackupController(
        producers={backup.BackupComponent.APPLICATION_POSTGRESQL: lambda: b"large-payload"},
        encrypt=_encrypt,
        store=lambda name, _payload: stored.append(name),
    )

    manifest = controller.run(
        recipient_catalog=backup.AgeRecipientCatalog(active=ACTIVE_RECIPIENT, retained=()),
        correlation=_context(backup),
        quota=backup.BackupQuota(limit_bytes=10, used_bytes=9),
        started_at=datetime(2026, 8, 29, tzinfo=UTC),
    )

    assert stored == []
    assert manifest.outcome == "permanent_failure"
    assert manifest.components[0].diagnostic_code == "backup_quota_exhausted"


def test_backup_manifest_round_trip_preserves_correlated_component_evidence() -> None:
    backup = _backup()
    controller = backup.GX10BackupController(
        producers=_components(backup),
        encrypt=_encrypt,
        store=lambda _name, _payload: None,
    )
    original = controller.run(
        recipient_catalog=backup.AgeRecipientCatalog(active=ACTIVE_RECIPIENT, retained=()),
        correlation=_context(backup),
        quota=backup.BackupQuota(limit_bytes=1_000_000, used_bytes=0),
        started_at=datetime(2026, 8, 29, tzinfo=UTC),
    )

    loaded = backup.BackupManifest.from_json(original.to_json())

    assert loaded == original


def test_restore_accepts_rotated_recipient_retained_for_restore_window(tmp_path: Path) -> None:
    backup = _backup()
    artifact = backup.EncryptedArtifact(
        component=backup.BackupComponent.APPLICATION_POSTGRESQL,
        name="postgres.age",
        payload=b"ciphertext",
        checksum_sha256=hashlib.sha256(b"ciphertext").hexdigest(),
        encryption_recipient=OLD_RECIPIENT,
        completed_at=datetime(2026, 8, 29, tzinfo=UTC),
    )
    target = tmp_path / "isolated" / "postgres"
    source = tmp_path / "production" / "postgres"
    source.mkdir(parents=True)
    source_sentinel = source / "sentinel"
    source_sentinel.write_text("production")
    drill = backup.GX10RestoreDrill(
        decrypt=lambda payload, _recipient: b"plain:" + payload,
        restore={backup.BackupComponent.APPLICATION_POSTGRESQL: lambda _payload, path: path.mkdir(parents=True)},
        validate={backup.BackupComponent.APPLICATION_POSTGRESQL: lambda _path: True},
    )

    result = drill.restore_component(
        artifact=artifact,
        target=target,
        isolated_root=tmp_path / "isolated",
        production_sources=(source,),
        available_recipients=(ACTIVE_RECIPIENT, OLD_RECIPIENT),
        correlation=_context(backup),
        restore_started_at=datetime(2026, 8, 30, tzinfo=UTC),
    )

    assert result.outcome == "succeeded"
    assert source_sentinel.read_text() == "production"
    assert target.is_dir()


def test_restore_rejects_missing_rotated_recipient_before_decryption(tmp_path: Path) -> None:
    backup = _backup()
    decrypted: list[bytes] = []
    artifact = backup.EncryptedArtifact(
        component=backup.BackupComponent.NEO4J,
        name="neo4j.age",
        payload=b"ciphertext",
        checksum_sha256=hashlib.sha256(b"ciphertext").hexdigest(),
        encryption_recipient=OLD_RECIPIENT,
        completed_at=datetime(2026, 8, 29, tzinfo=UTC),
    )
    drill = backup.GX10RestoreDrill(
        decrypt=lambda payload, _recipient: decrypted.append(payload) or b"plain",
        restore={backup.BackupComponent.NEO4J: lambda _payload, _path: None},
        validate={backup.BackupComponent.NEO4J: lambda _path: True},
    )

    result = drill.restore_component(
        artifact=artifact,
        target=tmp_path / "isolated" / "neo4j",
        isolated_root=tmp_path / "isolated",
        production_sources=(tmp_path / "production" / "neo4j",),
        available_recipients=(ACTIVE_RECIPIENT,),
        correlation=_context(backup),
        restore_started_at=datetime(2026, 8, 30, tzinfo=UTC),
    )

    assert result.outcome == "permanent_failure"
    assert result.diagnostic_code == "restore_recipient_unavailable"
    assert decrypted == []


def test_restore_rejects_checksum_mismatch_before_decryption(tmp_path: Path) -> None:
    backup = _backup()
    decrypted: list[bytes] = []
    artifact = backup.EncryptedArtifact(
        component=backup.BackupComponent.MINIO,
        name="minio.age",
        payload=b"corrupt",
        checksum_sha256="0" * 64,
        encryption_recipient=ACTIVE_RECIPIENT,
        completed_at=datetime(2026, 8, 29, tzinfo=UTC),
    )
    drill = backup.GX10RestoreDrill(
        decrypt=lambda payload, _recipient: decrypted.append(payload) or b"plain",
        restore={backup.BackupComponent.MINIO: lambda _payload, _path: None},
        validate={backup.BackupComponent.MINIO: lambda _path: True},
    )

    result = drill.restore_component(
        artifact=artifact,
        target=tmp_path / "isolated" / "minio",
        isolated_root=tmp_path / "isolated",
        production_sources=(tmp_path / "production" / "minio",),
        available_recipients=(ACTIVE_RECIPIENT,),
        correlation=_context(backup),
        restore_started_at=datetime(2026, 8, 30, tzinfo=UTC),
    )

    assert result.outcome == "permanent_failure"
    assert result.diagnostic_code == "artifact_checksum_mismatch"
    assert decrypted == []


@pytest.mark.parametrize("target_kind", ["source", "inside_source", "outside_isolated"])
def test_restore_refuses_nonisolated_or_source_targets(
    tmp_path: Path,
    target_kind: str,
) -> None:
    backup = _backup()
    source = tmp_path / "production" / "postgres"
    isolated = tmp_path / "isolated"
    source.mkdir(parents=True)
    targets = {
        "source": source,
        "inside_source": source / "restore",
        "outside_isolated": tmp_path / "other" / "restore",
    }

    with pytest.raises(backup.RestoreIsolationError):
        backup.validate_restore_target(
            target=targets[target_kind],
            isolated_root=isolated,
            production_sources=(source,),
        )


def test_restore_validation_failure_is_component_specific_and_source_untouched(
    tmp_path: Path,
) -> None:
    backup = _backup()
    source = tmp_path / "production" / "clickhouse"
    source.mkdir(parents=True)
    sentinel = source / "sentinel"
    sentinel.write_text("keep")
    artifact = backup.EncryptedArtifact(
        component=backup.BackupComponent.CLICKHOUSE,
        name="clickhouse.age",
        payload=b"ciphertext",
        checksum_sha256=hashlib.sha256(b"ciphertext").hexdigest(),
        encryption_recipient=ACTIVE_RECIPIENT,
        completed_at=datetime(2026, 8, 29, tzinfo=UTC),
    )
    drill = backup.GX10RestoreDrill(
        decrypt=lambda payload, _recipient: payload,
        restore={backup.BackupComponent.CLICKHOUSE: lambda _payload, path: path.mkdir(parents=True)},
        validate={backup.BackupComponent.CLICKHOUSE: lambda _path: False},
    )

    result = drill.restore_component(
        artifact=artifact,
        target=tmp_path / "isolated" / "clickhouse",
        isolated_root=tmp_path / "isolated",
        production_sources=(source,),
        available_recipients=(ACTIVE_RECIPIENT,),
        correlation=_context(backup),
        restore_started_at=datetime(2026, 8, 30, tzinfo=UTC),
    )

    assert result.outcome == "permanent_failure"
    assert result.diagnostic_code == "component_restore_validation_failed"
    assert result.component is backup.BackupComponent.CLICKHOUSE
    assert sentinel.read_text() == "keep"


@pytest.mark.parametrize(
    ("backup_age", "component_rto", "full_stack_rto", "accepted", "breaches"),
    [
        (timedelta(hours=24), timedelta(hours=2), timedelta(hours=4), True, ()),
        (
            timedelta(hours=24, seconds=1),
            timedelta(hours=2),
            timedelta(hours=4),
            False,
            ("application_rpo",),
        ),
        (
            timedelta(hours=24),
            timedelta(hours=2, seconds=1),
            timedelta(hours=4),
            False,
            ("component_rto",),
        ),
        (
            timedelta(hours=24),
            timedelta(hours=2),
            timedelta(hours=4, seconds=1),
            False,
            ("full_stack_rto",),
        ),
    ],
)
def test_recovery_objectives_use_inclusive_24h_2h_4h_limits(
    backup_age: timedelta,
    component_rto: timedelta,
    full_stack_rto: timedelta,
    accepted: bool,
    breaches: tuple[str, ...],
) -> None:
    backup = _backup()
    failure = datetime(2026, 8, 30, 12, tzinfo=UTC)
    started = failure

    result = backup.evaluate_recovery_objectives(
        application_backup_completed_at=failure - backup_age,
        declared_failure_at=failure,
        restore_started_at=started,
        component_completed_at=started + component_rto,
        synthetic_operation_passed_at=started + full_stack_rto,
    )

    assert result.accepted is accepted
    assert result.breaches == breaches
    assert result.application_rpo_seconds == int(backup_age.total_seconds())
    assert result.component_rto_seconds == int(component_rto.total_seconds())
    assert result.full_stack_rto_seconds == int(full_stack_rto.total_seconds())


def test_application_restore_requires_operation_rows_and_trace_metadata(tmp_path: Path) -> None:
    backup = _backup()
    metadata = backup.RestoreValidation(
        application_operation_rows=False,
        langfuse_trace_metadata=True,
    )

    assert backup.required_restore_metadata_valid(metadata) is False

    metadata = backup.RestoreValidation(
        application_operation_rows=True,
        langfuse_trace_metadata=False,
    )
    assert backup.required_restore_metadata_valid(metadata) is False

    metadata = backup.RestoreValidation(
        application_operation_rows=True,
        langfuse_trace_metadata=True,
    )
    assert backup.required_restore_metadata_valid(metadata) is True
