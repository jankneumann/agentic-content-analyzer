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

## 2026-08-03 — P6 end-to-end reliability, documentation, and gates

### Objective

Finish RI-10 by committing the completed P5 vertical, running the durable tier
against a real PostgreSQL instance for the first time, and closing what that
execution surfaced.

### Context

P5 was complete but uncommitted when the previous session ended: `tasks.md` had
5.1–5.7 ticked and the P5 session-log entry was written, but ~60 files were
still in the worktree. That session recorded that "PostgreSQL-backed source
matrix/real-adapter execution ... were unavailable in this sandbox". This
session had PostgreSQL, so every `real_ingest` and `integration` assertion
written blind was executed for the first time.

### Defects found by first durable execution

1. **The real-ingestion harness could not claim any job.** RI-08 added
   `claim_generation` / `claim_protocol_version` to the worker's job contract
   (`worker._claim_jobs` sets the protocol version; a database trigger bumps the
   generation on queued -> in_progress). `harness._claim` still returned only
   `id, entrypoint, payload`, so `worker._process_job` raised
   `KeyError: 'claim_generation'` for **every** source, not just Obsidian. The
   harness now mirrors the poller exactly.

2. **A permanently invalid note failed every future scan.** Once a note's retry
   budget was spent and the file had not changed, `_process_note` still returned
   `status="failed"` with a fresh diagnostic. With `items_ingested == 0` the
   canonical `IngestionResponse` invariant forces `status="error"`, so the
   steady state of a polled vault holding one bad note was a failed durable
   operation and a repeated RI-09 alert, forever. Exhausted-budget observations
   are now `skipped` with a `retained=True` diagnostic projected as a warning.
   Measured convergence over six scans: ingest, two real bounded retries, then
   `completed`/`zero_items` with a `retry_exhausted` warning and no attempts.

3. **Obsidian alerts carried no diagnostic code.** `WorkflowAlertDiagnosticCode`
   is a closed allowlist and contained no Obsidian code, so every externally
   routed Obsidian alert shipped `codes: []` with `codes_omitted: N`. All parser,
   scanner, and adapter codes are fixed literals derived from no note content,
   so they are now allowlisted.

### Corrections to assertions written without execution

- `content_ids` in a durable result carries canonicalized **identities**, while
  `items_ingested` counts **rows**. Two notes clipping one page are two rows
  under one primary, exactly as the spec requires ("SHALL NOT create duplicate
  primary identity"). The PR-tier delta helper and the failure classifier now
  compare claims against a primary-identity delta; for every other source the
  two numbers are identical.
- A changed note is a new immutable file version, so its claimed identity is
  disjoint from the row it commits. Asserted explicitly rather than as equality.
- Unchanged re-scans do consume one bounded retry attempt for the invalid note;
  the attempt deltas are 1, not 0.

### Decisions

1. Retained failures stay visible as warnings rather than being silenced, so
   "typed failure is retained" holds without permanent re-alerting.
2. `retry_exhausted` is kept as the retained code even though it replaces the
   original cause on the event row; the original code is carried by the earlier
   operation's result, and the event row remains queryable.
3. P6 scope was widened (task 6.6) rather than deferring the defects, since
   shipping the source with either one defeats the acceptance outcomes P6 exists
   to verify.

### Evidence

- Whole `real_ingest` tier green against PostgreSQL: 58 passed, 15 skipped.
- Obsidian integration/migration/repository/architecture suites: 31 passed.
- Alert redaction, terminal-event, and telemetry suites: 88 passed.
- P5 pre-commit gates: 497 focused tests, 51 registry/policy/contract/fixture
  tests, 55 web unit tests, workflow-contract drift, strict OpenSpec, scoped
  ruff and mypy.
- The stale pre-registry `sources.d/obsidian-ingest.yaml.example` (poller,
  `move_processed_to`, `type: obsidian_ingest`) was removed; it described the
  design this change explicitly rejected.
