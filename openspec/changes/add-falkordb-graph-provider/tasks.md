# Tasks: Add FalkorDB Graph Provider

## Phase 1: graphiti-core Upgrade + Provider Foundation

This phase upgrades graphiti-core and introduces the provider abstraction with Neo4j-only to validate no regressions.

- [ ] 1.1 Write tests for GraphDBProvider protocol and Neo4j implementation
  **Spec scenarios**: graph-provider.1 (factory construction), graph-provider.2 (Neo4j local), graph-provider.2 (Neo4j AuraDB), graph-provider.2 (backward compat)
  **Design decisions**: D1 (protocol shape), D3 (backward compat)
  **Dependencies**: None

- [ ] 1.2 Write tests for GraphitiClient with provider injection
  **Spec scenarios**: graph-provider.4 (default construction), graph-provider.4 (explicit injection), graph-provider.4 (all methods work)
  **Design decisions**: D5 (constructor refactoring)
  **Dependencies**: None

- [ ] 1.3 Upgrade graphiti-core to >=0.28.0 in pyproject.toml
  Update dependency from `graphiti-core[anthropic,google-genai]>=0.5.0` to `graphiti-core[neo4j,falkordb,anthropic,google-genai]>=0.28.0`. Run `uv lock` to update lockfile.
  **Spec scenarios**: graph-provider.MODIFIED (updated dependency)
  **Design decisions**: D8 (upgrade strategy)
  **Dependencies**: None

- [ ] 1.4 Create GraphDBProvider protocol and Neo4jGraphDBProvider implementation
  New file `src/storage/graph_provider.py` with:
  - `GraphDBProvider` protocol (create_graphiti_driver, execute_query, execute_write, close, health_check, create_exporter, create_importer)
  - `Neo4jGraphDBProvider` implementation using `Neo4jDriver` from graphiti_core + `neo4j.GraphDatabase` for raw queries
  - `get_graph_provider()` factory function reading from Settings
  **Design decisions**: D1 (protocol), D3 (backward compat)
  **Dependencies**: 1.1, 1.3

- [ ] 1.5 Refactor GraphitiClient to use GraphDBProvider
  Modify `src/storage/graphiti_client.py`:
  - Constructor takes `provider: GraphDBProvider | None` instead of neo4j_uri/user/password
  - Use `provider.create_graphiti_driver()` → `Graphiti(graph_driver=...)`
  - Replace `self.driver.session()` raw Cypher calls with `provider.execute_query()`
  - Call `build_indices_and_constraints()` after initialization
  - Update imports from graphiti_core to match v0.28 API
  **Design decisions**: D5 (constructor), D8 (upgrade)
  **Dependencies**: 1.2, 1.4

- [ ] 1.6 Add graphdb_provider and falkordb_* settings fields
  Modify `src/config/settings.py` and `src/config/profiles.py`:
  - Add `GraphDBProviderType = Literal["neo4j", "falkordb"]`
  - Add `FalkorDBSubProviderType = Literal["local", "lite"]`
  - Add `graphdb_provider`, `falkordb_provider`, `falkordb_host`, `falkordb_port`, `falkordb_username`, `falkordb_password`, `falkordb_database`, `falkordb_lite_data_dir` fields
  - Add `validate_falkordb_provider_config()` validator
  - Update profile flattening to handle `providers.graphdb` and `settings.graphdb.*`
  **Spec scenarios**: graph-provider.7 (settings), graph-provider.7 (profile support), graph-provider.7 (validation)
  **Design decisions**: D2 (settings structure)
  **Dependencies**: 1.1

- [ ] 1.7 Update ReferenceGraphSync to use provider
  Modify `src/services/reference_graph_sync.py`:
  - Accept `GraphDBProvider` instead of using `GraphitiClient.driver` directly
  - Replace `driver.session().run()` with `provider.execute_query()` / `provider.execute_write()`
  **Spec scenarios**: graph-provider.5 (citation creation), graph-provider.5 (episode lookup)
  **Design decisions**: D1 (raw query interface)
  **Dependencies**: 1.4

