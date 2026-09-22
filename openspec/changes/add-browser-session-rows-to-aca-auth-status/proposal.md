# Add browser-session rows to aca auth status

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `add-browser-session-rows-to-aca-auth-status`
> Effort: S
> Priority: 5

## Summary

Extend aca auth status with one row per browser session (substack, x) showing saved_at, last_verified_at, and the exact refresh command, in both table and --json output.

## Dependencies

- `ri-04`

## Acceptance Outcomes

- aca auth status --json lists substack and x sessions with saved_at, last_verified_at, and refresh_command fields.
- Stdout contains exactly one JSON document in --json mode with diagnostics on stderr.
- No cookie value appears in either output mode.

## Rationale

Until the terminal-event outbox exists this is the primary place an operator learns that a session is stale and which command to run.
