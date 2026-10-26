## Purpose

Defines the provider-adapter boundary through which every retrieval store is written,
searched, read, and maintained, so that content chunks and agent memories can be served
by interchangeable backends without changing ranking, reranking, or consumer behavior.

## ADDED Requirements

### Requirement: Retrieval Adapter Actions

The system SHALL expose retrieval storage through an adapter contract with exactly
four actions, `write`, `search`, `read`, and `improve`, plus a health probe. Every
retrieval backend SHALL implement the same contract, and no consumer SHALL issue
backend-specific queries outside an adapter.

The `write` action SHALL accept a batch of typed records for one namespace, each with
an identifier, text, optional embedding, embedding provenance, and namespace-specific
metadata, and SHALL upsert them so a repeated write of the same identifier replaces
the prior record.

The `search` action SHALL accept a namespace, a query text, an optional query
embedding, a search mode of `bm25`, `vector`, or `hybrid`, a candidate limit, and a
typed filter, and SHALL return one ranked candidate list per requested leg, where each
candidate carries the record identifier, the raw leg score, and the parent identifier
used for aggregation.

The `read` action SHALL return full records for a list of identifiers in one
namespace, omitting identifiers that do not exist.

The `improve` action SHALL perform backend index maintenance for one namespace,
covering at minimum: folding unindexed rows into the text index, compacting or
rebuilding the vector index, and rebuilding after an embedding dimension change. It
SHALL report what work was performed.

#### Scenario: Write is idempotent per identifier

- **WHEN** the same record identifier is written twice with different text
- **THEN** exactly one record exists for that identifier
- **AND** a subsequent read returns the second text

#### Scenario: Search returns per-leg candidates

- **WHEN** a hybrid search is requested with a query text and query embedding
- **THEN** the adapter returns a BM25 candidate list and a vector candidate list
- **AND** neither list is fused, reranked, or truncated below the requested limit by the adapter

#### Scenario: Search mode limits legs

- **WHEN** a search is requested in `bm25` mode
- **THEN** only the BM25 candidate list is returned
- **AND** no query embedding is required

#### Scenario: Read omits missing identifiers

- **WHEN** a read is requested for three identifiers of which one does not exist
- **THEN** two records are returned
- **AND** no error is raised for the missing identifier

#### Scenario: Improve reports its work

- **WHEN** improve is invoked on a namespace
- **THEN** the result names each maintenance step performed and its duration
- **AND** a second invocation with no pending work reports zero steps

### Requirement: Retrieval Namespaces

The system SHALL serve two retrieval namespaces through the adapter contract:
`content_chunks`, holding chunked document text with structural metadata and a parent
content identifier, and `agent_memories`, holding agent memory entries with memory
type, tags, confidence, and access statistics. An adapter MAY support one or both
namespaces and SHALL declare which it supports.

#### Scenario: Adapter declares namespace support

- **WHEN** an adapter is asked whether it supports a namespace
- **THEN** it answers deterministically without contacting the backend

#### Scenario: Unsupported namespace is rejected

- **WHEN** a write or search targets a namespace the adapter does not support
- **THEN** the call fails with an error naming the adapter and the namespace
- **AND** no partial write occurs

### Requirement: Typed Retrieval Filters

The system SHALL express search filters as a typed structure per namespace rather
than as query fragments. For `content_chunks` the filter SHALL support source types,
publications, statuses, chunk types, a published-date range, and an explicit parent
identifier allow-list. For `agent_memories` the filter SHALL support memory types,
tags, minimum confidence, source task, and a created-since timestamp. Each adapter
SHALL translate the typed filter into its native predicate form and SHALL apply it
before ranking.

#### Scenario: Filter applied before ranking

- **WHEN** a hybrid search is requested with a source-type filter
- **THEN** every returned candidate belongs to a matching source type
- **AND** the candidate limit is filled from matching records only

#### Scenario: Empty filter result short-circuits

- **WHEN** a filter matches no records
- **THEN** the adapter returns empty candidate lists
- **AND** no ranking work is performed

#### Scenario: Unsupported filter field is rejected explicitly

- **WHEN** an adapter receives a filter field it cannot translate
- **THEN** the call fails with an error naming the field and the adapter
- **AND** the adapter never silently ignores the field

### Requirement: Composition Above the Adapter

The system SHALL perform rank fusion, optional reranking, tree search, document
aggregation, result highlighting, and degraded-backend handling in a composition layer
that consumes adapter candidate lists. The composition layer SHALL apply the same
weighted reciprocal rank fusion formula to both namespaces, with per-namespace
weights, and SHALL preserve the fusion constants, weight redistribution, minimum
score, and circuit-breaker cooldown already required for agent memory recall.

#### Scenario: Fusion identical across namespaces

- **WHEN** identical candidate lists are fused for `content_chunks` and for `agent_memories` with identical weights
- **THEN** the fused scores are identical

#### Scenario: Reranking stays adapter-independent

- **WHEN** reranking is enabled and the primary adapter changes
- **THEN** reranking runs over the fused candidates in the same way
- **AND** the adapter is never asked to rerank

#### Scenario: Tree search stays in the composition layer

- **WHEN** tree-indexed content is present among candidates
- **THEN** tree search runs against the tree index exactly as before
- **AND** no adapter is required to implement tree traversal

### Requirement: Primary Adapter Parity

The system SHALL provide a Postgres adapter as the default primary adapter. With no
secondary adapter configured, search responses, ranked identifiers, strategy names
reported in response metadata, and write side effects SHALL be identical to the
behavior before the adapter boundary existed.

