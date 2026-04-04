# Design: Add FalkorDB Graph Provider

## Selected Approach

**Approach 1: Graphiti Driver Delegation** — leverage graphiti-core's built-in `GraphDriver` abstraction (`Neo4jDriver`, `FalkorDriver`) as the primary switching mechanism. Build a thin `GraphDBProvider` protocol that wraps driver construction, raw query execution, and export/import operations.

## Architecture Overview

```
Settings (graphdb_provider)
    │
    ▼
GraphDBProviderFactory
    ├── Neo4jGraphDBProvider
    │     ├── Neo4jDriver (from graphiti_core)
    │     └── neo4j.GraphDatabase.driver (for raw Cypher)
    └── FalkorDBGraphDBProvider
          ├── FalkorDriver (from graphiti_core)
          └── falkordb.FalkorDB client (for raw queries)
```

## Key Design Decisions

### D1: GraphDBProvider Protocol — Thin Wrapper Over graphiti-core Drivers

The `GraphDBProvider` protocol defines four responsibilities:

```python
class GraphDBProvider(Protocol):
    # 1. Construct a graphiti-core GraphDriver for the Graphiti() constructor
    def create_graphiti_driver(self) -> GraphDriver: ...

    # 2. Execute raw graph queries (for reference_graph_sync, export/import)
    async def execute_query(self, query: str, params: dict) -> list[dict]: ...
    async def execute_write(self, query: str, params: dict) -> dict: ...

    # 3. Lifecycle (both sync and async close for caller compatibility)
    def close(self) -> None: ...           # Sync facade for CLI/non-async callers
    async def aclose(self) -> None: ...    # Async close for async callers
    async def health_check(self) -> bool: ...

    # 4. Export/Import — file-level operations matching CLI sync workflow
    def export_graph(self, output_path: Path) -> ExportManifest: ...
    def import_graph(self, input_path: Path, mode: str = "merge") -> ImportStats: ...
```

**Why:** We need raw query execution because `reference_graph_sync.py` and the exporters use Cypher directly, not Graphiti's API. Both Neo4j and FalkorDB speak openCypher, so the same queries work on both — but the driver/session management differs. The export/import interface is file-level (not record-level) to match the existing CLI sync workflow.

**How to apply:** `GraphitiClient.create()` calls `provider.create_graphiti_driver()` and passes it to `Graphiti(graph_driver=...)`. Raw-query callers use `provider.execute_query()`. CLI sync commands use `provider.export_graph()` / `provider.import_graph()`.

### D2: Settings Structure — graphdb_provider with Sub-Variants

```python
GraphDBProviderType = Literal["neo4j", "falkordb"]

# Settings fields
graphdb_provider: GraphDBProviderType = "neo4j"  # Top-level backend selection

# Neo4j sub-variants (existing, unchanged)
neo4j_provider: Neo4jSubProviderType = "local"  # "local" | "auradb"

# FalkorDB sub-variants (new)
falkordb_provider: FalkorDBSubProviderType = "local"  # "local" | "lite"
falkordb_host: str = "localhost"
falkordb_port: int = 6379
falkordb_username: str | None = None
falkordb_password: str | None = None
falkordb_database: str = "newsletter_graph"

# FalkorDB Lite specific
falkordb_lite_data_dir: str | None = None  # File-based storage path
```

**Why:** Two-level provider selection mirrors the existing `neo4j_provider: "local" | "auradb"` pattern. The top-level `graphdb_provider` selects the backend (Neo4j vs FalkorDB), then sub-provider selects deployment mode.

**Profile flattening precedence** (addresses review finding on two-level mapping):
1. `providers.graphdb` → `graphdb_provider` (new top-level, applied FIRST)
2. `providers.neo4j` → `neo4j_provider` (existing, applied AFTER — still works as sub-provider)
3. `settings.graphdb.*` → `falkordb_*` fields (new section)
4. `settings.neo4j.*` → existing `neo4j_*` fields (unchanged)

When `graphdb_provider=falkordb`, the `neo4j_*` settings are ignored at runtime (factory only reads falkordb_* fields). When `graphdb_provider=neo4j` (default), the `falkordb_*` settings are ignored. No cross-contamination — the factory branches on `graphdb_provider` before reading any sub-provider fields.

**Validation rule:** If `graphdb_provider=falkordb` and `falkordb_provider=local`, require `falkordb_host` to be non-empty. Mirror the existing `validate_neo4j_provider_config()` pattern.

