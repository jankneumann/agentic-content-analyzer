# Change: Add Direct Audio Digest Generation

## Why

The current podcast workflow requires:
1. Script generation (agentic, slow)
2. Human review and approval
3. Audio synthesis

This is appropriate for high-quality podcast production but overkill for users
who just want to listen to their digest content. A simpler audio digest feature
enables:
- Quick audio generation without script review
- Single-voice narration (not conversational)
- Faster turnaround for daily consumption
- Mobile-friendly audio delivery

## What Changes

- **NEW**: `TextChunker` utility in `src/delivery/` (shared with podcasts)
- **NEW**: `TTSService.synthesize_long()` method for any-length text
- **NEW**: `AudioDigestGenerator` class in `src/processors/`
- **NEW**: `AudioDigest` model for tracking audio digest records
- **NEW**: API endpoints for audio digest generation
- **NEW**: Simple text-to-audio pipeline (digest markdown → TTS)
- **USES**: Unified file storage for audio files (depends on `refactor-unified-file-storage`)

## Impact

- **Affected specs**: Creates new `audio-digest` capability
- **New files**:
  - `src/delivery/text_chunker.py` - Shared text chunking utility
  - `src/processors/audio_digest_generator.py`
  - `src/processors/digest_text_preparer.py`
  - `src/models/audio_digest.py`
  - `src/api/audio_digest_routes.py`
- **Affected code**:
  - `src/delivery/tts_service.py` - Add `synthesize_long()` method
  - `src/config/settings.py` - Audio digest configuration
- **Dependencies**: `refactor-unified-file-storage` (for storage)
- **Breaking changes**: None
