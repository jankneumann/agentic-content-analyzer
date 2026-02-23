/**
 * Mock Data Factories
 *
 * Typed factory functions producing API responses that match the
 * TypeScript types in web/src/types/. All field names use snake_case
 * to match the Python backend API responses.
 *
 * Usage:
 *   const item = createContentListItem({ title: "Custom Title" })
 *   const list = createContentListResponse({ total: 50 })
 */

import type {
  ContentListItem,
  ContentListResponse,
  ContentStats,
  Content,
  SummaryListItem,
  Summary,
  DigestListItem,
  DigestDetail,
  DigestStatistics,
  ScriptListItem,
  PodcastListItem,
  PodcastStatistics,
  AudioDigestListItem,
  AudioDigestStatistics,
  AudioDigestDetail,
  ThemeAnalysisResult,
  ThemeData,
  PaginatedResponse,
  PodcastDetail,
  PromptInfo,
  PromptListResponse,
  PromptTestResponse,
  PromptUpdateResponse,
} from "../../../src/types"

import type { ScriptDetail, ScriptSection } from "../../../src/types/review"

// ─── Content ───────────────────────────────────────────────

export function createContentListItem(
  overrides: Partial<ContentListItem> = {}
): ContentListItem {
  return {
    id: 1,
    source_type: "gmail",
    title: "AI Weekly: GPT-5 Announced",
    publication: "AI Weekly Newsletter",
    published_date: "2025-01-15T10:00:00Z",
    status: "completed",
    ingested_at: "2025-01-15T12:00:00Z",
    ...overrides,
  }
}

export function createContent(overrides: Partial<Content> = {}): Content {
  return {
    id: 1,
    source_type: "gmail",
    source_id: "msg-abc123",
    source_url: "https://example.com/newsletter/1",
    title: "AI Weekly: GPT-5 Announced",
    author: "Jane Smith",
    publication: "AI Weekly Newsletter",
    published_date: "2025-01-15T10:00:00Z",
    markdown_content:
      "# AI Weekly\n\nGPT-5 has been announced with remarkable capabilities...",
    tables_json: null,
    links_json: ["https://openai.com/gpt-5"],
    metadata_json: { subject: "AI Weekly #42" },
    parser_used: "gmail_html",
    content_hash: "sha256-abc123def456",
    canonical_id: null,
    status: "completed",
    error_message: null,
    ingested_at: "2025-01-15T12:00:00Z",
    parsed_at: "2025-01-15T12:01:00Z",
    processed_at: "2025-01-15T12:05:00Z",
    ...overrides,
  }
}

export function createContentListResponse(
  overrides: Partial<ContentListResponse> = {}
): ContentListResponse {
  return {
    items: [
      createContentListItem({ id: 1, title: "AI Weekly: GPT-5 Announced" }),
      createContentListItem({
        id: 2,
        title: "ML Ops Digest: Kubernetes for ML",
        source_type: "rss",
        publication: "ML Ops Digest",
      }),
      createContentListItem({
        id: 3,
        title: "Data Engineering Weekly",
        source_type: "rss",
        publication: "Data Eng Weekly",
        status: "pending",
      }),
    ],
    total: 3,
    page: 1,
    page_size: 20,
    has_next: false,
    has_prev: false,
    ...overrides,
  }
}

export function createContentStats(
  overrides: Partial<ContentStats> = {}
): ContentStats {
  return {
    total: 42,
    by_status: {
      pending: 5,
      parsing: 1,
      parsed: 3,
      processing: 2,
      completed: 28,
      failed: 3,
    },
    by_source: {
      gmail: 20,
      rss: 15,
      file_upload: 3,
      youtube: 2,
      manual: 1,
      webpage: 1,
      other: 0,
    },
    pending_count: 5,
    completed_count: 28,
    failed_count: 3,
    needs_summarization_count: 8,
    ...overrides,
  }
}

// ─── Summaries ─────────────────────────────────────────────

export function createSummaryListItem(
  overrides: Partial<SummaryListItem> = {}
): SummaryListItem {
  return {
    id: 1,
    content_id: 1,
    title: "AI Weekly: GPT-5 Announced",
    publication: "AI Weekly Newsletter",
    executive_summary_preview:
      "OpenAI announced GPT-5 with significant improvements in reasoning and multimodal capabilities...",
    key_themes: ["Large Language Models", "AI Safety", "Multimodal AI"],
    model_used: "claude-haiku-4-5",
    created_at: "2025-01-15T12:05:00Z",
    processing_time_seconds: 4.2,
    ...overrides,
  }
}

