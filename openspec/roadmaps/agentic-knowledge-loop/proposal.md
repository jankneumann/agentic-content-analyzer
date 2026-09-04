# Agentic Knowledge Loop: Corrections That Land as Verified Edits

Source analysis: chat analysis of Meta Engineering, "An Organizational Second Brain:
Building an AI That Learns From Experts" (2 September 2026), mapped against the ACA
knowledge base (`src/services/knowledge_base.py`), agent memory (`src/agents/memory/`),
prompt overrides (`src/services/prompt_service.py`), and the LLM-judge evaluation
framework (`src/evaluation/`, `src/services/evaluation_service.py`). Evidence verified
at commit `96d465d`.

## Motivation

ACA already has the nouns of a self-improving knowledge system: a compiled topic
knowledge base with per-topic markdown articles, a `TopicNote` model with a
`correction` note type and a `filed_back` flag, a `prompt_overrides` table with a
version counter, an LLM-as-judge evaluation framework with datasets and a calibrator,
and a KB health linter. What it lacks is the verbs that connect them. Today:

- `TopicNote.filed_back` is only ever read for API serialization
  (`src/api/kb_routes.py:145,244`). Nothing sets it and `KnowledgeBaseService` never
  reads notes, so every correction a reviewer files is a dead end.
- Digest review outcomes are stored as free text in `review_notes` and a
  `revision_history` JSON blob (`src/services/review_service.py:198-244`); nothing
  downstream learns from them. Filter review feedback is explicitly fire-and-forget
  (`src/services/filter_feedback.py`).
- The conductor recalls the ten nearest memories by fused similarity and injects them
  into planning (`src/agents/conductor.py:287-299`) but never records which entries it
  loaded. KB Q&A selects topics by substring match over name, summary, and article body
  (`src/services/kb_qa.py:186-208`). Neither selection is auditable, so nobody can ask
  the question that makes a correction loop work: *could the agent have reached the
  right answer from what it loaded?*
- Each recompile overwrites `Topic.article_md` and bumps `article_version`; the prior
  text is gone. `PromptService.set_override` does the same to prompt text. A bad compile
  cannot be diffed or reverted.
- The evaluation framework is never invoked when a prompt override is saved or a topic
  is recompiled, and rejected review cases never become regression samples.
- `MemoryType.PREFERENCE` and `MemoryType.META_LEARNING` exist in
  `src/models/agent_memory.py:22-23` and nothing writes them.

Meta's architecture makes one structural claim worth adopting: an expert correction is
not a note, it is the input to a four-phase pipeline (diagnose, compile, evaluate, land)
that emits a reviewable, reversible diff to a file, with the failing case added to a
regression suite so the bar rises with every fix. This epic wires ACA's existing pieces
into that loop. Success looks like: a reviewer rejects a digest section or corrects a
topic article, and within one compile cycle a diff lands on the responsible prompt or
topic, having passed a structural linter, an independent validator, and the regression
set, with the whole trail visible and revertible.

## Capabilities

### Store: Knowledge load ledger per task and digest

Record exactly which knowledge loaded into every agent task and digest generation. For
agent tasks this is the memory entries returned by `Conductor._query_memory` and the
persona snapshot already captured in `ConductorResult.persona_snapshot`. For digests it
is the `ResolvedContentSet` identifiers plus any topic articles or prompt override
versions rendered into the prompt. Persist as a `knowledge_load_events` table keyed by
task id or digest id, with the loaded entity type, id, version, and the selection reason
(similarity score, routing rule, explicit include).

This is the shared plumbing for the attribution test, the routing layer, and the
evaluation gate, so it lands first.

**Acceptance Outcomes:**
- Every completed `agent_tasks` row has at least one `knowledge_load_events` row or an
  explicit "nothing loaded" marker.
- Every digest created through `OperationService` records the prompt override versions
  and topic article versions it rendered.
- `aca agent status <task-id>` and `aca kb show <slug>` can print what loaded and why.

### Pipeline: Close the correction loop into KB compilation

Make unfiled `TopicNote` rows of type `correction` and `question` part of the evidence
that `KnowledgeBaseService._gather_evidence` feeds into `_compile_topic_from_evidence`,
render them into the `kb_compilation` user template as a distinct "Corrections" block,
and set `filed_back=True` on the notes whose topic recompiled successfully. Add a
`correction` emitter to the digest review flow so a rejected or revised section files a
correction note on the topics the section drew from.

**Acceptance Outcomes:**
- A `correction` note on an active topic is included in that topic's next compile and
  its `filed_back` flag flips to true in the same transaction as the article update.
- A failed compile leaves `filed_back=False` so the correction is retried next cycle.
- Rejecting a digest section in review creates a correction note on each topic the
  section referenced, authored as `user`.
