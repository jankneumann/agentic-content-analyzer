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

---

## Phase: Plan Iteration 1 (2026-04-01)

**Agent**: claude-opus-4-6 | **Session**: session_013Qjiy1Lvdb7uU48dfWZxyv

### Decisions
1. **Thread safety via threading.Lock** — FastAPI runs multi-threaded; concurrent `get_bao_secret()` calls must not trigger duplicate vault fetches. Lock on initial load, atomic dict reference swap on refresh.
2. **Shared key merge: newsletter wins** — When seeding `secret/shared/`, newsletter values overwrite conflicting keys but preserve all other project keys. Explicit merge-read-write pattern.
3. **Exception isolation in BaoSettingsSource** — `__call__()` and `get_field_value()` catch all exceptions and return empty dict. Settings instantiation must never fail due to vault issues.
4. **5 audit event types** — Defined canonical event names: `bao.secrets_loaded`, `bao.token_refreshed`, `bao.auth_failure`, `bao.connection_error`, `bao.token_manager_stopped`.
5. **Token manager shutdown via atexit** — `_BaoTokenManager.stop()` cancels pending timer; registered with `atexit` for clean process shutdown.

### Alternatives Considered
- **Per-request vault lookups**: rejected (D2) — adds latency with no benefit for secrets that change at most daily
- **Lazy per-key vault access**: rejected — 30 secrets is one HTTP call; lazy approach would be 30 calls

### Trade-offs
- Accepted threading.Lock complexity over lock-free design because correctness under concurrent load is critical
- Accepted 6 new spec scenarios (18-23) expanding scope slightly, because they cover real production failure modes

### Open Questions
- [ ] Should the seeding script auto-detect and seed shared keys by comparing with coordinator's secrets?
- [ ] What TTL should production AppRole tokens use? (Currently 1h default, 24h max)

### Context
Iteration 1 addressed 15 findings from parallel analysis: 6 high (thread safety, shared key semantics, exception isolation, graceful degradation log levels, task file conflict, token manager cleanup), 9 medium (special chars, empty vault, seeding failures, file table alignment, token atomicity, credential TTL, audit events, task vagueness, Impact section). Added 6 new spec scenarios (18-23), 3 new tasks (2.5, 2.6 renumbered, 3.3), fixed task dependencies for 1.6, added dependency graph summary, aligned design file table with actual deliverables.
