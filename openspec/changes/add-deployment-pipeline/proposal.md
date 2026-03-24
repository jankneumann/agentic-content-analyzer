# Change: Complete Deployment Pipeline & Migrate to ParadeDB

## Why

The project has a working CI pipeline (lint, test, contract-test, profile-validation) but lacks:
- **CD pipeline**: No automated deployment after merge — Railway deployments are triggered manually
- **Dependency management**: No Dependabot for automated security/version updates
- **Code ownership**: No CODEOWNERS for review routing
- **Branch protection**: CI must pass but no formal branch protection rules configured
- **Coverage gates**: Tests run but no coverage threshold enforced
- **PostgreSQL image consolidation**: Dev/CI use `pgvector/pgvector:pg17` which only includes pgvector. The codebase also uses pg_search (BM25 full-text), pg_cron (scheduled jobs), and pgmq. These require either a custom-built Railway Docker image (~20min compile) or manual installation. ParadeDB bundles all essential extensions pre-built.

## What Changes

### CD Pipeline (Main Branch)
- **NEW**: `.github/workflows/deploy.yml`
  - Trigger Railway deployment via Railway CLI
  - Run Alembic migrations against staging, then production
  - Manual approval gate for production deployment
  - Tag releases with commit SHA

### CI Pipeline Improvements
- **MODIFIED**: `.github/workflows/ci.yml`
  - Add coverage reporting with threshold gate
  - Migrate service container from `pgvector/pgvector:pg17` to `paradedb/paradedb:latest`
  - Add mypy job (currently missing from CI — only ruff runs)

### PostgreSQL Image Migration
- **MODIFIED**: `docker-compose.yml` — switch from `pgvector/pgvector:pg17` to `paradedb/paradedb:latest`
- **MODIFIED**: `.github/workflows/ci.yml` — same image switch for service containers
- **MODIFIED**: `Dockerfile` — update Railway production image base (if applicable)
- **IMPACT**: ParadeDB includes pgvector, pg_search, pg_cron, pgmq, pg_ivm pre-built — eliminates custom Railway image build and manual extension installation

### Dependency & Governance
- **NEW**: `.github/dependabot.yml` — Python, GitHub Actions, Docker base image updates
- **NEW**: `.github/CODEOWNERS` — review routing for src/, web/, .github/
- **MODIFIED**: GitHub branch protection settings (documented, applied manually)

### Documentation
- **MODIFIED**: `docs/SETUP.md` — deployment documentation
- **MODIFIED**: `CLAUDE.md` — update PostgreSQL image references and gotchas

## Pipeline Stages

```
PR Created/Updated
    │
    ▼
┌─────────────────────────────────────────────┐
│ CI: Lint + Type Check + Test  [EXISTS]       │
│ ├─ ruff check + format check                │
│ ├─ mypy src/  [ADD]                         │
│ ├─ Alembic single-head check                │
│ ├─ pytest --cov (threshold gate) [IMPROVE]  │
│ ├─ Contract/fuzz tests (Schemathesis)       │
│ └─ Profile validation + secrets scan        │
└─────────────────────────────────────────────┘
    │
    ▼ (merge to main)
┌─────────────────────────────────────────────┐
│ CD: Deploy Staging  [NEW]                   │
│ ├─ railway deploy --environment staging     │
│ └─ alembic upgrade head (staging DB)        │
└─────────────────────────────────────────────┘
    │
    ▼ (manual approval)
┌─────────────────────────────────────────────┐
│ CD: Deploy Production  [NEW]                │
│ ├─ alembic upgrade head (production DB)     │
│ └─ railway deploy --environment production  │
└─────────────────────────────────────────────┘
```

## Secrets Required

| Secret | Scope | Purpose |
|--------|-------|---------|
| `RAILWAY_TOKEN` | Repository | Railway CLI authentication for deployments |
| `DATABASE_URL_STAGING` | Environment: staging | Staging database for migrations |
| `DATABASE_URL_PRODUCTION` | Environment: production | Production database for migrations |
| `ANTHROPIC_API_KEY` | Repository | For CI integration tests |
| `ADMIN_API_KEY` | Repository | For CI contract tests |
| `APP_SECRET_KEY` | Repository | For CI contract tests |

## Impact

- **Modified spec**: `deployment` — CI/CD pipeline (existing spec updated)
- **New files**:
  - `.github/workflows/deploy.yml`
  - `.github/dependabot.yml`
  - `.github/CODEOWNERS`
- **Modified**:
  - `.github/workflows/ci.yml` — coverage gate, mypy, ParadeDB image
  - `docker-compose.yml` — ParadeDB image migration
  - `Dockerfile` — ParadeDB base image (if applicable)
  - `docs/SETUP.md` — deployment documentation
  - `CLAUDE.md` — updated PostgreSQL image gotchas

## Related Proposals

- **harden-public-repo-security**: Branch protection, secrets scanning (complementary)

## Non-Goals

- Kubernetes deployment (Railway handles orchestration)
- Multi-region deployment
- Blue-green deployments
- Infrastructure as Code (Terraform/Pulumi)
- GHCR image registry (Railway builds from source)
