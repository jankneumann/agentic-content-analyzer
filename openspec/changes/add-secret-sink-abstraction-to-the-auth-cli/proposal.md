# Add secret sink abstraction to the auth CLI

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `add-secret-sink-abstraction-to-the-auth-cli`
> Effort: M
> Priority: 1

## Summary

Replace the Railway-only --deploy flag on aca auth commands with a --to railway|bao|secrets-file sink under src/cli/, where the OpenBao sink uses KV v2 patch_secret on secret/newsletter and records saved_at beside each value. Add SUBSTACK_SESSION_COOKIE, X_AUTH_TOKEN, and X_CT0 to the Railway secret allowlist for the interim.

## Dependencies

- None

## Acceptance Outcomes

- aca auth gmail --to bao writes only GMAIL_OAUTH_TOKEN_JSON and leaves every other key at secret/newsletter byte-identical, proven by a test against a fake KV v2 client.
- The railway sink behaves exactly as --deploy did, and --deploy remains as a deprecated alias that emits a deprecation warning for one release.
- Gmail and YouTube OAuth flows accept --to bao with no provider-specific code changes.
- settings/deploy/railway_secrets.yaml lists SUBSTACK_SESSION_COOKIE, X_AUTH_TOKEN, and X_CT0.

## Rationale

The background token manager only re-fetches the single secret/newsletter path, so a single-key patch is the only write shape that reaches a running worker without clobbering the LLM keys stored alongside; every later credential write reuses this sink.