export function createSummary(overrides: Partial<Summary> = {}): Summary {
  return {
    id: 1,
    content_id: 1,
    executive_summary:
      "OpenAI announced GPT-5 with significant improvements in reasoning, multimodal processing, and safety alignment.",
    key_themes: ["Large Language Models", "AI Safety", "Multimodal AI"],
    strategic_insights: [
      "GPT-5 represents a significant leap in reasoning capabilities",
      "New safety measures could set industry standards",
    ],
    technical_details: [
      "Architecture uses mixture-of-experts with 8 specialized modules",
      "Training data includes 15T tokens from diverse sources",
    ],
    actionable_items: [
      "Evaluate GPT-5 API for existing summarization pipeline",
      "Review safety alignment approach for internal AI systems",
    ],
    notable_quotes: [
      '"This represents the biggest leap in AI capability since GPT-4" - Sam Altman',
    ],
    relevant_links: [
      { url: "https://openai.com/gpt-5", title: "GPT-5 Announcement" },
    ],
    relevance_scores: {
      cto_leadership: 0.9,
      technical_teams: 0.85,
      individual_developers: 0.75,
    },
    agent_framework: "claude-sdk",
    model_used: "claude-haiku-4-5",
    model_version: "claude-haiku-4-5-20250115",
    created_at: "2025-01-15T12:05:00Z",
    token_usage: 2500,
    processing_time_seconds: 4.2,
    ...overrides,
  }
}

export function createSummaryListResponse(
  overrides: Partial<PaginatedResponse<SummaryListItem>> = {}
): PaginatedResponse<SummaryListItem> {
  return {
    items: [
      createSummaryListItem({ id: 1, content_id: 1 }),
      createSummaryListItem({
        id: 2,
        content_id: 2,
        title: "ML Ops Digest: Kubernetes for ML",
        publication: "ML Ops Digest",
        key_themes: ["MLOps", "Kubernetes", "Infrastructure"],
      }),
    ],
    total: 2,
    offset: 0,
    limit: 20,
    has_more: false,
    ...overrides,
  }
}

// ─── Digests ───────────────────────────────────────────────

export function createDigestListItem(
  overrides: Partial<DigestListItem> = {}
): DigestListItem {
  return {
    id: 1,
    digest_type: "daily",
    title: "Daily AI & Data Digest - Jan 15, 2025",
    period_start: "2025-01-15T00:00:00Z",
    period_end: "2025-01-15T23:59:59Z",
    content_count: 8,
    status: "COMPLETED",
    created_at: "2025-01-16T06:00:00Z",
    model_used: "claude-sonnet-4-5",
    revision_count: 0,
    reviewed_by: null,
    ...overrides,
  }
}

export function createDigestDetail(
  overrides: Partial<DigestDetail> = {}
): DigestDetail {
  return {
    id: 1,
    digest_type: "daily",
    title: "Daily AI & Data Digest - Jan 15, 2025",
    period_start: "2025-01-15T00:00:00Z",
    period_end: "2025-01-15T23:59:59Z",
    executive_overview:
      "Today's key developments center on GPT-5's announcement and its implications for enterprise AI adoption.",
    strategic_insights: [
      {
        title: "GPT-5 Changes Enterprise AI Landscape",
        summary:
          "The announcement signals a shift toward more capable AI systems.",
        details: [
          "Improved reasoning capabilities enable new use cases",
          "Safety features address enterprise compliance needs",
        ],
        themes: ["Enterprise AI", "Safety"],
        continuity: null,
      },
    ],
    technical_developments: [
      {
        title: "Mixture-of-Experts Architecture",
        summary: "GPT-5 uses MoE with 8 specialized modules.",
        details: [
          "Each expert focuses on different reasoning domains",
          "Dynamic routing reduces computational cost by 40%",
        ],
        themes: ["Model Architecture", "Efficiency"],
        continuity: null,
      },
    ],
    emerging_trends: [
      {
        title: "AI Safety Regulation",
        summary:
          "Growing momentum for AI safety standards in enterprise deployment.",
        details: [
          "New industry consortium announced for AI safety benchmarks",
          "EU AI Act compliance tools emerging as a new market",
        ],
        themes: ["Regulation", "Safety"],
        continuity: null,
      },
    ],
    actionable_recommendations: {
      for_leadership: [
        "Evaluate GPT-5 for strategic initiatives",
        "Review AI governance framework",
      ],
      for_teams: ["Begin GPT-5 API evaluation sprint"],
      for_individuals: ["Review updated API documentation"],
    },
    sources: [
      {
        title: "AI Weekly: GPT-5 Announced",
        publication: "AI Weekly",
        date: "2025-01-15",
        url: "https://example.com/1",
      },
    ],
    content_count: 8,
    status: "COMPLETED",
    created_at: "2025-01-16T06:00:00Z",
    completed_at: "2025-01-16T06:05:00Z",
    model_used: "claude-sonnet-4-5",
    model_version: "claude-sonnet-4-5-20250115",
    processing_time_seconds: 45.2,
    revision_count: 0,
    reviewed_by: null,
    reviewed_at: null,
    review_notes: null,
    is_combined: false,
    child_digest_ids: null,
    ...overrides,
  }
}

