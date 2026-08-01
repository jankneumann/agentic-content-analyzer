"""Contract tests for the Gemini batch persistence migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "1e6a460b6722_add_batch_execution_tables.py"
)


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("batch_processing_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _OperationsRecorder:
    def __init__(self) -> None:
        self.tables: dict[str, tuple[object, ...]] = {}
        self.indexes: dict[str, tuple[str, list[str], dict[str, object]]] = {}

    def create_table(self, name: str, *elements: object) -> None:
        self.tables[name] = elements

    def create_index(self, name: str, table: str, columns: list[str], **kwargs: object) -> None:
        self.indexes[name] = (table, columns, kwargs)


def test_batch_migration_is_based_on_current_workflow_provenance_head():
    migration = _load_migration()

    assert migration.down_revision == "d4e5f6a7b8c9"


def test_migration_graph_has_one_head():
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_heads() == ["7f4a2c9e1b60"]


def test_upgrade_matches_revised_typed_lifecycle_contract(monkeypatch):
    migration = _load_migration()
    recorder = _OperationsRecorder()
    monkeypatch.setattr(migration, "op", recorder)

    migration.upgrade()

    job_elements = recorder.tables["batch_jobs"]
    request_elements = recorder.tables["batch_requests"]
    job_columns = {item.name: item for item in job_elements if isinstance(item, sa.Column)}
    request_columns = {item.name: item for item in request_elements if isinstance(item, sa.Column)}
    job_checks = {
        item.name: str(item.sqltext)
        for item in job_elements
        if isinstance(item, sa.CheckConstraint)
    }
    request_checks = {
        item.name: str(item.sqltext)
        for item in request_elements
        if isinstance(item, sa.CheckConstraint)
    }

    assert "updated_at" in job_columns
    assert "submitting" in job_checks["ck_batch_jobs_state"]
    assert "claimed" in request_checks["ck_batch_requests_status"]
    assert isinstance(request_columns["content_id"].type, sa.BigInteger)
    assert request_columns["content_id"].nullable is True
    foreign_keys = [item for item in request_elements if isinstance(item, sa.ForeignKeyConstraint)]
    content_fk = next(
        constraint
        for constraint in foreign_keys
        if constraint.elements[0].target_fullname == "contents.id"
    )
    assert content_fk.ondelete == "SET NULL"
    assert "target_table" not in request_columns
    assert "target_id" not in request_columns
    assert "fallback_attempts" in request_columns
    assert request_columns["request_key"].type.length >= 128

    provider_job_index = recorder.indexes["uq_batch_jobs_provider_job_name"]
    assert provider_job_index[2]["unique"] is True
    assert "postgresql_where" in provider_job_index[2]
    active_target_index = recorder.indexes["uq_batch_requests_active_target"]
    assert active_target_index[1] == ["model_step", "content_id"]
    assert active_target_index[2]["unique"] is True
    assert "claimed" in str(active_target_index[2]["postgresql_where"])
