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
GX10_CONTRACTS = ROOT / "openspec/changes/gx10-full-operation-observability/contracts"
RECONCILIATION_SCHEMA_PATH = (
    ROOT
    / "openspec/changes/stuck-content-sweeper-and-requeue-cli/contracts/reconciliation-report.schema.json"
)

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
    "obsidian_vault",
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


def test_obsidian_vault_ingest_command_is_public_strict_and_bounded() -> None:
    schemas = _openapi()["components"]["schemas"]
    schema = schemas["ObsidianVaultIngestCommand"]

    assert schema["additionalProperties"] is False
    assert schema["required"] == ["kind", "source_key"]
    assert schema["properties"]["kind"] == {"type": "string", "const": "obsidian_vault"}
    assert schema["properties"]["source_key"] == {
        "type": "string",
        "pattern": "^src_[a-f0-9]{20}$",
    }
    assert schema["properties"]["max_items"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 10_000,
    }
    assert schema["properties"]["force_reprocess"] == {
        "type": "boolean",
        "default": False,
    }
    assert schema["properties"]["configured_source_version"] == {
        "type": "string",
        "pattern": "^[a-f0-9]{64}$",
        "readOnly": True,
        "x-internal": True,
    }
    assert not {
        "vault_id",
        "vault_path",
        "ingest_folder",
        "path",
        "note_path",
        "note_name",
    } & set(schema["properties"])


def test_configured_source_contract_exposes_typed_readiness() -> None:
    schema = _openapi()["components"]["schemas"]["ConfiguredSource"]

    assert {"ready", "readiness_code"} <= set(schema["required"])
    assert schema["properties"]["ready"] == {"type": "boolean", "default": True}
    assert schema["properties"]["readiness_code"] == {
        "type": ["string", "null"],
        "default": None,
    }


def test_content_query_source_types_match_persisted_content_sources() -> None:
    from src.models.content import ContentSource

    source_type_schema = _openapi()["components"]["schemas"]["ContentQuery"]["properties"][
        "source_types"
    ]["items"]
    expected = {source.value for source in ContentSource}

    assert set(source_type_schema["enum"]) == expected

    generated = _generated_models()
    query = generated.ContentQuery(source_types=[ContentSource.OBSIDIAN.value])
    assert query.source_types == ["obsidian"]

    for path in (
        CONTRACTS / "generated/types.ts",
        ROOT / "web/src/generated/workflow-contracts.ts",
    ):
        content_query = (
            path.read_text().split("export interface ContentQuery", 1)[1].split("}", 1)[0]
        )
        assert '"obsidian"' in content_query


def test_generated_obsidian_vault_command_has_python_typescript_and_runtime_parity() -> None:
    module = _generated_models()
    runtime_contract = __import__(
        "src.contracts.workflow_models", fromlist=["ObsidianVaultIngestCommand"]
    )
    runtime_commands = __import__("src.ingestion.commands", fromlist=["ObsidianVaultIngestCommand"])
    payload = {
        "kind": "obsidian_vault",
        "source_key": "src_0123456789abcdef0123",
        "max_items": 25,
        "force_reprocess": True,
    }

    command = TypeAdapter(module.IngestCommand).validate_python(payload)
    assert isinstance(command, module.ObsidianVaultIngestCommand)
    assert command.model_dump(exclude_none=True) == payload
    internal = module.ObsidianVaultIngestCommand.model_validate(
        {**payload, "configured_source_version": "a" * 64}
    )
    assert internal.configured_source_version == "a" * 64
    assert (
        runtime_commands.ObsidianVaultIngestCommand is runtime_contract.ObsidianVaultIngestCommand
    )
    assert runtime_commands.ObsidianVaultIngestCommand in runtime_commands.COMMAND_MODELS

    for invalid in (
        {**payload, "source_key": "obsidian_vault:personal"},
        {**payload, "max_items": 0},
        {**payload, "max_items": 10_001},
        {**payload, "configured_source_version": "a" * 63},
        {**payload, "vault_path": "/private/vault"},
        {**payload, "ingest_folder": "Inbox"},
        {**payload, "note_path": "Inbox/private.md"},
    ):
        with pytest.raises(ValidationError):
            TypeAdapter(module.IngestCommand).validate_python(invalid)

    generated_typescript = (CONTRACTS / "generated/types.ts").read_text()
    runtime_typescript = (ROOT / "web/src/generated/workflow-contracts.ts").read_text()
    for source in (generated_typescript, runtime_typescript):
        interface = source.split("export interface ObsidianVaultIngestCommand", 1)[1].split("}", 1)[
            0
        ]
        assert 'kind: "obsidian_vault";' in interface
        assert "source_key: string;" in interface
        assert "max_items?: number;" in interface
        assert "force_reprocess?: boolean;" in interface
        assert "configured_sources" not in interface
        assert "configured_source_version" not in interface
        assert "vault_path" not in interface
        assert "ingest_folder" not in interface
        assert "ObsidianVaultIngestCommand" in source.split("export type IngestCommand =", 1)[1]


