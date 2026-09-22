# Add admin endpoint for browser-session sync

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `add-admin-endpoint-for-browser-session-sync`
> Effort: M
> Priority: 6

## Summary

Add an admin API endpoint that accepts the substack.sid, auth_token, and ct0 cookies, keeps the X-Admin-Key check and audit-log fingerprint, and writes only the session keys with saved_at through the OpenBao sink.

## Dependencies

- `ri-01`
- `ri-02`

## Acceptance Outcomes

- The endpoint rejects requests without a valid admin key with 401 or 403 and records an audit row with admin_key_fp for both accepted and rejected calls.
- A valid request patches only the session keys and leaves every other key at secret/newsletter byte-identical.
- No cookie value appears in logs, audit rows, or error responses.

## Rationale

Gives the extension a tailnet-reachable write path for the fast manual response when an expiry alert fires and the operator is at a laptop rather than the workstation.
