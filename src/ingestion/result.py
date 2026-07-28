"""Canonical ingestion response envelope.

Used by all `aca ingest *` commands and the corresponding HTTP / MCP
endpoints to produce a consistent JSON response shape across transports.

Services that previously emitted per-source outcome dataclasses now build
an ``IngestionResponse`` directly (typically via
``build_response_from_source_results``); the legacy ``on_result`` callback
parameters on a few orchestrator entry points still pass this same envelope
for backward compatibility and will be removed once all CLI direct paths
consume the canonical envelope from the return value.

Design notes
------------
- ``model_config = ConfigDict(extra="ignore")`` — Postel's law for
  forward compatibility: emitters write the full envelope; consumers
  ignore unknown fields. Drift detection is opt-in via the strict
  fixture ``IngestionResponse.model_validate_strict`` (see below) used
  in cross-transport contract tests. Without ``extra="ignore"`` the
  ``success`` computed field would prevent ``model_dump → model_validate``
  round-trips, breaking the very testing pattern the envelope exists to
  support.

- ``status`` is the canonical success/failure signal. ``success`` is
  exposed as a ``@computed_field`` derived from ``status != "error"``
  for backward compatibility with consumers keying on the boolean.
  Removal planned for ``schema_version`` 2.

- ``items_ingested`` / ``items_skipped`` / ``items_failed`` are mutually
  exclusive categories. Their sum equals the total items the orchestrator
  *attempted* to process. ``_validate_status_invariants`` enforces:
    - ``status="ok"`` ⇒ ``errors == []`` AND ``items_failed == 0``
    - ``status="error"`` ⇒ ``items_ingested == 0`` AND
      (``len(errors) > 0`` OR ``items_failed > 0``)
    - ``status="partial"`` ⇒ ``items_ingested > 0`` AND
      (``len(errors) > 0`` OR ``items_failed > 0``)

  Either ``errors`` or ``items_failed > 0`` is a valid "something went
  wrong" signal — services that increment ``items_failed`` without
  emitting an ``IngestionError`` entry (e.g. logged-and-counted parse
  failures) are representable, even though attaching a corresponding
  error is strongly preferred for debuggability.

  Categorization policy:
    - ``items_ingested``: items successfully persisted to the DB.
    - ``items_skipped``: items intentionally not persisted — deduplicated,
      filtered out, paywalled without auth, blocked by robots.txt.
    - ``items_failed``: items that errored mid-processing — parse failure,
      LLM call failure, persistence error. Each typically warrants a
      corresponding ``IngestionError`` entry pointing at the offending URL.
    - Source-level failures (a feed returned HTTP 5xx, OAuth expired,
      RSS XML malformed before any item parse) belong in ``errors`` with
      no ``items_failed`` increment — there were no items to fail.

  Per-item failure tracking is wired through ``SourceFetchResult.items_failed``
  / ``item_errors`` (per-source) and the ``extra_item_errors`` /
  ``extra_items_failed`` parameters on ``build_response_from_source_results``
  (for service-level cross-source failures, e.g. RSS persistence happens
  in a flat post-fetch loop). Sources still being migrated to the envelope
  (substack, podcast, youtube, etc.) emit only an item count today; their
  ``items_failed`` will populate as they cut over.

- ``schema_version`` is a MAJOR version integer. Minor / additive field
  additions do NOT bump it (consumers ignore unknown fields). Bump only
  on breaking changes (renamed fields, removed fields, semantic changes
  to existing fields). Currently 1; planned bump to 2 when ``success``
  computed field is removed.

- ``details`` is the per-command escape hatch for command-specific extras.
  Reserved key names (every command MUST use these names if it carries
  the corresponding signal):
    - ``citations`` — list of citation/source URLs (xsearch, perplexity)
    - ``query_echo`` — string of the resolved search query (xsearch, perplexity)
    - ``dry_run`` — bool flag (scholar-refs --dry-run mode)
    - ``papers_ingested`` — int subset of items_ingested counted as papers (scholar-refs)
  Per-command typed sub-models may follow in a later PR; reserving the
  names now prevents 11 commands from inventing 11 different keys for
  the same concept. Source-level redirects/failures should use top-level
  ``warnings`` / ``errors`` rather than ``details``.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

IngestionStatus = Literal["ok", "partial", "error"]

_ACTIVE_PUBLIC_SOURCE_KEYS: ContextVar[Mapping[str, str] | None] = ContextVar(
    "active_public_source_keys",
    default=None,
)


@contextmanager
def use_public_source_keys(keys: Mapping[str, str]) -> Iterator[None]:
    """Carry natural-to-public configured identity without exposing locators."""

    token = _ACTIVE_PUBLIC_SOURCE_KEYS.set(dict(keys))
    try:
        yield
    finally:
        _ACTIVE_PUBLIC_SOURCE_KEYS.reset(token)


def public_source_key_for(source: object) -> str | None:
    """Look up configured public identity from an explicit source model."""

    keys = _ACTIVE_PUBLIC_SOURCE_KEYS.get()
    if keys is None:
        return None
    from src.config.sources import SourceBase, source_key

    if not isinstance(source, (SourceBase, dict)):
        return None
    return keys.get(source_key(source))


# Closed registry of canonical ``command`` values. New transports/services
# adding an ingest path MUST add their identifier here so cross-transport
# contract tests can assert agreement. Subcommand naming uses hyphen-case;
# command identifier is always ``ingest.<subcommand>``.
IngestionCommandLiteral = Literal[
    "ingest.gmail",
    "ingest.rss",
    "ingest.blog",
    "ingest.substack",
    "ingest.youtube",
    "ingest.youtube-rss",
    "ingest.youtube-playlist",
    "ingest.podcast",
    "ingest.xsearch",
    "ingest.perplexity-search",
    "ingest.huggingface-papers",
    "ingest.scholar",
    "ingest.scholar-paper",
    "ingest.scholar-refs",
    "ingest.arxiv",
    "ingest.arxiv-paper",
    "ingest.files",
    "ingest.url",
    "ingest.readwise",
]

# Closed registry of canonical ``source`` identifiers. Note the two
# inconsistencies the ingestion subsystem inherited from history and which
# this Literal codifies (rather than silently letting them drift further):
#   - ``perplexity-search`` subcommand emits ``source: "perplexity"``
#   - Multi-word sources use ``snake_case`` (``huggingface_papers``,
#     ``arxiv_paper``) while compound subcommands keep ``hyphen-case``
#     (``scholar-refs``, ``youtube-rss``)
IngestionSourceLiteral = Literal[
    "gmail",
    "rss",
    "blog",
    "substack",
    "youtube",
    "youtube-rss",
    "youtube-playlist",
    "podcast",
    "xsearch",
    "perplexity",
    "huggingface_papers",
    "scholar",
    "scholar_paper",
    "scholar-refs",
    "arxiv",
    "arxiv_paper",
    "files",
    "url",
    "readwise",
]


class IngestionError(BaseModel):
    """Structured error entry on the response envelope."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    url: str | None = None


