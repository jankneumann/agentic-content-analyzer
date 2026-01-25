# Digest Review System Documentation

## Overview

The review system provides human-in-the-loop quality control for AI-generated digests before email delivery. It features an AI-powered interactive revision interface that enables conversational refinement of digest content.

**Key Features:**
- **Interactive AI Revision**: Multi-turn conversational refinement with Claude
- **Token-Efficient Context**: Loads condensed summaries, fetches full content on-demand
- **Tool Use**: LLM can call tools to retrieve specific content when needed
- **Complete Audit Trail**: Full conversation history stored for transparency
- **Service Layer Architecture**: Web-ready design for future UI integration
- **Batch & Interactive Modes**: Quick approve/reject or detailed revision sessions

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────┐
│                    CLI Interface                         │
│              (scripts/review_digest.py)                  │
│  - List pending reviews                                  │
│  - View digest content                                   │
│  - Interactive revision session                          │
│  - Quick approve/reject                                  │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│              Review Service Layer                        │
│          (src/services/review_service.py)                │
│  - Business logic for review operations                  │
│  - Session management                                    │
│  - Status transitions                                    │
│  - Revision history tracking                             │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│              Digest Reviser (AI Agent)                   │
│        (src/processors/digest_reviser.py)                │
│  - Context loading (digest + summaries + themes)         │
│  - LLM-powered revision with tool use                    │
│  - On-demand content fetching                            │
│  - Section-level content updates                         │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│                   Data Layer                             │
│  - PostgreSQL (digests, summaries, contents)             │
│  - Revision history (JSON)                               │
│  - Audit trail                                           │
└─────────────────────────────────────────────────────────┘
```

### Design Patterns

**Service Layer Pattern**: Business logic separated from presentation (CLI), enabling reuse for future web UI:
- `ReviewService` handles all review operations
- CLI scripts only handle user interaction and display
- Same service can be called from FastAPI endpoints

**AI Agent with Tool Use**: DigestReviser uses Anthropic SDK tool calling pattern:
- Loads efficient context (summaries, not raw content)
- LLM can call `fetch_content(content_id)` when details needed
- LLM can call `search_content(query)` to find relevant content
- Reduces initial token usage, retrieves details on-demand

## Database Schema

### New Status Values

Added to `DigestStatus` enum in `src/models/digest.py`:

```python
class DigestStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    PENDING_REVIEW = "pending_review"  # NEW: Awaiting human review
    APPROVED = "approved"              # NEW: Approved for delivery
    REJECTED = "rejected"              # NEW: Rejected (won't deliver)
    DELIVERED = "delivered"
```

### New Fields

Added to `Digest` model:

| Field | Type | Purpose |
|-------|------|---------|
| `reviewed_by` | String(200), nullable | Username/email of reviewer |
| `review_notes` | Text, nullable | Optional feedback/notes |
| `reviewed_at` | DateTime(timezone), nullable | When review completed |
| `revision_count` | Integer, default=0 | Number of revisions made |
| `revision_history` | JSON, nullable | Complete conversation audit trail |

### Revision History Structure

The `revision_history` JSON field stores complete audit trail of all review sessions:

```json
{
  "sessions": [
    {
      "session_id": "uuid-string",
      "started_at": "2025-12-28T10:00:00Z",
      "ended_at": "2025-12-28T10:15:00Z",
      "reviewer": "user@example.com",
      "turns": [
        {
          "turn": 1,
          "user_input": "Make executive summary more concise",
          "ai_response": "I've condensed the summary to focus on the top 3 themes",
          "section_modified": "executive_overview",
          "change_accepted": true,
          "timestamp": "2025-12-28T10:05:00Z",
          "tools_called": ["search_content"]
        },
        {
          "turn": 2,
          "user_input": "Add technical details about RAG architecture",
          "ai_response": "Added detailed RAG implementation patterns from content items 3 and 7",
          "section_modified": "technical_developments",
          "change_accepted": true,
          "timestamp": "2025-12-28T10:12:00Z",
          "tools_called": ["fetch_content", "fetch_content"]
        }
      ],
      "final_action": "approved"
    }
  ]
}
```

### Status Flow

```
PENDING → GENERATING → COMPLETED → PENDING_REVIEW
                                        ↓
                        ┌───────────────┼─────────────┐
                        ↓               ↓             ↓
        [Interactive Revision]      APPROVED      REJECTED
                        ↓               ↓
                 PENDING_REVIEW     DELIVERED
                 (continue editing)
