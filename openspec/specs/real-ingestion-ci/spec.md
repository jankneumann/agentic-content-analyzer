# real-ingestion-ci Specification

## Purpose
TBD - created by archiving change real-ingestion-test-tiers-in-ci. Update Purpose after archive.
## Requirements
### Requirement: Pull-request real-ingestion tier verifies durable results against database deltas

The CI pull-request tier SHALL submit a curated set of representative typed source
commands through the canonical workflow service (`OperationService`), SHALL observe
each durable operation to a terminal state, and SHALL assert the claimed result
against the actual database row delta. The tier SHALL run offline against deterministic
fixtures and SHALL NOT require any credential or live network access.

#### Scenario: Representative fixture ingestion completes and matches the DB delta

- **WHEN** a representative typed source command (one of `rss`, `gmail`, `url`,
  `youtube-playlist`, `arxiv-search`, `blog`) is submitted through `OperationService`
- **THEN** CI SHALL observe its durable operation to a terminal state within the tier
  timeout
- **AND** the operation's claimed result count SHALL equal the number of `Content` rows
  the fixture deterministically persists
- **AND** the tier SHALL run without contacting any external network host

#### Scenario: A terminal operation claims results that the database did not persist

- **WHEN** a submitted operation reaches a successful terminal state but the expected
  `Content` rows are absent
- **THEN** the tier SHALL fail
- **AND** the failure SHALL be classified as a persistence failure

### Requirement: Scheduled real-ingestion tier applies explicit live-adapter policy

The CI scheduled tier SHALL run every fixture-backed source and SHALL additionally
exercise live adapters according to an explicit, documented policy covering credential
availability, skip behavior, retry behavior, and failure rules. A source whose required
credential is absent SHALL be skipped with a recorded reason rather than failing. Paid
external APIs SHALL be a reviewed live exclusion and SHALL NOT be called live in CI.

#### Scenario: A credentialed adapter runs live when its secret is present

- **WHEN** the scheduled tier evaluates a credentialed-non-paid source (`gmail`,
  `youtube`, `substack`, `scholar`, `readwise`) and the required secret is configured
- **THEN** the tier SHALL submit the live command through `OperationService`
- **AND** SHALL observe the durable operation to a terminal state under the tier's
  retry policy

#### Scenario: A credentialed adapter is skipped when its secret is absent

- **WHEN** the scheduled tier evaluates a credentialed source whose required secret is
  not configured
- **THEN** the tier SHALL skip that source
- **AND** SHALL record an explicit skip reason naming the missing credential

#### Scenario: A paid API is never called live

- **WHEN** the scheduled tier evaluates a paid source (`x-search`, `perplexity`)
- **THEN** the tier SHALL exercise it only through its deterministic fixture
- **AND** SHALL NOT issue a live request to the paid provider

### Requirement: Every source registry entry maps to a fixture tier or a reviewed exclusion

Test collection SHALL fail if any `SOURCE_REGISTRY` entry lacks either a canonical
fixture or an entry in a documented exclusion set, and SHALL fail if the exclusion set
names a source that is not in the registry. Each exclusion SHALL carry a recorded
reason.

#### Scenario: A new registry source has no fixture and no exclusion

- **WHEN** a source is added to `SOURCE_REGISTRY` without a matching `SOURCE_FIXTURES`
  entry or a reviewed exclusion
- **THEN** real-ingestion test collection SHALL fail with a diagnostic naming the
  unmapped source

#### Scenario: The exclusion set references an unknown source

- **WHEN** the exclusion set names a source key absent from `SOURCE_REGISTRY`
- **THEN** collection SHALL fail with a diagnostic naming the stale exclusion

### Requirement: CI publishes failure-class evidence distinguishing adapter, queue, and persistence failures

For each real-ingestion tier run, CI SHALL publish evidence derived from the durable
operation and result records that attributes every non-successful source outcome to an
adapter, queue, or persistence failure class. The evidence SHALL NOT introduce a
run-state representation parallel to the durable operation model.

#### Scenario: A run summary attributes each failure to a layer

- **WHEN** a tier run completes with one or more non-successful sources
- **THEN** CI SHALL publish a summary that maps each failing source to exactly one of
  adapter, queue, or persistence
- **AND** each classification SHALL be derived from the source's durable operation and
  result records

#### Scenario: An adapter error is not misreported as a persistence failure

- **WHEN** a source's durable operation terminates with an adapter-level problem (for
  example an upstream parse or HTTP error) and writes no `Content` rows
- **THEN** the published evidence SHALL classify it as an adapter failure
- **AND** SHALL NOT classify it as a persistence failure
