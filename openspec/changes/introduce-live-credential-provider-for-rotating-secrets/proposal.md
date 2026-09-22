# Introduce live credential provider for rotating secrets

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `introduce-live-credential-provider-for-rotating-secrets`
> Effort: M
> Priority: 2

## Summary

Add a CredentialProvider that resolves a named credential at request time from the OpenBao cache first and falls back to Settings, carrying saved_at and last_verified_at metadata, and migrate the Substack adapter to it with all reads and writes passing through log redaction.

## Dependencies

- `ri-02`

## Acceptance Outcomes

- After a KV patch and one token-manager refresh, a long-running worker process uses the new Substack cookie without restart, proven by an integration test that swaps the cache.
- src/ingestion/substack.py no longer references settings.substack_session_cookie directly.
- The provider exposes saved_at and last_verified_at for the substack.sid, x.auth_token, and x.ct0 credentials.
- No credential value appears in log output in any provider test.

## Rationale

The module-level settings object is built once behind lru_cache, so adapters reading settings.substack_session_cookie keep the boot-time value forever and a rotated cookie never reaches a running worker.
