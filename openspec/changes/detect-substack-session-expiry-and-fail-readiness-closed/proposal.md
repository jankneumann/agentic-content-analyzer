# Detect Substack session expiry and fail readiness closed

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `detect-substack-session-expiry-and-fail-readiness-closed`
> Effort: M
> Priority: 2

## Summary

Make the Substack adapter detect a login redirect or HTML login page in place of JSON and raise a typed readiness failure with the stable code session_expired, and route the descriptor readiness_resolver through the credential provider so a patched cookie flips readiness without restart.

## Dependencies

- `ri-04`

## Acceptance Outcomes

- A Hoverfly-simulated login redirect makes the Substack descriptor report ready=false with code session_expired and the run produces zero rows rather than a partial result.
- Patching a fresh cookie into the OpenBao cache flips the descriptor to ready=true in the same process without restart.
- The typed readiness failure is reusable by other adapters and carries no cookie value in its message or payload.

## Rationale

Today an expired cookie only produces a log warning and a silently thinner corpus; the proposal requires credential-gated sources to yield ready=false with a stable code rather than a partial run.
