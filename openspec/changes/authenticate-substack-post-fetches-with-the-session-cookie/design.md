# Design: Authenticate Substack post fetches with the session cookie

## Why not keep `substack_api`

`substack_api` 1.3.1 (`post.py`, `newsletter.py`, `auth.py`) authenticates only
through `SubstackAuth(cookies_path)`, which reads a JSON cookies file into its
own `requests.Session`. Using it would mean writing `substack.sid` to disk,
bypassing the live `CredentialProvider` (no per-request rotation), and escaping
the ri-05 dead-session policy. Its two calls are plain JSON GETs, so the adapter
now makes them itself through `SubstackClient._get_with_session()`:

| Library call | Endpoint (now via httpx) |
|---|---|
| `Newsletter.get_posts(sorting="new", limit=n)` | `GET <publication>/api/v1/archive?sort=new&offset=0&limit=n` |
| `Post.get_metadata()` / `get_content()` | `GET <publication>/api/v1/posts/<slug>` |

Details:

- The post URL is built from the **configured publication URL** and the slug,
  never from the payload's `canonical_url` host, so the cookie only goes to
  hosts the operator configured. Slugs must match
  `[A-Za-z0-9][A-Za-z0-9._~-]*`; anything else (`../`, `/`, empty) is skipped.
- The client still never follows redirects on its own (a sign-in redirect must
  be judged as a dead session). The library's `requests` followed redirects, so
  to keep publications that moved host working, `_get_publication_json()`
  follows exactly one redirect whose target is the same API path on another
  https host. Any other redirect is an ordinary failure.
- A detail failure that is not a session verdict (404, 429, 5xx, network) keeps
  the archive entry; with no body it is reported as `extraction_failed`, as
  before. A dead session anywhere raises and the run persists zero rows.
- Post-detail requests are paced by `substack_request_delay_s` (setting,
  env `SUBSTACK_REQUEST_DELAY_S`, default 1.0 s, 0 to 30): the library slept 2 s
  per request, and runs now use the operator's own paid account. The delay
  applies between detail requests across the run, not before the first; the
  client takes `request_delay_s`/`sleep` as a test seam.

## A 403 on a publication endpoint is ambiguous

On the probe (`/api/v1/subscriptions`) a non-Cloudflare 403 is a dead session.
On the archive and post endpoints it may only mean this reader's tier cannot
see that post (a founding-only post for a paid-tier reader). So publication
requests pass `forbidden_is_ambiguous=True` to `_get_with_session()`, which then
returns such a 403 unjudged (no refresh, no `mark_rejected`), and
`_get_publication()` asks the probe, once per run (`begin_run()` resets it):

- probe dead: `verify_session()` does its own refresh-once/retry-once, records
  the rejection, and raises `SessionExpiredError`; the run persists zero rows;
- probe accepts the session (or is inconclusive: no evidence of a dead
  session): `PublicationAccessDeniedError`. A post keeps its archive entry,
  and the value-free `substack.post_access_denied: slug=<slug>` is logged (the
  slug passed the slug regex); an archive is skipped with
  `substack.archive_access_denied`. If the probe's refresh rotated the cookie,
  the refused request is retried once with the new one first.

To keep the teaser in that case, a paid post with no readable body stores the
archive's `truncated_body_text` as a `substack_body = teaser` row, which a later
run upgrades. 401, sign-in redirects, and HTML from a JSON endpoint remain
unconditional dead-session verdicts on every endpoint.
- The default client sends the browser-like `User-Agent` the library used and
  `Accept: application/json`.
- `mark_verified()` is still only called by the probe/subscriptions: archive
  and post endpoints are public, so their 200 proves nothing.

## Teaser detection

Substack does not return an explicit "you only got the preview" flag that we
can rely on without a live account, so detection uses signals that a full body
cannot produce:

1. `audience` in `{"only_paid", "founding"}` marks a paid post (the library's
   own `is_paywalled()` uses `audience == "only_paid"`). Other posts are never
   classified.
2. No `body_html` on a paid post: teaser (the library's `get_content()` treats
   an empty body on an `only_paid` post as paywalled).
3. `wordcount` counts the whole post even for a logged-out reader. A body with
   fewer than 80% of `wordcount` words is a teaser. The margin absorbs caption,
   footnote and markup counting differences.
