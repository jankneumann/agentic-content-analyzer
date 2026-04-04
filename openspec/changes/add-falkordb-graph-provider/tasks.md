# Tasks: Add FalkorDB Graph Provider

## Phase 1: graphiti-core Upgrade + Provider Foundation

This phase upgrades graphiti-core and introduces the provider abstraction with Neo4j-only to validate no regressions.

- [ ] 1.1 Write tests for GraphDBProvider protocol and Neo4j implementation
  **Spec scenarios**: graph-provider.1 (factory construction, raw queries, health check, startup logging, slow query logging), graph-provider.2 (Neo4j local, AuraDB, backward compat)
  **Design decisions**: D1 (protocol shape), D2 (profile flattening precedence), D3 (backward compat), D10 (observability)
  **Dependencies**: None

- [ ] 1.2 Write tests for GraphitiClient async factory and graceful degradation
  **Spec scenarios**: graph-provider.4 (async factory, explicit injection, graceful degradation, sync close)
  **Design decisions**: D5 (async factory), D9 (graceful degradation)
  **Dependencies**: None

- [ ] 1.3 Upgrade graphiti-core to >=0.28.0 in pyproject.toml
  Update dependency from `graphiti-core[anthropic,google-genai]>=0.5.0` to `graphiti-core[neo4j,falkordb,anthropic,google-genai]>=0.28.0`. Run `uv lock` to update lockfile.
  **Spec scenarios**: graph-provider.MODIFIED (updated dependency)
  **Design decisions**: D8 (upgrade strategy)
  **Dependencies**: None

- [ ] 1.4 Create GraphDBProvider protocol and Neo4jGraphDBProvider in `src/storage/graph_provider.py`
  - `GraphDBProvider` protocol: create_graphiti_driver, execute_query, execute_write, close (sync), aclose (async), health_check, export_graph, import_graph
  - `Neo4jGraphDBProvider` using `Neo4jDriver` from graphiti_core + `neo4j.GraphDatabase` for raw queries
  - `get_graph_provider()` factory function reading from Settings
  - `GraphBackendUnavailableError` exception class
  - INFO logging on construction, WARN on slow queries (>5s)
  **Design decisions**: D1 (protocol), D3 (backward compat), D10 (observability)
  **Dependencies**: 1.1, 1.3

- [ ] 1.5 Refactor GraphitiClient to use async factory + provider
  Modify `src/storage/graphiti_client.py`:
  - Add `async classmethod create(provider=None)` — constructs Graphiti, calls `await build_indices_and_constraints()`
  - Private `__init__` takes provider + graphiti instance
  - Replace `self.driver.session()` raw Cypher calls with `provider.execute_query()`
  - Keep `close()` as sync facade calling `provider.close()`
  - Update imports from graphiti_core to match v0.28 API
  - Raise `GraphBackendUnavailableError` if health check fails during create()
  **Design decisions**: D5 (async factory), D9 (graceful degradation)
  **Dependencies**: 1.2, 1.4

- [ ] 1.6 Add graphdb_provider and falkordb_* settings fields + profile flattening
  Modify `src/config/settings.py` and `src/config/profiles.py`:
  - Add `GraphDBProviderType = Literal["neo4j", "falkordb"]`
  - Add `FalkorDBSubProviderType = Literal["local", "lite"]`
  - Add `graphdb_provider`, `falkordb_provider`, `falkordb_host`, `falkordb_port`, `falkordb_username`, `falkordb_password`, `falkordb_database`, `falkordb_lite_data_dir` fields
  - Add `validate_falkordb_provider_config()` validator
  - Add `providers.graphdb` mapping to `_flatten_profile_to_settings()` (applied FIRST)
  - Add `settings.graphdb` section handling alongside existing `settings.neo4j`
  - Write dedicated tests for two-level flattening precedence (graphdb_provider + neo4j_provider)
  **Spec scenarios**: graph-provider.7 (settings, profile support, validation, profile flattening precedence)
  **Design decisions**: D2 (settings structure, flattening precedence)
  **Dependencies**: 1.1

- [ ] 1.7 Update ReferenceGraphSync to use provider
  Modify `src/services/reference_graph_sync.py`:
  - Accept `GraphDBProvider` instead of using `GraphitiClient.driver` directly
  - Replace `driver.session().run()` with `provider.execute_query()` / `provider.execute_write()`
  **Spec scenarios**: graph-provider.5 (citation creation), graph-provider.5 (episode lookup)
  **Design decisions**: D1 (raw query interface)
  **Dependencies**: 1.4

