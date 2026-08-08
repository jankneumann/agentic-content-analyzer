"""Ingress and knowledge-base export remain separate ownership domains."""

from __future__ import annotations

import ast
from pathlib import Path


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_obsidian_ingress_and_exporter_do_not_import_one_another() -> None:
    root = Path(__file__).resolve().parents[2]
    adapter_imports = _imports(root / "src/ingestion/obsidian_adapter.py")
    exporter_imports = _imports(root / "src/sync/obsidian_exporter.py")
    assert "src.sync.obsidian_exporter" not in adapter_imports
    assert "src.ingestion.obsidian_adapter" not in exporter_imports
