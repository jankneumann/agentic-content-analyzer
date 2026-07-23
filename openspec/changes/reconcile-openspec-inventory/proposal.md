# Reconcile the OpenSpec inventory

> Parent roadmap: `roadmap-workflow-surface-reliability`
> Change ID: `reconcile-openspec-inventory`
> Effort: M
> Priority: 3

## Summary

Verify implementation and deployment evidence, archive completed or superseded changes, and extract only genuine remaining gaps into focused follow-up changes. Do not repeat filtering, database override, HuggingFace, LLM routing foundation, ParadeDB/Langfuse configuration, or MCP envelope implementation.

## Dependencies

- None

## Acceptance Outcomes

- add-ingestion-filtering-prioritization and db-source-overrides are verified and archived.
- add-huggingface-papers-source, llm-router-evaluation, and use-paradedb-railway-langfuse-default are reconciled against implementation and external evidence.
- unify-mcp-ingest-envelope is archived as superseded by canonical durable operations.
- Any unresolved image-name, deployment, or model-reachability gap is represented by a focused schema-valid change.
- The active OpenSpec inventory contains only actionable work.

## Rationale

Accurate planning state is required before refining the remaining reliability proposals and prevents completed work from being implemented twice.
