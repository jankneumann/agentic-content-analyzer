/**
 * Background Tasks Context
 *
 * Provides global state management for tracking background tasks
 * like digest generation, script creation, summarization, and audio generation.
 *
 * Tasks are tracked with progress updates and can be displayed in a
 * persistent indicator across the application.
 */

import * as React from "react"

/**
 * Task types for background operations
 */
export type TaskType = "digest" | "script" | "summary" | "audio" | "audio-digest" | "ingest" | "themes"

/**
 * Task status
 */
export type TaskStatus = "pending" | "running" | "completed" | "failed"

/**
 * Background task interface
 */
export interface BackgroundTask {
  id: string
  type: TaskType
  status: TaskStatus
  title: string
  message: string
  progress: number
  startedAt: Date
  completedAt?: Date
  error?: string
}

/**
 * Context value interface
 */
interface BackgroundTasksContextValue {
  /** All tracked tasks */
  tasks: BackgroundTask[]
  /** Active (running) tasks */
  activeTasks: BackgroundTask[]
  /** Completed tasks (for recent history) */
  completedTasks: BackgroundTask[]
  /** Add a new task */
  addTask: (task: Omit<BackgroundTask, "id" | "startedAt" | "status" | "progress">) => string
  /** Update task progress */
  updateTask: (id: string, updates: Partial<BackgroundTask>) => void
  /** Mark task as completed */
  completeTask: (id: string, message?: string) => void
  /** Mark task as failed */
  failTask: (id: string, error: string) => void
  /** Remove a task from tracking */
  removeTask: (id: string) => void
  /** Clear all completed tasks */
  clearCompleted: () => void
  /** Check if any tasks are running */
  hasActiveTasks: boolean
}

const BackgroundTasksContext = React.createContext<BackgroundTasksContextValue | null>(null)

/**
 * Generate unique task ID
 */
function generateTaskId(): string {
  return `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

/**
 * Task type display names
 */
export const taskTypeLabels: Record<TaskType, string> = {
  digest: "Digest",
  script: "Script",
  summary: "Summary",
  audio: "Audio",
  "audio-digest": "Audio Digest",
  ingest: "Ingest",
  themes: "Themes",
}

/**
 * Background Tasks Provider
 */
export function BackgroundTasksProvider({ children }: { children: React.ReactNode }) {
  const [tasks, setTasks] = React.useState<BackgroundTask[]>([])

  // Derived state
  const activeTasks = React.useMemo(
    () => tasks.filter((t) => t.status === "running" || t.status === "pending"),
    [tasks]
  )

  const completedTasks = React.useMemo(
    () => tasks.filter((t) => t.status === "completed" || t.status === "failed"),
    [tasks]
  )

  const hasActiveTasks = activeTasks.length > 0

  // Add a new task
  const addTask = React.useCallback(
    (task: Omit<BackgroundTask, "id" | "startedAt" | "status" | "progress">): string => {
      const id = generateTaskId()
      const newTask: BackgroundTask = {
        ...task,
        id,
        status: "running",
        progress: 0,
        startedAt: new Date(),
      }
      setTasks((prev) => [newTask, ...prev])
      return id
    },
    []
  )

  // Update task
  const updateTask = React.useCallback((id: string, updates: Partial<BackgroundTask>) => {
    setTasks((prev) =>
      prev.map((task) =>
        task.id === id ? { ...task, ...updates } : task
      )
    )
  }, [])

  // Complete task
  const completeTask = React.useCallback((id: string, message?: string) => {
    setTasks((prev) =>
      prev.map((task) =>
        task.id === id
          ? {
              ...task,
              status: "completed" as const,
              progress: 100,
              completedAt: new Date(),
              message: message ?? task.message,
            }
          : task
      )
    )
  }, [])

  // Fail task
  const failTask = React.useCallback((id: string, error: string) => {
    setTasks((prev) =>
      prev.map((task) =>
        task.id === id
          ? {
              ...task,
              status: "failed" as const,
              completedAt: new Date(),
              error,
            }
          : task
      )
    )
  }, [])

  // Remove task
  const removeTask = React.useCallback((id: string) => {
    setTasks((prev) => prev.filter((task) => task.id !== id))
  }, [])

  // Clear completed
  const clearCompleted = React.useCallback(() => {
    setTasks((prev) => prev.filter((task) => task.status === "running" || task.status === "pending"))
  }, [])

  // Auto-remove old completed tasks (after 5 minutes)
  React.useEffect(() => {
    const interval = setInterval(() => {
      const fiveMinutesAgo = Date.now() - 5 * 60 * 1000
      setTasks((prev) =>
        prev.filter(
          (task) =>
            task.status === "running" ||
            task.status === "pending" ||
            !task.completedAt ||
            task.completedAt.getTime() > fiveMinutesAgo
        )
      )
    }, 60000) // Check every minute

    return () => clearInterval(interval)
  }, [])

  const value: BackgroundTasksContextValue = {
    tasks,
    activeTasks,
    completedTasks,
    addTask,
    updateTask,
    completeTask,
    failTask,
    removeTask,
    clearCompleted,
    hasActiveTasks,
  }

  return (
    <BackgroundTasksContext.Provider value={value}>
      {children}
    </BackgroundTasksContext.Provider>
  )
}

/**
 * Hook to access background tasks context
 */
export function useBackgroundTasks() {
  const context = React.useContext(BackgroundTasksContext)
  if (!context) {
    throw new Error("useBackgroundTasks must be used within BackgroundTasksProvider")
  }
  return context
}
