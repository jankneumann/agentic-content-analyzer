# Real ingestion test tiers in CI

> Parent roadmap: `ingestion-reliability`
> Change ID: `real-ingestion-test-tiers-in-ci`
> Effort: M
> Priority: 1

## Summary

Un-skip and implement test_ingest_actually_writes_to_db (tests/cli/test_ingest_contract.py:383) using the existing Hoverfly RSS simulation and the CI Postgres service. Add a PR-blocking job running pytest -m 'integration or hoverfly' (41 tests currently deselected by ci.yml:152 / pyproject.toml:285). Add a nightly schedule: workflow running the Hoverfly-replayed pipeline plus a minimal live_api smoke set.

## Dependencies

- None

## Acceptance Outcomes

- A run whose claimed items_ingested does not match the DB row delta fails CI
- All integration-marked tests execute on every PR
- Upstream feed/API format breakage produces a red nightly run within 24 hours

## Rationale

The exact reported symptom — orchestrator returns 0, CLI reports success — has a written test that is skipped, and CI executes zero real ingestion behavior.
