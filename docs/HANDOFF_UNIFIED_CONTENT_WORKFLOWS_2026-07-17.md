# Unified Content Workflows Handoff

Last updated: 2026-07-17 09:32 EDT

## Objective

Finish the post-merge closure work for the unified content workflow architecture. The
original effort unified ingestion, provenance, summarization, digest generation, podcast
generation, durable operations, and the CLI, HTTP, MCP, worker, and frontend surfaces.

The coordinated breaking migration was accepted. All surfaces should use the shared job
queue. Merge commits should preserve individual commit history; use rebase merges.

## Repository State

- Repository: `jankneumann/agentic-content-analyzer`
- Original implementation: PR [#445](https://github.com/jankneumann/agentic-content-analyzer/pull/445), merged
- Current follow-up: PR [#449](https://github.com/jankneumann/agentic-content-analyzer/pull/449)
- Current branch: `openspec/durable-workflow-contracts--ci-fix`
- Current worktree: `.git-worktrees/durable-workflow-contracts/ci-fix`
- Durable-contract commit before this handoff: `59e26573`
- Primary tracking issue: [#448](https://github.com/jankneumann/agentic-content-analyzer/issues/448)
- Rollout issue: [#446](https://github.com/jankneumann/agentic-content-analyzer/issues/446)
- Security follow-up: [#447](https://github.com/jankneumann/agentic-content-analyzer/issues/447)

The root checkout is an unrelated dirty checkout on `temp-merge-431`. It contains untracked
`.pnpm-store/` and `openspec/changes/add-gemini-batch-processing/`. Do not modify, clean,
stage, or revert those paths. Continue from the worktree above.

There is no Beads database in the worktree. `bd sync` reports `no beads database found`;
GitHub issues are the current durable task record. No child agent is still running.

## Completed Work

PR #449 establishes `openspec/contracts/content-workflows/` as the durable executable
contract registry, parallel to `openspec/specs/` and outside the OpenSpec change/archive
lifecycle.

The registry contains:

- `openapi/v1.yaml`
- `events/operation.progress.schema.json`
- `db/schema.sql` and `db/seed.sql`
- generated Python and TypeScript models
- registry and lifecycle documentation

The generator and live tests now use the durable registry. Archived contract files remain
an immutable historical snapshot. Live application code, generators, and tests must not
depend on `openspec/changes/` or `openspec/changes/archive/`.

Relevant files:

- `openspec/contracts/README.md`
- `openspec/contracts/content-workflows/README.md`
- `scripts/generate_workflow_contracts.py`
- `tests/contract/test_canonical_workflow_contracts.py`
- `tests/queue/test_operation_service.py`
- `tests/services/test_capability_service.py`
- `docs/ARCHITECTURE.md`

## Validation Evidence

Local validation passed:

- `make workflow-contracts-check`
- Focused contract, operation projection, and capability tests: 16 passed
- Services-stack CI shard: 1605 passed, 3 skipped, 4 deselected
- Rest CI shard: 2131 tests selected, exit 0
- Ruff check and format check
- Git diff checks
- Pre-commit hooks, including MyPy and secret scanning

PR #449 GitHub CI is green for:

- cold-start migration and boot
- dependency audits
- lint and type checking
- secret scanning
- API, CLI, rest, and services-stack test shards
- profile validation

The two shards previously broken by archived contract paths, `rest` and `services-stack`,
both pass in GitHub CI.

## Current Merge Blocker

The `contract-test` job in Actions run
[29581840339](https://github.com/jankneumann/agentic-content-analyzer/actions/runs/29581840339)
is still in progress after every other job completed. Job ID: `87889156321`.

The known cause is ordinary Schemathesis request/response fuzzing entering the infinite SSE
endpoint `/api/v1/notifications/stream`. `tests/contract/conftest.py` documents SSE
exclusions but does not include that route. The CI job also has no explicit timeout, so the
GitHub default permits a six-hour hang.

The previous partial contract log also reported failures for:

- `GET /api/v1/chat/conversations`
- `GET /api/v1/settings/overrides`
- `GET /api/v1/pricing/neon/compare`
- `GET /api/v1/sources`
- `GET /api/v1/search`

Do not merge PR #449 until the contract job completes successfully. There are currently no
review comments, requested changes, or merge conflicts.

## Recommended Contract Fix

Keep this fix on PR #449 because it directly unblocks validation of the durable contracts:

1. Cancel the currently hanging Actions run.
2. Add `/api/v1/notifications/stream` to `EXCLUDED_COMMON_PATHS`.
3. Add a regression guard that discovers every OpenAPI response advertising
   `text/event-stream` and asserts that the route matches a common exclusion.
4. Add a bounded `timeout-minutes` value to the `contract-test` job in
   `.github/workflows/ci.yml`; 20 to 30 minutes is sufficient.
5. Run the complete contract suite and resolve or explicitly classify the five failures
   listed above. Do not merely exclude ordinary JSON endpoints to make the gate green.
6. Commit, rebase onto the latest `origin/main`, push, and watch PR #449 checks.

Suggested restart commands:

```bash
cd ~/Coding/agentic-newsletter-aggregator/.git-worktrees/durable-workflow-contracts/ci-fix
git status --short --branch
git pull --rebase origin main
gh pr checks 449
gh run cancel 29581840339
```

For local contract validation, start the worktree Postgres service on host port `55432` so
the root checkout port `5432` service is not disturbed. Use the test database credentials
declared in `docker-compose.yml`, migrate it with Alembic, and run:

```bash
POSTGRES_PORT=55432 docker compose up -d postgres
.venv/bin/alembic upgrade head
.venv/bin/pytest tests/contract/ -m contract -v --no-cov --tb=short
POSTGRES_PORT=55432 docker compose down -v
```

Set `DATABASE_URL`, `APP_SECRET_KEY`, and the other contract-test environment variables as
declared in `.github/workflows/ci.yml` before migration and testing. The worktree-local
`.venv` already exists but is ignored by Git.

## Separate Workflow Health PR

After the contract fix is pushed, create a small branch from current `main` for the two
unrelated workflow defects. Do not expand PR #449 with these changes.

### iOS

The latest iOS run
[29552072426](https://github.com/jankneumann/agentic-content-analyzer/actions/runs/29552072426)
fails because `.github/workflows/ios-build.yml` sets the default working directory to
`web`, then runs `cd web && ...` again.

Fix both install/build steps to run directly from `web`, and use:

```bash
pnpm install --frozen-lockfile
pnpm build
```

### Tauri Intel

The current main Tauri run
[29552072445](https://github.com/jankneumann/agentic-content-analyzer/actions/runs/29552072445)
and four predecessors remain queued because `macos-13` has no available runner. Linux,
Windows, and Apple Silicon all pass. Replace `macos-13` with the currently supported
`macos-15-intel` label, then cancel stale queued runs after the replacement is pushed.

## Completion Order

1. Make PR #449 contract tests bounded and green.
2. Rebase-merge PR #449 and verify the resulting main run.
3. Land the separate iOS/Tauri workflow-health PR and verify both workflows.
4. Close #448 only after the full contract suite and workflows pass.
5. Execute the coordinated production cutover tracked by #446.
6. Address the non-blocking dependency and API hardening findings in #447.

## Final Session Checklist

Before ending the next session:

```bash
git status
git add docs/HANDOFF_UNIFIED_CONTENT_WORKFLOWS_2026-07-17.md
bd sync
git commit -m "docs: add unified workflow handoff"
git pull --rebase origin main
git push
git status
```

`bd sync` is expected to fail until a Beads database is configured; record the result and
continue with the GitHub issue update. Confirm the branch reports that it is up to date
with its remote and update the relevant issue with validation evidence and any remaining
blocker.
