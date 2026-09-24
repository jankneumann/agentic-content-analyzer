## ADDED Requirements

### Requirement: X Bookmarks GraphQL client authentication

The X bookmarks HTTP client SHALL call X's web Bookmarks GraphQL endpoint with
the public web-app bearer token, the `auth_token` and `ct0` cookies, and an
`x-csrf-token` header equal to `ct0`, reading `X_AUTH_TOKEN` and `X_CT0`
through the live credential provider for every request. It SHALL run in the
standard Python worker image, SHALL NOT shell out, and SHALL NOT send the
session to any host other than `x.com`. When either credential is missing
after one bounded provider refresh it SHALL raise `CredentialsMissingError`
before sending any request.

#### Scenario: A request carries the web session headers

- **WHEN** the client fetches a bookmarks page with a configured session
- **THEN** the request carries the bearer token, the `auth_token`/`ct0` cookie header, and `x-csrf-token` equal to `ct0`

#### Scenario: Static bundles never receive the session

- **WHEN** the client downloads a JavaScript bundle from `abs.twimg.com` during query ID discovery
- **THEN** that request carries no cookie, bearer token, or CSRF header

#### Scenario: A missing cookie fails closed

- **WHEN** `X_AUTH_TOKEN` or `X_CT0` is absent after one provider refresh
- **THEN** the client raises `CredentialsMissingError` with code `credentials_missing` and the refresh command `aca auth session x`, and sends no request

### Requirement: Bookmarks query ID discovery and cache

The client SHALL discover the rotating `Bookmarks` GraphQL query ID from X's
web bundles, first through the webpack runtime chunk map inlined in the
authenticated `/i/bookmarks` page and then through the `main.<hash>.js`
bundle. It SHALL cache the last good ID durably as the settings override
`x_bookmarks.graphql_query_id` and reuse it without scraping. When X answers
404 or a GraphQL "query not found" error, the client SHALL invalidate the
cache, rediscover once, and retry once; a second stale answer SHALL raise
`QueryIdDiscoveryError`.

#### Scenario: Discovery through the runtime chunk map

- **WHEN** the cache is empty and the page's inline runtime maps a `bundle.Bookmarks` chunk to a content hash
- **THEN** the client fetches that chunk, extracts the `Bookmarks` query ID, stores it in the cache, and uses it for the GraphQL request

#### Scenario: Discovery falls back to main.js

- **WHEN** the page has no runtime chunk map but references `main.<hash>.js`
- **THEN** the client extracts the query ID from that bundle

#### Scenario: A cached ID is reused

- **WHEN** the cache holds a valid query ID
- **THEN** the first request goes straight to the GraphQL endpoint with no page or bundle request

#### Scenario: A stale ID is rediscovered once

- **WHEN** the GraphQL endpoint answers 404 for the cached ID
- **THEN** the cache is cleared, the ID is rediscovered, the same page is requested again with the new ID, and the new ID is cached

### Requirement: Bookmarks cursor pagination

The client SHALL walk the bookmarks timeline newest-first by its
`cursor-bottom` entries with a conservative page size (default 20, at most
100), a hard page cap (default 50, at most 500), and a configurable pause
between pages (`x_bookmarks_page_delay_s`, default 1 second). After each
yielded page it SHALL call the caller's `stop_when(page_ids)` hook and stop
when it returns true. The walk SHALL report why it stopped.

#### Scenario: Two-page walk

- **WHEN** page one has a bottom cursor, page two has another, and page three has no posts
- **THEN** two pages are yielded, the second and third requests carry the previous bottom cursor, the walk pauses between pages, and the stop reason is `exhausted`

#### Scenario: stop_when ends an incremental walk

- **WHEN** `stop_when` returns true for page one's post IDs
- **THEN** no second page is requested and the stop reason is `stop_when`

### Requirement: Bookmarks rate-limit handling

