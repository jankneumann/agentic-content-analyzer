# Design: Introduce live credential provider for rotating secrets

## Decisions

### D1. OpenBao cache first, then Settings

`Settings` ranks environment variables above OpenBao. The provider does the
opposite for the registered browser-session credentials: a process
environment variable is a boot-time snapshot, while the OpenBao cache is the
only store that can change under a running worker. An explicit per-call
override (`SubstackClient(session_cookie=...)`, the API/worker payload
override) still wins over both. Empty strings (what `${X:-}` yields in a
profile) count as absent.

### D2. Reads never touch the network

`get()` and `metadata()` read `bao_secrets.get_bao_secrets()`, a read-only view
of the module-level cache reference. After the one-time load that is a pointer
read, so it is safe on every request. The cache changes only by reference swap
from three places: the AppRole token manager (75% TTL), an explicit
`refresh()`, and `apply_local_write()`. A caller that reads the value and its
`_SAVED_AT` sibling from one view sees a consistent pair.

### D3. Bounded refresh lives in `bao_secrets`, not in the provider

`refresh_bao_secrets(min_interval_s)` holds `_bao_lock`, checks a monotonic
`_last_fetch_at` that every fetch attempt updates (boot load, token manager,
earlier refreshes, successful or not), and only then reads. The bound is
therefore process-wide, however many providers or adapters call it, and a
burst of callers that all just saw a 401 costs one read. It reuses the client
authenticated at load time; when the read fails it re-authenticates once with
`_authenticate_client()` (an AppRole token can expire between manager runs)
and retries once. If the boot load failed, it builds the client then. Failures
log the exception type only and keep the old cache.

### D4. Fetch-and-swap is serialized with local write-back

The token manager and `refresh_bao_secrets` now fetch and swap while holding
`_bao_lock`, and `apply_bao_local_write` copy-merge-swaps under the same lock.
A read that started before this process's PATCH therefore finishes and swaps
before the local write is merged on top, and any read that starts after it
sees the PATCHed value. Lockless readers keep the existing guarantee: they see
the old or the new dict, never a partially updated one.

### D5. `apply_local_write` takes the payload, stamps `saved_at`

`BaoSink.write()` returns key names only and computes `saved_at` internally.
`apply_local_write(values, saved_at=None)` stamps `<NAME>_SAVED_AT` for each
registered credential that the mapping does not already carry one for, using
the given time or now. ri-11 should pass the same timestamp it gave the sink
(or the sink's payload) so both copies agree to the second. Only registered
credentials are accepted, so a write-back cannot plant arbitrary keys in the
process cache.

### D6. `last_verified_at` stays in process memory

Writing `last_verified_at` to OpenBao on every successful run would turn each
ingestion into a secret-store write and need `patch` capability on the worker
role. `mark_verified(name)` instead records the time plus a SHA-256 digest of
the value in memory; `metadata()` reports it only while the current value
still has that digest, so a rotation clears it without bookkeeping. ri-06
(`aca auth status`) runs in a different process and will see `None` here: it
needs a durable source (for example the latest successful credential-gated
operation, or the readiness evidence ri-05 records). That is an explicit seam,
not a gap in this change.

### D7. Log names, never values

The provider and the new `bao_secrets` functions log credential names and
counts only. `Settings` declares the three fields `repr=False`, and
`is_secret_key()` now matches `*_COOKIE` and `X_CT0` (`X_AUTH_TOKEN` already
matched `*_TOKEN`), so profile display masks them. The Substack HTTP fallbacks
log `log_error_type(exc)` instead of the exception text.

## Non-goals

- Session-expiry detection and readiness (ri-05), `aca auth status` rows
  (ri-06), and the X adapter write-back caller (ri-11).
- Migrating Gmail/YouTube OAuth token reads; they are not browser sessions and
  still need a restart after `aca auth ... --to bao`.
- Changing the `Settings` source precedence.
