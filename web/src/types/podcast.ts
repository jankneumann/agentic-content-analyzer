/**
 * Podcast Types
 *
 * TypeScript interfaces for podcast script and audio entities.
 * These types mirror the backend Python models in src/models/podcast.py
 *
 * The podcast pipeline generates conversational scripts from digests
 * and then synthesizes audio using TTS providers.
 *
 * @see Backend model: src/models/podcast.py
 */

/**
 * Podcast script length options
 *
 * Determines the depth and duration of the generated script.
 */
export type ScriptLength = "brief" | "standard" | "extended"

/**
 * Script workflow status
 *
 * Tracks the script through generation, review, and audio synthesis.
 */
export type ScriptStatus =
  | "pending" // Created but not generated
  | "script_generating" // LLM generating script
  | "script_pending_review" // Script ready for review
  | "script_revision_requested" // Reviewer requested changes
  | "script_approved" // Script approved, ready for audio
  | "audio_generating" // TTS synthesizing audio
  | "completed" // Audio generated successfully
  | "failed" // Process failed

/**
 * Audio generation status
 */
export type AudioStatus = "generating" | "completed" | "failed"

/**
 * Speaker in the podcast dialogue
 *
 * The podcast features two personas having a conversation:
 * - Alex: VP of Engineering perspective
 * - Sam: Distinguished Engineer perspective
 */
export type Speaker = "alex" | "sam"

/**
 * Emotional emphasis for dialogue delivery
 *
 * Hints for TTS voice modulation and listener engagement.
 */
export type DialogueEmphasis =
  | "excited" // Enthusiastic delivery
  | "thoughtful" // Contemplative, slower pace
  | "concerned" // Serious, cautionary tone
  | "amused" // Light, humorous delivery

/**
 * Type of podcast section
 *
 * Scripts are organized into sections by content type.
 */
export type SectionType =
  | "intro" // Opening of the podcast
  | "strategic" // Strategic insights discussion
  | "technical" // Technical deep-dive
  | "trend" // Emerging trends discussion
  | "outro" // Closing remarks

/**
 * Single turn of dialogue
 *
 * Represents one speaker's contribution to the conversation.
 */
export interface DialogueTurn {
  /** Who is speaking */
  speaker: Speaker
  /** The spoken text */
  text: string
  /** Optional emotional emphasis */
  emphasis: DialogueEmphasis | null
  /** Pause duration after this turn (seconds) */
  pauseAfter: number | null
}

/**
 * Section of the podcast script
 *
 * A thematic segment of the conversation.
 */
export interface PodcastSection {
  /** Type of section */
  sectionType: SectionType
  /** Section title/topic */
  title: string
  /** Dialogue turns in this section */
  dialogue: DialogueTurn[]
  /** Newsletter IDs cited in this section */
  sourcesCited: string[]
}

/**
 * Source summary for script attribution
 */
export interface ScriptSource {
  /** Newsletter ID */
  id: string
  /** Newsletter title */
  title: string
  /** Publication name */
  publication: string | null
  /** URL if available */
  url?: string
}

/**
 * Complete podcast script structure
 *
 * The full script ready for TTS synthesis.
 */
export interface PodcastScript {
  /** Script title */
  title: string
  /** Script length category */
  length: ScriptLength
  /** Estimated duration in seconds */
  estimatedDurationSeconds: number
  /** Total word count */
  wordCount: number
  /** Main content sections */
  sections: PodcastSection[]
  /** Introduction dialogue */
  intro: DialogueTurn[]
  /** Closing dialogue */
  outro: DialogueTurn[]
  /** Sources referenced */
  sourcesSummary: ScriptSource[]
}

/**
 * Podcast Script Record (database entity)
 *
 * The persisted script with metadata and review tracking.
 */
export interface PodcastScriptRecord {
  /** Unique identifier (UUID) */
  id: string

  /** Source digest ID */
  digestId: string

  /** Script length setting */
  length: ScriptLength

  /** Script title */
  title: string

  /** Full script content */
  script: PodcastScript

  /** Total word count */
  wordCount: number

  /** Estimated duration in seconds */
  estimatedDurationSeconds: number

  /** Current workflow status */
  status: ScriptStatus

  /** Who reviewed */
  reviewedBy: string | null

  /** When reviewed */
  reviewedAt: string | null

  /** Review notes */
  reviewNotes: string | null

  /** Number of revisions */
  revisionCount: number

  /** Revision history entries */
  revisionHistory: ScriptRevisionEntry[]

  /** Available newsletter IDs when generated */
  newsletterIdsAvailable: string[]

  /** Newsletter IDs actually used */
  newsletterIdsFetched: string[]

  /** Theme IDs referenced */
  themeIds: string[]

  /** Web search queries made (if enabled) */
  webSearchQueries: string[]

  /** Number of tool calls during generation */
  toolCallCount: number

  /** Model used */
  modelUsed: string

  /** Model version */
  modelVersion: string | null

  /** Token usage breakdown */
  tokenUsage: {
    input: number
    output: number
    total: number
  }

  /** Processing time in seconds */
  processingTimeSeconds: number

  /** Error message if failed */
  errorMessage: string | null

  /** When created */
  createdAt: string // ISO 8601

  /** When approved */
  approvedAt: string | null
}

/**
 * Script revision history entry
 */