```

**Notes:**
- Digests stay in `PENDING_REVIEW` during interactive revision
- Only `APPROVED` digests are eligible for email delivery
- `REJECTED` digests are archived but not delivered
- Digest generation scripts default to `PENDING_REVIEW` status

## CLI Usage Guide

### Installation

Review system is included with the main project installation. No additional setup required.

### Basic Commands

#### List Pending Reviews

```bash
python -m scripts.review_digest --list
```

Output:
```
╔════╦════════╦═══════════════════════════════════╦═════════════════════╦═══════╗
║ ID ║  Type  ║              Period               ║      Created        ║ Count ║
╠════╬════════╬═══════════════════════════════════╬═════════════════════╬═══════╣
║ 42 ║ DAILY  ║ 2025-12-27 to 2025-12-27          ║ 2025-12-28 08:00:00 ║   15  ║
║ 41 ║ WEEKLY ║ 2025-12-21 to 2025-12-27          ║ 2025-12-28 07:00:00 ║   87  ║
╚════╩════════╩═══════════════════════════════════╩═════════════════════╩═══════╝

2 digests pending review
```

#### View Digest

```bash
# View in markdown (default)
python -m scripts.review_digest --id 42 --view

# View as HTML
python -m scripts.review_digest --id 42 --view --format html

# View as plain text
python -m scripts.review_digest --id 42 --view --format text
```

#### Quick Approve/Reject (Batch Mode)

For simple cases without revision:

```bash
# Approve digest
python -m scripts.review_digest --id 42 --action approve --reviewer "user@example.com"

# Reject with notes
python -m scripts.review_digest --id 42 --action reject \
  --notes "Too technical for executive audience" \
  --reviewer "user@example.com"
```

### Interactive Revision Session

The most powerful feature - conversational refinement with AI:

```bash
python -m scripts.review_digest --id 42 --revise-interactive --reviewer "user@example.com"
```

#### Session Walkthrough

**1. Context Loading**

```
Loading digest #42 and context...
✓ Loaded 15 summaries, 1 theme analysis (15 content items available for on-demand fetching)
```

The system loads:
- The current digest (all sections)
- Content summaries (condensed, ~200 words each)
- Theme analysis (cross-content patterns)
- Content IDs (for on-demand fetching)

**2. Initial Digest Display**

```
================================================================================
CURRENT DIGEST
================================================================================

# AI Advances - December 27, 2025

## Executive Overview
[Current executive summary text...]

## Strategic Insights
[Current strategic insights...]

[... full digest content ...]
```

**3. Interactive Revision Loop**

```
================================================================================
AI REVISION ASSISTANT
================================================================================
Commands: Type your revision request, 'show' to redisplay, 'done' to finish

You: Make executive summary more concise and focus on top 3 themes

AI: [Analyzing request with full context...]

AI: I've condensed the executive summary to focus on the three most significant themes:
1. RAG architecture maturation
2. LLM cost optimization
3. Agentic workflow adoption

The new summary is 40% shorter while maintaining strategic impact.

================================================================================
PROPOSED CHANGE TO: executive_overview
================================================================================
[New executive summary focusing on top 3 themes - 150 words instead of 250]
================================================================================

Keep this change? [yes/no/edit]: yes
✓ Change applied

You: Add more technical details about the RAG patterns mentioned

AI: [Analyzing request with full context...]
[Calling tool: fetch_content(content_id=7)]
[Calling tool: fetch_content(content_id=12)]

AI: I've added detailed technical information about RAG implementation patterns,
including hybrid search strategies and chunking approaches from content items 7 and 12.

================================================================================
PROPOSED CHANGE TO: technical_developments
================================================================================
### RAG Architecture Evolution

**Hybrid Search Strategies:**
- Dense retrieval (embeddings) + sparse retrieval (BM25)
- Reranking with cross-encoders for accuracy
- Query decomposition for complex questions

[... detailed technical content ...]
================================================================================

Keep this change? [yes/no/edit]: yes
✓ Change applied

You: done
```

**4. Final Review**

```
================================================================================
REVISED DIGEST (FINAL)
================================================================================

[Full digest with all applied changes]

