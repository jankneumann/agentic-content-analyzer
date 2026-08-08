import type { ReactNode } from "react"
import {
  BookOpen,
  FileText,
  Globe,
  GraduationCap,
  Mail,
  Mic,
  Rss,
  Search,
  Upload,
  Youtube,
} from "lucide-react"

import type { ContentSource } from "@/types"

const SOURCE_DISPLAY: Record<
  ContentSource,
  { label: string; icon: ReactNode }
> = {
  gmail: { label: "Gmail", icon: <Mail className="h-3 w-3" /> },
  rss: { label: "RSS", icon: <Rss className="h-3 w-3" /> },
  youtube: { label: "YouTube", icon: <Youtube className="h-3 w-3" /> },
  podcast: { label: "Podcast", icon: <Mic className="h-3 w-3" /> },
  substack: { label: "Substack", icon: <BookOpen className="h-3 w-3" /> },
  file_upload: { label: "Upload", icon: <Upload className="h-3 w-3" /> },
  manual: { label: "Manual", icon: <FileText className="h-3 w-3" /> },
  webpage: { label: "Webpage", icon: <Globe className="h-3 w-3" /> },
  xsearch: { label: "X Search", icon: <Search className="h-3 w-3" /> },
  perplexity: { label: "Perplexity", icon: <Globe className="h-3 w-3" /> },
  blog: { label: "Blog", icon: <BookOpen className="h-3 w-3" /> },
  scholar: { label: "Scholar", icon: <GraduationCap className="h-3 w-3" /> },
  arxiv: { label: "arXiv", icon: <FileText className="h-3 w-3" /> },
  huggingface_papers: { label: "HF Papers", icon: <FileText className="h-3 w-3" /> },
  readwise: { label: "Readwise", icon: <BookOpen className="h-3 w-3" /> },
  obsidian: { label: "Obsidian", icon: <FileText className="h-3 w-3" /> },
  other: { label: "Other", icon: <FileText className="h-3 w-3" /> },
}

export function getContentSourceDisplay(source: ContentSource) {
  return SOURCE_DISPLAY[source]
}