def test_obsidian_ingestion_response_literals_are_registered() -> None:
    from src.ingestion.result import IngestionResponse

    response = IngestionResponse(
        command="ingest.obsidian-vault",
        source="obsidian",
        status="ok",
    )

    assert response.command == "ingest.obsidian-vault"
    assert response.source == "obsidian"


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


def test_content_reconciliation_request_defaults_to_one_bounded_dry_run_page() -> None:
    schemas = _openapi()["components"]["schemas"]
    request = schemas["ContentReconciliationRequest"]

    assert request["additionalProperties"] is False
    assert request.get("required", []) == []
    assert request["properties"] == {
        "apply": {"type": "boolean", "default": False},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        # int4 max, not int8: contents.id is an integer column, and asyncpg
        # infers $1 from `c.id > $1`, so a wider declared bound is a promise the
        # database refuses to keep.
        "after_content_id": {
            "type": ["integer", "null"],
            "minimum": 1,
            "maximum": 2_147_483_647,
        },
    }


def test_content_reconciliation_openapi_matches_change_contract() -> None:
    schemas = _openapi()["components"]["schemas"]
    change_defs = json.loads(RECONCILIATION_SCHEMA_PATH.read_text())["$defs"]

    assert schemas["ContentReconciliationRequest"] == change_defs["request"]
    assert schemas["ContentReconciliationCounts"] == change_defs["counts"]

    canonical_item = schemas["ContentReconciliationItem"]
    change_item = change_defs["item"]
    assert canonical_item["additionalProperties"] == change_item["additionalProperties"]
    assert set(canonical_item["required"]) == set(change_item["required"])
    assert set(canonical_item["properties"]) == set(change_item["properties"])
    assert (
        schemas["ContentReconciliationContentStatus"]["enum"]
        == change_defs["content_status"]["enum"]
    )
    assert schemas["ContentReconciliationOperationStatus"]["enum"] == [
        value for value in change_defs["operation_status"]["enum"] if value is not None
    ]
    assert (
        schemas["ContentReconciliationAction"]["enum"]
        == change_item["properties"]["action"]["enum"]
    )
    assert (
        schemas["ContentReconciliationReason"]["enum"]
        == change_item["properties"]["reason"]["enum"]
    )

    canonical_report = schemas["ContentReconciliationReport"]
    change_report = change_defs["report"]
    assert canonical_report["additionalProperties"] == change_report["additionalProperties"]
    assert set(canonical_report["required"]) == set(change_report["required"])
    assert set(canonical_report["properties"]) == set(change_report["properties"])


def test_content_reconciliation_contract_is_closed_bounded_and_safe() -> None:
    schemas = _openapi()["components"]["schemas"]
    report = schemas["ContentReconciliationReport"]
    item = schemas["ContentReconciliationItem"]
    counts = schemas["ContentReconciliationCounts"]

    assert report["additionalProperties"] is False
    assert set(report["required"]) == {
        "run_id",
        "mode",
        "scanned",
        "reported",
        "counts",
        "items",
    }
    assert report["properties"]["scanned"]["maximum"] == 100
    assert report["properties"]["reported"]["maximum"] == 100
    assert report["properties"]["items"]["maxItems"] == 100
    assert report["properties"]["next_after_content_id"]["minimum"] == 1

    expected_counts = {
        "applied",
        "retried",
        "projected",
        "restored",
        "active",
        "locked",
        "missing",
        "conflicted",
        "cancelled",
        "forced",
        "exhausted",
        "incompatible",
        "failed",
    }
    assert counts["additionalProperties"] is False
    assert set(counts["required"]) == expected_counts
    assert set(counts["properties"]) == expected_counts
    assert all(field["minimum"] == 0 for field in counts["properties"].values())
    assert all(field["maximum"] == 100 for field in counts["properties"].values())

    assert item["additionalProperties"] is False
    safe_fields = {
        "content_id",
        "projection",
        "content_status_before",
        "content_status_after",
        "operation_id",
        "claim_generation",
        "claim_protocol_version",
        "operation_status_before",
        "operation_status_after",
        "retry_count_before",
        "retry_count_after",
        "phase",
        "action",
        "reason",
        "operation_heartbeat_at",
        "operation_completed_at",
        "applied",
    }
    assert set(item["properties"]) == safe_fields
    assert not {
        "title",
        "url",
        "content",
        "error",
        "payload",
        "input",
        "result",
        "checkpoint",
        "secret",
    } & set(item["properties"])
    assert set(schemas["ContentReconciliationAction"]["enum"]) == {
        "none",
        "retry_operation",
        "project_completed",
        "project_parsed",
        "restore_parsed",
        "restore_pending",
        "cancel_restore_parsed",
        "cancel_restore_pending",
    }
    assert "apply_failed" in schemas["ContentReconciliationReason"]["enum"]
    assert "incompatible_worker" in schemas["ContentReconciliationReason"]["enum"]


