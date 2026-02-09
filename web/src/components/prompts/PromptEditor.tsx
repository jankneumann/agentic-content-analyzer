/**
 * Prompt Editor Dialog
 *
 * A dialog for viewing and editing a single LLM prompt.
 * Features:
 * - Textarea for editing prompt text
 * - Diff toggle to compare current vs. default value
 * - Test button to render template with sample variables
 * - Save and Reset-to-default actions
 */

import { useState, useEffect, useMemo } from "react"
import { toast } from "sonner"
import {
  RotateCcw,
  Save,
  FlaskConical,
  Eye,
  EyeOff,
  Undo2,
} from "lucide-react"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { usePrompt, useUpdatePrompt, useResetPrompt, useTestPrompt } from "@/hooks/use-prompts"
import type { PromptInfo } from "@/types/prompt"

interface PromptEditorProps {
  /** The prompt key to edit, or null to close */
  promptKey: string | null
  /** Callback when the dialog should close */
  onClose: () => void
  /** Pre-fetched prompt info from the list (avoids extra fetch) */
  promptInfo?: PromptInfo
}

/**
 * Extract template variable names from a prompt string.
 * Matches single-brace {variable} patterns (not doubled {{escaped}}).
 */
function extractVariables(template: string): string[] {
  const regex = /(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})/g
  const vars = new Set<string>()
  let match
  while ((match = regex.exec(template)) !== null) {
    vars.add(match[1])
  }
  return Array.from(vars)
}