class IngestionWarning(BaseModel):
    """Structured warning entry — non-fatal signal (redirects, deprecations, quota)."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    url: str | None = None
    redirected_to: str | None = None


class BoundedIngestionDiagnostic(BaseModel):
    """Sanitized diagnostic safe for durable configured-source outcomes."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)
    redirected_source_key: str | None = Field(
        default=None,
        pattern=r"^src_[a-f0-9]{20}$",
    )


class ConfiguredSourceResult(BaseModel):
    """Bounded per-configured-source result carrying only opaque identity."""

    model_config = ConfigDict(extra="forbid")

    source_key: str = Field(pattern=r"^src_[a-f0-9]{20}$")
    status: IngestionStatus
    items_ingested: int = Field(ge=0)
    items_failed: int = Field(ge=0)
    errors: list[BoundedIngestionDiagnostic] = Field(default_factory=list, max_length=20)
    warnings: list[BoundedIngestionDiagnostic] = Field(default_factory=list, max_length=20)
    errors_omitted: int = Field(default=0, ge=0)
    warnings_omitted: int = Field(default=0, ge=0)


@dataclass
class SourceFetchResult:
    """Canonical per-source outcome accumulator.

    Used by ingestion services as a per-source diagnostic record while
    fetching content; the service then passes a list of these to
    ``build_response_from_source_results`` to construct the canonical
    ``IngestionResponse`` envelope.

    Field semantics:
      - ``url`` / ``name``: identifies the source (feed URL, channel,
        playlist, subscription, etc.).
      - ``success``: source-level success flag — flips to False when the
        outer fetch (HTTP error, OAuth expired, malformed feed before any
        item parses) fails. Surfaces as an ``IngestionError`` on the envelope.
      - ``items_fetched``: items successfully persisted from this source.
      - ``error`` / ``error_type``: populated when ``success=False``;
        ``error_type`` becomes the ``IngestionError.code`` on the envelope.
      - ``items_failed`` / ``item_errors``: per-item failure tracking
        (e.g. one feed entry parsed badly while others succeeded). Each
        ``item_errors`` entry should map 1:1 to a count in ``items_failed``,
        though the helper accepts the ``items_failed > 0`` signal alone.
      - ``redirected_to``: optional, set when the source URL was followed
        through an HTTP 30x to a new canonical URL. Surfaces as an
        ``IngestionWarning`` (``code="feed_redirected"``) on the envelope.
        Generic across HTTP-fetched sources; today only RSS sets it.

    The ``build_response_from_source_results`` helper consumes this via
    duck-typing (``getattr(r, "items_failed", 0)`` etc.), so service-specific
    extensions or omissions (e.g. YouTube currently never increments
    ``items_failed``) are tolerated without breaking the contract.
    """

    url: str
    name: str | None = None
    success: bool = True
    items_fetched: int = 0
    error: str | None = None
    error_type: str | None = None
    items_failed: int = 0
    item_errors: list[IngestionError] = field(default_factory=list)
    redirected_to: str | None = None
    public_source_key: str | None = None

    @property
    def is_redirect(self) -> bool:
        return self.redirected_to is not None


