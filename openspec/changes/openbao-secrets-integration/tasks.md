# Tasks: OpenBao Secrets Management Integration

## Phase 1: Core Module and Tests

- [ ] 1.1 Write unit tests for `bao_secrets.py` — graceful degradation, caching, key mapping
  **Spec scenarios**: openbao-secrets.1 (graceful degradation), openbao-secrets.7 (connection failure), openbao-secrets.8 (hvac not installed), openbao-secrets.16 (cache isolation), openbao-secrets.17 (key mapping)
  **Design decisions**: D4 (graceful degradation as default)
  **Dependencies**: None

- [ ] 1.2 Write unit tests for OpenBao authentication — AppRole and token auth
  **Spec scenarios**: openbao-secrets.4 (AppRole auth), openbao-secrets.5 (token auth fallback)
  **Design decisions**: D1 (settings source over service)
  **Dependencies**: None

- [ ] 1.3 Write unit tests for secret resolution with OpenBao tier
  **Spec scenarios**: openbao-secrets.2 (resolution from OpenBao), openbao-secrets.3 (env var override)
  **Design decisions**: D1 (settings source), D4 (graceful degradation)
  **Dependencies**: None

- [ ] 1.4 Create `src/config/bao_secrets.py` — core module with `_load_bao_secrets()`, `get_bao_secret()`, `BaoSettingsSource`, `clear_bao_cache()`
  **Spec scenarios**: openbao-secrets.1, .2, .4, .5, .7, .8, .17
  **Design decisions**: D1, D2, D4
  **Dependencies**: 1.1, 1.2

- [ ] 1.5 Update `src/config/secrets.py` — add OpenBao tier to `resolve_secret()`
  **Spec scenarios**: openbao-secrets.2, .3
  **Dependencies**: 1.3, 1.4

- [ ] 1.6 Update `src/config/settings.py` — wire `BaoSettingsSource` into `settings_customise_sources()`
  **Spec scenarios**: openbao-secrets.15 (settings chain integration)
  **Design decisions**: D1
  **Dependencies**: 1.4

## Phase 2: Token Lifecycle and Audit

- [ ] 2.1 Write unit tests for token refresh — timer scheduling, atomic cache update, stop on shutdown
  **Spec scenarios**: openbao-secrets.6 (token refresh)
  **Design decisions**: D2 (process-level caching with background refresh)
  **Dependencies**: 1.4

- [ ] 2.2 Write unit tests for audit logging — structured events, no secret values in logs
  **Spec scenarios**: openbao-secrets.14 (audit logging)
  **Design decisions**: D5 (structured audit logging)
  **Dependencies**: 1.4

- [ ] 2.3 Implement `_BaoTokenManager` — background token refresh at 75% TTL
  **Spec scenarios**: openbao-secrets.6
  **Design decisions**: D2
  **Dependencies**: 2.1, 1.4

- [ ] 2.4 Add structured audit logging to `bao_secrets.py` — load, refresh, failure events
  **Spec scenarios**: openbao-secrets.14
  **Design decisions**: D5
  **Dependencies**: 2.2, 1.4

## Phase 3: Seeding Script

- [ ] 3.1 Write tests for seeding script — secret seeding, shared keys, dry run
  **Spec scenarios**: openbao-secrets.9 (seeding), openbao-secrets.10 (shared keys), openbao-secrets.13 (dry run)
  **Design decisions**: D3 (separate seeding script)
  **Dependencies**: None

- [ ] 3.2 Write tests for AppRole creation and DB engine setup
  **Spec scenarios**: openbao-secrets.11 (AppRole creation), openbao-secrets.12 (dynamic DB creds)
  **Dependencies**: None

- [ ] 3.3 Create `scripts/bao_seed_newsletter.py` — seed secrets, shared keys, AppRole, DB engine
  **Spec scenarios**: openbao-secrets.9, .10, .11, .12, .13
  **Design decisions**: D3
  **Dependencies**: 3.1, 3.2

## Phase 4: Infrastructure and Profile

- [ ] 4.1 Create `docker-compose.openbao.yml` — OpenBao dev server overlay (dev mode, in-memory)
  **Dependencies**: None

- [ ] 4.2 Create `profiles/local-openbao.yaml` — extends `local` profile for OpenBao dev workflow
  **Dependencies**: None

- [ ] 4.3 Add `vault` optional dependency group to `pyproject.toml` — `hvac>=2.1.0`
  **Dependencies**: None

## Phase 5: Settings Integration Tests

- [ ] 5.1 Write integration tests for full Settings chain with mocked OpenBao
  **Spec scenarios**: openbao-secrets.15 (settings chain), openbao-secrets.3 (env override), openbao-secrets.1 (graceful degradation)
  **Design decisions**: D1 (settings source), D4 (graceful degradation)
  **Dependencies**: 1.4, 1.5, 1.6

- [ ] 5.2 Write integration test for `resolve_secret()` with OpenBao tier
  **Spec scenarios**: openbao-secrets.2, .3, .16
  **Dependencies**: 1.5

## Phase 6: Documentation

- [ ] 6.1 Create `docs/OPENBAO.md` — architecture, quick-start, production deployment, configuration reference
  **Dependencies**: 1.4, 3.3, 4.1

- [ ] 6.2 Update `CLAUDE.md` — add OPENBAO.md to documentation index
  **Dependencies**: 6.1

- [ ] 6.3 Update `.secrets.yaml.example` — add `BAO_*` environment variable examples in comments
  **Dependencies**: 1.4
