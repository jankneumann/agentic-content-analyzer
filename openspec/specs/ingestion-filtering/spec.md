# ingestion-filtering Specification

## Purpose

Define the implemented ingestion-time relevance filtering foundation. Broader
runtime-control and operator-surface behavior is tracked separately by
`reconcile-ingestion-filtering-runtime-contract`.

## Requirements

### Requirement: Global ingestion filter hook

Supported ingestion workflows SHALL invoke the shared filter hook for newly
persisted content when global filtering is enabled and SHALL bypass filtering
without writing filter fields when it is disabled.

#### Scenario: Global filtering is enabled

- **WHEN** a supported adapter persists new content and invokes the shared
  post-ingest hook
- **THEN** the hook SHALL evaluate that content through
  `IngestionFilterService`
- **AND** a skip decision SHALL prevent downstream summarization for that item

#### Scenario: Global filtering is disabled

- **WHEN** the filtering configuration disables the feature
- **THEN** the hook SHALL return without evaluating the content
- **AND** SHALL not write filter decision fields

### Requirement: Tiered relevance evaluation

The filter service SHALL evaluate heuristic, embedding, and optional LLM tiers
in order and SHALL short-circuit when an earlier tier yields a deterministic
decision.

#### Scenario: Heuristic rule decides

- **WHEN** a must-include or must-exclude rule matches
- **THEN** the service SHALL return the corresponding keep or skip decision
- **AND** SHALL not call embedding or LLM tiers

#### Scenario: Embedding result is borderline

- **WHEN** heuristic rules do not decide and embedding similarity falls inside
  the configured borderline band
- **THEN** the service SHALL use the configured LLM fallback when available
- **AND** SHALL retain a safe fallback decision if that tier is unavailable

### Requirement: Non-dry-run filter persistence

Completed non-dry-run evaluations SHALL persist the decision, score, tier,
reason, priority, and timestamp on `Content`; skip decisions SHALL use
`FILTERED_OUT` without deleting the row.

#### Scenario: Content is kept

- **WHEN** a non-dry-run evaluation returns keep
- **THEN** filter metadata and priority SHALL be persisted
- **AND** the pre-filter content status SHALL remain eligible for downstream
  processing

#### Scenario: Content is skipped

- **WHEN** a non-dry-run evaluation returns skip
- **THEN** filter metadata SHALL be persisted
- **AND** content status SHALL become `FILTERED_OUT`
- **AND** the content row SHALL remain stored
