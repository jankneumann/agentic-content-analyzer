# Design: Add secret sink abstraction to the auth CLI

## Decisions

### D1. OpenBao writes use a raw server-side PATCH, not `hvac`'s `kv.v2.patch()`

hvac 2.x implements `KvV2.patch()` on the client: `read_secret_version()` and then
`create_or_update_secret(cas=version)`. That:

- calls `create_or_update_secret`, which this roadmap forbids outside the seed script;
- needs `read` capability, which the ri-03 workstation AppRole deliberately lacks.

`BaoSink` instead calls
`client.adapter.request("PATCH", "/v1/<mount>/data/<path>", json={"data": {...}},
headers={"Content-Type": "application/merge-patch+json"})`. The server applies the
JSON merge patch atomically, needs only the `patch` capability, and leaves every
other key untouched.

### D2. Missing path fails; the sink never creates it

A KV v2 PATCH on a secret that does not exist returns 404. The sink maps that to
"path does not exist; seed it with `scripts/bao_seed_newsletter.py`". Creating the
path would need a full write, which could hide a wrong `BAO_SECRET_PATH` (the worker
would never read the new path) and would need `create` capability. No
"allow create" flag is offered. Seeding stays the job of the seed script.

### D3. `saved_at` is a sibling key

For each written key `K` the same PATCH writes `K_SAVED_AT` as an ISO-8601 UTC
timestamp. KV v2 `custom_metadata` is per secret, not per key, and reading it needs
separate capabilities. A sibling string key flows through the existing
`_fetch_secrets()` / token-manager cache unchanged, so ri-04 can read it with
`saved_at_key(K)`. Settings ignore unknown keys (`extra="ignore"`), so the siblings
cannot break settings loading. Only the OpenBao sink records `saved_at`: the
Railway sink must behave exactly like `--deploy`, and `.secrets.yaml` is a local
fallback.

### D4. One `write()` is one atomic operation

`write(mapping)` is a single PATCH (OpenBao), a single `railway variables` call
(Railway, so one redeploy never sees a torn `X_AUTH_TOKEN`/`X_CT0` pair), or a single
atomic file replace (secrets file). `aca auth` keeps two separate writes (token, then
the optional client JSON), so `--to railway` issues the same `railway variables
--set` argv lists that `--deploy` did.

### D5. Secrets-file edits are line-based and then verified

The sink replaces the top-level `KEY:` entry, including indented continuation lines
of block scalars, with a `yaml.safe_dump` rendering, or appends it. It then re-parses
the result and requires it to equal `{**old, **new}`. If the in-place edit cannot be
proven lossless (flow mappings, anchors), it falls back to a full re-dump that keeps
every key but drops comments, and warns on stderr. The file is written through a
same-directory temp file created with mode 0600 and `os.replace`d. A malformed file
is refused, never overwritten.

### D6. Fail fast before the browser

`SecretSink.check()` runs before the OAuth flow. It checks `BAO_ADDR`, credentials,
the hvac install and authentication for OpenBao; the `railway` CLI and the target
notice for Railway; and parseability for the secrets file. A misconfiguration then
costs no browser consent round-trip.

## Non-goals

- AppRole policies (ri-03), the credential provider (ri-04), and browser-session
  capture (ri-06).
- Changing `aca auth status` or `aca deploy sync-secrets`.
