# Session Log — add-obsidian-vault-ingest

## 2026-08-02 — Plan iteration 2

### Objective

Refresh the pre-registry Obsidian proposal so RI-10 can be implemented through the
canonical source, durable operation, persistence, recovery, telemetry, and fixture
contracts established by RI-05, RI-06, and RI-09.

### Evidence consulted

- Current proposal, design, spec, tasks, and roadmap acceptance outcomes.
- `docs/ARCHITECTURE.md`, source configuration/registry, generated workflow command
  path, MCP source map/toolset, capability projection, fixture completeness, live
  adapter policy, worker dispatch, and Obsidian exporter ownership.
- Independent architecture, security, and task/DAG reviews.

### Decisions

1. Replace the long-lived local poller with one bounded durable scan command.
2. Support only worker-local approved mounts in v1 and fail readiness closed when
   mount routing cannot be guaranteed.
3. Keep vault and note paths private; use a stable `vault_id` and existing HMAC public
   configured-source identity.
4. Treat clipped Markdown as authoritative and never refetch `source_url`.
5. Require valid HTTP(S) `source_url` and timezone-aware `captured_at`.
6. Reject all symlinks and use descriptor-relative no-follow reads with identity
   revalidation.
7. Use source/path digests, immutable file-version identity, leases, uniqueness, and
   reconciliation for idempotency.
8. Preserve every distinct note as `ContentSource.OBSIDIAN` while linking shared
   canonical URL identity.
9. Keep v1 read-only and defer watchers, attachments, file moves, and remote bridges.
10. Land registry/generated/interface/fixture changes as one collection-green package.

### Alternatives rejected

- A process-local watcher/poller: unbounded and outside the durable operation model.
- Passing absolute or relative paths in commands: not portable and leaks private data.
- Mapping to `url` ingestion: would refetch and discard captured annotations.
- Mapping to file uploads: requires durable upload IDs and loses URL semantics.
- Frontmatter status or processed-folder moves: violates read-only least privilege.
- Missing timestamp or invalid URL fallback: makes provenance nondeterministic.

### Result

Proposal, design, three delta specs, task packages, traceability, and review findings
were rewritten. Strict OpenSpec and whitespace validation pass. Implementation may
begin with P1/P2/P3 foundations after this plan commit is pushed.

## 2026-08-02 — P5 canonical source vertical

### Objective

Land the Obsidian configured source as one canonical, privacy-preserving vertical
across generated contracts, registry/worker dispatch, HTTP, MCP, CLI, source
management, capability discovery, frontend rendering, and real-ingestion fixtures.

### Decisions

1. Public commands select one vault by a 20-hex opaque HMAC key; paths, folders, and
   raw configured-source snapshots never enter durable operation payloads.
2. A domain-separated full-config HMAC version detects stale queued configuration;
   workers reload the deployment-configured source location and compare versions.
3. Readiness is fail-closed and path-free, using deployment-owned allowed roots and
   a compatible-worker flag.
4. Obsidian server scan/parser policy is not projected through configured-source
   discovery; the UI receives only the opaque key, readiness, and generated public
   command fields.
5. Public source mutations require opaque Obsidian keys while database storage keeps
   the private natural identity for stable merge/upsert behavior.
6. Canonical content queries and frontend badge/filter mappings include persisted
   `obsidian` content.
7. Fixture evidence snapshots Content rows independently of result claims and records
   state/event status and attempt deltas.

### Independent review corrections

- Unified custom `SOURCES_CONFIG_DIR`/`SOURCES_CONFIG_FILE` loading across HTTP, MCP,
  direct CLI, and worker execution.
- Removed private Obsidian limits from discovery and hid invalid path input from
  validation/log/protocol errors.
- Added exhaustive frontend content-source rendering and canonical query enum parity.
- Rejected natural Obsidian identities at management boundaries and stopped echoing
  caller-provided deletion keys.
- Replaced self-referential durable-result counting with independent database
  snapshots and transition counters.

### Evidence

- 555 focused Python tests passed; 17 registry/live-policy tests, 5 pure source-matrix
  contract cases, and the path-free source API projection passed separately.
- 55 web unit tests, production build, scoped ESLint, contract generation/drift,
  scoped mypy/Ruff, strict OpenSpec, package DAG validation, and whitespace checks
  passed.
- The corrected verification matrix collected 1,502 selected tests.
- Repository-wide web lint remains red on 66 pre-existing unrelated findings.
- PostgreSQL-backed source matrix/real-adapter execution and Playwright browser launch
  were unavailable in this sandbox; P6 retains the environment-capable durable-delta
  and end-to-end verification gate.
