## 1. Implementation
- [x] 1.1 Inventory FastAPI endpoints and confirm OpenAPI schema coverage for critical routes.
- [x] 1.2 Add Schemathesis configuration and baseline contract/fuzz tests targeting core endpoints.
- [x] 1.3 Establish seeded test environment workflow for API contract tests (database + fixtures).
- [ ] 1.4 Introduce contract test artifacts and publish/consume flow via Pact Broker (or equivalent OSS broker).
  - Deferred: Single-producer system with no external consumers — Pact adds overhead without value until multi-agent consumers exist.
- [x] 1.5 Add CI job(s) for contract validation and fuzz testing gates.
- [x] 1.6 Update documentation with local/CI instructions for running contract and fuzz tests.

## Migration Notes
Open task 1.4 migrated to beads issue `aca-c9v` (P4 backlog) on 2026-02-21.
