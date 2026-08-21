# Design: Cross-harness session flow display

## What zoetrope proves, and what we keep

Zoetrope's architecture rests on one invariant worth adopting verbatim:
the session model is a pure function of the set of facts folded into it,
never of their arrival order — folds are idempotent and commutative, so
seeking rebuilds state from `facts[0..playhead]` and reaches exactly the
state that playing there would have. It also separates two clocks:
content time (transcript timestamps, governs state) and presentation time
(playback, governs animation only). Both carry over unchanged.

What we replace is its input assumption. Zoetrope reads local Claude Code
JSONL and is provably network-free. Our sessions span seven harnesses and
ephemeral cloud containers, so the local filesystem cannot be the only
fact source. The generalization: keep the fold, swap the transport.

## Two capture paths, one fact schema

```
harness session
   │
   ├─ live path ────────────────────────────────┐
   │   Stop/SubagentStop hook                   │
   │   → adapter.normalize_session()            │
   │   → sanitize → Langfuse observations       ▼
   │     (as_type=agent per turn,          Langfuse project
   │      as_type=tool children,           (durable, cross-machine)
   │      session_id + harness tag)             │
   │                                            │
   └─ capture path ─────────────────────────┐   │
       collect-transcripts adapters         │   │
       → sanitize → NormalizedEvent JSONL   │   │
         docs/transcripts/<date>/<id>.jsonl ▼   ▼
                                        flow API (read-only)
                                        normalizes both sources
                                        to one fact stream
                                                │
                                                ▼
                                        web `flows` route
                                        pure fold → graph + scrubber
```

`NormalizedEvent` (from `collect-transcripts/scripts/normalize.py`) is the
single fact type. The Langfuse hook's private `group_into_turns()` parser
is deleted; the hook imports the adapter for its harness and derives turn
grouping from the normalized stream. This closes the two-schemas gap and
makes every future adapter (e.g. Jules, later) automatically
hook-capable.

Schema additions (bump `collect-transcripts` schema version, regenerate
`references/event-schema.md`):

- `parent_session_id: str | None` — set for subagent sessions.
- `spawned_by_tool_use_id: str | None` — the `tool_use_id` of the Agent /
  Task invocation that launched this session; the flow graph's
  agent-to-subagent edge.
- `agent_label: str | None` — display label when the harness provides one.

Absence of these fields degrades to a single-node session graph, so old
captures stay renderable.

## Harness coverage tiers

| Tier | Harnesses | Mechanism | Latency |
|---|---|---|---|
| Hooked | Claude Code CLI, cloud sessions | Stop/SubagentStop hook → Langfuse | per-turn |
| Batch | Codex, Antigravity, Grok, Pi | `collect-transcripts` run → JSONL + Langfuse batch uploader | post-hoc |
| Absent | Jules (no adapter) | out of scope; adding the adapter later grants both paths | — |

The batch uploader is a small addition to `collect-transcripts`: after
normalize+sanitize, optionally emit the same observation shape the hook
emits (`agent` turn / `tool` child, `session_id`, harness tag). Every
harness then lands in one Langfuse project with a uniform vocabulary; the
flow display filters by tag.

## Fold and graph model

Node kinds: session (root agent), subagent, tool aggregate. Edges:
`spawned_by_tool_use_id` (agent→subagent), `tool_use_id` pairing
(invocation→result closes a tool's pending state). Liveness follows
zoetrope's ruling: derive only where no ground truth exists — pending
tool_use blocks mean working; a spawn acknowledgment is a launch ack,
never a completion; terminal status comes only from explicit completion
facts, and time-derived liveness reverses when contradicted.

The fold is implemented once, client-side, in TypeScript
(`web/src/lib/flow/fold.ts`): the API serves ordered facts; the frontend
folds `facts[0..playhead]` for seeking, and appends for live-follow. A
property test replays shuffled fact orders and asserts state equality —
the executable form of the idempotent/commutative contract.

## Flow API (read-only)

- `GET /api/v1/flows/sessions` — merged session summaries from
  `docs/transcripts/` (via `SessionSummary`) and the Langfuse API
  (sessions by tag), deduplicated on `session_id`, cursor-paginated with
  absent-param serialization per the house httpx gotcha.
- `GET /api/v1/flows/sessions/{session_id}/events` — ordered fact stream;
  `source=transcript|langfuse` resolved server-side, transcript preferred
  when both exist (full fidelity beats reconstructed observations).

Langfuse credentials stay server-side (settings already exist); the
Langfuse-to-fact reverse mapping lives next to the routes. Both sources
fail soft: an unreachable Langfuse or empty transcripts dir yields an
empty list plus a `source_warnings` field, mirroring
`agent-metrics/scripts/query_metrics.py`. No `OperationService` types are
added — nothing here mutates.

## Frontend

New manual route `flows` (three coordinated edits: `routes/flows.tsx`,
`routeTree.gen.ts`, `lib/navigation.ts`). Structure mirrors
`routes/themes.tsx`: a view switcher (`graph | timeline | list`), TanStack
Query hooks, `PageContainer`. Graph rendering reuses
`react-force-graph-2d` (per `ThemeNetworkGraph`), the scrubber and token
timeline reuse `recharts` (per `ThemeTimelineChart`). Presentation-time
effects (fade, camera) never touch fold state.

## Sanitization and limits

Sanitize before any egress, at the capture edge, using the existing
chain: `collect-transcripts/scripts/sanitize_events.py` (which already
extends the `session-log` sanitizer to tool args/results). The Langfuse
SDK metadata limit (str values, 200 chars) means structured flow fields
travel in observation input/output and tags, never metadata. Prompt
bodies obey the existing `log_prompts` truncation posture.

## Decisions

1. **Langfuse is the cross-machine event bus, transcripts are ground
   truth.** Replay/seek needs full-fidelity ordered facts; Langfuse
   observations are a lossy projection good for liveness, aggregation,
   and sessions whose filesystems are gone. Prefer transcript when both
   exist.
2. **Fold client-side, normalize server-side.** Seeking re-folds locally
   without refetching; the server's job is source merging and credential
   custody.
3. **Do not widen `ObservabilityProvider`.** The Protocol has no session
   concept and app telemetry does not need one; the hook path talks to
   the Langfuse SDK directly. Revisit only if a second provider must
   render flows.
4. **Host default reconciliation:** the hook's `:3050` default and the
   profile's `:3100` self-hosted UI must converge on the profile value;
   the hook reads `LANGFUSE_HOST` from the same OpenBao-backed env
   script either way.
5. **Hook registration follows house convention:** tracked script
   location, registered via the existing idempotent
   `install_stop_hook.py`, gated on `LANGFUSE_ENABLED`, never fails
   noisily. Verify the actual mirror layout (`.claude/skills/` is the
   tracked root here) before wiring paths.

## Risks

- Langfuse observation → fact reverse-mapping is the only new lossy
  boundary; keep it thin and covered by a round-trip test (hook-emitted
  session fetched back must fold to the same graph topology).
- Transcript directories on cloud containers vanish at reclaim; the hook
  path is therefore the only reliable capture there — document that
  cloud sessions may be Langfuse-source-only.
- `react-force-graph-2d` is force-directed, not hierarchical; if agent
  trees read poorly, fall back to a computed layered layout fed as fixed
  node positions before reaching for a new dependency.
