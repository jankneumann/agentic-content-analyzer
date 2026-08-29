// Generated from contracts/openapi/v1.yaml; do not edit.
export const CONTRACT_SHA256 = "cf0dbd992a3617bd4887ea21e305e9cee0b7eb360f7f3f060fea4ce85a401c55" as const;

export type OperationStatus = "queued" | "in_progress" | "completed" | "failed" | "cancelled";
export type OperationType = "ingestion.execute" | "summarization.run" | "theme_analysis.create" | "digest.create" | "pipeline.run" | "podcast_script.create" | "podcast_audio.create" | "audio_digest.create";
type Brand<Value, Name extends string> = Value & { readonly __brand: Name };
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
export type TraceId = Brand<string, "TraceId">;
export type SpanId = Brand<string, "SpanId">;
export type OperationId = Brand<string, "OperationId">;
export type Int64NonNegativeString = Brand<string, "Int64NonNegativeString">;
export type ClaimGenerationString = Brand<string, "ClaimGenerationString">;
export type Int64PositiveString = Brand<string, "Int64PositiveString">;
export type OperationStage = "submit" | "queue_wait" | "claim" | "fetch" | "discover" | "metadata" | "transcript" | "extract" | "parse" | "filter" | "deduplicate" | "model" | "fallback" | "persist" | "index" | "graph" | "deliver" | "backup" | "restore" | "alert" | "cleanup" | "flush";
export type OperationOutcome = "succeeded" | "partial" | "skipped_policy" | "skipped_duplicate" | "filtered" | "retryable_failure" | "permanent_failure" | "cancelled";
export type TelemetryDeliveryState = "pending" | "delivered" | "degraded" | "dropped" | "disabled";
export const SIGNED_BIGINT_MAX = 9223372036854775807n;
export const CLAIM_GENERATION_MAX = 9223372036854775806n;
const CANONICAL_DECIMAL = /^(0|[1-9][0-9]*)$/;
const TRACE_ID = /^[0-9a-f]{32}$/;
const SPAN_ID = /^[0-9a-f]{16}$/;
const AUTHORITY_FINGERPRINT = /^[0-9a-f]{64}$/;
const TRACEPARENT = /^00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}$/;
const TRACESTATE_KEY = /^[a-z0-9][a-z0-9_*/-]{0,255}$/;
const OPERATION_STAGES = new Set<string>(["submit", "queue_wait", "claim", "fetch", "discover", "metadata", "transcript", "extract", "parse", "filter", "deduplicate", "model", "fallback", "persist", "index", "graph", "deliver", "backup", "restore", "alert", "cleanup", "flush"]);
const CONTEXT_KEYS = new Set([
  "schema_version", "operation_id", "root_operation_id", "parent_operation_id",
  "traceparent", "tracestate", "trace_id", "span_id", "claim_generation",
  "attempt_number", "entrypoint", "service_name", "service_instance_id",
  "environment", "release_revision", "authority_fingerprint", "ownership_epoch",
  "stage", "resource_kind", "resource_key",
]);
const codePointLength = (value: string): number => Array.from(value).length;

function isBoundedDecimal(value: string, minimum: bigint, maximum: bigint): boolean {
  return value.length <= 19 && CANONICAL_DECIMAL.test(value)
    && BigInt(value) >= minimum && BigInt(value) <= maximum;
}

export function isOperationId(value: string): value is OperationId {
  return isBoundedDecimal(value, 1n, SIGNED_BIGINT_MAX);
}
export function isClaimGenerationString(value: string): value is ClaimGenerationString {
  return isBoundedDecimal(value, 0n, CLAIM_GENERATION_MAX);
}
export function isInt64PositiveString(value: string): value is Int64PositiveString {
  return isBoundedDecimal(value, 1n, SIGNED_BIGINT_MAX);
}
export function isInt64NonNegativeString(value: string): value is Int64NonNegativeString {
  return isBoundedDecimal(value, 0n, SIGNED_BIGINT_MAX);
}
export function isTraceId(value: string): value is TraceId {
  return TRACE_ID.test(value) && value !== "0".repeat(32);
}
export function isSpanId(value: string): value is SpanId {
  return SPAN_ID.test(value) && value !== "0".repeat(16);
}

