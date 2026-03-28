## Architecture

Two-layer storage with clear responsibilities:

```
Reference Extraction (on ingestion or backfill)
    ↓
content_references table (PostgreSQL — source of truth)
    ↓  background job
Resolution: external_id → target_content_id
    ↓  on resolution
Neo4j sync: CITES/CITED_BY edges between Episodes
```

## Data Model

### content_references Table

```sql
CREATE TABLE content_references (
    id              SERIAL PRIMARY KEY,
    source_content_id   INTEGER NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    reference_type      VARCHAR(20) NOT NULL DEFAULT 'cites',  -- ReferenceType StrEnum (app-level validation, NOT PG enum)

    -- Resolution target (one of these populated)
    target_content_id   INTEGER REFERENCES contents(id) ON DELETE SET NULL,
    external_url        TEXT,
    external_id         TEXT,             -- "2301.12345", "10.1038/nature12345"
    external_id_type    VARCHAR(20),      -- ExternalIdType StrEnum (app-level validation, NOT PG enum)

    -- Resolution tracking
    resolution_status   VARCHAR(20) NOT NULL DEFAULT 'unresolved',  -- ResolutionStatus StrEnum (app-level validation)
    resolved_at         TIMESTAMPTZ,

    -- Context (anchored to document chunk model)
    source_chunk_id     INTEGER REFERENCES document_chunks(id) ON DELETE SET NULL,  -- chunk where reference was found
    context_snippet     TEXT,             -- surrounding text (fallback when chunk not yet indexed)
    confidence          FLOAT DEFAULT 1.0, -- extraction confidence (1.0 for structured IDs, lower for heuristic)

    -- Timestamps
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT chk_has_identifier CHECK (external_id IS NOT NULL OR external_url IS NOT NULL),
    CONSTRAINT uq_content_reference UNIQUE (source_content_id, external_id, external_id_type)
);

-- Partial unique index for URL-only references (where external_id IS NULL)
CREATE UNIQUE INDEX uq_content_reference_url
    ON content_references (source_content_id, external_url)
    WHERE external_id IS NULL;

CREATE INDEX ix_content_refs_source ON content_references(source_content_id);
CREATE INDEX ix_content_refs_target ON content_references(target_content_id) WHERE target_content_id IS NOT NULL;
CREATE INDEX ix_content_refs_external_id ON content_references(external_id_type, external_id) WHERE external_id IS NOT NULL;
CREATE INDEX ix_content_refs_unresolved ON content_references(resolution_status) WHERE resolution_status = 'unresolved';
```

### Enums (VARCHAR + Application-Level Validation)

All enum-like fields use `VARCHAR(20)` columns with Python `StrEnum` validation at the application layer. **No PostgreSQL enum types** are created — this avoids the `ALTER TYPE ... ADD VALUE` migration burden when adding new values (see CLAUDE.md gotcha: "PG enum + Python StrEnum mismatch").

```python
class ReferenceType(StrEnum):
    CITES = "cites"              # A cites B (most common)
    EXTENDS = "extends"          # A builds on B
    DISCUSSES = "discusses"      # A discusses/reviews B
    CONTRADICTS = "contradicts"  # A challenges B
    SUPPLEMENTS = "supplements"  # A is full-text for B's abstract (Scholar↔arXiv)

class ExternalIdType(StrEnum):
    ARXIV = "arxiv"              # arXiv paper ID (e.g., "2301.12345")
    DOI = "doi"                  # Digital Object Identifier (e.g., "10.1038/nature12345")
    S2 = "s2"                    # Semantic Scholar paper ID
    PMID = "pmid"                # PubMed ID
    URL = "url"                  # Generic URL (not a structured ID, but tracked)

class ResolutionStatus(StrEnum):
    UNRESOLVED = "unresolved"    # Not yet attempted
    RESOLVED = "resolved"        # Matched to target_content_id
    EXTERNAL = "external"        # Resolved but content not in DB (known external resource)
    FAILED = "failed"            # Resolution attempted but failed
    NOT_FOUND = "not_found"      # Identifier doesn't resolve (404, invalid)
```

SQLAlchemy model uses `sa.String(20)` with `@validates` decorator to enforce enum membership at the ORM layer.

