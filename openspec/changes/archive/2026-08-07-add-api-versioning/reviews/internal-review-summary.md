# Independent review summary

Three read-only internal reviewers independently assessed the RI-11 decision on
2026-08-07. External multi-vendor dispatch was not performed because it required
separate authorization to disclose repository materials to configured external
CLI destinations.

## Consensus

All reviewers support deferring and archiving the existing 42-task proposal. No
reviewer found a concrete current successor contract that justifies a second live
URL version, and none recommended keeping an implementation task active.

## Corrections applied

- The consumer inventory now includes the independently installed iOS Shortcut and
  the external `agentic-assistant` HTTP/OpenAPI and MCP consumer. Neither is assumed
  to migrate in lockstep without evidence.
- Optional response fields are no longer described as inherently additive because
  canonical Python response models reject unknown fields.
- Executable evidence is explicitly scoped to the canonical workflow surface, not
  every legacy `/api/v1` router or the separate legacy CLI client.
- A future version design must prevent authentication downgrade, make audit coverage
  version-agnostic, preserve middleware/error/CORS invariants, and define safe cache
  and rollback behavior for sunset responses.

## Task review

The 42 tasks divide into:

- 14 unnecessary speculative tasks: `1.1–1.4`, `2.5–2.6`, `3.1–3.7`, `8.1`;
- 7 tasks already represented by current contracts, tests, or ADR-0002: `5.1`,
  `5.4`, `6.1`, `7.4`, `8.2`, `8.3`, `8.5`; and
- 21 tasks that are meaningful only after a concrete incompatible successor is
  named and must then be rewritten against its exact diff: `2.1–2.4`, `4.1–4.4`,
  `5.2–5.3`, `6.2–6.3`, `7.1–7.3`, `8.4`, `9.1–9.5`.

## Security review

Deferral introduces no security regression and avoids duplicating the attack
surface. The old design is unsafe to revive unchanged because:

- retaining weaker v1 authentication during a fixed deprecation window creates a
  downgrade path;
- current audit and Problem-path classifications contain explicit `/api/v1`
  boundaries and would not automatically cover v2;
- a short-circuiting version or sunset middleware could bypass deliberate auth,
  audit, CORS, security-header, and error-handler ordering; and
- a cacheable 410 response can persist after rollback unless cache behavior is
  explicit.

The optional detailed security-checklist reference named by the installed skill was
absent from both repository skill copies. The reviewer applied the complete
preventive checklist embedded in the skill plus current repository invariants; no
code or scanner target was introduced by this planning-only change.
