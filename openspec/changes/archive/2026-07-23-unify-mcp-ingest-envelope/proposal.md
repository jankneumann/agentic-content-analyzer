# Unify MCP `ingest_*` envelope shapes with the canonical `IngestionResponse`

## Why

The `harmonize/cli-ingest-envelope` branch (merged 2026-05-08, commit `1ea74ab`) made every `aca ingest *` command return the canonical `IngestionResponse` envelope across CLI, HTTP, queue worker, and pipeline transports. The MCP wrapper layer at `src/mcp_server.py` was deliberately left out of that migration — instead, each MCP tool projects the canonical envelope down to a flat ad-hoc shape per command:

| MCP tool                    | Current return-shape                                          |
|-----------------------------|---------------------------------------------------------------|
| `ingest_gmail` / `ingest_rss` / `ingest_youtube` / `ingest_podcast` / `ingest_substack` / `ingest_scholar` / `ingest_arxiv` / `ingest_huggingface_papers` / `ingest_xsearch` / `ingest_perplexity_search` | `{items_ingested: int, source: str}` |
| `ingest_url`                | `{content_id, status, duplicate, source}`                     |
| `ingest_arxiv_paper`        | `{identifier, items_ingested, source}`                        |
| `ingest_scholar_paper`      | `{paper_id, items_ingested, source}` (similar)                |

Cross-MCP-tool consumers see N different envelope-projection shapes when there is now exactly one canonical shape upstream. Reviewers caught this drift in the harmonization branch's whole-branch review (finding #7); the codebase comment ("Envelope-level migration of MCP wrappers is tracked in the cross-transport pass") flagged it but pointed to nowhere — this change closes that loop.

The MCP sole-consumer model (memory `project_mcp_sole_consumer.md`) means we can break the existing flat shape: only `@jankneumann` and `agentic-assistant` consume MCP tools today. That eliminates the migration-shim concern that drove the original projection.

## What Changes

Migrate every `ingest_*` MCP tool in `src/mcp_server.py` to return the full canonical envelope JSON dump:

```json
{
  "schema_version": 1,
  "command": "ingest.gmail",
  "source": "gmail",
  "status": "ok",
  "items_ingested": 5,
  "items_skipped": 0,
  "items_failed": 0,
  "duration_ms": 1234,
  "started_at": "2026-05-08T12:34:56+00:00",
  "errors": [],
  "warnings": [],
  "details": { ... },
  "success": true
}
```

The agentic-assistant consumer (the only external reader today) is updated in lockstep to consume the canonical envelope. Out-of-scope: the legacy flat-shape contract is retired without a deprecation period.

### Behavioral tweaks shipped together
1. MCP tools call `response.with_timing(...)` to populate `duration_ms` / `started_at` from the MCP request boundary (matches what CLI direct mode does).
2. The MCP server gains a contract test (`tests/mcp/test_mcp_ingest_envelope_conformance.py`) that asserts every MCP `ingest_*` tool's return JSON validates as a canonical `IngestionResponse` via `model_validate_strict`.
3. The `run_pipeline` MCP tool's nested `ingestion_results` dict (currently `{name: count}`) becomes `{name: <full envelope>}` so per-source diagnostics (errors, warnings, details) are exposed end-to-end.

## Impact

- **Affected specs**: none (no openspec/specs entry covers MCP today; this change adds one)
- **Affected code**: `src/mcp_server.py` (12 `ingest_*` tools), `tests/mcp/`, the agentic-assistant consumer (separate repo)
- **Migration**: hard cut — the agentic-assistant repo merges its consumer-side update at the same time as this change lands
- **Risk**: low — sole-consumer model means breakage is detectable end-to-end before merge

## Out of scope

- Non-`ingest_*` MCP tools (summarize, digest, search) — separate harmonization track, not on this branch
- HTTP API envelope shape — already canonical post-harmonization
- Streaming/progress events for long-running MCP tools — future work
