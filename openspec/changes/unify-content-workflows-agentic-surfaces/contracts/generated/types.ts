// Generated-contract stub for contracts/openapi/v1.yaml.
// Implementation SHALL replace this file with generated output.

export type OperationStatus =
  | "queued"
  | "in_progress"
  | "completed"
  | "failed"
  | "cancelled";

export type OperationType =
  | "ingestion.execute"
  | "summarization.run"
  | "theme_analysis.create"
  | "digest.create"
  | "pipeline.run"
  | "podcast_script.create"
  | "podcast_audio.create"
  | "audio_digest.create";

export interface ProblemField {
  path: Array<string | number>;
  code: string;
  message: string;
}

export interface Problem {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance?: string | null;
  code?: string | null;
  errors?: ProblemField[];
}

export interface ResourceReference {
  type: string;
  id: string;
  url: string;
}

export interface OperationHandle {
  schema_version: 2;
  operation_id: string;
  operation_type: OperationType;
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

export interface ContentQuery {
  source_types?: string[];
  statuses?: string[];
  publications?: string[];
  publication_search?: string;
  start_date?: string;
  end_date?: string;
  date_basis?: "published_date" | "ingested_at";
  search?: string;
  limit?: number;
  sort_by?: string;
  sort_order?: "asc" | "desc";
  canonical_only?: boolean;
  require_summary?: boolean;
}

interface ConfiguredSourceCommand {
  max_items?: number;
  days_back?: number;
  force_reprocess?: boolean;
}

export type IngestCommand =
  | (ConfiguredSourceCommand & { kind: "gmail"; query?: string })
  | (ConfiguredSourceCommand & { kind: "rss" })
  | (ConfiguredSourceCommand & { kind: "blog" })
  | (ConfiguredSourceCommand & { kind: "substack" })
  | (ConfiguredSourceCommand & { kind: "youtube_playlist"; public_only?: boolean })
  | (ConfiguredSourceCommand & { kind: "youtube_rss" })
  | (ConfiguredSourceCommand & { kind: "podcast"; transcribe?: boolean })
  | { kind: "x_search"; prompt?: string; max_threads?: number; force_reprocess?: boolean }
  | {
      kind: "perplexity_search";
      prompt?: string;
      max_items?: number;
      recency?: "hour" | "day" | "week" | "month";
      context_size?: "low" | "medium" | "high";
      force_reprocess?: boolean;
    }
  | { kind: "files"; upload_ids: string[]; force_reprocess?: boolean }
  | { kind: "url"; url: string; title?: string; tags?: string[]; notes?: string; force_reprocess?: boolean }
  | { kind: "scholar_search"; max_items?: number }
  | { kind: "scholar_paper"; identifier: string; with_references?: boolean }
  | {
      kind: "scholar_references";
      after?: string;
      before?: string;
      source_types?: string[];
      dry_run?: boolean;
      limit?: number;
    }
  | (ConfiguredSourceCommand & { kind: "arxiv_search"; extract_pdf?: boolean })
  | { kind: "arxiv_paper"; identifier: string; extract_pdf?: boolean; force_reprocess?: boolean }
  | (ConfiguredSourceCommand & { kind: "huggingface_papers" })
  | {
      kind: "readwise";
      updated_after?: string;
      source_types?: string[];
      include_deleted?: boolean;
      max_books?: number;
      force_reprocess?: boolean;
    };

export interface CapabilityField {
  name: string;
  type: string;
  required: boolean;
  description?: string | null;
  enum?: string[];
  default?: unknown;
}

export interface SourceCapability {
  key: string;
  display_name: string;
  emitted_source: string;
  scheduled: boolean;
  transports: Array<"cli" | "http" | "mcp" | "frontend">;
  fields: CapabilityField[];
}

export interface CapabilityDocument {
  contract_version: string;
  source_commands: SourceCapability[];
  operation_types: OperationType[];
  resource_types: string[];
}
