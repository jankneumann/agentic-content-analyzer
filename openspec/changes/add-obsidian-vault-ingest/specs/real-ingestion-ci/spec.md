# real-ingestion-ci Specification

## MODIFIED Requirements

### Requirement: Every source registry entry maps to a fixture tier or a reviewed exclusion

Test collection SHALL fail if any `SOURCE_REGISTRY` entry lacks either a canonical
fixture or an entry in a documented exclusion set, and SHALL fail if the exclusion set
names a source that is not in the registry. Each exclusion SHALL carry a recorded
reason. Filesystem-backed sources SHALL have a deterministic temporary-vault fixture
that exercises the same bounded durable command without external sync or network
access, plus an explicit live-adapter policy for compatible mounted environments.

#### Scenario: Obsidian fixture covers the canonical vertical

- **WHEN** the fixture tier exercises `obsidian_vault`
- **THEN** it SHALL create a bounded temporary vault with valid, invalid, changed, and
  duplicate clips
- **AND** submit the typed command through `OperationService`
- **AND** assert terminal result counts against Content and private-state database
  deltas without external network access

#### Scenario: Obsidian registry entry is incomplete

- **WHEN** `obsidian_vault` is registered without an exact `SOURCE_FIXTURES` entry,
  live-adapter policy, generated contract, or interface projection
- **THEN** test collection or contract CI SHALL fail with a diagnostic naming the
  missing Obsidian mapping

#### Scenario: Live Obsidian mount is unavailable

- **WHEN** the scheduled tier evaluates `obsidian_vault` without an approved readable
  worker-local test mount
- **THEN** the live adapter SHALL be skipped with a recorded non-secret reason
- **AND** deterministic fixture coverage SHALL still be required

### Requirement: Pull-request real-ingestion tier verifies durable results against database deltas

The CI pull-request tier SHALL submit a curated set of representative typed source
commands, including the deterministic `obsidian_vault` filesystem fixture, through the
canonical workflow service (`OperationService`), SHALL observe each durable operation
to a terminal state, and SHALL assert the claimed result against actual Content and
source-state database deltas. The tier SHALL run offline and SHALL NOT require a real
user vault, sync client, credential, or live network access.

#### Scenario: Obsidian incremental ingestion matches durable evidence

- **WHEN** fixture scans process a new note, re-observe it unchanged, then process a
  changed version
- **THEN** each operation's typed persisted/skipped/failed counts SHALL match Content,
  ingest-event, and state-row deltas
- **AND** duplicate canonical URLs and overlapping claims SHALL not create duplicate
  primary identity or file-version events

#### Scenario: Obsidian typed failure is retained

- **WHEN** a fixture note fails path, encoding, metadata, stability, or size validation
- **THEN** the terminal operation SHALL classify it as an adapter diagnostic
- **AND** operation and CI evidence SHALL contain the stable code but no path, full URL,
  frontmatter, body, or raw exception text
