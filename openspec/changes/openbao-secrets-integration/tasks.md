# Tasks: OpenBao Secrets Management Integration

## Phase 1: Core Module and Tests

- [ ] 1.1 Write unit tests for `bao_secrets.py` — graceful degradation, caching, key mapping, thread safety, special chars
  **Spec scenarios**: openbao-secrets.1 (unconfigured), openbao-secrets.7 (connection failure), openbao-secrets.8 (hvac missing), openbao-secrets.16 (cache isolation), openbao-secrets.17 (key mapping), openbao-secrets.18 (thread safety), openbao-secrets.19 (partial response), openbao-secrets.20 (special chars), openbao-secrets.21 (empty vault)
  **Design decisions**: D4 (graceful degradation as default)
  **Dependencies**: None

- [ ] 1.2 Write unit tests for OpenBao authentication — AppRole, token auth, exception isolation
  **Spec scenarios**: openbao-secrets.4 (AppRole auth), openbao-secrets.5 (token auth fallback), openbao-secrets.23 (exception isolation)
  **Design decisions**: D1 (settings source over service)
  **Dependencies**: None

- [ ] 1.3 Write unit tests for secret resolution with OpenBao tier — env override, vault resolution, tier ordering, graceful fallback
  **Spec scenarios**: openbao-secrets.2 (resolution from OpenBao), openbao-secrets.3 (env var override), openbao-secrets.19 (partial response falls through)
  **Design decisions**: D1 (settings source), D4 (graceful degradation)
  **Dependencies**: None

- [ ] 1.4 Create `src/config/bao_secrets.py` — core module with `_load_bao_secrets()`, `get_bao_secret()`, `BaoSettingsSource`, `clear_bao_cache()`, threading lock for concurrent access, exception isolation in `__call__()`
  **Spec scenarios**: openbao-secrets.1, .2, .4, .5, .7, .8, .17, .18, .19, .20, .21, .23
  **Design decisions**: D1, D2, D4
  **Dependencies**: 1.1, 1.2

- [ ] 1.5 Update `src/config/secrets.py` — add OpenBao tier to `resolve_secret()` between env vars and .secrets.yaml
  **Spec scenarios**: openbao-secrets.2, .3
  **Dependencies**: 1.3, 1.4

- [ ] 1.6 Update `src/config/settings.py` — wire `BaoSettingsSource` into `settings_customise_sources()` as priority 3
  **Spec scenarios**: openbao-secrets.15 (settings chain integration)
  **Design decisions**: D1
  **Dependencies**: 1.4, 1.5
  **Note**: Modifies same file as 1.5 (`settings.py` imports from `bao_secrets.py`, `secrets.py` imports from `bao_secrets.py`). Must run after 1.5 to avoid merge conflicts.

## Phase 2: Token Lifecycle and Audit

- [ ] 2.1 Write unit tests for token refresh — timer scheduling, atomic cache update, re-schedule after refresh
  **Spec scenarios**: openbao-secrets.6 (token refresh)
  **Design decisions**: D2 (process-level caching with background refresh)
  **Dependencies**: 1.4

- [ ] 2.2 Write unit tests for token manager shutdown — cancel timer, log event, no further operations
  **Spec scenarios**: openbao-secrets.22 (token manager shutdown)
  **Design decisions**: D2
  **Dependencies**: 1.4

- [ ] 2.3 Write unit tests for audit logging — all 5 event types, correct log levels, no secret values in output
  **Spec scenarios**: openbao-secrets.14 (audit logging)
  **Design decisions**: D5 (structured audit logging)
  **Dependencies**: 1.4

- [ ] 2.4 Implement `_BaoTokenManager` — background token refresh at 75% TTL with atomic cache update and re-scheduling
  **Spec scenarios**: openbao-secrets.6
  **Design decisions**: D2
  **Dependencies**: 2.1, 2.2, 1.4

- [ ] 2.5 Implement `_BaoTokenManager.stop()` — cancel timer, integrate with `atexit` for process shutdown
  **Spec scenarios**: openbao-secrets.22
  **Design decisions**: D2
  **Dependencies**: 2.2, 2.4