- [ ] 1.8 Write tests for ReferenceGraphSync with provider (Neo4j)
  Test with mocked Neo4j provider — verify query patterns and fire-and-forget behavior.
  **Spec scenarios**: graph-provider.5 (citation creation, episode lookup)
  **Design decisions**: D1
  **Dependencies**: 1.7

- [ ] 1.9 Update connection_checker.py and manage_commands.py for provider
  Modify `src/services/connection_checker.py` and `src/cli/manage_commands.py`:
  - Use `provider.health_check()` for graph backend status instead of direct Neo4j driver
  - Report correct backend name in status output
  **Dependencies**: 1.4

- [ ] 1.10 Verify all existing tests pass after graphiti-core upgrade
  Run full test suite (`pytest`). Fix any import changes, API signature updates, or behavioral differences from the graphiti-core upgrade.
  **Dependencies**: 1.3, 1.4, 1.5

## Phase 2: FalkorDB Provider + Infrastructure

This phase adds FalkorDB as a second backend option.

- [ ] 2.1 Write tests for FalkorDBGraphDBProvider (unit tests with mocks)
  Test driver construction, raw query routing, health check, close lifecycle.
  Do NOT test live LLM/embedder behavior — that's Graphiti's responsibility.
  **Spec scenarios**: graph-provider.3 (Docker provider, Lite provider, Cypher compat, datetime handling)
  **Design decisions**: D7 (Cypher compatibility)
  **Dependencies**: 1.4

- [ ] 2.2 Create FalkorDBGraphDBProvider in `src/storage/falkordb_provider.py`
  Separate file from graph_provider.py (clean file ownership per work package):
  - `FalkorDBGraphDBProvider` using `FalkorDriver` from graphiti_core + `falkordb.FalkorDB` for raw queries
  - Handle datetime compatibility (D7): convert `datetime()` calls to ISO-8601 strings
  - Audit all 14 raw Cypher queries against FalkorDB's Cypher documentation
  - Update `get_graph_provider()` factory in graph_provider.py to lazily import from falkordb_provider.py
  **Design decisions**: D1 (protocol), D7 (Cypher compat)
  **Dependencies**: 2.1, 1.4

- [ ] 2.3 Add FalkorDB Docker service
  Modify `docker-compose.yml`:
  - Add `falkordb` service using pinned `falkordb/falkordb:v4.4.1` image (or latest tested version)
  - Map port 6379 (verify no Redis conflict — confirmed none exists)
  - Add persistent volume `falkordb_data`
  - Add health check
  **Spec scenarios**: graph-provider.8 (Docker Compose service, Docker image pinning)
  **Design decisions**: D11 (image pinning)
  **Dependencies**: None

- [ ] 2.4 Create FalkorDB Lite test fixture with orphan cleanup
  New file `tests/helpers/falkordb_lite.py`:
  - `FalkorDBLiteFixture` class managing embedded subprocess
  - PID file for orphan detection, atexit handler, startup timeout (10s)
  - `reset()` using FLUSHALL via Redis protocol
  New file `tests/integration/fixtures/falkordb.py`:
  - `falkordb_lite` fixture (session-scoped), `falkordb_provider` fixture, `requires_falkordb` marker
  - Stale PID cleanup at startup
  **Spec scenarios**: graph-provider.8 (Lite test fixture, orphan cleanup)
  **Design decisions**: D4 (Lite for tests, orphan cleanup strategy)
  **Dependencies**: 2.2

- [ ] 2.5 Write provider-level integration tests on FalkorDB
  Test provider operations (driver construction, raw Cypher queries, health check, export/import)
  against FalkorDB Lite backend. Do NOT test GraphitiClient methods with live LLM — Graphiti's
  own test suite covers that. Our tests verify the provider layer works correctly.
  **Spec scenarios**: graph-provider.3 (Cypher compat), graph-provider.1 (raw queries)
  **Dependencies**: 2.2, 2.4

- [ ] 2.6 Write ReferenceGraphSync integration test on FalkorDB
  Test citation edge creation and episode lookup against FalkorDB Lite backend.
  Verify CITES edge writes and episode UUID lookups produce correct results.
  **Spec scenarios**: graph-provider.5 (citation creation on both backends, episode lookup on both)
  **Dependencies**: 2.2, 2.4, 1.7

- [ ] 2.7 Update profile YAML files for FalkorDB support
  Modify `profiles/base.yaml`, `profiles/local.yaml`, and add `profiles/local-falkordb.yaml`:
  - Add `providers.graphdb` section with interpolation
  - Add `settings.graphdb.*` section with FalkorDB defaults
  - Create a convenience profile for FalkorDB local dev
  **Spec scenarios**: graph-provider.7 (profile support)
  **Dependencies**: 1.6