function isValidTracestate(value: string): boolean {
  if (value.length < 1 || value.length > 512) return false;
  const members = value.split(",");
  if (members.length < 1 || members.length > 32) return false;
  const keys = new Set<string>();
  return members.every((member) => {
    const separator = member.indexOf("=");
    if (separator < 1) return false;
    const key = member.slice(0, separator);
    const memberValue = member.slice(separator + 1);
    if (!TRACESTATE_KEY.test(key) || keys.has(key) || memberValue.length < 1 || memberValue.length > 256) return false;
    for (const char of memberValue) {
      const code = char.charCodeAt(0);
      if (code < 0x21 || code > 0x7e || char === "," || char === "=") return false;
    }
    keys.add(key);
    return true;
  });
}

/** Mandatory semantic ingress validator; structural validation alone is insufficient. */
export function parseOperationContextEnvelope(value: unknown): OperationContextEnvelope {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError("operation context must be an object");
  }
  const context = value as Record<string, unknown>;
  const keys = Object.keys(context);
  if (keys.length !== CONTEXT_KEYS.size || keys.some((key) => !CONTEXT_KEYS.has(key))) {
    throw new TypeError("operation context keys do not match schema version 1");
  }
  const boundedString = (field: string, minimum: number, maximum: number): string => {
    const item = context[field];
    if (typeof item !== "string" || codePointLength(item) < minimum || codePointLength(item) > maximum) {
      throw new TypeError(`${field} is outside its string bounds`);
    }
    return item;
  };
  if (context.schema_version !== 1) throw new TypeError("schema_version must be 1");
  if (typeof context.operation_id !== "string" || !isOperationId(context.operation_id)) throw new TypeError("invalid operation_id");
  if (typeof context.root_operation_id !== "string" || !isOperationId(context.root_operation_id)) throw new TypeError("invalid root_operation_id");
  if (context.parent_operation_id !== null && (typeof context.parent_operation_id !== "string" || !isOperationId(context.parent_operation_id))) throw new TypeError("invalid parent_operation_id");
  if (typeof context.trace_id !== "string" || !isTraceId(context.trace_id)) throw new TypeError("invalid trace_id");
  if (typeof context.span_id !== "string" || !isSpanId(context.span_id)) throw new TypeError("invalid span_id");
  const carrier = typeof context.traceparent === "string" ? TRACEPARENT.exec(context.traceparent) : null;
  if (carrier === null || carrier[1] !== context.trace_id || carrier[2] !== context.span_id) throw new TypeError("invalid or mismatched traceparent");
  if (context.tracestate !== null && (typeof context.tracestate !== "string" || !isValidTracestate(context.tracestate))) throw new TypeError("invalid tracestate");
  if (typeof context.claim_generation !== "string" || !isClaimGenerationString(context.claim_generation)) throw new TypeError("invalid claim_generation");
  if (context.attempt_number !== null && (typeof context.attempt_number !== "string" || !isInt64PositiveString(context.attempt_number) || BigInt(context.attempt_number) !== BigInt(context.claim_generation) + 1n)) throw new TypeError("invalid attempt_number");
  boundedString("entrypoint", 1, 160);
  boundedString("service_name", 1, 100);
  boundedString("service_instance_id", 1, 128);
  boundedString("environment", 1, 32);
  boundedString("release_revision", 1, 64);
  if (context.authority_fingerprint !== null && (typeof context.authority_fingerprint !== "string" || !AUTHORITY_FINGERPRINT.test(context.authority_fingerprint))) throw new TypeError("invalid authority_fingerprint");
  if (context.ownership_epoch !== null && (typeof context.ownership_epoch !== "string" || !isInt64NonNegativeString(context.ownership_epoch))) throw new TypeError("invalid ownership_epoch");
  if (context.stage !== null && (typeof context.stage !== "string" || !OPERATION_STAGES.has(context.stage))) throw new TypeError("invalid stage");
  if (context.resource_kind !== null && (typeof context.resource_kind !== "string" || codePointLength(context.resource_kind) > 64)) throw new TypeError("invalid resource_kind");
  if (context.resource_key !== null && (typeof context.resource_key !== "string" || codePointLength(context.resource_key) > 128)) throw new TypeError("invalid resource_key");
  return context as unknown as OperationContextEnvelope;
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
  observability?: OperationObservabilitySummary | null;
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

