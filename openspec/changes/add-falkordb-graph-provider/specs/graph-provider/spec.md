# Spec: Graph Database Provider Abstraction

## ADDED Requirements

### Requirement: GraphDB Provider Protocol

The system SHALL provide a `GraphDBProvider` protocol that abstracts graph database access across backend implementations.

#### Scenario: Provider construction via factory
WHEN a caller requests a graph provider via `get_graph_provider()`
THEN the factory SHALL read `graphdb_provider` from Settings
AND construct the appropriate provider implementation (Neo4j or FalkorDB)
AND return a fully initialized provider ready for queries.

#### Scenario: Provider exposes graphiti-core driver
WHEN a caller invokes `provider.create_graphiti_driver()`
THEN the provider SHALL return a `GraphDriver` instance compatible with `Graphiti(graph_driver=...)` constructor
AND the driver type SHALL match the configured backend (Neo4jDriver or FalkorDriver).

#### Scenario: Provider executes raw queries
WHEN a caller invokes `provider.execute_query(cypher, params)`
THEN the provider SHALL execute the openCypher query against the configured backend
AND return results as a list of dictionaries
AND handle session/connection lifecycle internally.

#### Scenario: Provider write operations
WHEN a caller invokes `provider.execute_write(cypher, params)`
THEN the provider SHALL execute the write query within an appropriate transaction
AND return a summary dictionary with operation metadata.

#### Scenario: Provider health check
WHEN a caller invokes `provider.health_check()`
THEN the provider SHALL verify connectivity to the graph backend
AND return True if the backend is reachable and responsive
AND return False otherwise without raising exceptions.

#### Scenario: Provider sync cleanup
WHEN a caller invokes `provider.close()` (synchronous)
THEN the provider SHALL close all connections and release resources
AND subsequent operations SHALL raise an appropriate error.

#### Scenario: Provider async cleanup
WHEN a caller invokes `await provider.aclose()` (asynchronous)
THEN the provider SHALL close all connections and release resources asynchronously.

#### Scenario: Provider startup logging
WHEN a provider is constructed
THEN it SHALL log at INFO level the backend type, deployment mode, and connection target.

#### Scenario: Provider slow query logging
WHEN a query takes longer than 5 seconds to execute
THEN the provider SHALL log at WARN level with the query text (truncated to 200 chars) and elapsed time.

---

### Requirement: Neo4j Provider Implementation

The system SHALL provide a `Neo4jGraphDBProvider` that wraps Neo4j connectivity for both Graphiti and raw Cypher operations.

#### Scenario: Neo4j local mode
WHEN `graphdb_provider` is `"neo4j"` AND `graphdb_mode` is `"local"`
THEN the provider SHALL connect using `neo4j_uri`
AND use `neo4j_user` / `neo4j_password` credentials
AND construct a `Neo4jDriver` from `graphiti_core.driver.neo4j_driver`.

#### Scenario: Neo4j cloud mode
WHEN `graphdb_provider` is `"neo4j"` AND `graphdb_mode` is `"cloud"`
THEN the provider SHALL connect using `neo4j_cloud_uri`
AND use `neo4j_cloud_user` / `neo4j_cloud_password` credentials
AND validate that required cloud fields are configured.

#### Scenario: Neo4j embedded mode rejected
WHEN `graphdb_provider` is `"neo4j"` AND `graphdb_mode` is `"embedded"`
THEN the validator SHALL reject this combination with a clear error message
AND the system SHALL not start.

#### Scenario: Backward compatibility with existing settings
WHEN `graphdb_provider` is not explicitly set
THEN it SHALL default to `"neo4j"` with `graphdb_mode` defaulting to `"local"`
AND the system SHALL behave identically to the pre-abstraction implementation.

#### Scenario: Deprecated neo4j_provider alias
WHEN `neo4j_provider` is set but `graphdb_provider` is not
THEN the system SHALL map `neo4j_provider: local` to `graphdb_provider: neo4j, graphdb_mode: local`
AND map `neo4j_provider: auradb` to `graphdb_provider: neo4j, graphdb_mode: cloud`
AND log a deprecation warning.

---

### Requirement: FalkorDB Provider Implementation

The system SHALL provide a `FalkorDBGraphDBProvider` that wraps FalkorDB connectivity.

