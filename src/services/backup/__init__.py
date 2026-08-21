"""Off-site backup: engine, store adapters, target access, and freshness reading.

The public surface is deliberately small. `aca backup` drives :class:`BackupEngine`;
the readiness check and the worker read :func:`read_freshness`. Nothing else in the
application should reach further into this package.
"""

from src.services.backup.engine import BackupEngine, BackupPreflightError, VerifyResult
from src.services.backup.manifest_reader import (
    BackupFreshness,
    BackupFreshnessStatus,
    read_freshness,
)
from src.services.backup.models import (
    BackupRunResult,
    RetentionTier,
    StoreName,
    StoreOutcome,
    StoreResult,
    retention_tier_for,
)

__all__ = [
    "BackupEngine",
    "BackupFreshness",
    "BackupFreshnessStatus",
    "BackupPreflightError",
    "BackupRunResult",
    "RetentionTier",
    "StoreName",
    "StoreOutcome",
    "StoreResult",
    "VerifyResult",
    "read_freshness",
    "retention_tier_for",
]
