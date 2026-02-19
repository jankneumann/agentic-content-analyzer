/**
 * Connection Dashboard Component
 *
 * Read-only dashboard showing health status for all backend services.
 * Displays each service with status indicator, details, and latency.
 * Auto-refreshes every 60 seconds via the useConnectionStatus hook.
 */

import {
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  XCircle,
  MinusCircle,
  AlertTriangle,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { useConnectionStatus } from "@/hooks/use-settings"
import type { ServiceStatus } from "@/types/settings"

const STATUS_CONFIG = {
  ok: {
    icon: CheckCircle2,
    color: "text-green-500",
    label: "Connected",
  },
  unavailable: {
    icon: XCircle,
    color: "text-red-500",
    label: "Unavailable",
  },
  not_configured: {
    icon: MinusCircle,
    color: "text-muted-foreground",
    label: "Not Configured",
  },
  error: {
    icon: AlertTriangle,
    color: "text-amber-500",
    label: "Error",
  },
} as const

function StatusIcon({ status }: { status: ServiceStatus["status"] }) {
  const config = STATUS_CONFIG[status]
  const Icon = config.icon
  return <Icon className={`h-4 w-4 shrink-0 ${config.color}`} />
}

function ServiceRow({ service }: { service: ServiceStatus }) {
  const config = STATUS_CONFIG[service.status]

  return (
    <div className="flex items-center gap-3 rounded-md border bg-card px-3 py-2.5">
      <StatusIcon status={service.status} />
      <div className="flex-1 min-w-0">
        <span className="text-sm font-medium">{service.name}</span>
        <p className="text-xs text-muted-foreground truncate">
          {service.details}
        </p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {service.latency_ms != null && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="text-xs text-muted-foreground tabular-nums">
                  {Math.round(service.latency_ms)}ms
                </span>
              </TooltipTrigger>
              <TooltipContent>
                <p>Response latency</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
        <Badge
          variant={service.status === "ok" ? "secondary" : "outline"}
          className="text-[10px] px-1.5 py-0"
        >
          {config.label}
        </Badge>
      </div>
    </div>
  )
}

export function ConnectionDashboard() {
  const { data, isLoading, isError, error, refetch } = useConnectionStatus()

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-8 w-20" />
        </div>
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
      </div>
    )
  }

  // Error state
  if (isError) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border border-dashed">
        <div className="text-center">
          <AlertCircle className="mx-auto h-10 w-10 text-destructive/50" />
          <p className="mt-2 text-sm text-muted-foreground">
            Failed to check connections: {error?.message}
          </p>
          <Button
            className="mt-3"
            size="sm"
            variant="outline"
            onClick={() => refetch()}
          >
            <RefreshCw className="mr-2 h-3.5 w-3.5" />
            Retry
          </Button>
        </div>
      </div>
    )
  }

  const services = data?.services ?? []
  const allOk = data?.all_ok ?? false

  return (
    <div className="space-y-4">
      {/* Header with overall status and refresh */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {allOk ? (
            <CheckCircle2 className="h-4 w-4 text-green-500" />
          ) : (
            <AlertCircle className="h-4 w-4 text-red-500" />
          )}
          <span className="text-sm font-medium">
            {allOk ? "All Connected" : "Issues Detected"}
          </span>
        </div>
        <Button size="sm" variant="outline" onClick={() => refetch()}>
          <RefreshCw className="mr-2 h-3.5 w-3.5" />
          Refresh
        </Button>
      </div>

      {/* Service list */}
      <div className="space-y-2">
        {services.map((service) => (
          <ServiceRow key={service.name} service={service} />
        ))}
      </div>

      {/* Empty state */}
      {services.length === 0 && (
        <div className="flex h-32 items-center justify-center rounded-lg border border-dashed">
          <p className="text-sm text-muted-foreground">
            No services reported
          </p>
        </div>
      )}
    </div>
  )
}
