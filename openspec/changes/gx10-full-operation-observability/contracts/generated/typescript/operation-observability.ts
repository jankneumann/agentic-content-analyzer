// Generated contract stub. Regenerate from contracts/openapi/v1.yaml.

export type OperationStage =
  | "submit"
  | "queue_wait"
  | "claim"
  | "fetch"
  | "discover"
  | "metadata"
  | "transcript"
  | "extract"
  | "parse"
  | "filter"
  | "deduplicate"
  | "model"
  | "fallback"
  | "persist"
  | "index"
  | "graph"
  | "deliver"
  | "backup"
  | "restore"
  | "alert"
  | "cleanup"
  | "flush";

export type OperationOutcome =
  | "succeeded"
  | "partial"
  | "skipped_policy"
  | "skipped_duplicate"
  | "filtered"
  | "retryable_failure"
  | "permanent_failure"
  | "cancelled";

export type TelemetryDeliveryState =
  | "pending"
  | "delivered"
  | "degraded"
  | "dropped"
  | "disabled";

export interface OperationContextEnvelope {
  schema_version: 1;
  operation_id: string;
  root_operation_id: string;
  parent_operation_id: string | null;
  traceparent: string;
  tracestate: string | null;
  trace_id: string;
  span_id: string;
  claim_generation: number;
  attempt_number: number;
  entrypoint: string;
  service_name: string;
  service_instance_id: string;
  environment: string;
  release_revision: string;
  stage: OperationStage | null;
  resource_kind: string | null;
  resource_key: string | null;
}

export interface OperationAttemptSummary {
  claim_generation: number;
  attempt_number: number;
  trace_id: string;
  root_span_id: string;
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
  diagnostic_codes: string[];
  diagnostics_omitted: number;
}

export interface OperationObservabilitySummary {
  root_operation_id: string;
  trace_id: string;
  attempt_count: number;
  latest_attempt: OperationAttemptSummary | null;
  telemetry_delivery_state: TelemetryDeliveryState;
  langfuse_url: string | null;
}
