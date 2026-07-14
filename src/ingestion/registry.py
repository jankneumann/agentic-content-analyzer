"""Executable registry for ingestion dispatch and capability discovery."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from src.config.sources import (
    ArxivSource,
    BlogSource,
    GmailSource,
    HuggingFacePapersSource,
    PodcastSource,
    ReadwiseSource,
    RSSSource,
    ScholarSource,
    SourceBase,
    SourcesConfig,
    SubstackSource,
    WebSearchSource,
    YouTubeChannelSource,
    YouTubePlaylistSource,
    YouTubeRSSSource,
)
from src.ingestion.commands import (
    ArxivPaperIngestCommand,
    ArxivSearchIngestCommand,
    BlogIngestCommand,
    FilesIngestCommand,
    GmailIngestCommand,
    HuggingFacePapersIngestCommand,
    IngestCommandBase,
    PerplexitySearchIngestCommand,
    PodcastIngestCommand,
    ReadwiseIngestCommand,
    RssIngestCommand,
    ScholarPaperIngestCommand,
    ScholarReferencesIngestCommand,
    ScholarSearchIngestCommand,
    SubstackIngestCommand,
    UrlIngestCommand,
    XSearchIngestCommand,
    YouTubePlaylistIngestCommand,
    YouTubeRssIngestCommand,
)
from src.ingestion.result import IngestionResponse
from src.ingestion.url_router import RouteKind, classify_url, route_to_source
from src.models.content import ContentSource

type Transport = str
type Orchestrator = Callable[[IngestCommandBase], IngestionResponse | int]
type ConfigMatcher = Callable[[SourceBase], bool]
type ConfigAccessor = Callable[[SourcesConfig], list[SourceBase]]
type RouteResolver = Callable[[IngestCommandBase], str | RouteKind]
type SourceResolver = Callable[[IngestCommandBase], frozenset[ContentSource]]


@dataclass(frozen=True)
class SourceOptions:
    supports_force: bool = False
    supports_date_range: bool = False
    supports_preview: bool = False
    requires_identifier: bool = False


@dataclass(frozen=True)
class SourceDescriptor:
    key: str
    display_name: str
    command_model: type[IngestCommandBase]
    orchestrator: Orchestrator
    emitted_sources: frozenset[ContentSource]
    scheduled: bool
    aliases: frozenset[str] = field(default_factory=frozenset)
    removed_aliases: Mapping[str, str] = field(default_factory=dict)
    config_matcher: ConfigMatcher | None = None
    config_accessor: ConfigAccessor | None = None
    route_resolver: RouteResolver | None = None
    source_resolver: SourceResolver | None = None
    options: SourceOptions = field(default_factory=SourceOptions)
    transports: frozenset[Transport] = field(
        default_factory=lambda: frozenset({"cli", "http", "mcp", "frontend"})
    )

    def resolve_route(self, command: IngestCommandBase) -> str | RouteKind:
        if self.route_resolver is None:
            return self.key
        return self.route_resolver(command)

    def resolve_sources(self, command: IngestCommandBase) -> frozenset[ContentSource]:
        if self.source_resolver is None:
            return self.emitted_sources
        resolved = self.source_resolver(command)
        if not resolved or not resolved.issubset(self.emitted_sources):
            raise ValueError(f"Descriptor '{self.key}' resolved undeclared emitted sources")
        return resolved


@dataclass(frozen=True)
class ConfiguredSource:
    command_key: str
    configuration: dict[str, Any]


class SourceRegistry:
    """Validated, ordered registry used by dispatch and all surface projections."""

    def __init__(
        self,
        descriptors: Iterable[SourceDescriptor],
        *,
        removed_aliases: Mapping[str, str] | None = None,
    ) -> None:
        self._descriptors = tuple(descriptors)
        self._by_key: dict[str, SourceDescriptor] = {}
        self._by_alias: dict[str, SourceDescriptor] = {}
        self._removed: dict[str, str] = {}
        self._validate()
        for alias, diagnostic in (removed_aliases or {}).items():
            if alias in self._by_key or alias in self._by_alias or alias in self._removed:
                raise ValueError(f"Removed alias '{alias}' is claimed more than once")
            self._removed[alias] = diagnostic

    def __iter__(self) -> Iterator[SourceDescriptor]:
        return iter(self._descriptors)

    def keys(self) -> tuple[str, ...]:
        return tuple(descriptor.key for descriptor in self._descriptors)

    def get(self, key: str) -> SourceDescriptor:
        descriptor = self._by_key.get(key) or self._by_alias.get(key)
        if descriptor is not None:
            return descriptor
        if key in self._removed:
            raise KeyError(f"Removed ingestion source '{key}': {self._removed[key]}")
        available = ", ".join(self.keys())
        raise KeyError(f"Unknown ingestion source '{key}'. Available sources: {available}")

    def parse_command(self, value: IngestCommandBase | Mapping[str, Any]) -> IngestCommandBase:
        if isinstance(value, IngestCommandBase):
            descriptor = self.get(value.kind)
            return descriptor.command_model.model_validate(value.model_dump())
        kind = value.get("kind")
        if not isinstance(kind, str):
            raise ValueError("Ingestion command requires a string 'kind' discriminator")
        try:
            descriptor = self.get(kind)
        except KeyError as exc:
            raise ValueError(exc.args[0]) from exc
        normalized = dict(value)
        normalized["kind"] = descriptor.key
        return descriptor.command_model.model_validate(normalized)

    def scheduled_descriptors(self) -> tuple[SourceDescriptor, ...]:
        return tuple(descriptor for descriptor in self if descriptor.scheduled)

    def descriptor_for_config(self, source: SourceBase) -> SourceDescriptor:
        matches = [
            descriptor
            for descriptor in self
            if descriptor.config_matcher is not None and descriptor.config_matcher(source)
        ]
        if len(matches) != 1:
            keys = ", ".join(descriptor.key for descriptor in matches) or "none"
            raise ValueError(
                f"Config source type '{source.type}' maps to {len(matches)} descriptors: {keys}"
            )
        return matches[0]

    def validate_config(self, config: SourcesConfig) -> None:
        self.scheduled_sources(config)

    def scheduled_sources(self, config: SourcesConfig) -> list[ConfiguredSource]:
        """Project enabled config through descriptor-owned accessors exactly once."""
        discovered: list[ConfiguredSource] = []
        seen: set[int] = set()
        for descriptor in self.scheduled_descriptors():
            if descriptor.config_accessor is None:
                raise ValueError(f"Scheduled descriptor '{descriptor.key}' has no config accessor")
            for source in descriptor.config_accessor(config):
                if not source.enabled:
                    raise ValueError(
                        f"Descriptor '{descriptor.key}' accessor returned a disabled source"
                    )
                matched = self.descriptor_for_config(source)
                if matched is not descriptor:
                    raise ValueError(
                        f"Descriptor '{descriptor.key}' accessor returned config for "
                        f"'{matched.key}'"
                    )
                identity = id(source)
                if identity in seen:
                    raise ValueError(
                        f"Config source type '{source.type}' was returned by multiple accessors"
                    )
                seen.add(identity)
                discovered.append(
                    ConfiguredSource(
                        command_key=descriptor.key,
                        configuration=source.model_dump(mode="json"),
                    )
                )

        enabled = {id(source) for source in config.sources if source.enabled}
        if seen != enabled:
            missing = [
                source.type
                for source in config.sources
                if source.enabled and id(source) not in seen
            ]
            raise ValueError(
                "Enabled source configuration is not exposed by a scheduled descriptor: "
                + ", ".join(missing)
            )
        return discovered

    def configured_sources(self, config: SourcesConfig) -> list[ConfiguredSource]:
        return self.scheduled_sources(config)

    def _validate(self) -> None:
        if not self._descriptors:
            raise ValueError("SourceRegistry requires at least one descriptor")
        claimed: dict[str, str] = {}
        for descriptor in self._descriptors:
            if not descriptor.key or not descriptor.display_name:
                raise ValueError("Source descriptor requires key and display_name")
            if not callable(descriptor.orchestrator):
                raise ValueError(f"Descriptor '{descriptor.key}' has no orchestrator")
            if not descriptor.emitted_sources:
                raise ValueError(f"Descriptor '{descriptor.key}' has empty emitted_sources")
            if (descriptor.config_matcher is None) != (descriptor.config_accessor is None):
                raise ValueError(
                    f"Descriptor '{descriptor.key}' must define both config matcher and accessor"
                )
            command_kind = descriptor.command_model.model_fields.get("kind")
            if command_kind is None or command_kind.default != descriptor.key:
                raise ValueError(
                    f"Descriptor '{descriptor.key}' does not match its command discriminator"
                )
            for claim in (descriptor.key, *sorted(descriptor.aliases)):
                owner = claimed.get(claim)
                if owner is not None:
                    raise ValueError(
                        f"Source key or alias '{claim}' conflicts between '{owner}' "
                        f"and '{descriptor.key}'"
                    )
                claimed[claim] = descriptor.key
            self._by_key[descriptor.key] = descriptor
            for alias in descriptor.aliases:
                self._by_alias[alias] = descriptor
            for alias, diagnostic in descriptor.removed_aliases.items():
                if alias in claimed or alias in self._removed:
                    raise ValueError(f"Removed alias '{alias}' is claimed more than once")
                self._removed[alias] = diagnostic
        conflicts = set(self._removed).intersection(claimed)
        if conflicts:
            alias = sorted(conflicts)[0]
            raise ValueError(f"Removed alias '{alias}' conflicts with an active source key")


def _after_date(days_back: int | None) -> datetime | None:
    if days_back is None:
        return None
    return datetime.now(UTC) - timedelta(days=days_back)


def _compact(**kwargs: Any) -> dict[str, Any]:
    return {key: value for key, value in kwargs.items() if value is not None}


def _dispatch(name: str, kwargs: Callable[[Any], dict[str, Any]]) -> Orchestrator:
    def run(command: IngestCommandBase) -> IngestionResponse | int:
        from src.ingestion import orchestrator

        return getattr(orchestrator, name)(**kwargs(command))

    return run


def _url_route(command: IngestCommandBase) -> RouteKind:
    assert isinstance(command, UrlIngestCommand)
    if command.routing_mode == "webpage":
        return RouteKind.WEBPAGE
    return classify_url(str(command.url))


def _url_sources(command: IngestCommandBase) -> frozenset[ContentSource]:
    return frozenset({route_to_source(_url_route(command))})


def _is(source_type: type[SourceBase]) -> ConfigMatcher:
    return lambda source: isinstance(source, source_type)


def _websearch(provider: str) -> ConfigMatcher:
    return lambda source: isinstance(source, WebSearchSource) and source.provider == provider


def _get(config_method: str, *, provider: str | None = None) -> ConfigAccessor:
    def access(config: SourcesConfig) -> list[SourceBase]:
        values = list(getattr(config, config_method)())
        if provider is not None:
            values = [value for value in values if getattr(value, "provider", None) == provider]
        return values

    return access


def _default_descriptors() -> tuple[SourceDescriptor, ...]:
    force_date = SourceOptions(supports_force=True, supports_date_range=True)
    force = SourceOptions(supports_force=True)
    return (
        SourceDescriptor(
            "gmail",
            "Gmail",
            GmailIngestCommand,
            _dispatch(
                "ingest_gmail",
                lambda c: _compact(
                    query=c.query,
                    max_results=c.max_items,
                    after_date=_after_date(c.days_back),
                    force_reprocess=c.force_reprocess,
                ),
            ),
            frozenset({ContentSource.GMAIL}),
            True,
            config_matcher=_is(GmailSource),
            config_accessor=_get("get_gmail_sources"),
            options=force_date,
        ),
        SourceDescriptor(
            "rss",
            "RSS",
            RssIngestCommand,
            _dispatch(
                "ingest_rss",
                lambda c: _compact(
                    max_entries_per_feed=c.max_items,
                    after_date=_after_date(c.days_back),
                    force_reprocess=c.force_reprocess,
                ),
            ),
            frozenset({ContentSource.RSS}),
            True,
            config_matcher=_is(RSSSource),
            config_accessor=_get("get_rss_sources"),
            options=force_date,
        ),
        SourceDescriptor(
            "blog",
            "Blogs",
            BlogIngestCommand,
            _dispatch(
                "ingest_blog",
                lambda c: _compact(
                    max_entries_per_source=c.max_items,
                    after_date=_after_date(c.days_back),
                    force_reprocess=c.force_reprocess,
                ),
            ),
            frozenset({ContentSource.BLOG}),
            True,
            config_matcher=_is(BlogSource),
            config_accessor=_get("get_blog_sources"),
            options=force_date,
        ),
        SourceDescriptor(
            "substack",
            "Substack",
            SubstackIngestCommand,
            _dispatch(
                "ingest_substack",
                lambda c: _compact(
                    max_entries_per_source=c.max_items,
                    after_date=_after_date(c.days_back),
                    force_reprocess=c.force_reprocess,
                ),
            ),
            frozenset({ContentSource.SUBSTACK}),
            True,
            config_matcher=_is(SubstackSource),
            config_accessor=_get("get_substack_sources"),
            options=force_date,
        ),
        SourceDescriptor(
            "youtube_playlist",
            "YouTube playlists and channels",
            YouTubePlaylistIngestCommand,
            _dispatch(
                "ingest_youtube_playlist",
                lambda c: _compact(
                    max_videos=c.max_items,
                    after_date=_after_date(c.days_back),
                    force_reprocess=c.force_reprocess,
                    use_oauth=not c.public_only,
                ),
            ),
            frozenset({ContentSource.YOUTUBE}),
            True,
            config_matcher=lambda source: isinstance(
                source, (YouTubePlaylistSource, YouTubeChannelSource)
            ),
            config_accessor=lambda config: [
                *config.get_youtube_playlist_sources(),
                *config.get_youtube_channel_sources(),
            ],
            options=force_date,
        ),
        SourceDescriptor(
            "youtube_rss",
            "YouTube RSS",
            YouTubeRssIngestCommand,
            _dispatch(
                "ingest_youtube_rss",
                lambda c: _compact(
                    max_videos=c.max_items,
                    after_date=_after_date(c.days_back),
                    force_reprocess=c.force_reprocess,
                ),
            ),
            frozenset({ContentSource.YOUTUBE}),
            True,
            config_matcher=_is(YouTubeRSSSource),
            config_accessor=_get("get_youtube_rss_sources"),
            options=force_date,
        ),
        SourceDescriptor(
            "podcast",
            "Podcasts",
            PodcastIngestCommand,
            _dispatch(
                "ingest_podcast",
                lambda c: _compact(
                    max_entries_per_feed=c.max_items,
                    after_date=_after_date(c.days_back),
                    force_reprocess=c.force_reprocess,
                    transcribe=c.transcribe,
                ),
            ),
            frozenset({ContentSource.PODCAST}),
            True,
            config_matcher=_is(PodcastSource),
            config_accessor=_get("get_podcast_sources"),
            options=force_date,
        ),
        SourceDescriptor(
            "x_search",
            "X search",
            XSearchIngestCommand,
            _dispatch(
                "ingest_xsearch",
                lambda c: _compact(
                    prompt=c.prompt,
                    max_threads=c.max_threads,
                    force_reprocess=c.force_reprocess,
                ),
            ),
            frozenset({ContentSource.XSEARCH}),
            True,
            removed_aliases={"xsearch": "use 'x_search'"},
            config_matcher=_websearch("grok"),
            config_accessor=_get("get_websearch_sources", provider="grok"),
            options=force,
        ),
        SourceDescriptor(
            "perplexity_search",
            "Perplexity search",
            PerplexitySearchIngestCommand,
            _dispatch(
                "ingest_perplexity_search",
                lambda c: _compact(
                    prompt=c.prompt,
                    max_results=c.max_items,
                    recency_filter=c.recency,
                    context_size=c.context_size,
                    force_reprocess=c.force_reprocess,
                ),
            ),
            frozenset({ContentSource.PERPLEXITY}),
            True,
            removed_aliases={"perplexity-search": "use 'perplexity_search'"},
            config_matcher=_websearch("perplexity"),
            config_accessor=_get("get_websearch_sources", provider="perplexity"),
            options=force,
        ),
        SourceDescriptor(
            "files",
            "Files",
            FilesIngestCommand,
            _dispatch("ingest_files", lambda c: {}),
            frozenset({ContentSource.FILE_UPLOAD}),
            False,
            options=force,
        ),
        SourceDescriptor(
            "url",
            "URL",
            UrlIngestCommand,
            _dispatch(
                "ingest_url",
                lambda c: _compact(
                    url=str(c.url),
                    title=c.title,
                    tags=c.tags,
                    notes=c.notes,
                    auto_route=c.routing_mode == "auto",
                    force_reprocess=c.force_reprocess,
                ),
            ),
            frozenset({ContentSource.WEBPAGE, ContentSource.RSS, ContentSource.YOUTUBE}),
            False,
            route_resolver=_url_route,
            source_resolver=_url_sources,
            options=force,
        ),
        SourceDescriptor(
            "scholar_search",
            "Semantic Scholar search",
            ScholarSearchIngestCommand,
            _dispatch("ingest_scholar", lambda c: {"max_entries": c.max_items}),
            frozenset({ContentSource.SCHOLAR}),
            True,
            removed_aliases={"scholar": "use 'scholar_search'"},
            config_matcher=_is(ScholarSource),
            config_accessor=_get("get_scholar_sources"),
        ),
        SourceDescriptor(
            "scholar_paper",
            "Semantic Scholar paper",
            ScholarPaperIngestCommand,
            _dispatch(
                "ingest_scholar_paper",
                lambda c: {
                    "identifier": c.identifier,
                    "with_refs": c.with_references,
                },
            ),
            frozenset({ContentSource.SCHOLAR}),
            False,
            removed_aliases={"scholar-paper": "use 'scholar_paper'"},
            options=SourceOptions(requires_identifier=True),
        ),
        SourceDescriptor(
            "scholar_references",
            "Scholar references",
            ScholarReferencesIngestCommand,
            _dispatch(
                "ingest_scholar_refs",
                lambda c: _compact(
                    after=c.after,
                    before=c.before,
                    source_types=c.source_types,
                    dry_run=c.dry_run,
                    limit=c.limit,
                ),
            ),
            frozenset({ContentSource.SCHOLAR}),
            False,
            removed_aliases={"scholar-refs": "use 'scholar_references'"},
            options=SourceOptions(supports_date_range=True, supports_preview=True),
        ),
        SourceDescriptor(
            "arxiv_search",
            "arXiv search",
            ArxivSearchIngestCommand,
            _dispatch(
                "ingest_arxiv",
                lambda c: _compact(
                    max_results=c.max_items,
                    after_date=_after_date(c.days_back),
                    force_reprocess=c.force_reprocess,
                    no_pdf=not c.extract_pdf,
                ),
            ),
            frozenset({ContentSource.ARXIV}),
            True,
            removed_aliases={"arxiv": "use 'arxiv_search'"},
            config_matcher=_is(ArxivSource),
            config_accessor=_get("get_arxiv_sources"),
            options=force_date,
        ),
        SourceDescriptor(
            "arxiv_paper",
            "arXiv paper",
            ArxivPaperIngestCommand,
            _dispatch(
                "ingest_arxiv_paper",
                lambda c: {
                    "identifier": c.identifier,
                    "pdf_extraction": c.extract_pdf,
                    "force_reprocess": c.force_reprocess,
                },
            ),
            frozenset({ContentSource.ARXIV}),
            False,
            removed_aliases={"arxiv-paper": "use 'arxiv_paper'"},
            options=SourceOptions(supports_force=True, requires_identifier=True),
        ),
        SourceDescriptor(
            "huggingface_papers",
            "Hugging Face papers",
            HuggingFacePapersIngestCommand,
            _dispatch(
                "ingest_huggingface_papers",
                lambda c: _compact(
                    max_papers=c.max_items,
                    after_date=_after_date(c.days_back),
                    force_reprocess=c.force_reprocess,
                ),
            ),
            frozenset({ContentSource.HUGGINGFACE_PAPERS}),
            True,
            removed_aliases={"huggingface-papers": "use 'huggingface_papers'"},
            config_matcher=_is(HuggingFacePapersSource),
            config_accessor=_get("get_huggingface_papers_sources"),
            options=force_date,
        ),
        SourceDescriptor(
            "readwise",
            "Readwise",
            ReadwiseIngestCommand,
            _dispatch(
                "ingest_readwise",
                lambda c: _compact(
                    updated_after=c.updated_after,
                    source_types=c.source_types,
                    include_deleted=c.include_deleted,
                    max_books=c.max_books,
                    force_reprocess=c.force_reprocess,
                ),
            ),
            frozenset({ContentSource.READWISE}),
            True,
            config_matcher=_is(ReadwiseSource),
            config_accessor=_get("get_readwise_sources"),
            options=force_date,
        ),
    )


SOURCE_REGISTRY = SourceRegistry(
    _default_descriptors(),
    removed_aliases={
        "youtube": (
            "choose 'youtube_playlist' for configured playlists/channels or 'youtube_rss' for feeds"
        ),
        "youtube-playlist": "use 'youtube_playlist'",
        "youtube-rss": "use 'youtube_rss'",
        "perplexity": "use 'perplexity_search'",
    },
)
