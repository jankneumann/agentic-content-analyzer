from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).parents[3]


def test_gx10_profile_declares_exact_storage_budget_and_hysteresis_policy() -> None:
    profile = yaml.safe_load((ROOT / "profiles/gx10.yaml").read_text())
    policy = profile["settings"]["gx10"]

    assert policy["component_budgets_percent"] == {
        "application_postgresql": 22,
        "neo4j": 12,
        "clickhouse": 28,
        "minio": 8,
        "backups": 15,
        "redis_and_logs": 2,
    }
    assert sum(policy["component_budgets_percent"].values()) == 87
    assert policy["reserve_percent"] == 13
    assert (
        policy["high_clear_percent"],
        policy["high_watermark_percent"],
        policy["critical_clear_percent"],
        policy["critical_watermark_percent"],
    ) == (75, 80, 85, 90)
    assert policy["hysteresis_minutes"] == 15


def test_storage_governance_has_no_direct_database_file_deletion_primitive() -> None:
    source = (ROOT / "src/services/storage_governance.py").read_text()
    tree = ast.parse(source)
    forbidden_attributes = {"remove", "unlink", "rmtree", "rmdir"}

    assert not [
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in forbidden_attributes
    ]
    assert "DELETE FROM" not in source.upper()
    assert "TRUNCATE " not in source.upper()
    assert "langfuse" not in source.lower() or "schema" not in source.lower()


def test_backup_controller_has_no_plaintext_fallback_or_source_delete_primitive() -> None:
    source = (ROOT / "src/services/backup/gx10.py").read_text()
    tree = ast.parse(source)
    forbidden_attributes = {"remove", "unlink", "rmtree", "rmdir"}

    assert not [
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in forbidden_attributes
    ]
    assert "plaintext_fallback" not in source
    assert "DELETE FROM" not in source.upper()


@pytest.mark.parametrize(
    "script",
    [
        "scripts/gx10/storage/simulate_policy.py",
        "scripts/gx10/backup/validate_restore_drill.py",
    ],
)
def test_checkpoint_scripts_are_bounded_python_entrypoints(script: str) -> None:
    source = (ROOT / script).read_text()
    tree = ast.parse(source)

    assert "if __name__ == \"__main__\":" in source
    assert any(isinstance(node, ast.FunctionDef) and node.name == "main" for node in ast.walk(tree))
    assert "shell=True" not in source


def test_checkpoint_scripts_never_embed_direct_database_mutation() -> None:
    source = "\n".join(
        (ROOT / path).read_text()
        for path in (
            "scripts/gx10/storage/simulate_policy.py",
            "scripts/gx10/backup/validate_restore_drill.py",
        )
    ).upper()

    assert "DELETE FROM" not in source
    assert "TRUNCATE " not in source
    assert "PGDATA" not in source
