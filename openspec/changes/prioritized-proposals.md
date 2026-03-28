# Proposal Prioritization Report

**Date**: 2026-03-28
**Analyzed Range**: HEAD~50..HEAD (50 commits)
**Proposals Analyzed**: 4 active

---

## Priority Order

### 1. `add-arxiv-ingest` — Add arXiv Paper Ingestion
- **Relevance**: Still Relevant — no arXiv-specific code exists yet; Scholar foundation (Semantic Scholar client, migration, enum) is in place but arXiv client, PDF extraction, and version-aware dedup are entirely unaddressed
- **Readiness**: Ready — proposal approved, 9 task sections fully defined with dependency DAG, design.md present, max parallel width 4
- **Task Progress**: 0/40 tasks complete
- **Conflicts**: Overlaps with `add-content-references` on `src/models/content.py`, `src/mcp_server.py`, `alembic/versions/`, and `metadata_json` JSONB migration (both proposals reference same ALTER). Overlaps with `add-content-references` on `src/config/sources.py`
- **Recommendation**: **Implement next** — builds directly on the Scholar foundation (d03c0e3), reuses existing ingestion patterns, and the arXiv API requires no API key. The `metadata_json` JSONB migration should be done here first so `add-content-references` can skip it.
- **Next Step**: `/implement-feature add-arxiv-ingest`

### 2. `tree-index-chunking` — Tree Index Chunking (PageIndex-inspired)
- **Relevance**: Still Relevant — no tree indexing code exists; `src/services/chunking.py`, `src/services/search.py`, `src/models/chunk.py` untouched in recent commits
- **Readiness**: Ready — proposal approved, 3-phase task breakdown with clear dependencies, design.md present. Phase 1 (chunk thinning) is zero-dependency and can ship independently
- **Task Progress**: 0/18 tasks complete (across 3 phases)
- **Conflicts**: Overlaps with `add-content-references` on `src/config/settings.py`. No overlap with `add-arxiv-ingest`.
- **Recommendation**: **Implement in parallel with #1** — touches entirely different files (chunking/search/indexing vs ingestion/orchestrator). Phase 1 alone is a quick win (~50 LOC, no LLM calls, no migration).
- **Next Step**: `/implement-feature tree-index-chunking`

### 3. `add-content-references` — Content References & Citation Tracking
- **Relevance**: Needs Verification — `src/ingestion/reference_extractor.py` (227 lines) already exists from the Scholar implementation, containing arXiv/DOI/S2 regex patterns, extraction logic, and `aca ingest scholar-refs` CLI. The proposal's Section 2 (Reference Extraction Service) substantially overlaps with this existing code, but the proposal's broader scope (resolution service, auto-ingest, Neo4j sync, API routes, queue handler) remains unaddressed.
- **Readiness**: Partially Ready — depends on arXiv ingestion existing for auto-ingest trigger (Section 6). Core infrastructure (Sections 1-5) can proceed independently.
- **Task Progress**: 0/50 tasks complete (though ~30% of Section 2 may be covered by existing code)
- **Conflicts**: Overlaps with `add-arxiv-ingest` on `src/models/content.py`, `src/mcp_server.py`, `alembic/versions/`, `src/config/sources.py`. Overlaps with `tree-index-chunking` on `src/config/settings.py`. Overlaps with `add-api-versioning` on `src/api/app.py` (router registration).
- **Recommendation**: **Implement after #1** — the auto-ingest feature (Section 6) explicitly depends on arXiv orchestrator functions. The existing `reference_extractor.py` needs audit against the proposal's design to identify what's already built vs what's new. Update `proposal.md` and `tasks.md` to account for existing code before implementation.
- **Next Step**: `/iterate-on-plan add-content-references` (reconcile with existing reference_extractor.py)

### 4. `add-api-versioning` — Add API Versioning
- **Relevance**: Needs Refinement — the proposal references the `refactor-unified-content-model` as "~75% complete" but that refactor was completed and archived long ago. The motivation (safe API evolution) is valid but non-urgent: no external consumers exist beyond the bundled frontend. The proposal would reorganize the entire `src/api/` directory, creating high merge conflict risk with every other proposal.
- **Readiness**: Ready technically (tasks defined), but **low urgency** — the API currently serves only the co-located frontend
- **Task Progress**: 0/25+ tasks complete
- **Conflicts**: **High conflict risk** — reorganizes `src/api/content_routes.py`, `src/api/digest_routes.py`, `src/api/shared_routes.py`, and `src/api/app.py`. Every proposal that adds API routes (#3 adds `reference_routes.py`) would need to account for the version directory structure.
- **Recommendation**: **Defer** — implementing this now would create unnecessary merge conflicts with #1 and #3. Better to implement after the ingestion and search features stabilize. Update proposal to reflect current API state when ready.
- **Next Step**: Defer. Revisit after #1 and #3 are complete.

---

## Parallel Workstreams

### Stream A (start immediately — independent files)
| Proposal | Key Files | Est. Scope |
|----------|-----------|------------|
| `add-arxiv-ingest` | `src/ingestion/arxiv*.py`, `src/cli/ingest_commands.py`, `src/ingestion/orchestrator.py` | ~800 LOC |
| `tree-index-chunking` (Phase 1) | `src/services/chunking.py`, `src/config/settings.py` | ~100 LOC |

These two have **zero file overlap** and can be implemented by separate agents concurrently.

### Stream B (after Stream A, or after arxiv only)
| Proposal | Key Files | Prerequisite |
|----------|-----------|--------------|
| `tree-index-chunking` (Phases 2-3) | `src/services/indexing.py`, `src/services/search.py`, `src/models/chunk.py` | Phase 1 |
| `add-content-references` | `src/models/content_reference.py`, `src/services/reference_*.py`, `src/api/reference_routes.py` | `add-arxiv-ingest` (for auto-ingest) |

These can also run in parallel with each other (different file sets), but `add-content-references` benefits from having arXiv ingestion available.

### Deferred
| Proposal | Reason |
|----------|--------|
| `add-api-versioning` | High conflict risk, low urgency — wait for ingestion/search features to stabilize |

---

## Conflict Matrix

| | arxiv-ingest | tree-index-chunking | content-references | api-versioning |
|---|---|---|---|---|
| **arxiv-ingest** | — | none | `content.py`, `mcp_server.py`, `sources.py`, `alembic/` | none |
| **tree-index-chunking** | none | — | `settings.py` | none |
| **content-references** | `content.py`, `mcp_server.py`, `sources.py`, `alembic/` | `settings.py` | — | `api/app.py` |
| **api-versioning** | none | none | `api/app.py` | — |

---

## Proposals Needing Attention

### Needs Verification
- **`add-content-references`**: `src/ingestion/reference_extractor.py` (227 lines) already implements arXiv/DOI/S2 regex extraction, normalization, and a CLI command. Section 2 of the proposal overlaps significantly. Run `/iterate-on-plan add-content-references` to reconcile tasks.md with existing code.

### Needs Refinement
- **`add-api-versioning`**: Proposal references stale "refactor-unified-content-model ~75% complete" — that's long done. Motivation section needs updating to reflect current API consumers (just the bundled frontend). Consider whether versioning is needed before external API consumers exist.

### Stale Residual Directories
The following appear in `openspec/changes/` but their proposals are already archived:
- Residual files from archived proposals still linger under `openspec/changes/archive/` (a nested archive directory)
- Consider consolidating to a single archive location (`openspec/archive/`)
