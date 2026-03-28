# Design — Tree Index Chunking

## Background: PageIndex Approach

[VectifyAI's PageIndex](https://github.com/VectifyAI/PageIndex) is a vectorless, reasoning-based RAG system that replaces chunk embedding + vector similarity with hierarchical tree indexing + LLM tree search. Key ideas we borrow:

1. **Tree thinning** — merge undersized nodes upward to reduce fragmentation (`page_index_md.py:tree_thinning_for_index()`)
2. **Hierarchical tree from headings** — stack-based tree building from heading levels (`page_index_md.py:build_tree_from_nodes()`)
3. **LLM node summarization** — generate summaries for internal tree nodes during indexing (`page_index_md.py:get_node_summary()`)
4. **Tree search prompt** — LLM reasons over tree structure (summaries only, no text) to select relevant nodes (`cookbook/pageindex_RAG_simple.ipynb`)
5. **Adaptive document routing** — detect TOC/structure complexity to choose processing path (`page_index.py:page_index_main()`)

We do NOT use PageIndex as a dependency because: (a) it uses `litellm` while we use `llm_router` with observability, (b) it uses `PyPDF2` while we use Docling for richer parsing, (c) it replaces vector search while we want to augment it, (d) pinned dependency versions conflict.

## Architecture

### Content Type Routing

```
Content arrives → ChunkingService.chunk_content()
  │
  ├─ Standard strategy selection (existing):
  │   parser_used → PARSER_TO_STRATEGY → flat chunks
  │
  └─ Tree index qualification check (new):
      IF token_count > tree_index_min_tokens (8000)
      AND heading_depth >= tree_index_min_heading_depth (3):
          ALSO run TreeIndexChunkingStrategy → tree chunks
```

Both flat and tree chunks are stored in `document_chunks`. Flat chunks have `parent_chunk_id=NULL`; tree chunks have populated tree columns.

### Tree Structure in Database

```
document_chunks table (existing + new columns):

  id | content_id | chunk_text | chunk_type | parent_chunk_id | tree_depth | is_summary
  ---+------------+------------+------------+-----------------+------------+-----------
  1  | 42         | "Full §1"  | paragraph  | NULL            | NULL       | NULL       ← flat chunk
  2  | 42         | "Full §2"  | paragraph  | NULL            | NULL       | NULL       ← flat chunk
  10 | 42         | "Summary"  | section    | NULL            | 0          | TRUE       ← tree root
  11 | 42         | "Sum §1"   | section    | 10              | 1          | TRUE       ← internal node
  12 | 42         | "Sum §2"   | section    | 10              | 1          | TRUE       ← internal node
  13 | 42         | "Content"  | paragraph  | 11              | 2          | FALSE      ← leaf node
  14 | 42         | "Content"  | paragraph  | 11              | 2          | FALSE      ← leaf node
  15 | 42         | "Content"  | paragraph  | 12              | 2          | FALSE      ← leaf node
```

### Tree Building Algorithm

```python
def _build_tree_from_headings(content: str) -> list[TreeNode]:
    """Build tree from markdown heading hierarchy.

    Uses a stack-based approach (inspired by PageIndex's build_tree_from_nodes):
    1. Split content on heading boundaries (H1-H6)
    2. For each section, determine heading level
    3. Maintain a stack of ancestor nodes
    4. Pop stack until finding a node at a lower level (= parent)
    5. Attach current node as child of that parent
    6. Push current node onto stack
    """
    sections = re.split(r"(?=^#{1,6}\s)", content, flags=re.MULTILINE)
    root = TreeNode(level=0, title="Document Root", children=[])
    stack = [root]

    for section in sections:
        level = _get_heading_level(section)  # 0 if no heading
        node = TreeNode(level=level, title=_get_heading_text(section), text=section)

        # Pop stack to find parent (first node with level < current)
        while len(stack) > 1 and stack[-1].level >= level:
            stack.pop()

        stack[-1].children.append(node)
        stack.append(node)

    return root
```

### LLM Node Summarization (Phase 2)

For each internal node (has children), generate a summary:

```python
async def _summarize_node(node: TreeNode, model: str) -> str:
    """Generate a summary for an internal tree node.

    Input: concatenated summaries/text of child nodes (truncated to fit context)
    Output: 1-3 sentence summary of the section's content
    """
    child_content = "\n\n".join(
        child.summary if child.is_internal else child.text[:500]
        for child in node.children
    )

    prompt = f"Summarize this document section in 1-3 sentences:\n\n{child_content}"
    return await llm_router.complete(prompt, model=model)
```

Summarization runs bottom-up: leaf nodes have actual content, then each parent is summarized from its children's summaries. This is done during indexing (write path), not during search.

### Tree Search Retrieval (Phase 3)

```
Search query arrives → HybridSearchService.search()
  │
  ├─ Partition content_ids:
  │   tree_indexed = {ids with tree_depth IS NOT NULL}
  │   flat_indexed = {all other ids}
  │
  ├─ Flat path (existing): BM25 + vector → RRF
  │
  ├─ Tree path (new):
  │   1. Load tree structure (summaries only, no leaf text)
  │   2. Format prompt: query + tree JSON
  │   3. LLM call → {"thinking": "...", "node_list": ["10", "12"]}
  │   4. Fetch leaf chunks under selected nodes
  │   5. Score: position in node_list → rank
  │
  └─ Merge: RRF fusion across flat + tree results
```

### Tree Search Prompt Template

```
You are given a question and a tree structure of a document.
Each node contains a node_id, title, and a corresponding summary.
Your task is to find all nodes that are likely to contain the answer.

Question: {query}

Document tree structure:
{tree_json}

Reply in JSON format:
{
  "thinking": "<Your reasoning on which nodes are relevant>",
  "node_list": ["node_id_1", "node_id_2"]
}
```

The tree JSON sent to the LLM contains only summaries and hierarchy — no leaf text. This keeps the prompt small even for large documents. Example:

```json
{
  "node_id": "10",
  "title": "2. Approach",
  "summary": "Describes the training methodology including RL and SFT stages",
  "children": [
    {"node_id": "11", "title": "2.1 RL Training", "summary": "Details the reinforcement learning stage..."},
    {"node_id": "12", "title": "2.2 SFT Stage", "summary": "Describes supervised fine-tuning..."}
  ]
}
```

### Cost Analysis

| Operation | LLM Calls | When |
|-----------|-----------|------|
| Chunk thinning (Phase 1) | 0 | Always (post-processing step) |
| Tree summarization (Phase 2) | ~1 per internal node | During indexing of qualifying docs |
| Tree search (Phase 3) | 1-2 per query per tree-indexed doc | During search queries |

For a typical 30-page arXiv paper with ~15 sections:
- **Indexing**: ~10 summary calls (internal nodes only) × ~500 input tokens = ~5K tokens total
- **Search**: 1 call × ~2K tokens (tree structure) = ~2K tokens per query

For short content (newsletters, RSS, blog posts): **zero additional cost** — flat chunks only.

### Migration Strategy

Phase 2 migration adds nullable columns:

```sql
ALTER TABLE document_chunks ADD COLUMN parent_chunk_id INTEGER;
ALTER TABLE document_chunks ADD COLUMN tree_depth INTEGER;
ALTER TABLE document_chunks ADD COLUMN is_summary BOOLEAN DEFAULT FALSE;

ALTER TABLE document_chunks
    ADD CONSTRAINT fk_chunk_parent
    FOREIGN KEY (parent_chunk_id) REFERENCES document_chunks(id) ON DELETE CASCADE;

CREATE INDEX ix_document_chunks_parent ON document_chunks(parent_chunk_id);
CREATE INDEX ix_document_chunks_tree ON document_chunks(content_id, tree_depth);
```

All columns nullable — no impact on existing rows. Existing flat chunks continue to work with `NULL` tree columns.

### Interaction with Existing Systems

| System | Impact |
|--------|--------|
| BM25 search | No change — tree summary chunks are indexed by BM25 too |
| Vector search | No change — tree summary chunks get embeddings too |
| Reranking | Works on tree search results same as flat results |
| `aca manage backfill-chunks` | Unchanged — only creates flat chunks |
| `aca manage backfill-tree-index` | New command — builds tree indexes for existing qualifying content |
| `aca manage switch-embeddings` | Unchanged — operates on all chunks including tree chunks |
| Search API response | Unchanged — `SearchResult` model already supports `matching_chunks` |
| Frontend | No changes needed — tree search results appear as standard search results |

## Future Work

### Phase 4: Cross-Document Tree Hierarchy

Phases 1-3 build tree indexes **within** a single long document (e.g., an arXiv PDF's internal section hierarchy). But the pipeline itself already has a natural multi-document tree structure:

```
Weekly Digest (root summary)
  ├─ Daily Digest (Monday)
  │   ├─ Newsletter Summary A  → links to Content A (original article)
  │   ├─ Newsletter Summary B  → links to Content B
  │   └─ YouTube Summary C     → links to Content C
  ├─ Daily Digest (Tuesday)
  │   ├─ Newsletter Summary D  → links to Content D
  │   └─ ...
  └─ Theme Analysis
      ├─ Theme 1: "LLM Scaling"   → references multiple Content records
      └─ Theme 2: "Agent Frameworks" → references multiple Content records
```

A digest is a "summary of summaries," and each summary is a "summary of content." This is a tree that spans multiple `content_id` values — architecturally different from the within-content tree in Phases 1-3, but the same `parent_chunk_id` / `tree_depth` / `is_summary` schema supports it.

Enabling cross-document tree search would allow queries like *"What has been said about RAG architectures across the last month?"* to navigate: weekly digest overview → relevant daily digests → individual summaries → original source content — using the same LLM reasoning-based tree traversal.

This pairs naturally with the knowledge graph, which already tracks entity and theme relationships across content via Graphiti/Neo4j. The tree provides structural navigation (what summarized what), while the knowledge graph provides semantic navigation (what relates to what).

**Prerequisites**: Cross-content lineage tracking (partially exists via `digest_items` and summary FK relationships), and tree search that traverses across content records rather than within a single one.

### Phase 5: Topic Deep Research Reviews

Beyond weekly digests, the tree hierarchy enables a new output type: **deep research reviews** that span themes across longer time horizons (monthly, quarterly, or topic-triggered).

A deep research review would:

1. **Start from the knowledge graph** — identify a topic cluster (e.g., "reasoning models") that has accumulated significant coverage across multiple weeks
2. **Traverse the cross-document tree** — collect all summaries, digests, and original content related to that topic, across weekly boundaries
3. **Build a topic-specific tree** — organize the collected content chronologically and thematically into a new hierarchical structure:

```
Deep Research Review: "Reasoning Models" (Q1 2026)
  ├─ Evolution Timeline
  │   ├─ January: DeepSeek-R1 release and analysis
  │   ├─ February: OpenAI o3 benchmarks and community response
  │   └─ March: Open-source reasoning model convergence
  ├─ Technical Analysis
  │   ├─ Training approaches (RL vs SFT vs hybrid)
  │   ├─ Benchmark performance trends
  │   └─ Cost/performance tradeoffs
  ├─ Strategic Implications
  │   ├─ Impact on agent architectures
  │   └─ Enterprise adoption patterns
  └─ Source Materials
      ├─ arXiv papers (tree-indexed, navigable)
      ├─ Newsletter coverage (weekly digest references)
      └─ YouTube technical deep-dives (timestamped)
```

4. **Use tree search for generation** — the LLM navigates this topic tree to produce a comprehensive review, citing specific sources with deep links (page numbers for PDFs, timestamps for videos, section references for articles)

This builds on all previous phases: within-document tree indexes (Phases 2-3) make individual sources navigable, cross-document trees (Phase 4) connect the pipeline hierarchy, and topic deep research reviews (Phase 5) synthesize across both dimensions — themes and time — to produce the kind of longitudinal analysis that no single weekly digest can capture.

**Key insight**: The tree model unifies both the temporal axis (daily → weekly → monthly → quarterly) and the thematic axis (individual articles → theme clusters → cross-theme synthesis) into a single navigable structure that LLM tree search can reason over.