- [ ] 1.8 Write tests for ReferenceGraphSync with provider
  **Spec scenarios**: graph-provider.5 (citation creation on both backends), graph-provider.5 (episode lookup)
  **Design decisions**: D1
  **Dependencies**: 1.7

- [ ] 1.9 Verify all existing tests pass after graphiti-core upgrade
  Run full test suite (`pytest`). Fix any import changes, API signature updates, or behavioral differences from the graphiti-core upgrade.
  **Dependencies**: 1.3, 1.4, 1.5

## Phase 2: FalkorDB Provider + Infrastructure

This phase adds FalkorDB as a second backend option.

- [ ] 2.1 Write tests for FalkorDBGraphDBProvider
  **Spec scenarios**: graph-provider.3 (Docker provider), graph-provider.3 (Lite provider), graph-provider.3 (Cypher compat), graph-provider.3 (datetime handling)
  **Design decisions**: D7 (Cypher compatibility)
  **Dependencies**: 1.4

- [ ] 2.2 Create FalkorDBGraphDBProvider implementation
  Add to `src/storage/graph_provider.py`:
  - `FalkorDBGraphDBProvider` using `FalkorDriver` from graphiti_core + `falkordb.FalkorDB` for raw queries
  - Handle datetime compatibility (D7): convert `datetime()` calls to ISO-8601 strings
  - Update `get_graph_provider()` factory to handle `graphdb_provider: "falkordb"`
  **Design decisions**: D1 (protocol), D7 (Cypher compat)
  **Dependencies**: 2.1, 1.4

- [ ] 2.3 Add FalkorDB Docker service
  Modify `docker-compose.yml`:
  - Add `falkordb` service using `falkordb/falkordb:latest` image
  - Map port 6379 (or 6380 to avoid Redis conflict)
  - Add persistent volume `falkordb_data`
  - Add health check
  **Spec scenarios**: graph-provider.8 (Docker Compose service)
  **Dependencies**: None

- [ ] 2.4 Create FalkorDB Lite test fixture
  New file `tests/helpers/falkordb_lite.py`:
  - `FalkorDBLiteFixture` class managing embedded subprocess
  - Session-scoped startup/shutdown
  - Function-scoped data reset
  New file `tests/integration/fixtures/falkordb.py`:
  - `falkordb_lite` fixture, `falkordb_provider` fixture, `requires_falkordb` marker
  **Spec scenarios**: graph-provider.8 (Lite test fixture)
  **Design decisions**: D4 (Lite for tests)
  **Dependencies**: 2.2

- [ ] 2.5 Write integration tests — GraphitiClient on FalkorDB
  Test all GraphitiClient methods (add_content_summary, search_related_concepts, get_temporal_context, etc.) against FalkorDB Lite backend. Verify identical results to Neo4j.
  **Spec scenarios**: graph-provider.4 (all methods work on both backends)
  **Dependencies**: 2.2, 2.4

- [ ] 2.6 Update profile YAML files for FalkorDB support
  Modify `profiles/base.yaml`, `profiles/local.yaml`, and add `profiles/local-falkordb.yaml`:
  - Add `providers.graphdb` section with interpolation
  - Add `settings.graphdb.*` section with FalkorDB defaults
  - Create a convenience profile for FalkorDB local dev
  **Spec scenarios**: graph-provider.7 (profile support)
  **Dependencies**: 1.6

## Phase 3: Export/Import Abstraction

- [ ] 3.1 Write tests for GraphExporter/GraphImporter protocols
  **Spec scenarios**: graph-provider.6 (export nodes), graph-provider.6 (import nodes), graph-provider.6 (cross-backend portability), graph-provider.6 (clean mode)
  **Design decisions**: D6 (export/import protocols)
  **Dependencies**: 1.4

- [ ] 3.2 Create GraphExporter/GraphImporter protocols and data models
  New file `src/storage/graph_export.py`:
  - `NodeRecord`, `RelationshipRecord`, `ExportManifest` (renamed from Neo4j-prefixed models)
  - `GraphExporter` and `GraphImporter` protocols
  **Design decisions**: D6
  **Dependencies**: 3.1

