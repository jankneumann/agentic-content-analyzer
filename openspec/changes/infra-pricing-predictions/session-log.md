---

## Phase: Plan (2026-04-04)

**Agent**: claude-opus-4-6 | **Session**: sequential tier

### Decisions
1. **Separate YAML config (D1)** — Infrastructure pricing lives in `settings/pricing.yaml`, not merged into `models.yaml`, because plan-tier pricing structure is fundamentally different from per-token LLM pricing.
2. **Reuse `fetch_pricing_page` (D2)** — The HTTP fetching pipeline (httpx + trafilatura) is domain-agnostic and already tested. Importing it avoids duplication.
3. **Independent refresh triggers (D3)** — Infrastructure pricing changes less frequently than LLM pricing; a unified refresh would create unnecessary coupling.
4. **Cost prediction only for Resend (scope)** — No Resend delivery integration. Email delivery continues via Gmail API; Resend is modeled only for cost comparison.
5. **Document as-is + refinements (scope)** — Spec the existing implementation but also capture ConfigRegistry integration, test coverage, and input validation as Phase 2 tasks.

### Alternatives Considered
- **Extend ModelConfig**: Rejected because it would turn ModelConfig into a god object and conflate infrastructure pricing (plan tiers) with LLM pricing (per-token rates).
- **Database-backed pricing**: Rejected as over-engineering for relatively static data that changes a few times per year at most.
- **Unified refresh endpoint**: Rejected because infrastructure and LLM pricing change at different cadences and from different sources.

### Trade-offs
- Accepted two separate YAML files over one, gaining clean separation at the cost of two refresh endpoints.
- Accepted module-level state for refresh reports over database persistence, gaining simplicity at the cost of losing reports on process restart.

### Open Questions
- [ ] Should pricing.yaml be registered as a ConfigRegistry domain? (Task 2.6 captures this)
- [ ] What is the acceptable staleness for pricing data? (Currently manual refresh only)

### Context
The goal was to formalize the infrastructure cost prediction feature (Neon + Resend) already implemented on branch `claude/add-pricing-cost-predictions-oE6oi`. Three approaches were considered; Approach A (standalone YAML config) was selected as it follows existing project conventions. Phase 1 (core implementation) is complete; Phase 2 (tests, ConfigRegistry, validation) is planned.
