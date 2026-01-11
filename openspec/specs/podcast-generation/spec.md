# Capability: Podcast Generation

## Purpose

Transform digests into podcast-style audio content featuring two expert personas (Alex Chen - VP Engineering, Dr. Sam Rodriguez - Distinguished Engineer) discussing AI/Data news. The feature provides a two-phase workflow with script generation, human review, and text-to-speech synthesis using configurable voice providers.

## Requirements

### Requirement: Podcast Script Generation

The system SHALL generate conversational podcast scripts from digests using LLM-based dialogue creation with tool-based content retrieval.

#### Scenario: Generate standard length script from digest
- **GIVEN** a completed digest with ID exists
- **WHEN** a script generation request is submitted with length "standard"
- **THEN** the system generates a ~15-minute script (~2250-3000 words)
- **AND** the script contains intro, strategic, technical, trends, and outro sections
- **AND** each section has dialogue turns between Alex and Sam personas
- **AND** the script status is set to "script_pending_review"

#### Scenario: Generate brief length script
- **GIVEN** a completed digest exists
- **WHEN** a script generation request is submitted with length "brief"
- **THEN** the system generates a ~5-minute script (~750-1000 words)
- **AND** the script focuses on executive highlights only

#### Scenario: Generate extended length script
- **GIVEN** a completed digest exists
- **WHEN** a script generation request is submitted with length "extended"
- **THEN** the system generates a ~30-minute script (~4500-6000 words)
- **AND** the script includes full coverage with detailed analysis
- **AND** web search grounding is enabled by default

#### Scenario: Tool-based newsletter content retrieval
- **GIVEN** script generation is in progress
- **WHEN** the LLM needs detailed information from a source newsletter
- **THEN** it can call the `get_newsletter_content` tool with a newsletter ID
- **AND** the full text of the newsletter is returned
- **AND** the fetched newsletter ID is tracked in generation metadata

#### Scenario: Script generation with web search
- **GIVEN** web search is enabled in the request
- **WHEN** the LLM needs external context for grounding
- **THEN** it can call the `web_search` tool with a query
- **AND** search results are returned for incorporation
- **AND** queries are tracked in generation metadata

---

### Requirement: Script Review Workflow

The system SHALL support human review of generated scripts with section-based feedback and revision capabilities before audio generation.

#### Scenario: View script for review
- **GIVEN** a script with status "script_pending_review"
- **WHEN** the script is retrieved for review
- **THEN** the response includes all sections with dialogue formatted for reading
- **AND** revision history is included if any revisions have been made
- **AND** source citations are visible per section

#### Scenario: Approve script
- **GIVEN** a script with status "script_pending_review"
- **WHEN** a review is submitted with action "approve"
- **THEN** the script status changes to "script_approved"
- **AND** reviewer name and timestamp are recorded
- **AND** the script becomes eligible for audio generation

#### Scenario: Request revision with section feedback
- **GIVEN** a script with status "script_pending_review"
- **WHEN** a review is submitted with action "request_revision" and section feedback
- **THEN** the script status changes to "script_revision_requested"
- **AND** each section with feedback is revised by the LLM
- **AND** revision history is updated with original content and feedback
- **AND** revision count is incremented
- **AND** status returns to "script_pending_review" after revision

#### Scenario: Reject script
- **GIVEN** a script with status "script_pending_review"
- **WHEN** a review is submitted with action "reject"
- **THEN** the script status changes to "failed"
- **AND** reviewer notes are recorded

#### Scenario: Revise single section
- **GIVEN** a script with status "script_pending_review" or "script_revision_requested"
- **WHEN** section-specific feedback is submitted for a single section
- **THEN** only that section is regenerated based on feedback
- **AND** other sections remain unchanged
- **AND** revision history is updated

---

### Requirement: Text-to-Speech Audio Generation

The system SHALL synthesize podcast audio from approved scripts using configurable TTS providers and voice personas.

#### Scenario: Generate audio with OpenAI TTS
- **GIVEN** a script with status "script_approved"
- **AND** voice provider is set to "openai_tts"
- **WHEN** audio generation is requested
- **THEN** audio is synthesized using OpenAI TTS API
- **AND** dialogue turns are processed sequentially with appropriate pauses
- **AND** Alex and Sam personas use distinct voice IDs
- **AND** the resulting MP3 file is saved to local storage

#### Scenario: Generate audio with ElevenLabs
- **GIVEN** a script with status "script_approved"
- **AND** voice provider is set to "elevenlabs"
- **AND** ElevenLabs API key is configured
- **WHEN** audio generation is requested
- **THEN** audio is synthesized using ElevenLabs API
- **AND** voice personas map to configured ElevenLabs voice IDs

