"""Validation and drift tests for the canonical workflow contracts."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import yaml
from jsonschema.validators import validator_for

ROOT = Path(__file__).parents[2]
CHANGE = ROOT / "openspec/changes/unify-content-workflows-agentic-surfaces"
CONTRACTS = CHANGE / "contracts"
OPENAPI_PATH = CONTRACTS / "openapi/v1.yaml"
GENERATOR = ROOT / "scripts/generate_workflow_contracts.py"

SOURCE_KEYS = {
    "gmail",
    "rss",
    "blog",
    "substack",
    "youtube_playlist",
    "youtube_rss",
    "podcast",
    "x_search",
    "perplexity_search",
    "files",
    "url",
    "scholar_search",
    "scholar_paper",
    "scholar_references",
    "arxiv_search",
    "arxiv_paper",
    "huggingface_papers",
    "readwise",
}

OPERATION_TYPES = {
    "ingestion.execute",
    "summarization.run",
    "theme_analysis.create",
    "digest.create",
    "pipeline.run",
    "podcast_script.create",
    "podcast_audio.create",
    "audio_digest.create",
}


def _openapi() -> dict:
    return cast(dict[str, Any], yaml.safe_load(OPENAPI_PATH.read_text()))


def test_openapi_contract_is_valid() -> None:
    document = _openapi()
    assert document["openapi"] == "3.1.0"
    assert document["info"]["version"] == "2.0.0"
    assert document["paths"]
    for schema in document["components"]["schemas"].values():
        validator_for(schema).check_schema(schema)


def test_ingest_command_discriminator_is_complete() -> None:
    schema = _openapi()["components"]["schemas"]["IngestCommand"]
    assert schema["discriminator"]["propertyName"] == "kind"
    mapping = schema["discriminator"]["mapping"]
    assert set(mapping) == SOURCE_KEYS
    assert len(schema["oneOf"]) == len(SOURCE_KEYS)


def test_operation_handle_contract_is_complete() -> None:
    schemas = _openapi()["components"]["schemas"]
    handle = schemas["OperationHandle"]
    assert set(handle["required"]) >= {
        "schema_version",
        "operation_id",
        "operation_type",
        "status",
        "progress",
        "message",
        "cancellable",
        "retry_count",
        "status_url",
        "events_url",
        "created_at",
    }
    assert set(handle["properties"]["operation_type"]["enum"]) == OPERATION_TYPES
    assert "cancelled" in handle["properties"]["status"]["enum"]
    assert handle["x-operation-result-schemas"]["ingestion.execute"] == {
        "$ref": "#/components/schemas/IngestionResult"
    }


def test_url_contract_preserves_routing_behavior_from_main() -> None:
    schemas = _openapi()["components"]["schemas"]
    url_command = schemas["UrlIngestCommand"]
    assert url_command["properties"]["routing_mode"] == {
        "type": "string",
        "enum": ["auto", "webpage"],
        "default": "auto",
    }
    capability = schemas["SourceCapability"]
    assert "emitted_sources" in capability["required"]
    assert capability["properties"]["emitted_sources"]["minItems"] == 1


def test_operation_routes_cover_status_events_retry_and_cancel() -> None:
    paths = _openapi()["paths"]
    assert "get" in paths["/api/v1/operations/{operation_id}"]
    assert "get" in paths["/api/v1/operations/{operation_id}/events"]
    assert "post" in paths["/api/v1/operations/{operation_id}/retry"]
    assert "post" in paths["/api/v1/operations/{operation_id}/cancel"]


def test_progress_event_schema_is_valid() -> None:
    schema = json.loads((CONTRACTS / "events/operation.progress.schema.json").read_text())
    validator_for(schema).check_schema(schema)
    assert set(schema["required"]) >= {
        "schema_version",
        "operation_id",
        "status",
        "progress",
        "occurred_at",
    }
    openapi_event = _openapi()["components"]["schemas"]["OperationEvent"]
    assert set(openapi_event["required"]) == set(schema["required"])


def test_database_contract_declares_provenance_and_queue_payload() -> None:
    schema = (CONTRACTS / "db/schema.sql").read_text()
    for fragment in (
        "source_summary_ids",
        "selection_fingerprint",
        "selection_policy",
        "source_content_ids_available",
        "source_content_ids_cited",
        "pgqueuer_jobs.payload",
    ):
        assert fragment in schema
    cited_backfill = schema.split("source_content_ids_cited =", 1)[1].split(")", 1)[0]
    assert "newsletter_ids_fetched" not in cited_backfill


def test_generated_contract_files_have_no_drift() -> None:
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_generated_python_contract_imports() -> None:
    generated = CONTRACTS / "generated/models.py"
    spec = importlib.util.spec_from_file_location("canonical_workflow_models", generated)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert set(module.OperationType.__args__) == OPERATION_TYPES
