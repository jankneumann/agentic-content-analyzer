## Context

Users want audio versions of digests without the podcast production workflow.
The podcast system requires script generation and approval, which is heavyweight
for simple audio consumption.

## Goals

- Simple digest → audio pipeline
- Single-voice narration (not conversational)
- No script review required
- Fast generation (~30 seconds for typical digest)
- Share infrastructure with podcast system

## Non-Goals

- Conversational format (use podcasts for that)
- Human review workflow
- Multiple voice options per digest

## Shared Architecture

```
                    ┌─────────────────────────────────────┐
                    │         src/delivery/               │
                    ├─────────────────────────────────────┤
                    │  tts_service.py     (providers)     │
                    │  text_chunker.py    (NEW - shared)  │
                    │  audio_utils.py     (concatenation) │
                    │  dialogue_batcher.py (podcasts)     │
                    └───────────────┬─────────────────────┘
                                    │
           ┌────────────────────────┴────────────────────────┐
           │                                                 │
    ┌──────▼──────────┐                          ┌──────────▼──────────┐
    │  Podcast Audio  │                          │   Audio Digest      │
    ├─────────────────┤                          ├─────────────────────┤
    │ DialogueBatcher │                          │ DigestTextPreparer  │
    │ 2 voices        │                          │ 1 voice             │
    │ Script required │                          │ No script           │
    └─────────────────┘                          └─────────────────────┘
```

## Decisions

### Decision 1: Create Shared TextChunker

**Choice**: Extract chunking logic to reusable `TextChunker` class
**Rationale**:
- Both podcasts and digests need to respect TTS limits
- Podcasts currently handle this per-turn; digests need it for full content
- Single source of truth for provider limits

### Decision 2: Text Preparation Strategy

**Choice**: Convert digest markdown to plain text with SSML markup
**Rationale**:
- Markdown headings become `<break>` pauses
- Lists become natural reading flow
- Code blocks are announced but not read verbatim

### Decision 3: Chunking for Long Content

**Provider Limits**:

| Provider | Limit | Safe Target |
|----------|-------|-------------|
| OpenAI | 4096 | 3800 chars |
| ElevenLabs | 5000 | 4500 chars |
| Google | 5000 | 4500 chars |
| AWS Polly | 3000 | 2800 chars |

**Strategy**: Split at paragraph boundaries, fall back to sentence boundaries

### Decision 4: Add synthesize_long() to TTSService

**Choice**: Extend existing service rather than create new one
**Rationale**:
- Reuses provider abstraction
- Single service for all TTS needs
- Easier to maintain

### Decision 5: Storage

**Choice**: Use unified file storage with "audio-digests" bucket
**Rationale**: Leverages infrastructure from storage proposal

## Comparison: Audio Digest vs Podcast

| Aspect | Audio Digest | Podcast |
|--------|--------------|---------|
| Voices | 1 (narrator) | 2 (Alex + Sam) |
| Script | None | Generated + reviewed |
| Format | Narration | Conversation |
| Time to generate | ~30 seconds | ~5 minutes |
| Use case | Quick listen | Deep engagement |
| Text chunking | TextChunker | DialogueBatcher + TextChunker |

## Risks / Trade-offs

- **Risk**: Lower quality than podcasts
  - Mitigation: Position as "quick listen", not replacement

- **Risk**: Long digests exceed TTS limits
  - Mitigation: TextChunker with seamless concatenation

- **Risk**: Code duplication with podcast audio
  - Mitigation: Shared TextChunker and TTSService.synthesize_long()