Action [approve/save-draft/discard]: approve
✓ Digest #42 approved for delivery
```

**5. Session Complete**

```
Review Summary:
- Session ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
- Revisions: 2
- Tools called: 2x fetch_content, 1x search_content
- Status: APPROVED
- Reviewer: user@example.com
- Reviewed at: 2025-12-28 10:15:23 UTC
```

### Interactive Commands

During an interactive session:

| Command | Action |
|---------|--------|
| `<your request>` | Describe desired revision |
| `show` | Redisplay current digest |
| `done` | Exit revision loop |

After revisions:

| Action | Result |
|--------|--------|
| `approve` | Set status to APPROVED, ready for delivery |
| `save-draft` | Keep in PENDING_REVIEW, save changes |
| `discard` | Discard all changes, revert to original |

## AI-Powered Revision

### How It Works

1. **Context Assembly**: Loads token-efficient context
   - Digest content (all sections)
   - Content summaries (~200 words each)
   - Theme analysis
   - Content IDs for tool use

2. **User Request**: Natural language revision request
   - "Make executive summary shorter"
   - "Add technical details about RAG"
   - "Focus more on strategic implications"

3. **LLM Processing**: Claude analyzes request and context
   - Understands which section to modify
   - Determines if more detail needed
   - Calls tools if necessary

4. **Tool Use** (on-demand):
   - `fetch_content(content_id)`: Get full content text
   - `search_content(query)`: Find relevant content

5. **Revision Generation**: LLM produces updated content
   - Modified section with changes
   - Explanation of what changed and why
   - Confidence score

6. **Human Approval**: User reviews proposed change
   - Accept: Apply to digest, increment revision_count
   - Reject: Discard, try different approach
   - Edit: Provide more specific guidance

### Tool Use Examples

**Example 1: Fetch Content**

```
User: Add details about the new OpenAI model mentioned

AI: [Calls fetch_content(content_id=5)]
    [Retrieves full content about OpenAI GPT-5 announcement]

AI: I've added detailed information about GPT-5's capabilities,
    pricing, and availability based on content #5 from OpenAI Weekly.
```

**Example 2: Search Content**

```
User: Include more about agent frameworks

AI: [Calls search_content(query="agent frameworks")]
    [Finds 3 content items discussing LangChain, CrewAI, AutoGen]

AI: I found 3 content items covering agent frameworks. I've added a new
    section comparing LangChain, CrewAI, and AutoGen based on those sources.
```

### Token Efficiency

**Initial Context** (~15K tokens for 15 content items):
- Digest: ~2K tokens
- 15 summaries @ 500 tokens each: ~7.5K tokens
- Theme analysis: ~3K tokens
- Tool definitions: ~1K tokens
- System prompt: ~1.5K tokens

**With On-Demand Fetching** (when needed):
- Tool call for full content: +5K tokens (only when needed)
- Tool call for search: +2K tokens (condensed results)

**Comparison to Loading All Content Upfront**:
- Without tool use: ~150K tokens (15 content items x 10K tokens each)
- With tool use: ~15K base + ~5-10K per fetch = 20-25K average
- **Savings: ~83% token reduction**

### Model Configuration

Digest revision uses the `digest_revision` model step:

```yaml
# src/config/model_registry.yaml
default_models:
  digest_revision: claude-sonnet-4-5  # High quality for revisions
```

Override with environment variable:
```bash
MODEL_DIGEST_REVISION=claude-opus-4-5  # Use Opus for highest quality
```

## API Reference (ReviewService)

The `ReviewService` class provides all review operations for both CLI and future web UI.

### Class: ReviewService

**Location**: `src/services/review_service.py`

**Initialization**:
```python
from src.services.review_service import ReviewService

service = ReviewService(model_config=None)  # Uses default config if None
```

### Methods

#### list_pending_reviews()

Get all digests awaiting review.

```python
async def list_pending_reviews() -> List[Digest]
```

**Returns**: List of Digest objects with status `PENDING_REVIEW`

**Example**:
```python
digests = await service.list_pending_reviews()
for digest in digests:
    print(f"{digest.id}: {digest.title} ({digest.content_count} content items)")
