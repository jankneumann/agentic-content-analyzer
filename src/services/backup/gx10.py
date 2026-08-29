"""Encrypted GX-10 component backup and isolated restore policy."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, cast

from src.clients.operational_observability import operational_stage
from src.config.bao_secrets import get_bao_secret

_AGE_RECIPIENT = re.compile(r"^age1[0-9a-z]{20,100}$")
_AGE_ENVELOPE = b"age-encryption.org/v1\n"


class BackupComponent(StrEnum):
    APPLICATION_POSTGRESQL = "application_postgresql"
    NEO4J = "neo4j"
    LANGFUSE_POSTGRESQL = "langfuse_postgresql"
    CLICKHOUSE = "clickhouse"
    MINIO = "minio"
    CONFIGURATION_METADATA = "configuration_metadata"


@dataclass(frozen=True, slots=True)
class BackupSchedule:
    """Daily schedule aligned with the declared 24-hour application RPO."""

    maximum_interval: timedelta = timedelta(hours=24)

    def __post_init__(self) -> None:
        if self.maximum_interval <= timedelta(0):
            raise ValueError("maximum backup interval must be positive")

    def is_due(self, *, last_completed_at: datetime | None, now: datetime) -> bool:
        return last_completed_at is None or now - last_completed_at >= self.maximum_interval


@dataclass(frozen=True, slots=True)
class RetainedBackupArtifact:
    component: BackupComponent
    name: str
    completed_at: datetime
    outcome: Literal["succeeded", "permanent_failure"]


def select_expired_backups(
    artifacts: Sequence[RetainedBackupArtifact],
    *,
    now: datetime,
    retention_days: int,
) -> tuple[RetainedBackupArtifact, ...]:
    """Select old successes only when a newer successful backup remains."""

    if retention_days <= 0:
        raise ValueError("retention days must be positive")
    cutoff = now - timedelta(days=retention_days)
    newest_success: dict[BackupComponent, datetime] = {}
    for artifact in artifacts:
        if artifact.outcome == "succeeded":
            newest_success[artifact.component] = max(
                newest_success.get(artifact.component, artifact.completed_at),
                artifact.completed_at,
            )
    return tuple(
        artifact
        for artifact in artifacts
        if artifact.outcome == "succeeded"
        and artifact.completed_at < cutoff
        and newest_success[artifact.component] > artifact.completed_at
    )


class EncryptionMaterialError(RuntimeError):
    """The active age recipient is absent or malformed."""


class RestoreIsolationError(RuntimeError):
    """A requested restore target is not isolated from production volumes."""


class ComponentInventoryError(RuntimeError):
    """Backup or restore activation omitted a required GX-10 component."""


def _require_complete_inventory(label: str, values: Mapping[BackupComponent, Any]) -> None:
    required = set(BackupComponent)
    actual = set(values)
    if actual != required:
        missing = sorted(str(component) for component in required - actual)
        extra = sorted(str(component) for component in actual - required)
        raise ComponentInventoryError(
            f"{label} must contain the complete GX-10 component inventory; "
            f"missing={missing}, extra={extra}"
        )


@dataclass(frozen=True, slots=True)
class AgeCommandRequest:
    argv: tuple[str, ...]
    stdin: bytes
    env: Mapping[str, str] = field(default_factory=dict)
    secret_identity: str | None = None


@dataclass(frozen=True, slots=True)
class AgeCommandResult:
    returncode: int
    stdout: bytes


class AgeCommandAdapter:
    """Invoke age without placing private identities in argv or environment."""

    def __init__(
        self,
        *,
        run: Callable[[AgeCommandRequest], AgeCommandResult] | None = None,
    ) -> None:
        self._run = run or self._run_subprocess

    def encrypt(self, payload: bytes, recipient: str) -> bytes:
        if _AGE_RECIPIENT.fullmatch(recipient) is None:
            raise EncryptionMaterialError("valid age recipient required")
        result = self._run(
            AgeCommandRequest(
                argv=("age", "--encrypt", "--recipient", recipient),
                stdin=payload,
            )
        )
        if result.returncode != 0:
            raise EncryptionMaterialError("age encryption command failed")
        _validate_age_ciphertext(result.stdout, plaintext=payload)
        return result.stdout

    def decrypt(self, payload: bytes, identity: str) -> bytes:
        _validate_age_ciphertext(payload)
        if not identity.startswith("AGE-SECRET-KEY-"):
            raise EncryptionMaterialError("valid age identity required")
        result = self._run(
            AgeCommandRequest(
                argv=("age", "--decrypt"),
                stdin=payload,
                secret_identity=identity,
            )
        )
        if result.returncode != 0:
            raise EncryptionMaterialError("age decryption command failed")
        return result.stdout

    @staticmethod
    def _run_subprocess(request: AgeCommandRequest) -> AgeCommandResult:
        safe_env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        argv = list(request.argv)
        identity_fd: int | None = None
        pass_fds: tuple[int, ...] = ()
        try:
            if request.secret_identity is not None:
                identity_fd, identity_writer = os.pipe()
                try:
                    os.write(identity_writer, request.secret_identity.encode())
                finally:
                    os.close(identity_writer)
                argv.extend(("--identity", f"/proc/self/fd/{identity_fd}"))
                pass_fds = (identity_fd,)
            completed = subprocess.run(
                argv,
                input=request.stdin,
                capture_output=True,
                check=False,
                env=safe_env,
                pass_fds=pass_fds,
            )
        finally:
            if identity_fd is not None:
                os.close(identity_fd)
        return AgeCommandResult(returncode=completed.returncode, stdout=completed.stdout or b"")


@dataclass(frozen=True, slots=True)
class OpenBaoAgeMaterialProvider:
    """Resolve age public recipients and private identities from OpenBao."""

    read_secret: Callable[[str], str | None] = get_bao_secret

    def catalog(self) -> AgeRecipientCatalog:
        active = self.read_secret("GX10_AGE_RECIPIENT")
        retained_raw = self.read_secret("GX10_AGE_RETAINED_RECIPIENTS") or "[]"
        try:
            retained_value = json.loads(retained_raw)
        except json.JSONDecodeError as exc:
            raise EncryptionMaterialError("retained age recipients are unreadable") from exc
        if not isinstance(retained_value, list) or not all(
            isinstance(value, str) for value in retained_value
        ):
            raise EncryptionMaterialError("retained age recipients must be a JSON string list")
        catalog = AgeRecipientCatalog(active=active, retained=tuple(retained_value))
        catalog.validated_active()
        return catalog

    def identity_for(self, recipient: str) -> str:
        identities_raw = self.read_secret("GX10_AGE_IDENTITIES")
        if identities_raw is None:
            raise EncryptionMaterialError("OpenBao age identities are unavailable")
        try:
            identities = json.loads(identities_raw)
        except json.JSONDecodeError as exc:
            raise EncryptionMaterialError("OpenBao age identities are unreadable") from exc
        identity = identities.get(recipient) if isinstance(identities, dict) else None
        if not isinstance(identity, str) or not identity.startswith("AGE-SECRET-KEY-"):
            raise EncryptionMaterialError("matching OpenBao age identity is unavailable")
        return identity


@dataclass(frozen=True, slots=True)
class OpenBaoAgeAdapter:
    material: OpenBaoAgeMaterialProvider = field(default_factory=OpenBaoAgeMaterialProvider)
    command: AgeCommandAdapter = field(default_factory=AgeCommandAdapter)

    def catalog(self) -> AgeRecipientCatalog:
        return self.material.catalog()

    def encrypt(self, payload: bytes, recipient: str) -> bytes:
        return self.command.encrypt(payload, recipient)

    def decrypt(self, payload: bytes, recipient: str) -> bytes:
        return self.command.decrypt(payload, self.material.identity_for(recipient))


def _validate_age_ciphertext(payload: bytes, *, plaintext: bytes | None = None) -> None:
    if not payload.startswith(_AGE_ENVELOPE):
        raise EncryptionMaterialError("ciphertext is missing the age envelope")
    if plaintext is not None and payload == plaintext:
        raise EncryptionMaterialError("identity encryption is forbidden")


@dataclass(frozen=True, slots=True)
class AgeRecipientCatalog:
    active: str | None
    retained: tuple[str, ...]

    def validated_active(self) -> str:
        if self.active is None or _AGE_RECIPIENT.fullmatch(self.active) is None:
            raise EncryptionMaterialError("valid OpenBao-managed age recipient required")
        if any(_AGE_RECIPIENT.fullmatch(value) is None for value in self.retained):
            raise EncryptionMaterialError("retained restore recipient is malformed")
        return self.active


@dataclass(frozen=True, slots=True)
class MaintenanceCorrelation:
    operation_id: str
    trace_id: str


@dataclass(frozen=True, slots=True)
class BackupQuota:
    limit_bytes: int
    used_bytes: int

    @property
    def remaining_bytes(self) -> int:
        return max(0, self.limit_bytes - self.used_bytes)


@dataclass(frozen=True, slots=True)
class ComponentBackupResult:
    component: BackupComponent
    outcome: Literal["succeeded", "permanent_failure"]
    stage: Literal["backup"]
    operation_id: str
    trace_id: str
    diagnostic_code: str | None = None
    artifact_name: str | None = None
    bytes: int | None = None
    checksum_sha256: str | None = None
    encryption_recipient: str | None = None


@dataclass(frozen=True, slots=True)
class BackupManifest:
    schema_version: int
    started_at: datetime
    completed_at: datetime
    outcome: Literal["succeeded", "partial", "permanent_failure"]
    operation_id: str
    trace_id: str
    components: tuple[ComponentBackupResult, ...]

    def to_json(self) -> str:
        payload = asdict(self)
        payload["started_at"] = self.started_at.isoformat().replace("+00:00", "Z")
        payload["completed_at"] = self.completed_at.isoformat().replace("+00:00", "Z")
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, value: str) -> BackupManifest:
        payload = json.loads(value)
        return cls(
            schema_version=int(payload["schema_version"]),
            started_at=_parse_time(payload["started_at"]),
            completed_at=_parse_time(payload["completed_at"]),
            outcome=cast(Any, payload["outcome"]),
            operation_id=str(payload["operation_id"]),
            trace_id=str(payload["trace_id"]),
            components=tuple(
                ComponentBackupResult(
                    component=BackupComponent(item["component"]),
                    outcome=cast(Any, item["outcome"]),
                    stage="backup",
                    operation_id=str(item["operation_id"]),
                    trace_id=str(item["trace_id"]),
                    diagnostic_code=item.get("diagnostic_code"),
                    artifact_name=item.get("artifact_name"),
                    bytes=item.get("bytes"),
                    checksum_sha256=item.get("checksum_sha256"),
                    encryption_recipient=item.get("encryption_recipient"),
                )
                for item in payload["components"]
            ),
        )


class GX10BackupController:
    """Produce locally, encrypt, quota-check, then store—always in that order."""

    def __init__(
        self,
        *,
        producers: Mapping[BackupComponent, Callable[[], bytes]],
        encrypt: Callable[[bytes, str], bytes],
        store: Callable[[str, bytes], None],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        _require_complete_inventory("backup producers", producers)
        self._producers = dict(producers)
        self._encrypt = encrypt
        self._store = store
        self._clock = clock or (lambda: datetime.now(UTC))

    def run(
        self,
        *,
        recipient_catalog: AgeRecipientCatalog,
        correlation: MaintenanceCorrelation,
        quota: BackupQuota,
        started_at: datetime,
    ) -> BackupManifest:
        recipient = recipient_catalog.validated_active()
        remaining = quota.remaining_bytes
        results: list[ComponentBackupResult] = []
        for component, producer in self._producers.items():
            attributes = {
                "backup.component": str(component),
                "backup.operation_id": correlation.operation_id,
            }
            with operational_stage("gx10.backup.component", stage="backup", attributes=attributes):
                try:
                    plain = producer()
                    if not isinstance(plain, bytes):
                        raise TypeError("component producer must return bytes")
                    encrypted = self._encrypt(plain, recipient)
                    if not isinstance(encrypted, bytes) or not encrypted:
                        raise EncryptionMaterialError("age encryption produced no artifact")
                    _validate_age_ciphertext(encrypted, plaintext=plain)
                    artifact_name = f"{component}-{started_at:%Y%m%dT%H%M%SZ}.age"
                    if len(encrypted) > remaining:
                        results.append(
                            _failed_component(component, correlation, "backup_quota_exhausted")
                        )
                        continue
                    self._store(artifact_name, encrypted)
                    remaining -= len(encrypted)
                    results.append(
                        ComponentBackupResult(
                            component=component,
                            outcome="succeeded",
                            stage="backup",
                            operation_id=correlation.operation_id,
                            trace_id=correlation.trace_id,
                            artifact_name=artifact_name,
                            bytes=len(encrypted),
                            checksum_sha256=hashlib.sha256(encrypted).hexdigest(),
                            encryption_recipient=recipient,
                        )
                    )
                except Exception:
                    results.append(
                        _failed_component(component, correlation, "component_backup_failed")
                    )
        succeeded = sum(result.outcome == "succeeded" for result in results)
        outcome: Literal["succeeded", "partial", "permanent_failure"]
        if succeeded == len(results):
            outcome = "succeeded"
        elif succeeded:
            outcome = "partial"
        else:
            outcome = "permanent_failure"
        return BackupManifest(
            schema_version=1,
            started_at=started_at,
            completed_at=self._clock(),
            outcome=outcome,
            operation_id=correlation.operation_id,
            trace_id=correlation.trace_id,
            components=tuple(results),
        )


def _failed_component(
    component: BackupComponent,
    correlation: MaintenanceCorrelation,
    diagnostic_code: str,
) -> ComponentBackupResult:
    return ComponentBackupResult(
        component=component,
        outcome="permanent_failure",
        stage="backup",
        operation_id=correlation.operation_id,
        trace_id=correlation.trace_id,
        diagnostic_code=diagnostic_code,
    )


@dataclass(frozen=True, slots=True)
class EncryptedArtifact:
    component: BackupComponent
    name: str
    payload: bytes
    checksum_sha256: str
    encryption_recipient: str
    completed_at: datetime


@dataclass(frozen=True, slots=True)
class ComponentRestoreResult:
    component: BackupComponent
    outcome: Literal["succeeded", "permanent_failure"]
    stage: Literal["restore"]
    operation_id: str
    trace_id: str
    diagnostic_code: str | None = None
    target: str | None = None
    completed_at: datetime | None = None
    rto_seconds: int | None = None


def validate_restore_target(
    *,
    target: Path,
    isolated_root: Path,
    production_sources: Sequence[Path],
) -> None:
    resolved_target = target.resolve()
    resolved_root = isolated_root.resolve()
    if resolved_target == resolved_root or not resolved_target.is_relative_to(resolved_root):
        raise RestoreIsolationError("restore target must be beneath the isolated root")
    for source in production_sources:
        resolved_source = source.resolve()
        if resolved_target == resolved_source or resolved_target.is_relative_to(resolved_source):
            raise RestoreIsolationError("restore target overlaps a production source")
        if resolved_source.is_relative_to(resolved_target):
            raise RestoreIsolationError("restore target contains a production source")


class GX10RestoreDrill:
    def __init__(
        self,
        *,
        decrypt: Callable[[bytes, str], bytes],
        restore: Mapping[BackupComponent, Callable[[bytes, Path], None]],
        validate: Mapping[BackupComponent, Callable[[Path], bool]],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        _require_complete_inventory("restore handlers", restore)
        _require_complete_inventory("restore validators", validate)
        self._decrypt = decrypt
        self._restore = dict(restore)
        self._validate = dict(validate)
        self._clock = clock or (lambda: datetime.now(UTC))

    def restore_component(
        self,
        *,
        artifact: EncryptedArtifact,
        target: Path,
        isolated_root: Path,
        production_sources: Sequence[Path],
        available_recipients: Sequence[str],
        correlation: MaintenanceCorrelation,
    ) -> ComponentRestoreResult:
        restore_started_at = self._clock()
        return self._restore_one(
            artifact=artifact,
            target=target,
            isolated_root=isolated_root,
            production_sources=production_sources,
            available_recipients=available_recipients,
            correlation=correlation,
            restore_started_at=restore_started_at,
        )

    def _restore_one(
        self,
        *,
        artifact: EncryptedArtifact,
        target: Path,
        isolated_root: Path,
        production_sources: Sequence[Path],
        available_recipients: Sequence[str],
        correlation: MaintenanceCorrelation,
        restore_started_at: datetime,
    ) -> ComponentRestoreResult:
        validate_restore_target(
            target=target,
            isolated_root=isolated_root,
            production_sources=production_sources,
        )
        attributes = {
            "restore.component": str(artifact.component),
            "restore.operation_id": correlation.operation_id,
        }
        with operational_stage("gx10.restore.component", stage="restore", attributes=attributes):
            if artifact.encryption_recipient not in available_recipients:
                return self._restore_failure_measured(
                    artifact, correlation, "restore_recipient_unavailable", restore_started_at
                )
            checksum = hashlib.sha256(artifact.payload).hexdigest()
            if checksum != artifact.checksum_sha256:
                return self._restore_failure_measured(
                    artifact, correlation, "artifact_checksum_mismatch", restore_started_at
                )
            try:
                plaintext = self._decrypt(artifact.payload, artifact.encryption_recipient)
                self._restore[artifact.component](plaintext, target)
                if not self._validate[artifact.component](target):
                    return self._restore_failure_measured(
                        artifact,
                        correlation,
                        "component_restore_validation_failed",
                        restore_started_at,
                    )
            except Exception:
                return self._restore_failure_measured(
                    artifact, correlation, "component_restore_failed", restore_started_at
                )
        completed_at = self._clock()
        return ComponentRestoreResult(
            component=artifact.component,
            outcome="succeeded",
            stage="restore",
            operation_id=correlation.operation_id,
            trace_id=correlation.trace_id,
            target=str(target),
            completed_at=completed_at,
            rto_seconds=max(0, int((completed_at - restore_started_at).total_seconds())),
        )

    def _restore_failure_measured(
        self,
        artifact: EncryptedArtifact,
        correlation: MaintenanceCorrelation,
        diagnostic_code: str,
        restore_started_at: datetime,
    ) -> ComponentRestoreResult:
        completed_at = self._clock()
        return _restore_failure(
            artifact,
            correlation,
            diagnostic_code,
            completed_at=completed_at,
            rto_seconds=max(0, int((completed_at - restore_started_at).total_seconds())),
        )

    def run_drill(
        self,
        *,
        artifacts: Mapping[BackupComponent, EncryptedArtifact],
        targets: Mapping[BackupComponent, Path],
        isolated_root: Path,
        production_sources: Sequence[Path],
        available_recipients: Sequence[str],
        correlation: MaintenanceCorrelation,
        metadata_probe: Callable[[], RestoreValidation],
    ) -> RestoreDrillResult:
        _require_complete_inventory("restore artifacts", artifacts)
        _require_complete_inventory("restore targets", targets)
        restore_started_at = self._clock()
        results = tuple(
            self._restore_one(
                artifact=artifacts[component],
                target=targets[component],
                isolated_root=isolated_root,
                production_sources=production_sources,
                available_recipients=available_recipients,
                correlation=correlation,
                restore_started_at=restore_started_at,
            )
            for component in BackupComponent
        )
        validation = metadata_probe()
        synthetic_operation_passed_at = self._clock()
        completed = max(
            result.completed_at for result in results if result.completed_at is not None
        )
        objectives = evaluate_recovery_objectives(
            application_backup_completed_at=artifacts[
                BackupComponent.APPLICATION_POSTGRESQL
            ].completed_at,
            declared_failure_at=restore_started_at,
            restore_started_at=restore_started_at,
            component_completed_at=completed,
            synthetic_operation_passed_at=synthetic_operation_passed_at,
        )
        diagnostics = (
            tuple(
                result.diagnostic_code for result in results if result.diagnostic_code is not None
            )
            + tuple(
                code
                for code, present in (
                    ("application_operation_rows_missing", validation.application_operation_rows),
                    ("langfuse_trace_metadata_missing", validation.langfuse_trace_metadata),
                )
                if not present
            )
            + tuple(f"recovery_objective_{name}_exceeded" for name in objectives.breaches)
        )
        all_components_succeeded = all(result.outcome == "succeeded" for result in results)
        accepted = (
            all_components_succeeded
            and required_restore_metadata_valid(validation)
            and objectives.accepted
        )
        return RestoreDrillResult(
            started_at=restore_started_at,
            completed_at=synthetic_operation_passed_at,
            outcome="succeeded" if accepted else "permanent_failure",
            operation_id=correlation.operation_id,
            trace_id=correlation.trace_id,
            components=results,
            validation=validation,
            objectives=objectives,
            diagnostic_codes=diagnostics,
        )


def _restore_failure(
    artifact: EncryptedArtifact,
    correlation: MaintenanceCorrelation,
    diagnostic_code: str,
    *,
    completed_at: datetime | None = None,
    rto_seconds: int | None = None,
) -> ComponentRestoreResult:
    return ComponentRestoreResult(
        component=artifact.component,
        outcome="permanent_failure",
        stage="restore",
        operation_id=correlation.operation_id,
        trace_id=correlation.trace_id,
        diagnostic_code=diagnostic_code,
        completed_at=completed_at,
        rto_seconds=rto_seconds,
    )


@dataclass(frozen=True, slots=True)
class RecoveryObjectiveResult:
    application_rpo_seconds: int
    component_rto_seconds: int
    full_stack_rto_seconds: int
    accepted: bool
    breaches: tuple[str, ...]


def evaluate_recovery_objectives(
    *,
    application_backup_completed_at: datetime,
    declared_failure_at: datetime,
    restore_started_at: datetime,
    component_completed_at: datetime,
    synthetic_operation_passed_at: datetime,
) -> RecoveryObjectiveResult:
    application_rpo = max(
        0, int((declared_failure_at - application_backup_completed_at).total_seconds())
    )
    component_rto = max(0, int((component_completed_at - restore_started_at).total_seconds()))
    full_stack_rto = max(
        0, int((synthetic_operation_passed_at - restore_started_at).total_seconds())
    )
    breaches = tuple(
        name
        for name, measured, maximum in (
            ("application_rpo", application_rpo, 24 * 60 * 60),
            ("component_rto", component_rto, 2 * 60 * 60),
            ("full_stack_rto", full_stack_rto, 4 * 60 * 60),
        )
        if measured > maximum
    )
    return RecoveryObjectiveResult(
        application_rpo_seconds=application_rpo,
        component_rto_seconds=component_rto,
        full_stack_rto_seconds=full_stack_rto,
        accepted=not breaches,
        breaches=breaches,
    )


@dataclass(frozen=True, slots=True)
class RestoreValidation:
    application_operation_rows: bool
    langfuse_trace_metadata: bool


@dataclass(frozen=True, slots=True)
class RestoreDrillResult:
    started_at: datetime
    completed_at: datetime
    outcome: Literal["succeeded", "permanent_failure"]
    operation_id: str
    trace_id: str
    components: tuple[ComponentRestoreResult, ...]
    validation: RestoreValidation
    objectives: RecoveryObjectiveResult
    diagnostic_codes: tuple[str, ...]


def required_restore_metadata_valid(validation: RestoreValidation) -> bool:
    return validation.application_operation_rows and validation.langfuse_trace_metadata


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include an offset")
    return parsed.astimezone(UTC)
