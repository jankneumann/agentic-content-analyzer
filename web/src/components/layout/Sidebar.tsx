/**
 * Sidebar Component
 *
 * The main navigation sidebar for the application.
 * Features:
 * - Collapsible (icon-only mode)
 * - Grouped navigation items
 * - Active state highlighting
 * - Tooltips in collapsed mode
 * - Responsive (hidden on mobile, shown via sheet)
 *
 * @example
 * <Sidebar
 *   isCollapsed={isCollapsed}
 *   onToggleCollapse={() => setIsCollapsed(!isCollapsed)}
 * />
 */

import { Link } from "@tanstack/react-router"
import { ChevronLeft, ChevronRight } from "lucide-react"

import { cn } from "@/lib/utils"
import { navigation, type NavItem } from "@/lib/navigation"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

/**
 * Props for the Sidebar component
 */
interface SidebarProps {
  /** Whether the sidebar is collapsed (icon-only mode) */
  isCollapsed: boolean
  /** Callback to toggle collapse state */
  onToggleCollapse: () => void
  /** Additional CSS classes */
  className?: string
}

/**
 * Individual navigation item component
 *
 * Handles both expanded and collapsed states,
 * showing tooltips when collapsed.
 */
function NavItemComponent({
  item,
  isCollapsed,
}: {
  item: NavItem
  isCollapsed: boolean
}) {
  const Icon = item.icon

  // In collapsed mode, wrap with tooltip
  if (isCollapsed) {
    const baseClasses = cn(
      "flex h-10 w-10 items-center justify-center rounded-md",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      item.disabled && "pointer-events-none opacity-50"
    )

    return (
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>
          <Link
            to={item.href}
            activeOptions={{ exact: item.href === "/" }}
            activeProps={{
              className: cn(baseClasses, "bg-primary text-primary-foreground"),
              "aria-current": "page",
            }}
            inactiveProps={{
              className: cn(
                baseClasses,
                "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              ),
            }}
            className={baseClasses}
          >
            <Icon className="h-5 w-5" />
            <span className="sr-only">{item.title}</span>
          </Link>
        </TooltipTrigger>
        <TooltipContent side="right" className="flex items-center gap-4">
          {item.title}
          {item.description && (
            <span className="text-muted-foreground">{item.description}</span>
          )}
        </TooltipContent>
      </Tooltip>
    )
  }

  // Expanded mode - full navigation item
  const baseClasses = cn(
    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
    item.disabled && "pointer-events-none opacity-50"
  )

  return (
    <Link
      to={item.href}
      activeOptions={{ exact: item.href === "/" }}
      activeProps={{
        className: cn(baseClasses, "bg-primary text-primary-foreground"),
        "aria-current": "page",
      }}
      inactiveProps={{
        className: cn(
          baseClasses,
          "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
        ),
      }}
      className={baseClasses}
    >
      <Icon className="h-5 w-5 shrink-0" />
      <span className="truncate">{item.title}</span>
      {/* Badge for counts/notifications */}
      {item.badge && (
        <span className="bg-primary/10 text-primary ml-auto flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-xs font-medium">
          {item.badge}
        </span>
      )}
    </Link>
  )
}

/**
 * Sidebar component
 *
 * Main navigation sidebar with collapsible functionality.
 */
export function Sidebar({
  isCollapsed,
  onToggleCollapse,
  className,
}: SidebarProps) {
  return (
    <aside
      className={cn(
        // Base styles
        "bg-sidebar flex h-full flex-col border-r",
        // Width transition
        "transition-all duration-300 ease-in-out",
        isCollapsed ? "w-16" : "w-64",
        className
      )}
    >
      {/* Logo/Brand Section */}
      <div
        className={cn(
          "flex h-16 items-center border-b px-4",
          isCollapsed && "justify-center px-2"
        )}
      >
        {isCollapsed ? (
          <img src="/icons/icon-192.png" alt="ACA" className="h-8 w-8" />
        ) : (
          <div className="flex items-center gap-2">
            <img src="/icons/icon-192.png" alt="ACA" className="h-8 w-8" />
            <span className="font-semibold">AI Content Analyzer</span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <ScrollArea className="flex-1 py-4">
        <nav
          className={cn("flex flex-col gap-4", isCollapsed ? "px-2" : "px-3")}
        >
          {navigation.map((group, groupIndex) => (
            <div key={group.title}>
              {/* Group title - hidden when collapsed */}
              {!isCollapsed && (
                <h4 className="text-muted-foreground mb-2 px-3 text-xs font-semibold tracking-wider uppercase">
                  {group.title}
                </h4>
              )}

              {/* Separator between groups when collapsed */}
              {isCollapsed && groupIndex > 0 && <Separator className="my-2" />}

              {/* Navigation items */}
              <div
                className={cn(
                  "flex flex-col gap-1",
                  isCollapsed && "items-center"
                )}
              >
                {group.items.map((item) => (
                  <NavItemComponent
                    key={item.href}
                    item={item}
                    isCollapsed={isCollapsed}
                  />
                ))}
              </div>
            </div>
          ))}
        </nav>
      </ScrollArea>

      {/* Collapse Toggle Button */}
      <div className="border-t p-2">
        {isCollapsed ? (
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                onClick={onToggleCollapse}
                aria-label="Expand sidebar"
                className="w-full justify-center"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">Expand sidebar</TooltipContent>
          </Tooltip>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleCollapse}
            aria-label="Collapse sidebar"
            className="w-full justify-start"
          >
            <ChevronLeft className="mr-2 h-4 w-4" />
            <span>Collapse</span>
          </Button>
        )}
      </div>
    </aside>
  )
}