```

#### get_digest(digest_id)

Load specific digest by ID.

```python
async def get_digest(digest_id: int) -> Optional[Digest]
```

**Parameters**:
- `digest_id`: Database ID of digest

**Returns**: Digest object or None if not found

#### start_revision_session(digest_id, session_id, reviewer)

Initialize interactive revision session.

```python
async def start_revision_session(
    digest_id: int,
    session_id: str,
    reviewer: str
) -> RevisionContext
```

**Parameters**:
- `digest_id`: Digest to revise
- `session_id`: Unique session identifier (UUID)
- `reviewer`: Username/email of reviewer

**Returns**: RevisionContext with digest, summaries, themes

**Raises**: ValueError if digest status is not reviewable

#### process_revision_turn(context, user_input, conversation_history, session_id)

Process single revision request.

```python
async def process_revision_turn(
    context: RevisionContext,
    user_input: str,
    conversation_history: List[dict],
    session_id: str
) -> RevisionResult
```

**Parameters**:
- `context`: RevisionContext from start_revision_session()
- `user_input`: User's revision request
- `conversation_history`: List of previous turns
- `session_id`: Current session ID

**Returns**: RevisionResult with revised content and explanation

#### apply_revision(digest_id, section, new_content)

Apply revision to digest.

```python
async def apply_revision(
    digest_id: int,
    section: str,
    new_content: Any,
    increment_count: bool = True
) -> Digest
```

**Parameters**:
- `digest_id`: Digest to update
- `section`: Section name (e.g., "executive_overview")
- `new_content`: New content for section
- `increment_count`: Whether to increment revision_count

**Returns**: Updated Digest object

#### finalize_review(digest_id, action, revision_history, reviewer, review_notes)

Complete review process.

```python
async def finalize_review(
    digest_id: int,
    action: str,  # "approve", "reject", or "save-draft"
    revision_history: dict,
    reviewer: str,
    review_notes: Optional[str] = None
) -> Digest
```

**Parameters**:
- `digest_id`: Digest to finalize
- `action`: Final action (approve/reject/save-draft)
- `revision_history`: Complete session history
- `reviewer`: Username/email
- `review_notes`: Optional notes

**Returns**: Updated Digest object

**Raises**: ValueError if action is invalid

#### quick_review(digest_id, action, reviewer, notes)

Quick approve/reject without revision.

```python
async def quick_review(
    digest_id: int,
    action: str,  # "approve" or "reject"
    reviewer: str,
    notes: Optional[str] = None
) -> Digest
```

**Parameters**:
- `digest_id`: Digest to review
- `action`: approve or reject
- `reviewer`: Username/email
- `notes`: Optional review notes

**Returns**: Updated Digest with new status

## Future Web UI Integration

The service layer architecture enables easy web UI integration:

### Planned FastAPI Endpoints

```python
# src/api/routes/review.py (FUTURE)

from fastapi import APIRouter, WebSocket
from src.services.review_service import ReviewService

router = APIRouter(prefix="/api/review")
service = ReviewService()

@router.get("/digests/pending")
async def list_pending():
    """List all digests pending review."""
    digests = await service.list_pending_reviews()
    return {"digests": [d.to_dict() for d in digests]}

@router.get("/digests/{digest_id}")
async def get_digest(digest_id: int):
    """Get specific digest."""
    digest = await service.get_digest(digest_id)
    return digest.to_dict()

@router.websocket("/ws/revise/{digest_id}")
async def websocket_revision(websocket: WebSocket, digest_id: int):
    """Real-time interactive revision via WebSocket."""
    await websocket.accept()

    # Initialize session
    session_id = str(uuid.uuid4())
    context = await service.start_revision_session(
        digest_id, session_id, "web-user"
    )

    # Interactive loop
    while True:
        user_input = await websocket.receive_text()

        result = await service.process_revision_turn(
            context, user_input, [], session_id
        )

        await websocket.send_json({
            "section": result.section_modified,
            "content": result.revised_content,
            "explanation": result.explanation
        })

@router.post("/digests/{digest_id}/approve")
async def approve(digest_id: int, data: dict):
    """Approve digest for delivery."""
    return await service.finalize_review(
        digest_id, "approve", data["history"], data["reviewer"]
    )
