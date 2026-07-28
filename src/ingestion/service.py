"""Canonical application boundary for typed ingestion execution."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import nullcontext
from typing import TYPE_CHECKING, Any

from src.config.sources import (
    SourcesConfig,
    configured_source_public_key,
    source_key,
    use_sources_config,
    validate_configured_source_key_secret,
)
from src.ingestion.commands import FilesIngestCommand, IngestCommandBase
from src.ingestion.content_references import ContentReferences, collect_content_references
from src.ingestion.registry import SOURCE_REGISTRY, SourceDescriptor, SourceRegistry
from src.ingestion.result import IngestionResponse, derive_status, use_public_source_keys

if TYPE_CHECKING:
    from src.services.upload_service import UploadService


class IngestionService:
    """Validate and dispatch every ingestion source through its descriptor."""

    def __init__(
        self,
        registry: SourceRegistry = SOURCE_REGISTRY,
        upload_service: UploadService | None = None,
        configured_source_key_secret: str | None = None,
    ) -> None:
        if configured_source_key_secret is not None:
            validate_configured_source_key_secret(configured_source_key_secret)
        self.registry = registry
        self._upload_service = upload_service
        self._configured_source_key_secret = configured_source_key_secret

    def execute(self, command: IngestCommandBase | Mapping[str, Any]) -> IngestionResponse:
        typed_command = self.registry.parse_command(command)
        descriptor = self.registry.get(typed_command.kind)
        configured_sources = getattr(typed_command, "configured_sources", None)
        source_config = None
        if configured_sources is not None:
            if not configured_sources:
                raise ValueError("Configured source snapshot cannot be empty")
            source_config = SourcesConfig.model_validate({"sources": configured_sources})
            for source in source_config.sources:
                matched = self.registry.descriptor_for_config(source)
                if matched is not descriptor:
                    raise ValueError(
                        f"Configured source type '{source.type}' does not match "
                        f"command '{descriptor.key}'"
                    )

        config_context = (
            use_sources_config(source_config) if source_config is not None else nullcontext()
        )
        if source_config is not None:
            source_key_secret = self._configured_source_key_secret
            if source_key_secret is None:
                from src.config.settings import get_settings

                source_key_secret = get_settings().get_configured_source_key_secret()
            public_source_keys = {
                source_key(source): configured_source_public_key(
                    source,
                    secret=source_key_secret,
                )
                for source in source_config.sources
            }
            identity_context = use_public_source_keys(public_source_keys)
        else:
            identity_context = nullcontext()

        with (
            config_context,
            identity_context,
            collect_content_references() as committed_content_ids,
        ):
            if isinstance(typed_command, FilesIngestCommand):
                response = self._execute_files(descriptor, typed_command)
            else:
                response = descriptor.orchestrator(typed_command)

            if isinstance(response, int):
                response = IngestionResponse(
                    command="ingest.readwise",
                    source="readwise",
                    status="ok",
                    items_ingested=response,
                )
            if not isinstance(response, IngestionResponse):
                raise TypeError(
                    f"Source '{descriptor.key}' returned {type(response).__name__}, "
                    "expected IngestionResponse"
                )
            if source_config is not None:
                represented = {
                    outcome.source_key
                    for outcome in response.source_outcomes
                    if outcome.source_key in public_source_keys.values()
                }
                unmatched = len(set(public_source_keys.values()).difference(represented))
                response = response.model_copy(
                    update={
                        "source_outcomes_omitted": max(
                            response.source_outcomes_omitted,
                            unmatched,
                        )
                    }
                )
            return self._normalize(
                response,
                descriptor,
                typed_command,
                committed_content_ids,
            )

    def _execute_files(
        self,
        descriptor: SourceDescriptor,
        command: FilesIngestCommand,
    ) -> IngestionResponse | int:
        if self._upload_service is None:
            from src.services.upload_service import UploadService

            self._upload_service = UploadService()
        with self._upload_service.materialize_sync(command.upload_ids) as uploads:
            from src.ingestion import orchestrator

            responses = [
                orchestrator.ingest_files(
                    paths=[upload.path],
                    title=upload.title,
                    publication=upload.publication,
                    force_reprocess=command.force_reprocess,
                )
                for upload in uploads
            ]
        if len(responses) == 1:
            return responses[0]
        errors = [error for response in responses for error in response.errors]
        warnings = [warning for response in responses for warning in response.warnings]
        items_ingested = sum(response.items_ingested for response in responses)
        items_failed = sum(response.items_failed for response in responses)
        return IngestionResponse(
            command="ingest.files",
            source="files",
            status=derive_status(
                items_ingested=items_ingested,
                items_failed=items_failed,
                errors=errors,
            ),
            items_ingested=items_ingested,
            items_skipped=sum(response.items_skipped for response in responses),
            items_failed=items_failed,
            errors=errors,
            warnings=warnings,
            details={
                "results": [
                    result
                    for response in responses
                    for result in response.details.get("results", [])
                ]
            },
        )

    @staticmethod
    def _normalize(
        response: IngestionResponse,
        descriptor: SourceDescriptor,
        command: IngestCommandBase,
        committed_content_ids: ContentReferences,
    ) -> IngestionResponse:
        details = dict(response.details)
        route = descriptor.resolve_route(command)
        emitted_sources = sorted(source.value for source in descriptor.resolve_sources(command))

        content_ids = set(committed_content_ids)
        content_id = details.get("content_id")
        if isinstance(content_id, int) and content_id > 0:
            content_ids.add(committed_content_ids.canonicalize(content_id))
        for item in details.get("results", []):
            if isinstance(item, Mapping):
                item_id = item.get("content_id")
                if isinstance(item_id, int) and item_id > 0:
                    content_ids.add(committed_content_ids.canonicalize(item_id))

        details.update(
            {
                "command_key": descriptor.key,
                "resolved_route": str(route),
                "emitted_sources": emitted_sources,
                "content_ids": sorted(content_ids),
            }
        )
        details.pop("routed_to", None)
        return response.model_copy(update={"details": details})
