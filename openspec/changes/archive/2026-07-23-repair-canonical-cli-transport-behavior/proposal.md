# Repair canonical CLI transport behavior

> Parent roadmap: `roadmap-workflow-surface-reliability`
> Change ID: `repair-canonical-cli-transport-behavior`
> Effort: M
> Priority: 1

## Why

The shared workflow client currently sends absent cursors as `cursor=`. The API
correctly treats an empty opaque cursor as invalid, so production discovery and
operation-list commands fail with HTTP 422 even though mocked CLI tests pass.
The CLI suite also depends on developer-local YouTube credentials, leaks an
unawaited graph coroutine, and permits diagnostics to contaminate
machine-readable output.

This is the first roadmap item because later release-smoke and evaluation work
must be able to trust the canonical CLI transport.

## What Changes

- Omit absent optional query parameters in `WorkflowApiClient` while preserving
  explicit cursor values.
- Add transport-boundary regressions for operation, capability, and configured
  source pagination.
- Support the documented command-local
  `aca configured-sources --json` spelling.
- Keep JSON stdout to one document and route diagnostics to stderr.
- Make YouTube curation and graph async tests independent of ambient
  credentials and garbage-collection timing.
- Constrain the optional Crawl4AI character detector to a Requests-compatible
  version and migrate the tracked local profile off deprecated Neo4j keys.

## Out of Scope

- Relaxing API cursor validation.
- Restoring direct CLI workflow execution or a transport-specific fallback.
- Changing generated OpenAPI or workflow models.
- Adding deployed cross-surface smoke tests; roadmap item `ri-04` owns them.
- Changing production YouTube transport auto-selection.

## Approaches Considered

### Approach A: Repair the shared client boundary (Recommended)

Build request parameters without absent values in the shared client, test the
serialized URL through `httpx.MockTransport`, and make focused CLI/test hygiene
changes at their existing boundaries.

**Pros**

- Fixes CLI and HTTP-mode MCP consumers at one canonical boundary.
- Preserves strict server-side cursor validation.
- Small, rollback-friendly edits with direct regression coverage.

**Cons**

- Touches several focused test and configuration files.
- Does not itself prove a deployed revision; that remains `ri-04`.

**Effort:** M

### Approach B: Normalize empty cursors in the API

Treat `cursor=""` as equivalent to an absent cursor in capability and operation
services.

**Pros**

- Makes malformed clients appear to work without upgrading.

**Cons**

- Hides a transport defect and weakens the opaque-cursor contract.
- Requires duplicated normalization in multiple services.
- Leaves serialized request behavior untested.

**Effort:** S

### Approach C: Patch only CLI commands

Strip `None` values in each CLI command before calling the shared client.

**Pros**

- Limits the initial code diff to CLI call sites.

**Cons**

- Leaves the shared client unsafe for MCP and future callers.
- Repeats parameter-shaping logic and invites drift.

**Effort:** S

### Selected Approach

Approach A is selected. The approved roadmap requires a trustworthy canonical
transport, so the shared client is the correct repair point. Server validation
and production YouTube selection remain unchanged.

## Impact

- **Code:** shared workflow client, CLI output/discovery edges, logging stream.
- **Tests:** client transport tests plus focused CLI determinism regressions.
- **Configuration:** optional Crawl4AI dependency constraint and local Neo4j
  profile key migration.
- **Contracts:** no OpenAPI shape changes; existing canonical workflow OpenAPI
  remains authoritative.
- **Rollback:** revert the focused implementation commits; no data migration or
  persistent state change is involved.
