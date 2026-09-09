# Vision

agentic-content-analyzer exists so that people who must keep up with a fast-moving field get trend analysis and leadership advice they can trust.
It serves technical leaders and practitioners first, and anyone who points it at their own sources and prompts, because the repository is public and the domain focus lives in configuration.
It owns exactly one thing: turning external content, memories, and observations into durably stored, verifiably summarized knowledge.

## A claim of success must be provable, not reported

A backup, a workflow submission, or a digest run is not done because a process exited zero.
It is done when the artifact it was supposed to produce is checked back, byte for byte.
A shell pipeline that reports only its last stage's exit code is treated as a defect, not a shortcut.
A test that mocks a subprocess's output into the shape the code expects, rather than the bytes the real tool emits, does not count as proof that a feature works end to end.
Verification effort is sized to blast radius: a limited idea may be explored in a simulated or mocked environment, and the moment it touches the durable path or a user it is proven against the real mechanism.
End-to-end integration is where this project has been bitten most, so proof of a shipped feature is as comprehensive as it needs to be to show the feature truly works.
A 5xx response is a claim about this system's own health, and mapping every exception to one blindly misdirects an operator's response.
Every path that can reject or fail a workflow lands somewhere an operator can see it, because a rejection that fails silently is worse than one that crashes loudly.

## The structure is deterministic and durable, the judgment is agentic, the decisions are human

What runs, in what order, with what inputs, is fixed code, never a model's choice at runtime.
CLI, HTTP, MCP, and the frontend submit the same operation types to one durable queue, and none of them executes ingestion, summarization, digest, or audio work inline.
An in-memory queue, a background task, or a direct execution path is a durability regression, not an optimization.
A feature that cannot survive a restart mid-run is not finished.
Inside that structure, agentic specialists supply the judgment that has to scale: ranking, synthesis, analysis, and the questions a deterministic step cannot answer.
Judgment a specialist should not make alone escalates to a human decision through an approval gate, and the gate is a recorded step, not a suggestion.
A focused lookup does not go through the specialist framework; the framework exists for multi-step analysis, not for work a deterministic pipeline does better.
Agents with distinct goals, such as independent research or an AI tutor, use the system as a tool, and each is defined by clear goals and clear limits before it runs.
Risk tiers change only with human approval.
A gate may learn from observation and empirical evidence, but the agent subject to a gate is never the source of a change to it; that change is always a separate process.

## Built for today's scale, behind abstractions that can carry tomorrow's

Designs are sized to the scale the project actually runs at, not to the scale it might reach.
Complexity is added when a need is demonstrated, not when it is imagined, and it arrives inside an existing abstraction rather than as a new subsystem.
The abstractions stay clean enough that the next step up in complexity is an addition, not a rewrite.
A simpler mechanism that is proven to work is preferred over a stronger one that is not yet proven here.
Boundaries between modules are thin abstraction layers with a contract, so a module can be replaced in line with its contract without touching its neighbors.
The project evolves continuously and reprioritizes as it learns; it has no fixed release cadence.

## Providers are chosen explicitly and held behind thin abstractions

Database, object storage, graph database, and observability each ship at least two interchangeable backends, selected by configuration, not by code branch.
A provider that shapes capabilities or the build is named explicitly in configuration, never inferred from other settings, because an explicit choice is what keeps the whole stack aligned around it.
Each provider gets a dedicated build path behind the same thin abstraction, so a provider-specific capability can be used where it earns its place without the rest of the stack learning that provider's name.
Moving off a host is a planned capability, not a fire drill.

## The project holds its own history to the evidence standard it demands of its infrastructure

Specs describe current, evidenced behavior.
A checked requirement that contradicts running behavior gets reclassified, not left checked.
Archived decisions are never rewritten; a later change supersedes one in the open, in a new document.
A roadmap idea with no bounded proposal, task plan, or spec delta does not get promoted into a feature because it sounds compelling.
Independently deployed consumers are served through standard revision and upgrade mechanisms: versioned contracts, compatibility windows stated in writing, and thin adapters that carry a retirement date.
A stated window is a coordination promise, not a cutoff: a breaking change lands when its consumers can take it, not when a calendar says so.
A retired contract shape does not come back unversioned, undated, or by accident.

## A process that can delete never runs unattended, and a compromised credential never unlocks everything

Retention against the backup target is dry run by default and cannot delete; only a human-run command can.
A backup host's own credentials are sufficient to write a new backup and never sufficient to decrypt an old one.
Ingested content is precious, not re-derivable: it carries the provenance behind every claim, and it is reprocessed as models and the system improve, so it is kept and backed up alongside human decisions.

## Scope

It is not a system whose domain is fixed in code: what it pays attention to, the voice it writes in, and which personas analyze it live in prompts, personas, and source lists.
It is not a general-purpose agent platform: it is a tool that agents with a defined goal and defined limits use, and an agent without both does not run here.
It is not a CI system, or a place to bolt on every integration a source could plausibly offer.
It is not a cache: what it ingests it keeps, with provenance, because a better model will read it again.
It is not a marketing surface: digest quality is measured against a written content guideline, not against enthusiasm.

A change aligns when it can prove the artifact it claims to produce, survives a restart, keeps a provider behind its abstraction, is sized to the scale that exists, defines an agent's goals and limits before it runs, sizes its verification to its blast radius, and states its evidence.
A change should be resisted when it reports success without checking, reaches the durable path or a user on a mock, executes a mutation inline just this once, lets a model decide what the pipeline runs next, adds a subsystem for a scale that has not arrived, infers a provider instead of naming it, teaches the stack a vendor's name outside its adapter, treats ingested content as disposable, lets an agent change the gate it is subject to, rewrites archived history, or hands delete authority to an unattended process.