def test_content_reconciliation_endpoint_has_exact_response_semantics() -> None:
    operation = _openapi()["paths"]["/api/v1/operations/reconcile-content"]["post"]

    assert operation["operationId"] == "reconcileContent"
    assert operation["requestBody"]["required"] is True
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ContentReconciliationRequest"
    }
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ContentReconciliationReport"
    }
    # Disabled apply is 409, not 503: it is a standing policy decision, so the
    # request conflicts with server state rather than hitting a transient outage
    # a retry would clear. A 5xx here would also breach the fuzz contract that
    # schema-valid input never produces a server error.
    assert set(operation["responses"]) == {"200", "401", "403", "409", "422"}
    assert operation["responses"]["409"]["content"]["application/problem+json"]["schema"] == {
        "$ref": "#/components/schemas/Problem"
    }


def test_generated_reconciliation_models_are_strict_and_default_to_dry_run() -> None:
    module = _generated_models()

    request = module.ContentReconciliationRequest()
    assert request.apply is False
    assert request.limit is None
    assert request.after_content_id is None
    with pytest.raises(ValidationError):
        module.ContentReconciliationRequest(unexpected=True)

    assert set(get_args(module.ContentReconciliationMode)) == {"dry_run", "apply"}
    assert set(get_args(module.ContentReconciliationProjection)) == {"proposed", "observed"}

    item = {
        "content_id": 42,
        "projection": "proposed",
        "content_status_before": "failed",
        "content_status_after": "failed",
        "operation_id": "not-numeric",
        "claim_generation": 1,
        "claim_protocol_version": 2,
        "operation_status_before": "failed",
        "operation_status_after": "failed",
        "retry_count_before": 0,
        "retry_count_after": 0,
        "phase": "processing",
        "action": "none",
        "reason": "failed_operation",
        "applied": False,
    }
    with pytest.raises(ValidationError):
        module.ContentReconciliationItem.model_validate(item)

    with pytest.raises(ValidationError):
        module.ContentReconciliationReport.model_validate(
            {
                "run_id": "not-a-uuid",
                "mode": "dry_run",
                "scanned": 0,
                "reported": 0,
                "counts": dict.fromkeys(
                    {
                        "applied",
                        "retried",
                        "projected",
                        "restored",
                        "active",
                        "locked",
                        "missing",
                        "conflicted",
                        "cancelled",
                        "forced",
                        "exhausted",
                        "incompatible",
                        "failed",
                    },
                    0,
                ),
                "items": [],
            }
        )


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


def test_operation_observability_contract_is_in_the_durable_registry() -> None:
    document = _openapi()
    schemas = document["components"]["schemas"]

    assert "/api/v1/operations/{operation_id}/attempts" in document["paths"]
    assert "/api/v1/status/observability" in document["paths"]
    assert "/api/v1/status/environment-ownership" in document["paths"]
    assert document["components"]["securitySchemes"]["OperatorKey"]["name"] == (
        "X-Operator-Key"
    )
    assert schemas["OperationHandle"]["properties"]["observability"] == {
        "oneOf": [
            {"$ref": "#/components/schemas/OperationObservabilitySummary"},
            {"type": "null"},
        ],
        "default": None,
    }
    assert schemas["OperationAttemptPage"]["properties"]["attempts"]["maxItems"] == 100
    assert schemas["ObservabilityHealthPage"]["properties"]["processes"]["maxItems"] == 1000


