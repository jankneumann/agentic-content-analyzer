import type { ResourceReference } from "@/generated/workflow-contracts"

export function operationResourcePath(resource: ResourceReference): string | null {
  switch (resource.type) {
    case "content": return "/contents"
    case "summary_batch": return "/summaries"
    case "theme_analysis": return "/themes"
    case "digest": return `/review/digest/${resource.id}`
    case "podcast_script": return `/review/script/${resource.id}`
    case "podcast": return "/podcasts"
    case "audio_digest": return "/audio-digests"
    case "ingestion_run": return "/contents"
    case "pipeline_run": return "/digests"
    default: return null
  }
}
