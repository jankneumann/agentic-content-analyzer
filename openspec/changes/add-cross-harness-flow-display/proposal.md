# Change: Cross-harness session flow display

## Why

Zoetrope (github.com/furkankly/zoetrope) demonstrates that a Claude Code
session rendered as a live flow graph — agents as nodes, tool chips, a
scrubber timeline — is a materially better observability surface than raw
transcripts. But it is Claude-Code-only, local-filesystem-only, and
deliberately network-free, so it cannot cover this repository's fleet of
harnesses (Claude Code CLI/web, Codex CLI/web, Antigravity, Grok, Pi) or
sessions running on ephemeral cloud containers.

This repository already owns every ingredient of a generalized version, in
disconnected pieces:

- `collect-transcripts` normalizes seven harnesses' transcripts into one
  `NormalizedEvent` schema with `tool_use_id` linkage and sequence ordering.
- The `langfuse` skill ships a Stop hook that emits per-turn
  `as_type="agent"` observations with `as_type="tool"` children, grouped by
  `session_id` and tagged by harness — but it is unregistered, and it
  re-parses Claude Code JSONL itself instead of reusing the adapters.
- The web frontend already carries `react-force-graph-2d` and `recharts`
  with working graph/timeline precedents (`ThemeNetworkGraph`,
  `ThemeTimelineChart`, the `themes` route view-switcher).

Nothing connects them: no frontend consumes Langfuse or transcript data,
`docs/transcripts/` has never been populated, and the hook and adapter
paths maintain two divergent schemas for the same underlying reality.

## What Changes

- Unify the capture substrate: the Langfuse hook SHALL parse transcripts
  through the `collect-transcripts` adapters, and `NormalizedEvent` gains
  the minimal linkage fields (parent session, spawning `tool_use_id`) a
  flow graph needs. One schema feeds both Langfuse and local capture.
- Register hook-based Langfuse logging as a live capture path (Stop /
  SubagentStop via the existing idempotent installer), and add a batch
  uploader so hook-less harnesses reach the same Langfuse project through
  `collect-transcripts` output, tagged by harness.
- Add a read-only flow API that lists sessions and serves ordered fact
  streams from two sources: captured transcript JSONL (full fidelity,
  replay/seek) and the Langfuse API (cross-machine, near-live), normalized
  to the same fact shape server-side so credentials stay off the client.
- Add a `flows` frontend route rendering the fact stream as a flow graph
  with a content-time scrubber. Graph state is a pure, idempotent,
  commutative fold over facts — zoetrope's core invariant — so live-follow
  and replay of the same session converge to identical state.
- Reconcile the self-hosted Langfuse host defaults (hook `:3050` vs
  profile `:3100`).

Out of scope: widening the `ObservabilityProvider` Protocol with session
semantics (the hook path uses the Langfuse SDK directly and app telemetry
is unaffected), a Jules transcript adapter, and any new durable mutation
types (the flow surface is read-only; transcript capture stays a
CLI/skill concern).

## Capability

- `agentic-flow-display`

## Impact

New backend read-only routes, one new frontend route (three-edit manual
routing), `.claude/settings.json` gains Stop/SubagentStop hook entries,
`collect-transcripts` schema version bump with regenerated
`event-schema.md`, and the `langfuse` skill hook loses its private parser.
App observability (`src/telemetry/`) and canonical workflow contracts are
untouched.