**How to apply:** Add `providers.graphdb` mapping to `_flatten_profile_to_settings()` in `settings.py` (line ~95). Add `settings.graphdb` section handling alongside existing `settings.neo4j` (line ~80). Factory uses `graphdb_provider` to construct the right `GraphDBProvider` implementation.

### D3: Backward Compatibility — neo4j_provider Preserved as Sub-Provider

The existing `neo4j_provider` setting continues to work. If `graphdb_provider` is not set (defaults to `"neo4j"`), behavior is identical to today. The `get_effective_neo4j_*()` methods remain but are now called internally by `Neo4jGraphDBProvider`.

**Why:** Zero-disruption upgrade path. Existing profiles, .env files, and documentation continue to work.

**How to apply:** `neo4j_provider` becomes a sub-provider under `graphdb_provider: "neo4j"`. Migration is purely additive — no renaming, no removal.

### D4: FalkorDB Lite for Test Fixtures

FalkorDB Lite runs as an embedded subprocess with file-based storage — no Docker required. Test fixtures create an ephemeral FalkorDB Lite instance per test session.

```python
# tests/helpers/falkordb_lite.py
class FalkorDBLiteFixture:
    """Manage embedded FalkorDB for testing."""
    def start(self, data_dir: Path, timeout: float = 10.0) -> tuple[str, int]:
        # Returns (host, port). Writes PID to data_dir/falkordb.pid.
        # Registers atexit handler for orphan cleanup.
    def stop(self) -> None:
        # Kills subprocess, removes PID file.
    def reset(self) -> None:
        # FLUSHALL via Redis protocol — fast, we own the instance.
    def __del__(self) -> None:
        # Safety net — calls stop() if not already stopped.
```

**Why:** Mirrors the coordinator's embedded-process-for-testing / Docker-for-E2E pattern that the user validated. Unit and integration tests get a fast, isolated graph backend. E2E tests use Docker FalkorDB for production fidelity.

**Orphan cleanup strategy** (addresses review finding on subprocess resilience):
- PID file written to `data_dir/falkordb.pid` on start
- `atexit.register(self.stop)` for normal exit cleanup
- Startup timeout (default 10s) with clear error on failure
- Session-scoped fixture checks for stale PID file at startup and kills orphans

**How to apply:** Session-scoped pytest fixture starts FalkorDB Lite, function-scoped fixture calls `reset()` (FLUSHALL). Test profiles set `graphdb_provider: falkordb`, `falkordb_provider: lite`.

### D5: GraphitiClient Refactoring — Async Factory Method

```python
# Before (current)
class GraphitiClient:
    def __init__(self, neo4j_uri="", neo4j_user="", neo4j_password="", ...):
        self.driver = GraphDatabase.driver(uri, auth=(...))
        self.graphiti = Graphiti(uri, user, password, ...)

# After (new) — async factory pattern
class GraphitiClient:
    def __init__(self, provider: GraphDBProvider, graphiti: Graphiti):
        """Private-ish constructor. Use GraphitiClient.create() instead."""
        self.provider = provider
        self.graphiti = graphiti

    @classmethod
    async def create(cls, provider: GraphDBProvider | None = None, ...) -> "GraphitiClient":
        """Async factory — constructs Graphiti and runs build_indices_and_constraints()."""
        provider = provider or get_graph_provider()
        graph_driver = provider.create_graphiti_driver()
        graphiti = Graphiti(graph_driver=graph_driver, llm_client=..., embedder=..., ...)
        await graphiti.build_indices_and_constraints()  # One-time DDL, idempotent
        return cls(provider, graphiti)

    def close(self) -> None:
        """Sync close for CLI callers."""
        self.provider.close()
```

**Why:** `build_indices_and_constraints()` is async (required by graphiti-core 0.28) and cannot be called from `__init__`. The async factory pattern (`create()`) handles this cleanly. DDL is idempotent (CREATE IF NOT EXISTS), so calling it per-construction is safe but adds ~50ms latency. For hot paths, callers should cache the client instance.

**How to apply:** All existing callers already go through CLI adapters that use `asyncio.run()`, so switching to `await GraphitiClient.create()` is straightforward. The sync CLI adapters in `src/cli/adapters.py` wrap the async factory. Processors and services that construct GraphitiClient directly need to `await` the factory.

