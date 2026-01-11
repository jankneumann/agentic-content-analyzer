# Design: Podcast Generation

Architectural decisions and patterns for the digest-to-podcast audio feature.

## Context

The podcast feature transforms newsletter digests into engaging audio content featuring two expert personas discussing AI/Data news. The design prioritizes human review, cost control, and flexible voice configuration.

## Key Architectural Decisions

### Two-Phase Workflow

**Decision**: Separate script generation from audio synthesis with mandatory human review.

**Rationale**:
- TTS is expensive (~$0.02-$9 per episode depending on provider and length)
- Script quality directly impacts audio quality
- Human reviewers can catch hallucinations, tone issues, or missing context
- Scripts can be revised incrementally without re-generating audio

**Implementation**:
- Phase 1: `PodcastScriptGenerator` → `SCRIPT_PENDING_REVIEW`
- Review: Human approval via `ScriptReviewService`
- Phase 2: `PodcastAudioGenerator` → `COMPLETED` (only for approved scripts)

### Tool-Based Content Retrieval

**Decision**: Provide LLM with lightweight context (metadata + summaries) and tools to fetch full newsletter content on-demand.

**Rationale**:
- Reduces initial context size significantly
- Model decides which newsletters are worth quoting directly
- Enables smarter token budget management
- Works consistently across all lengths

**Tools**:
- `get_newsletter_content(newsletter_id)` - Fetch full text
- `web_search(query)` - External grounding (optional)

### TTS Provider Abstraction

**Decision**: Abstract TTS providers behind a common interface with provider-specific voice mappings.

**Rationale**:
- Different providers offer different cost/quality tradeoffs
- Voice IDs are provider-specific
- Easy to switch providers or add new ones
- Supports A/B testing of voice quality

**Providers**:
| Provider | Cost (15min) | Quality | Use Case |
|----------|--------------|---------|----------|
| OpenAI TTS | ~$0.25 | Good | Default, cost-efficient |
| ElevenLabs | ~$4.50 | Excellent | Premium quality |
| Google TTS | ~$0.06 | Good | Alternative |
| AWS Polly | ~$0.06 | Good | AWS integration |

### Dialogue Batching

**Decision**: Process dialogue turns in batches for TTS efficiency.

**Rationale**:
- Reduces API call overhead
- Allows for pause insertion between turns
- Enables parallel processing of different speakers
- Improves audio consistency

## Data Model

```
Digest (1) ─────┬──────> PodcastScriptRecord (many)
                │             │
                │             └──> Podcast (many, one per voice config)
                │
                └──> Newsletter (many, via period dates)
```

### PodcastScriptRecord

Stores generated scripts with review workflow state:
- `script_json`: Full PodcastScript serialized (sections, dialogue, sources)
- `status`: Workflow state (generating → pending_review → approved/failed)
- `revision_history`: Track all section-level revisions
- `tool_call_count`, `web_search_queries`: Generation metadata

### Podcast

Stores audio output with voice configuration:
- `script_id`: Links to source script
- `audio_url`: Local file path (S3/SharePoint future)
- `voice_provider`, `alex_voice`, `sam_voice`: Voice configuration
- `duration_seconds`, `file_size_bytes`: Audio metadata

## Script Structure

```python
PodcastScript:
  title: str
  length: PodcastLength (brief/standard/extended)
  sections: List[PodcastSection]
    - section_type: intro/strategic/technical/trend/outro
    - title: str
    - dialogue: List[DialogueTurn]
      - speaker: "alex" | "sam"
      - text: str
      - emphasis: excited/thoughtful/concerned/amused
      - pause_after: float (seconds)
    - sources_cited: List[int] (newsletter IDs)
```

## Voice Personas

### Alex Chen (VP of Engineering)
- **Role**: Strategic perspective, organizational impact
- **Style**: Confident, strategic, uses business metaphors
- **Voices**: `alex_male` (onyx/Brian), `alex_female` (nova/Matilda)

### Dr. Sam Rodriguez (Distinguished Engineer)
- **Role**: Technical deep-dives, implementation details
- **Style**: Thoughtful, precise, enthusiastic about solutions
- **Voices**: `sam_male` (fable/Roger), `sam_female` (shimmer/River)

## File Structure

```
src/
├── models/podcast.py              # Enums, Pydantic, SQLAlchemy models
├── processors/
│   ├── podcast_creator.py         # Two-phase orchestration
│   ├── podcast_script_generator.py # LLM script generation
│   └── script_reviser.py          # Section-based revision
├── services/
│   └── script_review_service.py   # Review workflow management
├── delivery/
│   ├── tts_service.py             # TTS provider abstraction
│   ├── audio_generator.py         # Audio synthesis orchestration
│   ├── audio_generator_v2.py      # Updated implementation
│   ├── dialogue_batcher.py        # Batch processing for TTS
│   └── audio_utils.py             # Audio file utilities
└── api/
    ├── script_routes.py           # Script review API
    └── podcast_routes.py          # Audio management API
```

## Future Extensions (Not Implemented)

- Intro/outro music and transitions
- Cloud storage (S3, SharePoint)
- RSS podcast feed generation
- Scheduled generation
- VTT/SRT subtitles
- Voice cloning for custom personas