- `aca kb notes --unfiled` lists corrections still waiting to land.

### Service: Attribution test and correction triage

Implement the diagnosis step: given a correction and the load ledger for the task or
digest it refers to, classify it as `procedure_fault` (the right information was in what
loaded), `knowledge_gap` (it was not), or `ambiguity` (reviewers or sources disagree).
The classifier is an LLM call through the router with a fixed output schema, backed by a
deterministic pre-check that the referenced topic or content actually appeared in the
ledger. Route the verdict: procedure faults open a prompt override proposal, knowledge
gaps open a topic compile with the correction attached, ambiguity creates a review item
and edits nothing.

**Acceptance Outcomes:**
- Every correction row carries a `triage_verdict` and a pointer to the ledger it was
  judged against.
- A correction whose referenced content is absent from the ledger cannot be classified
  as `procedure_fault`.
- `ambiguity` verdicts never produce an article or prompt change; they appear in a
  pending review list.
- Triage verdicts are queryable so the ratio of procedure faults to knowledge gaps can
  be tracked over time.

### Store: Versioned history and diffs for topic articles and prompt overrides

Retain prior versions instead of overwriting. Add `topic_article_versions` and
`prompt_override_versions` tables written on every change, each row carrying the full
prior text, the author (system, agent persona, or user), the triggering correction or
task id, and a unified diff against the previous version. Expose `diff` and `revert`
operations through the KB and prompt APIs and CLI. Extend the existing Obsidian exporter
so positions, routing rules, and prompt overrides export alongside topic articles into a
git-trackable directory, giving an external audit trail without changing the
database-first source of truth.

**Acceptance Outcomes:**
- Recompiling a topic or saving a prompt override never deletes the previous text; the
  prior version is retrievable by version number.
- `aca kb diff <slug> --from N --to M` and `aca prompts diff <key>` print a unified diff.
- `aca kb revert <slug> --to N` restores the article and records the revert as a new
  version with author `user`.
- The vault export contains topic articles, positions, routing rules, and prompt
  overrides as files with YAML frontmatter naming their version and dependencies.

### Gate: Structural linter before a compile or override lands

Turn the offline `KBHealthService` checks into a pre-landing gate that is
non-probabilistic and fails fast. A candidate article or prompt override is rejected
before it is written when: a referenced related topic slug does not resolve; the article
exceeds a configurable size budget; a new topic exceeds `kb_merge_similarity_threshold`
against an existing active topic; a prompt override template references a variable the
step does not provide; or a routing rule references a missing topic. Failures are
recorded on the pending change with the rule that fired.

**Acceptance Outcomes:**
- A compiled article with a dangling related-topic slug is not persisted and the compile
  summary names the slug.
- A prompt override whose template uses an undeclared variable is rejected with the
  variable name.
- The existing `aca kb health` report continues to work unchanged for post-hoc review.
- Lint failures are counted in the compile summary so the failure rate is observable.

### Gate: Regression evaluation before a change lands

Wire the existing evaluation framework into the landing path. Saving a prompt override
for a step replays that step's evaluation dataset against the new prompt and blocks the
write when the judged pass rate drops below the calibrated threshold, with an explicit
force flag for operators. Recompiling a topic replays any stored Q&A samples that
reference the topic. Every rejected or revised digest section, and every correction
classified as a procedure fault, is added as a sample to the relevant step's dataset so
the suite grows with each fix.

**Acceptance Outcomes:**
- `PromptService.set_override` for a step with a dataset refuses the write when the
  judged pass rate regresses, and reports the failing sample ids.
- A rejected digest section appears as a new sample in the `digest_creation` dataset
  within the same review transaction.
- `aca evaluate report` shows the regression suite size growing over time and the last
  gate result per step.
- The gate can be bypassed only with an explicit flag that is recorded on the version
  row.

### Service: Adversarial validator with a fresh context

Before a topic recompile or prompt override lands, dispatch a second LLM call through
the router that receives only the unified diff and the target file type's structural
contract. It receives no rationale, no correction text, and no conversation history. It
returns a fixed-schema verdict (accept, reject, needs-human) with a reason. Rejections
recompile with the reason attached; needs-human enters the pending review list. The
validator runs after the structural linter and before the regression gate so cheap
checks fail first.

**Acceptance Outcomes:**
- The validator prompt contains the diff and the file-type contract and nothing else,
  asserted by a unit test on the rendered prompt.
- A validator rejection triggers at most one automatic recompile before the change is
  parked for human review.
- Validator verdicts and reasons are stored on the version row.
- Validator cost per landed change is reported alongside compile token usage.

