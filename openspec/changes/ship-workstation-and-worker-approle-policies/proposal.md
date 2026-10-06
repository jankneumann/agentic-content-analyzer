# Ship workstation and worker AppRole policies

> Parent roadmap: `x-bookmarks-session-capture` (item `ri-03`)
> Change ID: `ship-workstation-and-worker-approle-policies`
> Effort: S · Priority: 4 · Depends on: none (pairs with ri-02's `BaoSink`)

## Why

Two writers will put credentials into the same KV v2 secret that the app reads
(`secret/newsletter`):

- the operator's **workstation** runs `aca auth ... --to bao` (ri-02 `BaoSink`) to push
  OAuth tokens and browser-session cookies, and
- the **worker** (and the API session endpoint) writes back a rotated X `ct0` cookie.

The only role the seed script creates today is `newsletter-app`, with the
read-only `newsletter-read` policy. Today the workstation would need the root/admin
token, which can read every LLM key, and the worker cannot write at all. Both
writers use the server-side KV v2 PATCH. That needs only the `patch` capability,
so each role can get exactly what it needs and nothing more.

## What Changes

- `scripts/bao_seed_newsletter.py` gains `--with-session-roles`, which implies
  `--with-approle` and does the following:
  - writes policy `newsletter-session-writer`, which grants only `patch` on
    `<mount>/data/<path>`, and creates AppRole `newsletter-workstation` with it.
    Token TTL is 15 min (max 1 h) and the secret-id TTL is 90 days.
  - writes policy `newsletter-worker`, which grants `read` and `patch` on the same
    path, and attaches it to the existing `newsletter-app` role next to
    `newsletter-read`.
  - prints each role_id, the secret-id command, and a response-wrapped variant
    for handing the workstation its secret-id over the tailnet. It never mints
    or prints a secret-id.
- Pure HCL builders (`read_policy_hcl`, `worker_policy_hcl`,
  `workstation_policy_hcl`) replace the inline policy string, so the policies can
  be unit-tested. `newsletter-read` renders byte-identically to before.
- Policies are compared with what is stored and only written when they differ
  (`created` / `updated` / `unchanged`). A later plain `--with-approle` run keeps
  `newsletter-worker` on `newsletter-app` instead of silently revoking it.
- No policy grants `create`, `update`, `delete`, `destroy`, `list`, or any
  `metadata`/`delete`/`destroy` path.
- `docs/OPENBAO.md` gains a "Session-Credential Roles" section: the role and
  capability tables, why hvac's `kv.v2.patch()` must not be used with these
  roles, the key-scope limitation of PATCH, and the wrapped secret-id handover
  over the tailnet (it links to `docs/TAILNET.md`).

## Impact

- Affected spec: `openbao-secrets` (ADDED "Session-Credential AppRole Policies").
- Affected code: `scripts/bao_seed_newsletter.py`,
  `tests/test_config/test_bao_seeding.py`, `docs/OPENBAO.md`.
- Behaviour of `--with-approle` alone is unchanged, except that an already attached
  `newsletter-worker` policy is preserved and the policy line now reports its
  status. The client parameter annotations moved from ineffective
  `# type: ignore` comments to `Any`, so mypy is clean on the script.
- Operators must run `--with-session-roles` once on gx-10 before `aca auth ... --to bao`
  can work with an AppRole. Until then, the sink works only with an admin `BAO_TOKEN`.
