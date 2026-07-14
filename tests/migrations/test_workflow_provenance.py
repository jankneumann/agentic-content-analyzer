"""Migration coverage for durable digest and podcast provenance."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import Engine

from src.models.digest import Digest, DigestData, DigestType
from src.models.podcast import PodcastScriptRecord


def _load_migration() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[2]
    migrations = list(repo_root.glob("alembic/versions/*workflow_provenance*.py"))
    assert len(migrations) == 1, "expected exactly one workflow provenance migration"

    spec = importlib.util.spec_from_file_location("workflow_provenance_migration", migrations[0])
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json_table(name: str, *columns: sa.Column) -> sa.Table:
    metadata = sa.MetaData()
    return sa.Table(name, metadata, *columns)


def test_provenance_migration_round_trip_preserves_legacy_semantics() -> None:
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    digests = sa.Table(
        "digests",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_content_ids", sa.JSON, nullable=True),
    )
    scripts = sa.Table(
        "podcast_scripts",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("digest_id", sa.Integer, nullable=False),
        sa.Column("newsletter_ids_available", sa.JSON, nullable=True),
        sa.Column("newsletter_ids_fetched", sa.JSON, nullable=True),
    )
    jobs = sa.Table(
        "pgqueuer_jobs",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("payload", sa.JSON, nullable=True),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(digests.insert(), {"id": 1, "source_content_ids": [12, 10, 12]})
        connection.execute(
            scripts.insert(),
            {
                "id": 1,
                "digest_id": 1,
                "newsletter_ids_available": [10, 12],
                "newsletter_ids_fetched": [10],
            },
        )
        connection.execute(
            jobs.insert(),
            {"id": 1, "payload": {"schema_version": 1, "operation_type": "legacy"}},
        )

        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        migration.upgrade()  # The additive deployment migration is restart-safe.

        # A migration-first deployment and application rollback both leave legacy
        # writers unaware of the additive columns. Database defaults must keep
        # those writes valid until old workers have drained.
        connection.execute(digests.insert(), {"id": 2, "source_content_ids": [20]})
        connection.execute(
            scripts.insert(),
            {
                "id": 2,
                "digest_id": 2,
                "newsletter_ids_available": [20],
                "newsletter_ids_fetched": [20],
            },
        )

        inspector = sa.inspect(connection)
        digest_columns = {column["name"]: column for column in inspector.get_columns("digests")}
        script_columns = {
            column["name"]: column for column in inspector.get_columns("podcast_scripts")
        }
        assert digest_columns["source_summary_ids"]["nullable"] is False
        assert digest_columns["selection_policy"]["nullable"] is False
        assert digest_columns["source_summary_ids"]["default"] is not None
        assert digest_columns["selection_policy"]["default"] is not None
        assert {
            "source_content_ids_available",
            "source_content_ids_cited",
            "selection_fingerprint",
        } <= script_columns.keys()
        assert script_columns["source_content_ids_available"]["nullable"] is False
        assert script_columns["source_content_ids_cited"]["nullable"] is False
        assert script_columns["source_content_ids_available"]["default"] is not None
        assert script_columns["source_content_ids_cited"]["default"] is not None

        migrated_digests = _json_table(
            "digests",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("source_content_ids", sa.JSON),
            sa.Column("source_summary_ids", sa.JSON),
            sa.Column("selection_policy", sa.JSON),
            sa.Column("selection_fingerprint", sa.String(64)),
        )
        migrated_scripts = _json_table(
            "podcast_scripts",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("source_content_ids_available", sa.JSON),
            sa.Column("source_content_ids_cited", sa.JSON),
            sa.Column("selection_fingerprint", sa.String(64)),
        )
        digest_row = (
            connection.execute(sa.select(migrated_digests).where(migrated_digests.c.id == 1))
            .mappings()
            .one()
        )
        script_row = (
            connection.execute(sa.select(migrated_scripts).where(migrated_scripts.c.id == 1))
            .mappings()
            .one()
        )
        legacy_digest_row = (
            connection.execute(sa.select(migrated_digests).where(migrated_digests.c.id == 2))
            .mappings()
            .one()
        )
        legacy_script_row = (
            connection.execute(sa.select(migrated_scripts).where(migrated_scripts.c.id == 2))
            .mappings()
            .one()
        )

        assert digest_row["source_summary_ids"] == []
        assert digest_row["selection_policy"]["provenance"] == "legacy-v0"
        assert digest_row["selection_fingerprint"] == migration._selection_fingerprint(
            digest_row["selection_policy"], [12, 10, 12], []
        )
        assert script_row["source_content_ids_available"] == [10, 12]
        # A fetched legacy item was tool context, not necessarily a model citation.
        assert script_row["source_content_ids_cited"] == []
        assert script_row["selection_fingerprint"] == digest_row["selection_fingerprint"]
        assert legacy_digest_row["source_summary_ids"] == []
        assert legacy_digest_row["selection_policy"]["provenance"] == "legacy-v0"
        assert legacy_script_row["source_content_ids_available"] == []
        assert legacy_script_row["source_content_ids_cited"] == []

        indexes = {index["name"] for index in inspector.get_indexes("digests")}
        assert "ix_digests_selection_fingerprint" in indexes
        script_indexes = {index["name"] for index in inspector.get_indexes("podcast_scripts")}
        assert "ix_podcast_scripts_selection_fingerprint" in script_indexes

        # Reusing the queue does not introduce a competing operation table or mutate payloads.
        assert "operations" not in inspector.get_table_names()
        assert connection.execute(sa.select(jobs.c.payload)).scalar_one() == {
            "schema_version": 1,
            "operation_type": "legacy",
        }

        migration.downgrade()
        downgraded = sa.inspect(connection)
        assert "source_summary_ids" not in {
            column["name"] for column in downgraded.get_columns("digests")
        }
        assert "source_content_ids_available" not in {
            column["name"] for column in downgraded.get_columns("podcast_scripts")
        }
        assert "newsletter_ids_fetched" in {
            column["name"] for column in downgraded.get_columns("podcast_scripts")
        }


def test_postgresql_defaults_accept_legacy_writes(test_engine: Engine) -> None:
    """Exercise the deployed PostgreSQL schema through a pre-migration write shape."""

    if test_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL test database is not available")

    with test_engine.connect() as connection, connection.begin() as transaction:
        metadata = sa.MetaData()
        digests = sa.Table("digests", metadata, autoload_with=connection)
        scripts = sa.Table("podcast_scripts", metadata, autoload_with=connection)
        now = datetime.now(UTC)
        digest_id = connection.execute(
            digests.insert()
            .values(
                digest_type="DAILY",
                period_start=now,
                period_end=now,
                title="Legacy PostgreSQL writer",
                executive_overview="Pre-migration insert shape",
                strategic_insights=[],
                technical_developments=[],
                emerging_trends=[],
                actionable_recommendations={},
                sources=[],
                source_content_ids=[31],
                newsletter_count=1,
                status="PENDING",
                created_at=now,
                agent_framework="test",
                model_used="test",
            )
            .returning(digests.c.id)
        ).scalar_one()
        script_id = connection.execute(
            scripts.insert()
            .values(
                digest_id=digest_id,
                length="brief",
                newsletter_ids_available=[31],
                newsletter_ids_fetched=[31],
            )
            .returning(scripts.c.id)
        ).scalar_one()

        digest_defaults = connection.execute(
            sa.select(
                digests.c.source_summary_ids,
                digests.c.selection_policy,
            ).where(digests.c.id == digest_id)
        ).one()
        script_defaults = connection.execute(
            sa.select(
                scripts.c.source_content_ids_available,
                scripts.c.source_content_ids_cited,
            ).where(scripts.c.id == script_id)
        ).one()

        assert digest_defaults.source_summary_ids == []
        assert digest_defaults.selection_policy["provenance"] == "legacy-v0"
        assert script_defaults.source_content_ids_available == []
        assert script_defaults.source_content_ids_cited == []
        transaction.rollback()


def test_legacy_fingerprint_is_deterministic_and_order_sensitive() -> None:
    migration = _load_migration()
    policy = migration._legacy_policy()

    first = migration._selection_fingerprint(policy, [1, 2], [])
    assert first == migration._selection_fingerprint(policy, [1, 2], [])
    assert first != migration._selection_fingerprint(policy, [2, 1], [])
    assert len(first) == 64


def test_orm_models_expose_additive_provenance_fields() -> None:
    assert {
        "source_summary_ids",
        "selection_fingerprint",
        "selection_policy",
    } <= set(Digest.__table__.columns.keys())
    assert {
        "source_content_ids_available",
        "source_content_ids_cited",
        "selection_fingerprint",
    } <= set(PodcastScriptRecord.__table__.columns.keys())

    digest = DigestData(
        digest_type=DigestType.DAILY,
        period_start=datetime(2026, 7, 12),
        period_end=datetime(2026, 7, 13),
        title="Legacy caller",
        executive_overview="Existing creation path",
        newsletter_count=0,
        agent_framework="test",
        model_used="test",
    )
    assert digest.source_summary_ids == []
    assert digest.selection_policy["provenance"] == "legacy-v0"
