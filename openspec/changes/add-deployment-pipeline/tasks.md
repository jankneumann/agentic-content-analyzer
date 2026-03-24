# Implementation Tasks

## Phase 1: ParadeDB Image Migration

**Done when**: ParadeDB image used in CI and docker-compose, all migrations + contract tests pass.

- [ ] **T1.1** Update `docker-compose.yml`: change `pgvector/pgvector:pg17` to `paradedb/paradedb:<pinned-tag>` (T1.1 and T1.2 MUST use the same pinned version tag)
- [ ] **T1.2** Update `.github/workflows/ci.yml`: change both service container images to `paradedb/paradedb:<pinned-tag>` (same tag as T1.1)
- [ ] **T1.3** Verify all Alembic migrations pass: clean `alembic upgrade head` from empty DB against ParadeDB image locally
- [ ] **T1.4** Verify pg_search BM25 index creation succeeds: `CREATE EXTENSION pg_search` completes and existing BM25 search tests in `tests/api/test_search_api.py` pass
- [ ] **T1.5** Verify pgvector extension: `CREATE EXTENSION pgvector` completes and vector similarity queries return correct results
- [ ] **T1.6** Verify pg_cron helper function creation in `f1a2b3c4d5e6` migration succeeds
- [ ] **T1.7** Update `CLAUDE.md` gotchas: replace `pgvector/pgvector:pg17` references with ParadeDB image name and tag
- [ ] **T1.8** Check `.github/workflows/build-railway-postgres.yml` — if it compiles pg_search/pgvector from source, note that ParadeDB eliminates this need (may deprecate workflow)
- [ ] **T1.9** Run full CI test suite + contract tests against ParadeDB image in CI

## Phase 2: CI Pipeline Improvements
> Depends on: Phase 1 (ParadeDB image in CI)

**Done when**: Coverage report visible in PR, mypy job runs in CI, all jobs green.

- [ ] **T2.1** Add mypy type-check job to `.github/workflows/ci.yml` (currently only ruff runs in lint job)
- [ ] **T2.2** Add coverage threshold gate: `pytest --cov --cov-fail-under=25` with line coverage
- [ ] **T2.3** Add coverage summary to GitHub Actions job summary (not external service)
- [ ] **T2.4** Verify all CI jobs pass: lint (ruff check + format + alembic heads), mypy, test (pytest --cov), contract-test, validate-profiles

## Phase 3: CD Pipeline (Railway Deployment)
> Depends on: Phase 2 (CI improvements stable)

**Done when**: Merge to main auto-deploys to staging, production requires approval, health check confirms deployment.

- [ ] **T3.1** Create `.github/workflows/deploy.yml` with Railway CLI (`railway deploy`)
- [ ] **T3.2** Add staging deployment job: auto-trigger on push to main after CI passes
- [ ] **T3.3** Add staging migration step: `alembic upgrade head` against staging DB; verify `alembic_version` table matches latest revision
- [ ] **T3.4** Add staging health check: HTTP GET to staging `/health` returns 200 within 3 minutes
- [ ] **T3.5** Add production deployment job with GitHub Environment manual approval gate
- [ ] **T3.6** Add production migration step: `alembic upgrade head` against production DB
- [ ] **T3.7** Configure GitHub Environment: `staging` with deployment protection
- [ ] **T3.8** Configure GitHub Environment: `production` with required reviewers
- [ ] **T3.9** Add RAILWAY_TOKEN as repository secret
- [ ] **T3.10** Test staging deployment end-to-end on a real merge to main

## Phase 4: Dependency & Governance
> Independent of Phases 1-3 (can start in parallel)

**Done when**: Dependabot creates first update PR, CODEOWNERS routes reviews, branch protection active.

- [ ] **T4.1** Create `.github/dependabot.yml`: pip, github-actions, docker ecosystems; weekly schedule
- [ ] **T4.2** Configure Dependabot: grouped updates, `open-pull-requests-limit: 5`; security updates auto-labeled
- [ ] **T4.3** Create `.github/CODEOWNERS` mapping `src/` and `web/` to repository owner(s)
- [ ] **T4.4** Enable branch protection on main via GitHub Settings: require CI pass + at least 1 approval + dismiss stale reviews on push

## Phase 5: Documentation
> Depends on: Phases 1-3 (Phase 4 can still be in progress)

**Done when**: Deployment docs updated, ParadeDB documented, CI badge on README.

- [ ] **T5.1** Update `docs/SETUP.md` with CD pipeline and Railway deployment documentation
- [ ] **T5.2** Document ParadeDB migration in `docs/SETUP.md` PostgreSQL section (image name, extensions included, version pinning)
- [ ] **T5.3** Update `CLAUDE.md` deployment section, quick links, and PostgreSQL gotchas
- [ ] **T5.4** Add CI status badge to README