export function PromptEditor({ promptKey, promptInfo, onClose }: PromptEditorProps) {
  const { data: prompt } = usePrompt(promptKey ?? "", {
    enabled: !!promptKey && !promptInfo,
  })
  const updateMutation = useUpdatePrompt()
  const resetMutation = useResetPrompt()
  const testMutation = useTestPrompt()

  // Use pre-fetched info or fetched data
  const activePrompt = promptInfo ?? prompt

  // Editor state
  const [editValue, setEditValue] = useState("")
  const [showDiff, setShowDiff] = useState(false)
  const [showTest, setShowTest] = useState(false)
  const [testVariables, setTestVariables] = useState<Record<string, string>>({})

  // Reset editor state when prompt changes
  useEffect(() => {
    if (activePrompt) {
      setEditValue(activePrompt.current_value)
      setShowDiff(false)
      setShowTest(false)
      setTestVariables({})
    }
  }, [activePrompt])

  // Track whether the value has been modified
  const isDirty = activePrompt ? editValue !== activePrompt.current_value : false

  // Extract variables from the current edit value
  const variables = useMemo(() => extractVariables(editValue), [editValue])

  const handleSave = () => {
    if (!promptKey) return
    updateMutation.mutate(
      { key: promptKey, data: { value: editValue } },
      {
        onSuccess: () => {
          toast.success("Prompt updated", {
            description: `${promptKey} saved successfully`,
          })
          onClose()
        },
        onError: (err) => {
          toast.error(`Failed to save prompt: ${err.message}`)
        },
      }
    )
  }

  const handleReset = () => {
    if (!promptKey) return
    resetMutation.mutate(promptKey, {
      onSuccess: () => {
        toast.success("Prompt reset to default", {
          description: `${promptKey} restored`,
        })
        onClose()
      },
      onError: (err) => {
        toast.error(`Failed to reset prompt: ${err.message}`)
      },
    })
  }

  const handleTest = () => {
    if (!promptKey) return
    testMutation.mutate(
      {
        key: promptKey,
        data: {
          draft_value: isDirty ? editValue : undefined,
          variables: Object.keys(testVariables).length > 0 ? testVariables : undefined,
        },
      },
      {
        onError: (err) => {
          toast.error(`Test failed: ${err.message}`)
        },
      }
    )
  }

  const handleRevertEdit = () => {
    if (activePrompt) {
      setEditValue(activePrompt.current_value)
    }
  }

  return (
    <Dialog open={!!promptKey} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="w-full md:min-w-[700px] max-w-[95vw] max-h-[90vh] flex flex-col overflow-hidden">
        <DialogHeader className="shrink-0">
          <div className="flex items-center gap-2">
            <DialogTitle className="text-base">Edit Prompt</DialogTitle>
            {activePrompt?.has_override && (
              <Badge variant="default" className="text-[10px] px-1.5 py-0">
                Override
              </Badge>
            )}
            {activePrompt?.version && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                v{activePrompt.version}
              </Badge>
            )}
          </div>
          <DialogDescription className="font-mono text-xs">
            {promptKey}
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="flex-1 min-h-0 pr-4">
          <div className="space-y-4 py-2">
            {/* Prompt editor textarea */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <Label className="text-sm font-medium">Prompt Template</Label>
                <div className="flex items-center gap-1">
                  {isDirty && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleRevertEdit}
                      className="h-7 text-xs"
                    >
                      <Undo2 className="h-3 w-3 mr-1" />
                      Revert
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowDiff(!showDiff)}
                    className="h-7 text-xs"
                  >
                    {showDiff ? (
                      <EyeOff className="h-3 w-3 mr-1" />
                    ) : (
                      <Eye className="h-3 w-3 mr-1" />
                    )}
                    {showDiff ? "Hide Default" : "Show Default"}
                  </Button>
                </div>
              </div>
              <Textarea
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                className="min-h-[200px] font-mono text-sm"
                placeholder="Enter prompt template..."
              />
              {variables.length > 0 && (
                <p className="mt-1.5 text-xs text-muted-foreground">
                  Variables: {variables.map((v) => `{${v}}`).join(", ")}
                </p>
              )}
            </div>

            {/* Diff view: show default value for comparison */}
            {showDiff && activePrompt && (
              <div>
                <Label className="text-sm font-medium text-muted-foreground">
                  Default Value
                </Label>
                <div className="mt-2 rounded-md border bg-muted/50 p-3">
                  <pre className="whitespace-pre-wrap font-mono text-xs text-muted-foreground">
                    {activePrompt.default_value}
                  </pre>
                </div>
              </div>
            )}

            <Separator />

            {/* Test section */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <Label className="text-sm font-medium">Test Prompt</Label>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowTest(!showTest)}
                  className="h-7 text-xs"
                >
                  <FlaskConical className="h-3 w-3 mr-1" />
                  {showTest ? "Hide Test" : "Show Test"}
                </Button>
              </div>

              {showTest && (
                <div className="space-y-3">
                  {/* Variable inputs */}
                  {variables.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-xs text-muted-foreground">
                        Provide sample values for template variables:
                      </p>
                      <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                        {variables.map((varName) => (
                          <div key={varName} className="flex items-center gap-2">
                            <Label className="text-xs font-mono w-24 shrink-0 truncate">
                              {`{${varName}}`}
                            </Label>
                            <Input
                              value={testVariables[varName] ?? ""}
                              onChange={(e) =>
                                setTestVariables((prev) => ({
                                  ...prev,
                                  [varName]: e.target.value,
                                }))
                              }
                              placeholder={`Sample ${varName}...`}
                              className="h-8 text-xs"
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleTest}
                    disabled={testMutation.isPending}
                  >
                    <FlaskConical className="h-3.5 w-3.5 mr-1.5" />
                    {testMutation.isPending ? "Rendering..." : "Render Template"}
                  </Button>

                  {/* Test result */}
                  {testMutation.data && (
                    <div className="rounded-md border bg-muted/50 p-3">
                      <Label className="text-xs font-medium text-muted-foreground mb-1 block">
                        Rendered Output
                      </Label>
                      <pre className="whitespace-pre-wrap font-mono text-xs">
                        {testMutation.data.rendered_prompt}
                      </pre>
                      {testMutation.data.variable_names.length > 0 && (
                        <p className="mt-2 text-xs text-muted-foreground">
                          Detected variables:{" "}
                          {testMutation.data.variable_names.join(", ")}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </ScrollArea>

        <DialogFooter className="shrink-0 gap-2 sm:gap-0">
          {activePrompt?.has_override && (
            <Button
              variant="destructive"
              size="sm"
              onClick={handleReset}
              disabled={resetMutation.isPending}
              className="mr-auto"
            >
              <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
              Reset to Default
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={!isDirty || updateMutation.isPending}
          >
            <Save className="h-3.5 w-3.5 mr-1.5" />
            {updateMutation.isPending ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
