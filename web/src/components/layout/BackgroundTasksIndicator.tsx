/**
 * Background Tasks Indicator
 *
 * A persistent indicator that shows the status of background tasks.
 * Displays in the bottom-right corner of the screen.
 */

import * as React from "react"
import {
  Loader2,
  CheckCircle,
  AlertCircle,
  X,
  ChevronUp,
  ChevronDown,
  FileText,
  Mic,
  Volume2,
  Download,
  Sparkles,
} from "lucide-react"
import { formatDistanceToNow } from "date-fns"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  useBackgroundTasks,
  taskTypeLabels,
  type TaskType,
  type BackgroundTask,
} from "@/contexts/BackgroundTasksContext"

/**
 * Task type icons
 */
const taskTypeIcons: Record<TaskType, React.ReactNode> = {
  digest: <FileText className="h-4 w-4" />,
  script: <Mic className="h-4 w-4" />,
  summary: <Sparkles className="h-4 w-4" />,
  audio: <Volume2 className="h-4 w-4" />,
  ingest: <Download className="h-4 w-4" />,
}

/**
 * Single task item component
 */
function TaskItem({
  task,
  onRemove,
}: {
  task: BackgroundTask
  onRemove: () => void
}) {
  const isActive = task.status === "running" || task.status === "pending"
  const isCompleted = task.status === "completed"
  const isFailed = task.status === "failed"

  return (
    <div className="flex items-start gap-3 p-3 rounded-lg border bg-card">
      {/* Icon */}
      <div className="flex-shrink-0 mt-0.5">
        {isActive ? (
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
        ) : isCompleted ? (
          <CheckCircle className="h-4 w-4 text-green-500" />
        ) : (
          <AlertCircle className="h-4 w-4 text-destructive" />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">
            {taskTypeIcons[task.type]}
          </span>
          <span className="font-medium text-sm truncate">{task.title}</span>
          <Badge variant="outline" className="text-xs ml-auto flex-shrink-0">
            {taskTypeLabels[task.type]}
          </Badge>
        </div>

        <p className="text-xs text-muted-foreground mt-1 truncate">
          {isFailed ? task.error : task.message}
        </p>

        {isActive && (
          <div className="mt-2">
            <Progress value={task.progress} className="h-1" />
            <div className="flex justify-between mt-1">
              <span className="text-xs text-muted-foreground">
                {task.progress}%
              </span>
              <span className="text-xs text-muted-foreground">
                {formatDistanceToNow(task.startedAt, { addSuffix: true })}
              </span>
            </div>
          </div>
        )}

        {!isActive && task.completedAt && (
          <span className="text-xs text-muted-foreground mt-1 block">
            {formatDistanceToNow(task.completedAt, { addSuffix: true })}
          </span>
        )}
      </div>

      {/* Remove button (only for completed/failed) */}
      {!isActive && (
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 flex-shrink-0"
          onClick={onRemove}
        >
          <X className="h-3 w-3" />
        </Button>
      )}
    </div>
  )
}

/**
 * Background Tasks Indicator Component
 */
export function BackgroundTasksIndicator() {
  const {
    tasks,
    activeTasks,
    completedTasks,
    removeTask,
    clearCompleted,
    hasActiveTasks,
  } = useBackgroundTasks()

  const [isExpanded, setIsExpanded] = React.useState(false)

  // Don't render if no tasks
  if (tasks.length === 0) {
    return null
  }

  // Calculate overall progress
  const overallProgress =
    activeTasks.length > 0
      ? Math.round(
          activeTasks.reduce((sum, t) => sum + t.progress, 0) / activeTasks.length
        )
      : 0

  return (
    <div className="fixed bottom-4 right-4 z-50 w-80">
      <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
        {/* Header / Trigger */}
        <CollapsibleTrigger asChild>
          <Button
            variant="outline"
            className="w-full justify-between bg-background shadow-lg border"
          >
            <div className="flex items-center gap-2">
              {hasActiveTasks ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  <span className="text-sm">
                    {activeTasks.length} task{activeTasks.length !== 1 ? "s" : ""} running
                  </span>
                  <Badge variant="secondary" className="ml-1">
                    {overallProgress}%
                  </Badge>
                </>
              ) : (
                <>
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  <span className="text-sm">
                    {completedTasks.length} task{completedTasks.length !== 1 ? "s" : ""} completed
                  </span>
                </>
              )}
            </div>
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronUp className="h-4 w-4" />
            )}
          </Button>
        </CollapsibleTrigger>

        {/* Progress bar for collapsed state */}
        {!isExpanded && hasActiveTasks && (
          <Progress value={overallProgress} className="h-1 mt-1" />
        )}

        {/* Expanded content */}
        <CollapsibleContent>
          <div className="mt-2 bg-background border rounded-lg shadow-lg max-h-80 overflow-y-auto">
            {/* Active tasks */}
            {activeTasks.length > 0 && (
              <div className="p-2 space-y-2">
                <h4 className="text-xs font-medium text-muted-foreground px-1">
                  Running
                </h4>
                {activeTasks.map((task) => (
                  <TaskItem
                    key={task.id}
                    task={task}
                    onRemove={() => removeTask(task.id)}
                  />
                ))}
              </div>
            )}

            {/* Completed tasks */}
            {completedTasks.length > 0 && (
              <div className="p-2 space-y-2 border-t">
                <div className="flex items-center justify-between px-1">
                  <h4 className="text-xs font-medium text-muted-foreground">
                    Recent
                  </h4>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 text-xs"
                    onClick={clearCompleted}
                  >
                    Clear all
                  </Button>
                </div>
                {completedTasks.slice(0, 5).map((task) => (
                  <TaskItem
                    key={task.id}
                    task={task}
                    onRemove={() => removeTask(task.id)}
                  />
                ))}
                {completedTasks.length > 5 && (
                  <p className="text-xs text-muted-foreground text-center py-1">
                    +{completedTasks.length - 5} more
                  </p>
                )}
              </div>
            )}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}
