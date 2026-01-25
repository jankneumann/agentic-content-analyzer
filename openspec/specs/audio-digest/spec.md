# audio-digest Specification

## Purpose
TBD - created by archiving change add-audio-digest-generation. Update Purpose after archive.
## Requirements
### Requirement: Audio Digest Generation

The system SHALL support generating single-voice audio narration from digest content.

#### Scenario: Generate audio digest from daily digest

- **GIVEN** a published daily digest exists
- **WHEN** a user requests audio generation via `POST /api/v1/digests/{id}/audio`
- **THEN** an audio file is generated using TTS
- **AND** the audio is stored in the "audio-digests" storage bucket
- **AND** an AudioDigest record is created with status "completed"

#### Scenario: Stream audio digest

- **WHEN** a user requests `GET /api/v1/audio-digests/{id}/stream`
- **THEN** the audio file is streamed with appropriate headers
- **AND** range requests are supported for seeking

### Requirement: Audio Digest Text Preparation

The system SHALL convert digest markdown to TTS-friendly text.

#### Scenario: Headings become pauses

- **GIVEN** digest markdown with `## Section Title`
- **WHEN** text is prepared for TTS
- **THEN** the heading becomes a pause followed by the title
- **AND** SSML `<break>` tags are inserted (if provider supports)

#### Scenario: Code blocks are handled

- **GIVEN** digest markdown with code blocks
- **WHEN** text is prepared for TTS
- **THEN** code blocks are either summarized or announced
- **AND** raw code is not read verbatim

### Requirement: Audio Digest Configuration

The system SHALL support configurable voice and speed settings.

#### Scenario: Custom voice selection

- **GIVEN** settings specify `audio_digest_default_voice = "nova"`
- **WHEN** an audio digest is generated without explicit voice
- **THEN** the "nova" voice is used for synthesis

#### Scenario: Speed adjustment

- **GIVEN** settings specify `audio_digest_speed = 1.25`
- **WHEN** an audio digest is generated
- **THEN** the audio plays at 1.25x normal speed

### Requirement: Text Chunking for TTS Limits

The system SHALL automatically chunk long text to respect TTS provider limits.

#### Scenario: Long digest exceeds provider limit

- **GIVEN** a digest with 10,000 characters of text
- **AND** the TTS provider has a 4,096 character limit
- **WHEN** audio is generated
- **THEN** the text is split at paragraph boundaries
- **AND** each chunk is synthesized separately
- **AND** the audio segments are concatenated seamlessly

#### Scenario: Chunk boundaries preserve readability

- **WHEN** text is chunked for TTS synthesis
- **THEN** chunks end at paragraph or sentence boundaries
- **AND** SSML pause tags are inserted between chunks
