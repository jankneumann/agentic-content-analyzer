"""The single manifest reader shared by the readiness check and the worker.

Design A8: `wp-health-alerts` had no service module in scope, so the only in-scope
options were duplicating this reader — two caches, two timeout policies, two
definitions of "stale" — or importing an API module from the queue worker and
inverting the layering. It lives here instead, next to the code that writes the
manifest, and both consumers import it.

Three properties this module exists to guarantee:

* **It never raises.** A backup-target read failure is a *status value*, not an
  exception. A readiness probe that 500s because a bucket is slow has turned a
  monitoring signal into an outage.
* **It holds no decryption identity.** The manifest is the one unencrypted object
  on the target precisely so this path needs read access to one key and nothing
  more. A reader that could decrypt would be a reader worth stealing.
* **It rejects a foreign environment.** A manifest whose recorded environment is
  not ours is not evidence about us, however fresh it is (design A6.3).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from src.services.backup.target import manifest_key
from src.utils.logging import get_logger

logger = get_logger(__name__)

#: Repeated readiness probes must not each issue a network read. Short enough that
#: a freshly written manifest is visible within one check window.
CACHE_TTL_SECONDS = 60.0


class BackupFreshnessStatus(StrEnum):
    OK = "ok"
    STALE = "stale"
    PARTIAL = "partial"
    NO_HISTORY = "no_history"
    ENVIRONMENT_MISMATCH = "environment_mismatch"
    UNKNOWN = "unknown"
    NOT_CONFIGURED = "not_configured"


#: Status -> the diagnostic code in the alert contract. The contract's enum is
#: authoritative (design A11); this mapping is the only place the two meet.
STATUS_DIAGNOSTIC_CODE: dict[BackupFreshnessStatus, str] = {
    BackupFreshnessStatus.STALE: "backup_stale",
    BackupFreshnessStatus.NO_HISTORY: "backup_no_history",
    BackupFreshnessStatus.PARTIAL: "backup_partial",
    BackupFreshnessStatus.UNKNOWN: "backup_target_unreachable",
    BackupFreshnessStatus.ENVIRONMENT_MISMATCH: "backup_environment_mismatch",
}

#: Statuses that warrant a durable alert. `ok` and `not_configured` do not.
ALERTABLE_STATUSES = frozenset(STATUS_DIAGNOSTIC_CODE)


@dataclass(frozen=True)
class BackupFreshness:
    """What the manifest says about this environment's last backup."""

    status: BackupFreshnessStatus
    manifest_age_seconds: int | None = None
    completed_at: datetime | None = None
    stores_succeeded: int = 0
    stores_failed: int = 0
    stores_skipped: int = 0

    @property
    def diagnostic_code(self) -> str | None:
        return STATUS_DIAGNOSTIC_CODE.get(self.status)

    @property
    def alertable(self) -> bool:
        return self.status in ALERTABLE_STATUSES

    @property
    def severity(self) -> str:
        return "error" if self.status is BackupFreshnessStatus.STALE else "warning"


_cache: tuple[float, BackupFreshness] | None = None


def reset_cache() -> None:
    """Drop the memoized reading. Tests call this; production does not need to."""
    global _cache
    _cache = None


def read_freshness(
    settings: Any,
    *,
    now: datetime | None = None,
    use_cache: bool = True,
    monotonic: Any = time.monotonic,
) -> BackupFreshness:
    """Evaluate backup freshness for THIS environment. Never raises."""
    global _cache

    if not getattr(settings, "backup_monitoring_enabled", True):
        return BackupFreshness(status=BackupFreshnessStatus.NOT_CONFIGURED)

    if use_cache and _cache is not None:
        cached_at, cached = _cache
        if monotonic() - cached_at < CACHE_TTL_SECONDS:
            return cached

    freshness = _evaluate(settings, now=now or datetime.now(UTC))
    if use_cache:
        _cache = (monotonic(), freshness)
    return freshness