export function createDigestStatistics(
  overrides: Partial<DigestStatistics> = {}
): DigestStatistics {
  return {
    total: 15,
    pending: 1,
    generating: 0,
    completed: 8,
    pending_review: 3,
    approved: 2,
    delivered: 1,
    by_type: { daily: 12, weekly: 3 },
    ...overrides,
  }
}

// ─── Scripts ───────────────────────────────────────────────

export function createScriptListItem(
  overrides: Partial<ScriptListItem> = {}
): ScriptListItem {
  return {
    id: 1,
    digest_id: 1,
    title: "AI Weekly Deep Dive - Episode 42",
    length: "standard",
    word_count: 3200,
    estimated_duration: "12 min",
    status: "script_pending_review",
    revision_count: 0,
    created_at: "2025-01-16T08:00:00Z",
    reviewed_by: null,
    ...overrides,
  }
}

export function createScriptDetail(
  overrides: Partial<ScriptDetail> = {}
): ScriptDetail {
  return {
    id: 1,
    digest_id: 1,
    title: "AI Weekly Deep Dive - Episode 42",
    length: "standard",
    word_count: 3200,
    estimated_duration: "12 min",
    estimated_duration_seconds: 720,
    status: "script_pending_review",
    revision_count: 0,
    created_at: "2025-01-16T08:00:00Z",
    reviewed_by: null,
    reviewed_at: null,
    sections: [
      createScriptSection({ index: 0, type: "intro", title: "Opening" }),
      createScriptSection({
        index: 1,
        type: "strategic",
        title: "Strategic Insights",
      }),
      createScriptSection({
        index: 2,
        type: "technical",
        title: "Technical Deep-Dive",
      }),
      createScriptSection({
        index: 3,
        type: "trend",
        title: "Emerging Trends",
      }),
      createScriptSection({ index: 4, type: "outro", title: "Wrap-Up" }),
    ],
    sources_summary: [
      {
        id: "1",
        title: "AI Weekly Newsletter",
        publication: "AI Weekly",
        url: "https://example.com/1",
      },
    ],
    revision_history: [],
    content_ids_fetched: ["1", "2", "3"],
    web_search_queries: [],
    tool_call_count: 5,
    ...overrides,
  }
}

export function createScriptSection(
  overrides: Partial<ScriptSection> = {}
): ScriptSection {
  return {
    index: 0,
    type: "intro",
    title: "Opening",
    word_count: 250,
    dialogue: [
      {
        speaker: "alex",
        text: "Welcome to another episode of our AI weekly deep-dive.",
        emphasis: "excited",
        pause_after: 0.5,
      },
      {
        speaker: "sam",
        text: "Great to be here! We have some exciting developments to discuss.",
        emphasis: null,
        pause_after: 0.3,
      },
    ],
    sources_cited: [],
    ...overrides,
  }
}

// ─── Podcasts ──────────────────────────────────────────────

export function createPodcastListItem(
  overrides: Partial<PodcastListItem> = {}
): PodcastListItem {
  return {
    id: 1,
    script_id: 1,
    title: "AI Weekly Deep Dive - Episode 42",
    digest_id: 1,
    length: "standard",
    duration_seconds: 720,
    file_size_bytes: 11520000,
    audio_format: "mp3",
    voice_provider: "openai",
    status: "completed",
    error_message: null,
    created_at: "2025-01-16T09:00:00Z",
    completed_at: "2025-01-16T09:05:00Z",
    ...overrides,
  }
}

