# Vision

agentic-content-analyzer exists so that people tracking AI and data developments get a digest they can trust, built from newsletters, feeds, video, search, and papers it ingests on their behalf.
It serves technical leaders and practitioners who need signal without reading every source themselves.
It owns exactly one thing: turning scattered external content into durably stored, verifiably summarized knowledge.

## A claim of success must be provable, not reported

A backup, a workflow submission, or a digest run is not done because a process exited zero.
It is done when the artifact it was supposed to produce is checked back, byte for byte.
A shell pipeline that reports only its last stage's exit code is treated as a defect, not a shortcut.
A test that mocks a subprocess's output into the shape the code expects, rather than the bytes the real tool emits, does not count as coverage.
A 5xx response is a claim about this system's own health, and mapping every exception to one blindly misdirects an operator's response.
Every path that can reject or fail a workflow lands somewhere an operator can see it, because a rejection that fails silently is worse than one that crashes loudly.

## Every mutation is durable by construction

CLI, HTTP, MCP, and the frontend submit the same operation types to one durable queue.
None of them executes ingestion, summarization, digest, or audio work inline.
An in-memory queue, a background task, or a direct execution path is a durability regression, not an optimization.
A feature that cannot survive a restart mid-run is not finished.

## No layer of the stack locks the project to one vendor

Database, object storage, graph database, and observability each ship at least two interchangeable backends, selected by configuration, not by code branch.
A design that trades a portable option for a vendor's proprietary feature is rejected unless the portable option is proven not viable.
Moving off a host is a planned capability, not a fire drill.

## The project holds its own history to the evidence standard it demands of its infrastructure

Specs describe current, evidenced behavior.
A checked requirement that contradicts running behavior gets reclassified, not left checked.
Archived decisions are never rewritten.
A later change supersedes a decision in the open, in a new document, rather than editing history.
A roadmap idea with no bounded proposal, task plan, or spec delta does not get promoted into a feature because it sounds compelling.

## A process that can delete never runs unattended, and a compromised credential never unlocks everything

Retention against the backup target is dry run by default and cannot delete.
Only a human-run command can delete a backup.
A backup host's own credentials are sufficient to write a new backup and never sufficient to decrypt an old one.
Independently deployed API consumers get a compatibility window stated in writing.
Retired contract shapes do not quietly come back as an adapter.

## Scope

It is not a general-purpose agent platform, a CI system, or a place to bolt on every integration a source could plausibly offer.
It is not a system that silently decides which content is precious and which is disposable; that line is drawn explicitly, in writing, and revisited as ingestion grows.
It is not a marketing surface: digest quality is measured against a written content guideline, not against enthusiasm.

A change aligns when it can prove the artifact it claims to produce, survives a restart, keeps a vendor swappable, and states its evidence.
A change should be resisted when it reports success without checking, executes a mutation inline just this once, hardcodes a single vendor's feature, rewrites archived history, or hands delete authority to an unattended process.
