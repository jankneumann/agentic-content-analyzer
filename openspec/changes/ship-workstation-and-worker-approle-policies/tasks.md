# Tasks: Ship workstation and worker AppRole policies

> Change ID: `ship-workstation-and-worker-approle-policies`

## 1. Plan

- [x] 1.1 Read `scripts/bao_seed_newsletter.py` `seed_approle()`, `src/config/bao_secrets.py` (BAO_ROLE_ID/BAO_SECRET_ID, KV v2 mount `secret`, path `newsletter`), and ri-02's `BaoSink`
- [x] 1.2 Confirm from the hvac 2.4.0 source that `kv.v2.patch()` is a read followed by `create_or_update_secret(cas=...)`. Decide that the policies grant `patch` only and rely on the raw server-side PATCH (design D1)
- [x] 1.3 Move the spec delta to `openbao-secrets`

## 2. Implement

- [x] 2.1 Add the pure HCL builders `read_policy_hcl`, `worker_policy_hcl`, and `workstation_policy_hcl`. `newsletter-read` output must be byte-identical to the old string
- [x] 2.2 Add `_ensure_policy` (read back, write only on change, report created/updated/unchanged) and `_ensure_approle_auth`
- [x] 2.3 Add `seed_session_roles`: the `newsletter-session-writer` policy, the `newsletter-workstation` AppRole (15 min / 1 h token, 90 d secret-id), and the `newsletter-worker` policy attached to `newsletter-app`
- [x] 2.4 Give `seed_approle` an `extra_policies` parameter, and keep an already attached `newsletter-worker` on plain re-runs
- [x] 2.5 Add the `--with-session-roles` flag, which implies `--with-approle`, and print role_ids plus plain and wrapped secret-id commands. Never print a secret-id
- [x] 2.6 Replace the ineffective `# type: ignore[no-untyped-def]` on `client` parameters with `client: Any`

## 3. Test

- [x] 3.1 HCL builder tests: exact capabilities per path, no destructive or enumerating capability, no globs or metadata, custom mount and path, determinism
- [x] 3.2 An exact-path ACL evaluator over the seeded policies: the workstation is allowed `patch` and denied read, delete, update, create, and metadata; the worker is allowed read, patch, and shared read and denied delete, update, and metadata
- [x] 3.3 Idempotency: a second run rewrites no policy, reports `unchanged`, and leaves roles identical. A plain `--with-approle` re-run keeps `newsletter-worker`
- [x] 3.4 Dry run makes no client calls (`MagicMock().mock_calls == []`), and `main --dry-run --with-session-roles` never builds a client or prints a secret value
- [x] 3.5 The existing seeding tests pass unchanged

## 4. Document

- [x] 4.1 `docs/OPENBAO.md`: the role table, the capability table, the hvac `kv.v2.patch()` warning, the PATCH key-scope limitation, and the wrapped secret-id handover over the tailnet (linking `docs/TAILNET.md`)