- [ ] 2.6 Add structured audit logging to `bao_secrets.py` — 5 event types: secrets_loaded, token_refreshed, auth_failure, connection_error, token_manager_stopped
  **Spec scenarios**: openbao-secrets.14
  **Design decisions**: D5
  **Dependencies**: 2.3, 1.4

## Phase 3: Seeding Script

- [ ] 3.1 Write tests for seeding script — secret seeding, shared keys merge semantics, dry run
  **Spec scenarios**: openbao-secrets.9 (seeding), openbao-secrets.10 (shared keys — newsletter wins on conflict, other project keys preserved), openbao-secrets.13 (dry run)
  **Design decisions**: D3 (separate seeding script)
  **Dependencies**: None

- [ ] 3.2 Write tests for AppRole creation and DB engine setup
  **Spec scenarios**: openbao-secrets.11 (AppRole creation), openbao-secrets.12 (dynamic DB creds — TTL 1h, max 24h)
  **Dependencies**: None

- [ ] 3.3 Write tests for seeding script failure cases — vault write permission denied, policy creation failure, network timeout
  **Spec scenarios**: openbao-secrets.9 (error paths)
  **Dependencies**: None

- [ ] 3.4 Create `scripts/bao_seed_newsletter.py` — seed secrets, shared keys (merge semantics), AppRole, DB engine, dry run
  **Spec scenarios**: openbao-secrets.9, .10, .11, .12, .13
  **Design decisions**: D3
  **Dependencies**: 3.1, 3.2, 3.3

## Phase 4: Infrastructure and Profile

Phase 4 tasks create new files with no dependencies on Phase 1. They can run in parallel with any other phase.

- [ ] 4.1 Create `docker-compose.openbao.yml` — OpenBao dev server overlay (dev mode, in-memory, root token `dev-root-token`)
  **Dependencies**: None

- [ ] 4.2 Create `profiles/local-openbao.yaml` — extends `local` profile for OpenBao dev workflow
  **Dependencies**: None

- [ ] 4.3 Add `vault` optional dependency group to `pyproject.toml` — `hvac>=2.1.0`
  **Dependencies**: None

## Phase 5: Integration Tests

- [ ] 5.1 Write integration tests for full Settings chain with mocked OpenBao — verify 6-source priority order
  **Spec scenarios**: openbao-secrets.15 (settings chain), openbao-secrets.3 (env override), openbao-secrets.1 (graceful degradation), openbao-secrets.23 (exception isolation)
  **Design decisions**: D1 (settings source), D4 (graceful degradation)
  **Dependencies**: 1.4, 1.5, 1.6

- [ ] 5.2 Write integration test for `resolve_secret()` with OpenBao tier — full resolution chain end-to-end
  **Spec scenarios**: openbao-secrets.2, .3, .16, .19
  **Dependencies**: 1.5

## Phase 6: Documentation

- [ ] 6.1 Create `docs/OPENBAO.md` — architecture diagram, quick-start, production deployment (AppRole + DB engine), configuration reference, audit event reference
  **Dependencies**: 1.4, 3.4, 4.1

- [ ] 6.2 Update `CLAUDE.md` — add OPENBAO.md to documentation index
  **Dependencies**: 6.1

- [ ] 6.3 Update `.secrets.yaml.example` — add `BAO_*` environment variable examples in comments
  **Dependencies**: 1.4

## Dependency Graph Summary

```
Independent (max parallel width = 7):
  1.1, 1.2, 1.3, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3

Sequential chains:
  1.1 + 1.2 → 1.4 → 1.5 → 1.6
  1.3 → 1.5
  1.4 → 2.1, 2.2, 2.3 → 2.4 → 2.5
  2.3 → 2.6
  3.1 + 3.2 + 3.3 → 3.4
  1.4 + 1.5 + 1.6 → 5.1
  1.5 → 5.2
  1.4 + 3.4 + 4.1 → 6.1 → 6.2

File overlap requiring serialization:
  1.5 (secrets.py) → 1.6 (settings.py): no overlap but 1.6 depends on 1.5
  2.4, 2.5, 2.6 all modify bao_secrets.py: serialize as 2.4 → 2.5, then 2.6
```
