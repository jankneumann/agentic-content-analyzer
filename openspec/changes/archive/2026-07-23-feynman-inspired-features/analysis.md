# Feature Analysis: Feynman-Inspired Capabilities

**Date**: 2026-04-08
**Source**: [getcompanion-ai/feynman](https://github.com/getcompanion-ai/feynman) — open-source AI research agent
**Status**: Analysis / Opportunity identification

---

## 1. Feynman Overview

Feynman is an open-source CLI AI research agent (MIT, TypeScript, 3.2k stars) that automates complex research workflows through multi-agent collaboration. It orchestrates four specialized agents — **Researcher**, **Reviewer**, **Writer**, **Verifier** — to investigate topics, synthesize findings, and produce source-grounded outputs.

### Architecture

- **Runtime**: Built on [Pi agent framework](https://github.com/badlogic/pi-mono) (`@mariozechner/pi-agent-core`) for multi-LLM orchestration with tool calling
- **Paper Backend**: [AlphaXIV](https://www.alphaxiv.org/) via the `alpha` CLI — search, full-text Q&A, code annotation, persistent notes
- **Compute**: Docker (local isolation), Modal (serverless GPU), RunPod (persistent GPU pods)
- **Skills**: Ship as Markdown prompt files synced to `~/.feynman/agent/skills/`

### Key Research Workflows (Slash Commands)

| Command | Description |
|---------|-------------|
| `/deepresearch` | Multi-agent parallel investigation with synthesis & verification |
| `/lit` | Systematic literature review — consensus, disagreements, gaps |
| `/audit` | Compare paper claims against public codebases |
| `/replicate` | Run experiments on local or cloud GPUs |
| `/review` | Simulated peer review with severity grading |
| `/compare` | Side-by-side source comparison matrices |
| `/draft` | Academic-style paper generation from research notes |
| `/autoresearch` | Autonomous experimental loops |
| `/watch` | Recurring topic monitoring |

### Source Grounding

Every claim links to papers, docs, or repos with direct URLs — no hallucinated citations.

---

## 2. Current ACA Capabilities (Gap Analysis)

### What We Already Have

| Capability | ACA Component | Feynman Equivalent |
|------------|---------------|--------------------|
| Multi-agent orchestration | `Conductor` (state machine) | Pi agent runtime |
| Research tools | `ResearchSpecialist` (search, graph, web, fetch_url) | Researcher agent |
| Theme analysis | `AnalysisSpecialist` (ThemeAnalyzer, HistoricalContextAnalyzer) | — (no equivalent) |
| Content synthesis | `SynthesisSpecialist` (DigestCreator) | Writer agent |
| Source ingestion | `IngestionSpecialist` (12 source types) | — (limited) |
| Academic papers | arXiv client + Semantic Scholar client | AlphaXIV CLI |
| Knowledge graph | Graphiti/Neo4j temporal context | — (no equivalent) |
| Persona system | 3 YAML personas with tool restrictions | — (no equivalent) |
| Reference extraction | arXiv IDs, DOIs, S2 IDs → auto-resolution | Source grounding |
| Memory | Vector + keyword + graph (RRF fusion) | Session indexing |
| Scheduled analysis | Cron-driven tasks in `schedule.yaml` | `/watch` monitoring |

### What We're Missing (Feynman Gaps)

1. **AlphaXIV integration** — paper Q&A, community annotations, linked code repos
2. **Verification agent** — inline citation validation, dead link detection, claim verification
3. **Peer review simulation** — severity-graded critique of research artifacts
4. **Paper-to-code audit** — comparing paper claims against actual implementations
5. **Source comparison matrices** — structured agreement/disagreement analysis
6. **Literature review workflow** — systematic consensus/gap identification
7. **Autonomous research loops** — iterative hypothesis → experiment → refine cycles
8. **Experiment replication** — sandboxed execution of paper experiments

---

## 3. Proposed Features (Prioritized)

### P0: AlphaXIV CLI Integration (High Impact, Low Risk)

**Why**: AlphaXIV is the paper interaction layer Feynman uses most heavily. It provides capabilities our arXiv/Scholar clients lack — community-sourced Q&A, annotations, and linked code repositories. This would significantly enhance our academic paper pipeline.

**What the `alpha` CLI provides**:
- `alpha search --mode agentic` — broad paper retrieval (vs `--mode keyword` for exact terms)
- Full-text paper reading with section navigation
- Targeted Q&A against paper content (ask questions, get grounded answers)
- Linked code repository inspection (find GitHub repos implementing the paper)
- Persistent annotations and notes on papers

**Integration points in ACA**:
- **New tool in `ResearchSpecialist`**: Add `search_alphaxiv` and `ask_paper` tools
- **Ingestion source**: Add `alphaxiv` to `IngestionSpecialist` source types and `ContentSource` enum
- **Reference resolver**: Extend `reference_resolver.py` to resolve via AlphaXIV when arXiv/Scholar fail
- **CLI command**: `aca ingest alphaxiv --query "..." --mode agentic|keyword`

**Implementation sketch**:
```python
# src/ingestion/alphaxiv_client.py
class AlphaXIVClient:
    """Wrapper around the alpha CLI for paper search and Q&A."""

    async def search(self, query: str, mode: str = "agentic") -> list[PaperResult]:
        """Search papers via alpha CLI."""

    async def read_paper(self, paper_id: str) -> PaperContent:
        """Read full paper text with section navigation."""

    async def ask_paper(self, paper_id: str, question: str) -> AnswerResult:
        """Ask a question against paper content."""

    async def get_linked_code(self, paper_id: str) -> list[CodeRepo]:
        """Find GitHub repos implementing this paper."""

    async def get_annotations(self, paper_id: str) -> list[Annotation]:
        """Get community annotations/discussions."""
```

**Files to modify**:
- `src/ingestion/alphaxiv_client.py` (new)
- `src/ingestion/alphaxiv.py` (new service, following `arxiv.py` pattern)
- `src/ingestion/orchestrator.py` (add `ingest_alphaxiv` function)
- `src/models/content.py` (add `ALPHAXIV` to `ContentSource` enum)
- `src/agents/specialists/research.py` (add `search_alphaxiv` and `ask_paper` tools)
- `src/cli/ingest_commands.py` (add `alphaxiv` subcommand)
- `sources.d/alphaxiv.yaml` (new source config)

---

### P1: Verification Specialist (High Impact, Medium Effort)

**Why**: Feynman's Verifier agent addresses a real gap in our pipeline — we generate insights and digests but don't systematically verify citations or validate claims. This is the "trust layer" that makes outputs reliable.

**What it would do**:
- Validate URLs in generated content (detect dead links)
- Verify inline citations match their claimed source
- Cross-reference claims against our knowledge graph
- Flag unsupported or contradictory assertions
- Add confidence scores to individual claims

**Integration points**:
- **New specialist**: `src/agents/specialists/verification.py`
- **New task type**: Add `"verification"` to `_TASK_TYPE_TO_SPECIALIST` in `conductor.py`
- **Post-processing hook**: Run after `SynthesisSpecialist` produces a digest
- **Registry**: Add to `SpecialistRegistry.create_default()`

**Tools for the specialist**:
```python
tools = [
    "verify_url",         # HEAD request + status check
    "verify_citation",    # Cross-ref claim text against source content
    "check_consistency",  # Compare claim against knowledge graph facts
    "validate_data",      # Verify numerical claims, dates, stats
]
```

---

### P2: Paper Audit Workflow (Medium Impact, Medium Effort)

**Why**: Feynman's `/audit` command compares paper claims against codebases — a powerful capability for evaluating whether research actually delivers what it promises. Complements our existing arXiv/Scholar integrations.

**What it would do**:
- Extract claims from a paper (methods, results, performance numbers)
- Find linked code repositories (via AlphaXIV or Papers With Code)
- Compare claimed methodology against actual implementation
- Identify discrepancies, missing components, or unreproducible elements
- Generate an audit report with severity-graded findings

**Integration approach**:
- Leverage existing `ResearchSpecialist` tools (search, fetch_url)
- Add new `audit_paper` CLI command: `aca agent task --type audit "Audit paper arxiv:2401.12345"`
- Use `AnalysisSpecialist.detect_anomalies` for claim verification
- Output to knowledge graph as a structured episode

---

### P3: Source Comparison Matrices (Medium Impact, Low Effort)

**Why**: Feynman's `/compare` generates structured matrices of agreements, disagreements, and confidence across sources. This maps directly to our theme analysis pipeline — we detect themes but don't systematically compare source positions.

**What it would do**:
- Select multiple content items on the same topic
- Extract key claims from each source
- Build a comparison matrix: source × claim × evidence × confidence
- Highlight consensus, disagreements, and areas of uncertainty
- Visualize with structured markdown tables (or Mermaid diagrams)

**Integration approach**:
- Extend `AnalysisSpecialist` with a `compare_sources` tool
- Leverage existing `search_content` to find related items
- Add comparison output format to `SynthesisSpecialist.create_report`
- CLI: `aca analyze compare --topic "RAG architectures" --sources arxiv,scholar,rss`

---

### P4: Literature Review Workflow (Medium Impact, Medium Effort)

**Why**: Feynman's `/lit` produces systematic literature reviews — consensus, disagreements, open questions, and gaps. Our `trend_detection_tech_arxiv_only` schedule does weekly analysis but lacks the structured lit-review format.

**What it would do**:
- Search across arXiv, Scholar, and AlphaXIV for a topic
- Categorize papers by methodology, findings, and recency
- Identify consensus positions and disagreements
- Map open questions and research gaps
- Generate a structured review document

**Integration approach**:
- New prompt template in `settings/prompts.yaml` for literature review output format
- New scheduled task type or a dedicated CLI command
- Combine `ResearchSpecialist` (gather) + `AnalysisSpecialist` (analyze) + `SynthesisSpecialist` (structure)
- CLI: `aca agent task --type literature_review "RAG vs fine-tuning for domain adaptation"`

---

### P5: Simulated Peer Review (Lower Impact, Medium Effort)

**Why**: Feynman's `/review` simulates peer review with severity-graded objections and revision plans. Could be applied to our digest quality assurance — the review system already exists but focuses on editorial quality, not scientific rigor.

**What it would do**:
- Evaluate a digest or analysis for: novelty, rigor, evidence quality, reproducibility
- Generate severity-ranked critique (critical, major, minor, suggestion)
- Propose concrete revision actions
- Optionally iterate (re-review after corrections)

**Integration approach**:
- Extend existing review system (`docs/REVIEW_SYSTEM.md`)
- Add `peer_review` output format to `SynthesisSpecialist`
- Could use a new "reviewer" persona with high `novelty_bias` and strict standards

---

### P6: Recurring Topic Watch (Lower Impact, Low Effort)

**Why**: Feynman's `/watch` sets up recurring monitoring — we already have `schedule.yaml` but it's admin-configured. User-initiated topic watches would be more accessible.

**What it would do**:
- User specifies a topic and frequency
- System creates a schedule entry targeting arXiv/Scholar/AlphaXIV
- On each trigger, search for new papers, compare against previous results
- Notify user of new developments via digest or alert

**Integration approach**:
- Dynamic schedule entry creation via CLI: `aca agent watch "multimodal reasoning" --every 2d`
- Store in DB (not just YAML) for per-user watches
- Leverage existing `scan_sources` + `trend_detection` infrastructure
- Diff against previous watch results to highlight only new findings

---

## 4. Architecture Alignment

Feynman and ACA share remarkably similar architecture patterns:

| Aspect | Feynman | ACA |
|--------|---------|-----|
| Orchestration | Pi agent runtime | Conductor state machine |
| Specialists | 4 agents (Researcher, Reviewer, Writer, Verifier) | 4 specialists (Research, Analysis, Synthesis, Ingestion) |
| Tool system | Pi tools with namespace prefixing | ToolDefinition with `specialist.tool` naming |
| Skills/Prompts | Markdown files in `~/.feynman/agent/skills/` | YAML in `settings/prompts.yaml` |
| Output artifacts | `outputs/<slug>-*.md` files | Digests, insights, reports in DB |
| Source grounding | Every claim has a URL | Reference extraction + resolution pipeline |

The key philosophical difference: Feynman is a **research-forward** tool (papers in, analysis out), while ACA is a **newsletter aggregation** platform that added academic capabilities. The proposed features bridge this gap by bringing Feynman's research rigor to ACA's broader content pipeline.

---

## 5. Implementation Roadmap

### Phase 1: Foundation (AlphaXIV + Verification)
- P0: AlphaXIV CLI integration
- P1: Verification specialist

### Phase 2: Research Workflows
- P2: Paper audit workflow
- P3: Source comparison matrices
- P4: Literature review workflow

### Phase 3: Quality & Automation
- P5: Simulated peer review
- P6: Recurring topic watch

### Dependencies
- P0 (AlphaXIV) is a prerequisite for P2 (audit) and P4 (lit review) at full capability
- P1 (verification) is independent and can proceed in parallel with P0
- P3 (comparison) can start immediately — uses existing tools

---

## 6. Risk Assessment

| Feature | Risk | Mitigation |
|---------|------|------------|
| AlphaXIV CLI dependency | External tool, may change API | Wrap in client abstraction (same pattern as arxiv_client.py) |
| Verification false positives | May flag valid content | Configurable confidence thresholds, human review fallback |
| Paper audit scope creep | Could become arbitrarily deep | Depth limits (like `auto_ingest_depth` pattern) |
| Source comparison quality | LLM may hallucinate agreement/disagreement | Ground in extracted quotes, not summaries |
| Additional specialist complexity | More moving parts in conductor | Gate behind persona config, off by default |
