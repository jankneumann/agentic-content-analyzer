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

export interface OperationContextEnvelope {
  schema_version: 1; operation_id: string; root_operation_id: string; parent_operation_id: string | null;
  traceparent: string; tracestate: string | null; trace_id: string; span_id: string;
  claim_generation: string; attempt_number: string | null; entrypoint: string; service_name: string;
  service_instance_id: string; environment: string; release_revision: string; stage: OperationStage | null;
  resource_kind: string | null; resource_key: string | null;
}
export interface OperationAttemptSummary {
  claim_generation: string; attempt_number: string; trace_id: string; root_span_id: string | null;
  langfuse_observation_id: string | null; service_name: string; service_instance_id: string;
  environment: string; release_revision: string; started_at: string; completed_at: string | null;
  terminal_stage: OperationStage | null; outcome: OperationOutcome | null; retryable: boolean | null;
  telemetry_delivery_state: TelemetryDeliveryState; diagnostic_codes: string[]; diagnostics_omitted: number;
}
export interface OperationObservabilitySummary {
  root_operation_id: string; trace_id: string; attempt_count: number; latest_attempt: OperationAttemptSummary | null;
  telemetry_delivery_state: TelemetryDeliveryState; langfuse_url: string | null;
}
export interface OperationObservabilityExtension { observability?: OperationObservabilitySummary | null; [key: string]: unknown; }
export interface OperationAttemptPage {
  schema_version: 1; operation_id: string; root_operation_id: string; attempts: OperationAttemptSummary[];
  attempts_omitted: number; next_after_claim_generation: string | null;
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
  target_environment: string; allowed: boolean; next_epoch: string | null; checks: string[];
}
export interface EnvironmentOwnershipStatus {
  schema_version: 1; configured_environment: string; active_environment: string;
  mode: "active" | "passive" | "conflict"; authority_matches: boolean;
  authority_fingerprint_prefix: string; epoch: string; passive_reasons: string[];
  dry_run: OwnershipDryRun | null;
}
