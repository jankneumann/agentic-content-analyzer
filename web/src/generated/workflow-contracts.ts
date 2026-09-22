// Generated from contracts/openapi/v1.yaml; do not edit.
export const CONTRACT_SHA256 = "4a676697b5d8db6579b6efe1d708a33567d9443152a983ec2cd4dfc0f7eb7536" as const;

export type OperationStatus = "queued" | "in_progress" | "completed" | "failed" | "cancelled";
export type OperationType = "ingestion.execute" | "summarization.run" | "theme_analysis.create" | "digest.create" | "pipeline.run" | "podcast_script.create" | "podcast_audio.create" | "audio_digest.create";
export type IngestionOutcome = "success" | "zero_items" | "partial" | "failed" | "cancelled" | "unknown";
export type IngestionStatus = "ok" | "partial" | "error";
export type TerminalOperationStatus = "completed" | "failed" | "cancelled";
export type ContentReconciliationMode = "dry_run" | "apply";
export type ContentReconciliationProjection = "proposed" | "observed";
export type ContentReconciliationContentStatus = "pending" | "parsing" | "parsed" | "processing" | "completed" | "failed" | "filtered_out";
export type ContentReconciliationOperationStatus = "queued" | "in_progress" | "completed" | "failed" | "cancelled";
export type ContentReconciliationPhase = "parsing" | "processing";
export type ContentReconciliationAction = "none" | "retry_operation" | "project_completed" | "project_parsed" | "restore_parsed" | "restore_pending" | "cancel_restore_parsed" | "cancel_restore_pending";
export type ContentReconciliationReason = "summary_exists" | "extraction_completed" | "completed_output_missing" | "output_owner_mismatch" | "active_operation" | "cancellation_pending" | "execution_locked" | "cancellation_requested" | "stale_operation" | "failed_operation" | "retry_budget_exhausted" | "forced_reprocessing" | "summarization_cancelled" | "extraction_cancelled" | "missing_operation" | "ownership_conflict" | "incompatible_worker" | "revalidation_conflict" | "apply_failed";
export type SourceManagementType = "blog" | "rss" | "substack" | "podcast" | "youtube_playlist" | "youtube_channel" | "youtube_rss" | "gmail" | "scholar" | "arxiv" | "huggingface_papers" | "websearch" | "readwise" | "obsidian_vault";
export type PublicSourceKey = string;

export interface LegacyDetailError {
  detail: string;
}

export interface LegacyAuthError {
  error: string;
  detail: string;
  trace_id?: string | null;
}

export interface LegacyValidationErrorBody {
  detail: Array<LegacyValidationErrorItem>;
}

export interface LegacyValidationErrorItem {
  [key: string]: unknown;
  type: string;
  loc: Array<string | number>;
  msg: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}

export interface Problem {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance?: string | null;
  code?: string | null;
  errors?: Array<Record<string, unknown>>;
}

export interface ResourceReference {
  type: "content" | "ingestion_run" | "summary_batch" | "theme_analysis" | "digest" | "pipeline_run" | "podcast_script" | "podcast" | "audio_digest";
  id: string;
  url: string;
}

export interface BoundedDiagnostic {
  code: string;
  message: string;
  redirected_source_key?: string | null;
}

export interface ConfiguredSourceOutcome {
  source_key: string;
  status: IngestionStatus;
  items_ingested: number;
  items_failed: number;
  errors: Array<BoundedDiagnostic>;
  warnings: Array<BoundedDiagnostic>;
  errors_omitted: number;
  warnings_omitted: number;
}

export interface IngestionResultV1 {
  schema_version?: 1;
  command_key: string;
  resolved_route: string;
  emitted_sources: Array<string>;
  items_ingested: number;
  content_ids: Array<number>;
  warnings?: Array<string>;
  details?: Record<string, unknown>;
}

export interface IngestionResultV2 {
  schema_version: 2;
  command_key: string;
  resolved_route: string;
  emitted_sources: Array<string>;
  status: IngestionStatus;
  outcome: IngestionOutcome;
  items_ingested: number;
  items_skipped: number;
  items_failed: number;
  content_ids: Array<number>;
  errors: Array<BoundedDiagnostic>;
  warnings: Array<BoundedDiagnostic>;
  errors_omitted: number;
  warnings_omitted: number;
  source_outcomes: Array<ConfiguredSourceOutcome>;
  source_outcomes_omitted: number;
  details: SafeIngestionDetails;
  details_omitted: number;
}