**Sync close facade** (addresses review finding): `close()` remains sync for backward compatibility with existing callers. Internally calls `provider.close()` (sync). For async callers, `aclose()` is available on the provider.

### D6: Export/Import Abstraction — File-Level Interface

The export/import abstraction is file-level, matching the existing CLI sync workflow. Each provider implementation handles its own record-level iteration internally.

```python
# On GraphDBProvider:
def export_graph(self, output_path: Path) -> ExportManifest:
    """Export all graph data to JSONL file at output_path."""
    ...

def import_graph(self, input_path: Path, mode: str = "merge") -> ImportStats:
    """Import graph data from JSONL file. Mode: 'merge' or 'clean'."""
    ...
```

Data models renamed from `Neo4j*` prefixes to backend-agnostic names:
- `Neo4jNodeRecord` → `NodeRecord`
- `Neo4jRelationshipRecord` → `RelationshipRecord`
- `Neo4jManifest` → `ExportManifest`

JSONL record `_type` discriminator values also change: `neo4j_node` → `graph_node`, `neo4j_relationship` → `graph_relationship`, `neo4j_manifest` → `graph_manifest`. Update `src/sync/models.py` and `src/sync/pg_importer.py` type-skip logic accordingly. No backward compatibility needed — only a single test export exists.

**Why:** The existing `Neo4jExporter`/`Neo4jImporter` are file-oriented (`export(path)`, `import_file(path)`). Keeping the same interface level avoids introducing an unnecessary record-level async protocol that the CLI would just have to wrap again.

**How to apply:** Refactor existing exporter/importer classes to implement the file-level methods on the provider. FalkorDB implementation uses the same openCypher queries with FalkorDB's session management. CLI sync commands call `provider.export_graph()` / `provider.import_graph()` directly.

### D7: Raw Cypher Compatibility Assessment

All 14 raw Cypher queries in the codebase use basic openCypher patterns:
- `MATCH (n:Label) WHERE ... RETURN ...`
- `MERGE (n:Label {uuid: $uuid}) ON CREATE SET ... ON MATCH SET ...`
- `MATCH (a)-[r:TYPE]->(b) ...`
- `DELETE`, `SET`, `ORDER BY`, `LIMIT`
- Functions: `count()`, `toLower()`, `CONTAINS`, `datetime()`

FalkorDB supports the openCypher subset. The only potential issue is `datetime()` — FalkorDB may not support Neo4j's built-in `datetime()` function. Mitigation: pass ISO-8601 strings and store as string properties rather than native datetime types.

**How to apply:** Audit each query during implementation. Queries that use Neo4j-specific functions get a compatibility shim in the FalkorDB provider.

### D8: graphiti-core Upgrade Strategy

The version jump from `>=0.5.0` to `>=0.28.0` involves these breaking changes:

1. **Constructor signature**: `Graphiti(uri, user, password)` → `Graphiti(graph_driver=driver)`
2. **Driver operations redesign**: Low-level queries moved to `driver.search_ops`, `driver.entity_node_ops`, etc.
3. **NodeNamespace/EdgeNamespace**: New pattern for accessing graph data
4. **`build_indices_and_constraints()`**: Must be called after initialization
5. **Pip extras**: `[anthropic,google-genai]` → `[neo4j,falkordb,anthropic,google-genai]`

**How to apply:** Phase 1 of tasks handles the upgrade with Neo4j-only to validate no regressions, Phase 2 adds FalkorDB.

### D9: Graceful Degradation When Graph Backend Unavailable

Graph enrichment operations (theme analysis, historical context, reference sync) SHALL degrade gracefully when the graph backend is unavailable. Core pipeline operations (ingest, summarize, digest) SHALL continue without graph enrichment.

```python
# Pattern for graph-optional operations:
try:
    client = await GraphitiClient.create()
    result = await client.some_operation(...)
except GraphBackendUnavailableError:
    logger.warning("Graph backend unavailable, skipping graph enrichment")
    result = empty_default
```

**Why:** The ingestion pipeline should not fail because Neo4j/FalkorDB is down. Reference sync is already fire-and-forget. Theme analysis and historical context should follow the same pattern.

**How to apply:** `GraphitiClient.create()` raises `GraphBackendUnavailableError` if `provider.health_check()` fails. Callers in processors and CLI catch this and proceed without graph data.