class IngestionResponse(BaseModel):
    """Canonical envelope for ingest command responses (CLI / HTTP / MCP)."""

    model_config = ConfigDict(extra="ignore")

    schema_version: int = 1
    """Major version. Additive field changes do not bump this; consumers
    ignore unknown fields. Bump only on breaking changes."""

    command: IngestionCommandLiteral
    """Fully-qualified command identifier, e.g. ``ingest.gmail``. Closed
    registry — see ``IngestionCommandLiteral``. New commands must register."""

    source: IngestionSourceLiteral
    """Source identifier — typically matches the subcommand, but may differ
    (e.g. ``perplexity-search`` subcommand emits ``source: "perplexity"``).
    Closed registry — see ``IngestionSourceLiteral``."""

    status: IngestionStatus

    items_ingested: int = 0
    """Items successfully persisted. Mutually exclusive with skipped/failed."""

    items_skipped: int = 0
    """Items deduplicated, filtered out, or otherwise not persisted by design.
    Mutually exclusive with ingested/failed."""

    items_failed: int = 0
    """Items that errored during processing. Mutually exclusive with
    ingested/skipped. Note: source-level failures (e.g. a feed that 500'd
    before any items could be parsed) belong in ``errors``, not here."""

    duration_ms: int | None = None
    """Wall-clock duration in milliseconds, or None if not measured.
    For CLI direct mode: orchestrator runtime. For HTTP mode: end-to-end
    request including queueing. Consumers needing finer-grained timing
    should query Langfuse via ``trace_id``."""

    started_at: datetime | None = None
    """When the command began executing, in UTC. Combined with ``duration_ms``,
    enables timeline plotting and Langfuse correlation."""

    trace_id: str | None = None
    """Langfuse / OTel trace ID for correlating this command with backend
    observability. Populated by the CLI from env / generated UUID; HTTP
    transport reads from the ``traceparent`` request header."""

    errors: list[IngestionError] = Field(default_factory=list)
    warnings: list[IngestionWarning] = Field(default_factory=list)
    source_outcomes: list[ConfiguredSourceResult] = Field(default_factory=list, max_length=100)
    source_outcomes_omitted: int = Field(default=0, ge=0)

    details: dict[str, Any] = Field(default_factory=dict)
    """Command-specific extras. See module docstring for reserved key names."""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def success(self) -> bool:
        """Backward-compatibility boolean derived from ``status``.

        Consumers should prefer ``status`` (three-state) for richer signal.
        Retained for one major version to ease migration of downstream
        consumers (web UI, agentic-assistant); planned for removal when
        ``schema_version`` bumps to 2.
        """
        # TODO(schema_v2): remove this computed field; bump schema_version=2
        return self.status != "error"

    @model_validator(mode="after")
    def _validate_status_invariants(self) -> Self:
        """Enforce status / items / errors consistency per docstring contract."""
        if self.status == "ok":
            if self.errors:
                raise ValueError(
                    "status='ok' incompatible with non-empty errors; "
                    "use 'partial' if some items succeeded, 'error' if none did"
                )
            if self.items_failed > 0:
                raise ValueError(
                    "status='ok' incompatible with items_failed > 0; "
                    "use 'partial' if some items succeeded despite failures"
                )
        elif self.status == "error":
            if self.items_ingested > 0:
                raise ValueError(
                    "status='error' requires items_ingested == 0; "
                    "use 'partial' when some items landed despite errors"
                )
            if not self.errors and self.items_failed == 0:
                raise ValueError(
                    "status='error' requires errors or items_failed > 0; "
                    "consumers need at least one failure signal"
                )
        elif self.status == "partial":
            if self.items_ingested == 0:
                raise ValueError(
                    "status='partial' requires items_ingested > 0; "
                    "use 'error' when nothing was persisted"
                )
            if not self.errors and self.items_failed == 0:
                raise ValueError(
                    "status='partial' requires errors or items_failed > 0; "
                    "use 'ok' when no failures occurred"
                )
        return self

    def with_timing(self, *, duration_ms: int, started_at: datetime) -> Self:
        """Return a copy with transport-side timing fields populated, re-validated.

        Use this at transport boundaries (CLI direct mode, HTTP handler, MCP
        tool wrapper) to augment a service-built envelope with wall-clock
        timing measured at the transport. Unlike raw ``model_copy(update=...)``
        which skips validators by design, ``with_timing`` re-runs the full
        validator chain so future schema changes that introduce timing-aware
        invariants (e.g. "duration_ms > 0 if status='ok'") cannot be silently
        bypassed.

        Today the validator does not depend on either field, so the cost is
        a small Pydantic round-trip; the value is forward compatibility.
        """
        return self.model_validate(
            {**self.model_dump(), "duration_ms": duration_ms, "started_at": started_at}
        )

    @classmethod
    def model_validate_strict(cls, payload: dict[str, Any]) -> Self:
        """Strict validation for cross-transport drift detection.

        Unlike ``model_validate``, this rejects unknown top-level fields.
        Use in contract tests that assert the envelope is exactly the
        documented shape (no transport has silently added a field).
        """
        unknown = set(payload.keys()) - set(cls.model_fields.keys()) - {"success"}
        if unknown:
            raise ValueError(
                f"Unknown fields in IngestionResponse payload: {sorted(unknown)}. "
                f"Either add them to the model or remove from the emitter."
            )
        return cls.model_validate(payload)


