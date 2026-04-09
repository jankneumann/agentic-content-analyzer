/**
 * Header Component
 *
 * Top navigation bar with:
 * - Mobile menu toggle
 * - Breadcrumb navigation
 * - Action buttons (future: notifications, user menu)
 *
 * @example
 * <Header onMenuClick={() => setMobileMenuOpen(true)} />
 */

import { useNavigate, useLocation } from "@tanstack/react-router"
import { Menu, ChevronRight, Moon, Sun } from "lucide-react"
import { useState, useEffect } from "react"

import { cn } from "@/lib/utils"
import { getBreadcrumbs } from "@/lib/navigation"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { NotificationBell } from "@/components/notifications/NotificationBell"

/**
 * Props for the Header component
 */
interface HeaderProps {
  /** Callback when mobile menu button is clicked */
  onMenuClick?: () => void
  /** Additional CSS classes */
  className?: string
}

/**
 * Breadcrumb component
 *
 * Displays the current navigation path.
 * Each item except the last is a link.
 */
function Breadcrumbs() {
  const location = useLocation()
  const navigate = useNavigate()
  const breadcrumbs = getBreadcrumbs(location.pathname)

  const handleClick = (href: string) => (e: React.MouseEvent) => {
    e.preventDefault()
    navigate({ to: href })
  }

  // Don't render if only one item (we're at root)
  if (breadcrumbs.length <= 1) {
    return (
      <h1 className="text-lg font-semibold" aria-current="page">
        {breadcrumbs[0]?.title || "Dashboard"}
      </h1>
    )
  }

  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1">
      {breadcrumbs.map((crumb, index) => {
        const isLast = index === breadcrumbs.length - 1

        return (
          <div key={crumb.href} className="flex items-center gap-1">
            {/* Separator (except for first item) */}
            {index > 0 && (
              <ChevronRight className="text-muted-foreground h-4 w-4" />
            )}

            {/* Breadcrumb item */}
            {isLast ? (
              // Current page - not a link
              <span className="text-lg font-semibold" aria-current="page">
                {crumb.title}
              </span>
            ) : (
              // Parent page - link
              <a
                href={crumb.href}
                onClick={handleClick(crumb.href)}
                className="text-muted-foreground hover:text-foreground focus-visible:ring-ring rounded-sm text-sm focus-visible:ring-2 focus-visible:outline-none"
              >
                {crumb.title}
              </a>
            )}
          </div>
        )
      })}
    </nav>
  )
}

/**
 * Theme toggle component
 *
 * Switches between light and dark mode.
 * Persists preference to localStorage.
 */
function ThemeToggle() {
  // Initialize from localStorage or system preference lazily to prevent flash
  const [isDark, setIsDark] = useState(() => {
    if (typeof window === "undefined") return false
    const stored = localStorage.getItem("theme")
    const prefersDark = window.matchMedia(
      "(prefers-color-scheme: dark)"
    ).matches

    const initialDark = stored === "dark" || (!stored && prefersDark)

    // Apply class immediately if possible to reduce flash
    if (initialDark) {
      document.documentElement.classList.add("dark")
    }

    return initialDark
  })

  // Track whether the user has explicitly toggled the theme
  const [hasUserChoice, setHasUserChoice] = useState(
    () =>
      typeof window !== "undefined" && localStorage.getItem("theme") !== null
  )

  // Sync theme changes — only persist when the user has made an explicit choice
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add("dark")
    } else {
      document.documentElement.classList.remove("dark")
    }
    if (hasUserChoice) {
      localStorage.setItem("theme", isDark ? "dark" : "light")
    }
  }, [isDark, hasUserChoice])

  // Toggle theme — marks as explicit user choice
  const toggleTheme = () => {
    setHasUserChoice(true)
    setIsDark(!isDark)
  }

  const label = isDark ? "Switch to light mode" : "Switch to dark mode"

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label={label}>
          {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}

/**
 * Header component
 *
 * Main header with breadcrumbs and actions.
 */
export function Header({ onMenuClick, className }: HeaderProps) {
  return (
    <header
      className={cn(
        "bg-background flex h-16 items-center gap-4 border-b px-4",
        className
      )}
    >
      {/* Mobile menu button - only visible on small screens */}
      {onMenuClick && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={onMenuClick}
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Open menu</TooltipContent>
        </Tooltip>
      )}

      {/* Breadcrumbs */}
      <div className="flex-1">
        <Breadcrumbs />
      </div>

      {/* Right side actions */}
      <div className="flex items-center gap-2">
        {/* Notifications */}
        <NotificationBell />

        {/* Theme toggle */}
        <ThemeToggle />
      </div>
    </header>
  )
}