### Registry: Deterministic routing layer for what knowledge loads

Replace "nearest ten by similarity" and "substring match, top fifty" with a routing
index that decides what loads and logs why. Topics and positions carry an
`applies_when` block in frontmatter (persona names, task types, category, keyword
patterns). Personas declare the topics and positions they always load. The router
resolves the deterministic set first, records each selection reason in the load ledger,
and only then fills remaining budget from hybrid search for the long tail. Q&A and the
conductor both consume the router.

**Acceptance Outcomes:**
- Two tasks with the same persona, task type, and prompt load the same deterministic set.
- Every loaded entry in the ledger has a selection reason of `routing_rule`,
  `persona_default`, or `search_fallback`.
- `aca kb route --persona X --task-type Y "prompt"` prints what would load and why
  without running the task.
- Search-fallback entries are capped by a configurable token budget per step.

### Store: Positions as a knowledge file type

Add positions: authoritative stances with boundary conditions, distinct from topic
articles (evidence summaries) and personas (perspective and weighting). A position has a
statement, the conditions under which it applies, the conditions under which it does
not, supporting topic references, an owner, and routing rules. Positions are versioned
through the same history tables, exported to the vault, and rendered into digest
creation and synthesis prompts when routed. Corrections of the form "we hold that X" are
triaged into position edits rather than topic edits.

**Acceptance Outcomes:**
- A position can be created, edited, and reverted via `aca kb position` commands and the
  KB API, with full version history.
- A digest generated under a persona that routes a position renders that position's
  statement and boundary conditions into the prompt, visible in the load ledger.
- The attribution triage can return `position_fault` as a sub-type of
  `procedure_fault` and route the edit to the position.
- Positions appear in the vault export as files with frontmatter.

### Component: Retire or repurpose unused memory types

`MemoryType.PREFERENCE` and `MemoryType.META_LEARNING` have no writers. Decide per type:
retire, or redefine as the compile input for positions. Recommended: retire
`meta_learning` outright; redefine `preference` as a transient signal that the position
compile consumes and then marks filed. Update the enum, the docs, and any tests. Because
the column is VARCHAR, no migration is required for removal, but existing rows must be
audited first.

**Acceptance Outcomes:**
- No enum member in `MemoryType` lacks at least one writer in `src/`.
- `docs/ACA-AGENTS.md` memory type table matches the enum.
- If `preference` is retained, a test proves a preference row is consumed by a position
  compile and marked filed.

## Constraints

- The database must remain the source of truth for knowledge; file export is a derived
  audit trail and must never be read back as authority without an explicit import step.
- All knowledge mutations (compile, override, revert, position edit) must go through
  `OperationService` as durable operations; none may execute inline in a request handler
  or CLI process.
- Every landed change must be reversible from stored history; no capability may
  introduce a write path that overwrites without a version row.
- Gates must fail closed: a linter, validator, or regression gate error must block the
  change, not skip the check.
- Ambiguity verdicts must never produce an automatic edit.
- The structural linter must be deterministic and contain no LLM call.
- The adversarial validator must not receive the correction rationale or conversation
  history; the prompt content is a tested invariant.
- New tables require Alembic migrations with single-head verification.
- Existing CLI command names and API routes must remain backward compatible; new
  behavior is additive.
- Per-change LLM cost (validator plus regression replay) must be recorded and visible
  before the gates are enabled by default.

## Phases

### Phase 0 — Record what loads

Knowledge load ledger. Nothing else in this epic can be attributed or evaluated
without it.

### Phase 1 — Close the loop

Correction loop into KB compilation; versioned history and diffs; attribution test and
triage. After this phase a correction lands as a reviewable diff on the right target.

### Phase 2 — Gate the landing

Structural linter; regression evaluation gate; adversarial validator. After this phase
nothing lands without passing cheap checks first and a growing regression set last.

### Phase 3 — Shape what loads

Deterministic routing layer; positions as a file type; retire unused memory types.
These change what the agent reads, and they depend on the ledger and gates so their
effect can be measured and their edits validated.

## Out of Scope

- Replacing hybrid search or the knowledge graph. Search stays as the long-tail
  fallback behind the routing layer.
- Parallel sub-agent compilation with cross-reference and token-budget checks across
  hundreds of files. ACA has one reviewer; the linter and validator cover the checks
  that matter at this scale.
- Model fine-tuning or retraining of any kind.
- Moving the source of truth from PostgreSQL to files; the earlier database-first
  decision in `docs/LLM_KNOWLEDGE_BASE.md` stands.
- Changes to the ingestion filter feedback log beyond consuming it as a triage input.
- A web UI for triage and diff review. CLI and API first; the frontend follows in a
  separate epic once the data model is stable.