export interface SafeIngestionDetails {
  dry_run?: boolean;
  duplicate?: boolean;
  version_updated?: boolean;
  papers_ingested?: number;
  refs_ingested?: number;
  content_scanned?: number;
  references_found?: number;
  references_resolved?: number;
  references_unresolved?: number;
  queries_made?: number;
  citations_found?: number;
  tool_calls_made?: number;
  threads_found?: number;
}

export interface PipelineSourceIngestionSummary {
  operation_id: string;
  command_key: string;
  operation_status: TerminalOperationStatus;
  outcome: IngestionOutcome;
  items_ingested: number | null;
  items_skipped: number | null;
  items_failed: number | null;
}

export interface PipelineIngestionSummary {
  outcome: IngestionOutcome;
  sources: Array<PipelineSourceIngestionSummary>;
  sources_omitted: number;
}

export interface PipelineResultV2 {
  [key: string]: unknown;
  schema_version: 2;
  ingestion_summary: PipelineIngestionSummary;
}

export interface ConfiguredSourceHistoryOutcome {
  source_key: string;
  status: IngestionStatus;
  outcome: IngestionOutcome;
  items_ingested: number | null;
  items_failed: number | null;
  error_codes?: Array<string>;
  warning_codes?: Array<string>;
}

export interface IngestionHistoryItem {
  operation_id: string;
  parent_operation_id?: string | null;
  command_key: string;
  operation_status: TerminalOperationStatus;
  outcome: IngestionOutcome;
  items_ingested: number | null;
  items_skipped: number | null;
  items_failed: number | null;
  source_outcomes: Array<ConfiguredSourceHistoryOutcome>;
  retry_count: number;
  problem_code?: string | null;
  status_url: string;
  created_at: string;
  completed_at?: string | null;
}

export interface IngestionHistoryPage {
  data: Array<IngestionHistoryItem>;
  next_cursor?: string | null;
}

