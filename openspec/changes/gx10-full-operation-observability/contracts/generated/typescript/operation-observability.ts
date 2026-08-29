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

type Brand<Value, Name extends string> = Value & { readonly __brand: Name };
export type OperationIdString = Brand<string, "OperationIdString">;
export type PositiveInt64String = Brand<string, "PositiveInt64String">;
export type ClaimGenerationString = Brand<string, "ClaimGenerationString">;
export type NonNegativeInt64String = Brand<string, "NonNegativeInt64String">;
export type TraceIdString = Brand<string, "TraceIdString">;
export type SpanIdString = Brand<string, "SpanIdString">;

export const SIGNED_BIGINT_MAX = 9223372036854775807n;
export const CLAIM_GENERATION_MAX = 9223372036854775806n;
const CANONICAL_DECIMAL = /^(0|[1-9][0-9]*)$/;
const TRACE_ID = /^[0-9a-f]{32}$/;
const SPAN_ID = /^[0-9a-f]{16}$/;
const AUTHORITY_FINGERPRINT = /^[0-9a-f]{64}$/;
const TRACEPARENT = /^00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}$/;
const codePointLength = (value: string): number => Array.from(value).length;

function isBoundedDecimal(value: string, minimum: bigint, maximum: bigint): boolean {
  return value.length <= 19 && CANONICAL_DECIMAL.test(value)
    && BigInt(value) >= minimum && BigInt(value) <= maximum;
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

const CONTEXT_KEYS = new Set([
  "schema_version", "operation_id", "root_operation_id", "parent_operation_id",
  "traceparent", "tracestate", "trace_id", "span_id", "claim_generation",
  "attempt_number", "entrypoint", "service_name", "service_instance_id",
  "environment", "release_revision", "authority_fingerprint", "ownership_epoch",
  "stage", "resource_kind", "resource_key",
]);
const OPERATION_STAGES = new Set<string>([
  "submit", "queue_wait", "claim", "fetch", "discover", "metadata", "transcript",
  "extract", "parse", "filter", "deduplicate", "model", "fallback", "persist",
  "index", "graph", "deliver", "backup", "restore", "alert", "cleanup", "flush",
]);
const TRACESTATE_KEY = /^[a-z0-9][a-z0-9_*/-]{0,255}$/;

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

/** Mandatory semantic ingress validator; structural OpenAPI/JSON Schema validation alone is insufficient. */
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
  if (typeof context.operation_id !== "string" || !isOperationIdString(context.operation_id)) throw new TypeError("invalid operation_id");
  if (typeof context.root_operation_id !== "string" || !isOperationIdString(context.root_operation_id)) throw new TypeError("invalid root_operation_id");
  if (context.parent_operation_id !== null && (typeof context.parent_operation_id !== "string" || !isOperationIdString(context.parent_operation_id))) throw new TypeError("invalid parent_operation_id");
  if (typeof context.trace_id !== "string" || !isTraceIdString(context.trace_id)) throw new TypeError("invalid trace_id");
  if (typeof context.span_id !== "string" || !isSpanIdString(context.span_id)) throw new TypeError("invalid span_id");
  if (typeof context.traceparent !== "string" || !hasCanonicalMatchingTraceparent(context.traceparent, context.trace_id, context.span_id)) throw new TypeError("invalid or mismatched traceparent");
  if (context.tracestate !== null && (typeof context.tracestate !== "string" || !isValidTracestate(context.tracestate))) throw new TypeError("invalid tracestate");
  if (typeof context.claim_generation !== "string" || !isClaimGenerationString(context.claim_generation)) throw new TypeError("invalid claim_generation");
  if (context.attempt_number !== null) {
    if (typeof context.attempt_number !== "string" || !isPositiveInt64String(context.attempt_number)
      || BigInt(context.attempt_number) !== BigInt(context.claim_generation) + 1n) throw new TypeError("invalid attempt_number");
  }
  boundedString("entrypoint", 1, 160);
  boundedString("service_name", 1, 100);
  boundedString("service_instance_id", 1, 128);
  boundedString("environment", 1, 32);
  boundedString("release_revision", 1, 64);
  if (context.authority_fingerprint !== null && (typeof context.authority_fingerprint !== "string" || !AUTHORITY_FINGERPRINT.test(context.authority_fingerprint))) throw new TypeError("invalid authority_fingerprint");
  if (context.ownership_epoch !== null && (typeof context.ownership_epoch !== "string" || !isNonNegativeInt64String(context.ownership_epoch))) throw new TypeError("invalid ownership_epoch");
  if (context.stage !== null && (typeof context.stage !== "string" || !OPERATION_STAGES.has(context.stage))) throw new TypeError("invalid stage");
  if (context.resource_kind !== null && (typeof context.resource_kind !== "string" || codePointLength(context.resource_kind) > 64)) throw new TypeError("invalid resource_kind");
  if (context.resource_key !== null && (typeof context.resource_key !== "string" || codePointLength(context.resource_key) > 128)) throw new TypeError("invalid resource_key");
  return context as unknown as OperationContextEnvelope;
}

export interface OperationContextEnvelope {
  schema_version: 1; operation_id: OperationIdString; root_operation_id: OperationIdString; parent_operation_id: OperationIdString | null;
  traceparent: string; tracestate: string | null; trace_id: TraceIdString; span_id: SpanIdString;
  claim_generation: ClaimGenerationString; attempt_number: PositiveInt64String | null; entrypoint: string; service_name: string;
  service_instance_id: string; environment: string; release_revision: string; authority_fingerprint: string | null;
  ownership_epoch: NonNegativeInt64String | null; stage: OperationStage | null;
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