export function createPodcastDetail(
  overrides: Partial<PodcastDetail> = {}
): PodcastDetail {
  return {
    id: 1,
    script_id: 1,
    title: "AI Weekly Deep Dive - Episode 42",
    digest_id: 1,
    length: "standard",
    word_count: 3200,
    estimated_duration_seconds: 720,
    duration_seconds: 718,
    file_size_bytes: 11520000,
    audio_url: "/api/v1/podcasts/1/audio",
    audio_format: "mp3",
    voice_provider: "openai",
    alex_voice: "onyx",
    sam_voice: "nova",
    status: "completed",
    error_message: null,
    created_at: "2025-01-16T09:00:00Z",
    completed_at: "2025-01-16T09:05:00Z",
    ...overrides,
  }
}

export function createPodcastStatistics(
  overrides: Partial<PodcastStatistics> = {}
): PodcastStatistics {
  return {
    total: 5,
    generating: 0,
    completed: 4,
    failed: 1,
    total_duration_seconds: 2880,
    by_voice_provider: { openai: 4, elevenlabs: 1 },
    ...overrides,
  }
}

// ─── Audio Digests ─────────────────────────────────────────

export function createAudioDigestListItem(
  overrides: Partial<AudioDigestListItem> = {}
): AudioDigestListItem {
  return {
    id: 1,
    digest_id: 1,
    voice: "nova",
    speed: 1.0,
    provider: "openai",
    status: "completed",
    duration_seconds: 480,
    file_size_bytes: 7680000,
    created_at: "2025-01-16T10:00:00Z",
    completed_at: "2025-01-16T10:03:00Z",
    error_message: null,
    ...overrides,
  }
}

export function createAudioDigestDetail(
  overrides: Partial<AudioDigestDetail> = {}
): AudioDigestDetail {
  return {
    ...createAudioDigestListItem(),
    audio_url: "/api/v1/audio-digests/1/stream",
    audio_format: "mp3",
    text_char_count: 15000,
    chunk_count: 8,
    ...overrides,
  }
}

export function createAudioDigestStatistics(
  overrides: Partial<AudioDigestStatistics> = {}
): AudioDigestStatistics {
  return {
    total: 8,
    generating: 1,
    completed: 6,
    failed: 1,
    total_duration_seconds: 2400,
    by_voice: { nova: 4, onyx: 2, echo: 1, shimmer: 1 },
    by_provider: { openai: 6, elevenlabs: 2 },
    ...overrides,
  }
}

// ─── Themes ────────────────────────────────────────────────

export function createThemeData(
  overrides: Partial<ThemeData> = {}
): ThemeData {
  return {
    name: "Large Language Models",
    description: "Developments in LLM capabilities, training, and deployment",
    category: "ml_ai",
    mention_count: 12,
    content_ids: [1, 2, 3, 5],
    first_seen: "2025-01-01T00:00:00Z",
    last_seen: "2025-01-15T00:00:00Z",
    trend: "growing",
    relevance_score: 0.92,
    strategic_relevance: 0.88,
    tactical_relevance: 0.85,
    novelty_score: 0.7,
    cross_functional_impact: 0.9,
    related_themes: ["AI Safety", "Multimodal AI"],
    key_points: [
      "GPT-5 announced with improved reasoning",
      "Enterprise adoption accelerating",
    ],
    ...overrides,
  }
}

export function createThemeAnalysisResult(
  overrides: Partial<ThemeAnalysisResult> = {}
): ThemeAnalysisResult {
  return {
    analysis_date: "2025-01-16T00:00:00Z",
    start_date: "2025-01-01T00:00:00Z",
    end_date: "2025-01-15T23:59:59Z",
    content_count: 25,
    content_ids: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    themes: [
      createThemeData({ name: "Large Language Models", category: "ml_ai" }),
      createThemeData({
        name: "MLOps Best Practices",
        category: "devops_infra",
        trend: "established",
        mention_count: 8,
      }),
      createThemeData({
        name: "AI Safety Regulation",
        category: "security",
        trend: "emerging",
        mention_count: 6,
      }),
    ],
    total_themes: 3,
    emerging_themes_count: 1,
    top_theme: "Large Language Models",
    processing_time_seconds: 32.5,
    token_usage: 15000,
    model_used: "claude-sonnet-4-5",
    model_version: "claude-sonnet-4-5-20250115",
    agent_framework: "claude-sdk",
    cross_theme_insights: [
      "LLM capabilities and safety regulation are becoming increasingly intertwined",
    ],
    ...overrides,
  }
}