export interface OperationContextEnvelope {
  schema_version: 1;
  operation_id: OperationId;
  root_operation_id: OperationId;
  parent_operation_id: OperationId | null;
  traceparent: string;
  tracestate: string | null;
  trace_id: TraceId;
  span_id: SpanId;
  claim_generation: ClaimGenerationString;
  attempt_number: Int64PositiveString | null;
  entrypoint: string;
  service_name: string;
  service_instance_id: string;
  environment: string;
  release_revision: string;
  authority_fingerprint: string | null;
  ownership_epoch: Int64NonNegativeString | null;
  stage: OperationStage | null;
  resource_kind: string | null;
  resource_key: string | null;
}

export interface OperationAttemptSummary {
  claim_generation: ClaimGenerationString;
  attempt_number: Int64PositiveString;
  trace_id: TraceId;
  root_span_id: SpanId | null;
  langfuse_observation_id: string | null;
  service_name: string;
  service_instance_id: string;
  environment: string;
  release_revision: string;
  started_at: string;
  completed_at: string | null;
  terminal_stage: OperationStage | null;
  outcome: OperationOutcome | null;
  retryable: boolean | null;
  telemetry_delivery_state: TelemetryDeliveryState;
  diagnostic_codes: Array<string>;
  diagnostics_omitted: number;
}

export interface OperationObservabilitySummary {
  root_operation_id: OperationId;
  trace_id: TraceId;
  attempt_count: number;
  latest_attempt: OperationAttemptSummary | null;
  telemetry_delivery_state: TelemetryDeliveryState;
  langfuse_url: string | null;
}

export interface OperationAttemptPage {
  schema_version: 1;
  operation_id: OperationId;
  root_operation_id: OperationId;
  attempts: Array<OperationAttemptSummary>;
  attempts_omitted: number;
  next_after_claim_generation: ClaimGenerationString | null;
}

export interface ProcessObservabilityHealth {
  schema_version: 1;
  required: boolean;
  initialized: boolean;
  status: "healthy" | "degraded" | "disabled" | "stale";
  service_name: string;
  service_instance_id: string;
  environment: string;
  release_revision: string;
  lifecycle_kind: "long_running" | "short_lived";
  expires_at: string;
  export_target: "local_langfuse" | "remote_langfuse" | "other_otlp" | "none";
  last_heartbeat_at: string;
  last_success_at: string | null;
  last_success_age_seconds: number | null;
  last_error_at: string | null;
  last_error_age_seconds: number | null;
  last_error_code: string | null;
  buffered_count: number;
  buffer_capacity: number;
  dropped_count: number;
  last_flush_at: string | null;
  last_flush_succeeded: boolean | null;
}

export interface ObservabilityHealthPage {
  schema_version: 1;
  status: "healthy" | "degraded";
  generated_at: string;
  stale_after_seconds: number;
  processes_omitted: number;
  processes: Array<ProcessObservabilityHealth>;
}

export interface EnvironmentOwnershipStatus {
  schema_version: 1;
  configured_environment: string;
  active_environment: string;
  mode: "active" | "passive" | "conflict";
  authority_matches: boolean;
  authority_fingerprint_prefix: string;
  epoch: Int64NonNegativeString;
  passive_reasons: Array<string>;
  dry_run: OwnershipDryRun | null;
}

export interface OwnershipDryRun {
  target_environment: string;
  allowed: boolean;
  next_epoch: Int64NonNegativeString | null;
  checks: Array<string>;
}

export type IngestionResult = IngestionResultV1 | IngestionResultV2;

export type IngestCommand = GmailIngestCommand | RssIngestCommand | BlogIngestCommand | SubstackIngestCommand | YouTubePlaylistIngestCommand | YouTubeRssIngestCommand | PodcastIngestCommand | XSearchIngestCommand | PerplexitySearchIngestCommand | FilesIngestCommand | UrlIngestCommand | ScholarSearchIngestCommand | ScholarPaperIngestCommand | ScholarReferencesIngestCommand | ArxivSearchIngestCommand | ArxivPaperIngestCommand | HuggingFacePapersIngestCommand | ReadwiseIngestCommand | ObsidianVaultIngestCommand;