4. A paid body with no usable `wordcount` counts as full: no evidence, no guess.

Marker strings inside `body_html` (paywall divs) were rejected: they also
appear in full bodies served to subscribers, so they cannot tell the two apart.

A valid session can still receive a teaser (not subscribed to that tier, or a
custom domain that does not honour `substack.sid`). Those rows are stored with
`substack_body = teaser`, a `substack.paid_teasers` warning logs the count, and
they stay upgradeable. No new diagnostic code was added, to keep the closed
vocabulary unchanged.

## Failing closed without a cookie

ri-05 kept cookie-less runs "successful" because the post path never sent the
cookie, so a cookied run fetched the same bodies. Its design said to revisit
this once the path was authenticated. That is now true, and a cookie-less run
of a paid source produces only teasers that dedup would then keep forever.

Is the `substack` source type paid-only? By construction, yes:
`sync_substack_sources()` writes paid subscriptions (`membership_state` other
than `free_signup`) to `substack.yaml` and free ones to `rss.yaml` as `/feed`
URLs, removing paid ones from `rss.yaml`; `docs/SETUP.md` introduces the
section with "Substack paid posts require an authenticated session cookie".
Nothing else creates `substack` sources. An operator can still add a free
publication by hand, but RSS is the documented path for free publications, and
a per-source `paid` flag would widen the `SubstackSource` schema (source
overrides, contracts) for a case the sync never produces. So the whole run fails
closed; the documentation says free publications go through RSS.

Mechanics: `SubstackClient.require_session_cookie()` makes one bounded
`provider.refresh()` when the value is missing (a cookie just patched into
OpenBao should not be reported missing from a stale cache), then raises
`CredentialsMissingError` (new, in `credential_failures.py`, next to
`SessionExpiredError`). `ingest_content()` catches `CredentialFailureError` and
returns `status=error`, `items_ingested=0`, one `credentials_missing` error,
before any request or `get_db()`. A run whose sources are all disabled needs no
cookie. `credentials_missing` is already in the sanitizer's closed vocabulary
(ri-05) and is the readiness code `_substack_readiness` reports.

Superseded ri-05 artifacts: its design's "No cookie: warn, do not fail" section
is marked superseded, the cookie-less sentence and scenario are removed from its
spec delta, and `test_cookie_less_run_keeps_public_posts_and_warns` is replaced
by `test_cookie_less_run_returns_zero_rows_with_credentials_missing`.

The real-ingestion live policy listed `substack` as free (no key). With
fail-closed, a live run without the secret would be a guaranteed failure, so it
is now `_credentialed("substack", "SUBSTACK_SESSION_COOKIE")` (skip with reason),
which is what `openspec/specs/real-ingestion-ci` already says.

## Teaser upgrade

Dedup finds an existing row by `(source_type, source_id)`. Without
`--force`, the adapter now upgrades it only when all hold:

- the fresh fetch is paid with `substack_body = full`;
- its content hash differs from the stored one;
- the stored row is a teaser: `substack_body = teaser`, or no recorded body
  state (rows stored before this change were always fetched logged out) and
  fewer than 80% of the fresh body's words;
- the stored row is not `processing` (a running summarization would write a
  summary of the teaser after ours is deleted; the next run upgrades it).

The upgrade overwrites the fetched fields (shared `_overwrite_content()` with the
`--force` path), deletes the row's `Summary` rows (the summarizer skips content
that already has one, the same approach as arXiv's version update), and resets
the status to `parsed`. A `filtered_out` row keeps that status: setting it to
`parsed` would bypass the ingestion filter, whose hook only evaluates rows by
`ingested_at`; `aca filter rerun` can re-judge it on the full body. Search
chunks are rebuilt with `reindex_content()` (fail-safe, gated on
`ENABLE_SEARCH_INDEXING`), mirroring `index_content()` on the insert path:
`register_content_listeners()` exists but nothing registers it.

## Non-goals

- Custom-domain authentication (`connect.sid` on the publication's own domain).
  The client sends `substack.sid` to the configured host; if that host does not
  honour it, rows stay teasers and are upgraded when it does.
- A per-source `paid` flag, new diagnostic codes, or removing the `substack-api`
  dependency.
