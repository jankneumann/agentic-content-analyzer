import { useMemo } from "react"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts"
import { format } from "date-fns"
import type { ThemeData } from "@/types/theme"
import type { ThemeCategory, ThemeTrend } from "@/types/theme"

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
  devops_infra: "DevOps & Infra",
  data_engineering: "Data Engineering",
  business_strategy: "Business Strategy",
  tools_products: "Tools & Products",
  research_academia: "Research & Academia",
  security: "Security",
  other: "Other",
}

const TREND_LABELS: Record<ThemeTrend, string> = {
  emerging: "Emerging",
  growing: "Growing",
  established: "Established",
  declining: "Declining",
  one_off: "One-off",
}

const TREND_ARROWS: Record<ThemeTrend, string> = {
  emerging: "\u2197",
  growing: "\u2191",
  established: "\u2192",
  declining: "\u2193",
  one_off: "\u00B7",
}

interface ChartDataItem {
  name: string
  category: ThemeCategory
  trend: ThemeTrend
  relevance: number
  timeRange: [number, number]
  first_seen: string
  last_seen: string
}

function formatDate(timestamp: number): string {
  return format(new Date(timestamp), "MMM d")
}

interface CustomBarProps {
  x?: number
  y?: number
  width?: number
  height?: number
  payload?: ChartDataItem
}

function CustomBar({ x = 0, y = 0, width = 0, height = 0, payload }: CustomBarProps) {
  if (!payload) return null

  const color = CATEGORY_COLORS[payload.category] || CATEGORY_COLORS.other
  const opacity = 0.4 + payload.relevance * 0.6
  const barWidth = Math.max(width, 4)
  const trendText = TREND_ARROWS[payload.trend] || ""
  const showLabel = barWidth > 30

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={barWidth}
        height={height}
        fill={color}
        fillOpacity={opacity}
        rx={3}
        ry={3}
      />
      {showLabel && (
        <text
          x={x + barWidth / 2}
          y={y + height / 2}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={11}
          fill="#fff"
          fontWeight={500}
        >
          {trendText}
        </text>
      )}
    </g>
  )
}

function CustomTooltip({
  active,
  payload,
}: // eslint-disable-next-line @typescript-eslint/no-explicit-any
{ active?: boolean; payload?: any[] }) {
  if (!active || !payload || !payload[0]) return null

  const data = payload[0].payload as ChartDataItem
  const color = CATEGORY_COLORS[data.category] || CATEGORY_COLORS.other

  return (
    <div
      style={{
        background: "#1f2937",
        border: "1px solid #374151",
        borderRadius: 8,
        padding: "10px 14px",
        fontSize: 13,
        color: "#e5e7eb",
        lineHeight: 1.6,
        maxWidth: 280,
      }}
    >
      <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>
        {data.name}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
        <span
          style={{
            display: "inline-block",
            width: 10,
            height: 10,
            borderRadius: "50%",
            background: color,
          }}
        />
        <span>{CATEGORY_LABELS[data.category]}</span>
      </div>
      <div>
        Trend: {TREND_LABELS[data.trend]} {TREND_ARROWS[data.trend]}
      </div>
      <div>
        {format(new Date(data.first_seen), "MMM d, yyyy")} &mdash;{" "}
        {format(new Date(data.last_seen), "MMM d, yyyy")}
      </div>
      <div>Relevance: {(data.relevance * 100).toFixed(0)}%</div>
    </div>
  )
}

interface ThemeTimelineChartProps {
  themes: ThemeData[]
}

export function ThemeTimelineChart({ themes }: ThemeTimelineChartProps) {
  const chartData = useMemo<ChartDataItem[]>(() => {
    const sorted = [...themes].sort(
      (a, b) =>
        new Date(a.first_seen).getTime() - new Date(b.first_seen).getTime()
    )
    return sorted.map((theme) => ({
      name: theme.name,
      category: theme.category,
      trend: theme.trend,
      relevance: theme.relevance_score,
      timeRange: [
        new Date(theme.first_seen).getTime(),
        new Date(theme.last_seen).getTime(),
      ] as [number, number],
      first_seen: theme.first_seen,
      last_seen: theme.last_seen,
    }))
  }, [themes])

  const activeCategories = useMemo(() => {
    const cats = new Set(themes.map((t) => t.category))
    return (Object.keys(CATEGORY_COLORS) as ThemeCategory[]).filter((c) =>
      cats.has(c)
    )
  }, [themes])

  if (themes.length === 0) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: 300,
          color: "#9ca3af",
          fontSize: 14,
        }}
      >
        No themes to display
      </div>
    )
  }

  const chartHeight = Math.max(themes.length * 40 + 80, 300)

  return (
    <div>
      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart
          layout="vertical"
          data={chartData}
          margin={{ top: 10, right: 30, left: 10, bottom: 10 }}
        >
          <XAxis
            type="number"
            domain={["dataMin", "dataMax"]}
            tickFormatter={formatDate}
            tick={{ fontSize: 11, fill: "#9ca3af" }}
            axisLine={{ stroke: "#374151" }}
            tickLine={{ stroke: "#374151" }}
          />
          <YAxis
            dataKey="name"
            type="category"
            width={150}
            tick={{ fontSize: 12, fill: "#d1d5db" }}
            axisLine={{ stroke: "#374151" }}
            tickLine={false}
          />
          <Tooltip content={<CustomTooltip />} cursor={false} />
          <Bar
            dataKey="timeRange"
            shape={<CustomBar />}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>

      {/* Category legend */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "12px 20px",
          justifyContent: "center",
          paddingTop: 12,
        }}
      >
        {activeCategories.map((category) => (
          <div
            key={category}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12,
              color: "#9ca3af",
            }}
          >
            <span
              style={{
                display: "inline-block",
                width: 10,
                height: 10,
                borderRadius: "50%",
                background: CATEGORY_COLORS[category],
              }}
            />
            {CATEGORY_LABELS[category]}
          </div>
        ))}
      </div>
    </div>
  )
}
