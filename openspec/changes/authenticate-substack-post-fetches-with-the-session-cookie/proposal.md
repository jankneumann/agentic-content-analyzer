# Authenticate Substack post fetches with the session cookie

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `authenticate-substack-post-fetches-with-the-session-cookie`
> Effort: M
> Priority: 8

## Summary

Send the live substack.sid on the requests that fetch Substack post bodies (the substack_api Newsletter/Post path, or an httpx replacement), so paid posts are ingested in full. Once authenticated, make a Substack run without a cookie fail closed with credentials_missing, and re-fetch teaser rows that dedup would otherwise keep forever.

## Dependencies

- `ri-05`

## Acceptance Outcomes

- A mocked paid post that returns a truncated body without substack.sid and the full body with it is ingested in full when the cookie is configured.
- No request on the post-fetch path is sent without the live cookie when one is configured, and no log line or exception contains the cookie value.
- A Substack run with no configured cookie returns zero rows with readiness code credentials_missing.
- A previously ingested teaser row for a paid post is updated to the full body on the next authenticated run.

## Rationale

Paid Substack access is why the session cookie exists; today the post path never sends it, so capture and rotation have no effect on content.
