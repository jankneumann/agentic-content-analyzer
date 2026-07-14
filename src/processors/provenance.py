"""Exact persisted content provenance for theme, digest, and podcast processors."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from src.models.content import Content
from src.models.digest import Digest
from src.models.query import (
    SELECTION_SCHEMA_VERSION,
    ResolvedContentItem,
    ResolvedContentSet,
    SelectionPolicy,
    compute_selection_fingerprint,
)
from src.models.summary import Summary
from src.storage.database import get_db


class ProvenanceViolationError(ValueError):
    """Raised when persisted resources do not match their immutable selection."""

    code = "provenance_violation"

    def __init__(self, message: str, *, resource_id: int | None = None) -> None:
        super().__init__(message)
        self.resource_id = resource_id

    def as_tool_result(self) -> str:
        """Return a stable machine-readable tool rejection."""

        import json

        return json.dumps(
            {
                "error": {
                    "type": self.code,
                    "message": str(self),
                    "resource_id": self.resource_id,
                }
            },
            separators=(",", ":"),
            sort_keys=True,
        )


class DigestProvenanceError(ProvenanceViolationError):
    """Raised when a digest cannot prove its exact source selection."""

    code = "incomplete_digest_provenance"


@dataclass(frozen=True)
class LoadedContentItem:
    """One exact Content/Summary pair in resolved selection order."""

    content: Content | Any
    summary: Summary | Any


@dataclass(frozen=True)
class LoadedDigestContext:
    """A validated digest and its exact persisted source snapshot."""

    digest: Digest | Any
    resolved_set: ResolvedContentSet
    items: tuple[LoadedContentItem, ...]


class ExactContentSetLoader:
    """Load only the IDs captured by a resolved set or current digest snapshot."""

    def load(
        self,
        resolved_set: ResolvedContentSet,
        *,
        session: Session | None = None,
    ) -> tuple[LoadedContentItem, ...]:
        """Load and verify exact content/summary pairs without latest-summary joins."""

        expected = compute_selection_fingerprint(
            resolved_set.policy,
            resolved_set.content_ids,
            resolved_set.summary_ids,
        )
        if resolved_set.fingerprint != expected:
            raise ProvenanceViolationError("Resolved content set fingerprint is inconsistent")
        self._validate_unique_ids(
            resolved_set.content_ids,
            resolved_set.summary_ids,
            error_type=ProvenanceViolationError,
        )

        with self._session(session) as db:
            return self._load_ids(
                db,
                resolved_set.content_ids,
                resolved_set.summary_ids,
            )

    def load_digest(
        self,
        digest_id: int,
        *,
        session: Session | None = None,
    ) -> LoadedDigestContext:
        """Load a digest only when its current provenance snapshot is complete."""

        with self._session(session) as db:
            digest = db.query(Digest).filter(Digest.id == digest_id).first()
            if digest is None:
                raise ValueError(f"Digest {digest_id} not found")

            policy_data = digest.selection_policy or {}
            if (
                policy_data.get("schema_version") != SELECTION_SCHEMA_VERSION
                or policy_data.get("provenance") == "legacy-v0"
            ):
                raise DigestProvenanceError(
                    f"Digest {digest_id} has incomplete legacy-v0 provenance",
                    resource_id=digest_id,
                )

            content_ids = tuple(digest.source_content_ids or ())
            summary_ids = tuple(digest.source_summary_ids or ())
            if len(content_ids) != len(summary_ids):
                raise DigestProvenanceError(
                    f"Digest {digest_id} has mismatched content and summary provenance",
                    resource_id=digest_id,
                )
            self._validate_unique_ids(
                content_ids,
                summary_ids,
                error_type=DigestProvenanceError,
                resource_id=digest_id,
            )
            if digest.newsletter_count != len(content_ids):
                raise DigestProvenanceError(
                    f"Digest {digest_id} count does not match its unique content snapshot",
                    resource_id=digest_id,
                )
            if (
                digest.source_content_ids is None
                or digest.source_summary_ids is None
                or digest.selection_fingerprint is None
            ):
                raise DigestProvenanceError(
                    f"Digest {digest_id} has incomplete source provenance",
                    resource_id=digest_id,
                )

            try:
                policy = SelectionPolicy.model_validate(policy_data)
            except ValueError as exc:
                raise DigestProvenanceError(
                    f"Digest {digest_id} has invalid selection policy: {exc}",
                    resource_id=digest_id,
                ) from exc

            expected = compute_selection_fingerprint(policy, content_ids, summary_ids)
            if digest.selection_fingerprint != expected:
                raise DigestProvenanceError(
                    f"Digest {digest_id} selection fingerprint is inconsistent",
                    resource_id=digest_id,
                )

            loaded = self._load_ids(db, content_ids, summary_ids)
            resolved_items: list[ResolvedContentItem] = []
            for loaded_item in loaded:
                content = loaded_item.content
                selection_date = getattr(content, policy.date_basis.value, None)
                if selection_date is None:
                    raise DigestProvenanceError(
                        f"Digest {digest_id} content {content.id} no longer has its selection date",
                        resource_id=digest_id,
                    )
                resolved_items.append(
                    ResolvedContentItem(
                        content_id=content.id,
                        summary_id=loaded_item.summary.id,
                        source_type=content.source_type,
                        title=content.title,
                        publication=content.publication,
                        selection_date=selection_date,
                    )
                )
            resolved_set = ResolvedContentSet(
                policy=policy,
                items=tuple(resolved_items),
                fingerprint=expected,
            )
            return LoadedDigestContext(digest=digest, resolved_set=resolved_set, items=loaded)

    @staticmethod
    def _validate_unique_ids(
        content_ids: Sequence[int],
        summary_ids: Sequence[int],
        *,
        error_type: type[ProvenanceViolationError],
        resource_id: int | None = None,
    ) -> None:
        if len(set(content_ids)) != len(content_ids):
            raise error_type(
                "Content selection contains duplicate IDs",
                resource_id=resource_id,
            )
        if len(set(summary_ids)) != len(summary_ids):
            raise error_type(
                "Summary selection contains duplicate IDs",
                resource_id=resource_id,
            )

    def _load_ids(
        self,
        db: Session,
        content_ids: Sequence[int],
        summary_ids: Sequence[int],
    ) -> tuple[LoadedContentItem, ...]:
        if len(content_ids) != len(summary_ids):
            raise ProvenanceViolationError("Content and summary selections have different lengths")
        if not content_ids:
            return ()

        contents = db.query(Content).filter(Content.id.in_(content_ids)).all()
        summaries = db.query(Summary).filter(Summary.id.in_(summary_ids)).all()
        contents_by_id = {content.id: content for content in contents}
        summaries_by_id = {summary.id: summary for summary in summaries}

        missing_content = [
            content_id for content_id in content_ids if content_id not in contents_by_id
        ]
        missing_summaries = [
            summary_id for summary_id in summary_ids if summary_id not in summaries_by_id
        ]
        if missing_content or missing_summaries:
            raise ProvenanceViolationError(
                "Persisted selection references missing records: "
                f"content={missing_content}, summaries={missing_summaries}"
            )

        loaded: list[LoadedContentItem] = []
        for content_id, summary_id in zip(content_ids, summary_ids, strict=True):
            summary = summaries_by_id[summary_id]
            if summary.content_id != content_id:
                raise ProvenanceViolationError(
                    f"Persisted summary {summary_id} does not belong to content {content_id}"
                )
            loaded.append(LoadedContentItem(contents_by_id[content_id], summary))
        return tuple(loaded)

    @contextmanager
    def _session(self, session: Session | None) -> Iterator[Session]:
        if session is not None:
            yield session
            return
        with get_db() as db:
            yield db
