---

## Phase: Plan (2026-04-11)

**Agent**: claude-opus-4-6 | **Session**: plan-feature

### Decisions
1. **Config-First approach** — Switch Langfuse defaults across all profiles first (low risk), then deploy ParadeDB GHCR image to Railway. Langfuse tracing monitors the database migration.
2. **Self-hosted local, Cloud for Railway** — Local development uses self-hosted Langfuse via docker-compose.langfuse.yml. Railway/staging use Langfuse Cloud to avoid running full Langfuse infrastructure on Railway.
3. **GHCR pre-built image** — Publish existing railway/postgres/Dockerfile to ghcr.io rather than building on Railway (avoids build timeouts, faster deploys).
4. **Keep Braintrust as option** — Retain braintrust.py provider code; users override via OBSERVABILITY_PROVIDER=braintrust. No deprecation.
5. **All profiles updated** — base.yaml, local.yaml, railway.yaml, railway-neon.yaml, staging.yaml all switch to langfuse. CI and specialized profiles unchanged.

### Alternatives Considered
- Infrastructure-First (ParadeDB before Langfuse): rejected because preferred observability should be in place to monitor the database migration
- Parallel Implementation: rejected due to shared profile files creating merge conflict risk
- Langfuse Cloud for local dev: rejected because it breaks offline development workflow
- Self-hosted Langfuse on Railway: rejected as too resource-heavy for single-project deployment
- Remove Braintrust entirely: rejected as unnecessary breakage with no benefit

### Trade-offs
- Accepted additional Docker services for local dev (Langfuse stack) over zero-overhead noop default, because observability-by-default catches issues earlier
- Accepted graceful degradation (warn + drop traces) over hard failure when credentials missing, because local dev shouldn't require Langfuse to be running
- Accepted keeping redundant local-langfuse.yaml over removing it, because users may have PROFILE=local-langfuse in existing scripts

### Open Questions
- [ ] Should make dev auto-start the Langfuse stack, or keep it as a separate make langfuse-up step?
- [ ] Should CI/CD automation be added for GHCR image publish, or keep it manual for now?

### Context
Planning session to close two infrastructure parity gaps: (1) vanilla Railway PostgreSQL lacking ParadeDB extensions available in local dev, and (2) observability defaulting to noop/braintrust instead of the team's actual platform (Langfuse). Both changes are configuration-level — all code infrastructure is already implemented. The plan uses a config-first approach to get observability in place before the database infrastructure change.
