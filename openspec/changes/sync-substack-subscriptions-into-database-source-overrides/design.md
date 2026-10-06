# Design: Sync Substack subscriptions into database source overrides

## Context

`SubstackClient.fetch_subscriptions()` returns `SubstackSubscription(name, url,
is_paid)`; paid means `membership_state` is neither `free_signup` nor missing.
It returns `[]` when no cookie is configured and swallows transport errors, so
the sync cannot call it as is: an empty result must never look like "you
unsubscribed from everything".

`source_key()` is the raw `type:url` string, so `https://x.substack.com` and
`https://x.substack.com/` are different keys, and YAML often uses custom domains
(`https://hardcoresoftware.learningbyshipping.com`) or feed URLs
(`https://ruben.substack.com/feed`).

## Decisions

### D1. Match publications by a normalized locator, across both types

A publication is identified by `host` (lowercased, `www.` dropped) plus `path`
(trailing `/` and a trailing `/feed` dropped). Every configured `substack` and
`rss` source, YAML and database, enabled or disabled, is indexed by that
locator. A subscription is:

| Configured as | Owner | Result |
|---|---|---|
| nothing | — | **add** (`substack` if paid, `rss` `/feed` if free) |
| same type | anyone | **existing** (or **kept_disabled**) — untouched |
| other type | sync (`managed_by`) | **switch**: disable the managed row, add the new type |
| other type | operator | **conflict** — reported, nothing written |

The new row's URL is the subscription's base URL without a trailing slash, so a
later YAML entry for the same publication shadows or duplicates predictably.

### D2. Ownership marker: a `managed_by` column

`source_overrides.managed_by VARCHAR(64) NULL`. The sync writes
`substack-sync`. `--prune` only disables enabled rows with that marker whose
locator is not among the current subscriptions of that type. A description
convention was rejected: an operator edit through `aca sources add` would keep
or drop it unpredictably. Operator writes through `upsert` leave `managed_by`
unchanged unless passed, so an operator who edits a synced row keeps it synced;
to take ownership they can `aca sources remove` and re-add it.

### D3. Fail closed before planning

The service calls `require_session_cookie()` and then lists subscriptions with
a strict variant that raises on transport failure. `CredentialsMissingError` and
`SessionExpiredError` surface as `credentials_missing` / `session_expired` with
the refresh command (HTTP 412, CLI exit 1). Zero subscriptions with `--prune`
is refused.

### D4. Dry run by default

Matches `aca curate` (`--apply` to write). The plan is returned in both modes
with the same shape, so the dry run shows exactly what apply would do. All
writes of one apply commit in one transaction.

### D5. HTTP first, direct fallback

`POST /api/v1/sources/sync/substack` body `{apply, prune}` returns the plan. The
CLI follows the existing `aca sources` pattern (API client, `--direct` or a
connection error falls back to the database with `guard_remote_backend`). The
route is excluded from schemathesis fuzzing because it calls substack.com.

## Risks

- Substack changes the subscriptions payload: the listing is strict, so the
  sync fails loudly instead of pruning.
- A publication moves to a custom domain: it appears as a new locator; the old
  managed row is pruned only with `--prune`.
