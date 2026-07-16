import type {
  AudioDigestRequest,
  CapabilityDocument,
  DigestCreateRequest,
  IngestCommand,
  OperationHandle,
  OperationPage,
  PipelineRequest,
  PodcastAudioRequest,
  PodcastScriptRequest,
  SummarizationRequest,
  ThemeAnalysisRequest,
  UploadReference,
} from "@/generated/workflow-contracts"

import { API_BASE_URL, apiClient } from "./client"

type SubmissionOptions = { idempotencyKey?: string }

function submissionOptions(options?: SubmissionOptions) {
  return options?.idempotencyKey
    ? { headers: { "Idempotency-Key": options.idempotencyKey } }
    : undefined
}

export async function getAllCapabilities(): Promise<CapabilityDocument> {
  let cursor: string | null | undefined
  let result: CapabilityDocument | undefined
  do {
    const page = await apiClient.get<CapabilityDocument>("/capabilities", { params: { cursor, limit: 100 } })
    result = result
      ? { ...result, source_commands: [...result.source_commands, ...page.source_commands], next_cursor: page.next_cursor }
      : page
    cursor = page.next_cursor
  } while (cursor)
  if (!result) throw new Error("Capability discovery returned no document")
  return result
}

export function uploadFile(file: File, metadata?: { title?: string; publication?: string }) {
  const body = new FormData()
  body.append("file", file)
  if (metadata?.title) body.append("title", metadata.title)
  if (metadata?.publication) body.append("publication", metadata.publication)
  return apiClient.post<UploadReference>("/uploads", body, { headers: { Accept: "application/json" } })
}

export const submitIngestion = (request: IngestCommand, options?: SubmissionOptions) =>
  apiClient.post<OperationHandle>("/ingestions", request, submissionOptions(options))
export const submitSummarization = (request: SummarizationRequest, options?: SubmissionOptions) =>
  apiClient.post<OperationHandle>("/summarization-runs", request, submissionOptions(options))
export const submitThemeAnalysis = (request: ThemeAnalysisRequest, options?: SubmissionOptions) =>
  apiClient.post<OperationHandle>("/theme-analyses", request, submissionOptions(options))
export const submitDigest = (request: DigestCreateRequest, options?: SubmissionOptions) =>
  apiClient.post<OperationHandle>("/digests", request, submissionOptions(options))
export const submitPipeline = (request: PipelineRequest, options?: SubmissionOptions) =>
  apiClient.post<OperationHandle>("/pipeline-runs", request, submissionOptions(options))
export const submitPodcastScript = (request: PodcastScriptRequest, options?: SubmissionOptions) =>
  apiClient.post<OperationHandle>("/podcast-scripts", request, submissionOptions(options))
export const submitPodcastAudio = (request: PodcastAudioRequest, options?: SubmissionOptions) =>
  apiClient.post<OperationHandle>("/podcasts", request, submissionOptions(options))
export const submitAudioDigest = (request: AudioDigestRequest, options?: SubmissionOptions) =>
  apiClient.post<OperationHandle>("/audio-digests", request, submissionOptions(options))

export const getOperation = (operationId: string, waitSeconds = 0) =>
  apiClient.get<OperationHandle>(`/operations/${operationId}`, { params: { wait_seconds: waitSeconds } })
export const listOperations = (cursor?: string, limit = 100) =>
  apiClient.get<OperationPage>("/operations", { params: { cursor, limit } })
export const retryOperation = (operationId: string) =>
  apiClient.post<OperationHandle>(`/operations/${operationId}/retry`)
export const cancelOperation = (operationId: string) =>
  apiClient.post<OperationHandle>(`/operations/${operationId}/cancel`)

export function operationEventsUrl(operationId: string) {
  return `${API_BASE_URL}/operations/${operationId}/events`
}
