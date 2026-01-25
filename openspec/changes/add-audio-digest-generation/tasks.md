# Tasks: Audio Digest Generation

## Phase 1: Shared Text Chunking Utility (Benefits Podcasts Too)

- [x] 1.1 Create `src/delivery/text_chunker.py`
  - Generic text splitting at paragraph/sentence boundaries
  - Configurable max length per provider (OpenAI: 4096, ElevenLabs: 5000)
  - SSML pause injection between chunks
- [x] 1.2 Add `TextChunk` dataclass with text, position, estimated_duration
- [x] 1.3 Add unit tests for chunking edge cases
- [ ] 1.4 Update `DialogueBatcher` to use `TextChunker` for long turns

## Phase 2: TTSService Long-Form Synthesis

- [x] 2.1 Add `synthesize_long()` method to `TTSService`
  - Accept text of any length
  - Use TextChunker to split
  - Synthesize each chunk and concatenate
- [ ] 2.2 Add `synthesize_long_stream()` for progressive output
- [x] 2.3 Handle provider-specific limits automatically
- [x] 2.4 Add unit tests for long-form synthesis

## Phase 3: Data Model

- [x] 3.1 Create `AudioDigest` SQLAlchemy model
  - `id`, `digest_id`, `voice`, `status`, `audio_url`
  - `duration_seconds`, `file_size_bytes`, `created_at`
  - `text_char_count`, `chunk_count` (for analytics)
- [x] 3.2 Create Alembic migration for `audio_digests` table
- [x] 3.3 Create Pydantic schemas for API
  - AudioDigestCreate, AudioDigestResponse, AudioDigestListItem
  - AudioDigestStatistics (for frontend stats cards)

## Phase 4: Text Preparation

- [x] 4.1 Create `DigestTextPreparer` class
  - Extract text from digest markdown
  - Add natural pauses between sections
  - Handle headings as section breaks
- [x] 4.2 Add SSML markup for supported providers
  - `<break>` tags between sections
  - Emphasis for headings
- [x] 4.3 Handle code blocks (skip or announce)
- [x] 4.4 Estimate duration from text length

## Phase 5: Audio Generation

- [x] 5.1 Create `AudioDigestGenerator` class
  - Accept digest_id and voice configuration
  - Use `DigestTextPreparer` for text
  - Use `TTSService.synthesize_long()` for audio
  - Save to unified file storage ("audio-digests" bucket)
- [ ] 5.2 Add progress callback for long generations
- [x] 5.3 Handle failures gracefully (partial generation)

## Phase 6: API Endpoints

- [x] 6.1 Create `POST /api/v1/digests/{digest_id}/audio`
  - Generate audio digest (background task)
  - Return audio digest record with status
- [x] 6.2 Create `GET /api/v1/digests/{digest_id}/audio`
  - Get existing audio digest(s) for a digest
- [x] 6.3 Create `GET /api/v1/audio-digests/{id}`
  - Get specific audio digest details
- [x] 6.4 Create `GET /api/v1/audio-digests/{id}/stream`
  - Stream audio file (via unified file storage)
- [x] 6.5 Create `GET /api/v1/audio-digests/`
  - List all audio digests with filtering
- [x] 6.6 Create `GET /api/v1/audio-digests/statistics`
  - Get counts, durations, breakdowns by voice/provider
- [x] 6.7 Create `DELETE /api/v1/audio-digests/{id}`
  - Delete audio digest and associated file

## Phase 7: Configuration

- [x] 7.1 Add audio digest settings to `settings.py`
  - `audio_digest_default_voice: str = "nova"`
  - `audio_digest_speed: float = 1.0`
  - `audio_digest_provider: str = "openai"`
- [x] 7.2 Add voice presets for narration
  - Map friendly names to provider voice IDs
  - e.g., "nova", "onyx", "echo", "shimmer", "alloy", "fable"

## Phase 8: Testing

- [x] 8.1 Unit tests for `TextChunker`
- [x] 8.2 Unit tests for `DigestTextPreparer`
- [x] 8.3 Unit tests for `AudioDigestGenerator`
- [x] 8.4 Unit tests for `TTSService.synthesize_long()`
- [x] 8.5 API endpoint tests
- [ ] 8.6 Integration test: digest → audio flow

## Phase 9: Frontend

- [x] 9.1 Create TypeScript types (`web/src/types/audio-digest.ts`)
- [x] 9.2 Create API client functions (`web/src/lib/api/audio-digests.ts`)
- [x] 9.3 Add query keys to `query-keys.ts`
- [x] 9.4 Create React Query hooks (`web/src/hooks/use-audio-digests.ts`)
- [x] 9.5 Create `GenerateAudioDigestDialog` component
  - Digest selector, voice dropdown, speed slider, provider dropdown
- [x] 9.6 Create Audio Digests page (`web/src/routes/audio-digests.tsx`)
  - Stats cards, filterable table, audio player modal
- [x] 9.7 Add navigation item with Headphones icon
- [x] 9.8 Add background task type for progress tracking
- [x] 9.9 Add playback speed control to audio player (0.5x - 2x)

## Phase 10: Documentation

- [ ] 10.1 Add audio digest section to API docs
- [ ] 10.2 Update CLAUDE.md with audio digest guidance
- [ ] 10.3 Document TTS character limits and chunking behavior

---

## Summary

| Phase | Status | Notes |
|-------|--------|-------|
| 1. Text Chunking | 90% | DialogueBatcher integration pending |
| 2. TTSService | 90% | Streaming output pending |
| 3. Data Model | ✅ | Complete |
| 4. Text Preparation | ✅ | Complete |
| 5. Audio Generation | 90% | Progress callback pending |
| 6. API Endpoints | ✅ | Complete |
| 7. Configuration | ✅ | Complete |
| 8. Testing | 90% | Integration test pending |
| 9. Frontend | ✅ | Complete |
| 10. Documentation | 0% | Not started |
