# Implementation Tasks

## Phase 1: ParadeDB Image Migration

- [ ] **T1.1** Update `docker-compose.yml`: change `pgvector/pgvector:pg17` to `paradedb/paradedb:<pinned-tag>`
- [ ] **T1.2** Update `.github/workflows/ci.yml`: change both service container images to `paradedb/paradedb:<pinned-tag>`
- [ ] **T1.3** Verify all Alembic migrations pass against ParadeDB image locally
- [ ] **T1.4** Verify pg_search BM25 index creation succeeds (currently conditional with IF EXISTS guard)
- [ ] **T1.5** Verify pgvector extension and vector operations work identically
- [ ] **T1.6** Verify pg_cron helper function creation in migrations
- [ ] **T1.7** Update `CLAUDE.md` gotchas: replace pgvector/pgvector:pg17 references with ParadeDB
- [ ] **T1.8** Update Railway Dockerfile if it references pgvector base image
- [ ] **T1.9** Write tests: run full CI test suite + contract tests against ParadeDB image

## Phase 2: CI Pipeline Improvements
> Depends on: Phase 1 (ParadeDB image in CI)

- [ ] **T2.1** Add mypy type-check job to `.github/workflows/ci.yml` (currently only ruff runs)
- [ ] **T2.2** Add coverage threshold gate: `pytest --cov --cov-fail-under=25`
- [ ] **T2.3** Add coverage report upload (codecov or GitHub summary)
- [ ] **T2.4** Verify all 4 CI jobs pass: lint, test, contract-test, validate-profiles

## Phase 3: CD Pipeline (Railway Deployment)
> Depends on: Phase 2 (CI improvements stable)

- [ ] **T3.1** Create `.github/workflows/deploy.yml` with Railway CLI
- [ ] **T3.2** Add staging deployment job (auto-trigger on main merge)
- [ ] **T3.3** Add staging migration step: `alembic upgrade head` against staging DB
- [ ] **T3.4** Add production deployment job with manual approval gate
- [ ] **T3.5** Add production migration step: `alembic upgrade head` against production DB
- [ ] **T3.6** Configure GitHub Environment: `staging` with deployment protection
- [ ] **T3.7** Configure GitHub Environment: `production` with required reviewers
- [ ] **T3.8** Add RAILWAY_TOKEN as repository secret
- [ ] **T3.9** Test staging deployment end-to-end

## Phase 4: Dependency & Governance
> Independent of Phases 1-3

- [ ] **T4.1** Create `.github/dependabot.yml` with pip, github-actions, docker ecosystems
- [ ] **T4.2** Configure weekly schedule, grouped updates, auto-merge for patch versions
- [ ] **T4.3** Create `.github/CODEOWNERS` mapping src/, web/, .github/ to appropriate reviewers
- [ ] **T4.4** Document branch protection settings to apply manually
- [ ] **T4.5** Enable branch protection on main: require CI pass + review approval

## Phase 5: Documentation
> Depends on: Phases 1-4

- [ ] **T5.1** Update `docs/SETUP.md` with deployment pipeline documentation
- [ ] **T5.2** Document ParadeDB migration in `docs/SETUP.md` PostgreSQL section
- [ ] **T5.3** Update `CLAUDE.md` deployment section and quick links
- [ ] **T5.4** Add CI status badge to README
