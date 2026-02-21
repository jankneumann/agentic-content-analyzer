## Context
We need a shared, automated contract testing workflow for FastAPI endpoints that supports schema validation, fuzz testing, and multi-agent coordination. The system already exposes OpenAPI via FastAPI, but there is no automated validation pipeline enforcing it.

## Goals / Non-Goals
- Goals:
  - Provide schema-based API contract validation using OpenAPI as the source of truth.
  - Add fuzz testing to detect edge-case failures early.
  - Establish a contract broker workflow for multi-agent producer/consumer collaboration.
- Non-Goals:
  - Replacing existing unit/integration test suites.
  - Defining production SLOs or load testing.

## Decisions
- Decision: Use Schemathesis to generate fuzz and schema validation tests against the FastAPI OpenAPI schema.
  - Alternatives considered: Dredd, custom pytest generators; Schemathesis provides modern OpenAPI-aware fuzzing and is actively maintained.
- Decision: Defer Pact OSS / contract broker until external API consumers exist.
  - Rationale: Single-producer system with no external consumers — Pact adds overhead without value. Revisit when multi-agent consumers are introduced.
  - Alternatives considered: bespoke JSON schema checks or repo-local contract files; broker enables multi-agent coordination and versioning.

## Risks / Trade-offs
- Fuzz testing can be flaky without deterministic fixtures → Mitigation: seed the test database and limit initial fuzz cases.
- Contract broker adds operational overhead → Mitigation: scope to a minimal broker setup and start with a single producer/consumer contract.

## Migration Plan
1. Document the OpenAPI contract inventory and critical endpoints.
2. Add Schemathesis tests and run locally against seeded test environment.
3. Pilot Pact contracts for one API surface and publish to broker.
4. Add CI jobs for Schemathesis and Pact verification.

## Open Questions
- Which endpoints are considered critical for initial contract coverage?
- Should the broker run in docker compose for local development or use a hosted OSS broker?
