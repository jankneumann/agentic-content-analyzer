# Tasks — unify-mcp-ingest-envelope

## 1. MCP wrapper migration (`src/mcp_server.py`)
- [ ] 1.1 `ingest_gmail` — return `response.with_timing(...).model_dump(mode="json")` instead of flat `{items_ingested, source}`
- [ ] 1.2 `ingest_rss` — same migration
- [ ] 1.3 `ingest_youtube` — same migration
- [ ] 1.4 `ingest_youtube_rss` / `ingest_youtube_playlist` — same migration (both expose canonical envelope)
- [ ] 1.5 `ingest_podcast` — same migration
- [ ] 1.6 `ingest_substack` — same migration
- [ ] 1.7 `ingest_scholar` / `ingest_scholar_paper` / `ingest_scholar_refs` — same migration
- [ ] 1.8 `ingest_arxiv` / `ingest_arxiv_paper` — same migration
- [ ] 1.9 `ingest_huggingface_papers` — same migration
- [ ] 1.10 `ingest_xsearch` — same migration
- [ ] 1.11 `ingest_perplexity_search` — same migration
- [ ] 1.12 `ingest_url` — return canonical envelope; details still carry content_id/status/duplicate/url
- [ ] 1.13 `ingest_files` — wire MCP tool through orchestrator's `ingest_files` (currently no MCP tool exists)
- [ ] 1.14 `run_pipeline` — `ingestion_results` becomes `{name: full_envelope_dict}`; sum aggregation reads `entry["items_ingested"]`

## 2. Helper extraction
- [ ] 2.1 Add `_envelope_with_timing(response, started_at, started_mono) -> dict` helper in `src/mcp_server.py` to dedupe the timing-augment pattern across 13 tools

## 3. Tests
- [ ] 3.1 `tests/mcp/test_mcp_ingest_envelope_conformance.py` — for each MCP tool, mock the orchestrator return, invoke the tool, assert the JSON parses as a valid `IngestionResponse` via `model_validate_strict`
- [ ] 3.2 Update `tests/mcp/test_mcp_*.py` existing tests where they assert flat-shape keys
- [ ] 3.3 Pin `run_pipeline` per-source structure (regression test for the nested envelope dict)

## 4. Consumer migration (separate repo)
- [ ] 4.1 In `agentic-assistant` repo, update the MCP-tool result parsing for all 12 `ingest_*` tools and `run_pipeline`
- [ ] 4.2 Land both PRs (this repo + agentic-assistant) in lockstep — neither merges alone

## 5. Docs
- [ ] 5.1 Drop the now-stale comment in `src/mcp_server.py` that says "Envelope-level migration of MCP wrappers is tracked in the cross-transport pass"
- [ ] 5.2 Update `docs/GOTCHAS.md` row about MCP-tool shapes (the row added in commit `<this round>` that notes legacy flat shape)
- [ ] 5.3 Spec entry under `openspec/specs/mcp-ingest-envelope/spec.md` documenting the canonical MCP `ingest_*` return contract
