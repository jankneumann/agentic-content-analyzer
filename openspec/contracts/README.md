# Durable Contracts

This directory contains executable contracts that remain authoritative after an OpenSpec
change is archived. Each contract domain owns a subdirectory with its source schemas,
deterministic fixtures, generated artifacts, and domain-specific maintenance instructions.

## Lifecycle

1. Propose breaking or behavioral contract changes in an OpenSpec change.
2. Apply approved deltas to the matching durable contract domain during implementation.
3. Regenerate derived artifacts and run the domain's drift checks.
4. Archive the change as historical evidence without redirecting live consumers.

Live application code, generators, and tests MUST NOT depend on files below
`openspec/changes/` or `openspec/changes/archive/`.

## Domains

- `content-workflows/` - ingestion, operations, summarization, digest, and podcast workflow
  contracts shared by CLI, HTTP, MCP, workers, and the frontend.
