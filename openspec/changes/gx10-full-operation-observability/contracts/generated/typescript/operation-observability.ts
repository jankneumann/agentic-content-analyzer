// Generated review stub. Regenerate from the durable canonical OpenAPI contract.

export type OperationStage =
  | "submit" | "queue_wait" | "claim" | "fetch" | "discover"
  | "metadata" | "transcript" | "extract" | "parse" | "filter"
  | "deduplicate" | "model" | "fallback" | "persist" | "index"
  | "graph" | "deliver" | "backup" | "restore" | "alert"
  | "cleanup" | "flush";
export type OperationOutcome =
  | "succeeded" | "partial" | "skipped_policy" | "skipped_duplicate"
  | "filtered" | "retryable_failure" | "permanent_failure" | "cancelled";
export type TelemetryDeliveryState = "pending" | "delivered" | "degraded" | "dropped" | "disabled";

export type OperationIdString = string;
export type PositiveInt64String = string;
export type ClaimGenerationString = string;
export type NonNegativeInt64String = string;
export type TraceIdString = string;
export type SpanIdString = string;

export const SIGNED_BIGINT_MAX = 9223372036854775807n;
export const CLAIM_GENERATION_MAX = 9223372036854775806n;
const CANONICAL_DECIMAL = /^(0|[1-9][0-9]*)$/;
const TRACE_ID = /^[0-9a-f]{32}$/;
const SPAN_ID = /^[0-9a-f]{16}$/;
const TRACEPARENT = /^00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}$/;

function isBoundedDecimal(value: string, minimum: bigint, maximum: bigint): boolean {
  return CANONICAL_DECIMAL.test(value) && BigInt(value) >= minimum && BigInt(value) <= maximum;
}

export function isOperationIdString(value: string): value is OperationIdString {
  return isBoundedDecimal(value, 1n, SIGNED_BIGINT_MAX);
}

export function isPositiveInt64String(value: string): value is PositiveInt64String {
  return isOperationIdString(value);
}

export function isClaimGenerationString(value: string): value is ClaimGenerationString {
  return isBoundedDecimal(value, 0n, CLAIM_GENERATION_MAX);
}

export function isNonNegativeInt64String(value: string): value is NonNegativeInt64String {
  return isBoundedDecimal(value, 0n, SIGNED_BIGINT_MAX);
}

export function isTraceIdString(value: string): value is TraceIdString {
  return TRACE_ID.test(value) && value !== "0".repeat(32);
}

export function isSpanIdString(value: string): value is SpanIdString {
  return SPAN_ID.test(value) && value !== "0".repeat(16);
}

export function hasCanonicalMatchingTraceparent(
  traceparent: string,
  traceId: TraceIdString,
  spanId: SpanIdString,
): boolean {
  const match = TRACEPARENT.exec(traceparent);
  return match !== null && match[1] === traceId && match[2] === spanId;
}

export interface OperationContextEnvelope {
  schema_version: 1; operation_id: OperationIdString; root_operation_id: OperationIdString; parent_operation_id: OperationIdString | null;
  traceparent: string; tracestate: string | null; trace_id: TraceIdString; span_id: SpanIdString;
  claim_generation: ClaimGenerationString; attempt_number: PositiveInt64String | null; entrypoint: string; service_name: string;
  service_instance_id: string; environment: string; release_revision: string; stage: OperationStage | null;
  resource_kind: string | null; resource_key: string | null;
}
export interface OperationAttemptSummary {
  claim_generation: ClaimGenerationString; attempt_number: PositiveInt64String; trace_id: TraceIdString; root_span_id: SpanIdString | null;
  langfuse_observation_id: string | null; service_name: string; service_instance_id: string;
  environment: string; release_revision: string; started_at: string; completed_at: string | null;
  terminal_stage: OperationStage | null; outcome: OperationOutcome | null; retryable: boolean | null;
  telemetry_delivery_state: TelemetryDeliveryState; diagnostic_codes: string[]; diagnostics_omitted: number;
}
export interface OperationObservabilitySummary {
  root_operation_id: OperationIdString; trace_id: TraceIdString; attempt_count: number; latest_attempt: OperationAttemptSummary | null;
  telemetry_delivery_state: TelemetryDeliveryState; langfuse_url: string | null;
}
export interface OperationObservabilityExtension { observability?: OperationObservabilitySummary | null; [key: string]: unknown; }
export interface OperationAttemptPage {
  schema_version: 1; operation_id: OperationIdString; root_operation_id: OperationIdString; attempts: OperationAttemptSummary[];
  attempts_omitted: number; next_after_claim_generation: ClaimGenerationString | null;
}
export interface ProcessObservabilityHealth {
  schema_version: 1; required: boolean; initialized: boolean; status: "healthy" | "degraded" | "disabled" | "stale";
  service_name: string; service_instance_id: string; environment: string; release_revision: string;
  lifecycle_kind: "long_running" | "short_lived"; expires_at: string;
  export_target: "local_langfuse" | "remote_langfuse" | "other_otlp" | "none";
  last_heartbeat_at: string; last_success_at: string | null; last_success_age_seconds: number | null;
  last_error_at: string | null; last_error_age_seconds: number | null; last_error_code: string | null;
  buffered_count: number; buffer_capacity: number; dropped_count: number; last_flush_at: string | null;
  last_flush_succeeded: boolean | null;
}
export interface ObservabilityHealthPage {
  schema_version: 1; status: "healthy" | "degraded"; generated_at: string; stale_after_seconds: number;
  processes: ProcessObservabilityHealth[]; processes_omitted: number;
}
export interface Problem { title: string; status: number; code?: string | null; [key: string]: unknown; }

export interface OwnershipDryRun {
  target_environment: string; allowed: boolean; next_epoch: NonNegativeInt64String | null; checks: string[];
}
export interface EnvironmentOwnershipStatus {
  schema_version: 1; configured_environment: string; active_environment: string;
  mode: "active" | "passive" | "conflict"; authority_matches: boolean;
  authority_fingerprint_prefix: string; epoch: NonNegativeInt64String; passive_reasons: string[];
  dry_run: OwnershipDryRun | null;
}