#### Scenario: FalkorDB local mode
WHEN `graphdb_provider` is `"falkordb"` AND `graphdb_mode` is `"local"`
THEN the provider SHALL connect to FalkorDB using `falkordb_host` and `falkordb_port`
AND use `falkordb_username` / `falkordb_password` if configured
AND construct a `FalkorDriver` from `graphiti_core.driver.falkordb_driver`.

#### Scenario: FalkorDB cloud mode
WHEN `graphdb_provider` is `"falkordb"` AND `graphdb_mode` is `"cloud"`
THEN the provider SHALL connect using `falkordb_cloud_host` and `falkordb_cloud_port`
AND use `falkordb_cloud_password` for authentication.

#### Scenario: FalkorDB embedded mode
WHEN `graphdb_provider` is `"falkordb"` AND `graphdb_mode` is `"embedded"`
THEN the provider SHALL start or connect to an embedded FalkorDB Lite instance
AND use `falkordb_lite_data_dir` for file-based storage (or temp directory if unset)
AND the instance SHALL require no external Docker or server process.

#### Scenario: FalkorDB raw Cypher compatibility
WHEN a raw Cypher query is executed via `provider.execute_query()`
AND the query uses openCypher patterns (MATCH, MERGE, CREATE, DELETE, SET, RETURN)
THEN the query SHALL execute successfully on FalkorDB
AND return results in the same dictionary format as the Neo4j provider.

#### Scenario: FalkorDB datetime handling
WHEN a Cypher query uses Neo4j's `datetime()` function
THEN the FalkorDB provider SHALL handle this via ISO-8601 string representation
AND temporal ordering and comparison operations SHALL produce correct results.

---

### Requirement: GraphitiClient Provider Integration

The `GraphitiClient` SHALL use `GraphDBProvider` instead of direct Neo4j driver construction.

#### Scenario: Async factory construction
WHEN `await GraphitiClient.create()` is called without arguments
THEN it SHALL obtain a provider via `get_graph_provider()`
AND pass `provider.create_graphiti_driver()` to `Graphiti(graph_driver=...)`
AND call `await graphiti.build_indices_and_constraints()` before returning.

#### Scenario: Explicit provider injection
WHEN `await GraphitiClient.create(provider=some_provider)` is called with a provider
THEN it SHALL use that provider instead of the default
AND this SHALL be the primary testing seam for graph backend switching.

#### Scenario: Graceful degradation when graph backend unavailable
WHEN `GraphitiClient.create()` is called AND the graph backend is unreachable
THEN it SHALL raise `GraphBackendUnavailableError`
AND callers in processors (theme_analyzer, historical_context) SHALL catch this error
AND log a warning and return empty results
AND core pipeline operations (ingest, summarize, digest) SHALL continue without graph enrichment.

#### Scenario: All existing GraphitiClient methods work on both backends
WHEN any existing method (add_content_summary, search_related_concepts, get_temporal_context, etc.) is called
THEN it SHALL produce correct results on both Neo4j and FalkorDB backends
AND the method signatures SHALL not change.

#### Scenario: Sync close facade
WHEN `client.close()` is called synchronously
THEN it SHALL close the provider and release resources
AND existing sync callers (CLI adapters) SHALL continue to work without modification.

---

### Requirement: Reference Graph Sync Provider Integration

The `ReferenceGraphSync` service SHALL use `GraphDBProvider` for graph operations.

#### Scenario: Citation edge creation on both backends
WHEN `sync_reference(ref)` is called
THEN it SHALL use `provider.execute_write()` to create CITES edges
AND the operation SHALL work identically on Neo4j and FalkorDB.

#### Scenario: Episode lookup on both backends
WHEN `_find_episode_uuid(content_id)` is called
THEN it SHALL use `provider.execute_query()` to find matching episodes
AND return the UUID if found, None otherwise.

---

### Requirement: Graph Export/Import Abstraction

The system SHALL provide file-level export/import operations on `GraphDBProvider` that work across backends.

#### Scenario: Export graph to file
WHEN `provider.export_graph(output_path)` is called
THEN it SHALL write all nodes and relationships to a JSONL file at the given path
AND the JSONL format SHALL use `graph_node`, `graph_relationship`, `graph_manifest` record types
AND return an `ExportManifest` with counts and metadata.

#### Scenario: Import graph from file
WHEN `provider.import_graph(input_path, mode="merge")` is called
THEN it SHALL read JSONL records and create or update nodes/relationships using idempotent MERGE by UUID
AND return `ImportStats` with inserted/skipped/updated/failed counts.

