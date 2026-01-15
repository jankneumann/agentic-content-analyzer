# Design: Deployment Pipeline with GitHub Actions

## Context

The project needs automated CI/CD to ensure code quality and enable reliable deployments. GitHub Actions is the natural choice given the GitHub-hosted repository.

## Goals

1. Automated quality gates on every PR
2. Consistent Docker image builds
3. Safe database migrations
4. Environment-aware deployments

## Non-Goals

1. Kubernetes deployment (docker-compose first)
2. Multi-region deployment
3. Infrastructure as Code (Terraform)
4. GitOps (ArgoCD/Flux)

## Decisions

### Decision 1: Workflow Structure

**What**: Separate CI and CD workflows.

```
.github/workflows/
├── ci.yml          # Runs on PRs
└── deploy.yml      # Runs on main branch merge
```

**Why**: Clear separation of concerns, different triggers.

### Decision 2: CI Pipeline

**What**: Quality gates that must pass before merge.

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: uv run ruff check src/

  typecheck:
    runs-on: ubuntu-latest
    steps:
      - run: uv run mypy src/

  test:
    runs-on: ubuntu-latest
    services:
      postgres: ...
      redis: ...
    steps:
      - run: uv run pytest --cov
```

**Why**: Fast feedback, parallel execution.

### Decision 3: Docker Build Strategy

**What**: Multi-stage Dockerfile with layer caching.

```dockerfile
# Stage 1: Dependencies
FROM python:3.11-slim as deps
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Stage 2: Runtime
FROM python:3.11-slim as runtime
COPY --from=deps /app/.venv /app/.venv
COPY src/ /app/src/
```

**Why**: Small images, fast builds with layer caching.

### Decision 4: Image Registry

**What**: GitHub Container Registry (ghcr.io).

```yaml
- run: |
    docker build -t ghcr.io/${{ github.repository }}:${{ github.sha }} .
    docker push ghcr.io/${{ github.repository }}:${{ github.sha }}
```

**Why**: Native GitHub integration, free for public repos.

### Decision 5: Migration Strategy

**What**: Run migrations as separate CI step before deployment.

```yaml
migrate:
  runs-on: ubuntu-latest
  steps:
    - run: alembic upgrade head
  environment: staging
```

**Why**: Migrations can be rolled back independently, clear audit trail.

### Decision 6: Deployment Environments

**What**: GitHub Environments for staging and production.

```yaml
jobs:
  deploy-staging:
    environment: staging
    # Runs automatically

  deploy-production:
    environment: production
    needs: deploy-staging
    # Requires manual approval
```

**Why**: Built-in secrets management, approval gates, deployment history.

### Decision 7: Service Dependencies in CI

**What**: Use GitHub Actions service containers.

```yaml
services:
  postgres:
    image: postgres:15
    env:
      POSTGRES_PASSWORD: test
    ports:
      - 5432:5432

  redis:
    image: redis:7
    ports:
      - 6379:6379
```

**Why**: Real services for integration tests, no mocking overhead.

## File Structure

```
.github/
├── workflows/
│   ├── ci.yml              # PR quality gates
│   └── deploy.yml          # Deployment pipeline
├── dependabot.yml          # Dependency updates
└── CODEOWNERS              # Review requirements

Dockerfile                  # Multi-stage build
.dockerignore              # Build exclusions
docker-compose.yml         # Local development (updated)
docker-compose.prod.yml    # Production configuration
```

## Secrets Management

| Secret | Scope | Purpose |
|--------|-------|---------|
| `GHCR_TOKEN` | Repository | Push Docker images |
| `DATABASE_URL` | Environment | Database connection |
| `ANTHROPIC_API_KEY` | Environment | LLM API access |
| `OPIK_API_KEY` | Environment | Observability |

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Flaky tests | Retry mechanism, test isolation |
| Slow builds | Layer caching, parallel jobs |
| Migration failures | Dry-run first, manual approval |
| Secret exposure | Environment-scoped secrets |
