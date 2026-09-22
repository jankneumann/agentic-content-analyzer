# Implement X GraphQL client with query ID discovery and ct0 write-back

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `implement-x-graphql-client-with-ct0-write-back`
> Effort: M
> Priority: 1

## Summary

Build an httpx client for X's Bookmarks GraphQL endpoint using the public web-app bearer token, auth_token and ct0 cookies, an x-csrf-token header equal to ct0, query ID discovery from X's JavaScript bundles cached as a DB override and re-scraped on 404, 429 handling honouring x-rate-limit-reset, session_expired detection, and OpenBao patch of a rotated ct0 before the response is discarded.

## Dependencies

- `ri-02`
- `ri-04`
- `ri-05`

## Acceptance Outcomes

- Hoverfly tests cover query ID discovery, a 404 that triggers re-scrape, a 429 with x-rate-limit-reset that is honoured, and a login-page response that yields the typed session_expired failure.
- A Set-Cookie header carrying a new ct0 is written back through a fake sink as a single-key patch before the response is discarded.
- The client runs from the python:3.12-slim image and shells out to nothing.
- No cookie or bearer value appears in logs or test output.

## Rationale

This is the port of the exporter's fetch logic that removes the Node.js dependency and lets the worker heal routine ct0 rotation itself, so the human is only needed for the yearly auth_token expiry.
