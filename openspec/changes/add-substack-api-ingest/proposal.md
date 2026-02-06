# Change: Add Substack API ingestion source

## Why
Substack newsletters are a core source for this project, and relying only on RSS misses paid content and does not reflect a user's active subscriptions. Adding the unofficial Substack API enables subscription-aware ingestion and keeps source lists synchronized.

## What Changes
- Introduce a Substack API ingestion source using the `substack_api` Python library.
- Add a Substack subscription sync that updates `sources.d/substack.yaml` with enabled toggles for each subscription.
- Ingest the latest posts defined in `sources.d/substack.yaml` and deduplicate posts by canonical Substack URL across RSS, Gmail, and Substack sources.
- Document how to provide a Substack session cookie for paid subscriptions.

## Impact
- Affected specs: `specs/source-configuration/spec.md`
- Affected code: `src/ingestion/`, `src/config/`, `sources.d/`
