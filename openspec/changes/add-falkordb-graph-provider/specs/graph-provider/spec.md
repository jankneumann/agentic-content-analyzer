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

#### Scenario: Provider cleanup
WHEN a caller invokes `provider.close()`
THEN the provider SHALL close all connections and release resources
AND subsequent operations SHALL raise an appropriate error.

---

### Requirement: Neo4j Provider Implementation

The system SHALL provide a `Neo4jGraphDBProvider` that wraps Neo4j connectivity for both Graphiti and raw Cypher operations.

#### Scenario: Neo4j local provider
WHEN `graphdb_provider` is `"neo4j"` AND `neo4j_provider` is `"local"`
THEN the provider SHALL connect using `neo4j_local_uri` (or fallback `neo4j_uri`)
AND use `neo4j_local_user` / `neo4j_local_password` credentials
AND construct a `Neo4jDriver` from `graphiti_core.driver.neo4j_driver`.

#### Scenario: Neo4j AuraDB provider
WHEN `graphdb_provider` is `"neo4j"` AND `neo4j_provider` is `"auradb"`
THEN the provider SHALL connect using `neo4j_auradb_uri`
AND use `neo4j_auradb_user` / `neo4j_auradb_password` credentials
AND validate that required AuraDB fields are configured.

#### Scenario: Backward compatibility with existing settings
WHEN `graphdb_provider` is not explicitly set
THEN it SHALL default to `"neo4j"`
AND the system SHALL behave identically to the pre-abstraction implementation
AND existing `neo4j_*` settings, profiles, and .env files SHALL continue to work.

---

### Requirement: FalkorDB Provider Implementation

The system SHALL provide a `FalkorDBGraphDBProvider` that wraps FalkorDB connectivity.

#### Scenario: FalkorDB Docker provider
WHEN `graphdb_provider` is `"falkordb"` AND `falkordb_provider` is `"local"`
THEN the provider SHALL connect to FalkorDB using `falkordb_host` and `falkordb_port`
AND use `falkordb_username` / `falkordb_password` if configured
AND construct a `FalkorDriver` from `graphiti_core.driver.falkordb_driver`.

#### Scenario: FalkorDB Lite provider
WHEN `graphdb_provider` is `"falkordb"` AND `falkordb_provider` is `"lite"`
THEN the provider SHALL start or connect to an embedded FalkorDB Lite instance
AND use `falkordb_lite_data_dir` for file-based storage
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

#### Scenario: Default provider construction
WHEN `GraphitiClient()` is constructed without arguments
THEN it SHALL obtain a provider via `get_graph_provider()`
AND pass `provider.create_graphiti_driver()` to `Graphiti(graph_driver=...)`.

#### Scenario: Explicit provider injection
WHEN `GraphitiClient(provider=some_provider)` is constructed with a provider
THEN it SHALL use that provider instead of the default
AND this SHALL be the primary testing seam for graph backend switching.

#### Scenario: All existing GraphitiClient methods work on both backends
WHEN any existing method (add_content_summary, search_related_concepts, get_temporal_context, etc.) is called
THEN it SHALL produce correct results on both Neo4j and FalkorDB backends
AND the method signatures SHALL not change.

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

The system SHALL provide `GraphExporter` and `GraphImporter` protocols that work across backends.

#### Scenario: Export nodes from any backend
WHEN `exporter.export_nodes(label)` is called
THEN it SHALL return all nodes with the given label as `NodeRecord` instances
AND the JSONL serialization format SHALL be identical regardless of backend.

#### Scenario: Import nodes to any backend
WHEN `importer.import_node(record)` is called
THEN it SHALL create or update the node using idempotent MERGE by UUID
AND return the UUID of the affected node.

#### Scenario: Cross-backend portability
WHEN data is exported from Neo4j and imported to FalkorDB (or vice versa)
THEN the import SHALL succeed
AND all nodes, relationships, and properties SHALL be preserved.

#### Scenario: Clean mode import
WHEN import is run with `mode="clean"`
THEN all existing nodes and relationships SHALL be deleted before import
AND the deletion SHALL work on both backends.

---

### Requirement: Settings and Configuration

The system SHALL provide `graphdb_provider` and `falkordb_*` settings fields that integrate with the profile system and support environment variable overrides.

#### Scenario: graphdb_provider setting
WHEN `graphdb_provider` is set to `"falkordb"`
THEN the system SHALL use FalkorDB for all graph operations
AND `falkordb_*` settings SHALL be used for connection configuration.

#### Scenario: Profile support
WHEN a profile YAML includes `providers.graphdb: falkordb`
THEN the profile system SHALL set `graphdb_provider` to `"falkordb"`
AND `settings.graphdb.*` section SHALL configure FalkorDB-specific fields.

#### Scenario: Validation
WHEN `graphdb_provider` is `"falkordb"` AND `falkordb_provider` is `"local"`
AND `falkordb_host` is not reachable
THEN the health check SHALL return False
AND the system SHALL log a clear error message identifying the misconfiguration.

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
AND each test function SHALL get a clean graph state
AND the instance SHALL shut down after the test session.

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
WHEN `aca sync export --neo4j-only` or `aca sync import --neo4j-only` is run
THEN the command SHALL use the graph provider abstraction
AND the `--neo4j-only` flag name SHALL be preserved for backward compatibility
AND the operation SHALL work on whichever backend is configured.
