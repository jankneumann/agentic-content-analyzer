/**
 * Navigation Configuration
 *
 * Defines the sidebar navigation structure for the application.
 * Each item maps to a route and includes metadata for display.
 *
 * The navigation is organized into groups:
 * - Pipeline: Main workflow steps (newsletters → podcasts)
 * - Management: Review and approval workflows
 * - System: Settings and configuration
 */

import {
  Newspaper,
  Sparkles,
  BarChart3,
  FileText,
  Mic,
  Radio,
  LayoutDashboard,
  Settings,
  CheckSquare,
  type LucideIcon,
} from "lucide-react"

/**
 * Navigation item definition
 */
export interface NavItem {
  /** Display title */
  title: string
  /** Route path */
  href: string
  /** Lucide icon component */
  icon: LucideIcon
  /** Optional description for tooltips */
  description?: string
  /** Badge content (e.g., count of pending items) */
  badge?: string | number
  /** Whether this item is disabled */
  disabled?: boolean
}

/**
 * Navigation group (section in sidebar)
 */
export interface NavGroup {
  /** Group title (displayed as section header) */
  title: string
  /** Items in this group */
  items: NavItem[]
}

/**
 * Main navigation configuration
 *
 * Organized by functional area to help users understand
 * the workflow and find what they need quickly.
 */
export const navigation: NavGroup[] = [
  {
    title: "Overview",
    items: [
      {
        title: "Dashboard",
        href: "/",
        icon: LayoutDashboard,
        description: "Overview and recent activity",
      },
    ],
  },
  {
    title: "Pipeline",
    items: [
      {
        title: "Newsletters",
        href: "/newsletters",
        icon: Newspaper,
        description: "Ingested newsletters from Gmail and RSS",
      },
      {
        title: "Summaries",
        href: "/summaries",
        icon: Sparkles,
        description: "AI-generated newsletter summaries",
      },
      {
        title: "Themes",
        href: "/themes",
        icon: BarChart3,
        description: "Theme analysis and knowledge graph",
      },
      {
        title: "Digests",
        href: "/digests",
        icon: FileText,
        description: "Daily and weekly digest documents",
      },
      {
        title: "Scripts",
        href: "/scripts",
        icon: Mic,
        description: "Podcast dialogue scripts",
      },
      {
        title: "Podcasts",
        href: "/podcasts",
        icon: Radio,
        description: "Generated audio podcasts",
      },
    ],
  },
  {
    title: "Management",
    items: [
      {
        title: "Review Queue",
        href: "/review",
        icon: CheckSquare,
        description: "Items pending review and approval",
      },
    ],
  },
  {
    title: "System",
    items: [
      {
        title: "Settings",
        href: "/settings",
        icon: Settings,
        description: "Application configuration",
      },
    ],
  },
]

/**
 * Get a flat list of all navigation items
 *
 * Useful for route matching and breadcrumb generation.
 */
export function getAllNavItems(): NavItem[] {
  return navigation.flatMap((group) => group.items)
}

/**
 * Find navigation item by path
 *
 * @param path - Route path to find
 * @returns NavItem if found, undefined otherwise
 */
export function findNavItemByPath(path: string): NavItem | undefined {
  return getAllNavItems().find((item) => item.href === path)
}

/**
 * Get breadcrumb trail for a given path
 *
 * @param path - Current route path
 * @returns Array of breadcrumb items (always includes Dashboard)
 */
export function getBreadcrumbs(
  path: string
): Array<{ title: string; href: string }> {
  const breadcrumbs: Array<{ title: string; href: string }> = []

  // Always start with Dashboard unless we're already there
  if (path !== "/") {
    breadcrumbs.push({ title: "Dashboard", href: "/" })
  }

  // Find the current page
  const currentItem = findNavItemByPath(path)
  if (currentItem) {
    breadcrumbs.push({ title: currentItem.title, href: currentItem.href })
  }

  return breadcrumbs
}
