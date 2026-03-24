# Design: Deployment Pipeline & ParadeDB Migration

## Context

The project has a working CI pipeline but no CD automation. Deployments to Railway are manual. The PostgreSQL service container uses `pgvector/pgvector:pg17` which only bundles pgvector, but the codebase also depends on pg_search (BM25), pg_cron (scheduled jobs), and pgmq (job queue). These extensions currently require a custom-compiled Railway Docker image (~20min build time).

## Goals

1. Automated CD pipeline for Railway deployments via GitHub Actions
2. Coverage gates in CI to prevent regression
3. ParadeDB image migration for unified extension availability
4. Dependency management via Dependabot
5. Code ownership and branch protection

## Non-Goals

1. GHCR image registry (Railway builds from source — no separate image push needed)
2. Kubernetes or docker-compose-based production deployment
3. Multi-region or blue-green deployments

## Decisions

### Decision 1: Railway CLI for CD

**What**: Use `railway deploy` CLI commands in GitHub Actions instead of docker-compose or GHCR push.

**Why**: Railway is the production deployment target (see docs/MOBILE_DEPLOYMENT.md). Railway builds from source using the existing Dockerfile — no separate image push step needed. The Railway CLI supports environment targeting and integrates with GitHub Actions.

**Alternative considered**: GHCR push + Railway image pull. Rejected because Railway already builds from source and adding GHCR introduces a second artifact pipeline with no benefit.

### Decision 2: ParadeDB Image

**What**: Migrate from `pgvector/pgvector:pg17` to `paradedb/paradedb:latest` for all PostgreSQL service containers (docker-compose.yml, ci.yml).

**Why**: ParadeDB bundles pgvector, pg_search, pg_cron, pg_ivm, and pgmq pre-built. This eliminates:
- Custom Railway Docker image build (~20min compile for pg_search)
- Conditional `IF EXISTS` checks in migrations for pg_search availability
- Manual pgvector installation in CI (`postgresql-17-pgvector`)

**Risks**:
- ParadeDB image may be larger than pgvector-only image
- ParadeDB version pinning strategy differs from pgvector
- Must verify all existing extensions work identically

**Mitigation**: Pin to a specific ParadeDB tag (not `latest`), test all migrations in CI before merging.

### Decision 3: Staged Deployment with Manual Production Gate

**What**: Auto-deploy to staging on main merge, require manual approval for production.

**Why**: Staging deployment provides a verification environment. Manual production approval prevents accidental deployments and gives time for smoke testing.

**Implementation**: GitHub Environments with deployment protection rules.

### Decision 4: Coverage Threshold

**What**: Add pytest-cov threshold gate at 25% (current baseline).

**Why**: The codebase has 25% coverage. Setting the threshold at current level prevents regression while not blocking work. Can be raised incrementally.

**Alternative considered**: No threshold (current state). Rejected because coverage can silently decrease without a gate.

### Decision 5: Dependabot Configuration

**What**: Enable Dependabot for pip (Python), github-actions, and docker ecosystems.

**Why**: Automated security and version updates reduce maintenance burden and catch CVEs early.

**Configuration**: Weekly schedule, grouped updates, auto-merge for patch versions.

## File Structure

```
.github/
├── workflows/
│   ├── ci.yml              # PR quality gates [MODIFY]
│   ├── deploy.yml          # CD pipeline [NEW]
│   ├── build-railway-postgres.yml  # [EXISTS]
│   └── neon-pr.yml         # [EXISTS]
├── dependabot.yml          # Dependency updates [NEW]
└── CODEOWNERS              # Review requirements [NEW]

Dockerfile                  # Multi-stage build [EXISTS, may modify for ParadeDB]
.dockerignore               # Build exclusions [EXISTS]
docker-compose.yml          # Local development [MODIFY: ParadeDB image]
```

## Secrets Management

Secrets are managed in three scopes:
1. **Railway environment variables**: Production secrets (DATABASE_URL, ANTHROPIC_API_KEY, etc.)
2. **GitHub Repository secrets**: CI-only values (RAILWAY_TOKEN, test keys)
3. **GitHub Environment secrets**: Per-environment overrides (DATABASE_URL_STAGING, DATABASE_URL_PRODUCTION)

Profile-based secrets (`.secrets.yaml`) remain for local development. No duplication between GitHub and Railway — each scope serves its own purpose.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| ParadeDB image breaks existing migrations | Run full migration + contract test suite in CI before merge |
| Railway CLI auth token exposed | Store as GitHub repository secret, never in workflow logs |
| Flaky tests block deployment | Retry mechanism in CI, separate deploy from test jobs |
| Staging migration fails | Migrations run before deploy; failure blocks deployment |
| Coverage threshold too low to catch regressions | Start at 25%, raise 5% per quarter |
