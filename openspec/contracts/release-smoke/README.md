# Release Smoke Contracts

This directory is the durable source of truth for the cross-surface release-smoke
observation contracts. Live application code, generators, and tests consume these
files directly. Copies under `openspec/changes/archive/` are historical snapshots
and MUST NOT be used as runtime or test inputs.

- `release-smoke-evidence.schema.json` is the machine-readable evidence contract.
  It is intentionally restrictive and must be validated before a report is
  retained or uploaded. The runtime copy at
  `src/release_smoke/release_smoke_evidence.schema.json` MUST stay byte-identical
  to this file; `tests/release_smoke/test_evidence.py` enforces that parity.
- `retired-workflow-mutations.json` is the non-overridable baseline denial policy.
  The implementation promotes the same entries to
  `config/release_smoke_retired_routes.json`; runtime configuration may add but
  never remove entries.

This change does not modify the canonical workflow OpenAPI
(`openspec/contracts/content-workflows/openapi/v1.yaml`). It adds operational
release-observation fields outside that workflow contract: the backend `/health`
`revision` and allowlisted `revision_source` strings, the served frontend
`release-revision` / `release-revision-source` meta values, and the served
frontend `release-assets.json` revision-bound asset inventory with sizes and
SHA-256 digests.
