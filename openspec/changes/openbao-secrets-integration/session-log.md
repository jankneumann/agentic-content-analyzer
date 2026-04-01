# Session Log: openbao-secrets-integration

---

## Phase: Plan (2026-04-01)

**Agent**: claude-opus-4-6 | **Session**: session_013Qjiy1Lvdb7uU48dfWZxyv

### Decisions
1. **Pydantic Settings Source approach** — Integrates OpenBao as a settings source in the existing Pydantic chain rather than a dedicated SecretsService or sidecar injection. Zero changes to consuming code.
2. **Separate seeding script** — `scripts/bao_seed_newsletter.py` independent from coordinator's `bao_seed.py` to avoid coupling deployment lifecycles.
3. **Below env vars in precedence** — env var > OpenBao > profile > .env > defaults. Matches coordinator's api_key_resolver.py pattern.
4. **Full production scope** — Includes AppRole creation, dynamic DB credentials, token refresh, shared keys, and audit logging.

### Alternatives Considered
- **Dedicated SecretsService (Approach B)**: rejected because it requires refactoring all secret consumers and duplicates resolution logic Pydantic already handles.
- **Environment Variable Injection/Sidecar (Approach C)**: rejected because it provides no runtime rotation, no app-level audit trail, and makes vault-injected vars indistinguishable from explicit env vars.
- **Extending coordinator's bao_seed.py**: rejected because the two projects have different seeding needs (agents.yaml vs shared-keys) and independent deployment cycles.

### Trade-offs
- Accepted startup-time bulk loading over lazy per-key lookups because 30 secrets is a single HTTP call
- Accepted background thread complexity for token refresh because the API server is long-lived
- Accepted hvac as an optional dependency to keep zero-vault local dev working

### Open Questions
- [ ] Should the seeding script auto-detect and seed shared keys by comparing with coordinator's secrets?
- [ ] What TTL should production AppRole tokens use? (Currently 1h default, 24h max)

### Context
Planned OpenBao integration for centralized secrets management across the newsletter aggregator and agent-coordinator projects. Selected Pydantic Settings Source approach (Approach A) for minimal blast radius and maximum compatibility with existing config architecture. User chose full production scope including dynamic DB credentials and audit logging.