// ─── Script Review Statistics ──────────────────────────────

export function createScriptReviewStatistics() {
  return {
    pending_review: 2,
    revision_requested: 1,
    approved_ready_for_audio: 3,
    completed_with_audio: 5,
    failed_rejected: 1,
    total: 12,
  }
}

// ─── Generic Helpers ───────────────────────────────────────

/** Create an empty paginated response */
export function createEmptyPaginatedResponse<T>(): PaginatedResponse<T> {
  return {
    items: [],
    total: 0,
    offset: 0,
    limit: 20,
    has_more: false,
  }
}

/** Create an empty content list response */
export function createEmptyContentListResponse(): ContentListResponse {
  return {
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
    has_next: false,
    has_prev: false,
  }
}

/** Create a task response for background operations */
export function createTaskResponse(
  overrides: Partial<{ task_id: string; status: string; message: string }> = {}
) {
  return {
    task_id: "task-abc-123",
    status: "processing",
    message: "Task started successfully",
    ...overrides,
  }
}

/** Create available digests for selectors */
export function createAvailableDigests() {
  return [
    {
      id: 1,
      title: "Daily AI & Data Digest - Jan 15, 2025",
      digest_type: "daily",
      period_start: "2025-01-15T00:00:00Z",
      period_end: "2025-01-15T23:59:59Z",
      status: "APPROVED",
      created_at: "2025-01-16T06:00:00Z",
    },
    {
      id: 2,
      title: "Weekly AI & Data Digest - Jan 8-14, 2025",
      digest_type: "weekly",
      period_start: "2025-01-08T00:00:00Z",
      period_end: "2025-01-14T23:59:59Z",
      status: "APPROVED",
      created_at: "2025-01-15T06:00:00Z",
    },
  ]
}

/** Create approved scripts for podcast generation selector */
export function createApprovedScripts() {
  return [
    {
      id: 1,
      digest_id: 1,
      title: "AI Weekly Deep Dive - Episode 42",
      length: "standard",
      word_count: 3200,
      estimated_duration_seconds: 720,
      approved_at: "2025-01-16T10:00:00Z",
    },
  ]
}

/** Create a single job history item */
export function createJobHistoryItem(
  overrides: Partial<{
    id: number
    entrypoint: string
    task_label: string
    status: string
    content_id: number | null
    description: string | null
    error: string | null
    created_at: string
    started_at: string | null
    completed_at: string | null
  }> = {}
) {
  return {
    id: 1,
    entrypoint: "summarize_content",
    task_label: "Summarize",
    status: "completed",
    content_id: 101,
    description: "AI Weekly Newsletter",
    error: null,
    created_at: "2025-01-16T12:00:00Z",
    started_at: "2025-01-16T12:00:01Z",
    completed_at: "2025-01-16T12:00:05Z",
    ...overrides,
  }
}

/** Create a paginated job history response */
export function createJobHistoryResponse(
  overrides: Partial<{
    data: ReturnType<typeof createJobHistoryItem>[]
    pagination: { page: number; page_size: number; total: number }
  }> = {}
) {
  return {
    data: overrides.data ?? [
      createJobHistoryItem({ id: 1, entrypoint: "summarize_content", task_label: "Summarize", status: "completed", content_id: 101, description: "AI Weekly Newsletter" }),
      createJobHistoryItem({ id: 2, entrypoint: "ingest_content", task_label: "Ingest", status: "completed", content_id: null, description: "Gmail ingestion" }),
      createJobHistoryItem({ id: 3, entrypoint: "summarize_content", task_label: "Summarize", status: "failed", content_id: 42, description: "ML Ops Digest", error: "Connection timeout" }),
    ],
    pagination: overrides.pagination ?? { page: 1, page_size: 20, total: 3 },
  }
}

/** Create chat config response */
export function createChatConfig() {
  return {
    available_models: ["claude-sonnet-4-5", "claude-haiku-4-5"],
    default_model: "claude-sonnet-4-5",
    max_messages_per_conversation: 50,
    max_message_length: 4000,
    web_search_enabled: true,
  }
}