## Phase 3: Export/Import Abstraction

- [ ] 3.1 Write tests for file-level export/import on provider
  **Spec scenarios**: graph-provider.6 (export to file, import from file, cross-backend portability, clean mode)
  **Design decisions**: D6 (file-level interface)
  **Dependencies**: 1.4

- [ ] 3.2 Rename data models in src/sync/models.py
  Rename `neo4j_manifest` → `graph_manifest`, `neo4j_node` → `graph_node`, `neo4j_relationship` → `graph_relationship`.
  Update `src/sync/pg_importer.py` type-skip logic to match new names.
  No backward compatibility needed (single test export).
  **Dependencies**: None

- [ ] 3.3 Implement export_graph/import_graph on Neo4jGraphDBProvider
  Refactor existing `src/sync/neo4j_exporter.py` and `src/sync/neo4j_importer.py` logic into
  `export_graph()` / `import_graph()` methods on Neo4jGraphDBProvider.
  Use `provider.execute_query()` internally instead of direct driver sessions.
  **Dependencies**: 3.1, 3.2, 1.4

- [ ] 3.4 Implement export_graph/import_graph on FalkorDBGraphDBProvider
  Add file-level export/import to `src/storage/falkordb_provider.py`.
  Same JSONL format, same record types — only session management differs.
  **Dependencies**: 3.1, 3.2, 2.2

- [ ] 3.5 Update sync CLI commands to use provider
  Modify `src/cli/sync_commands.py`:
  - Replace direct `GraphDatabase.driver()` with `get_graph_provider()`
  - Use `provider.export_graph()` / `provider.import_graph()` directly
  - Add `--graph-only` flag as primary, `--neo4j-only` as deprecated alias
  - Log deprecation warning when `--neo4j-only` used with non-Neo4j backend
  **Spec scenarios**: graph-provider.MODIFIED (sync CLI, legacy flag alias)
  **Dependencies**: 3.3, 3.4

- [ ] 3.6 Write cross-backend round-trip integration test
  Export from Neo4j provider, import to FalkorDB provider (and vice versa). Verify data integrity.
  **Spec scenarios**: graph-provider.6 (cross-backend portability)
  **Dependencies**: 3.3, 3.4

## Phase 4: CLI, Processors, Documentation, and Polish

- [ ] 4.1 Update graph CLI commands for provider transparency
  Modify `src/cli/graph_commands.py`:
  - Ensure `extract-entities` and `query` use `await GraphitiClient.create()` with default provider
  **Spec scenarios**: graph-provider.MODIFIED (CLI graph commands)
  **Dependencies**: 1.5

- [ ] 4.2 Update CLI adapters for async factory
  Modify `src/cli/adapters.py`:
  - Update `search_graph_sync()` and `extract_themes_from_graph_sync()` to use `await GraphitiClient.create()`
  - Wrap in `asyncio.run()` as existing pattern
  **Dependencies**: 1.5

- [ ] 4.3 Update theme_analyzer and historical_context with graceful degradation
  Modify `src/processors/theme_analyzer.py` and `src/processors/historical_context.py`:
  - Use `await GraphitiClient.create()` instead of `GraphitiClient()`
  - Catch `GraphBackendUnavailableError` and return empty results with warning log
  **Spec scenarios**: graph-provider.4 (graceful degradation)
  **Design decisions**: D9 (graceful degradation)
  **Dependencies**: 1.5

- [ ] 4.4 Update agent memory GraphStrategy
  Modify `src/agents/memory/strategies/graph.py`:
  - Ensure it works with the refactored GraphitiClient async factory API
  - Verify loose-typed client interface still holds with provider-backed client
  **Dependencies**: 1.5

- [ ] 4.5 Add Makefile targets for FalkorDB
  Add `falkordb-up`, `falkordb-down` targets. Update `dev-bg` to optionally start FalkorDB.
  **Dependencies**: 2.3

- [ ] 4.6 Update documentation
  Modify `docs/SETUP.md`, `docs/ARCHITECTURE.md`, `CLAUDE.md`:
  - Document `graphdb_provider` setting and FalkorDB configuration
  - Document backend switching procedure for existing deployments
  - Update architecture diagrams
  - Add FalkorDB to the providers table
  **Dependencies**: All previous phases

- [ ] 4.7 End-to-end validation
  Run `aca pipeline daily` with `GRAPHDB_PROVIDER=falkordb` against Docker FalkorDB. Verify:
  - Content ingestion populates knowledge graph
  - Theme analysis queries return results (or gracefully degrades)
  - Reference sync creates citation edges
  - Export/import round-trips successfully
  **Dependencies**: All previous phases
