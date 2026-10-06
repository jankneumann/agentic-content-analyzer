# Design: Ship workstation and worker AppRole policies

## Context

ri-02 shipped `BaoSink` (`src/cli/secret_sinks.py`), which writes with one HTTP
`PATCH` (`Content-Type: application/merge-patch+json`) to
`/v1/<mount>/data/<path>`. This item provides the ACLs that let that write, and the
worker's later `ct0` write-back, run with least privilege.

## Decisions

### D1. Grant `patch` only, and rely on the raw server-side PATCH, not hvac

hvac 2.4.0 (the locked version, `uv.lock`) implements `KvV2.patch()` on the client
side:

```python
current_secret_version = self.read_secret_version(path=path, mount_point=mount_point)
patched_secret = current_secret_version["data"]["data"]
patched_secret.update(secret)
return self.create_or_update_secret(path=path, cas=current_secret_version["data"]["metadata"]["version"], ...)
```

That path needs `read` and `update` on the data path. The KV v2 HTTP `PATCH`
endpoint is merged on the server and needs only the `patch` capability. It returns
404 when the secret does not exist and never creates it. `BaoSink` already sends
the raw PATCH (ri-02 design D1). The workstation policy therefore grants `patch`
and nothing else: no `read` on data and nothing under `metadata/`.

Consequence: any future writer (for example the worker's `ct0` write-back) MUST
reuse `BaoSink` or the same raw PATCH. `hvac.kv.v2.patch()` would get a 403 under
`newsletter-session-writer`. Under `newsletter-worker` it would also fail, because
that policy has no `update`. This is recorded in `docs/OPENBAO.md`.

### D2. Extend `newsletter-app` for the worker; don't add a separate worker role

The API and the worker run the same image with the same `BAO_ROLE_ID`, and the API's
session-capture endpoint (a later item) also patches. A separate
`newsletter-worker` policy is attached to the existing `newsletter-app` role, so
`newsletter-read` keeps its meaning and its spec scenario. `newsletter-worker`
repeats `read` on the data path so that it describes itself; the grants are a
union, so the repeat has no effect.

### D3. Idempotent re-runs and no silent downgrade

Each policy is read back (`sys/policy/<name>`) and written only when the stored HCL
differs. A plain `--with-approle` re-run reads the role's current `token_policies`
and keeps `newsletter-worker` if it is attached, with a stderr note. Without this,
a routine re-run would silently remove the worker's write-back right, and the
failure would only show up as a 403 at the next `ct0` rotation.

### D4. Workstation TTLs and secret-id handover

- The token TTL is 15 minutes, with a maximum of 1 hour. One `aca auth` run needs
  a single login and PATCH.
- The secret-id TTL is 90 days. That bounds a credential file left on a laptop.
  Re-issue is one command.
- Handover: on gx-10 the admin runs `bao write -wrap-ttl=5m -f .../secret-id`, and
  the workstation runs `bao unwrap` over the tailnet
  (`BAO_ADDR=https://gx-10.<tailnet>.ts.net:8200`, see `docs/TAILNET.md`).
- No `token_bound_cidrs` is set. `tailscale serve` proxies from loopback, so
  OpenBao sees `127.0.0.1` and a `100.64.0.0/10` binding would lock out the
  workstation.

## Residual risk

KV v2 ACLs are path-scoped. `allowed_parameters` only sees the top-level `data`
object, so a PATCH can set or null out any key in the secret. A leaked workstation
credential can therefore clobber, but never read, the LLM keys. D4's TTLs bound that
window. A per-key split (a separate `secret/newsletter-sessions` path) would remove
the risk, but it conflicts with the roadmap constraint that the token manager
re-fetches exactly one path, so it is out of scope.

## Non-goals

- No live OpenBao test in CI. The acceptance checks run against an in-memory fake
  hvac client plus an exact-path ACL evaluator over the shipped HCL. This container
  has no Docker daemon, and the brief requires network-free tests.
- No change to `src/config/bao_secrets.py`. On the workstation, the startup read is
  denied and logged as a non-fatal `bao.connection_error`, which is the existing
  "Optional, Non-Fatal Integration" behaviour.
