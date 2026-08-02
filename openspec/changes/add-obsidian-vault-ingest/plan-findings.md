# Plan Findings — add-obsidian-vault-ingest

## Iteration 1

| # | Type | Criticality | Description | Proposed Fix | Status |
|---|------|-------------|-------------|--------------|--------|
| 1 | testability | high | Several requirements only had success-path scenarios, making failure acceptance criteria incomplete. | Add explicit failure/edge scenarios for frontmatter validation, canonicalization fallback, and replay failures. | Fixed |
| 2 | parallelizability | medium | Tasks did not declare dependency ordering, making parallel implementation scheduling ambiguous. | Add dependency annotations and a parallelization summary (independent chains + width). | Fixed |
| 3 | consistency | medium | Configuration template rollout path (`.yaml.example` → `.yaml`) was described in design/tasks but not represented as requirement behavior. | Add source-config compatibility requirement with unsupported-type guard scenario. | Fixed |
| 4 | completeness | medium | No explicit requirement for path safety/allowed roots and path traversal prevention. | Add security/path validation requirement and failure scenario. | Fixed |

## Residual Low-Criticality Findings

- Wording polish in a few tasks can be done during implementation.

## Iteration 2

Three independent reviews evaluated architecture, security, and task schedulability
against the post-RI-09 source and operation contracts. The implementation is blocked on
this revised plan; all medium-or-higher findings were resolved in proposal, design,
delta specs, and tasks before coding.

| # | Type | Criticality | Description | Resolution | Status |
|---|---|---|---|---|---|
| 1 | architecture | critical | A laptop/iCloud path cannot be executed by an arbitrary Railway worker. | Constrain v1 to an approved worker-local mount and compatible worker routing; fail readiness closed and defer a companion bridge. | Fixed |
| 2 | contract | critical | A local poller/watcher cannot produce a bounded durable operation and duplicates scheduler/run state. | Use one bounded `ingestion.execute` scan; existing scheduling may submit it, while watchers and per-note child operations are deferred. | Fixed |
| 3 | source parity | critical | The plan omitted OpenAPI/generated contracts, registry, CLI/HTTP/MCP/worker/UI, fixtures, live policy, and atomic collection-time completeness. | Add an atomic P5 source vertical owning all shared hot files and exact interface/fixture gates. | Fixed |
| 4 | payload identity | critical | Existing URL and file commands cannot preserve authoritative clipped Markdown without refetching or exposing a path. | Add an `obsidian_vault` command with opaque source key; scan resolves private config server-side and stores note bytes as authoritative `ContentSource.OBSIDIAN` content. | Fixed |
| 5 | privacy | high | Path-based natural keys and source overrides could leak through management, operation, log, and error projections. | Require stable `vault_id`, existing HMAC public keys, private server-side paths, safe allowlists, redaction tests, and deployment-owned allowed roots. | Fixed |
| 6 | filesystem security | high | Resolve-then-open checks were vulnerable to nested symlinks and TOCTOU replacement. | Require descriptor-relative no-follow access, rejection of every symlink component, post-open identity checks, deterministic race tests, and no embed reads. | Fixed |
| 7 | concurrency | high | A global path key and check-then-insert flow could duplicate content under overlapping scans/crashes. | Key state by source/path digests; add immutable file-version identity, transactional leased claims, database uniqueness, and crash reconciliation. | Fixed |
| 8 | contract consistency | high | `ingest_status`, move behavior, URL fallback, and missing timestamp fallback contradicted read-only/required-field claims. | Keep state in the database, remove moves/writeback, require valid HTTP(S) URL and timezone-aware timestamp, and reject instead of falling back. | Fixed |
| 9 | resource safety | high | Files, YAML, scans, recursion, and concurrency were unbounded. | Define hard bounds and injectable time/filesystem dependencies with explicit limit scenarios and tests. | Fixed |
| 10 | content behavior | medium | Embed handling, duplicate context, rename/deletion semantics, and renderer safety were vague. | Never dereference embeds; preserve each note and link canonical identity; treat rename as a new event, never delete content on absence, and test inert rendering. | Fixed |
| 11 | observability | medium | Proposed logs exposed note paths/full URLs and duplicated source-specific metrics. | Use operation-native outcomes plus RI-09 telemetry with opaque IDs, origins/hosts where permitted, stable codes, and redaction tests; remove custom metrics. | Fixed |
| 12 | task quality | high | Tests were deferred to the end and parallel packages would contend on collection-sensitive registries. | Put failing tests in every task, parallelize only pure P1/P2/P3 packages, join in P4, and reserve all hot shared files for atomic P5. | Fixed |

## Closed Decisions

- Trigger: one bounded durable scan submitted manually or by existing scheduling.
- Deployment: worker-local/co-located mount only in v1; no device bridge.
- Content: `ContentSource.OBSIDIAN`, clipped Markdown authoritative, URL never refetched.
- Configuration: stable `vault_id`; private path may be stored server-side but is never
  publicly projected; deployment-owned allowed roots fail closed.
- Metadata: strict HTTP(S) URL and timezone-aware `captured_at`; no filesystem fallback.
- Filesystem: reject all symlinks; read-only; no watcher, attachments, or moves.
- Identity: rename is a new note event; canonical URL links distinct annotation-bearing
  note rows; unchanged file versions remain idempotent.

## Validation Evidence

- `openspec validate add-obsidian-vault-ingest --strict` — passed.
- `git diff --check` — passed after removing Markdown trailing whitespace.
- Every added/modified requirement is mapped in `tasks.md` traceability.
- Dependency graph has one explicit synchronization point and no competing hot-file
  ownership.

## Residual Low-Criticality Findings After Iteration 2

- Exact default numerical bounds should reuse existing project constants where stricter
  and will be frozen by the first failing implementation tests.
- Distributed worker-pool affinity remains deliberately unsupported unless the runtime
  can prove compatible mount routing; the source must stay unavailable otherwise.
