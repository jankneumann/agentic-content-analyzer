# Proposal: Add FalkorDB Graph Provider

## Status: Proposed

## Change ID: add-falkordb-graph-provider

## Why

The project's knowledge graph layer is tightly coupled to Neo4j through three integration points: the GraphitiClient (via graphiti-core), raw Cypher in reference_graph_sync, and Neo4j-specific export/import tooling. Meanwhile, graphiti-core has evolved significantly — the latest version (0.28.x) introduces a pluggable `graph_driver` abstraction supporting Neo4j, FalkorDB, Kuzu, and Neptune backends. FalkorDB is now the default backend, offering 496x faster P99 latency and 6x better memory efficiency than Neo4j.

Our current graphiti-core pin (`>=0.5.0`) is far behind the current API. The `Graphiti()` constructor signature changed to accept a `graph_driver` parameter instead of raw Neo4j credentials. This upgrade is necessary regardless, and bundling FalkorDB support with it provides immediate value.

Additionally, FalkorDB Lite (embedded, subprocess-based, file-storage) provides a zero-infrastructure option for testing — mirroring our coordinator's embedded-process-for-testing / Docker-for-E2E pattern.

## What Changes

1. **Upgrade graphiti-core** from `>=0.5.0` to `>=0.28.0` with `[falkordb,anthropic,google-genai]` extras
2. **Introduce `graphdb_provider` abstraction** — a `GraphDBProvider` protocol with Neo4j and FalkorDB implementations covering:
   - Graphiti driver construction (leveraging graphiti-core's `FalkorDriver` / `Neo4jDriver`)
   - Raw graph queries (for reference_graph_sync)
   - Data export/import operations
3. **Add FalkorDB to infrastructure** — Docker container in docker-compose.yml, FalkorDB Lite for test fixtures
4. **Extend profile/settings system** — new `graphdb_provider: "neo4j" | "falkordb"` setting with sub-provider variants (local, auradb, lite)
5. **Migrate all raw Cypher code** in reference_graph_sync.py and neo4j_exporter/importer to use the provider abstraction
6. **Update CLI and configuration** — `aca` commands that touch the graph should work transparently with either backend

## Approaches Considered

### Approach 1: Graphiti Driver Delegation (Recommended)

Leverage graphiti-core's built-in driver abstraction (`FalkorDriver`, `Neo4jDriver`) as the primary switching mechanism. Build a thin `GraphDBProvider` protocol that wraps:
- Driver construction (delegated to graphiti-core)
- Raw query execution (thin Cypher-compatible layer for reference sync)
- Export/import operations (provider-specific implementations)

The `GraphitiClient` constructor changes from `Graphiti(uri, user, password)` to `Graphiti(graph_driver=driver)` where `driver` is constructed by the provider based on settings.

**Pros:**
- Minimal custom code — graphiti-core already solved the hard problem
- FalkorDB's Cypher compatibility means reference_graph_sync queries likely work as-is
- Clean upgrade path — if we later want Kuzu or Neptune, just add a new provider
- Aligned with upstream direction (FalkorDB is graphiti's default)

**Cons:**
- Tight coupling to graphiti-core's driver API (if they change it, we change)
- FalkorDB's Cypher subset may not cover 100% of our raw queries

**Effort:** M

### Approach 2: Full Custom Abstraction

Build our own `GraphDBProvider` interface from scratch that completely wraps both graphiti-core and raw graph operations. Each provider (Neo4j, FalkorDB) implements the full interface. GraphitiClient becomes a consumer of GraphDBProvider rather than directly using graphiti-core drivers.

**Pros:**
- Complete control over the abstraction boundary
- Can optimize per-backend (e.g., use FalkorDB-native APIs instead of Cypher compat)
- Insulated from graphiti-core API changes

**Cons:**
- Significantly more code to write and maintain
- Duplicates abstractions that graphiti-core already provides
- Higher risk of abstraction leaks when graphiti-core evolves

**Effort:** L

### Approach 3: Configuration-Only Switch

Keep the GraphitiClient largely as-is but switch between backends purely through configuration. The graphiti-core upgrade gives us `graph_driver` — we just construct the right driver based on a setting. Don't abstract reference_graph_sync or exporters; rely on FalkorDB's Cypher compatibility for raw queries.

**Pros:**
- Smallest change surface
- Fast to implement
- Low risk

**Cons:**
- Raw Cypher in reference_graph_sync may silently break on FalkorDB edge cases
- Export/import tooling stays Neo4j-only — can't round-trip data on FalkorDB
- No testing seam for graph backend switching
- Doesn't meet the "full abstraction" goal

**Effort:** S

### Selected Approach

**Approach 1: Graphiti Driver Delegation** — selected because it balances upstream alignment with full abstraction coverage. The user confirmed that all graph DB access (Graphiti, reference sync, and export/import) should be abstracted, and this approach achieves that with minimal custom code by delegating driver construction to graphiti-core while wrapping raw query execution in a thin protocol.

## Scope Boundaries

**In scope:**
- graphiti-core version upgrade to 0.28.x
- `graphdb_provider` setting and provider abstraction
- FalkorDB Docker service in docker-compose.yml
- FalkorDB Lite integration for test fixtures
- Migration of reference_graph_sync.py to provider abstraction
- Migration of neo4j_exporter.py / neo4j_importer.py to provider abstraction
- Profile updates (local, staging, production) with FalkorDB variants
- CLI commands that interact with the graph

**Out of scope:**
- Kuzu or Neptune backend support (future follow-up)
- Data migration tooling from Neo4j to FalkorDB (manual process, documented)
- Changes to the Graphiti MCP server configuration
- Knowledge graph schema changes

## Success Criteria

- `GRAPHDB_PROVIDER=falkordb` with Docker FalkorDB passes all existing graph-related tests
- `GRAPHDB_PROVIDER=neo4j` continues to work identically (no regression)
- FalkorDB Lite works in test fixtures without Docker
- Reference sync (CITES edges) works on both backends
- Export/import round-trips data on both backends
- Profile system supports `graphdb_provider: falkordb` with sub-variants (local, lite)