```

### React Component Example

```typescript
// Future web UI component
function DigestReviewer({ digestId }: { digestId: number }) {
  const [messages, setMessages] = useState([]);
  const ws = useWebSocket(`/ws/revise/${digestId}`);

  const sendRevision = (userInput: string) => {
    ws.send(userInput);
  };

  ws.onmessage = (event) => {
    const result = JSON.parse(event.data);
    setMessages([...messages, {
      section: result.section,
      content: result.content,
      explanation: result.explanation
    }]);
  };

  return (
    <div>
      <DigestDisplay digest={digest} />
      <RevisionChat messages={messages} onSend={sendRevision} />
      <ApprovalButtons onApprove={handleApprove} onReject={handleReject} />
    </div>
  );
}
```

## Best Practices

### When to Use Interactive Revision vs. Quick Approve

**Use Interactive Revision When**:
- Digest needs content improvements
- Want to add/remove specific details
- Need to adjust tone or focus
- Multiple sections need refinement
- Learning what makes good digests

**Use Quick Approve When**:
- Digest quality is already excellent
- Only minor issues (can note for next time)
- Urgent delivery needed
- Establishing baseline quality

**Use Quick Reject When**:
- Fundamental issues requiring full regeneration
- Wrong digest type generated
- Missing critical content
- Technical generation failure

### Revision Request Tips

**Good Revision Requests** (specific, actionable):
- ✅ "Make executive summary more concise, focus on top 3 themes"
- ✅ "Add technical implementation details about RAG architecture"
- ✅ "Include strategic implications for leadership decision-making"
- ✅ "Expand emerging trends section with historical context"

**Poor Revision Requests** (vague, subjective):
- ❌ "Make it better"
- ❌ "Fix the content"
- ❌ "I don't like this"
- ❌ "Change it"

**Multi-Turn Strategies**:
1. Start broad: "Make executive summary shorter"
2. Then specific: "Add details about cost optimization mentioned in content item 7"
3. Refine further: "Emphasize ROI implications for leadership"

### Review Workflow Recommendations

**Daily Digest Review**:
- Review same day as generation
- Use quick approve for routine quality
- Interactive revision for special topics
- Build muscle memory for quality standards

**Weekly Digest Review**:
- Allow 1-2 revision sessions
- More thorough review (higher impact)
- Use historical context verification
- Check theme consistency with previous weeks

**Team Review Process**:
1. Junior reviewer: Initial review, flag issues
2. Senior reviewer: Interactive revision, approve/reject
3. Track reviewer performance via `reviewed_by` field
4. Review revision history to learn patterns

## Troubleshooting

### Common Issues

**Issue: "Digest X not reviewable"**

**Cause**: Digest status is not `PENDING_REVIEW`, `APPROVED`, or `REJECTED`

**Solution**:
```python
# Check digest status
digest = await service.get_digest(digest_id)
print(f"Status: {digest.status}")

# If DELIVERED, cannot review
# If GENERATING, wait for completion
```

**Issue: Tool calls failing during revision**

**Cause**: Content ID not in current digest period

**Solution**: LLM will receive error message and work with available context. If critical, manually add content to digest period.

**Issue: Revision session timeout**

**Cause**: Long pause in interactive session

**Solution**: Use `save-draft` to preserve changes, start new session

**Issue: Conflicting revisions from multiple reviewers**

**Cause**: Two people reviewing same digest simultaneously

**Solution**: Check `reviewed_by` and `reviewed_at` before starting session. Implement locking in future web UI.

## Metrics and Analytics

### Tracking Review Performance

Query revision history for insights:

```python
# Average revisions per digest
SELECT AVG(revision_count) FROM digests WHERE status = 'APPROVED';

# Most common revision types
SELECT
    json_array_elements(revision_history->'sessions')->'turns'->>'section_modified' as section,
    COUNT(*) as frequency
FROM digests
WHERE revision_history IS NOT NULL
GROUP BY section
ORDER BY frequency DESC;

# Reviewer productivity
SELECT
    reviewed_by,
    COUNT(*) as digests_reviewed,
    AVG(revision_count) as avg_revisions,
    SUM(CASE WHEN status = 'APPROVED' THEN 1 ELSE 0 END) as approved,
    SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) as rejected
FROM digests
WHERE reviewed_by IS NOT NULL
GROUP BY reviewed_by;
```

### Cost Tracking

Calculate revision costs:

```python
from src.services.review_service import ReviewService

service = ReviewService()

