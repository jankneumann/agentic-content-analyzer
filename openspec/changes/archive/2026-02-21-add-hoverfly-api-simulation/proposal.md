# Change: Add Hoverfly-based API simulation for integration tests

## Why
Current integration tests rely on direct mocks for external HTTP services, which limits end-to-end validation of HTTP behaviors (headers, retries, error mapping). Introducing a proxy-based simulator enables realistic HTTP interactions without external dependencies.

## What Changes
- Add Hoverfly-backed API simulation support for integration tests.
- Introduce test-time HTTP proxy/base URL configuration for external client calls.

## Impact
- Affected specs: test-infrastructure
- Affected code: integration test tooling, HTTP client configuration (RSS ingestion, LLM providers, TTS)

## Related Proposals

This proposal is a **subset of `add-test-infrastructure`**, which provides:
- Model factories (ContentFactory, SummaryFactory, etc.)
- Database fixtures with transaction rollback
- Test organization (unit/integration/e2e markers)
- **Hoverfly integration points** (this proposal)

The `add-test-infrastructure` proposal coordinates this work within a broader testing strategy.

## Dependencies

- Required by: `add-test-infrastructure` (Hoverfly fixtures)
- Used by: `add-deployment-pipeline` (CI runs integration tests with Hoverfly)
