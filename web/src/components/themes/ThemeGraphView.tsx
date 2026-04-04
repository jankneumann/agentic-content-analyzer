/**
 * ThemeGraphView Component
 *
 * Tabbed container for theme visualizations:
 * - Network: Force-directed graph of theme relationships
 * - Timeline: Horizontal bar chart of theme evolution
 */

import { useState } from "react"

import { cn } from "@/lib/utils"
import { ThemeNetworkGraph } from "./ThemeNetworkGraph"
import { ThemeTimelineChart } from "./ThemeTimelineChart"
import type { ThemeData } from "@/types/theme"

type GraphTab = "network" | "timeline"

interface ThemeGraphViewProps {
  themes: ThemeData[]
  defaultTab?: GraphTab
  activeTab?: GraphTab
  onTabChange?: (tab: GraphTab) => void
}

export function ThemeGraphView({
  themes,
  defaultTab = "network",
  activeTab: controlledTab,
  onTabChange,
}: ThemeGraphViewProps) {
  const [internalTab, setInternalTab] = useState<GraphTab>(defaultTab)
  const activeTab = controlledTab ?? internalTab

  const handleTabChange = (tab: GraphTab) => {
    setInternalTab(tab)
    onTabChange?.(tab)
  }

  return (
    <div className="space-y-4">
      {/* Tab buttons */}
      <div role="tablist" className="bg-muted flex w-fit gap-1 rounded-lg p-1">
        <button
          role="tab"
          aria-selected={activeTab === "network"}
          onClick={() => handleTabChange("network")}
          className={cn(
            "focus-visible:ring-ring rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none",
            activeTab === "network"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          Network
        </button>
        <button
          role="tab"
          aria-selected={activeTab === "timeline"}
          onClick={() => handleTabChange("timeline")}
          className={cn(
            "focus-visible:ring-ring rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none",
            activeTab === "timeline"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          Timeline
        </button>
      </div>

      {/* Tab content */}
      {activeTab === "network" ? (
        <ThemeNetworkGraph themes={themes} />
      ) : (
        <ThemeTimelineChart themes={themes} />
      )}
    </div>
  )
}

export default ThemeGraphView