# After revision session
cost = service.calculate_revision_cost()
print(f"Session cost: ${cost:.4f}")
```

## Migration

The review system was added via database migration. To apply:

```bash
# Apply migration
alembic upgrade head

# Verify new columns exist
psql -d newsletters -c "\d digests"
# Should show: reviewed_by, review_notes, reviewed_at, revision_count, revision_history

# Verify new enum values
psql -d newsletters -c "SELECT unnest(enum_range(NULL::digeststatus));"
# Should include: pending_review, approved, rejected
```

**Backward Compatibility**: Existing digests remain in their current status. New digests default to `PENDING_REVIEW`.

## Security Considerations

### Reviewer Authentication

**Current**: CLI uses `--reviewer` flag (honor system)

**Future Web UI**: Integrate with authentication system
- OAuth/OIDC for identity
- Role-based access control (RBAC)
- Audit log of who reviewed what

### Revision History Integrity

**Storage**: Revision history is append-only JSON in database

**Protection**:
- Cannot modify past sessions (only add new ones)
- Timestamps are server-generated (not client-provided)
- Tool calls are logged automatically

**Compliance**: Full audit trail for regulatory requirements

---

## Audio Digests

Audio Digests provide single-voice narration of digest content, bypassing the full podcast workflow. This is ideal for users who want to listen to digest content without the conversational format of podcasts.

### Overview

Unlike the podcast workflow (which generates a scripted dialogue between two hosts), Audio Digests:
- Use a single narration voice
- Convert directly from digest markdown to speech
- Skip the script generation and review stages
- Support multiple voices and playback speeds

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    API Endpoints                         │
│              (src/api/audio_digest_routes.py)            │
│  - POST /digests/{id}/audio (generate)                   │
│  - GET /audio-digests/ (list all)                        │
│  - GET /audio-digests/statistics                         │
│  - GET /audio-digests/{id}/stream (play audio)           │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│            AudioDigestGenerator                          │
│      (src/processors/audio_digest_generator.py)          │
│  - Loads digest markdown content                         │
│  - Uses DigestTextPreparer for text processing           │
│  - Uses TTSService for synthesis                         │
│  - Handles chunking for long content                     │
└──────────────────┬──────────────────────────────────────┘
                   │
          ┌────────┴────────┐
          ▼                 ▼
┌───────────────────┐ ┌───────────────────┐
│  DigestTextPreparer │ │   TextChunker     │
│  - Strip code blocks │ │  - Split at sentence │
│  - Add SSML pauses  │ │  - Respect provider  │
│  - Format headings  │ │    character limits  │
└───────────────────┘ └───────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│               TTS Service                                │
│          (src/delivery/tts_service.py)                   │
│  - OpenAI TTS (default)                                  │
│  - ElevenLabs (optional)                                 │
│  - Synthesize chunks and concatenate                     │
└─────────────────────────────────────────────────────────┘
```

### TTS Character Limits & Chunking

TTS providers have character limits per API call. The `TextChunker` class automatically handles this:

| Provider | Character Limit | Notes |
|----------|-----------------|-------|
| OpenAI TTS | 4,096 characters | ~3 minutes of audio per chunk |
| ElevenLabs | 5,000 characters | SSML support available |

**Chunking Behavior:**
1. Content under the limit → Single API call
2. Content over the limit → Split at sentence/paragraph boundaries
3. Multiple chunks → Synthesized separately, then concatenated via ffmpeg

**Example:** A 10,000-character digest with OpenAI:
- Split into 3 chunks (~3,300 chars each)
- Each chunk synthesized separately
- Final MP3 concatenated from all chunks

### API Reference

#### Create Audio Digest

```http
POST /api/v1/digests/{digest_id}/audio
Content-Type: application/json

{
  "voice": "nova",
  "speed": 1.0,
  "provider": "openai"
}
```

**Response:**
```json
{
  "id": 42,
  "digest_id": 123,
  "voice": "nova",
  "speed": 1.0,
  "provider": "openai",
  "status": "pending",
  "created_at": "2025-01-15T10:00:00Z"
}
```

Generation happens in a background task. Poll the status or check the Audio Digests list.

#### List All Audio Digests

```http
GET /api/v1/audio-digests/?status=completed&voice=nova&limit=50
```