// ─── Prompts ──────────────────────────────────────────────

/** Create a single prompt info object */
export function createPromptInfo(
  overrides: Partial<PromptInfo> = {}
): PromptInfo {
  return {
    key: "pipeline.summarization.system",
    category: "pipeline",
    name: "system",
    default_value:
      "You are a professional content analyst. Summarize the following article for a technical audience.",
    current_value:
      "You are a professional content analyst. Summarize the following article for a technical audience.",
    has_override: false,
    version: null,
    description: null,
    ...overrides,
  }
}

/** Create a prompt list response with multiple prompts across categories */
export function createPromptListResponse(
  overrides: Partial<PromptListResponse> = {}
): PromptListResponse {
  return {
    prompts: [
      createPromptInfo({
        key: "pipeline.summarization.system",
        category: "pipeline",
        name: "system",
        default_value:
          "You are a professional content analyst. Summarize the following article.",
        current_value:
          "You are a professional content analyst. Summarize the following article.",
        has_override: false,
      }),
      createPromptInfo({
        key: "pipeline.summarization.user_template",
        category: "pipeline",
        name: "user_template",
        default_value: "Title: {title}\n\nContent:\n{content}",
        current_value: "Title: {title}\n\nContent:\n{content}",
        has_override: false,
      }),
      createPromptInfo({
        key: "pipeline.digest_creation.system",
        category: "pipeline",
        name: "system",
        default_value:
          "You are an AI newsletter curator creating a {period} digest.",
        current_value:
          "You are an expert AI newsletter curator creating a {period} digest for senior engineers.",
        has_override: true,
        version: 2,
        description: "Updated for senior engineer audience",
      }),
      createPromptInfo({
        key: "chat.content.system",
        category: "chat",
        name: "system",
        default_value:
          "You are a helpful assistant that answers questions about AI newsletter content.",
        current_value:
          "You are a helpful assistant that answers questions about AI newsletter content.",
        has_override: false,
      }),
    ],
    ...overrides,
  }
}

/** Create an empty prompt list response */
export function createEmptyPromptListResponse(): PromptListResponse {
  return { prompts: [] }
}

/** Create a prompt update response */
export function createPromptUpdateResponse(
  overrides: Partial<PromptUpdateResponse> = {}
): PromptUpdateResponse {
  return {
    key: "pipeline.digest_creation.system",
    current_value:
      "You are an expert AI newsletter curator creating a {period} digest for senior engineers.",
    has_override: true,
    version: 3,
    ...overrides,
  }
}

/** Create a prompt test response */
export function createPromptTestResponse(
  overrides: Partial<PromptTestResponse> = {}
): PromptTestResponse {
  return {
    rendered_prompt:
      "You are an expert AI newsletter curator creating a daily digest for senior engineers.",
    variable_names: ["period"],
    ...overrides,
  }
}

// ─── Settings: Model Configuration ────────────────────────

export function createModelOption(overrides: Record<string, unknown> = {}) {
  return {
    id: "claude-sonnet-4-5",
    name: "Claude Sonnet 4.5",
    family: "claude",
    supports_vision: true,
    supports_video: false,
    cost_per_mtok_input: 3.0,
    cost_per_mtok_output: 15.0,
    providers: ["anthropic"],
    ...overrides,
  }
}

export function createStepConfig(overrides: Record<string, unknown> = {}) {
  return {
    step: "summarization",
    current_model: "claude-haiku-4-5",
    source: "default",
    env_var: "MODEL_SUMMARIZATION",
    default_model: "claude-haiku-4-5",
    ...overrides,
  }
}

