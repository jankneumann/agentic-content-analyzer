## ADDED Requirements

### Requirement: Ingestion history derives from durable operations

Ingestion history SHALL derive from canonical `pgqueuer_jobs` operations,
parent-child relationships, checkpoints, results, resources, retries, and
terminal problems. It SHALL NOT introduce a second authoritative workflow
state machine.

#### Scenario: A pipeline has mixed source outcomes

- **WHEN** an operator queries a pipeline whose source children include
  successful, zero-item, partial, or failed ingestion outcomes
- **THEN** each source outcome SHALL be distinguishable from the operation
  lifecycle state
- **AND** retry, checkpoint, parent, and idempotency identity SHALL remain
  attached to the authoritative operations

#### Scenario: A new persistence projection is proposed

- **WHEN** existing operation payloads can satisfy the required query and
  retention behavior
- **THEN** no new run or source-result table SHALL be created
- **AND** any future read model SHALL require a documented query-plan or
  retention gap

### Requirement: Durable ingestion results preserve source outcomes

Every terminal ingestion operation SHALL retain a versioned typed result when
a canonical `IngestionResponse` exists. The result SHALL preserve source-domain
status, ingested/skipped/failed counts, structured diagnostics, configured
source outcomes, and exact content provenance.

#### Scenario: A version-one result is read

- **WHEN** an individual operation contains the pre-change result shape
- **THEN** it SHALL remain readable as `IngestionResultV1`
- **AND** new writers SHALL emit strict `IngestionResultV2`

#### Scenario: Ingestion completes with partial item failures

- **WHEN** an ingestion adapter returns `status=partial`
- **THEN** the operation lifecycle MAY be `completed`
- **AND** its durable outcome SHALL be `partial`
- **AND** failed/skipped counts plus bounded diagnostics SHALL survive

#### Scenario: Ingestion returns a domain error

- **WHEN** an ingestion adapter returns `status=error`
- **THEN** the typed failed result SHALL be attached before the operation
  transitions to lifecycle `failed`
- **AND** the RFC 7807 problem SHALL remain available

#### Scenario: Ingestion succeeds with no items

- **WHEN** ingestion completes with zero ingested items and no failure signal
- **THEN** its durable outcome SHALL be `zero_items`
- **AND** it SHALL NOT be conflated with `failed` or `partial`

#### Scenario: A legacy result lacks the outcome fields

- **WHEN** history projects a pre-change row whose partial status was not
  persisted
- **THEN** the outcome SHALL be `unknown`
- **AND** it SHALL NOT infer success from lifecycle `completed`

### Requirement: Configured-source failures remain visible without locators

Multi-source ingestion SHALL preserve bounded per-configured-source outcomes
using stable opaque keys. Public results SHALL NOT persist natural locators,
mailbox queries, prompts, credentials, or private URLs as source identity.

#### Scenario: One RSS feed fails while another succeeds

- **WHEN** one configured feed fails and at least one peer feed persists items
- **THEN** the command outcome SHALL be `partial`
- **AND** the failed configured source SHALL appear under an opaque key with
  bounded diagnostic codes and counts

#### Scenario: A configured source uses a private locator

- **WHEN** its source outcome is serialized or returned through history
- **THEN** the natural locator SHALL be absent
- **AND** the opaque key SHALL be stable for the same configured source
- **AND** the key SHALL be derived with a dedicated secret so low-entropy
  locators cannot be tested offline

#### Scenario: A diagnostic contains sensitive or hostile text

- **WHEN** a diagnostic contains URL credentials, secret query parameters,
  mailbox queries, prompts, or multiline control text
- **THEN** the durable result SHALL retain only its safe code and sanitized
  bounded message
- **AND** the raw sensitive or log-forging value SHALL not survive in result,
  problem, notification, or log projections

### Requirement: Public result projections have deterministic bounds

Compact history rows, command details, and diagnostics SHALL have documented
deterministic count and string-length bounds. Exact content IDs required for workflow
provenance SHALL appear once on individual operation results and SHALL be
excluded from compact history pages.

#### Scenario: Diagnostics exceed the public bound

- **WHEN** a source emits more diagnostics or configured-source outcomes than
  the contract limit
- **THEN** the public result SHALL retain a deterministic prefix
- **AND** SHALL report omitted counts without embedding omitted text
- **AND** the sanitized metadata outside exact content IDs SHALL remain within
  the documented serialized-byte budget

#### Scenario: An operation contains a large checkpoint

- **WHEN** it appears in an ingestion history page
- **THEN** the compact row SHALL exclude raw input, checkpoint, result details,
  resolved content sets, and content-ID arrays
- **AND** exact data SHALL remain available from the individual operation

#### Scenario: An operator lists generic operations

- **WHEN** an API, CLI, or web client requests `GET /api/v1/operations`
- **THEN** every list row SHALL use the bounded operation summary contract
- **AND** result, input, checkpoint, resource metadata, content IDs, diagnostic
  messages, and problem detail SHALL be absent
- **AND** the retained lifecycle message SHALL pass the same redaction and
  control-character sanitizer
- **AND** the exact-operation endpoint SHALL remain the only full-result read

### Requirement: Canonical ingestion history supports fixed-filter pagination

The API, client, and CLI SHALL expose the same compact ingestion-history query
derived from operations. It SHALL support command key, opaque configured-source
key, outcome, lifecycle status, parent operation, created-after, and
created-before filters with stable signed keyset pagination. The history SHALL
contain terminal operations only.

#### Scenario: An operator queries partial RSS history

