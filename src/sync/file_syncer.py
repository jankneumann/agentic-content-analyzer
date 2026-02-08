"""File storage sync between providers.

Discovers files referenced in the source database and copies them
from the source storage provider to the target storage provider.
Supports selective bucket sync and skip-if-exists deduplication.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.services.file_storage import FileStorageProvider
from src.sync.constants import FILE_PATH_COLUMNS

logger = logging.getLogger(__name__)

# Batch size for file path discovery queries
_DISCOVERY_BATCH_SIZE = 1000


@dataclass
class FileSyncStats:
    """Statistics from a file sync operation."""

    discovered: int = 0
    copied: int = 0
    skipped: int = 0
    missing: int = 0
    failed: int = 0
    bytes_copied: int = 0
    per_bucket: dict[str, dict[str, int]] = field(default_factory=dict)

    def summary(self) -> str:
        """Human-readable summary of sync results."""
        parts = [
            f"discovered={self.discovered}",
            f"copied={self.copied}",
            f"skipped={self.skipped}",
        ]
        if self.missing:
            parts.append(f"missing={self.missing}")
        if self.failed:
            parts.append(f"failed={self.failed}")
        if self.bytes_copied:
            parts.append(f"bytes={_format_size(self.bytes_copied)}")
        return ", ".join(parts)


@dataclass
class FileRef:
    """A file reference discovered from the source database."""

    table: str
    column: str
    bucket: str
    path: str


class FileSyncer:
    """Sync files between storage providers based on database references.

    Discovers file paths by querying the source database for non-NULL
    file path columns (images.storage_path, audio_digests.audio_url,
    podcasts.audio_url), then copies referenced files from source
    to target storage.

    Args:
        source_engine: SQLAlchemy Engine for the source database
                       (used for file path discovery).
        source_storage: Callable that returns a FileStorageProvider
                        for a given bucket on the source side.
        target_storage: Callable that returns a FileStorageProvider
                        for a given bucket on the target side.
    """

    def __init__(
        self,
        source_engine: Engine,
        source_storage: dict[str, FileStorageProvider],
        target_storage: dict[str, FileStorageProvider],
    ) -> None:
        self._engine = source_engine
        self._source_storage = source_storage
        self._target_storage = target_storage

    def discover_files(
        self,
        buckets: list[str] | None = None,
    ) -> list[FileRef]:
        """Discover file references from the source database.

        Queries each table/column pair in FILE_PATH_COLUMNS for
        non-NULL values. Optionally filters by bucket.

        Args:
            buckets: Optional list of bucket names to include.
                     If None, discovers files in all buckets.

        Returns:
            List of FileRef objects with table, column, bucket, and path.
        """
        refs: list[FileRef] = []

        for table_name, columns in FILE_PATH_COLUMNS.items():
            for column_name, bucket in columns.items():
                if buckets and bucket not in buckets:
                    continue

                table_refs = self._discover_table_files(table_name, column_name, bucket)
                refs.extend(table_refs)
                if table_refs:
                    logger.info(
                        "Discovered %d file refs from %s.%s (bucket: %s)",
                        len(table_refs),
                        table_name,
                        column_name,
                        bucket,
                    )

        logger.info("Total file references discovered: %d", len(refs))
        return refs

    def _discover_table_files(
        self,
        table_name: str,
        column_name: str,
        bucket: str,
    ) -> list[FileRef]:
        """Discover file paths from a single table/column pair.

        Uses server-side pagination to handle large tables.
        """
        refs: list[FileRef] = []
        offset = 0

        with self._engine.connect() as conn:
            while True:
                result = conn.execute(
                    text(
                        f"SELECT {column_name} FROM {table_name} "  # noqa: S608
                        f"WHERE {column_name} IS NOT NULL "
                        f"ORDER BY id LIMIT :limit OFFSET :offset"
                    ),
                    {"limit": _DISCOVERY_BATCH_SIZE, "offset": offset},
                )
                rows = result.fetchall()
                if not rows:
                    break

                for row in rows:
                    path = row[0]
                    if path:
                        refs.append(
                            FileRef(
                                table=table_name,
                                column=column_name,
                                bucket=bucket,
                                path=str(path),
                            )
                        )

                if len(rows) < _DISCOVERY_BATCH_SIZE:
                    break
                offset += _DISCOVERY_BATCH_SIZE

        return refs

    def sync_files(
        self,
        refs: list[FileRef],
        dry_run: bool = False,
    ) -> FileSyncStats:
        """Copy discovered files from source to target storage.

        Skips files that already exist on the target. Logs warnings
        for files missing from the source.

        Args:
            refs: File references to sync (from discover_files()).
            dry_run: If True, report what would be copied without
                     actually transferring files.

        Returns:
            FileSyncStats with counts and per-bucket breakdown.
        """
        stats = FileSyncStats(discovered=len(refs))

        if not refs:
            logger.info("No files to sync")
            return stats

        if dry_run:
            return self._dry_run_sync(refs, stats)

        # Group by bucket for reporting
        return asyncio.run(self._async_sync_files(refs, stats))

    async def _async_sync_files(
        self,
        refs: list[FileRef],
        stats: FileSyncStats,
    ) -> FileSyncStats:
        """Async implementation of file sync."""
        for ref in refs:
            bucket = ref.bucket
            path = ref.path

            source = self._source_storage.get(bucket)
            target = self._target_storage.get(bucket)

            if not source or not target:
                logger.warning(
                    "No storage provider for bucket %s, skipping %s",
                    bucket,
                    path,
                )
                stats.failed += 1
                continue

            # Initialize per-bucket stats
            if bucket not in stats.per_bucket:
                stats.per_bucket[bucket] = {
                    "copied": 0,
                    "skipped": 0,
                    "missing": 0,
                    "failed": 0,
                }

            try:
                # Check if already exists on target
                if await target.exists(path):
                    stats.skipped += 1
                    stats.per_bucket[bucket]["skipped"] += 1
                    continue

                # Check if exists on source
                if not await source.exists(path):
                    logger.warning(
                        "Source file missing: %s (bucket: %s, from %s.%s)",
                        path,
                        bucket,
                        ref.table,
                        ref.column,
                    )
                    stats.missing += 1
                    stats.per_bucket[bucket]["missing"] += 1
                    continue

                # Copy: read from source, write to target
                data = await source.get(path)
                # Use save() with the original path's filename
                filename = path.rsplit("/", 1)[-1] if "/" in path else path
                await target.save(
                    data=data,
                    filename=filename,
                    content_type="application/octet-stream",
                )
                stats.copied += 1
                stats.bytes_copied += len(data)
                stats.per_bucket[bucket]["copied"] += 1

                logger.debug("Copied %s (%s)", path, bucket)

            except Exception as e:
                logger.error(
                    "Failed to sync file %s (bucket: %s): %s",
                    path,
                    bucket,
                    e,
                )
                stats.failed += 1
                stats.per_bucket[bucket]["failed"] += 1

        logger.info("File sync complete: %s", stats.summary())
        return stats

    def _dry_run_sync(
        self,
        refs: list[FileRef],
        stats: FileSyncStats,
    ) -> FileSyncStats:
        """Preview file sync without transferring data."""
        for ref in refs:
            bucket = ref.bucket
            if bucket not in stats.per_bucket:
                stats.per_bucket[bucket] = {"would_copy": 0}
            stats.per_bucket[bucket]["would_copy"] = (
                stats.per_bucket[bucket].get("would_copy", 0) + 1
            )

        logger.info(
            "[DRY RUN] Would sync %d files across buckets: %s",
            len(refs),
            {b: c.get("would_copy", 0) for b, c in stats.per_bucket.items()},
        )
        return stats

    @staticmethod
    def check_same_storage(
        source_providers: dict[str, FileStorageProvider],
        target_providers: dict[str, FileStorageProvider],
    ) -> bool:
        """Check if source and target storage point to the same location.

        Returns True if all bucket providers are identical (same provider
        name and bucket configuration), meaning file sync would be a no-op.
        """
        for bucket in source_providers:
            source = source_providers.get(bucket)
            target = target_providers.get(bucket)
            if source is None or target is None:
                return False
            if source.provider_name != target.provider_name:
                return False
            if source.bucket != target.bucket:
                return False
        return True


def _format_size(size_bytes: int) -> str:
    """Format byte count as human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} TB"
