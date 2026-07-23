# RI-03 implementation review

**Reviewer**: independent Codex reviewer
**Date**: 2026-07-23
**Status**: Clean sign-off after rework

## Findings and resolutions

1. **Source mutation result overclaim** — The merged main spec required
   key/version/origin/enabled metadata for DELETE although runtime returns
   `{source_key, deleted}`. The requirement now distinguishes POST/PATCH from
   DELETE and matches `source_write_routes.py`.
2. **Work-package scope omissions** — Reconciled deployment, discovery-history,
   prioritization, and mobile-deployment documents were not in the archive
   package's write allowlist. Exact paths are now included.
3. **Stale live prioritization report** — `openspec/priorities/latest.md`
   continued to present archived entries as live recommendations. It now has a
   dated reconciliation banner and points readers to the current inventory.
4. **Validator evidence count drift** — Evidence now reports the current six
   passing validator tests.
5. **Broken post-archive evidence paths** — RI-01/RI-02 validation evidence and
   the frontend deployment validator input now use a phase-stable command that
   resolves the active or dated path without masking test failures.
6. **Untracked language-gate claim** — The filtering successor now explicitly
   requires a decision to implement detector/fail-open semantics and tests or
   retire the language promise consistently.
7. **Incomplete disposition snapshot** — The YAML snapshot now records
   disposition, next lifecycle action, and final location for every retained,
   successor, archived, and self-archived entry; the validator enforces exact
   coverage.
8. **Archive immutability** — The source-override successor now targets current
   durable design documentation or an ADR and explicitly forbids edits to the
   dated archive.

All affected active changes and the corrected main spec pass strict OpenSpec
validation after rework.
