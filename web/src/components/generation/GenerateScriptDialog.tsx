/**
 * GenerateScriptDialog Component
 *
 * Dialog for configuring and triggering podcast script generation.
 * Allows selecting:
 * - Source digest
 * - Script length (brief/standard/extended)
 * - Web search toggle
 * - Custom focus topics
 */

import * as React from "react"
import { Loader2, Mic, Search, Plus, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { DigestListItem } from "@/types"

interface GenerateScriptDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onGenerate: (params: ScriptGenerationParams) => void
  isGenerating?: boolean
  digests?: DigestListItem[]
  preselectedDigestId?: number
}

export interface ScriptGenerationParams {
  digest_id: number
  length: "brief" | "standard" | "extended"
  enable_web_search: boolean
  custom_focus_topics: string[]
}

const lengthDescriptions = {
  brief: "~5 minutes, quick overview of key points",
  standard: "~10 minutes, balanced coverage of topics",
  extended: "~15 minutes, deep dive with full context",
}

export function GenerateScriptDialog({
  open,
  onOpenChange,
  onGenerate,
  isGenerating = false,
  digests = [],
  preselectedDigestId,
}: GenerateScriptDialogProps) {
  // Form state
  const [digestId, setDigestId] = React.useState<number | null>(preselectedDigestId ?? null)
  const [length, setLength] = React.useState<"brief" | "standard" | "extended">("standard")
  const [enableWebSearch, setEnableWebSearch] = React.useState(true)
  const [focusTopics, setFocusTopics] = React.useState<string[]>([])
  const [newTopic, setNewTopic] = React.useState("")

  // Update digest ID when preselected changes
  React.useEffect(() => {
    if (preselectedDigestId) {
      setDigestId(preselectedDigestId)
    }
  }, [preselectedDigestId])

  // Filter to approved digests
  const approvedDigests = digests.filter(
    (d) => d.status === "APPROVED" || d.status === "COMPLETED"
  )

  const handleAddTopic = () => {
    if (newTopic.trim() && !focusTopics.includes(newTopic.trim())) {
      setFocusTopics([...focusTopics, newTopic.trim()])
      setNewTopic("")
    }
  }

  const handleRemoveTopic = (topic: string) => {
    setFocusTopics(focusTopics.filter((t) => t !== topic))
  }

  const handleGenerate = () => {
    if (!digestId) return

    onGenerate({
      digest_id: digestId,
      length,
      enable_web_search: enableWebSearch,
      custom_focus_topics: focusTopics,
    })
  }

  const selectedDigest = digests.find((d) => d.id === digestId)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Mic className="h-5 w-5" />
            Generate Podcast Script
          </DialogTitle>
          <DialogDescription>
            Create a conversational podcast script from a digest.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Source Digest */}
          <div className="space-y-2">
            <Label>Source Digest</Label>
            <Select
              value={digestId ? String(digestId) : ""}
              onValueChange={(v) => setDigestId(Number(v))}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select a digest..." />
              </SelectTrigger>
              <SelectContent className="max-w-[calc(500px-3rem)]">
                {approvedDigests.length === 0 ? (
                  <SelectItem value="" disabled>
                    No approved digests available
                  </SelectItem>
                ) : (
                  approvedDigests.map((digest) => (
                    <SelectItem
                      key={digest.id}
                      value={String(digest.id)}
                      className="max-w-full"
                    >
                      <span className="truncate">
                        [{digest.id}] {digest.title}
                      </span>
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
            {selectedDigest && (
              <p className="text-xs text-muted-foreground">
                {selectedDigest.digest_type} • {selectedDigest.content_count} content items
              </p>
            )}
          </div>

          {/* Script Length */}
          <div className="space-y-2">
            <Label>Script Length</Label>
            <Tabs value={length} onValueChange={(v) => setLength(v as typeof length)}>
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="brief">Brief</TabsTrigger>
                <TabsTrigger value="standard">Standard</TabsTrigger>
                <TabsTrigger value="extended">Extended</TabsTrigger>
              </TabsList>
            </Tabs>
            <p className="text-xs text-muted-foreground">{lengthDescriptions[length]}</p>
          </div>

          {/* Web Search Toggle */}
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div className="space-y-0.5">
              <Label className="flex items-center gap-2">
                <Search className="h-4 w-4" />
                Enable Web Search
              </Label>
              <p className="text-xs text-muted-foreground">
                Allow the AI to search for additional context
              </p>
            </div>
            <Switch checked={enableWebSearch} onCheckedChange={setEnableWebSearch} />
          </div>

          {/* Focus Topics */}
          <div className="space-y-2">
            <Label>Focus Topics (Optional)</Label>
            <div className="flex gap-2">
              <Input
                placeholder="Add a topic to emphasize..."
                value={newTopic}
                onChange={(e) => setNewTopic(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleAddTopic())}
              />
              <Button variant="outline" size="icon" onClick={handleAddTopic} disabled={!newTopic.trim()}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            {focusTopics.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {focusTopics.map((topic) => (
                  <Badge key={topic} variant="secondary" className="gap-1">
                    {topic}
                    <button
                      onClick={() => handleRemoveTopic(topic)}
                      className="ml-1 hover:text-destructive"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleGenerate} disabled={isGenerating || !digestId}>
            {isGenerating ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Mic className="mr-2 h-4 w-4" />
                Generate Script
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
