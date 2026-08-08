"""Database-backed deterministic harness for source-to-podcast workflows."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

from sqlalchemy.orm import Session

from src.config.sources import (
    ObsidianVaultSource,
    SourceBase,
    SourcesConfig,
    configured_source_public_key,
)
from src.ingestion.commands import IngestCommandBase
from src.ingestion.content_references import ContentReferences, record_content_reference
from src.ingestion.registry import SOURCE_REGISTRY, SourceRegistry, configured_source_version
from src.ingestion.result import IngestionResponse
from src.ingestion.service import IngestionService
from src.models.content import Content, ContentSource
from src.models.digest import Digest
from src.models.podcast import PodcastLength, PodcastRequest
from src.models.query import ContentQuery, ResolvedContentSet, SelectionExclusionReason
from src.models.summary import Summary
from src.processors.podcast_script_generator import PodcastScriptGenerator
from src.processors.provenance import ExactContentSetLoader
from src.services.content_set_resolver import ContentSetResolver
from src.services.upload_service import MaterializedUpload
from tests.factories.content import ContentFactory
from tests.factories.digest import DigestFactory
from tests.factories.summary import SummaryFactory
from tests.fixtures.sources.library import SOURCE_FIXTURES, SourceFixture

#: Deterministic secret for this harness only. It derives the opaque public key
#: and the config-version fingerprint, so it must be stable within a run but has
#: no relationship to any deployment secret.
_CONFIGURED_SOURCE_SECRET = "source-matrix-fixture-secret-0123456789"

#: A path-shaped vault the matrix never touches. The fixture orchestrator stands
#: in for the real adapter, so no scan reaches the filesystem; only the source's
#: field values matter, because they are what the key and version hash over.
_MATRIX_OBSIDIAN_SOURCE = ObsidianVaultSource(
    vault_id="source-matrix-fixture",
    vault_path="/srv/source-matrix/vault",
    ingest_folder="Clips/Inbox",
)


def _resolve_configured_source(
    key: str, fixture: SourceFixture
) -> tuple[dict[str, Any], SourceBase | None]:
    """Bind a configured-source fixture command to deployment configuration.

    Fixture commands store the canonical *shape* of a source's command. For a
    source selected by opaque key, the real key and config version depend on the
    deployment secret, so they cannot be checked in; they are bound here exactly
    as the scheduled command planner binds them at submission time.
    """

    command = dict(fixture.command)
    if "source_key" not in command:
        return command, None

    source = _MATRIX_OBSIDIAN_SOURCE if key == "obsidian_vault" else None
    if source is None:
        raise AssertionError(
            f"Fixture '{key}' selects a configured source by key but the matrix "
            "has no deployment source bound for it"
        )
    command["source_key"] = configured_source_public_key(source, secret=_CONFIGURED_SOURCE_SECRET)
    command["configured_source_version"] = configured_source_version(
        source, secret=_CONFIGURED_SOURCE_SECRET
    )
    return command, source


PERIOD_START = datetime(2026, 7, 1, tzinfo=UTC)
PERIOD_END = PERIOD_START + timedelta(days=1)


@dataclass(frozen=True)
class PersistedFixture:
    key: str
    command: Any
    route: str
    source: ContentSource
    content_id: int
    summary_id: int
    ingestion: IngestionResponse


@dataclass(frozen=True)
class VerticalWorkflowResult:
    persisted: tuple[PersistedFixture, ...]
    resolved: ResolvedContentSet
    digest: Digest
    podcast_context: dict[str, Any]
    canonical_references: frozenset[int]


class _SessionDigestLoader:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._loader = ExactContentSetLoader()

    def load_digest(self, digest_id: int):
        return self._loader.load_digest(digest_id, session=self._session)


class _FixtureUploadService:
    """Resolve the file command without touching durable or local storage."""

    def __init__(self) -> None:
        self.requested_ids: tuple[str, ...] = ()

    @contextmanager
    def materialize_sync(self, upload_ids: list[str]) -> Iterator[list[MaterializedUpload]]:
        self.requested_ids = tuple(upload_ids)
        yield [
            MaterializedUpload(
                path=Path("fixture-upload.md"),
                title="Uploaded agent report",
                publication="Fixture files",
            )
        ]


class VerticalWorkflowHarness:
    """Exercise canonical runtime boundaries while replacing only external ingestion/LLM I/O."""

    def __init__(self, session: Session, registry: SourceRegistry = SOURCE_REGISTRY) -> None:
        self.session = session
        self.registry = registry

    async def run(
        self,
        keys: tuple[str, ...],
        *,
        selected_sources: tuple[ContentSource, ...] | None = None,
        add_cross_source_alias: bool = False,
    ) -> VerticalWorkflowResult:
        persisted = tuple(
            self._ingest_fixture(key, SOURCE_FIXTURES[key], index)
            for index, key in enumerate(keys, start=1)
        )
        references = ContentReferences()
        references.record(
            {
                content_id: content_id
                for item in persisted
                for content_id in item.ingestion.details["content_ids"]
            }
        )

        if add_cross_source_alias:
            alias = ContentFactory(
                source_type=persisted[-1].source,
                source_id=f"fixture:{persisted[-1].key}:alias",
                title=f"Alias of {persisted[0].key}",
                canonical_id=persisted[0].content_id,
                published_date=PERIOD_START + timedelta(hours=12),
                ingested_at=PERIOD_START + timedelta(hours=12),
            )
            SummaryFactory(content=alias, content_id=alias.id)
            references.record({alias.id: persisted[0].content_id})

        source_types = selected_sources or tuple(
            sorted({item.source for item in persisted}, key=lambda value: value.value)
        )
        resolved = ContentSetResolver().resolve(
            ContentQuery(
                source_types=list(source_types),
                start_date=PERIOD_START,
                end_date=PERIOD_END,
                sort_order="asc",
            ),
            session=self.session,
        )
        digest = DigestFactory(
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            title="Deterministic source digest",
            executive_overview="Canonical source fixture digest",
            newsletter_count=resolved.eligible_content_count,
            source_content_ids=list(resolved.content_ids),
            source_summary_ids=list(resolved.summary_ids),
            selection_policy=resolved.policy.model_dump(mode="json"),
            selection_fingerprint=resolved.fingerprint,
        )
        self.session.flush()

        generator = object.__new__(PodcastScriptGenerator)
        generator.content_loader = _SessionDigestLoader(self.session)
        generator.available_content_ids = ()
        generator.selection_fingerprint = None
        context = await generator._assemble_lightweight_context(
            PodcastRequest(digest_id=digest.id, length=PodcastLength.BRIEF)
        )

        return VerticalWorkflowResult(
            persisted=persisted,
            resolved=resolved,
            digest=digest,
            podcast_context=context,
            canonical_references=frozenset(references),
        )

    def _ingest_fixture(self, key: str, fixture: SourceFixture, index: int) -> PersistedFixture:
        raw_command, deployment_source = _resolve_configured_source(key, fixture)
        command = self.registry.parse_command(raw_command)
        descriptor = self.registry.get(command.kind)
        created: tuple[Content, Summary, ContentSource] | None = None

        def fixture_orchestrator(typed_command: IngestCommandBase) -> IngestionResponse:
            nonlocal created
            sources = descriptor.resolve_sources(typed_command)
            if len(sources) != 1:
                raise AssertionError(
                    f"Fixture '{key}' did not resolve to exactly one content source"
                )
            source = next(iter(sources))
            content = ContentFactory(
                source_type=source,
                source_id=f"fixture:{key}:{index}",
                source_url=f"https://fixtures.test/{key}/{index}",
                title=fixture.title,
                publication=f"Fixture {key}",
                published_date=PERIOD_START + timedelta(minutes=index),
                ingested_at=PERIOD_START + timedelta(minutes=index),
                markdown_content=f"# {fixture.title}\n\nDeterministic content for {key}.",
            )
            summary = SummaryFactory(
                content=content,
                content_id=content.id,
                executive_summary=f"Persisted summary for {key}",
            )
            record_content_reference(content.id, content.canonical_id)
            created = (content, summary, source)
            return IngestionResponse(
                command=fixture.response_command,
                source=fixture.response_source,
                status="ok",
                items_ingested=1,
                details={
                    "content_id": content.id,
                    "results": [{"content_id": content.id}],
                },
            )

        fixture_registry = SourceRegistry([replace(descriptor, orchestrator=fixture_orchestrator)])
        upload_service = _FixtureUploadService() if key == "files" else None
        service = IngestionService(
            registry=fixture_registry,
            upload_service=upload_service,
            # A command naming a configured source by opaque key is resolved and
            # version-checked against deployment configuration before dispatch,
            # so the matrix must supply that configuration the same way a worker
            # does. Sources that carry their parameters inline pass None.
            configured_source_key_secret=(
                _CONFIGURED_SOURCE_SECRET if deployment_source is not None else None
            ),
            source_config_loader=(
                (lambda: SourcesConfig(sources=[deployment_source]))
                if deployment_source is not None
                else None
            ),
        )
        if key == "files":
            with patch(
                "src.ingestion.orchestrator.ingest_files",
                side_effect=lambda **_kwargs: fixture_orchestrator(command),
            ):
                response = service.execute(raw_command)
            assert upload_service is not None
            assert upload_service.requested_ids == tuple(command.upload_ids)
        else:
            response = service.execute(raw_command)

        if created is None:
            raise AssertionError(f"Fixture orchestrator '{key}' was not invoked")
        content, summary, source = created
        route = str(descriptor.resolve_route(command))
        assert response.details["command_key"] == key
        assert response.details["resolved_route"] == route
        assert response.details["emitted_sources"] == [source.value]
        assert response.details["content_ids"] == [content.id]
        return PersistedFixture(
            key=key,
            command=command,
            route=route,
            source=source,
            content_id=content.id,
            summary_id=summary.id,
            ingestion=response,
        )


def assert_provenance_invariants(result: VerticalWorkflowResult) -> None:
    """Assert the exact selection is preserved into digest and podcast context."""

    resolved = result.resolved
    assert len(resolved.content_ids) == len(set(resolved.content_ids))
    assert len(resolved.summary_ids) == len(set(resolved.summary_ids))
    assert result.digest.source_content_ids == list(resolved.content_ids)
    assert result.digest.source_summary_ids == list(resolved.summary_ids)
    assert result.digest.selection_fingerprint == resolved.fingerprint
    assert result.digest.newsletter_count == resolved.eligible_content_count
    assert [item["id"] for item in result.podcast_context["content_metadata"]] == list(
        resolved.content_ids
    )
    assert [summary.id for summary in result.podcast_context["summaries"]] == list(
        resolved.summary_ids
    )
    assert result.podcast_context["selection_fingerprint"] == resolved.fingerprint
    assert frozenset(resolved.content_ids).issubset(result.canonical_references)


def assert_one_duplicate_alias(result: VerticalWorkflowResult) -> None:
    aliases = result.resolved.exclusions_by_reason.get(SelectionExclusionReason.DUPLICATE_ALIAS, ())
    assert len(aliases) == 1
    assert aliases[0].canonical_content_id == result.persisted[0].content_id
