## MODIFIED Requirements

### Requirement: Memory Provider

The system SHALL persist and recall agent memory through a configurable provider built from
settings, supporting a hybrid recall strategy across prior tasks and insights, SHALL report
partial persistence truthfully, and SHALL store each insight once with a maturity-aware pointer
in memory.

#### Scenario: Store and recall with hybrid strategy
- **WHEN** an agent stores a memory entry and a subsequent recall query is made
- **THEN** the memory provider SHALL query all configured strategies (graph, vector, keyword) in parallel
- **AND** merge results using weighted Reciprocal Rank Fusion
- **AND** apply recency and frequency weighting to the merged results
- **AND** return deduplicated, ranked memory entries
- **AND** update `access_count` and `last_accessed_at` for returned entries

#### Scenario: Memory strategy configuration
- **WHEN** a memory provider is initialized with a strategy configuration dict (e.g., `{"graph": 0.4, "vector": 0.4, "keyword": 0.2}`)
- **THEN** the provider SHALL support any combination of `graph`, `vector`, `keyword`
- **AND** accept per-strategy weight configuration (0.0 to 1.0)
- **AND** gracefully degrade if a backend is unavailable (e.g., Neo4j down → skip graph strategy)
- **AND** log warnings for unavailable strategies without failing

#### Scenario: Memory strategies are built from settings
- **WHEN** the durable worker constructs the conductor
- **THEN** it SHALL build the provider with `build_memory_strategies(settings)` using the weights in `agent_memory_strategies` (default keyword 0.6, vector 0.4)
- **AND** it SHALL NOT construct a provider with an empty strategy map
- **AND** a strategy whose backend is not configured SHALL be omitted with a logged warning rather than failing task execution

#### Scenario: Vector strategy validates the embedding dimension
- **WHEN** the factory builds the vector strategy
- **THEN** it SHALL compare the `agent_memories.embedding` column dimension with the configured embedding provider's dimension
- **AND** on mismatch it SHALL disable the vector strategy with a warning that names both dimensions
- **AND** keyword recall SHALL continue to work

#### Scenario: Partial store is reported
- **WHEN** `store` succeeds on at least one strategy and fails on another
- **THEN** it SHALL return a `MemoryStoreOutcome` with `status = "partial"` and a per-strategy outcome map
- **AND** the memory ID SHALL be the same across every strategy that stored it
- **AND** the conductor SHALL log the partial outcome at warning level and record it in memory telemetry

#### Scenario: Store fails on every strategy
- **WHEN** no strategy stores the entry
- **THEN** `store` SHALL return `status = "failed"` without raising
- **AND** task execution SHALL continue

#### Scenario: Insights are stored once
- **WHEN** the conductor stores a generated insight
- **THEN** the full record SHALL be written to `agent_insights` only
- **AND** the memory entry SHALL be a pointer with `memory_type = insight`, a tag `insight:<uuid>`, and content limited to the title and a bounded excerpt
- **AND** recall SHALL resolve the pointer and SHALL omit entries whose insight is `superseded` or `withdrawn`

#### Scenario: Recall filters by maturity
- **WHEN** `recall` is called with `MemoryFilter(maturity=["active"])`
- **THEN** only pointers whose insight has that maturity SHALL be returned
- **AND** non-insight memory types SHALL be unaffected by the maturity filter