## Reference Extraction Service

### Migration from Existing Code

The existing `src/ingestion/reference_extractor.py` (from Scholar PR #338) provides the foundation. This proposal refactors it to `src/services/reference_extractor.py` and extends it:

- **Preserved**: `ARXIV_PATTERNS`, `DOI_PATTERNS`, `S2_URL_PATTERN` regex patterns, `extract_all()`, `extract_from_contents()`, `ingest_extracted_references()` methods
- **Restructured**: Separate pattern constants → unified `REFERENCE_PATTERNS` dict keyed by `ExternalIdType`
- **Added**: `classify_url()`, `_find_chunk_for_offset()`, `extract_context()`, `extract_from_content()` (DB-aware), `store_references()` (atomic persistence), `ExtractedReference` dataclass
- **Backward compatibility**: `src/ingestion/reference_extractor.py` becomes a re-export shim

### Pattern Matching

```python
REFERENCE_PATTERNS = {
    ExternalIdType.ARXIV: [
        r'arXiv:(\d{4}\.\d{4,5}(?:v\d+)?)',           # arXiv:2301.12345 or arXiv:2301.12345v3
        r'arxiv\.org/abs/(\d{4}\.\d{4,5}(?:v\d+)?)',   # arxiv.org/abs/2301.12345
        r'arxiv\.org/pdf/(\d{4}\.\d{4,5}(?:v\d+)?)',   # arxiv.org/pdf/2301.12345
    ],
    ExternalIdType.DOI: [
        r'doi\.org/(10\.\d{4,9}/[^\s\)]+)',             # doi.org/10.1234/...
        r'DOI:\s*(10\.\d{4,9}/[^\s\)]+)',               # DOI: 10.1234/...
    ],
    ExternalIdType.S2: [
        r'semanticscholar\.org/paper/[^/]*?/([a-f0-9]{40})',  # S2 paper page URL
    ],
}
```

### Extraction Flow

References are anchored to `DocumentChunk` records from the hierarchical document model when available. Each chunk has `id`, `chunk_index`, `section_path` (heading hierarchy), and `chunk_type` — providing structural location context within the source document.

**Important**: `DocumentChunk.start_char`/`end_char` fields exist in the model but are **never populated** by current chunking strategies (all return `None`). Therefore, chunk anchoring uses **chunk_index-based sequential matching**: iterate chunks by `chunk_index`, check if the regex match offset falls within the approximate character range for that chunk (computed from cumulative `len(chunk.text)`). This is best-effort — exact character alignment is not guaranteed when the chunker modifies whitespace or headers.

When chunks haven't been indexed yet (e.g., during initial ingestion before chunking runs), `context_snippet` serves as a fallback. When chunks are later created for previously-unchunked content, a re-anchoring pass updates `source_chunk_id` for references with `source_chunk_id IS NULL`.

```python
class ReferenceExtractor:
    def extract_from_content(self, content: Content, db: Session) -> list[ExtractedReference]:
        """Scan markdown_content and links_json for identifiable references.

        Anchors references to DocumentChunk records when available,
        falling back to context_snippet for unchunked content.
        """
        refs = []

        # Load chunks for this content (may be empty if not yet indexed)
        chunks = db.query(DocumentChunk).filter(
            DocumentChunk.content_id == content.id
        ).order_by(DocumentChunk.chunk_index).all()

        # 1. Structured ID extraction from markdown text
        for id_type, patterns in REFERENCE_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, content.markdown_content):
                    # Anchor to chunk via character offset
                    chunk = _find_chunk_for_offset(chunks, match.start())
                    refs.append(ExtractedReference(
                        external_id=normalize_id(id_type, match.group(1)),
                        external_id_type=id_type,
                        external_url=build_url(id_type, match.group(1)),
                        source_chunk_id=chunk.id if chunk else None,
                        context_snippet=extract_context(content.markdown_content, match) if not chunk else None,
                        confidence=1.0,
                    ))

        # 2. URL classification from links_json
        for url in (content.links_json or []):
            classified = classify_url(url)
            if classified:
                refs.append(classified)
            else:
                refs.append(ExtractedReference(
                    external_id=None,
                    external_id_type=None,
                    external_url=url,
                    confidence=0.5,
                ))

        return deduplicate_refs(refs)

    def store_references(self, content_id: int, refs: list[ExtractedReference], db: Session) -> int:
        """Persist extracted references using INSERT ... ON CONFLICT DO NOTHING.

        Uses atomic conflict handling (not session-level dedup) to avoid
        the autoflush=False gotcha where newly added rows are invisible
        to subsequent SELECTs within the same flush cycle.
        """
        from sqlalchemy.dialects.postgresql import insert

        stored = 0
        for ref in refs:
            stmt = insert(ContentReference).values(
                source_content_id=content_id,
                external_id=ref.external_id,
                external_id_type=ref.external_id_type,
                external_url=ref.external_url,
                source_chunk_id=ref.source_chunk_id,
                context_snippet=ref.context_snippet,
                confidence=ref.confidence,
                reference_type=ref.reference_type or ReferenceType.CITES,
            ).on_conflict_do_nothing(
                constraint="uq_content_reference"
            )
            result = db.execute(stmt)
            stored += result.rowcount
        return stored

    def _find_chunk_for_offset(self, chunks: list[DocumentChunk], char_offset: int) -> DocumentChunk | None:
        """Find the chunk containing this character offset.

        Uses chunk_index-based sequential matching since start_char/end_char
        are not populated by current chunking strategies. Computes approximate
        character ranges from cumulative chunk text lengths.
        """
        cumulative = 0
        for chunk in chunks:
            chunk_len = len(chunk.text) if chunk.text else 0
            if cumulative <= char_offset < cumulative + chunk_len:
                return chunk
            cumulative += chunk_len
        return None
```

### ID Normalization

```python
def normalize_id(id_type: ExternalIdType, raw_id: str) -> str:
    """Normalize identifiers to canonical form."""
    if id_type == ExternalIdType.ARXIV:
        # Strip version suffix for base ID: "2301.12345v3" → "2301.12345"
        return re.sub(r'v\d+$', '', raw_id)
    elif id_type == ExternalIdType.DOI:
        # Lowercase, strip trailing punctuation
        return raw_id.lower().rstrip('.,;:')
    return raw_id
```

## Resolution Service

### Background Job

```python
@register_handler("resolve_references")
async def resolve_references(job_id: int, payload: dict) -> None:
    """Resolve unresolved content_references against the database."""
    content_id = payload.get("content_id")  # Optional: resolve for specific content
    batch_size = payload.get("batch_size", 100)

    with get_db() as db:
        resolver = ReferenceResolver(db)
        if content_id:
            await resolver.resolve_for_content(content_id)
        else:
            await resolver.resolve_batch(batch_size)
```

### Resolution Logic

```python
class ReferenceResolver:
    def resolve_reference(self, ref: ContentReference) -> ResolutionStatus:
        """Attempt to resolve a single reference to a Content record."""

        # 1. Try structured ID lookup via GIN index
        if ref.external_id and ref.external_id_type:
            target = self._find_by_external_id(ref.external_id, ref.external_id_type)
            if target:
                ref.target_content_id = target.id
                ref.resolution_status = ResolutionStatus.RESOLVED
                ref.resolved_at = datetime.now(UTC)
                return ResolutionStatus.RESOLVED

        # 2. Try URL match against source_url
        if ref.external_url:
            target = self._find_by_source_url(ref.external_url)
            if target:
                ref.target_content_id = target.id
                ref.resolution_status = ResolutionStatus.RESOLVED
                ref.resolved_at = datetime.now(UTC)
                return ResolutionStatus.RESOLVED

        # 3. Not found in DB
        return ResolutionStatus.UNRESOLVED

    def _find_by_external_id(self, ext_id: str, id_type: ExternalIdType) -> Content | None:
        """GIN-indexed lookup in metadata_json."""
        key_map = {
            ExternalIdType.ARXIV: "arxiv_id",
            ExternalIdType.DOI: "doi",
            ExternalIdType.S2: "s2_paper_id",
        }
        json_key = key_map.get(id_type)
        if not json_key:
            return None
        return self.db.query(Content).filter(
            Content.metadata_json.op("@>")(cast({json_key: ext_id}, JSONB))
        ).first()
```

### Reverse Resolution (On New Content Ingestion)

When new content is ingested, check if any unresolved references point to it:

```python
def resolve_incoming(self, new_content: Content) -> int:
    """Check unresolved refs that might match newly ingested content."""
    resolved_count = 0

    # Check by arXiv ID
    arxiv_id = (new_content.metadata_json or {}).get("arxiv_id")
    if arxiv_id:
        resolved_count += self._resolve_matching_refs(
            ExternalIdType.ARXIV, arxiv_id, new_content.id
        )

    # Check by DOI
    doi = (new_content.metadata_json or {}).get("doi")
    if doi:
        resolved_count += self._resolve_matching_refs(
            ExternalIdType.DOI, doi, new_content.id
        )

    # Check by source_url
    if new_content.source_url:
        resolved_count += self._resolve_matching_refs_by_url(
            new_content.source_url, new_content.id
        )

    return resolved_count
```

## Auto-Ingest Trigger

Optional: when a reference can't be resolved and the identifier is actionable:

```python
class AutoIngestTrigger:
    """Optionally ingest content for unresolved structured references."""

    def __init__(self, enabled: bool = False, max_depth: int = 1):
        self.enabled = enabled
        self.max_depth = max_depth  # Prevent recursive auto-ingest

    async def maybe_ingest(self, ref: ContentReference) -> Content | None:
        if not self.enabled:
            return None

        # Only auto-ingest for structured IDs, not bare URLs
        if not ref.external_id or not ref.external_id_type:
            return None

        # Check depth via auto_ingest_depth integer (more robust than boolean check):
        # 0 = user-ingested, 1 = first-level auto-ingest, 2+ = recursive
        source = self.db.get(Content, ref.source_content_id)
        source_depth = (source.metadata_json or {}).get("auto_ingest_depth", 0)
        if source_depth >= self.max_depth:
            return None

        # Compute depth for the new content (source_depth + 1)
        new_depth = source_depth + 1

        if ref.external_id_type == ExternalIdType.ARXIV:
            from src.ingestion.orchestrator import ingest_arxiv_paper
            result = await ingest_arxiv_paper(ref.external_id)
            if result and result.content:
                # Tag with auto_ingest_depth for depth tracking
                meta = result.content.metadata_json or {}
                meta["ingestion_mode"] = "auto_ingest"
                meta["auto_ingest_depth"] = new_depth
                result.content.metadata_json = meta
            return result.content if result else None

        elif ref.external_id_type == ExternalIdType.DOI:
            from src.ingestion.orchestrator import ingest_scholar_paper
            result = await ingest_scholar_paper(f"DOI:{ref.external_id}")
            if result and result.content:
                meta = result.content.metadata_json or {}
                meta["ingestion_mode"] = "auto_ingest"
                meta["auto_ingest_depth"] = new_depth
                result.content.metadata_json = meta
            return result.content if result else None

        return None
```

## Neo4j Projection

### Edge Model

```
(Episode:source)-[:CITES {reference_type, confidence, resolved_at}]->(Episode:target)
```

Only resolved references (with both `source_content_id` and `target_content_id`) are projected.

### Sync Pattern

```python
class ReferenceGraphSync:
    """One-way sync: PostgreSQL → Neo4j citation edges.

    Reuses the existing GraphitiClient.driver instance for raw Cypher queries
    instead of creating a separate Neo4j driver (avoids a second connection pool
    outside Graphiti's management).
    """

    def __init__(self, graphiti_client: GraphitiClient):
        self.driver = graphiti_client.driver  # Reuse existing connection pool

    async def sync_reference(self, ref: ContentReference) -> None:
        """Create/update CITES edge when reference is resolved."""
        if ref.resolution_status != ResolutionStatus.RESOLVED:
            return
        if not ref.target_content_id:
            return

        # Find Episode UUIDs for both content items
        source_episode = await self._find_episode(ref.source_content_id)
        target_episode = await self._find_episode(ref.target_content_id)

        if not source_episode or not target_episode:
            return  # Episodes not yet in graph; will sync on next analysis

        await self._create_citation_edge(
            source_uuid=source_episode.uuid,
            target_uuid=target_episode.uuid,
            reference_type=ref.reference_type,
            confidence=ref.confidence,
        )

    async def _create_citation_edge(self, source_uuid, target_uuid, reference_type, confidence):
        """MERGE citation edge in Neo4j."""
        query = """
        MATCH (s:Episode {uuid: $source_uuid})
        MATCH (t:Episode {uuid: $target_uuid})
        MERGE (s)-[r:CITES]->(t)
        SET r.reference_type = $reference_type,
            r.confidence = $confidence,
            r.synced_at = datetime()
        """
        async with self.driver.session() as session:
            await session.run(query, source_uuid=source_uuid, target_uuid=target_uuid,
                            reference_type=reference_type, confidence=confidence)
```

### Graph Queries Enabled

```cypher
-- Most-cited papers across all sources
MATCH (e:Episode)<-[r:CITES]-()
RETURN e.name, count(r) AS citation_count
ORDER BY citation_count DESC LIMIT 20

-- Citation chain from blog post to papers
MATCH path = (blog:Episode)-[:CITES*1..3]->(paper:Episode)
WHERE blog.uuid = $blog_uuid
RETURN path

-- Clusters: papers that are co-cited by the same sources
MATCH (s:Episode)-[:CITES]->(a:Episode),
      (s)-[:CITES]->(b:Episode)
WHERE a <> b
RETURN a.name, b.name, count(s) AS co_citation_count
ORDER BY co_citation_count DESC
```

## Database Migration Notes

### metadata_json: json → jsonb

The `contents.metadata_json` column is currently declared as `sa.JSON()` (PostgreSQL `json` type). GIN indexes and the `@>` containment operator require `jsonb`. The migration MUST:

```sql
ALTER TABLE contents ALTER COLUMN metadata_json TYPE jsonb USING metadata_json::jsonb;
CREATE INDEX IF NOT EXISTS ix_content_metadata_json_gin ON contents USING GIN (metadata_json jsonb_path_ops);
```

This ALTER is idempotent with the arXiv migration — coordinate so only the first migration performs it (check column type before altering). The SQLAlchemy model should also be updated to use `JSONB` instead of `JSON`.

### Queue Handler Registration

The `resolve_references` handler must be registered in `register_all_handlers()` in `src/queue/worker.py`. Add a `_register_reference_handlers()` function following the existing pattern in `_register_content_handlers()`:

```python
def _register_reference_handlers():
    from src.services.reference_resolver import resolve_references_handler
    # Handler auto-registered via @register_handler decorator
```

## Integration Points

### On Content Ingestion (all source types)

After a content record is created/updated, the ingestion service calls:

```python
# In any ingestion service's persist step:
extractor = ReferenceExtractor()
refs = extractor.extract_from_content(content)
ref_service.store_references(content.id, refs)

# Enqueue background resolution
await enqueue_queue_job("resolve_references", {"content_id": content.id})
```

### On Content Ingestion (reverse resolution)

After a new content record is created:

```python
# Check if any existing unresolved refs now point to this content
resolver = ReferenceResolver(db)
resolved_count = resolver.resolve_incoming(new_content)
if resolved_count > 0:
    # Sync newly resolved edges to Neo4j
    await graph_sync.sync_resolved_for_content(new_content.id)
```

### Scholar ↔ arXiv Supplementary Link

When an arXiv paper is ingested and a Scholar record exists with the same arXiv ID (or vice versa), create **two rows** for true bidirectionality (avoids requiring symmetric query logic):

```python
# Create bidirectional SUPPLEMENTS relationship (two rows)
ref_service.create_reference(
    source_content_id=scholar_content.id,
    target_content_id=arxiv_content.id,
    reference_type=ReferenceType.SUPPLEMENTS,
    external_id=arxiv_id,
    external_id_type=ExternalIdType.ARXIV,
    resolution_status=ResolutionStatus.RESOLVED,
)
ref_service.create_reference(
    source_content_id=arxiv_content.id,
    target_content_id=scholar_content.id,
    reference_type=ReferenceType.SUPPLEMENTS,
    external_id=arxiv_id,
    external_id_type=ExternalIdType.ARXIV,
    resolution_status=ResolutionStatus.RESOLVED,
)
```

## Settings

```python
# In src/config/settings.py
reference_extraction_enabled: bool = True          # Extract refs on ingestion
reference_auto_ingest_enabled: bool = False         # Auto-ingest unresolved refs
reference_auto_ingest_max_depth: int = 1            # No recursive auto-ingest
reference_neo4j_sync_enabled: bool = True           # Sync to Neo4j
reference_min_confidence: float = 0.5               # Skip low-confidence URL-only refs
```

## Design Decisions

### Why PostgreSQL as source of truth (not Neo4j)?

1. **Transactional integrity** — FK constraints, unique constraints, atomic updates
2. **Resolution tracking** — status enum, timestamps, batch queries for unresolved refs
3. **API queries** — simple JOINs for "what does this content cite?" without Neo4j dependency
4. **Rebuild safety** — Neo4j can be rebuilt from PG data; PG cannot be rebuilt from Neo4j

### Why one-way sync (PG → Neo4j)?

1. Neo4j is a **read-optimized projection** for graph queries
2. No writes originate in Neo4j — all mutations go through PG
3. Avoids two-source-of-truth consistency issues
4. Matches existing pattern (theme analysis writes to Neo4j but doesn't read back for CRUD)

### Why auto-ingest is opt-in (disabled by default)?

1. Unbounded growth risk — a single blog post could reference 50 papers
2. Cost control — arXiv PDF download + Docling parsing is expensive
3. Rate limiting — auto-ingesting 50 papers hits arXiv rate limits
4. User should consciously enable and configure depth limits

### Why store URL-only references (no structured ID)?

1. Blog posts link to other blogs, docs, GitHub repos — these are valid relationships
2. Lower confidence (0.5) distinguishes them from structured IDs (1.0)
3. Can be resolved later if the URL content is ingested
4. Provides context for the knowledge graph even when not fully resolved

### Why anchor to DocumentChunk instead of text snippet?

1. Chunks are the existing unit of the hierarchical document model — `section_path`, `heading_text`, `start_char`/`end_char` give precise structural location
2. Enables frontend to highlight the exact section where a citation was found
3. Chunk-level anchoring survives content re-parsing (chunk IDs are stable per parse)
4. `context_snippet` is a fallback for content not yet chunked (ingestion happens before chunking)
5. When chunks are later indexed for unchunked content, references can be retroactively anchored

## MCP Tool Surface

All API endpoints and CLI commands are also exposed as MCP tools via `@mcp.tool()` in `src/mcp_server.py`, following the existing pattern where tools delegate to orchestrator functions:

```python
@mcp.tool()
def get_content_references(
    content_id: int,
    direction: str = "outgoing",
) -> str:
    """Get references for a content item.

    Args:
        content_id: Content record ID
        direction: "outgoing" (what this content cites) or "incoming" (what cites this content)

    Returns:
        JSON list of references with resolution status
    """
    # Delegates to reference service
    ...

@mcp.tool()
def extract_references(
    after: str | None = None,
    before: str | None = None,
    source: str | None = None,
    dry_run: bool = False,
    batch_size: int = 50,
) -> str:
    """Extract references from existing content (backfill).

    Args:
        after: ISO date - only process content after this date
        before: ISO date - only process content before this date
        source: Filter by source type (e.g., "rss", "substack")
        dry_run: Preview without storing
        batch_size: Number of content items per batch

    Returns:
        JSON with extraction stats
    """
    ...

@mcp.tool()
def resolve_references(
    batch_size: int = 100,
    auto_ingest: bool = False,
) -> str:
    """Resolve unresolved content references against the database.

    Args:
        batch_size: Number of references to process
        auto_ingest: Trigger ingestion for unresolved structured IDs.
            Only effective when reference_auto_ingest_enabled setting is True.
            If the setting is False, this parameter is ignored.

    Returns:
        JSON with resolution stats
    """
    ...

@mcp.tool()
def ingest_reference(
    reference_id: int,
) -> str:
    """Ingest content for a specific unresolved reference (ad-hoc).

    Args:
        reference_id: content_references row ID

    Returns:
        JSON with ingestion result and resolution status
    """
    ...
```

This ensures agentic workflows (MCP clients, AI assistants) can discover citations, trigger resolution, and ad-hoc ingest papers — the same capabilities as the API and CLI.
