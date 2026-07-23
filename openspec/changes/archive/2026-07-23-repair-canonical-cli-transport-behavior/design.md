# Design: Repair canonical CLI transport behavior

## Context

`WorkflowApiClient` is the canonical synchronous HTTP client for CLI workflow
commands and HTTP-mode MCP tools. `httpx` serializes a mapping entry whose value
is `None` as an empty query value. Both capability and operation services accept
`None` for the first page but intentionally reject an empty opaque cursor.

The current tests miss the defect because fake clients bypass serialization and
one cursor test normalizes both missing and empty values to `None`.

## Goals

- Make absent optional parameters absent on the wire.
- Preserve strict cursor validation and explicit cursor values.
- Guarantee one JSON document on stdout for machine-readable CLI commands.
- Remove environment-sensitive and unawaited-coroutine behavior from the CLI
  unit suite.

## Non-Goals

- Redesigning pagination.
- Adding API compatibility behavior for malformed cursors.
- Deploying or testing Railway services.

## Decisions

### D1 — Filter optional values in the shared HTTP client

The client will construct query parameters with required values and add
`cursor` only when it is not `None`. Tests will inspect `request.url.params`
through `httpx.MockTransport`.

This follows Implementation Rules 0 and 4: the smallest fix preserves current
behavior for every explicit value.

### D2 — Keep command-local JSON compatibility at discovery commands

`configured-sources` will mirror `capabilities` by accepting `--json` after the
command name. Root `aca --json ...` remains supported. Tests will parse stdout
as exactly one JSON value.

### D3 — Separate payload output from diagnostics

The root logging console handler will write to stderr. Human-only graph messages
will be guarded when JSON mode is active. This keeps stdout as the payload
channel without suppressing useful diagnostics.

### D4 — Make unit tests select transports explicitly

RSS-path curation tests will pass `--via-rss`; API-path tests will continue to
pass `--via-api`. The graph extraction test will execute the real sync/async
adapter with `AsyncMock` dependencies rather than replacing the coroutine
consumer.

### D5 — Fix dependency and profile causes instead of blanket suppression

The optional Crawl4AI extra will constrain `chardet` to Requests' supported
range. The tracked local profile will use canonical `neo4j_*` keys. Third-party
warnings will not be globally hidden.

## Risks and Mitigations

- **Risk:** filtering parameters could remove meaningful falsey values.
  **Mitigation:** filter only `None`; preserve `0`, `False`, empty strings
  supplied explicitly, and opaque cursor text.
- **Risk:** moving logs to stderr changes shell redirection behavior.
  **Mitigation:** diagnostics conventionally belong on stderr; JSON payload
  snapshots cover stdout.
- **Risk:** optional dependency resolution changes the lock.
  **Mitigation:** constrain only the Crawl4AI extra and run lock consistency
  checks.

## Package Boundaries

- `wp-transport`: shared client plus serialized-request tests.
- `wp-cli-output`: discovery commands, logging/graph JSON edges, CLI tests.
- `wp-test-isolation`: curation/graph test determinism.
- `wp-runtime-hygiene`: optional dependency and local profile.
- `wp-integration`: documentation, combined validation, evidence.

The four implementation packages have non-overlapping write scopes and may run
after planning artifacts are complete.
