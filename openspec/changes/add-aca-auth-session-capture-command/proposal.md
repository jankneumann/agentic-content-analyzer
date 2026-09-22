# Add aca auth session capture command

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `add-aca-auth-session-capture-command`
> Effort: L
> Priority: 3

## Summary

Add aca auth session substack|x, which launches headed Chromium via Playwright launch_persistent_context on a per-site profile under ~/.aca/browser-profiles/, polls context.cookies() for the target cookies, validates them with one cheap authenticated request, and writes them with saved_at through the secret sink.

## Dependencies

- `ri-01`
- `ri-02`
- `ri-07`

## Acceptance Outcomes

- Running the command with a stubbed browser context that already holds the cookies validates them and patches OpenBao within one invocation, with no cookie value on stdout or in logs.
- Running it against a context that never produces the cookies exits non-zero with a timeout message after the configured wait.
- A second run reuses the persisted profile directory and needs no interactive login when the session is still valid.
- No refresh timer, cron entry, or scheduled job is created by the command.
- docs/SETUP.md replaces the manual DevTools instructions for Substack with the command.

## Rationale

Replaces the manual DevTools cookie copy with a deterministic one-time login per site, and is the command an expiry alert names when the yearly auth_token expiry fires.
