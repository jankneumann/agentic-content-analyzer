/**
 * NotificationBell Component
 *
 * Bell icon with unread badge that opens a dropdown of recent notifications.
 * Subscribes to SSE for real-time badge updates.
 */

import { useState } from "react"
import {
  Bell,
  CheckCheck,
  FileText,
  Mic,
  BarChart3,
  Zap,
  XCircle,
} from "lucide-react"
import { useNavigate } from "@tanstack/react-router"
import { formatDistanceToNow } from "date-fns"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  useUnreadCount,
  useNotificationEvents,
  useMarkEventRead,
  useMarkAllRead,
  useNotificationSSE,
} from "@/hooks/use-notifications"
import {
  useLocalNotificationBridge,
  useNotificationTapHandler,
} from "@/hooks/use-push-notifications"
import type { NotificationEvent, NotificationEventType } from "@/types"

/** Icon mapping for event types */
const EVENT_ICONS: Record<NotificationEventType, typeof Bell> = {
  batch_summary: BarChart3,
  theme_analysis: BarChart3,
  digest_creation: FileText,
  script_generation: Mic,
  audio_generation: Mic,
  pipeline_completion: Zap,
  job_failure: XCircle,
}

/** Color mapping for event types */
const EVENT_COLORS: Record<NotificationEventType, string> = {
  batch_summary: "text-blue-500",
  theme_analysis: "text-purple-500",
  digest_creation: "text-green-500",
  script_generation: "text-orange-500",
  audio_generation: "text-orange-500",
  pipeline_completion: "text-emerald-500",
  job_failure: "text-red-500",
}

function NotificationItem({
  event,
  onRead,
  onNavigate,
}: {
  event: NotificationEvent
  onRead: (id: string) => void
  onNavigate: (url: string) => void
}) {
  const Icon = EVENT_ICONS[event.event_type] || Bell
  const color = EVENT_COLORS[event.event_type] || "text-muted-foreground"
  const url = (event.payload?.url as string) || ""

  const handleClick = () => {
    if (!event.read) {
      onRead(event.id)
    }
    if (url) {
      onNavigate(url)
    }
  }

  return (
    <button
      onClick={handleClick}
      className={cn(
        "hover:bg-accent/50 flex w-full items-start gap-3 p-3 text-left transition-colors",
        !event.read && "bg-accent/20"
      )}
    >
      <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", color)} />
      <div className="min-w-0 flex-1">
        <p
          className={cn("text-sm leading-tight", !event.read && "font-medium")}
        >
          {event.title}
        </p>
        {event.summary && (
          <p className="text-muted-foreground mt-0.5 line-clamp-2 text-xs">
            {event.summary}
          </p>
        )}
        <p className="text-muted-foreground mt-1 text-xs">
          {formatDistanceToNow(new Date(event.created_at), { addSuffix: true })}
        </p>
      </div>
      {!event.read && (
        <div className="bg-primary mt-1.5 h-2 w-2 shrink-0 rounded-full" />
      )}
    </button>
  )
}

export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const { data: unreadData } = useUnreadCount()
  const { data: eventsData } = useNotificationEvents({ page_size: 20 })
  const markRead = useMarkEventRead()
  const markAllRead = useMarkAllRead()

  // Bridge SSE events to native local notifications when foregrounded
  const showLocalNotification = useLocalNotificationBridge()

  // Subscribe to SSE for real-time updates, forwarding to local notifications
  useNotificationSSE(showLocalNotification)

  // Handle notification tap -> navigate to payload URL
  useNotificationTapHandler()

  const unreadCount = unreadData?.count ?? 0
  const events = eventsData?.events ?? []

  const handleRead = (id: string) => {
    markRead.mutate(id)
  }

  const handleMarkAllRead = () => {
    markAllRead.mutate()
  }

  const handleNavigate = (url: string) => {
    setOpen(false)
    navigate({ to: url })
  }

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <Tooltip>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="relative"
              aria-label={
                unreadCount > 0
                  ? `Notifications (${unreadCount} unread)`
                  : "Notifications"
              }
            >
              <Bell className="h-5 w-5" />
              {unreadCount > 0 && (
                <span className="bg-primary text-primary-foreground absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-bold">
                  {unreadCount > 99 ? "99+" : unreadCount}
                </span>
              )}
            </Button>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent>
          Notifications{unreadCount > 0 ? ` (${unreadCount} unread)` : ""}
        </TooltipContent>
      </Tooltip>

      <DropdownMenuContent align="end" className="w-80 p-0 md:w-96">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h3 className="text-sm font-semibold">Notifications</h3>
          {unreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-auto px-2 py-1 text-xs"
              onClick={handleMarkAllRead}
            >
              <CheckCheck className="mr-1 h-3 w-3" />
              Mark all read
            </Button>
          )}
        </div>

        {/* Event list */}
        <ScrollArea className="max-h-[400px]">
          {events.length === 0 ? (
            <div className="text-muted-foreground flex flex-col items-center justify-center py-8">
              <Bell className="mb-2 h-8 w-8 opacity-50" />
              <p className="text-sm">No notifications yet</p>
            </div>
          ) : (
            <div className="divide-y">
              {events.map((event) => (
                <NotificationItem
                  key={event.id}
                  event={event}
                  onRead={handleRead}
                  onNavigate={handleNavigate}
                />
              ))}
            </div>
          )}
        </ScrollArea>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
