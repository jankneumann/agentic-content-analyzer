import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import ForceGraph2D from "react-force-graph-2d"
import type { ThemeCategory, ThemeData, ThemeTrend } from "@/types/theme"

// ---------------------------------------------------------------------------
// Public interface
// ---------------------------------------------------------------------------

interface ThemeNetworkGraphProps {
  themes: ThemeData[]
}

// ---------------------------------------------------------------------------
// Internal types
// ---------------------------------------------------------------------------

interface ThemeNode {
  id: string
  name: string
  category: ThemeCategory
  trend: ThemeTrend
  relevance: number
  val: number
}

interface ThemeLink {
  source: string
  target: string
}

interface TooltipState {
  visible: boolean
  x: number
  y: number
  node: ThemeNode | null
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CATEGORY_COLORS: Record<ThemeCategory, string> = {
  ml_ai: "#3b82f6",
  devops_infra: "#22c55e",
  data_engineering: "#f97316",
  business_strategy: "#a855f7",
  tools_products: "#14b8a6",
  research_academia: "#ef4444",
  security: "#eab308",
  other: "#6b7280",
}

const CATEGORY_LABELS: Record<ThemeCategory, string> = {
  ml_ai: "ML / AI",
  devops_infra: "DevOps / Infra",
  data_engineering: "Data Engineering",
  business_strategy: "Business Strategy",
  tools_products: "Tools / Products",
  research_academia: "Research / Academia",
  security: "Security",
  other: "Other",
}

const GRAPH_HEIGHT = 500

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ThemeNetworkGraph({ themes }: ThemeNetworkGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState(800)
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [tooltip, setTooltip] = useState<TooltipState>({
    visible: false,
    x: 0,
    y: 0,
    node: null,
  })

  // Measure container width -------------------------------------------------
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerWidth(entry.contentRect.width)
      }
    })
    observer.observe(el)
    setContainerWidth(el.clientWidth)

    return () => observer.disconnect()
  }, [])

  // Build graph data --------------------------------------------------------
  const graphData = useMemo(() => {
    const themeNames = new Set(themes.map((t) => t.name))
    const nodes: ThemeNode[] = themes.map((t) => ({
      id: t.name,
      name: t.name,
      category: t.category,
      trend: t.trend,
      relevance: t.relevance_score,
      val: Math.max(t.relevance_score * 20, 3),
    }))
    const links: ThemeLink[] = []
    for (const theme of themes) {
      for (const related of theme.related_themes) {
        if (themeNames.has(related) && theme.name < related) {
          links.push({ source: theme.name, target: related })
        }
      }
    }
    return { nodes, links }
  }, [themes])

  // Derive selected-node neighbours for highlighting ------------------------
  const selectedNeighbors = useMemo(() => {
    if (!selectedNode) return new Set<string>()
    const neighbors = new Set<string>()
    neighbors.add(selectedNode)
    for (const link of graphData.links) {
      const src = typeof link.source === "object" ? (link.source as ThemeNode).id : link.source
      const tgt = typeof link.target === "object" ? (link.target as ThemeNode).id : link.target
      if (src === selectedNode) neighbors.add(tgt)
      if (tgt === selectedNode) neighbors.add(src)
    }
    return neighbors
  }, [selectedNode, graphData.links])

  // Handlers ----------------------------------------------------------------
  const handleNodeClick = useCallback(
    (node: { id?: string | number }) => {
      const id = String(node.id)
      setSelectedNode((prev) => (prev === id ? null : id))
    },
    [],
  )

  const handleNodeHover = useCallback(
    (node: { id?: string | number } | null, _prev: unknown) => {
      if (!node) {
        setTooltip((t) => ({ ...t, visible: false }))
        return
      }
      const el = containerRef.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      // node has x/y in graph coords after simulation — we approximate tooltip
      // position from the canvas center + offset. The library does not expose
      // screen coords in hover, so we place the tooltip near the cursor via
      // a mousemove listener below.
      setTooltip({
        visible: true,
        x: rect.width / 2,
        y: rect.height / 2,
        node: node as ThemeNode,
      })
    },
    [],
  )

  // Track mouse position for tooltip placement
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    setTooltip((prev) => {
      if (!prev.visible) return prev
      const rect = containerRef.current?.getBoundingClientRect()
      if (!rect) return prev
      return {
        ...prev,
        x: e.clientX - rect.left + 12,
        y: e.clientY - rect.top + 12,
      }
    })
  }, [])

  const handleBackgroundClick = useCallback(() => {
    setSelectedNode(null)
  }, [])

  // Custom node renderer ----------------------------------------------------
  const nodeCanvasObject = useCallback(
    (
      node: { id?: string | number; x?: number; y?: number },
      ctx: CanvasRenderingContext2D,
      globalScale: number,
    ) => {
      const n = node as ThemeNode & { x: number; y: number }
      const label = n.name
      const fontSize = Math.min(12 / globalScale, 4)
      const radius = Math.sqrt(Math.max(n.val, 1)) * 2

      const isHighlighted = selectedNode === null || selectedNeighbors.has(n.id)
      const alpha = isHighlighted ? 1 : 0.15

      // Circle
      ctx.beginPath()
      ctx.arc(n.x, n.y, radius, 0, 2 * Math.PI, false)
      ctx.fillStyle = hexWithAlpha(CATEGORY_COLORS[n.category] ?? CATEGORY_COLORS.other, alpha)
      ctx.fill()

      // Selection ring
      if (selectedNode === n.id) {
        ctx.strokeStyle = "#ffffff"
        ctx.lineWidth = 1.5 / globalScale
        ctx.stroke()
      }

      // Label
      ctx.font = `${fontSize}px Sans-Serif`
      ctx.textAlign = "center"
      ctx.textBaseline = "top"
      ctx.fillStyle = hexWithAlpha("#e2e8f0", alpha)
      ctx.fillText(label, n.x, n.y + radius + 1)
    },
    [selectedNode, selectedNeighbors],
  )

  // Pointer area paint for hit detection ------------------------------------
  const nodePointerAreaPaint = useCallback(
    (
      node: { id?: string | number; x?: number; y?: number },
      color: string,
      ctx: CanvasRenderingContext2D,
    ) => {
      const n = node as ThemeNode & { x: number; y: number }
      const radius = Math.sqrt(Math.max(n.val, 1)) * 2 + 2
      ctx.beginPath()
      ctx.arc(n.x, n.y, radius, 0, 2 * Math.PI, false)
      ctx.fillStyle = color
      ctx.fill()
    },
    [],
  )

  // Link color with dimming -------------------------------------------------
  const linkColor = useCallback(
    (link: { source?: unknown; target?: unknown }) => {
      if (selectedNode === null) return "rgba(148,163,184,0.3)"
      const src = typeof link.source === "object" ? (link.source as ThemeNode).id : String(link.source)
      const tgt = typeof link.target === "object" ? (link.target as ThemeNode).id : String(link.target)
      if (selectedNeighbors.has(src) && selectedNeighbors.has(tgt)) {
        return "rgba(148,163,184,0.6)"
      }
      return "rgba(148,163,184,0.05)"
    },
    [selectedNode, selectedNeighbors],
  )

  // Empty state -------------------------------------------------------------
  if (themes.length === 0 || graphData.links.length === 0) {
    return (
      <div style={{ position: "relative", height: GRAPH_HEIGHT }}>
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#94a3b8",
            fontSize: 14,
            textAlign: "center",
            padding: 24,
          }}
        >
          No theme relationships found. Themes with related_themes connections
          will appear as a network.
        </div>
      </div>
    )
  }

  // Render ------------------------------------------------------------------
  return (
    <div ref={containerRef} style={{ position: "relative", height: GRAPH_HEIGHT }}>
      {/* Graph */}
      <div onMouseMove={handleMouseMove}>
        <ForceGraph2D
          graphData={graphData}
          width={containerWidth}
          height={GRAPH_HEIGHT}
          backgroundColor="transparent"
          nodeCanvasObjectMode={() => "replace"}
          nodeCanvasObject={nodeCanvasObject}
          nodePointerAreaPaint={nodePointerAreaPaint}
          linkColor={linkColor}
          linkWidth={1}
          onNodeClick={handleNodeClick}
          onNodeHover={handleNodeHover}
          onBackgroundClick={handleBackgroundClick}
          enableNodeDrag
          cooldownTicks={100}
          d3AlphaDecay={0.02}
          d3VelocityDecay={0.3}
        />
      </div>

      {/* Tooltip */}
      {tooltip.visible && tooltip.node && (
        <div
          style={{
            position: "absolute",
            left: tooltip.x,
            top: tooltip.y,
            pointerEvents: "none",
            background: "rgba(15,23,42,0.95)",
            border: "1px solid rgba(148,163,184,0.2)",
            borderRadius: 6,
            padding: "8px 12px",
            fontSize: 12,
            lineHeight: 1.5,
            color: "#e2e8f0",
            maxWidth: 260,
            zIndex: 10,
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 2 }}>
            {tooltip.node.name}
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <span>
              <span style={{ color: "#94a3b8" }}>Category:</span>{" "}
              <span
                style={{
                  color: CATEGORY_COLORS[tooltip.node.category] ?? CATEGORY_COLORS.other,
                }}
              >
                {CATEGORY_LABELS[tooltip.node.category] ?? tooltip.node.category}
              </span>
            </span>
            <span>
              <span style={{ color: "#94a3b8" }}>Trend:</span>{" "}
              {tooltip.node.trend}
            </span>
          </div>
          <div>
            <span style={{ color: "#94a3b8" }}>Relevance:</span>{" "}
            {tooltip.node.relevance.toFixed(2)}
          </div>
        </div>
      )}

      {/* Legend */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "8px 16px",
          justifyContent: "center",
          padding: "8px 0 0",
          fontSize: 12,
          color: "#94a3b8",
        }}
      >
        {(Object.entries(CATEGORY_COLORS) as [ThemeCategory, string][]).map(
          ([cat, color]) => (
            <span key={cat} style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span
                style={{
                  display: "inline-block",
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  backgroundColor: color,
                  flexShrink: 0,
                }}
              />
              {CATEGORY_LABELS[cat]}
            </span>
          ),
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function hexWithAlpha(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}
