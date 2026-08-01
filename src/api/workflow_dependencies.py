"""Dependency providers for the canonical workflow HTTP adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator

from src.config.settings import get_settings
from src.config.sources import SourcesConfig, load_sources_config
from src.queue import setup as queue_setup
from src.services.capability_service import CapabilityService
from src.services.content_reconciliation_service import ContentReconciliationService
from src.services.operation_service import OperationService
from src.services.upload_service import UploadService


def get_operation_service() -> OperationService:
    return OperationService()


def get_upload_service() -> UploadService:
    return UploadService()


def get_capability_service() -> CapabilityService:
    return CapabilityService()


async def get_content_reconciliation_service() -> AsyncIterator[ContentReconciliationService]:
    """Provide a policy-configured reconciler on one request-scoped connection."""
    settings = get_settings()
    async with queue_setup._queue_connection() as connection:
        yield ContentReconciliationService(
            connection=connection,
            stale_seconds=settings.content_reconciliation_stale_seconds,
            max_retries=settings.content_reconciliation_max_retries,
            batch_size=settings.content_reconciliation_batch_size,
            lock_timeout_ms=settings.content_reconciliation_lock_timeout_ms,
            statement_timeout_ms=settings.content_reconciliation_statement_timeout_ms,
            apply_enabled=settings.content_reconciliation_apply_enabled,
        )


def get_sources_config() -> SourcesConfig:
    return load_sources_config()
