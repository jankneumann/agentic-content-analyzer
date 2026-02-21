/**
 * AppShell Component
 *
 * The main layout wrapper for the application.
 * Combines the sidebar, header, and content area into a cohesive layout.
 *
 * Features:
 * - Responsive sidebar (collapsible on desktop, sheet on mobile)
 * - Persistent sidebar state via localStorage
 * - Proper scroll handling
 * - Keyboard accessibility
 *
 * @example
 * // In your root layout
 * <AppShell>
 *   <Outlet /> {/* Router outlet for page content *\/}
 * </AppShell>
 */

import { useState, useEffect } from "react"

import { cn } from "@/lib/utils"
import { Sidebar } from "./Sidebar"
import { Header } from "./Header"
import { TooltipProvider } from "@/components/ui/tooltip"

/**
 * Props for the AppShell component
 */
interface AppShellProps {
  /** Main content (typically router outlet) */
  children: React.ReactNode
  /** Additional CSS classes */
  className?: string
}

/**
 * Storage key for sidebar collapsed state
 */
const SIDEBAR_COLLAPSED_KEY = "sidebar-collapsed"

/**
 * AppShell component
 *
 * Main application layout with sidebar and header.
 */
export function AppShell({ children, className }: AppShellProps) {
  // Sidebar collapsed state - persisted to localStorage
  const [isCollapsed, setIsCollapsed] = useState(() => {
    // Only access localStorage on client side
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem(SIDEBAR_COLLAPSED_KEY)
      return stored === "true"
    }
    return false
  })

  // Mobile menu open state
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)

  // Persist collapsed state to localStorage
  useEffect(() => {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(isCollapsed))
  }, [isCollapsed])

  // Close mobile menu on route change or escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsMobileMenuOpen(false)
      }
    }

    document.addEventListener("keydown", handleEscape)
    return () => document.removeEventListener("keydown", handleEscape)
  }, [])

  return (
    <TooltipProvider delayDuration={0}>
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:rounded-md focus:bg-background focus:text-foreground focus:ring-2 focus:ring-ring focus:shadow-lg focus:outline-none"
      >
        Skip to main content
      </a>
      <div className={cn("flex h-screen overflow-hidden pt-[var(--safe-area-top)]", className)}>
        {/* Desktop Sidebar */}
        <div className="hidden md:block">
          <Sidebar
            isCollapsed={isCollapsed}
            onToggleCollapse={() => setIsCollapsed(!isCollapsed)}
          />
        </div>

        {/* Mobile Sidebar Overlay */}
        {isMobileMenuOpen && (
          <>
            {/* Backdrop */}
            <div
              className="fixed inset-0 z-40 bg-black/50 md:hidden"
              onClick={() => setIsMobileMenuOpen(false)}
              aria-hidden="true"
            />
            {/* Sidebar */}
            <div className="fixed inset-y-0 left-0 z-50 pt-[var(--safe-area-top)] md:hidden">
              <Sidebar
                isCollapsed={false}
                onToggleCollapse={() => setIsMobileMenuOpen(false)}
              />
            </div>
          </>
        )}

        {/* Main Content Area */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Header */}
          <Header onMenuClick={() => setIsMobileMenuOpen(true)} />

          {/* Page Content */}
          <main
            id="main-content"
            tabIndex={-1}
            className="flex-1 overflow-auto bg-muted/30 outline-none"
          >
            {children}
          </main>
        </div>
      </div>
    </TooltipProvider>
  )
}
