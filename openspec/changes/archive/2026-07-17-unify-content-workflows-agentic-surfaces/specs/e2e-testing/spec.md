## ADDED Requirements

### Requirement: Registry-generated vertical source coverage

CI SHALL execute a deterministic vertical contract for every registry descriptor covering fixture ingestion, canonical content persistence, persisted summarization, resolved workflow selection, digest persistence, and podcast context assembly. Registry and fixture key sets MUST be equal. The dynamically routed `url` descriptor SHALL cover webpage, YouTube video, YouTube playlist, RSS, and forced-webpage variants.

#### Scenario: Every source reaches podcast context
- **WHEN** vertical source contracts run
- **THEN** each registered source produces eligible canonical summarized content
- **AND** that content can be persisted in a digest and exposed to podcast generation
- **AND** each URL routing variant reports the same normalized command and resolved-route fields across interfaces

#### Scenario: Missing source fixture fails CI
- **WHEN** a registry descriptor has no vertical fixture
- **THEN** contract collection fails before tests execute
- **AND** the missing canonical key is reported

### Requirement: Mixed-source provenance coverage

CI SHALL cover all source pairs, the `gmail/rss/substack` triple, and the `scholar_search/arxiv_search/huggingface_papers` triple using deterministic fixtures. Every case MUST assert canonical counts and provenance invariants.

#### Scenario: Pairwise source matrix
- **WHEN** the pairwise matrix runs
- **THEN** every pair completes ingestion through podcast context assembly
- **AND** duplicate cross-source content contributes one canonical summarized item

#### Scenario: High-risk triples preserve filters
- **WHEN** either declared high-risk triple runs with a source-filtered digest
- **THEN** themes, digest sources, and podcast available IDs contain only the selected canonical items

### Requirement: Cross-interface conformance coverage

CI SHALL submit representative commands through direct application services, CLI JSON mode, HTTP, MCP HTTP mode, MCP in-process mode, and the frontend API client. Equivalent inputs MUST validate against the same operation, problem, capability, and resource schemas.

#### Scenario: Operation contracts match across interfaces
- **WHEN** an equivalent digest request is submitted through every interface
- **THEN** submission and terminal operation payloads conform to the same schemas
- **AND** every successful result identifies a persisted digest

#### Scenario: Invalid ingestion command matches across interfaces
- **WHEN** the same unsupported source option is submitted through every interface
- **THEN** each rejects it before enqueueing
- **AND** error codes and field paths are semantically equivalent

### Requirement: Workflow edge-case coverage

The end-to-end suite SHALL cover duplicate aliases, null dates, explicit ingestion-date selection, filtered and failed content, missing summaries, force reprocessing, partial source failure, idempotent resubmission, cancellation, retry, and version 1 queue-drain compatibility.

#### Scenario: Duplicate and null-date edge cases
- **WHEN** mixed fixtures contain aliases and null publication dates
- **THEN** default workflow resolution excludes them with structured reasons
- **AND** explicit ingestion-date selection includes only otherwise eligible null-date records

#### Scenario: Retry remains idempotent
- **WHEN** a resource-producing operation fails after resource reservation and is retried
- **THEN** the retry completes or updates the reserved resource
- **AND** it does not create a second logical resource
