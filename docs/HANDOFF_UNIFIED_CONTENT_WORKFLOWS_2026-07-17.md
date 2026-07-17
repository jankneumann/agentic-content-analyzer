# Unified Content Workflows Handoff

Last updated: 2026-07-17 19:20 EDT

## Outcome

The unified content workflow refactoring and its post-merge contract stabilization are
complete on `main`. The durable workflow contracts are now independent of archived
OpenSpec changes, the full API contract/fuzz suite is bounded and green, and the Tauri
desktop matrix passes on all supported runners.

The iOS workflow now completes dependency installation, the web contract/build, and
Capacitor synchronization. TestFlight deployment remains separate follow-up work because
the repository does not yet contain a Fastlane `Gemfile` and the required signing/App
Store Connect secrets are not configured.

## Repository State

- Repository: `jankneumann/agentic-content-analyzer`
- Original implementation: PR [#445](https://github.com/jankneumann/agentic-content-analyzer/pull/445)
- Durable contract refactor: PR [#449](https://github.com/jankneumann/agentic-content-analyzer/pull/449), merge `7b682598`
- CI and runner repair: PR [#450](https://github.com/jankneumann/agentic-content-analyzer/pull/450), merge `15104d75`
- Contract and iOS dependency repair: PR [#451](https://github.com/jankneumann/agentic-content-analyzer/pull/451), merge `3940812a`
- iOS Node upgrade: PR [#452](https://github.com/jankneumann/agentic-content-analyzer/pull/452), merge `cc20191d`
- Final agent-task query validation: PR [#454](https://github.com/jankneumann/agentic-content-analyzer/pull/454), merge `c8ef6747`
- Primary tracking issue: [#448](https://github.com/jankneumann/agentic-content-analyzer/issues/448), closed with validation evidence
- TestFlight follow-up: [#453](https://github.com/jankneumann/agentic-content-analyzer/issues/453)
- Production rollout: [#446](https://github.com/jankneumann/agentic-content-analyzer/issues/446)
- Security follow-up: [#447](https://github.com/jankneumann/agentic-content-analyzer/issues/447)

The root checkout remains an unrelated dirty checkout on `temp-merge-431`; its untracked
files were not modified. This work was completed in
`.git-worktrees/durable-workflow-contracts/ci-fix`.

There is no Beads database in this checkout. `bd sync` reports
`no beads database found`; GitHub issues are the durable task record.

## Delivered Architecture

`openspec/contracts/content-workflows/` is the durable executable contract registry,
parallel to `openspec/specs/` and outside the OpenSpec change/archive lifecycle. It owns:

- `openapi/v1.yaml`
- `events/operation.progress.schema.json`
- `db/schema.sql` and `db/seed.sql`
- generated Python and TypeScript models
- registry and lifecycle documentation

Live code, generators, and tests no longer depend on `openspec/changes/` or
`openspec/changes/archive/`. Archived contract files remain immutable historical
snapshots.

Key implementation and documentation files include:

- `openspec/contracts/README.md`
- `openspec/contracts/content-workflows/README.md`
- `scripts/generate_workflow_contracts.py`
- `tests/contract/test_canonical_workflow_contracts.py`
- `tests/contract/conftest.py`
- `tests/queue/test_operation_service.py`
- `tests/services/test_capability_service.py`
- `docs/ARCHITECTURE.md`

## Stabilization Work

The follow-up PRs resolved all failures exposed by running the durable OpenAPI contract
against the live application:

- excluded streaming SSE and health-only endpoints from ordinary request/response fuzzing
  and added regression coverage for SSE discovery
- bounded the GitHub contract job and pinned Hypothesis/Schemathesis to lockfile versions
- repaired evaluation, agent, chat, settings, pricing, source, search, knowledge-base,
  topic, and operation boundary behavior
- constrained query parameters so invalid and NUL-containing values are rejected before
  reaching PostgreSQL
- fixed iOS workflow directory handling, frozen dependency installation, uv availability,
  and Node 22 compatibility
- moved the unavailable Tauri Intel runner from `macos-13` to `macos-15-intel`

## Validation Evidence

Local validation included:

- `make workflow-contracts-check`
- focused contract, operation, capability, upload, evaluation, and agent route tests
- complete contract/fuzz runs against a disposable PostgreSQL database
- Ruff check and format check
- MyPy and pre-commit hooks
- `git diff --check`

GitHub validation:

- PR #454 CI run [29619378527](https://github.com/jankneumann/agentic-content-analyzer/actions/runs/29619378527): all jobs passed, including the full contract/fuzz job
- PR #454 security run [29619378530](https://github.com/jankneumann/agentic-content-analyzer/actions/runs/29619378530): Python and Node audits plus secret scan passed
- Final `main` CI run [29620163060](https://github.com/jankneumann/agentic-content-analyzer/actions/runs/29620163060): all jobs passed, including the full contract/fuzz job
- Tauri run [29614600618](https://github.com/jankneumann/agentic-content-analyzer/actions/runs/29614600618): Linux, Windows, Intel macOS, and Apple Silicon macOS passed
- iOS run [29618584088](https://github.com/jankneumann/agentic-content-analyzer/actions/runs/29618584088): dependency install, web contract/build, and Capacitor sync passed; deployment stopped at the unconfigured Fastlane/signing boundary tracked by #453

## Remaining Work

No refactoring or contract-stabilization work remains.

1. Complete TestFlight signing and Fastlane setup in #453. Add a `Gemfile` or remove the
   `bundle exec` mismatch, configure signing/App Store Connect credentials, add a clear
   preflight, and prove a signed IPA upload.
2. Execute the coordinated production cutover in #446 only with explicit deployment
   authority. It was intentionally not performed during this refactoring session.
3. Address the non-blocking dependency and API hardening work in #447.

## Restart Context

A future session should start from current `origin/main`, not from the historical feature
branches. Before taking rollout action, read #446 and verify the current CI state. For iOS
deployment, work exclusively from #453 and treat credentials/signing as the primary
blocker rather than reopening the completed workflow refactor.