def _evaluate(settings: Any, *, now: datetime) -> BackupFreshness:
    document = _fetch_manifest(settings)
    if document is _ABSENT:
        return BackupFreshness(status=BackupFreshnessStatus.NO_HISTORY)
    if document is None:
        return BackupFreshness(status=BackupFreshnessStatus.UNKNOWN)

    assert isinstance(document, dict)
    environment = str(getattr(settings, "environment", "development"))
    if str(document.get("environment")) != environment:
        return BackupFreshness(status=BackupFreshnessStatus.ENVIRONMENT_MISMATCH)

    completed_at = _parse_timestamp(document.get("completed_at"))
    if completed_at is None:
        return BackupFreshness(status=BackupFreshnessStatus.UNKNOWN)

    stores = document.get("stores")
    stores = stores if isinstance(stores, list) else []
    tallies = {
        outcome: sum(1 for s in stores if isinstance(s, dict) and s.get("outcome") == outcome)
        for outcome in ("succeeded", "failed", "skipped")
    }

    age_seconds = max(0, int((now - completed_at).total_seconds()))
    threshold_hours = int(getattr(settings, "backup_staleness_hours", 48) or 48)

    if age_seconds > threshold_hours * 3600:
        status = BackupFreshnessStatus.STALE
    elif tallies["failed"] or document.get("overall_outcome") == "partial":
        # A6.2 — freshness from timestamp ALONE reported a partial run as ok. A
        # fresh manifest that records a failed store is not a healthy backup.
        status = BackupFreshnessStatus.PARTIAL
    else:
        status = BackupFreshnessStatus.OK

    return BackupFreshness(
        status=status,
        manifest_age_seconds=age_seconds,
        completed_at=completed_at,
        stores_succeeded=tallies["succeeded"],
        stores_failed=tallies["failed"],
        stores_skipped=tallies["skipped"],
    )


class _Absent:
    """Sentinel distinguishing 'no manifest' from 'could not reach the target'."""


_ABSENT = _Absent()


def _fetch_manifest(settings: Any) -> dict[str, Any] | _Absent | None:
    """Fetch and parse the manifest. `_ABSENT` = no object; `None` = unreachable."""
    bucket = getattr(settings, "backup_s3_bucket", None)
    if not bucket:
        return _ABSENT

    prefix = str(getattr(settings, "backup_s3_prefix", None) or "aca").strip("/")
    environment = str(getattr(settings, "environment", "development"))
    key = manifest_key(prefix, environment)

    try:
        client = _s3_client(settings)
        response = client.get_object(Bucket=str(bucket), Key=key)
        body = response["Body"].read()
    except Exception as exc:
        if _is_missing_object(exc):
            return _ABSENT
        logger.warning("backup manifest could not be read: %s", type(exc).__name__)
        return None

    try:
        document = json.loads(body)
    except (ValueError, TypeError):
        return None
    return document if isinstance(document, dict) else None


def _is_missing_object(exc: Exception) -> bool:
    code = getattr(getattr(exc, "response", None), "get", lambda _k, _d=None: None)("Error", {})
    if isinstance(code, dict) and code.get("Code") in {"NoSuchKey", "404", "NotFound"}:
        return True
    return type(exc).__name__ in {"NoSuchKey", "404"}


def _s3_client(settings: Any) -> Any:
    """Build a bounded S3 client.

    Timeouts are explicit and short: this runs inside a readiness probe, and a
    default-timeout client turns a slow bucket into a failing health check.
    """
    import boto3
    from botocore.config import Config

    def plain(value: object) -> str | None:
        if value is None:
            return None
        if hasattr(value, "get_secret_value"):
            return str(value.get_secret_value())  # type: ignore[attr-defined]
        return str(value) or None

    return boto3.client(
        "s3",
        endpoint_url=plain(getattr(settings, "backup_s3_endpoint", None)),
        region_name=str(getattr(settings, "backup_s3_region", None) or "auto"),
        aws_access_key_id=plain(getattr(settings, "backup_s3_access_key_id", None)),
        aws_secret_access_key=plain(getattr(settings, "backup_s3_secret_access_key", None)),
        config=Config(
            connect_timeout=3,
            read_timeout=3,
            retries={"max_attempts": 1},
        ),
    )


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