export interface OperationSummary {
  schema_version: 2;
  operation_id: string;
  operation_type: "ingestion.execute" | "summarization.run" | "theme_analysis.create" | "digest.create" | "pipeline.run" | "podcast_script.create" | "podcast_audio.create" | "audio_digest.create";
  status: OperationStatus;
  progress: number;
  message: string;
  cancellable: boolean;
  retry_count: number;
  status_url: string;
  events_url: string;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface OperationHandle {
  schema_version: 2;
  operation_id: string;
  operation_type: "ingestion.execute" | "summarization.run" | "theme_analysis.create" | "digest.create" | "pipeline.run" | "podcast_script.create" | "podcast_audio.create" | "audio_digest.create";
  status: OperationStatus;
  progress: number;
  message: string;
  cancellable: boolean;
  retry_count: number;
  status_url: string;
  events_url: string;
  resource?: ResourceReference | null;
  result?: Record<string, unknown> | null;
  problem?: Problem | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface OperationPage {
  data: Array<OperationSummary>;
  next_cursor?: string | null;
}

export interface WorkflowAlertVerificationContext {
  schema_version: 1;
  environment_class: "staging";
  revision: string;
  revision_source: "railway_commit_sha";
}

export interface WorkflowTerminalDeliveryCounts {
  pending: number;
  leased: number;
  delivered: number;
  permanent_failure: number;
  exhausted: number;
}

export interface WorkflowTerminalEventDiagnostic {
  schema_version: 1;
  event_id: string;
  event_key: string;
  source_kind: "operation" | "reconciliation_action" | "reconciliation_failure" | "system_check";
  operation_id: string | null;
  claim_generation: number | null;
  terminal_status: "completed" | "failed" | "cancelled" | null;
  classification_status: "pending" | "ready" | "telemetry_only" | "rejected";
  release_revision: string | null;
  release_revision_source: "railway_commit_sha" | "local_development" | "unavailable" | null;
  occurred_at: string;
  telemetry_emitted_at: string | null;
  delivery_counts: WorkflowTerminalDeliveryCounts;
}

export interface ContentReconciliationRequest {
  apply?: boolean;
  limit?: number;
  after_content_id?: number | null;
}

export interface ContentReconciliationCounts {
  applied: number;
  retried: number;
  projected: number;
  restored: number;
  active: number;
  locked: number;
  missing: number;
  conflicted: number;
  cancelled: number;
  forced: number;
  exhausted: number;
  incompatible: number;
  failed: number;
}

export interface ContentReconciliationItem {
  content_id: number;
  projection: ContentReconciliationProjection;
  content_status_before: ContentReconciliationContentStatus;
  content_status_after: ContentReconciliationContentStatus;
  operation_id: string | null;
  claim_generation: number | null;
  claim_protocol_version: number | null;
  operation_status_before: ContentReconciliationOperationStatus | null;
  operation_status_after: ContentReconciliationOperationStatus | null;
  retry_count_before: number | null;
  retry_count_after: number | null;
  phase: ContentReconciliationPhase | null;
  action: ContentReconciliationAction;
  reason: ContentReconciliationReason;
  operation_heartbeat_at?: string | null;
  operation_completed_at?: string | null;
  applied: boolean;
}

export interface ContentReconciliationReport {
  run_id: string;
  mode: ContentReconciliationMode;
  scanned: number;
  reported: number;
  next_after_content_id?: number | null;
  counts: ContentReconciliationCounts;
  items: Array<ContentReconciliationItem>;
}

export interface OperationEvent {
  schema_version: 2;
  event_id: string;
  operation_id: string;
  operation_type: "ingestion.execute" | "summarization.run" | "theme_analysis.create" | "digest.create" | "pipeline.run" | "podcast_script.create" | "podcast_audio.create" | "audio_digest.create";
  status: OperationStatus;
  progress: number;
  message: string;
  resource?: ResourceReference | null;
  problem?: Problem | null;
  occurred_at: string;
}

export interface UploadReference {
  id: string;
  filename: string;
  media_type: string;
  size_bytes: number;
  title?: string | null;
  publication?: string | null;
}

export interface CapabilityField {
  name: string;
  type: string;
  required: boolean;
  description?: string | null;
  format?: string | null;
  enum?: Array<string>;
  default?: unknown;
  constraints?: Record<string, unknown>;
}

export interface SourceCapability {
  key: string;
  display_name: string;
  emitted_sources: Array<string>;
  scheduled: boolean;
  supports_force: boolean;
  supports_date_range: boolean;
  supports_preview: boolean;
  requires_identifier: boolean;
  transports: Array<"cli" | "http" | "mcp" | "frontend">;
  fields: Array<CapabilityField>;
}

export interface CapabilityDocument {
  contract_version: string;
  source_commands: Array<SourceCapability>;
  operation_types: Array<string>;
  resource_types: Array<string>;
  next_cursor?: string | null;
}

export interface SourceConfigBase {
  [key: string]: unknown;
  name?: string | null;
  tags?: Array<string>;
  enabled?: boolean;
  max_entries?: number | null;
  content_filter_strategy?: string | null;
  content_filter_topics?: Array<string> | null;
  content_filter_excerpt_chars?: number | null;
}

export interface BlogSourceOverrideConfig extends SourceConfigBase {
  type: "blog";
  url: string;
  link_selector?: string | null;
  link_pattern?: string | null;
  request_delay?: number;
  rss_url?: string | null;
}

export interface RSSSourceOverrideConfig extends SourceConfigBase {
  type: "rss";
  url: string;
}

export interface SubstackSourceOverrideConfig extends SourceConfigBase {
  type: "substack";
  url: string;
}

export interface PodcastSourceOverrideConfig extends SourceConfigBase {
  type: "podcast";
  url: string;
  transcribe?: boolean;
  stt_provider?: "openai" | "local_whisper";
  languages?: Array<string>;
}

export interface YouTubeSourceConfigBase {
  [key: string]: unknown;
  min_duration_seconds?: number | null;
  max_duration_seconds?: number | null;
  long_video_threshold_seconds?: number;
  long_video_strategy?: "grounding" | "segments";
  video_fps?: number | null;
  segment_overlap_seconds?: number;
  unknown_duration_strategy?: "short" | "grounding" | "segments" | "skip";
}

export interface YouTubePlaylistSourceOverrideConfig extends SourceConfigBase {
  type: "youtube_playlist";
  id: string;
  visibility?: "public" | "private";
  min_duration_seconds?: number | null;
  max_duration_seconds?: number | null;
  long_video_threshold_seconds?: number;
  long_video_strategy?: "grounding" | "segments";
  video_fps?: number | null;
  segment_overlap_seconds?: number;
  unknown_duration_strategy?: "short" | "grounding" | "segments" | "skip";
  hint_terms?: Array<string>;
  proofread?: boolean;
  gemini_summary?: boolean;
  gemini_resolution?: string;
}

export interface YouTubeChannelSourceOverrideConfig extends SourceConfigBase {
  type: "youtube_channel";
  channel_id: string;
  visibility?: "public" | "private";
  min_duration_seconds?: number | null;
  max_duration_seconds?: number | null;
  long_video_threshold_seconds?: number;
  long_video_strategy?: "grounding" | "segments";
  video_fps?: number | null;
  segment_overlap_seconds?: number;
  unknown_duration_strategy?: "short" | "grounding" | "segments" | "skip";
  languages?: Array<string>;
  hint_terms?: Array<string>;
  proofread?: boolean;
  gemini_summary?: boolean;
  gemini_resolution?: string;
}

export interface YouTubeRSSSourceOverrideConfig extends SourceConfigBase {
  type: "youtube_rss";
  url: string;
  min_duration_seconds?: number | null;
  max_duration_seconds?: number | null;
  long_video_threshold_seconds?: number;
  long_video_strategy?: "grounding" | "segments";
  video_fps?: number | null;
  segment_overlap_seconds?: number;
  unknown_duration_strategy?: "short" | "grounding" | "segments" | "skip";
  gemini_summary?: boolean;
  gemini_resolution?: string;
}

export interface GmailSourceOverrideConfig extends SourceConfigBase {
  type: "gmail";
  query?: string;
  max_results?: number;
}

export interface ScholarSourceOverrideConfig extends SourceConfigBase {
  type: "scholar";
  query: string;
  fields_of_study?: Array<string>;
  paper_types?: Array<string>;
  min_citation_count?: number;
  year_range?: string;
  venues?: Array<string>;
}

export interface ArxivSourceOverrideConfig extends SourceConfigBase {
  type: "arxiv";
  categories?: Array<string>;
  search_query?: string | null;
  sort_by?: "relevance" | "lastUpdatedDate" | "submittedDate";
  pdf_extraction?: boolean;
  max_pdf_pages?: number;
}

export interface HuggingFacePapersSourceOverrideConfig extends SourceConfigBase {
  type: "huggingface_papers";
  url?: string;
  request_delay?: number;
}

export interface WebSearchSourceOverrideConfig extends SourceConfigBase {
  type: "websearch";
  provider: "perplexity" | "grok";
  prompt: string;
  max_results?: number | null;
  max_threads?: number | null;
  recency_filter?: string | null;
  context_size?: string | null;
  domain_filter?: Array<string> | null;
}

export interface ReadwiseSourceOverrideConfig extends SourceConfigBase {
  type: "readwise";
  source_types?: Array<string>;
  include_deleted?: boolean;
}

export interface ObsidianVaultSourceOverrideConfig {
  type: "obsidian_vault";
  name?: string | null;
  tags?: Array<string>;
  enabled?: boolean;
  content_filter_strategy?: string | null;
  content_filter_topics?: Array<string> | null;
  content_filter_excerpt_chars?: number | null;
  origin?: "yaml" | "db";
  vault_id: string;
  vault_path: string;
  ingest_folder?: string;
  max_files?: number;
  max_entries?: number;
  max_total_bytes?: number;
  max_depth?: number;
  max_duration_seconds?: number;
  max_note_bytes?: number;
  settle_seconds?: number;
  max_concurrency?: number;
  max_frontmatter_bytes?: number;
  max_yaml_nodes?: number;
  max_yaml_depth?: number;
  max_yaml_aliases?: number;
  max_yaml_string_chars?: number;
}

export interface SourceUpsertRequest {
  [key: string]: unknown;
  config: SourceOverrideConfig;
  description?: string | null;
}

export interface SourceEnabledRequest {
  [key: string]: unknown;
  enabled: boolean;
}

export interface SourceInfo {
  type: SourceManagementType;
  name: string | null;
  url: string;
  enabled: boolean;
  tags: Array<string>;
  origin: "yaml" | "db";
  source_key: PublicSourceKey | null;
}

export interface SourcesOverview {
  sources: Array<SourceInfo>;
  counts: Record<string, number>;
  total_sources: number;
  enabled_sources: number;
}

export interface SourceMutationResult {
  source_key: PublicSourceKey;
  version: number;
  origin: "db";
  enabled: boolean;
}

export interface SourceDeleteResult {
  source_key: PublicSourceKey;
  deleted: boolean;
}

export interface ConfiguredSource {
  key: string;
  command_key: string;
  source_type: string;
  name?: string | null;
  enabled: boolean;
  origin: "yaml" | "db";
  configuration: Record<string, unknown>;
  ready: boolean;
  readiness_code: string | null;
}

export interface ConfiguredSourcePage {
  data: Array<ConfiguredSource>;
  next_cursor?: string | null;
}

export interface ContentQuery {
  source_types?: Array<"gmail" | "rss" | "file_upload" | "youtube" | "podcast" | "substack" | "manual" | "webpage" | "xsearch" | "perplexity" | "blog" | "scholar" | "arxiv" | "huggingface_papers" | "readwise" | "obsidian" | "other">;
  statuses?: Array<"pending" | "parsing" | "parsed" | "processing" | "completed" | "failed" | "filtered_out">;
  publications?: Array<string>;
  publication_search?: string;
  start_date?: string;
  end_date?: string;
  date_basis?: "published_date" | "ingested_at";
  search?: string;
  limit?: number;
  sort_by?: "id" | "title" | "source_type" | "publication" | "status" | "published_date" | "ingested_at";
  sort_order?: "asc" | "desc";
  canonical_only?: boolean;
  require_summary?: boolean;
}

export interface ConfiguredSourceCommandBase {
  max_items?: number;
  days_back?: number;
  after_date?: string;
  force_reprocess?: boolean;
}

export interface GmailIngestCommand extends ConfiguredSourceCommandBase {
  kind: "gmail";
  query?: string;
  max_items?: number;
  days_back?: number;
  after_date?: string;
  force_reprocess?: boolean;
}

export interface RssIngestCommand {
  kind: "rss";
  max_items?: number;
  days_back?: number;
  after_date?: string;
  force_reprocess?: boolean;
}

export interface BlogIngestCommand {
  kind: "blog";
  max_items?: number;
  days_back?: number;
  after_date?: string;
  force_reprocess?: boolean;
}

export interface SubstackIngestCommand {
  kind: "substack";
  max_items?: number;
  days_back?: number;
  after_date?: string;
  force_reprocess?: boolean;
}

export interface YouTubePlaylistIngestCommand {
  kind: "youtube_playlist";
  max_items?: number;
  days_back?: number;
  after_date?: string;
  force_reprocess?: boolean;
  public_only?: boolean;
}

export interface YouTubeRssIngestCommand {
  kind: "youtube_rss";
  max_items?: number;
  days_back?: number;
  after_date?: string;
  force_reprocess?: boolean;
}

export interface PodcastIngestCommand {
  kind: "podcast";
  max_items?: number;
  days_back?: number;
  after_date?: string;
  force_reprocess?: boolean;
  transcribe?: boolean;
}

export interface XSearchIngestCommand {
  kind: "x_search";
  prompt?: string;
  max_threads?: number;
  force_reprocess?: boolean;
}

export interface PerplexitySearchIngestCommand {
  kind: "perplexity_search";
  prompt?: string;
  max_items?: number;
  recency?: "hour" | "day" | "week" | "month";
  context_size?: "low" | "medium" | "high";
  force_reprocess?: boolean;
}

export interface FilesIngestCommand {
  kind: "files";
  upload_ids: Array<string>;
  force_reprocess?: boolean;
}

export interface UrlIngestCommand {
  kind: "url";
  url: string;
  title?: string;
  tags?: Array<string>;
  notes?: string;
  routing_mode?: "auto" | "webpage";
  force_reprocess?: boolean;
}

export interface ScholarSearchIngestCommand {
  kind: "scholar_search";
  max_items?: number;
}

export interface ScholarPaperIngestCommand {
  kind: "scholar_paper";
  identifier: string;
  with_references?: boolean;
}

export interface ScholarReferencesIngestCommand {
  kind: "scholar_references";
  after?: string;
  before?: string;
  source_types?: Array<string>;
  dry_run?: boolean;
  limit?: number;
}

export interface ArxivSearchIngestCommand {
  kind: "arxiv_search";
  max_items?: number;
  days_back?: number;
  after_date?: string;
  force_reprocess?: boolean;
  extract_pdf?: boolean;
}

export interface ArxivPaperIngestCommand {
  kind: "arxiv_paper";
  identifier: string;
  extract_pdf?: boolean;
  force_reprocess?: boolean;
}

export interface HuggingFacePapersIngestCommand {
  kind: "huggingface_papers";
  max_items?: number;
  days_back?: number;
  after_date?: string;
  force_reprocess?: boolean;
}

export interface ReadwiseIngestCommand {
  kind: "readwise";
  updated_after?: string;
  source_types?: Array<string>;
  include_deleted?: boolean;
  max_books?: number;
  force_reprocess?: boolean;
}

export interface ObsidianVaultIngestCommand {
  kind: "obsidian_vault";
  source_key: string;
  max_items?: number;
  force_reprocess?: boolean;
}

export interface SummarizationRequest {
  content_ids?: Array<number>;
  query?: ContentQuery;
  force_reprocess?: boolean;
}

export interface ThemeAnalysisRequest {
  query: ContentQuery;
  max_themes?: number;
}

export interface DigestCreateRequest {
  digest_type: "daily" | "weekly";
  period_start: string;
  period_end: string;
  query?: ContentQuery;
  include_historical_context?: boolean;
}

export interface PipelineRequest {
  period: "daily" | "weekly";
  period_start: string;
  period_end: string;
  sources?: Array<string>;
  continue_on_source_error?: boolean;
}

export interface PodcastScriptRequest {
  digest_id: number;
  length?: "brief" | "standard" | "extended";
  enable_web_search?: boolean;
  custom_focus_topics?: Array<string>;
  custom_instructions?: string;
}

export interface PodcastAudioRequest {
  script_id: number;
  voice_provider?: "elevenlabs" | "google_tts" | "aws_polly" | "openai_tts";
  alex_voice?: "alex_male" | "alex_female";
  sam_voice?: "sam_male" | "sam_female";
}

export interface AudioDigestRequest {
  digest_id: number;
  provider?: string;
  voice?: string;
  speed?: number;
}

export type IngestionResult = IngestionResultV1 | IngestionResultV2;

export type SourceOverrideConfig = BlogSourceOverrideConfig | RSSSourceOverrideConfig | SubstackSourceOverrideConfig | PodcastSourceOverrideConfig | YouTubePlaylistSourceOverrideConfig | YouTubeChannelSourceOverrideConfig | YouTubeRSSSourceOverrideConfig | GmailSourceOverrideConfig | ScholarSourceOverrideConfig | ArxivSourceOverrideConfig | HuggingFacePapersSourceOverrideConfig | WebSearchSourceOverrideConfig | ReadwiseSourceOverrideConfig | ObsidianVaultSourceOverrideConfig;

export type IngestCommand = GmailIngestCommand | RssIngestCommand | BlogIngestCommand | SubstackIngestCommand | YouTubePlaylistIngestCommand | YouTubeRssIngestCommand | PodcastIngestCommand | XSearchIngestCommand | PerplexitySearchIngestCommand | FilesIngestCommand | UrlIngestCommand | ScholarSearchIngestCommand | ScholarPaperIngestCommand | ScholarReferencesIngestCommand | ArxivSearchIngestCommand | ArxivPaperIngestCommand | HuggingFacePapersIngestCommand | ReadwiseIngestCommand | ObsidianVaultIngestCommand;
