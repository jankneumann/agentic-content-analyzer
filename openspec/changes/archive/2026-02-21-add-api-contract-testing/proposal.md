# Change: Add API contract and fuzz testing workflow

## Why
The API surface lacks automated contract validation and fuzzing, which risks regressions and fragile integrations as the FastAPI endpoints evolve.

## What Changes
- Define an API contract testing capability aligned to the FastAPI OpenAPI schema.
- Add schema-driven fuzz testing with Schemathesis against a seeded test environment.
- Introduce contract testing and a broker workflow to coordinate producer/consumer expectations across agents.

## Impact
- Affected specs: validate-api-contracts (new)
- Affected code: FastAPI API layer, CI configuration, test tooling, documentation
- External dependencies: Schemathesis, Pact OSS + Pact Broker (or equivalent contract broker)