- [ ] 3.3 Refactor Neo4j exporter to implement GraphExporter
  Modify `src/sync/neo4j_exporter.py`:
  - Implement `GraphExporter` protocol
  - Use `provider.execute_query()` instead of direct driver sessions
  - Keep as `Neo4jGraphExporter` class, import `NodeRecord`/`RelationshipRecord` from `graph_export.py`
  **Dependencies**: 3.2, 1.4

- [ ] 3.4 Create FalkorDB exporter implementing GraphExporter
  New file `src/sync/falkordb_exporter.py` (or add to existing):
  - `FalkorDBGraphExporter` using FalkorDB provider's query interface
  - Same JSONL output format as Neo4j exporter
  **Dependencies**: 3.2, 2.2

- [ ] 3.5 Refactor Neo4j importer to implement GraphImporter
  Modify `src/sync/neo4j_importer.py`:
  - Implement `GraphImporter` protocol
  - Use `provider.execute_write()` instead of direct driver sessions
  **Dependencies**: 3.2, 1.4

- [ ] 3.6 Create FalkorDB importer implementing GraphImporter
  New or extended file for FalkorDB import using provider's write interface.
  **Dependencies**: 3.2, 2.2

- [ ] 3.7 Update sync CLI commands to use provider
  Modify `src/cli/sync_commands.py`:
  - Replace direct `GraphDatabase.driver()` usage with `get_graph_provider()`
  - Use `provider.create_exporter()` / `provider.create_importer()` instead of `Neo4jExporter` / `Neo4jImporter` directly
  **Spec scenarios**: graph-provider.MODIFIED (sync CLI)
  **Dependencies**: 3.3, 3.4, 3.5, 3.6

- [ ] 3.8 Write cross-backend round-trip integration test
  Export from Neo4j, import to FalkorDB (and vice versa). Verify data integrity.
  **Spec scenarios**: graph-provider.6 (cross-backend portability)
  **Dependencies**: 3.3, 3.4, 3.5, 3.6

## Phase 4: CLI, Documentation, and Polish

- [ ] 4.1 Update graph CLI commands for provider transparency
  Modify `src/cli/graph_commands.py`:
  - Ensure `extract-entities` and `query` use GraphitiClient with default provider
  - No user-visible changes needed (already delegates to GraphitiClient)
  **Spec scenarios**: graph-provider.MODIFIED (CLI graph commands)
  **Dependencies**: 1.5

- [ ] 4.2 Update CLI adapters
  Modify `src/cli/adapters.py`:
  - Update `search_graph_sync()` and `extract_themes_from_graph_sync()` if they construct GraphitiClient directly
  **Dependencies**: 1.5

- [ ] 4.3 Update theme_analyzer and historical_context processors
  Modify `src/processors/theme_analyzer.py` and `src/processors/historical_context.py`:
  - Ensure they construct GraphitiClient without explicit Neo4j params (use default provider)
  **Dependencies**: 1.5

- [ ] 4.4 Update agent memory GraphStrategy
  Modify `src/agents/memory/strategies/graph.py`:
  - Ensure it works with the refactored GraphitiClient API
  - Verify loose-typed client interface still holds with provider-backed client
  **Dependencies**: 1.5

- [ ] 4.5 Add Makefile targets for FalkorDB
  Add `falkordb-up`, `falkordb-down` targets. Update `dev-bg` to optionally start FalkorDB.
  **Dependencies**: 2.3

- [ ] 4.6 Update documentation
  Modify `docs/SETUP.md`, `docs/ARCHITECTURE.md`, `CLAUDE.md`:
  - Document `graphdb_provider` setting and FalkorDB configuration
  - Update architecture diagrams
  - Add FalkorDB to the providers table
  **Dependencies**: All previous phases

- [ ] 4.7 End-to-end validation
  Run `aca pipeline daily` with `GRAPHDB_PROVIDER=falkordb` against Docker FalkorDB. Verify:
  - Content ingestion populates knowledge graph
  - Theme analysis queries return results
  - Reference sync creates citation edges
  - Export/import round-trips successfully
  **Dependencies**: All previous phases
