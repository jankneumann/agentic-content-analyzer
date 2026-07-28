"""Validation and drift tests for the canonical workflow contracts."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast, get_args

import pytest
import yaml
from jsonschema.validators import validator_for
from pydantic import TypeAdapter, ValidationError

ROOT = Path(__file__).parents[2]
CONTRACTS = ROOT / "openspec/contracts/content-workflows"
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


def _generated_models() -> Any:
    generated = CONTRACTS / "generated/models.py"
    spec = importlib.util.spec_from_file_location("canonical_workflow_models", generated)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_contract_source_is_outside_change_lifecycle() -> None:
    relative_path = CONTRACTS.relative_to(ROOT / "openspec")
    assert relative_path.parts == ("contracts", "content-workflows")


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


def test_scheduled_date_commands_support_an_absolute_lower_bound() -> None:
    schemas = _openapi()["components"]["schemas"]
    for name in (
        "GmailIngestCommand",
        "RssIngestCommand",
        "BlogIngestCommand",
        "SubstackIngestCommand",
        "YouTubePlaylistIngestCommand",
        "YouTubeRssIngestCommand",
        "PodcastIngestCommand",
        "ArxivSearchIngestCommand",
        "HuggingFacePapersIngestCommand",
    ):
        schema = schemas[name]
        properties = dict(schema.get("properties", {}))
        for part in schema.get("allOf", []):
            if "$ref" in part:
                properties.update(schemas[part["$ref"].rsplit("/", 1)[-1]]["properties"])
            else:
                properties.update(part.get("properties", {}))
        assert properties["after_date"] == {
            "type": "string",
            "format": "date-time",
        }


def test_scheduled_commands_support_an_immutable_source_snapshot() -> None:
    schemas = _openapi()["components"]["schemas"]
    for name in (
        "GmailIngestCommand",
        "RssIngestCommand",
        "BlogIngestCommand",
        "SubstackIngestCommand",
        "YouTubePlaylistIngestCommand",
        "YouTubeRssIngestCommand",
        "PodcastIngestCommand",
        "XSearchIngestCommand",
        "PerplexitySearchIngestCommand",
        "ScholarSearchIngestCommand",
        "ArxivSearchIngestCommand",
        "HuggingFacePapersIngestCommand",
        "ReadwiseIngestCommand",
    ):
        schema = schemas[name]
        properties = dict(schema.get("properties", {}))
        for part in schema.get("allOf", []):
            if "$ref" in part:
                properties.update(schemas[part["$ref"].rsplit("/", 1)[-1]]["properties"])
            else:
                properties.update(part.get("properties", {}))
        assert properties["configured_sources"]["type"] == "array"
        assert properties["configured_sources"]["items"] == {
            "type": "object",
            "additionalProperties": True,
        }
        assert properties["configured_sources"]["readOnly"] is True
        assert properties["configured_sources"]["x-internal"] is True


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
    assert handle["properties"]["status"] == {"$ref": "#/components/schemas/OperationStatus"}
    assert "cancelled" in schemas["OperationStatus"]["enum"]
    assert handle["x-operation-result-schemas"]["ingestion.execute"] == {
        "$ref": "#/components/schemas/IngestionResult"
    }
    assert handle["x-operation-result-schemas"]["pipeline.run"] == {
        "$ref": "#/components/schemas/PipelineResultV2"
    }


def test_ingestion_result_contract_preserves_untagged_v1_and_strict_v2() -> None:
    schemas = _openapi()["components"]["schemas"]
    result = schemas["IngestionResult"]
    assert "discriminator" not in result
    assert result["oneOf"] == [
        {"$ref": "#/components/schemas/IngestionResultV1"},
        {"$ref": "#/components/schemas/IngestionResultV2"},
    ]
    assert "schema_version" not in schemas["IngestionResultV1"]["required"]
    assert schemas["IngestionResultV1"]["properties"]["schema_version"]["default"] == 1
    assert schemas["IngestionResultV1"]["additionalProperties"] is False
    assert schemas["IngestionResultV2"]["properties"]["schema_version"] == {
        "type": "integer",
        "const": 2,
    }
    assert "unknown" in schemas["IngestionOutcome"]["enum"]


def test_public_ingestion_projection_is_bounded_and_opaque() -> None:
    schemas = _openapi()["components"]["schemas"]
    result = schemas["IngestionResultV2"]
    assert result["additionalProperties"] is False
    assert result["x-max-serialized-metadata-bytes"] == 65_536
    assert result["properties"]["errors"]["maxItems"] == 20
    assert result["properties"]["warnings"]["maxItems"] == 20
    assert result["properties"]["source_outcomes"]["maxItems"] == 100
    assert {
        "errors_omitted",
        "warnings_omitted",
        "source_outcomes_omitted",
        "details_omitted",
    } <= set(result["required"])

    diagnostic = schemas["BoundedDiagnostic"]
    assert diagnostic["properties"]["code"]["maxLength"] == 100
    assert diagnostic["properties"]["message"]["maxLength"] == 500
    source = schemas["ConfiguredSourceOutcome"]
    assert source["properties"]["source_key"]["pattern"] == "^src_[a-f0-9]{20}$"
    assert "source_key" in source["required"]
    assert schemas["SafeIngestionDetails"]["additionalProperties"] is False

    history = schemas["IngestionHistoryItem"]
    assert history["additionalProperties"] is False
    assert not {
        "content_ids",
        "details",
        "errors",
        "warnings",
        "result",
        "checkpoint",
    } & set(history["properties"])
    assert schemas["IngestionHistoryPage"]["properties"]["data"]["maxItems"] == 100


def test_pipeline_and_history_contracts_have_stable_typed_summaries() -> None:
    document = _openapi()
    schemas = document["components"]["schemas"]
    assert schemas["PipelineResultV2"]["properties"]["ingestion_summary"] == {
        "$ref": "#/components/schemas/PipelineIngestionSummary"
    }
    assert schemas["PipelineIngestionSummary"]["required"] == [
        "outcome",
        "sources",
        "sources_omitted",
    ]
    assert schemas["OperationPage"]["properties"]["data"]["items"] == {
        "$ref": "#/components/schemas/OperationSummary"
    }
    assert document["paths"]["/api/v1/ingestions"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/IngestionHistoryPage"}
    history_status = next(
        parameter
        for parameter in document["paths"]["/api/v1/ingestions"]["get"]["parameters"]
        if parameter["name"] == "status"
    )
    assert history_status["schema"] == {"$ref": "#/components/schemas/TerminalOperationStatus"}
    history_parameters = {
        parameter["name"]: parameter["schema"]
        for parameter in document["paths"]["/api/v1/ingestions"]["get"]["parameters"]
        if "name" in parameter
    }
    assert "command_key" in history_parameters
    assert "source" not in history_parameters
    assert history_parameters["created_after"]["maxLength"] == 64
    assert history_parameters["created_before"]["maxLength"] == 64
    operation_parameters = {
        parameter["name"]: parameter["schema"]
        for parameter in document["paths"]["/api/v1/operations"]["get"]["parameters"]
        if "name" in parameter
    }
    assert operation_parameters["status"] == {"$ref": "#/components/schemas/OperationStatus"}
    assert set(schemas["OperationSummary"]["properties"]) <= set(
        schemas["OperationHandle"]["properties"]
    )
    assert not {"resource", "result", "problem"} & set(schemas["OperationSummary"]["properties"])
    history = schemas["IngestionHistoryItem"]
    assert history["properties"]["items_ingested"]["type"] == ["integer", "null"]
    assert history["properties"]["items_skipped"]["type"] == ["integer", "null"]
    assert history["properties"]["items_failed"]["type"] == ["integer", "null"]
    assert history["properties"]["command_key"]["maxLength"] == 100
    assert history["properties"]["problem_code"]["maxLength"] == 100


def test_named_enum_aliases_and_v1_v2_union_generate_runtime_types() -> None:
    module = _generated_models()
    assert set(get_args(module.IngestionOutcome)) == {
        "success",
        "zero_items",
        "partial",
        "failed",
        "cancelled",
        "unknown",
    }
    assert set(get_args(module.TerminalOperationStatus)) == {
        "completed",
        "failed",
        "cancelled",
    }

    legacy = TypeAdapter(module.IngestionResult).validate_python(
        {
            "command_key": "rss",
            "resolved_route": "rss",
            "emitted_sources": ["rss"],
            "items_ingested": 4,
            "content_ids": [11, 12],
            "details": {"legacy_extension": True},
        }
    )
    assert isinstance(legacy, module.IngestionResultV1)
    assert legacy.schema_version == 1
    assert legacy.details == {"legacy_extension": True}

    with pytest.raises(ValidationError):
        TypeAdapter(module.IngestionResult).validate_python(
            {
                "command_key": "rss",
                "resolved_route": "rss",
                "emitted_sources": ["rss"],
                "items_ingested": 4,
                "content_ids": [11, 12],
                "legacy_extension": True,
            }
        )

    with pytest.raises(ValidationError):
        TypeAdapter(module.IngestionResult).validate_python(
            {
                "schema_version": 2,
                "command_key": "rss",
                "resolved_route": "rss",
                "emitted_sources": ["rss"],
                "status": "ok",
                "outcome": "success",
                "items_ingested": 1,
                "items_skipped": 0,
                "items_failed": 0,
                "content_ids": [11],
                "errors": [],
                "warnings": [],
                "errors_omitted": 0,
                "warnings_omitted": 0,
                "source_outcomes": [],
                "source_outcomes_omitted": 0,
                "details": {},
                "details_omitted": 0,
                "unexpected": True,
            }
        )


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
    assert "get" in paths["/api/v1/operations"]
    assert "get" in paths["/api/v1/operations/{operation_id}"]
    assert "get" in paths["/api/v1/operations/{operation_id}/events"]
    assert "post" in paths["/api/v1/operations/{operation_id}/retry"]
    assert "post" in paths["/api/v1/operations/{operation_id}/cancel"]


def test_agent_facing_discovery_contracts_use_cursor_pages() -> None:
    document = _openapi()
    paths = document["paths"]
    schemas = document["components"]["schemas"]

    assert paths["/api/v1/operations"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/OperationPage"}
    assert paths["/api/v1/configured-sources"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/ConfiguredSourcePage"}
    assert schemas["OperationPage"]["properties"]["next_cursor"] == {
        "type": ["string", "null"],
        "maxLength": 2048,
    }
    configured = schemas["ConfiguredSource"]
    assert "url" not in configured["required"]
    assert set(configured["required"]) >= {
        "key",
        "command_key",
        "source_type",
        "configuration",
    }


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
        "ALTER TABLE theme_analyses",
        "summary_ids",
        "ix_theme_analyses_selection_fingerprint",
    ):
        assert fragment in schema
    cited_backfill = schema.split("source_content_ids_cited =", 1)[1].split(")", 1)[0]
    assert "newsletter_ids_fetched" not in cited_backfill

    assert "ALTER COLUMN summary_ids SET DEFAULT '[]'::jsonb" in schema
    assert "ALTER COLUMN selection_policy SET DEFAULT" in schema


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
    module = _generated_models()
    assert set(module.OperationType.__args__) == OPERATION_TYPES
    assert all(
        "configured_sources" not in command["properties"]
        for command in module.COMMAND_FIELD_SCHEMAS.values()
    )
    assert "configured_sources" in module.GmailIngestCommand.model_fields


def test_generated_typescript_omits_internal_scheduler_fields() -> None:
    generated = (CONTRACTS / "generated/types.ts").read_text()
    assert "configured_sources" not in generated


def test_generated_typescript_declares_named_unions_and_type_checks() -> None:
    generated = CONTRACTS / "generated/types.ts"
    source = generated.read_text()
    assert "export type IngestionResult = IngestionResultV1 | IngestionResultV2;" in source
    assert "export type IngestionOutcome =" in source
    assert "export interface OperationSummary" in source
    result = subprocess.run(
        [
            str(ROOT / "web/node_modules/.bin/tsc"),
            "--noEmit",
            "--skipLibCheck",
            "--target",
            "ES2022",
            str(generated),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