- **WHEN** the query selects `command_key=rss` and `outcome=partial`
- **THEN** every returned row SHALL satisfy both filters
- **AND** each row SHALL include operation identity, bounded opaque
  configured-source summaries, optional pipeline parent, counts, retry count,
  problem code, status URL, and timestamps

#### Scenario: An operator queries one configured feed

- **WHEN** the query supplies an opaque configured-source key
- **THEN** every returned operation SHALL contain that configured-source
  outcome
- **AND** no natural locator SHALL be returned

#### Scenario: A cursor is replayed under different filters

- **WHEN** a cursor created for one normalized filter set is supplied with a
  different filter set
- **THEN** the API SHALL reject it as invalid
- **AND** SHALL NOT silently continue under the new query

#### Scenario: A cursor is tampered with

- **WHEN** a cursor signature, position, version, or decoded size is invalid
- **THEN** the API SHALL reject it as invalid
- **AND** SHALL NOT execute a history query from the untrusted position

#### Scenario: Optional filters are absent

- **WHEN** the CLI client makes an unfiltered history request
- **THEN** absent optional values SHALL be omitted from the serialized query
- **AND** machine-readable stdout SHALL contain exactly one JSON document

#### Scenario: A CLI caller traverses all history pages

- **WHEN** `aca ingest history --all` follows history cursors
- **THEN** it SHALL stop at the validated `--max-pages` request budget
- **AND** the default budget SHALL be 20 pages of at most 100 rows each
- **AND** budget exhaustion SHALL expose `truncated=true` plus `next_cursor` in
  JSON or a human warning with the continuation cursor

#### Scenario: A client traverses generic operations

- **WHEN** CLI or web code follows generic operation cursors
- **THEN** traversal SHALL have an explicit page budget
- **AND** the web Background Tasks indicator SHALL query bounded active/recent
  summaries rather than the whole retained terminal history

#### Scenario: Legacy command identity is projected

- **WHEN** a legacy ingestion row lacks the current typed command field
- **THEN** classification SHALL prefer `payload.input.kind`, then a documented
  legacy root `source` or `entrypoint` mapping, then `unknown`
- **AND** legacy missing counts SHALL remain null rather than fabricated zeroes

#### Scenario: An ingestion operation is still active

- **WHEN** an ingestion operation is queued or in progress
- **THEN** it SHALL remain observable through the generic operations surface
- **AND** it SHALL NOT appear in terminal ingestion history with invented
  outcome counts

#### Scenario: An unauthenticated caller requests history

- **WHEN** a caller without the authorization required by canonical workflow
  reads requests ingestion history
- **THEN** the request SHALL be rejected by the existing API authorization
  boundary
- **AND** no history row SHALL be returned

### Requirement: Partial pipeline behavior is explicit

Pipeline result projection and CLI output SHALL use the shared ingestion
outcome classifier. Lifecycle failure behavior SHALL continue to follow the
submitted `continue_on_source_error` policy.

#### Scenario: A tolerated source is partial

- **WHEN** a pipeline completes after a source returns `partial` and
  continuation is enabled
- **THEN** the pipeline operation MAY complete successfully
- **AND** human CLI output SHALL emit a warning on stderr
- **AND** JSON output SHALL expose the partial outcome without extra stdout

#### Scenario: Source failure continuation is disabled

- **WHEN** any source fails or is partial and `continue_on_source_error` is false
- **THEN** the pipeline operation SHALL fail
- **AND** the waiting CLI SHALL exit non-zero

#### Scenario: A source succeeds with no items

- **WHEN** a source outcome is `zero_items`
- **THEN** the pipeline ingestion summary SHALL retain that outcome
- **AND** human CLI output SHALL report it without changing the zero exit code

### Requirement: Retention preserves operation graphs

Automatic retention SHALL delete only whole eligible terminal operation
graphs after configurable completed and failed history windows. Active work
SHALL remain intact, and failed graphs SHALL receive a longer finite retry
horizon.

#### Scenario: A completed graph crosses the retention cutoff

- **WHEN** a root and all descendants are terminal completed or cancelled and
  every node's completion time is strictly older than the configured cutoff
- **THEN** cleanup SHALL remove the graph as one maintenance action
- **AND** no surviving row SHALL lose its parent identity

#### Scenario: A terminal graph has a missing completion timestamp

- **WHEN** any terminal node has `completed_at=null`
- **THEN** cleanup SHALL retain the entire graph
- **AND** SQL aggregation SHALL NOT ignore the null and classify the graph old

#### Scenario: A descendant is active

- **WHEN** any descendant is queued or in progress
- **THEN** cleanup SHALL retain the root and every descendant

#### Scenario: A graph contains a recent retryable failure

- **WHEN** a failed source child or failed pipeline is newer than the failed
  retention cutoff
- **THEN** cleanup SHALL retain the entire graph
- **AND** its checkpoint and retry-child identity SHALL remain unchanged

#### Scenario: A failed graph exceeds its retry horizon

- **WHEN** every node is terminal and the graph's maximum completion time is
  strictly older than the configured failed cutoff
- **THEN** cleanup MAY remove the whole graph in a bounded batch
- **AND** no surviving row SHALL be detached from the removed root

#### Scenario: Multiple workers run maintenance

- **WHEN** more than one worker reaches the cleanup interval
- **THEN** a PostgreSQL advisory lock SHALL allow at most one cleanup execution
- **AND** lock contention SHALL not affect workflow processing

#### Scenario: Retention settings are invalid

- **WHEN** a retention horizon is outside 1–3650 days, the failed horizon is
  shorter than the completed horizon, or interval/batch bounds are invalid
- **THEN** settings validation SHALL fail at startup
- **AND** zero SHALL NOT silently disable cleanup
