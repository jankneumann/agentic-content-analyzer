import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { ThemeGraphView } from "../ThemeGraphView"
import { mockThemes, emptyThemes } from "@/test/theme-fixtures"

// jsdom lacks ResizeObserver — provide a minimal stub
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver

vi.mock("react-force-graph-2d", () => ({
  __esModule: true,
  default: (props: { graphData?: { nodes: unknown[]; links: unknown[] } }) => (
    <div data-testid="force-graph-2d">
      <span data-testid="node-count">{props.graphData?.nodes.length ?? 0}</span>
      <span data-testid="link-count">{props.graphData?.links.length ?? 0}</span>
    </div>
  ),
}))

vi.mock("recharts", async () => {
  const actual = await vi.importActual<typeof import("recharts")>("recharts")
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container" style={{ width: 800, height: 400 }}>
        {children}
      </div>
    ),
  }
})

describe("ThemeGraphView", () => {
  it("renders Network tab by default", () => {
    render(<ThemeGraphView themes={mockThemes} />)

    const networkBtn = screen.getByText("Network")
    expect(networkBtn).toHaveClass("bg-background")

    const timelineBtn = screen.getByText("Timeline")
    expect(timelineBtn).toHaveClass("text-muted-foreground")
  })

  it("switches to Timeline tab on click", async () => {
    const user = userEvent.setup()
    render(<ThemeGraphView themes={mockThemes} />)

    const timelineBtn = screen.getByText("Timeline")
    await user.click(timelineBtn)

    expect(timelineBtn).toHaveClass("bg-background")
    expect(screen.getByText("Network")).toHaveClass("text-muted-foreground")
  })

  it("renders ThemeNetworkGraph in Network tab", () => {
    render(<ThemeGraphView themes={mockThemes} />)

    expect(screen.getByTestId("force-graph-2d")).toBeInTheDocument()
    expect(screen.getByTestId("node-count")).toHaveTextContent("3")
    // RAG Architecture <-> LLM Fine-tuning (one link, alphabetical dedup)
    expect(screen.getByTestId("link-count")).toHaveTextContent("1")
  })

  it("renders ThemeTimelineChart in Timeline tab", async () => {
    const user = userEvent.setup()
    render(<ThemeGraphView themes={mockThemes} />)

    await user.click(screen.getByText("Timeline"))

    expect(screen.getByTestId("responsive-container")).toBeInTheDocument()
  })

  it("preserves tab selection via controlled props", () => {
    render(
      <ThemeGraphView themes={mockThemes} activeTab="timeline" onTabChange={() => {}} />
    )

    expect(screen.getByText("Timeline")).toHaveClass("bg-background")
    expect(screen.getByText("Network")).toHaveClass("text-muted-foreground")
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument()
  })

  it("calls onTabChange when tab switches", async () => {
    const user = userEvent.setup()
    const onTabChange = vi.fn()
    render(<ThemeGraphView themes={mockThemes} onTabChange={onTabChange} />)

    await user.click(screen.getByText("Timeline"))
    expect(onTabChange).toHaveBeenCalledWith("timeline")

    await user.click(screen.getByText("Network"))
    expect(onTabChange).toHaveBeenCalledWith("network")

    expect(onTabChange).toHaveBeenCalledTimes(2)
  })

  it("shows empty state when no themes in Network tab", () => {
    render(<ThemeGraphView themes={emptyThemes} />)

    expect(
      screen.getByText("No themes to display. Run a theme analysis to see the network.")
    ).toBeInTheDocument()
  })

  it("shows empty state when no themes in Timeline tab", async () => {
    const user = userEvent.setup()
    render(<ThemeGraphView themes={emptyThemes} />)

    await user.click(screen.getByText("Timeline"))

    expect(screen.getByText("No themes to display")).toBeInTheDocument()
  })
})
