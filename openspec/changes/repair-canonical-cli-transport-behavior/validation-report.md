# Validation Report: repair-canonical-cli-transport-behavior

**Date**: 2026-07-23 13:55:21 EDT
**Commit**: c0737dbc
**Branch**: openspec/repair-canonical-cli-transport-behavior
**Scope**: spec,evidence

## Phase Results

- ✓ Spec Compliance: 4/4 requirements have passing evidence in `change-context.md`; strict OpenSpec validation passed.
- ✓ Package Plan: schema, dependency references, DAG, lock keys, parallel scope overlap, and lock overlap passed.
- ✓ Package Evidence: 5/5 work-queue results passed schema, scope, verification, revision, and required-output checks.
- ✓ Cross-Package Consistency: plan revision 1 and contract revision 1 match for every package; no file overlap was reported between parallel packages.
- ✓ Focused Regression Gate: 382 passed, 1 skipped across CLI, canonical workflow client, and runtime-hygiene tests with `RuntimeWarning` promoted to an error.
- ✓ Runtime Hygiene: the lock resolves `chardet==5.2.0`; after aligning the validation environment, the Requests compatibility warning is absent.
- ✓ Static Quality: Ruff, Mypy (399 source files), `uv lock --check`, and `git diff --check` passed.
- ✓ Review: all three fix-disposition findings from independent cross-package and whole-branch review are resolved.
- ○ Deploy and Production Smoke: skipped in this item-level `spec,evidence` validation; production cross-surface proof belongs to roadmap item `ri-04`.
- ⚠ Log Analysis: one pre-existing `graphiti-core` class-based Pydantic configuration deprecation notice remains; it is unrelated to the changed dependency boundary and no unawaited-coroutine warning remains.
- ○ Generated Architecture Flow: skipped because this checkout has no `docs/architecture-analysis/architecture.graph.json`; manual impact analysis found no contract, persistence, or dependency-direction change.

## Result

**PASS** — ri-01 satisfies its local specification and evidence gates and is ready to
rejoin the roadmap integration branch. Production transport proof remains explicitly
deferred to dependent roadmap item `ri-04`.