#### Scenario: Cross-backend portability
WHEN data is exported from Neo4j and imported to FalkorDB (or vice versa)
THEN the import SHALL succeed
AND all nodes, relationships, and properties SHALL be preserved.

#### Scenario: Clean mode import
WHEN `provider.import_graph(input_path, mode="clean")` is called
THEN all existing nodes and relationships SHALL be deleted before import
AND the deletion SHALL work on both backends.

---

### Requirement: Settings and Configuration

The system SHALL provide `graphdb_provider` and `falkordb_*` settings fields that integrate with the profile system and support environment variable overrides.

#### Scenario: graphdb_provider setting
WHEN `graphdb_provider` is set to `"falkordb"`
THEN the system SHALL use FalkorDB for all graph operations
AND the connection fields read SHALL depend on `graphdb_mode`.

#### Scenario: graphdb_mode setting
WHEN `graphdb_mode` is set
THEN the factory SHALL use the mode-specific connection fields for the configured provider
AND invalid provider+mode combinations (e.g., neo4j+embedded) SHALL be rejected at validation time.

#### Scenario: Profile support
WHEN a profile YAML includes `providers.graphdb: falkordb`
THEN the profile system SHALL set `graphdb_provider` to `"falkordb"`
AND `settings.graphdb.*` section SHALL configure `graphdb_mode` and connection fields.

#### Scenario: Validation
WHEN `graphdb_provider` is `"falkordb"` AND `graphdb_mode` is `"local"`
AND `falkordb_host` is not reachable
THEN the health check SHALL return False
AND the system SHALL log a clear error message identifying the misconfiguration.

#### Scenario: Profile flattening
WHEN a profile defines `providers.graphdb` and `settings.graphdb.*`
THEN `providers.graphdb` SHALL set `graphdb_provider`
AND `settings.graphdb.graphdb_mode` SHALL set the deployment mode
AND all fields under `settings.graphdb.*` SHALL be flattened to top-level Settings fields
AND the factory SHALL only read fields relevant to the configured provider+mode combination.

---

### Requirement: Infrastructure

The system SHALL provide FalkorDB infrastructure for both production (Docker) and testing (FalkorDB Lite embedded) deployment modes.

#### Scenario: Docker Compose FalkorDB service
WHEN `docker compose up -d` is run
THEN a FalkorDB service SHALL be available on port 6379
AND it SHALL be configured with a persistent volume for data storage
AND it SHALL be in the same Docker network as other services.

#### Scenario: FalkorDB Lite test fixture
WHEN graph-related tests run
THEN a session-scoped FalkorDB Lite instance SHALL start automatically
AND each test function SHALL get a clean graph state via FLUSHALL
AND the instance SHALL shut down after the test session.

#### Scenario: FalkorDB Lite orphan cleanup
WHEN the test process crashes or is killed
THEN the FalkorDB Lite subprocess SHALL be cleaned up via atexit handler
AND a PID file SHALL be written to detect and kill orphaned processes on next startup.

#### Scenario: Docker image pinning
WHEN the FalkorDB Docker service is defined in docker-compose.yml
THEN the image SHALL be pinned to a specific tested version (not `latest`).

---

## MODIFIED Requirements

### Requirement: graphiti-core Version

The project SHALL use graphiti-core version 0.28.0 or later with both Neo4j and FalkorDB backend extras.

#### Scenario: Updated dependency
WHEN the project dependencies are installed
THEN `graphiti-core` SHALL be version `>=0.28.0`
AND extras SHALL include `[neo4j,falkordb,anthropic,google-genai]`.

### Requirement: CLI Graph Commands

The graph CLI commands SHALL operate transparently across configured graph backends.

#### Scenario: Backend-transparent CLI
WHEN `aca graph extract-entities` or `aca graph query` is run
THEN the command SHALL use the configured `graphdb_provider`
AND output SHALL be identical regardless of backend.

### Requirement: CLI Sync Commands

The sync CLI commands SHALL use the graph provider abstraction for export/import operations.

#### Scenario: Export/import with provider
WHEN `aca sync export --graph-only` or `aca sync import --graph-only` is run
THEN the command SHALL use the graph provider abstraction
AND the operation SHALL work on whichever backend is configured.

#### Scenario: Legacy flag alias
WHEN `--neo4j-only` is used as a CLI flag
THEN it SHALL be accepted as an alias for `--graph-only`
AND a deprecation warning SHALL be logged when used with a non-Neo4j backend.
