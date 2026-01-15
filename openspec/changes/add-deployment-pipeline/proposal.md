# Change: Add Deployment Pipeline with GitHub Actions

## Why

The project lacks automated CI/CD, requiring manual steps for:
- Running tests before merge
- Building and pushing Docker images
- Running database migrations
- Deploying to environments

By adding a GitHub Actions pipeline:

1. **Quality gates**: Automated tests, linting, type checking on every PR
2. **Consistent builds**: Docker images built and tagged automatically
3. **Safe deployments**: Migrations run in CI, staged rollouts
4. **Environment parity**: Same image runs in dev, staging, production

## What Changes

### CI Pipeline (Pull Requests)
- **NEW**: `.github/workflows/ci.yml`
  - Run pytest with coverage
  - Run ruff (linting)
  - Run mypy (type checking)
  - Build Docker image (verify it builds)

### CD Pipeline (Main Branch)
- **NEW**: `.github/workflows/deploy.yml`
  - Build and push to GitHub Container Registry (ghcr.io)
  - Tag with commit SHA and `latest`
  - Run Alembic migrations (staging, then production)
  - Deploy to target environment

### Docker Configuration
- **NEW**: `Dockerfile` (multi-stage, optimized)
- **NEW**: `.dockerignore`
- **MODIFIED**: `docker-compose.yml` for local dev parity

### Environment Configuration
- **NEW**: `.github/workflows/` workflow files
- **NEW**: Environment secrets configuration guide
- **MODIFIED**: Settings to support environment-specific config

## Pipeline Stages

```
PR Created/Updated
    │
    ▼
┌─────────────────────────────────────────────┐
│ CI: Lint + Type Check + Test                │
│ ├─ ruff check src/                          │
│ ├─ mypy src/                                │
│ ├─ pytest --cov                             │
│ └─ docker build (verify)                    │
└─────────────────────────────────────────────┘
    │
    ▼ (merge to main)
┌─────────────────────────────────────────────┐
│ CD: Build & Push                            │
│ ├─ docker build --tag ghcr.io/org/app:sha  │
│ └─ docker push                              │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ CD: Deploy Staging                          │
│ ├─ alembic upgrade head                     │
│ └─ deploy (docker-compose pull && up)       │
└─────────────────────────────────────────────┘
    │
    ▼ (manual approval)
┌─────────────────────────────────────────────┐
│ CD: Deploy Production                       │
│ ├─ alembic upgrade head                     │
│ └─ deploy                                   │
└─────────────────────────────────────────────┘
```

## Configuration

```yaml
# .github/workflows/ci.yml (simplified)
name: CI
on: [pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
      redis:
        image: redis:7
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync
      - run: uv run ruff check src/
      - run: uv run mypy src/
      - run: uv run pytest --cov
```

## Secrets Required

| Secret | Purpose |
|--------|---------|
| `GHCR_TOKEN` | Push to GitHub Container Registry |
| `DATABASE_URL_STAGING` | Staging database for migrations |
| `DATABASE_URL_PRODUCTION` | Production database |
| `ANTHROPIC_API_KEY` | For integration tests |

## Impact

- **New spec**: `deployment` - CI/CD pipeline
- **New files**:
  - `.github/workflows/ci.yml`
  - `.github/workflows/deploy.yml`
  - `Dockerfile`
  - `.dockerignore`
- **Modified**:
  - `docker-compose.yml` - Ensure parity with production
  - `docs/SETUP.md` - Add deployment documentation

## Related Proposals

- **add-observability**: Add Opik to docker-compose for local dev
- **add-test-infrastructure**: Tests must pass in CI
- **add-hoverfly-api-simulation**: Hoverfly runs in CI for integration tests

## Non-Goals

- Kubernetes deployment (docker-compose for now)
- Multi-region deployment
- Blue-green deployments (can add later)
- Infrastructure as Code (Terraform/Pulumi)
