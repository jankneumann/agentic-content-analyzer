# Change: Close out database source override evidence

## Why

Database-backed source storage, merge precedence, API authentication, and CLI
management are implemented. The historical change still overclaims completion:
the OpenAPI request shape and runtime differ, component/browser evidence is
missing, setup guidance is absent, migration behavior is not executable
evidence, and the design names obsolete enable/disable endpoints.

## Source and completed scope

- Extracted from archived `db-source-overrides`.
- Completed and excluded: table/model/service, validated source union, natural
  keys, YAML/DB precedence, disable shadows, fail-open merge, backend CRUD/PATCH
  behavior, authentication, and CLI commands.
- This closeout SHALL not redesign source resolution or add a second registry.

## What Changes

- Select one request/response contract that matches source-type discrimination
  and the runtime PATCH behavior, then regenerate clients if required.
- Add component/browser coverage for add, toggle, origin badges, and
  origin-aware deletion controls.
- Document setup and operations.
- Add executable migration evidence and update current durable design
  references or ADRs while leaving the archived source immutable.

## Capability

- `source-override-closeout-evidence`

## Impact

OpenAPI/generated clients, source settings UI tests, migration tests, setup
documentation, and current durable design/ADR alignment may change. Existing
database rows and natural keys remain compatible. The dated
`db-source-overrides` archive remains unchanged.