On HTTP 429 the client SHALL wait until `x-rate-limit-reset` when that wait
is at most `max_rate_limit_wait_s` (default 15 minutes) and retry, at most
twice per page. Otherwise it SHALL stop the walk gracefully with stop reason
`rate_limited` and the reset time, keeping the pages already yielded.

#### Scenario: A short rate limit is honoured

- **WHEN** X answers 429 with `x-rate-limit-reset` 30 seconds ahead
- **THEN** the client sleeps 30 seconds and retries the same page

#### Scenario: A long rate limit ends the walk with a partial result

- **WHEN** X answers 429 with a reset one hour ahead after one page was yielded
- **THEN** the walk stops with `rate_limited` and the reset time, and does not sleep for the hour

### Requirement: Bookmarks session expiry detection

The client SHALL treat a 401, a 403 without `cf-mitigated`, a redirect into
X's login flow, an HTML page in place of JSON, or a JSON session error as a
dead session. It SHALL then refresh the provider once and retry once when the
pair changed; if the session is still refused it SHALL mark both credentials
rejected and raise `SessionExpiredError` naming `aca auth session x`. A
successful GraphQL response SHALL mark both credentials verified.

#### Scenario: A refused session fails closed

- **WHEN** X answers 401 and the refresh yields the same pair
- **THEN** no retry is sent, both credentials are marked rejected, and `SessionExpiredError` with code `session_expired` is raised

#### Scenario: A login page yields session_expired

- **WHEN** the GraphQL endpoint answers 200 with an HTML login page
- **THEN** the client raises `SessionExpiredError`

#### Scenario: A Cloudflare challenge is not a session verdict

- **WHEN** X answers 403 with a `cf-mitigated` header
- **THEN** the client raises an upstream error and neither refreshes nor marks the session rejected

### Requirement: Rotated ct0 write-back

When a non-dead response carries `Set-Cookie: ct0=<value>` different from the
`ct0` the request used, the client SHALL, before parsing the response, write
`X_AUTH_TOKEN` and `X_CT0` together in one `BaoSink` KV v2 merge-patch on the
worker's authenticated OpenBao client, then apply the same values to the local
credential cache with the sink's `saved_at`, and use the new `ct0` for the
next request. Without OpenBao it SHALL update only the local cache and log a
value-free warning. A write-back failure SHALL NOT fail the fetch.

#### Scenario: A rotated ct0 is written back once

- **WHEN** page one's response sets a new `ct0`
- **THEN** exactly one PATCH with `application/merge-patch+json` writes both keys and their `_SAVED_AT` siblings, and page two's request carries the new `ct0` in the cookie and `x-csrf-token`

#### Scenario: A deleted or unchanged ct0 is not written

- **WHEN** a response sets the same `ct0` or deletes it with `Max-Age=0`
- **THEN** nothing is written

#### Scenario: A failing sink does not fail the fetch

- **WHEN** the OpenBao PATCH fails
- **THEN** the failure is logged by type, the walk continues, and the next request uses the new `ct0`

### Requirement: Value-free bookmark records and logs

The client SHALL map each post to a value-free record with the post ID, the
canonical URL `https://x.com/<handle>/status/<id>`, the note-tweet full text
when present, the author ID, handle and name, `created_at` in UTC, the
conversation ID, expanded outbound URLs excluding x.com, twitter.com and t.co
links, media URLs, and one level of quoted post. No log record, exception
message, exception chain, or record repr SHALL contain a cookie or bearer
value; httpx errors SHALL be reported by type only.

#### Scenario: A long-form post quoting another post

- **WHEN** a bookmarked post has a note tweet and quotes another post
- **THEN** the record's text is the note-tweet text with links expanded, its outbound URLs exclude X self links, and its quoted record has its own author and URL and no further quote

#### Scenario: No credential in logs

- **WHEN** any client path runs, including rotation, rejection, and network errors
- **THEN** no captured log record, stdout, or stderr contains a cookie or bearer value
