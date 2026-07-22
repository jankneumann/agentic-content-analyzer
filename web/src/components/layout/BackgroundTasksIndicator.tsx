import * as React from "react"
import {
  AlertCircle,
  Ban,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Loader2,
  RefreshCw,
  RotateCcw,
  X,
} from "lucide-react"
import { useNavigate } from "@tanstack/react-router"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Progress } from "@/components/ui/progress"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  taskTypeLabels,
  useBackgroundTasks,
  type BackgroundTask,
} from "@/contexts/BackgroundTasksContext"
import { operationResourcePath } from "@/lib/operation-navigation"

function StatusIcon({ task }: { task: BackgroundTask }) {
  if (task.status === "queued" || task.status === "in_progress")
    return <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
  if (task.status === "completed")
    return <CheckCircle2 className="h-4 w-4" aria-hidden />
  if (task.status === "cancelled")
    return <Ban className="h-4 w-4" aria-hidden />
  return <AlertCircle className="h-4 w-4" aria-hidden />
}

function OperationItem({ task }: { task: BackgroundTask }) {
  const navigate = useNavigate()
  const { cancelTask, retryTask, removeTask } = useBackgroundTasks()
  const active = task.status === "queued" || task.status === "in_progress"
  const target = task.resource ? operationResourcePath(task.resource) : null
  return (
    <div className="border-b p-3 last:border-b-0" aria-live="polite">
      <div className="flex items-start gap-2">
        <span className="mt-0.5" aria-label={task.status}>
          <StatusIcon task={task} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium">
              {taskTypeLabels[task.operation_type]}
            </span>
            <Badge variant="outline" className="text-xs">
              {(task.status ?? "unknown").replace("_", " ")}
            </Badge>
          </div>
          <p className="text-muted-foreground mt-1 text-xs break-words">
            {task.problem?.detail ?? task.message}
          </p>
          {active && (
            <Progress
              value={task.progress}
              className="mt-2 h-1.5"
              aria-label={`${task.progress}% complete`}
            />
          )}
        </div>
        <div className="flex shrink-0 gap-1">
          {active && task.cancellable && (
            <Button
              size="icon"
              variant="ghost"
              aria-label="Cancel operation"
              onClick={() => void cancelTask(task.operation_id)}
            >
              <X className="h-4 w-4" />
            </Button>
          )}
          {(task.status === "failed" || task.status === "cancelled") && (
            <Button
              size="icon"
              variant="ghost"
              aria-label="Retry operation"
              onClick={() => void retryTask(task.operation_id)}
            >
              <RotateCcw className="h-4 w-4" />
            </Button>
          )}
          {target && (
            <Button
              size="icon"
              variant="ghost"
              aria-label="Open result"
              onClick={() => void navigate({ to: target })}
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          )}
          {!active && (
            <Button
              size="icon"
              variant="ghost"
              aria-label="Dismiss operation"
              onClick={() => removeTask(task.operation_id)}
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

export function BackgroundTasksIndicator() {
  const { tasks, activeTasks, completedTasks, clearCompleted, hasActiveTasks } =
    useBackgroundTasks()
  const [expanded, setExpanded] = React.useState(false)
  if (!tasks.length) return null
  const progress = activeTasks.length
    ? Math.round(
        activeTasks.reduce((sum, task) => sum + task.progress, 0) /
          activeTasks.length
      )
    : 100
  return (
    <TooltipProvider>
      <div className="fixed inset-x-3 bottom-[max(0.75rem,var(--safe-area-bottom))] z-50 sm:right-4 sm:left-auto sm:w-96">
        <Collapsible
          open={expanded}
          onOpenChange={setExpanded}
          className="bg-background overflow-hidden rounded-md border shadow-lg"
        >
          <CollapsibleTrigger asChild>
            <Button
              variant="ghost"
              className="h-11 w-full justify-between rounded-none px-3"
              aria-label="Toggle operations"
            >
              <span className="flex min-w-0 items-center gap-2 text-sm">
                {hasActiveTasks ? (
                  <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
                ) : (
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                )}
                <span className="truncate">
                  {hasActiveTasks
                    ? `${activeTasks.length} operation${activeTasks.length === 1 ? "" : "s"} running`
                    : `${completedTasks.length} recent operation${completedTasks.length === 1 ? "" : "s"}`}
                </span>
                {hasActiveTasks && (
                  <Badge variant="secondary">{progress}%</Badge>
                )}
              </span>
              {expanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronUp className="h-4 w-4" />
              )}
            </Button>
          </CollapsibleTrigger>
          {!expanded && hasActiveTasks && (
            <Progress value={progress} className="h-1 rounded-none" />
          )}
          <CollapsibleContent>
            <div className="max-h-[min(60vh,28rem)] overflow-y-auto border-t">
              {tasks.slice(0, 20).map((task) => (
                <OperationItem key={task.operation_id} task={task} />
              ))}
            </div>
            {completedTasks.length > 0 && (
              <div className="flex justify-end border-t p-2">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button size="sm" variant="ghost" onClick={clearCompleted}>
                      Clear completed
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    Remove terminal operations from this view
                  </TooltipContent>
                </Tooltip>
              </div>
            )}
          </CollapsibleContent>
        </Collapsible>
      </div>
    </TooltipProvider>
  )
}