#### Scenario: Voice persona selection
- **GIVEN** an audio generation request
- **WHEN** alex_voice and sam_voice parameters are specified
- **THEN** the specified voice variants (male/female) are used for each persona
- **AND** voice IDs are looked up from provider-specific mappings

#### Scenario: Audio generation from unapproved script
- **GIVEN** a script with status other than "script_approved"
- **WHEN** audio generation is requested
- **THEN** the request is rejected with error
- **AND** the error message indicates script must be approved first

#### Scenario: Audio file streaming
- **GIVEN** a completed podcast with audio file
- **WHEN** the audio streaming endpoint is called
- **THEN** the MP3 file is streamed to the client
- **AND** appropriate content-type headers are set

---

### Requirement: Podcast Data Model

The system SHALL maintain podcast scripts and audio recordings as separate entities supporting the review workflow and multiple audio versions per script.

#### Scenario: Script record creation
- **WHEN** script generation begins
- **THEN** a PodcastScriptRecord is created with status "script_generating"
- **AND** the record links to the source digest
- **AND** the target length is recorded

#### Scenario: Script content storage
- **WHEN** script generation completes successfully
- **THEN** the full script JSON (sections, dialogue, sources) is stored
- **AND** word count and estimated duration are calculated and stored
- **AND** model used and token usage are recorded
- **AND** processing time is recorded

#### Scenario: Podcast audio record creation
- **WHEN** audio generation begins for an approved script
- **THEN** a Podcast record is created linking to the script
- **AND** voice configuration (provider, alex_voice, sam_voice) is recorded
- **AND** status is set to "generating"

#### Scenario: Multiple audio versions per script
- **GIVEN** an approved script
- **WHEN** audio is generated with different voice configurations
- **THEN** multiple Podcast records can exist for the same script
- **AND** each has its own voice settings and audio file

---

### Requirement: Podcast API Endpoints

The system SHALL provide REST API endpoints for script and audio management following the two-phase workflow.

#### Scenario: POST /api/v1/scripts/generate
- **WHEN** a script generation request is submitted
- **THEN** script generation is queued as a background task
- **AND** response includes status "queued"

#### Scenario: GET /api/v1/scripts
- **WHEN** scripts are listed
- **THEN** results can be filtered by status
- **AND** results are paginated
- **AND** each script includes summary information (id, title, status, word_count)

#### Scenario: GET /api/v1/scripts/{script_id}
- **WHEN** a specific script is requested
- **THEN** full script details are returned including all sections
- **AND** sections include dialogue with speaker and text

#### Scenario: POST /api/v1/scripts/{script_id}/review
- **WHEN** a review is submitted for a script
- **THEN** the review action is processed
- **AND** status and revision information are updated

#### Scenario: POST /api/v1/scripts/{script_id}/sections/{index}/revise
- **WHEN** section-specific revision feedback is submitted
- **THEN** only the specified section is revised
- **AND** updated section is returned

#### Scenario: POST /api/v1/podcasts/generate
- **WHEN** audio generation is requested for an approved script
- **THEN** audio generation is queued as a background task
- **AND** response includes status "queued"

#### Scenario: GET /api/v1/podcasts
- **WHEN** podcasts are listed
- **THEN** results can be filtered by status
- **AND** results include audio metadata (duration, file_size)

#### Scenario: GET /api/v1/podcasts/{podcast_id}/audio
- **WHEN** audio file is requested
- **THEN** MP3 file is streamed with appropriate headers

---

### Requirement: Voice Persona Configuration

The system SHALL support configurable voice personas with provider-specific voice ID mappings.

#### Scenario: Default voice persona mapping
- **GIVEN** no custom voice IDs are configured
- **WHEN** audio is generated with OpenAI TTS
- **THEN** Alex Male uses "onyx" voice
- **AND** Alex Female uses "nova" voice
- **AND** Sam Male uses "fable" voice
- **AND** Sam Female uses "shimmer" voice

#### Scenario: ElevenLabs custom voice configuration
- **GIVEN** ElevenLabs voice IDs are configured via environment variables
- **WHEN** audio is generated with ElevenLabs provider
- **THEN** configured voice IDs are used for each persona

#### Scenario: Voice provider fallback
- **GIVEN** a voice provider is specified but not fully configured
- **WHEN** audio generation is attempted
- **THEN** an appropriate error is returned
- **AND** error indicates which configuration is missing

---

## Acceptance Criteria Summary

1. Scripts generated from digests in three lengths (brief, standard, extended)
2. Two-phase workflow with human review between script and audio generation
3. Section-based feedback and revision capabilities
4. Multiple TTS providers supported (OpenAI TTS, ElevenLabs, Google, AWS)
5. Configurable voice personas with male/female variants
6. Scripts cached for multiple audio regenerations
7. Full API coverage for script and podcast management
8. Tool-based newsletter content retrieval during script generation
9. Optional web search grounding for extended scripts
