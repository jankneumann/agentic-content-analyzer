# Tasks: Audio Digest Generation

## Phase 1: Shared Text Chunking Utility (Benefits Podcasts Too)

- [ ] 1.1 Create `src/delivery/text_chunker.py`
  - Generic text splitting at paragraph/sentence boundaries
  - Configurable max length per provider (OpenAI: 4096, ElevenLabs: 5000)
  - SSML pause injection between chunks
- [ ] 1.2 Add `TextChunk` dataclass with text, position, estimated_duration
- [ ] 1.3 Add unit tests for chunking edge cases
- [ ] 1.4 Update `DialogueBatcher` to use `TextChunker` for long turns

## Phase 2: TTSService Long-Form Synthesis

- [ ] 2.1 Add `synthesize_long()` method to `TTSService`
  - Accept text of any length
  - Use TextChunker to split
  - Synthesize each chunk and concatenate
- [ ] 2.2 Add `synthesize_long_stream()` for progressive output
- [ ] 2.3 Handle provider-specific limits automatically
- [ ] 2.4 Add unit tests for long-form synthesis

## Phase 3: Data Model

- [ ] 3.1 Create `AudioDigest` SQLAlchemy model
  - `id`, `digest_id`, `voice`, `status`, `audio_url`
  - `duration_seconds`, `file_size_bytes`, `created_at`
  - `text_char_count`, `chunk_count` (for analytics)
- [ ] 3.2 Create Alembic migration for `audio_digests` table
- [ ] 3.3 Create Pydantic schemas for API

## Phase 4: Text Preparation

- [ ] 4.1 Create `DigestTextPreparer` class
  - Extract text from digest markdown
  - Add natural pauses between sections
  - Handle headings as section breaks
- [ ] 4.2 Add SSML markup for supported providers
  - `<break>` tags between sections
  - Emphasis for headings
- [ ] 4.3 Handle code blocks (skip or announce)
- [ ] 4.4 Estimate duration from text length

## Phase 5: Audio Generation

- [ ] 5.1 Create `AudioDigestGenerator` class
  - Accept digest_id and voice configuration
  - Use `DigestTextPreparer` for text
  - Use `TTSService.synthesize_long()` for audio
  - Save to unified file storage ("audio-digests" bucket)
- [ ] 5.2 Add progress callback for long generations
- [ ] 5.3 Handle failures gracefully (partial generation)

## Phase 6: API Endpoints

- [ ] 6.1 Create `POST /api/v1/digests/{digest_id}/audio`
  - Generate audio digest (background task)
  - Return audio digest record with status
- [ ] 6.2 Create `GET /api/v1/digests/{digest_id}/audio`
  - Get existing audio digest(s) for a digest
- [ ] 6.3 Create `GET /api/v1/audio-digests/{id}`
  - Get specific audio digest details
- [ ] 6.4 Create `GET /api/v1/audio-digests/{id}/stream`
  - Stream audio file (via unified file storage)

## Phase 7: Configuration

- [ ] 7.1 Add audio digest settings to `settings.py`
  - `audio_digest_default_voice: str = "nova"`
  - `audio_digest_speed: float = 1.0`
  - `audio_digest_provider: str = "openai"`
- [ ] 7.2 Add voice presets for narration
  - Map friendly names to provider voice IDs
  - e.g., "professional", "warm", "energetic"

## Phase 8: Testing

- [ ] 8.1 Unit tests for `TextChunker`
- [ ] 8.2 Unit tests for `DigestTextPreparer`
- [ ] 8.3 Unit tests for `AudioDigestGenerator`
- [ ] 8.4 Unit tests for `TTSService.synthesize_long()`
- [ ] 8.5 API endpoint tests
- [ ] 8.6 Integration test: digest → audio flow

## Phase 9: Documentation

- [ ] 9.1 Add audio digest section to API docs
- [ ] 9.2 Update CLAUDE.md with audio digest guidance
- [ ] 9.3 Document TTS character limits and chunking behavior