export function createModelSettingsResponse(overrides: Record<string, unknown> = {}) {
  return {
    steps: [
      createStepConfig({
        step: "summarization",
        current_model: "claude-haiku-4-5",
        source: "default",
        env_var: "MODEL_SUMMARIZATION",
        default_model: "claude-haiku-4-5",
      }),
      createStepConfig({
        step: "theme_analysis",
        current_model: "claude-sonnet-4-5",
        source: "default",
        env_var: "MODEL_THEME_ANALYSIS",
        default_model: "claude-sonnet-4-5",
      }),
      createStepConfig({
        step: "digest_creation",
        current_model: "claude-sonnet-4-5",
        source: "db",
        env_var: "MODEL_DIGEST_CREATION",
        default_model: "claude-haiku-4-5",
      }),
    ],
    available_models: [
      createModelOption({
        id: "claude-haiku-4-5",
        name: "Claude Haiku 4.5",
        family: "claude",
        cost_per_mtok_input: 0.8,
        cost_per_mtok_output: 4.0,
      }),
      createModelOption({
        id: "claude-sonnet-4-5",
        name: "Claude Sonnet 4.5",
        family: "claude",
        cost_per_mtok_input: 3.0,
        cost_per_mtok_output: 15.0,
      }),
      createModelOption({
        id: "gemini-2.5-flash",
        name: "Gemini 2.5 Flash",
        family: "gemini",
        supports_video: true,
        cost_per_mtok_input: 0.15,
        cost_per_mtok_output: 0.6,
        providers: ["google"],
      }),
    ],
    ...overrides,
  }
}

export function createEmptyModelSettingsResponse() {
  return { steps: [], available_models: [] }
}

// ─── Settings: Voice Configuration ────────────────────────

export function createVoiceSettingInfo(overrides: Record<string, unknown> = {}) {
  return {
    key: "voice.provider",
    value: "openai",
    source: "default",
    ...overrides,
  }
}

export function createVoiceSettingsResponse(overrides: Record<string, unknown> = {}) {
  return {
    provider: createVoiceSettingInfo({ key: "voice.provider", value: "openai", source: "default" }),
    default_voice: createVoiceSettingInfo({ key: "voice.default_voice", value: "nova", source: "default" }),
    speed: createVoiceSettingInfo({ key: "voice.speed", value: "1.0", source: "default" }),
    input_language: createVoiceSettingInfo({ key: "voice.input_language", value: "en-US", source: "default" }),
    input_continuous: createVoiceSettingInfo({ key: "voice.input_continuous", value: "false", source: "default" }),
    input_auto_submit: createVoiceSettingInfo({ key: "voice.input_auto_submit", value: "false", source: "default" }),
    presets: [
      { name: "professional", voices: { openai: "nova", elevenlabs: "Rachel" } },
      { name: "warm", voices: { openai: "shimmer", elevenlabs: "Domi" } },
      { name: "energetic", voices: { openai: "echo", elevenlabs: "Bella" } },
      { name: "calm", voices: { openai: "fable", elevenlabs: "Elli" } },
    ],
    valid_providers: ["openai", "elevenlabs"],
    valid_input_languages: ["en-US", "en-GB", "es-ES", "fr-FR", "de-DE", "ja-JP", "zh-CN"],
    ...overrides,
  }
}

// ─── Settings: Connection Status ──────────────────────────

export function createServiceStatus(overrides: Record<string, unknown> = {}) {
  return {
    name: "PostgreSQL",
    status: "ok",
    details: "local provider",
    latency_ms: 5.2,
    ...overrides,
  }
}

export function createConnectionStatusResponse(overrides: Record<string, unknown> = {}) {
  return {
    services: [
      createServiceStatus({ name: "PostgreSQL", status: "ok", details: "local provider", latency_ms: 5.2 }),
      createServiceStatus({ name: "Neo4j", status: "not_configured", details: "No URI configured", latency_ms: null }),
      createServiceStatus({ name: "Anthropic", status: "ok", details: "API key configured", latency_ms: null }),
      createServiceStatus({ name: "OpenAI", status: "not_configured", details: "OPENAI_API_KEY not set", latency_ms: null }),
      createServiceStatus({ name: "Embeddings", status: "ok", details: "local provider", latency_ms: 12.3 }),
    ],
    all_ok: true,
    ...overrides,
  }
}

// ─── Auth ─────────────────────────────────────────────────────

/** Create a session response (authenticated or not) */
export function createSessionResponse(
  overrides: Partial<{ authenticated: boolean }> = {}
) {
  return {
    authenticated: false,
    ...overrides,
  }
}

/** Create a successful login response */
export function createLoginSuccessResponse() {
  return {
    authenticated: true,
  }
}

/** Create a failed login response (401) */
export function createLoginFailureResponse(
  overrides: Partial<{ detail: string }> = {}
) {
  return {
    detail: "Invalid password",
    ...overrides,
  }
}

/** Create a rate-limited login response (429) */
export function createLoginRateLimitedResponse(
  overrides: Partial<{ detail: string }> = {}
) {
  return {
    detail: "Too many attempts. Please try again later.",
    ...overrides,
  }
}
