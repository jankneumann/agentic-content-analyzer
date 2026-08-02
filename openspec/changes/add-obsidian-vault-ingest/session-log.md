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