def test_operation_context_event_and_openapi_nullability_match() -> None:
    context_schema = json.loads(
        (CONTRACTS / "events/operation-context-v1.schema.json").read_text()
    )
    attempt_schema = json.loads(
        (CONTRACTS / "events/operation-attempt-v1.schema.json").read_text()
    )
    openapi_context = _openapi()["components"]["schemas"]["OperationContextEnvelope"]

    for schema in (context_schema, attempt_schema):
        validator_for(schema).check_schema(schema)
    assert set(context_schema["required"]) == set(openapi_context["required"])

    nullable = {
        "parent_operation_id",
        "tracestate",
        "attempt_number",
        "stage",
        "resource_kind",
        "resource_key",
    }

    def permits_null(schema: dict[str, Any]) -> bool:
        schema_type = schema.get("type")
        return schema_type == "null" or (
            isinstance(schema_type, list) and "null" in schema_type
        ) or any(permits_null(part) for part in schema.get("oneOf", []))

    for field in context_schema["properties"]:
        assert permits_null(context_schema["properties"][field]) == (field in nullable)
        assert permits_null(openapi_context["properties"][field]) == (field in nullable)


def test_operation_entrypoint_inventory_is_closed_and_reviewable() -> None:
    inventory = cast(
        dict[str, Any],
        yaml.safe_load((GX10_CONTRACTS / "operation-entrypoints.yaml").read_text()),
    )

    assert inventory["schema_version"] == 1
    assert inventory["policy"]
    assert inventory["shared_boundaries"]
    assert inventory["domain_operations"]
    assert inventory["provider_boundaries"]
    assert inventory["explicit_exclusions"]


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

    for fragment in (
        "operation_observation_attempts",
        "telemetry_process_health",
        "submission_context",
        "ck_pgqueuer_jobs_context_identity",
        "ck_audit_log_trace_id",
        "ck_workflow_terminal_events_trace_id",
        "environment_ownership",
    ):
        assert fragment in schema


def _valid_operation_context() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "operation_id": "9223372036854775807",
        "root_operation_id": "1",
        "parent_operation_id": None,
        "traceparent": "00-11111111111111111111111111111111-2222222222222222-01",
        "tracestate": "vendor=value",
        "trace_id": "11111111111111111111111111111111",
        "span_id": "2222222222222222",
        "claim_generation": "9223372036854775806",
        "attempt_number": "9223372036854775807",
        "entrypoint": "api.submit",
        "service_name": "api",
        "service_instance_id": "instance-1",
        "environment": "test",
        "release_revision": "a" * 40,
        "stage": "submit",
        "resource_kind": None,
        "resource_key": "😀" * 128,
    }


def test_generated_python_operation_context_parser_enforces_composite_semantics() -> None:
    module = _generated_models()
    payload = _valid_operation_context()

    parsed = module.parse_operation_context_envelope(payload)
    assert parsed.operation_id == "9223372036854775807"
    assert module.parse_operation_context_envelope({**payload, "schema_version": 1.0})

    invalid_payloads = (
        {**payload, "schema_version": True},
        {**payload, "schema_version": "1"},
        {**payload, "operation_id": "9223372036854775808"},
        {**payload, "claim_generation": "9223372036854775807"},
        {**payload, "trace_id": "0" * 32},
        {**payload, "span_id": "0" * 16},
        {**payload, "traceparent": "00-33333333333333333333333333333333-2222222222222222-01"},
        {**payload, "attempt_number": "1"},
        {**payload, "tracestate": "vendor=value,vendor=duplicate"},
        {**payload, "resource_key": "😀" * 129},
        {**payload, "unexpected": True},
    )
    for invalid in invalid_payloads:
        with pytest.raises(ValidationError):
            module.parse_operation_context_envelope(invalid)


def test_generated_typescript_contract_has_brands_and_mandatory_context_parser() -> None:
    source = (CONTRACTS / "generated/types.ts").read_text()
    runtime = (ROOT / "web/src/generated/workflow-contracts.ts").read_text()

    for generated in (source, runtime):
        assert 'type Brand<Value, Name extends string>' in generated
        assert 'export type OperationId = Brand<string, "OperationId">;' in generated
        assert 'export type TraceId = Brand<string, "TraceId">;' in generated
        assert 'export function parseOperationContextEnvelope(' in generated
        assert 'BigInt(context.attempt_number)' in generated
        assert 'Array.from(value).length' in generated


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