**Query Parameters:**
- `status`: Filter by status (pending, processing, completed, failed)
- `voice`: Filter by voice preset
- `provider`: Filter by TTS provider
- `limit`, `offset`: Pagination
- `sort_by`, `sort_order`: Sorting

#### Get Statistics

```http
GET /api/v1/audio-digests/statistics
```

**Response:**
```json
{
  "total": 25,
  "generating": 2,
  "completed": 20,
  "failed": 3,
  "total_duration_seconds": 3600.5,
  "by_voice": {"nova": 15, "onyx": 10},
  "by_provider": {"openai": 25}
}
```

#### Stream Audio

```http
GET /api/v1/audio-digests/{id}/stream
```

Returns the MP3 file with `Content-Type: audio/mpeg`.

#### Delete Audio Digest

```http
DELETE /api/v1/audio-digests/{id}
```

### Voice Presets

Available voices for OpenAI TTS:

| Voice | Description | Best For |
|-------|-------------|----------|
| `nova` (default) | Warm female | General narration |
| `onyx` | Deep male | Professional content |
| `echo` | Natural male | Conversational tone |
| `shimmer` | Expressive female | Engaging content |
| `alloy` | Neutral | Technical content |
| `fable` | Storytelling | Narrative content |

### Usage Examples

**Python (direct):**
```python
from src.processors.audio_digest_generator import AudioDigestGenerator

generator = AudioDigestGenerator(
    provider="openai",
    voice="nova",
    speed=1.0,
)

audio_digest = await generator.generate(
    digest_id=123,
    progress_callback=lambda cur, total, msg: print(f"{cur}% - {msg}")
)
print(f"Audio URL: {audio_digest.audio_url}")
```

**API (via frontend or curl):**
```bash
# Generate audio digest
curl -X POST "http://localhost:8000/api/v1/digests/123/audio" \
  -H "Content-Type: application/json" \
  -d '{"voice": "nova", "speed": 1.25}'

# Check status
curl "http://localhost:8000/api/v1/audio-digests/42"

# Stream audio
curl "http://localhost:8000/api/v1/audio-digests/42/stream" -o digest.mp3
```

### Configuration

Settings in `.env`:

```bash
# Default voice for audio digests
AUDIO_DIGEST_DEFAULT_VOICE=nova

# Default speed (0.25 to 4.0)
AUDIO_DIGEST_SPEED=1.0

# Default provider (openai or elevenlabs)
AUDIO_DIGEST_PROVIDER=openai

# For ElevenLabs (optional)
ELEVENLABS_API_KEY=your-api-key
```

### Database Schema

The `audio_digests` table stores generation metadata:

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `digest_id` | Integer | FK to digests table |
| `voice` | String | Voice preset used |
| `speed` | Float | Playback speed |
| `provider` | String | TTS provider |
| `status` | Enum | pending, processing, completed, failed |
| `audio_url` | String | Storage path to MP3 file |
| `duration_seconds` | Float | Estimated duration |
| `file_size_bytes` | Integer | File size |
| `text_char_count` | Integer | Input text length |
| `chunk_count` | Integer | Number of TTS chunks |
| `error_message` | Text | Error details if failed |
| `created_at` | DateTime | Generation start time |
| `completed_at` | DateTime | Generation completion time |

### Comparison: Audio Digests vs. Podcasts

| Aspect | Audio Digest | Podcast |
|--------|--------------|---------|
| **Input** | Digest markdown | Approved podcast script |
| **Voices** | Single voice | Two voices (Alex & Sam) |
| **Workflow** | Direct generation | Script → Review → Audio |
| **Duration** | ~5-10 minutes | ~15-30 minutes |
| **Use Case** | Quick listen | In-depth discussion |
| **Review Required** | No | Yes (script review) |

---

## Conclusion

The review system provides flexible, AI-powered quality control for digest content. Key benefits:

✅ **Interactive AI Revision**: Conversational refinement with Claude
✅ **Token Efficiency**: On-demand content fetching reduces costs by 83%
✅ **Complete Audit Trail**: Full transparency of all changes
✅ **Web-Ready Architecture**: Service layer enables future UI
✅ **Batch & Interactive Modes**: Flexible workflow options

For questions or issues, see:
- [Development Guide](DEVELOPMENT.md) for commands
- [Model Configuration](MODEL_CONFIGURATION.md) for LLM settings
- GitHub issues for bug reports
