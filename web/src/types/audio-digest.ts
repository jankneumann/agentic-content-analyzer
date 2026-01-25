/**
 * Audio Digest Types
 *
 * TypeScript interfaces for audio digest entities.
 * Audio digests are TTS-generated audio from Digests (single-voice narration).
 *
 * Unlike podcasts which require script generation and review, audio digests
 * provide direct digest-to-audio conversion with configurable voice and speed.
 *
 * @see Backend model: src/models/audio_digest.py
 * @see Backend API: src/api/audio_digest_routes.py
 */

/**
 * Audio digest generation status
 *
 * Tracks the audio digest through the generation pipeline.
 */
export type AudioDigestStatus =
  | "pending" // Created, queued for processing
  | "processing" // Currently generating audio
  | "completed" // Successfully generated
  | "failed" // Generation failed

/**
 * TTS voice provider options
 *
 * Available text-to-speech providers for audio generation.
 */
export type AudioDigestProvider = "openai" | "elevenlabs"

/**
 * Available voice options
 *
 * Voice presets available for audio digest narration.
 * These map to provider-specific voice IDs on the backend.
 */
export type AudioDigestVoice =
  | "nova" // Warm female (OpenAI default)
  | "onyx" // Deep male
  | "echo" // Natural male
  | "shimmer" // Expressive female
  | "alloy" // Neutral
  | "fable" // Storytelling

/**
 * Audio digest list item (lightweight view)
 *
 * Used in list views and tables.
 * Field names use snake_case to match the Python backend API.
 */
export interface AudioDigestListItem {
  /** Unique identifier */
  id: number
  /** Source digest ID */
  digest_id: number
  /** Voice used for synthesis */
  voice: string
  /** Speech speed multiplier */
  speed: number
  /** TTS provider used */
  provider: string
  /** Current status */
  status: AudioDigestStatus
  /** Audio duration in seconds (null if not completed) */
  duration_seconds: number | null
  /** File size in bytes (null if not completed) */
  file_size_bytes: number | null
  /** When created */
  created_at: string
  /** When completed (null if not completed) */
  completed_at: string | null
  /** Error message if failed */
  error_message: string | null
}

/**
 * Audio digest full details
 *
 * Complete information including audio URL and analytics.
 * Field names use snake_case to match the Python backend API.
 */
export interface AudioDigestDetail extends AudioDigestListItem {
  /** URL to audio file (null if not completed) */
  audio_url: string | null
  /** Audio format (always "mp3") */
  audio_format: string
  /** Number of characters in prepared text */
  text_char_count: number | null
  /** Number of TTS synthesis chunks */
  chunk_count: number | null
}

/**
 * Audio digest statistics
 *
 * Aggregate statistics for the audio digests page.
 */
export interface AudioDigestStatistics {
  /** Total number of audio digests */
  total: number
  /** Currently generating */
  generating: number
  /** Successfully completed */
  completed: number
  /** Failed generation */
  failed: number
  /** Total audio duration in seconds */
  total_duration_seconds: number
  /** Count by voice */
  by_voice: Record<string, number>
  /** Count by provider */
  by_provider: Record<string, number>
}

/**
 * Request to create an audio digest
 *
 * Configuration for audio digest generation.
 */
export interface CreateAudioDigestRequest {
  /** Voice preset to use */
  voice?: AudioDigestVoice
  /** Speech speed multiplier (0.5 to 2.0) */
  speed?: number
  /** TTS provider */
  provider?: AudioDigestProvider
}

/**
 * Response from create audio digest endpoint
 */
export interface CreateAudioDigestResponse {
  /** Status message */
  status: string
  /** Human-readable message */
  message: string
  /** Created audio digest ID */
  audio_digest_id: number
}

/**
 * Filters for audio digest list
 */
export interface AudioDigestFilters {
  /** Filter by status */
  status?: AudioDigestStatus
  /** Filter by provider */
  provider?: string
  /** Filter by voice */
  voice?: string
  /** Limit number of results */
  limit?: number
  /** Offset for pagination */
  offset?: number
  /** Sort field */
  sort_by?: string
  /** Sort order */
  sort_order?: "asc" | "desc"
}

/**
 * Digest available for audio generation
 *
 * Lightweight digest info for the source selector dropdown.
 */
export interface AvailableDigest {
  /** Digest ID */
  id: number
  /** Digest title */
  title: string | null
  /** Digest type (daily, weekly) */
  digest_type: string
  /** Period start date */
  period_start: string
  /** Period end date */
  period_end: string
  /** Current status */
  status: string
  /** When created */
  created_at: string
}

/**
 * Voice option for the selector dropdown
 */
export interface VoiceOption {
  /** Voice ID value */
  value: AudioDigestVoice
  /** Display label */
  label: string
  /** Voice description */
  description: string
}

/**
 * Provider option for the selector dropdown
 */
export interface ProviderOption {
  /** Provider ID value */
  value: AudioDigestProvider
  /** Display label */
  label: string
}
