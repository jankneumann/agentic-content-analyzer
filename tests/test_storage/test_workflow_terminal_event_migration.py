"""The `system_check` CHECK-constraint relaxation, and the three-copy drift risk.

The DDL for `workflow_terminal_events` exists in THREE places: the Alembic
migration, the ORM `__table_args__` in `src/models/workflow_alert.py`, and the
bootstrap DDL in `src/queue/setup.py`. A relaxation applied to one and not the
others produces a table whose behavior depends on how it happened to be created —
migrated deployments accept the row, bootstrapped ones reject it, and the
rejection is silent (`classification_status='rejected'`, no delivery, no raise).

Widening one or two of the three constraints is no better than widening none: the
row still does not insert. So these tests assert all three arms in all three
copies.

The live round-trip against a real database (reject before, accept after) needs
Postgres — SQLite has no `~` regex operator, which the event-identity constraint
uses — so it skips when no database is reachable and runs in CI.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    REPO_ROOT / "alembic" / "versions" / "c3f1a8b6e40d_admit_system_check_terminal_events.py"
)

CONSTRAINTS = (
    "ck_workflow_terminal_events_source_kind",
    "ck_workflow_terminal_events_event_identity",
    "ck_workflow_terminal_events_source_shape",
)


@pytest.fixture(scope="module")
def migration_source() -> str:
    return MIGRATION_PATH.read_text()


class TestMigrationRelaxesAllThreeConstraints:
    def test_the_migration_exists(self, migration_source: str) -> None:
        assert 'revision: str = "c3f1a8b6e40d"' in migration_source

    @pytest.mark.parametrize("constraint", CONSTRAINTS)
    def test_each_constraint_is_replaced(self, migration_source: str, constraint: str) -> None:
        assert constraint in migration_source

    def test_source_kind_admits_system_check(self, migration_source: str) -> None:
        assert "'system_check'" in migration_source

    def test_event_identity_admits_the_one_key_grammar(self, migration_source: str) -> None:
        assert "^system_check:backup_freshness:[0-9]+$" in migration_source

    def test_source_shape_permits_null_operation_and_reconciliation_identity(
        self, migration_source: str
    ) -> None:
        shape = migration_source.split("_SOURCE_SHAPE_SYSTEM_CHECK")[1]
        for column in (
            "operation_id IS NULL",
            "claim_generation IS NULL",
            "terminal_status IS NULL",
            "reconciliation_action_id IS NULL",
            "reconciliation_run_id IS NULL",
            "reconciliation_content_id IS NULL",
        ):
            assert column in shape

    def test_downgrade_removes_rows_that_cannot_satisfy_the_restored_constraints(
        self, migration_source: str
    ) -> None:
        """A downgrade that left system_check rows behind would fail at constraint
        validation. Deleting them loses alert history, never a backup."""
        downgrade = migration_source.split("def downgrade()")[1]
        assert "DELETE FROM workflow_alert_deliveries" in downgrade
        assert "DELETE FROM workflow_terminal_events" in downgrade
        assert downgrade.index("DELETE FROM workflow_terminal_events") < downgrade.index(
            "_SOURCE_KIND_NARROW"
        )

    def test_downgrade_restores_the_three_kind_constraint(self, migration_source: str) -> None:
        narrow = migration_source.split("_SOURCE_KIND_NARROW = ")[1].split('"""')[1]
        assert "system_check" not in narrow


class TestTheThreeDdlCopiesAgree:
    """The drift this guards against is silent, so it is checked mechanically."""

    @staticmethod
    def _read(relative: str) -> str:
        return (REPO_ROOT / relative).read_text()

    def test_the_orm_model_admits_system_check(self) -> None:
        source = self._read("src/models/workflow_alert.py")
        assert 'SYSTEM_CHECK = "system_check"' in source
        assert "'system_check'" in source

    def test_the_bootstrap_ddl_admits_system_check(self) -> None:
        source = self._read("src/queue/setup.py")
        assert "'system_check'" in source

    @pytest.mark.parametrize("relative", ["src/models/workflow_alert.py", "src/queue/setup.py"])
    def test_every_copy_carries_all_three_system_check_arms(self, relative: str) -> None:
        source = self._read(relative)
        # 1. source_kind list, 2. event-identity grammar, 3. source-shape arm.
        assert re.search(r"source_kind IN \([^)]*'system_check'", source, re.S)
        assert "system_check:backup_freshness:[0-9]+" in source
        assert re.search(r"source_kind = 'system_check' AND operation_id IS NULL", source, re.S)

    def test_the_key_grammar_is_identical_everywhere_including_the_model(self) -> None:
        """A2 — two candidate grammars once disagreed with each other about the
        middle segment. There is one now, and it is asserted to be one."""
        from src.contracts.workflow_alert_models import SYSTEM_CHECK_EVENT_KEY_PATTERN

        grammar = SYSTEM_CHECK_EVENT_KEY_PATTERN
        for relative in (
            "alembic/versions/c3f1a8b6e40d_admit_system_check_terminal_events.py",
            "src/models/workflow_alert.py",
            "src/queue/setup.py",
        ):
            assert grammar in self._read(relative)


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="live constraint round-trip needs Postgres; SQLite has no ~ regex operator",
)
class TestLiveConstraintRoundTrip:
    def test_a_system_check_row_is_accepted_after_the_migration(self) -> None:
        import sqlalchemy

        engine = sqlalchemy.create_engine(os.environ["DATABASE_URL"])
        with engine.begin() as conn:
            conn.execute(
                sqlalchemy.text(
                    "INSERT INTO workflow_terminal_events "
                    "(event_key, source_kind, occurred_at) "
                    "VALUES ('system_check:backup_freshness:1755734400', "
                    "'system_check', NOW())"
                )
            )
            conn.execute(
                sqlalchemy.text(
                    "DELETE FROM workflow_terminal_events "
                    "WHERE event_key = 'system_check:backup_freshness:1755734400'"
                )
            )

    def test_a_malformed_system_check_key_is_still_rejected(self) -> None:
        import sqlalchemy

        engine = sqlalchemy.create_engine(os.environ["DATABASE_URL"])
        with pytest.raises(sqlalchemy.exc.IntegrityError), engine.begin() as conn:
            conn.execute(
                sqlalchemy.text(
                    "INSERT INTO workflow_terminal_events "
                    "(event_key, source_kind, occurred_at) "
                    "VALUES ('system_check:backup_freshness:NOT-EPOCH', "
                    "'system_check', NOW())"
                )
            )

    def test_a_system_check_row_carrying_operation_identity_is_rejected(self) -> None:
        import sqlalchemy

        engine = sqlalchemy.create_engine(os.environ["DATABASE_URL"])
        with pytest.raises(sqlalchemy.exc.IntegrityError), engine.begin() as conn:
            conn.execute(
                sqlalchemy.text(
                    "INSERT INTO workflow_terminal_events "
                    "(event_key, source_kind, operation_id, occurred_at) "
                    "VALUES ('system_check:backup_freshness:1755734400', "
                    "'system_check', 42, NOW())"
                )
            )
