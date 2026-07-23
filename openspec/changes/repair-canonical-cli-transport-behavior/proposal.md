# Repair canonical CLI transport behavior

> Parent roadmap: `roadmap-workflow-surface-reliability`
> Change ID: `repair-canonical-cli-transport-behavior`
> Effort: M
> Priority: 1

## Summary

Fix optional query serialization in the shared workflow client and stabilize the affected CLI tests and machine-readable output. Cover capability discovery, configured sources, operation listing, credential-dependent curation behavior, and asynchronous graph tests at the real transport boundary.

## Dependencies

- None

## Acceptance Outcomes

- aca capabilities --json, aca configured-sources --json, and aca --json operations list succeed against a deployed API when no cursor is supplied.
- Transport-level tests assert that absent optional values do not appear in serialized query strings.
- CLI tests cannot select a live YouTube API path based on developer-local credentials.
- The CLI suite completes without unawaited-coroutine warnings, and JSON stdout contains only the requested result.

## Rationale

Production discovery and operation commands currently fail despite strong mocked coverage, so the canonical CLI surface must be trustworthy before higher-level evaluations depend on it.
