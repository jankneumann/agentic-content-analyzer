## Context
Integration tests currently mock external services, which avoids cost and instability but skips HTTP-level behavior (request composition, retries, headers, error mapping). We want a proxy-based simulator to replay realistic HTTP interactions while keeping tests deterministic.

## Goals / Non-Goals
- Goals:
  - Add Hoverfly as an optional integration test dependency.
  - Allow external HTTP clients to route through a proxy or base URL in tests.
  - Capture/replay simulations for supported HTTP integrations.
- Non-Goals:
  - Replace unit-test mocks for pure logic tests.
  - Enable live external API calls in CI.

## Decisions
- Decision: Use Hoverfly in simulate mode for CI integration tests with captured fixtures.
  - Alternatives considered: VCR.py-style fixtures or custom mock servers. Hoverfly offers protocol-aware simulation and captures real traffic without SDK-specific stubs.
- Decision: Introduce a test-only proxy/base URL configuration in settings to route HTTP clients through Hoverfly.
  - Alternatives considered: monkeypatching each SDK at test time (more brittle, less consistent).

## Risks / Trade-offs
- Added test infrastructure complexity (Hoverfly container, simulation fixtures) → Mitigate with clear docs and Makefile targets.
- SDKs may not respect proxy settings uniformly → Mitigate by documenting supported integrations and falling back to mocks where needed.

## Migration Plan
1. Add Hoverfly service and documentation.
2. Add proxy/base URL config and wire it into selected HTTP clients.
3. Capture baseline simulations and store in test fixtures.
4. Update integration tests to use Hoverfly for supported integrations.

## Open Questions
- Which external APIs should be simulated first (RSS, Anthropic/OpenAI, TTS)?
- Preferred storage location and naming convention for simulation files.