export interface ScriptRevisionEntry {
  /** When revised */
  timestamp: string
  /** Who revised */
  revisedBy: string
  /** Sections that were changed */
  sectionsRevised: number[]
  /** Feedback that prompted revision */
  feedback: string
}

/**
 * Script list item (lightweight view)
 * Field names use snake_case to match the Python backend API.
 */
export interface ScriptListItem {
  id: number
  digest_id: number
  title: string | null
  length: string
  word_count: number | null
  /** Duration formatted as string e.g., "5 min" */
  estimated_duration: string | null
  status: string
  revision_count: number
  created_at: string | null
  reviewed_by: string | null
}

/**
 * Podcast audio entity
 *
 * The synthesized audio file and its metadata.
 */
export interface Podcast {
  /** Unique identifier (UUID) */
  id: string

  /** Source script ID */
  scriptId: string

  /** URL to audio file */
  audioUrl: string

  /** Audio format */
  audioFormat: string // e.g., "mp3", "wav"

  /** Actual duration in seconds */
  durationSeconds: number

  /** File size in bytes */
  fileSizeBytes: number

  /** TTS provider used */
  voiceProvider: string

  /** Voice ID for Alex */
  alexVoice: string

  /** Voice ID for Sam */
  samVoice: string

  /** Additional voice configuration */
  voiceConfig: Record<string, unknown>

  /** Generation status */
  status: AudioStatus

  /** Error message if failed */
  errorMessage: string | null

  /** When created */
  createdAt: string // ISO 8601

  /** When completed */
  completedAt: string | null
}

/**
 * Podcast list item (snake_case to match API)
 */
export interface PodcastListItem {
  id: number
  script_id: number
  title: string | null
  digest_id: number | null
  length: string | null
  duration_seconds: number | null
  file_size_bytes: number | null
  audio_format: string
  voice_provider: string | null
  status: string
  created_at: string | null
  completed_at: string | null
}

/**
 * Full podcast details (snake_case to match API)
 */
export interface PodcastDetail {
  id: number
  script_id: number
  title: string | null
  digest_id: number | null
  length: string | null
  word_count: number | null
  estimated_duration_seconds: number | null
  duration_seconds: number | null
  file_size_bytes: number | null
  audio_url: string | null
  audio_format: string
  voice_provider: string | null
  alex_voice: string | null
  sam_voice: string | null
  status: string
  error_message: string | null
  created_at: string | null
  completed_at: string | null
}

/**
 * Podcast statistics
 */
export interface PodcastStatistics {
  total: number
  generating: number
  completed: number
  failed: number
  total_duration_seconds: number
  by_voice_provider: Record<string, number>
}

/**
 * Approved script ready for audio generation
 */
export interface ApprovedScript {
  id: number
  digest_id: number
  title: string | null
  length: string | null
  word_count: number | null
  estimated_duration_seconds: number | null
  approved_at: string | null
}

/**
 * Request to generate a podcast script
 * Field names use snake_case to match the Python backend API.
 */
export interface GenerateScriptRequest {
  /** Source digest ID */
  digest_id: number
  /** Script length preference */
  length?: ScriptLength
  /** Enable web search for additional context */
  enable_web_search?: boolean
  /** Custom focus topics */
  custom_focus_topics?: string[]
}

/**
 * Response from generate script endpoint
 */
export interface GenerateScriptResponse {
  status: string
  message: string
  length: string
}

/**
 * Review action for scripts
 */
export type ScriptReviewAction = "approve" | "request_revision" | "reject"

/**
 * Request to submit script review
 */
export interface ScriptReviewRequest {
  /** Review action */
  action: ScriptReviewAction
  /** Reviewer name */
  reviewer: string
  /** Section-specific feedback (key is section index) */
  sectionFeedback?: Record<number, string>
  /** General notes */
  generalNotes?: string
}

/**
 * Request to revise a script section
 */
export interface ReviseScriptSectionRequest {
  /** Section index to revise */
  sectionIndex: number
  /** Revision instructions */
  feedback: string
  /** Reviewer name */
  reviewer: string
}

/**
 * Request to generate podcast audio
 */
export interface GenerateAudioRequest {
  /** Script ID to synthesize */
  scriptId: string
  /** TTS provider to use */
  voiceProvider?: string
  /** Voice ID for Alex */
  alexVoice?: string
  /** Voice ID for Sam */
  samVoice?: string
}

/**
 * Progress event for audio generation (SSE)
 */
export interface AudioGenerationProgress {
  /** Task identifier */
  taskId: string
  /** Current step */
  step: string
  /** Progress percentage (0-100) */
  progress: number
  /** Currently processing section */
  currentSection?: number
  /** Total sections */
  totalSections?: number
  /** Status */
  status: "processing" | "completed" | "error"
  /** Error message if failed */
  errorMessage?: string
  /** Podcast ID once created */
  podcastId?: string
}

/**
 * Script review statistics
 * Field names use snake_case to match the Python backend API.
 */
export interface ScriptReviewStatistics {
  /** Scripts pending review */
  pending_review: number
  /** Scripts with revision requested */
  revision_requested: number
  /** Approved scripts ready for audio */
  approved_ready_for_audio: number
  /** Completed with audio */
  completed_with_audio: number
  /** Failed or rejected */
  failed_rejected: number
  /** Total scripts */
  total: number
}
