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

import { useNavigate, useLocation } from "@tanstack/react-router"
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
  isActive,
}: {
  item: NavItem
  isCollapsed: boolean
  isActive: boolean
}) {
  const Icon = item.icon
  const navigate = useNavigate()

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    if (!item.disabled) {
      navigate({ to: item.href })
    }
  }

  // In collapsed mode, wrap with tooltip
  if (isCollapsed) {
    return (
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>
          <a
            href={item.href}
            onClick={handleClick}
            className={cn(
              // Base styles
              "flex h-10 w-10 items-center justify-center rounded-md",
              // Hover and active states
              isActive
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              // Disabled state
              item.disabled && "pointer-events-none opacity-50"
            )}
          >
            <Icon className="h-5 w-5" />
            <span className="sr-only">{item.title}</span>
          </a>
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
  return (
    <a
      href={item.href}
      onClick={handleClick}
      className={cn(
        // Base styles
        "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium",
        // Hover and active states
        isActive
          ? "bg-primary text-primary-foreground"
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
        // Disabled state
        item.disabled && "pointer-events-none opacity-50"
      )}
    >
      <Icon className="h-5 w-5 shrink-0" />
      <span className="truncate">{item.title}</span>
      {/* Badge for counts/notifications */}
      {item.badge && (
        <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-primary/10 px-1.5 text-xs font-medium text-primary">
          {item.badge}
        </span>
      )}
    </a>
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
  // Get current location for active state
  const location = useLocation()
  const currentPath = location.pathname

  return (
    <aside
      className={cn(
        // Base styles
        "flex h-full flex-col border-r bg-sidebar",
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
          <span className="text-xl font-bold text-primary">NA</span>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-xl font-bold text-primary">NA</span>
            <span className="font-semibold">Newsletter Aggregator</span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <ScrollArea className="flex-1 py-4">
        <nav className={cn("flex flex-col gap-4", isCollapsed ? "px-2" : "px-3")}>
          {navigation.map((group, groupIndex) => (
            <div key={group.title}>
              {/* Group title - hidden when collapsed */}
              {!isCollapsed && (
                <h4 className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  {group.title}
                </h4>
              )}

              {/* Separator between groups when collapsed */}
              {isCollapsed && groupIndex > 0 && (
                <Separator className="my-2" />
              )}

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
                    isActive={currentPath === item.href}
                  />
                ))}
              </div>
            </div>
          ))}
        </nav>
      </ScrollArea>

      {/* Collapse Toggle Button */}
      <div className="border-t p-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleCollapse}
          className={cn(
            "w-full justify-center",
            !isCollapsed && "justify-start"
          )}
          aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {isCollapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <>
              <ChevronLeft className="mr-2 h-4 w-4" />
              <span>Collapse</span>
            </>
          )}
        </Button>
      </div>
    </aside>
  )
}
