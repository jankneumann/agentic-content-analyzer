"""Contract tests for the vendored change-graph document schema.

The schema is vendored rather than fetched so that projection is deterministic
and works offline.  Vendoring only stays honest if something proves the copy
still matches its source, so these tests pin three things:

1. the runtime copy inside the skill is byte-identical to the OpenSpec
   contract record, which is the governance artifact;
2. the copy is byte-identical to the installed npm package, when node_modules
   is present (the renderer validates against that copy, and two validators
   disagreeing is the failure mode vendoring is meant to prevent);
3. documents authored upstream still validate here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arch_utils import change_graph

REPO_ROOT = Path(__file__).resolve().parents[5]
SKILL_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "change"

OPENSPEC_CONTRACTS = (
    REPO_ROOT
    / "openspec"
    / "changes"
    / "change-visualization-graph-document"
    / "contracts"
)
INSTALLED_SCHEMA = (
    REPO_ROOT
    / "web"
    / "node_modules"
    / "@coldtea"
    / "pr-lens-schema"
    / "json-schema"
    / "graph-doc.schema.json"
)


# --------------------------------------------------------------------------
# Vendoring integrity
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["graph-doc.schema.json", "corrections.schema.json"]
)
def test_runtime_copy_matches_openspec_contract_record(name: str) -> None:
    """The skill's runtime schema is the same bytes as the governance record."""
    runtime = (SKILL_ROOT / "contracts" / name).read_bytes()
    record = (OPENSPEC_CONTRACTS / name).read_bytes()
    assert runtime == record, (
        f"{name} drifted between the skill copy and the OpenSpec contract "
        "record; re-vendor both from the pinned package"
    )


def test_vendored_schema_declares_the_expected_contract_version() -> None:
    schema = json.loads(change_graph.SCHEMA_PATH.read_text())
    assert schema["version"] == change_graph.CONTRACT_VERSION


@pytest.mark.skipif(
    not INSTALLED_SCHEMA.exists(),
    reason="web/node_modules is not installed; run pnpm install to check this",
)
def test_vendored_schema_matches_the_installed_package() -> None:
    assert change_graph.SCHEMA_PATH.read_bytes() == INSTALLED_SCHEMA.read_bytes()


# --------------------------------------------------------------------------
# Validation behaviour
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture", ["minimal.graph.json", "postmark-refactor.graph.json"]
)
def test_upstream_example_documents_validate(fixture: str) -> None:
    document = json.loads((FIXTURES / fixture).read_text())
    errors = change_graph.validation_errors(document)
    assert errors == []


def test_unknown_field_is_rejected() -> None:
    document = json.loads((FIXTURES / "minimal.graph.json").read_text())
    document["blastRadius"] = "everything"

    errors = change_graph.validation_errors(document)

    assert errors, "an unknown top-level field must be rejected"
    assert any("blastRadius" in error for error in errors)


def test_wrong_contract_version_is_rejected_naming_both_versions() -> None:
    document = json.loads((FIXTURES / "minimal.graph.json").read_text())
    document["schemaVersion"] = "0.2.0"

    with pytest.raises(change_graph.ContractVersionError) as excinfo:
        change_graph.validate_document(document)

    message = str(excinfo.value)
    assert "0.2.0" in message
    assert change_graph.CONTRACT_VERSION in message


def test_write_document_rejects_and_writes_a_sidecar(tmp_path: Path) -> None:
    """A document that fails validation is never written to its final path."""
    document = json.loads((FIXTURES / "minimal.graph.json").read_text())
    document["nodes"][0]["lane"] = "no-such-lane"
    target = tmp_path / "graph.json"

    with pytest.raises(change_graph.DocumentInvalidError):
        change_graph.write_document(target, document)

    assert not target.exists()
    sidecar = tmp_path / "graph.rejected.json"
    assert sidecar.exists()
    rejected = json.loads(sidecar.read_text())
    assert rejected["document"]["title"] == document["title"]
    assert any("no-such-lane" in error for error in rejected["errors"])


def test_write_document_is_deterministic(tmp_path: Path) -> None:
    document = json.loads((FIXTURES / "minimal.graph.json").read_text())

    first = change_graph.write_document(tmp_path / "a.json", document)
    second = change_graph.write_document(tmp_path / "b.json", document)

    assert first.read_bytes() == second.read_bytes()
