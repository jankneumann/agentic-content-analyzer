## ADDED Requirements

### Requirement: Session-Credential AppRole Policies

The seed script SHALL provide a `--with-session-roles` option that creates two
least-privilege policies on the KV v2 data path `<BAO_MOUNT_PATH>/data/<BAO_SECRET_PATH>`
(default `secret/data/newsletter`):

- `newsletter-session-writer`, granting only the `patch` capability. It SHALL be
  bound to a `newsletter-workstation` AppRole whose token TTL is at most 15 minutes
  and whose token max TTL is at most 1 hour.
- `newsletter-worker`, granting `read` and `patch`. It SHALL be attached to the
  `newsletter-app` AppRole in addition to `newsletter-read`.

Neither policy SHALL grant `create`, `update`, `delete`, `destroy`, `list`, or `sudo`,
or any capability on the `metadata/`, `delete/`, or `destroy/` paths, or use a glob.
The policy HCL SHALL be produced by pure functions. The script SHALL print each
role_id and the command that mints a secret_id, including a response-wrapped
variant. It SHALL NOT generate or print a secret_id or any secret value.

#### Scenario: Workstation role may patch but not read or delete
- **WHEN** `bao_seed_newsletter.py --with-session-roles` has run
- **THEN** the policies bound to `newsletter-workstation` allow `patch` on `secret/data/newsletter`
- **AND** deny `read`, `create`, `update`, and `delete` on it
- **AND** deny every operation on `secret/metadata/newsletter`, `secret/delete/newsletter`, `secret/destroy/newsletter`, and `secret/data/shared`

#### Scenario: Worker role may read and patch but not delete
- **WHEN** `bao_seed_newsletter.py --with-session-roles` has run
- **THEN** `newsletter-app` carries `newsletter-read` and `newsletter-worker`
- **AND** its policies allow `read` and `patch` on `secret/data/newsletter` and `read` on `secret/data/shared`
- **AND** deny `update`, `delete`, and every operation on the `metadata/`, `delete/`, and `destroy/` paths

#### Scenario: Re-running the seed script leaves the policies unchanged
- **WHEN** `--with-session-roles` runs a second time against the same OpenBao
- **THEN** no policy is rewritten, and each one is reported as `unchanged`
- **AND** both AppRoles keep identical settings

#### Scenario: A plain AppRole re-run keeps the worker's patch right
- **WHEN** `--with-approle` runs without `--with-session-roles` after the session roles exist
- **THEN** `newsletter-app` still carries `newsletter-worker`

#### Scenario: Dry run makes no OpenBao calls
- **WHEN** `bao_seed_newsletter.py --dry-run --with-session-roles` runs
- **THEN** it prints both policies' HCL and the AppRoles it would create
- **AND** it makes no call to an OpenBao client and prints no secret value
