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
import { Menu, ChevronRight, Bell, Moon, Sun } from "lucide-react"
import { useState, useEffect } from "react"

import { cn } from "@/lib/utils"
import { getBreadcrumbs } from "@/lib/navigation"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

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
      <h1 className="text-lg font-semibold">
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
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
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
                className="text-sm text-muted-foreground hover:text-foreground"
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
  // Initialize state lazily to avoid hydration mismatch and useEffect set state warning
  const [isDark, setIsDark] = useState(() => {
    if (typeof window === "undefined") return false
    const stored = localStorage.getItem("theme")
    const prefersDark = window.matchMedia(
      "(prefers-color-scheme: dark)"
    ).matches
    return stored === "dark" || (!stored && prefersDark)
  })

  // Sync class with state
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add("dark")
    } else {
      document.documentElement.classList.remove("dark")
    }
  }, [isDark])

  // Toggle theme
  const toggleTheme = () => {
    const newIsDark = !isDark
    setIsDark(newIsDark)
    localStorage.setItem("theme", newIsDark ? "dark" : "light")
  }

  const label = `Switch to ${isDark ? "light" : "dark"} mode`

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="ghost" size="icon" onClick={toggleTheme}>
          {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          <span className="sr-only">{label}</span>
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
        "flex h-16 items-center gap-4 border-b bg-background px-4",
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
            >
              <Menu className="h-5 w-5" />
              <span className="sr-only">Open menu</span>
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
        {/* Notifications - placeholder for future */}
        <Button variant="ghost" size="icon" disabled>
          <Bell className="h-5 w-5" />
          <span className="sr-only">Notifications</span>
        </Button>

        {/* Theme toggle */}
        <ThemeToggle />
      </div>
    </header>
  )
}