### D10: Observability — Provider Lifecycle Logging

The provider abstraction SHALL log backend lifecycle events:
- **Startup** (INFO): backend type, connection target, sub-provider variant
- **Health check failure** (WARN): backend, error details
- **Slow query** (WARN): query text (truncated), elapsed time >5s
- **Close** (DEBUG): backend disconnection

**Why:** Critical for debugging backend-specific issues in production and for operators to verify which backend is active after configuration changes.

**How to apply:** Logging is built into the `GraphDBProvider` implementations, not the protocol. Each implementation logs via `get_logger(__name__)`.

### D11: FalkorDB Docker Image Pinning

Pin FalkorDB to a tested version (e.g., `falkordb/falkordb:v4.4.1`) rather than `latest`. This follows the existing convention — all Docker services pin versions (postgres:17, spectolabs/hoverfly:v1.10.5).

**Why:** Reproducible builds. `latest` can break CI without code changes.

**How to apply:** Test against a specific version during implementation. Pin in docker-compose.yml.

## Component Diagram

```
┌─────────────────────────────────────────────────┐
│                   Settings                       │
│  graphdb_provider: "neo4j" | "falkordb"         │
│  neo4j_provider: "local" | "auradb"             │
│  falkordb_provider: "local" | "lite"            │
└──────────────────────┬──────────────────────────┘
                       │
              ┌────────▼────────┐
              │ GraphDBProvider  │ (Protocol)
              │   Factory       │
              └───┬─────────┬───┘
                  │         │
     ┌────────────▼──┐  ┌──▼─────────────┐
     │Neo4jGraphDB   │  │FalkorDBGraphDB │
     │Provider       │  │Provider        │
     │               │  │                │
     │ Neo4jDriver   │  │ FalkorDriver   │
     │ (graphiti)    │  │ (graphiti)     │
     │               │  │                │
     │ neo4j.Driver  │  │ falkordb.      │
     │ (raw queries) │  │ FalkorDB       │
     └───────┬───────┘  └───────┬────────┘
             │                  │
     ┌───────▼──────────────────▼────────┐
     │         GraphitiClient            │
     │   (provider.create_graphiti_      │
     │    driver() → Graphiti())         │
     ├───────────────────────────────────┤
     │  ReferenceGraphSync               │
     │   (provider.execute_query())      │
     ├───────────────────────────────────┤
     │  GraphExporter / GraphImporter    │
     │   (provider.create_exporter())    │
     └──────────────────────────────────┘
```

## File Changes Summary

| File | Change |
|------|--------|
| `src/storage/graph_provider.py` | **NEW** — GraphDBProvider protocol, Neo4j implementation, factory |
| `src/storage/falkordb_provider.py` | **NEW** — FalkorDB implementation of GraphDBProvider |
| `src/storage/graphiti_client.py` | **MODIFY** — Async factory, use provider instead of direct Neo4j driver |
| `src/services/reference_graph_sync.py` | **MODIFY** — Use provider.execute_query() instead of driver.session() |
| `src/services/connection_checker.py` | **MODIFY** — Use provider health_check() for graph backend status |
| `src/sync/neo4j_exporter.py` | **MODIFY** → Refactor to implement file-level export via provider |
| `src/sync/neo4j_importer.py` | **MODIFY** → Refactor to implement file-level import via provider |
| `src/sync/models.py` | **MODIFY** — Rename `neo4j_*` record types to `graph_*` |
| `src/sync/pg_importer.py` | **MODIFY** — Update type-skip logic for renamed record types |
| `src/config/settings.py` | **MODIFY** — Add graphdb_provider, falkordb_* fields, flattening, validation |
| `src/config/profiles.py` | **MODIFY** — Add GraphDBProviderType, FalkorDBSubProviderType |
| `src/cli/sync_commands.py` | **MODIFY** — Use provider instead of direct Neo4j driver, add `--graph-only` alias |
| `src/cli/manage_commands.py` | **MODIFY** — Use provider for graph backend health/status |
| `docker-compose.yml` | **MODIFY** — Add FalkorDB service (pinned version) |
| `pyproject.toml` | **MODIFY** — Upgrade graphiti-core, add falkordb extra |
| `tests/helpers/falkordb_lite.py` | **NEW** — FalkorDB Lite test fixture with orphan cleanup |
| `profiles/*.yaml` | **MODIFY** — Add graphdb_provider settings |