#### Scenario: Golden ranking preserved

- **WHEN** the regression search fixture is queried in each search mode
- **THEN** the ordered content identifiers match the recorded baseline exactly
- **AND** `meta.bm25_strategy` reports the same strategy name as the baseline

#### Scenario: BM25 strategy selection unchanged

- **WHEN** the database has the full-text extension available and no override is set
- **THEN** the Postgres adapter reports `paradedb_bm25`
- **AND** without the extension it reports `postgres_native_fts`

#### Scenario: Memory recall behavior preserved

- **WHEN** an agent recalls memories with graph, vector, and keyword strategies configured
- **THEN** results are merged with the same weights, minimum score, and access-count update as before
- **AND** a failing strategy is skipped with weights redistributed and a 60 second cooldown

### Requirement: Adapter Selection and Registry

The system SHALL select the primary adapter and an optional secondary adapter from
configuration. The primary adapter SHALL default to Postgres. An adapter SHALL be
constructed lazily and SHALL NOT import its backend library at application import
time. An adapter that is configured but cannot be initialized SHALL report itself
unavailable and SHALL NOT affect the primary path.

#### Scenario: Default configuration

- **WHEN** no adapter settings are provided
- **THEN** the primary adapter is Postgres
- **AND** no secondary adapter exists

#### Scenario: Secondary adapter library missing

- **WHEN** a secondary adapter is configured but its optional dependency is not installed
- **THEN** startup logs one warning naming the adapter and the missing extra
- **AND** searches and writes proceed through the primary adapter alone

#### Scenario: Unknown adapter name

- **WHEN** an unrecognized adapter name is configured
- **THEN** configuration validation fails with the list of known adapter names

### Requirement: Fail-Safe Dual Write

When a secondary adapter is configured, every `write` and `improve` performed on the
primary adapter SHALL also be performed on the secondary adapter. A secondary failure
SHALL be logged with the adapter name, namespace, and record count, SHALL be counted,
and SHALL NOT cause the primary write, the ingestion job, the backfill command, or the
embedding switch to fail.

#### Scenario: Secondary write failure is isolated

- **WHEN** content is indexed and the secondary adapter raises during write
- **THEN** the primary write is committed
- **AND** ingestion reports success
- **AND** the failure is logged with adapter, namespace, and count

#### Scenario: Backfill dual-writes

- **WHEN** the chunk backfill command runs with a secondary adapter configured
- **THEN** every chunk written to the primary adapter is also written to the secondary adapter
- **AND** the command summary reports secondary write counts and failures separately

#### Scenario: Embedding switch reaches both adapters

- **WHEN** the embedding provider is switched
- **THEN** both adapters are cleared and rebuilt through the improve action
- **AND** the secondary adapter uses the new embedding dimension

### Requirement: Shadow Read

When shadow reading is enabled and a secondary adapter is available, the system SHALL
execute the same search against the secondary adapter after the primary response has
been produced, SHALL NOT alter or delay the primary response, and SHALL record for
each comparison the overlap of top-k identifiers, a rank correlation, and per-adapter
latency.

#### Scenario: Shadow read does not delay the response

- **WHEN** a search runs with shadow reading enabled
- **THEN** the response is returned before the secondary search starts
- **AND** the response content is identical to a run with shadow reading disabled

#### Scenario: Shadow comparison recorded

- **WHEN** a shadow read completes
- **THEN** a comparison record is stored with query hash, both adapter names, top-k overlap, rank correlation, and both latencies

#### Scenario: Shadow read failure is silent to the caller

- **WHEN** the secondary adapter raises during a shadow read
- **THEN** the failure is logged and counted
- **AND** the caller observes no error

### Requirement: Object Storage Adapter

The system SHALL provide a secondary adapter backed by an embedded columnar retrieval
engine that stores its tables on a local directory or an S3-compatible object store,
supports BM25, vector, and hybrid search with native filter pushdown, and supports
row-level upsert and delete. The adapter SHALL take its object-store endpoint,
credentials, bucket, and prefix from provider-neutral settings and SHALL never log
credentials.

#### Scenario: Local directory table

- **WHEN** the adapter is configured with a local directory
- **THEN** writes create the namespace tables under that directory
- **AND** hybrid search returns candidates for the written records

#### Scenario: Object store table

- **WHEN** the adapter is configured with an S3-compatible endpoint, bucket, and prefix
- **THEN** the namespace tables are created under that prefix
- **AND** a fresh process can search them without a local copy

#### Scenario: New rows searchable after improve

- **WHEN** rows are written after the text index was last built
- **THEN** the improve action folds them into the text index
- **AND** they appear in BM25 candidates afterwards

#### Scenario: Deleted content removed

- **WHEN** a content record is deleted from the system of record
- **THEN** its chunks are removed from the secondary adapter
- **AND** they no longer appear in any candidate list

### Requirement: Retrieval Observability

The system SHALL emit a structured log event for every adapter action with the
adapter name, namespace, action, record or candidate count, and duration, and SHALL
expose counters for secondary write failures and shadow read failures.

#### Scenario: Action instrumented

- **WHEN** any adapter action completes
- **THEN** exactly one structured event is emitted with adapter, namespace, action, count, and duration

#### Scenario: Failure counters

- **WHEN** a secondary write or shadow read fails
- **THEN** the corresponding counter increments
- **AND** the counters are readable through the operations diagnostics surface
