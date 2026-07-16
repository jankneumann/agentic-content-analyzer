import * as React from "react"

import type {
  OperationEvent,
  OperationHandle,
  OperationType,
} from "@/generated/workflow-contracts"
import {
  cancelOperation,
  getOperation,
  listAllOperations,
  operationEventsUrl,
  retryOperation,
} from "@/lib/api/workflows"

export type TaskType = OperationType
export type BackgroundTask = OperationHandle

const TERMINAL = new Set(["completed", "failed", "cancelled"])

export const taskTypeLabels: Record<OperationType, string> = {
  "ingestion.execute": "Ingestion",
  "summarization.run": "Summarization",
  "theme_analysis.create": "Theme analysis",
  "digest.create": "Digest",
  "pipeline.run": "Pipeline",
  "podcast_script.create": "Podcast script",
  "podcast_audio.create": "Podcast audio",
  "audio_digest.create": "Audio digest",
}

interface BackgroundTasksContextValue {
  tasks: OperationHandle[]
  activeTasks: OperationHandle[]
  completedTasks: OperationHandle[]
  addOperation: (operation: OperationHandle) => void
  removeTask: (operationId: string) => void
  clearCompleted: () => void
  retryTask: (operationId: string) => Promise<void>
  cancelTask: (operationId: string) => Promise<void>
  hasActiveTasks: boolean
}

const BackgroundTasksContext =
  React.createContext<BackgroundTasksContextValue | null>(null)

function mergeOperation(
  previous: OperationHandle[],
  operation: OperationHandle
) {
  return [
    operation,
    ...previous.filter((item) => item.operation_id !== operation.operation_id),
  ]
}

function eventToOperation(
  current: OperationHandle,
  event: OperationEvent
): OperationHandle {
  return {
    ...current,
    status: event.status,
    progress: event.progress,
    message: event.message,
    resource: event.resource,
    problem: event.problem,
    completed_at: TERMINAL.has(event.status)
      ? event.occurred_at
      : current.completed_at,
  }
}

export function BackgroundTasksProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const [tasks, setTasks] = React.useState<OperationHandle[]>([])
  const streams = React.useRef(new Map<string, EventSource>())

  const reconcile = React.useCallback(async (operationId: string) => {
    try {
      const operation = await getOperation(operationId)
      setTasks((previous) => mergeOperation(previous, operation))
      if (TERMINAL.has(operation.status)) {
        streams.current.get(operationId)?.close()
        streams.current.delete(operationId)
      }
    } catch {
      // The indicator retains the last durable snapshot during transient failures.
    }
  }, [])

  const subscribe = React.useCallback(
    (operation: OperationHandle) => {
      if (
        TERMINAL.has(operation.status) ||
        streams.current.has(operation.operation_id)
      )
        return
      const stream = new EventSource(
        operationEventsUrl(operation.operation_id),
        { withCredentials: true }
      )
      stream.addEventListener("progress", (message) => {
        let event: OperationEvent
        try {
          event = JSON.parse(
            (message as MessageEvent<string>).data
          ) as OperationEvent
        } catch {
          void reconcile(operation.operation_id)
          return
        }
        setTasks((previous) =>
          previous.map((item) =>
            item.operation_id === event.operation_id
              ? eventToOperation(item, event)
              : item
          )
        )
        if (TERMINAL.has(event.status)) {
          stream.close()
          streams.current.delete(event.operation_id)
        }
      })
      stream.onerror = () => {
        void reconcile(operation.operation_id)
      }
      streams.current.set(operation.operation_id, stream)
    },
    [reconcile]
  )

  const addOperation = React.useCallback(
    (operation: OperationHandle) => {
      setTasks((previous) => mergeOperation(previous, operation))
      subscribe(operation)
    },
    [subscribe]
  )

  React.useEffect(() => {
    let cancelled = false
    const activeStreams = streams.current
    void listAllOperations()
      .then((operations) => {
        if (cancelled) return
        setTasks(operations)
        operations.forEach(subscribe)
      })
      .catch(() => {})
    return () => {
      cancelled = true
      activeStreams.forEach((stream) => stream.close())
      activeStreams.clear()
    }
  }, [subscribe])

  const activeTasks = React.useMemo(
    () => tasks.filter((task) => !TERMINAL.has(task.status)),
    [tasks]
  )
  const completedTasks = React.useMemo(
    () => tasks.filter((task) => TERMINAL.has(task.status)),
    [tasks]
  )
  const retryTask = React.useCallback(
    async (operationId: string) =>
      addOperation(await retryOperation(operationId)),
    [addOperation]
  )
  const cancelTask = React.useCallback(
    async (operationId: string) =>
      addOperation(await cancelOperation(operationId)),
    [addOperation]
  )

  const value: BackgroundTasksContextValue = {
    tasks,
    activeTasks,
    completedTasks,
    addOperation,
    removeTask: (operationId) => {
      streams.current.get(operationId)?.close()
      streams.current.delete(operationId)
      setTasks((previous) =>
        previous.filter((task) => task.operation_id !== operationId)
      )
    },
    clearCompleted: () =>
      setTasks((previous) =>
        previous.filter((task) => !TERMINAL.has(task.status))
      ),
    retryTask,
    cancelTask,
    hasActiveTasks: activeTasks.length > 0,
  }
  return (
    <BackgroundTasksContext.Provider value={value}>
      {children}
    </BackgroundTasksContext.Provider>
  )
}

export function useBackgroundTasks() {
  const context = React.useContext(BackgroundTasksContext)
  if (!context)
    throw new Error(
      "useBackgroundTasks must be used within BackgroundTasksProvider"
    )
  return context
}