def derive_status(
    *,
    items_ingested: int,
    items_failed: int,
    errors: list[IngestionError],
) -> IngestionStatus:
    """Compute the canonical three-state status from items + failure signals.

    Single-shot services (perplexity, xsearch, scholar-paper, arxiv-paper,
    files-loop) that don't aggregate per-source ``SourceFetchResult`` records
    call this directly; ``build_response_from_source_results`` calls it
    internally. Centralizing in one place ensures any future invariant tweak
    (e.g. "status='ok' requires items_ingested >= 1") only needs to land here
    instead of at every emitter site.

    Status rules (mirroring ``_validate_status_invariants`` on the model):
      - ``ok`` — no errors AND items_failed == 0
      - ``partial`` — items_ingested > 0 AND (errors OR items_failed > 0)
      - ``error`` — items_ingested == 0 AND (errors OR items_failed > 0)
    """
    has_failure = bool(errors) or items_failed > 0
    if not has_failure:
        return "ok"
    if items_ingested > 0:
        return "partial"
    return "error"


def build_response_from_source_results(
    *,
    command: IngestionCommandLiteral,
    source: IngestionSourceLiteral,
    items_ingested: int,
    source_results: list[Any],
    extra_item_errors: list[IngestionError] | None = None,
    extra_items_failed: int = 0,
) -> IngestionResponse:
    """Construct an IngestionResponse from an ingestion service's per-source diagnostics.

    Shared helper for ingestion services (RSS, blog, HuggingFace papers, etc.)
    to convert their internal ``SourceFetchResult`` accumulator into the
    canonical envelope.

    Each ``source_results`` entry is duck-typed:
      - Required: ``url``, ``success``
      - For source-level failures: ``error`` / ``error_type``
      - Optional redirect signal: ``redirected_to`` (RSS-style sources)
      - Optional per-item failure counters (added during the harmonization
        rollout): ``items_failed: int`` and ``item_errors: list[IngestionError]``

    ``extra_item_errors`` / ``extra_items_failed`` carry per-item failures
    that occur at the service level — outside any single ``SourceFetchResult``
    boundary (e.g. RSS persists to the DB in a flat loop after all fetches
    return, so a persistence error can't naturally attribute to one source).

    Status is derived from items_ingested vs. the union of all failure
    signals (source-level errors + item-level errors + items_failed counters).
    """
    errors: list[IngestionError] = []
    warnings: list[IngestionWarning] = []
    raw_source_outcomes: list[dict[str, Any]] = []
    items_failed = extra_items_failed

    for r in source_results:
        source_errors: list[IngestionError] = []
        source_warnings: list[IngestionWarning] = []
        if not getattr(r, "success", True):
            source_errors.append(
                IngestionError(
                    code=getattr(r, "error_type", None) or "fetch_error",
                    message=getattr(r, "error", None) or "unknown fetch error",
                    url=getattr(r, "url", None),
                )
            )
            errors.extend(source_errors)
        redirected_to = getattr(r, "redirected_to", None)
        if redirected_to:
            source_warnings.append(
                IngestionWarning(
                    code="feed_redirected",
                    message=f"Source redirected to {redirected_to}",
                    url=getattr(r, "url", None),
                    redirected_to=redirected_to,
                )
            )
            warnings.extend(source_warnings)
        source_items_failed = getattr(r, "items_failed", 0)
        source_item_errors = list(getattr(r, "item_errors", []))
        items_failed += source_items_failed
        errors.extend(source_item_errors)
        source_errors.extend(source_item_errors)

        public_source_key = getattr(r, "public_source_key", None)
        if public_source_key is not None:
            source_items_ingested = getattr(r, "items_fetched", 0)
            raw_source_outcomes.append(
                {
                    "source_key": public_source_key,
                    "status": derive_status(
                        items_ingested=source_items_ingested,
                        items_failed=source_items_failed,
                        errors=source_errors,
                    ),
                    "items_ingested": source_items_ingested,
                    "items_failed": source_items_failed,
                    "errors": source_errors,
                    "warnings": source_warnings,
                }
            )

    if extra_item_errors:
        errors.extend(extra_item_errors)

    from src.ingestion.result_sanitizer import sanitize_ingestion_metadata

    source_projection = sanitize_ingestion_metadata(source_outcomes=raw_source_outcomes)
    return IngestionResponse(
        command=command,
        source=source,
        status=derive_status(
            items_ingested=items_ingested, items_failed=items_failed, errors=errors
        ),
        items_ingested=items_ingested,
        items_failed=items_failed,
        errors=errors,
        warnings=warnings,
        source_outcomes=[
            ConfiguredSourceResult.model_validate(value)
            for value in source_projection["source_outcomes"]
        ],
        source_outcomes_omitted=source_projection["source_outcomes_omitted"],
    )
