"""Add durable theme, digest, and podcast workflow provenance.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-14
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")

_OPERATION_OWNED_TABLES = (
    "theme_analyses",
    "digests",
    "podcast_scripts",
    "podcasts",
    "audio_digests",
)


def _legacy_policy() -> dict[str, Any]:
    return {
        "schema_version": 0,
        "provenance": "legacy-v0",
        "date_basis": "published_date",
        "start_inclusive": True,
        "end_exclusive": False,
    }


def _selection_fingerprint(
    policy: dict[str, Any], content_ids: list[int], summary_ids: list[int]
) -> str:
    payload = {
        "schema_version": 1,
        "policy": policy,
        "content_ids": content_ids,
        "summary_ids": summary_ids,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _columns(bind: sa.Connection, table_name: str) -> dict[str, dict[str, Any]]:
    return {
        str(column["name"]): dict(column)
        for column in sa.inspect(bind).get_columns(table_name)
    }


def _indexes(bind: sa.Connection, table_name: str) -> set[str]:
    return {
        str(index["name"])
        for index in sa.inspect(bind).get_indexes(table_name)
        if index["name"] is not None
    }


def _ensure_operation_ownership(bind: sa.Connection, table_name: str) -> None:
    """Add restart-safe ownership used to recover resources after worker crashes."""

    if "operation_id" not in _columns(bind, table_name):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(sa.Column("operation_id", sa.BigInteger(), nullable=True))

    index_name = f"ix_{table_name}_operation_id"
    if index_name not in _indexes(bind, table_name):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_index(index_name, ["operation_id"], unique=True)


def _drop_operation_ownership(bind: sa.Connection, table_name: str) -> None:
    """Remove ownership independently so a repeated downgrade remains safe."""

    columns = _columns(bind, table_name)
    index_name = f"ix_{table_name}_operation_id"
    indexes = _indexes(bind, table_name)
    if "operation_id" not in columns and index_name not in indexes:
        return
    with op.batch_alter_table(table_name) as batch_op:
        if index_name in indexes:
            batch_op.drop_index(index_name)
        if "operation_id" in columns:
            batch_op.drop_column("operation_id")


def _backfill_digests(bind: sa.Connection) -> None:
    digests = sa.table(
        "digests",
        sa.column("id", sa.Integer()),
        sa.column("source_content_ids", _JSON),
        sa.column("source_summary_ids", _JSON),
        sa.column("selection_policy", _JSON),
        sa.column("selection_fingerprint", sa.String(64)),
    )
    rows = bind.execute(
        sa.select(
            digests.c.id,
            digests.c.source_content_ids,
            digests.c.source_summary_ids,
            digests.c.selection_policy,
            digests.c.selection_fingerprint,
        )
    ).mappings()
    for row in rows:
        policy = row["selection_policy"] or _legacy_policy()
        content_ids = list(row["source_content_ids"] or [])
        summary_ids = list(row["source_summary_ids"] or [])
        fingerprint = row["selection_fingerprint"] or _selection_fingerprint(
            policy, content_ids, summary_ids
        )
        bind.execute(
            digests.update()
            .where(digests.c.id == row["id"])
            .values(
                source_summary_ids=summary_ids,
                selection_policy=policy,
                selection_fingerprint=fingerprint,
            )
        )


def _backfill_theme_analyses(bind: sa.Connection) -> None:
    analyses = sa.table(
        "theme_analyses",
        sa.column("id", sa.Integer()),
        sa.column("content_ids", _JSON),
        sa.column("summary_ids", _JSON),
        sa.column("selection_policy", _JSON),
        sa.column("selection_fingerprint", sa.String(64)),
    )
    rows = bind.execute(
        sa.select(
            analyses.c.id,
            analyses.c.content_ids,
            analyses.c.summary_ids,
            analyses.c.selection_policy,
            analyses.c.selection_fingerprint,
        )
    ).mappings()
    for row in rows:
        policy = row["selection_policy"] or _legacy_policy()
        content_ids = list(row["content_ids"] or [])
        summary_ids = list(row["summary_ids"] or [])
        fingerprint = row["selection_fingerprint"] or _selection_fingerprint(
            policy, content_ids, summary_ids
        )
        bind.execute(
            analyses.update()
            .where(analyses.c.id == row["id"])
            .values(
                summary_ids=summary_ids,
                selection_policy=policy,
                selection_fingerprint=fingerprint,
            )
        )


def _backfill_podcast_scripts(bind: sa.Connection) -> None:
    digests = sa.table(
        "digests",
        sa.column("id", sa.Integer()),
        sa.column("selection_fingerprint", sa.String(64)),
    )
    scripts = sa.table(
        "podcast_scripts",
        sa.column("id", sa.Integer()),
        sa.column("digest_id", sa.Integer()),
        sa.column("newsletter_ids_available", _JSON),
        sa.column("source_content_ids_available", _JSON),
        sa.column("source_content_ids_cited", _JSON),
        sa.column("selection_fingerprint", sa.String(64)),
    )
    digest_fingerprints: dict[int, str | None] = {
        int(row.id): row.selection_fingerprint
        for row in bind.execute(
            sa.select(digests.c.id, digests.c.selection_fingerprint)
        )
    }
    rows = bind.execute(
        sa.select(
            scripts.c.id,
            scripts.c.digest_id,
            scripts.c.newsletter_ids_available,
            scripts.c.source_content_ids_available,
            scripts.c.source_content_ids_cited,
            scripts.c.selection_fingerprint,
        )
    ).mappings()
    for row in rows:
        available = row["source_content_ids_available"]
        if available is None:
            available = list(row["newsletter_ids_available"] or [])
        # Legacy fetched IDs only prove tool access. They do not prove citation.
        cited = row["source_content_ids_cited"]
        if cited is None:
            cited = []
        fingerprint = row["selection_fingerprint"] or digest_fingerprints.get(row["digest_id"])
        bind.execute(
            scripts.update()
            .where(scripts.c.id == row["id"])
            .values(
                source_content_ids_available=available,
                source_content_ids_cited=cited,
                selection_fingerprint=fingerprint,
            )
        )


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    empty_list_default = "[]"
    legacy_policy_json = json.dumps(
        _legacy_policy(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    legacy_policy_default = legacy_policy_json

    for table_name in _OPERATION_OWNED_TABLES:
        if table_name in tables:
            _ensure_operation_ownership(bind, table_name)

    if "theme_analyses" in tables:
        columns = _columns(bind, "theme_analyses")
        with op.batch_alter_table("theme_analyses") as batch_op:
            if "summary_ids" not in columns:
                batch_op.add_column(sa.Column("summary_ids", _JSON, nullable=True))
            if "selection_fingerprint" not in columns:
                batch_op.add_column(
                    sa.Column("selection_fingerprint", sa.String(length=64), nullable=True)
                )
            if "selection_policy" not in columns:
                batch_op.add_column(sa.Column("selection_policy", _JSON, nullable=True))

        _backfill_theme_analyses(bind)
        columns = _columns(bind, "theme_analyses")
        with op.batch_alter_table("theme_analyses") as batch_op:
            if columns["summary_ids"]["nullable"] or columns["summary_ids"]["default"] is None:
                batch_op.alter_column(
                    "summary_ids",
                    existing_type=_JSON,
                    nullable=False,
                    server_default=empty_list_default,
                )
            if (
                columns["selection_policy"]["nullable"]
                or columns["selection_policy"]["default"] is None
            ):
                batch_op.alter_column(
                    "selection_policy",
                    existing_type=_JSON,
                    nullable=False,
                    server_default=legacy_policy_default,
                )
            if "ix_theme_analyses_selection_fingerprint" not in _indexes(
                bind, "theme_analyses"
            ):
                batch_op.create_index(
                    "ix_theme_analyses_selection_fingerprint",
                    ["selection_fingerprint"],
                    unique=False,
                )

    if "digests" in tables:
        columns = _columns(bind, "digests")
        with op.batch_alter_table("digests") as batch_op:
            if "source_summary_ids" not in columns:
                batch_op.add_column(sa.Column("source_summary_ids", _JSON, nullable=True))
            if "selection_fingerprint" not in columns:
                batch_op.add_column(
                    sa.Column("selection_fingerprint", sa.String(length=64), nullable=True)
                )
            if "selection_policy" not in columns:
                batch_op.add_column(sa.Column("selection_policy", _JSON, nullable=True))

        _backfill_digests(bind)
        columns = _columns(bind, "digests")
        with op.batch_alter_table("digests") as batch_op:
            if (
                columns["source_summary_ids"]["nullable"]
                or columns["source_summary_ids"]["default"] is None
            ):
                batch_op.alter_column(
                    "source_summary_ids",
                    existing_type=_JSON,
                    nullable=False,
                    server_default=empty_list_default,
                )
            if (
                columns["selection_policy"]["nullable"]
                or columns["selection_policy"]["default"] is None
            ):
                batch_op.alter_column(
                    "selection_policy",
                    existing_type=_JSON,
                    nullable=False,
                    server_default=legacy_policy_default,
                )
            if "ix_digests_selection_fingerprint" not in _indexes(bind, "digests"):
                batch_op.create_index(
                    "ix_digests_selection_fingerprint", ["selection_fingerprint"], unique=False
                )

    if "podcast_scripts" in tables:
        columns = _columns(bind, "podcast_scripts")
        with op.batch_alter_table("podcast_scripts") as batch_op:
            if "source_content_ids_available" not in columns:
                batch_op.add_column(
                    sa.Column("source_content_ids_available", _JSON, nullable=True)
                )
            if "source_content_ids_cited" not in columns:
                batch_op.add_column(sa.Column("source_content_ids_cited", _JSON, nullable=True))
            if "selection_fingerprint" not in columns:
                batch_op.add_column(
                    sa.Column("selection_fingerprint", sa.String(length=64), nullable=True)
                )

        _backfill_podcast_scripts(bind)
        columns = _columns(bind, "podcast_scripts")
        with op.batch_alter_table("podcast_scripts") as batch_op:
            if (
                columns["source_content_ids_available"]["nullable"]
                or columns["source_content_ids_available"]["default"] is None
            ):
                batch_op.alter_column(
                    "source_content_ids_available",
                    existing_type=_JSON,
                    nullable=False,
                    server_default=empty_list_default,
                )
            if (
                columns["source_content_ids_cited"]["nullable"]
                or columns["source_content_ids_cited"]["default"] is None
            ):
                batch_op.alter_column(
                    "source_content_ids_cited",
                    existing_type=_JSON,
                    nullable=False,
                    server_default=empty_list_default,
                )
            if "ix_podcast_scripts_selection_fingerprint" not in _indexes(
                bind, "podcast_scripts"
            ):
                batch_op.create_index(
                    "ix_podcast_scripts_selection_fingerprint",
                    ["selection_fingerprint"],
                    unique=False,
                )

    if bind.dialect.name == "postgresql":
        if "theme_analyses" in tables:
            op.execute(
                "COMMENT ON COLUMN theme_analyses.summary_ids IS "
                "'Ordered persisted Summary IDs paired with content_ids'"
            )
            op.execute(
                "COMMENT ON COLUMN theme_analyses.selection_fingerprint IS "
                "'SHA-256 fingerprint of normalized policy, content IDs, and summary IDs'"
            )
            op.execute(
                "COMMENT ON COLUMN theme_analyses.selection_policy IS "
                "'Normalized workflow selection policy including schema version and date basis'"
            )
        op.execute(
            "COMMENT ON COLUMN digests.source_summary_ids IS "
            "'Ordered persisted Summary IDs paired with source_content_ids'"
        )
        op.execute(
            "COMMENT ON COLUMN digests.selection_fingerprint IS "
            "'SHA-256 fingerprint of normalized policy, content IDs, and summary IDs'"
        )
        op.execute(
            "COMMENT ON COLUMN digests.selection_policy IS "
            "'Normalized workflow selection policy including schema version and date basis'"
        )
        if "pgqueuer_jobs" in tables:
            op.execute(
                "COMMENT ON COLUMN pgqueuer_jobs.payload IS "
                "'Versioned operation payload: schema_version, operation_type, input, progress, "
                "message, cancel_requested, resource, result'"
            )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    for table_name in _OPERATION_OWNED_TABLES:
        if table_name in tables:
            _drop_operation_ownership(bind, table_name)

    if "theme_analyses" in tables:
        columns = _columns(bind, "theme_analyses")
        with op.batch_alter_table("theme_analyses") as batch_op:
            if "ix_theme_analyses_selection_fingerprint" in _indexes(
                bind, "theme_analyses"
            ):
                batch_op.drop_index("ix_theme_analyses_selection_fingerprint")
            for column_name in (
                "selection_policy",
                "selection_fingerprint",
                "summary_ids",
            ):
                if column_name in columns:
                    batch_op.drop_column(column_name)

    if "podcast_scripts" in tables:
        columns = _columns(bind, "podcast_scripts")
        with op.batch_alter_table("podcast_scripts") as batch_op:
            if "ix_podcast_scripts_selection_fingerprint" in _indexes(
                bind, "podcast_scripts"
            ):
                batch_op.drop_index("ix_podcast_scripts_selection_fingerprint")
            for column_name in (
                "selection_fingerprint",
                "source_content_ids_cited",
                "source_content_ids_available",
            ):
                if column_name in columns:
                    batch_op.drop_column(column_name)
    if "digests" in tables:
        columns = _columns(bind, "digests")
        with op.batch_alter_table("digests") as batch_op:
            if "ix_digests_selection_fingerprint" in _indexes(bind, "digests"):
                batch_op.drop_index("ix_digests_selection_fingerprint")
            for column_name in (
                "selection_policy",
                "selection_fingerprint",
                "source_summary_ids",
            ):
                if column_name in columns:
                    batch_op.drop_column(column_name)
