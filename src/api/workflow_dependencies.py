"""Dependency providers for the canonical workflow HTTP adapters."""

from __future__ import annotations

from src.config.sources import SourcesConfig, load_sources_config
from src.services.capability_service import CapabilityService
from src.services.operation_service import OperationService
from src.services.upload_service import UploadService


def get_operation_service() -> OperationService:
    return OperationService()


def get_upload_service() -> UploadService:
    return UploadService()


def get_capability_service() -> CapabilityService:
    return CapabilityService()


def get_sources_config() -> SourcesConfig:
    return load_sources_config()
