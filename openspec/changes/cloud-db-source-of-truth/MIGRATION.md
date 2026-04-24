# Migration notes — cloud-db-source-of-truth

This OpenSpec change introduces **breaking changes** to the MCP tool return
shapes for the 4 tools listed below. The sole consumer set is @jankneumann's
personal Claude Code / Codex / Gemini configs **and** the `agentic-assistant`
project. This document records the coordinated migration required to keep
both consumer sides working after merge.

## Breaking change summary

| Tool | Legacy shape | New shape (OpenAPI-aligned) |
|------|--------------|------------------------------|
| `search_knowledge_base` | flat list of `{name, category, summary, relevance_score, mention_count}` | `{topics: [{slug, title, score, excerpt, last_compiled_at}], total_count}` |
| `search_knowledge_graph` | ad-hoc text/dict | `{entities: [{id, name, type, score}], relationships: [{source_id, target_id, type, score}]}` |
| `extract_references` | `{scanned, references_found, dry_run}` | `{references_extracted, content_processed, has_more, next_cursor?, per_content?}` |
| `resolve_references` | `{resolved, batch_size}` | `{resolved_count, still_unresolved_count, has_more}` |

Field notes:
- `last_compiled_at` is now **required** on every KB search result (ISO-8601 UTC).
- `score` is now **required** on every graph **relationship** (was previously only on entities).
- `has_more` is always present on `extract_references` and `resolve_references`; `next_cursor` is only present when `has_more=true`; `per_content` is optional (may be omitted on very large batches to limit payload size).

## Agentic-assistant migration checklist

The `agentic-assistant` project at `~/Coding/agentic-assistant` consumes these
tools via MCP. Before merging this proposal, update that repo:

- [ ] Update all MCP tool result parsers to accept the new shapes. Grep for the
      legacy keys (`relevance_score`, `mention_count`, `scanned`,
      `references_found`, `dry_run`, `resolved`, `batch_size`) and replace.
- [ ] Confirm any downstream logic that computed averages / rankings from
      `relevance_score` now uses the renamed `score` field.
- [ ] Remove any tolerance for the legacy shapes — single-consumer set, so no
      need for adapter fallbacks.
- [ ] Record the updating PR link + commit SHA in this file (see placeholder
      below) before this proposal's PR is merged.

### Migration status

- **agentic-assistant PR**: `<link or SHA once created>`
- **Merge order**: agentic-assistant PR must land **before** this proposal merges. The ACA PR description should reference the agentic-assistant commit so both sides land together.

## Owner-side migration checklist

For @jankneumann's personal tooling (Claude Code / Codex / Gemini configs):

- [ ] Any custom slash-commands or skills that invoke these 4 MCP tools and
      parse the result shapes locally must be updated. Common locations:
      `~/.claude/skills/*/`, `~/.codex/skills/*/`.
- [ ] If a skill caches MCP responses (e.g., persistent memory), clear those
      caches post-merge — legacy-shape cached responses will fail the new
      parsers.

## Non-breaking changes (reference only)

The following changes are additive and do NOT require migration:

- 6 new HTTP endpoints at `/api/v1/kb/search`, `/api/v1/kb/lint`,
  `/api/v1/kb/lint/fix`, `/api/v1/graph/query`,
  `/api/v1/graph/extract-entities`, `/api/v1/references/extract`,
  `/api/v1/references/resolve`.
- `GET /api/v1/audit` query endpoint.
- `aca manage restore-from-cloud` CLI command.
- All `/api/v1/*` requests now produce audit log entries (including 401/403).
- `@audited(operation="topics.delete")` retrofitted on `DELETE /api/v1/kb/topics/{slug}` (operation tagging only — semantics unchanged).

## HTTP contract (external consumers)

The committed OpenAPI contract lives at
`openspec/changes/cloud-db-source-of-truth/contracts/openapi/v1.yaml`. A drift
test (`tests/contract/test_openapi_drift.py`) runs in CI to catch accidental
divergence between the authored contract and FastAPI's runtime `/openapi.json`.
