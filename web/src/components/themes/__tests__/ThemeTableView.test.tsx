import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { ThemeTableView } from "../ThemeTableView"
import { mockThemes, emptyThemes } from "@/test/theme-fixtures"

describe("ThemeTableView", () => {
  it("renders all themes in the table", () => {
    render(<ThemeTableView themes={mockThemes} />)

    expect(screen.getByText("RAG Architecture")).toBeInTheDocument()
    expect(screen.getByText("LLM Fine-tuning")).toBeInTheDocument()
    expect(screen.getByText("Edge AI Deployment")).toBeInTheDocument()
  })

  it("shows empty state when no themes", () => {
    render(<ThemeTableView themes={emptyThemes} />)

    expect(screen.getByText("No themes to display")).toBeInTheDocument()
  })

  it("sorts by relevance descending by default", () => {
    render(<ThemeTableView themes={mockThemes} />)

    // Get all data rows (skip header row)
    const rows = screen.getAllByRole("row")
    // Row 0 is the header, rows 1-3 are data
    const firstDataRow = rows[1]
    const secondDataRow = rows[2]
    const thirdDataRow = rows[3]

    expect(within(firstDataRow).getByText("RAG Architecture")).toBeInTheDocument()
    expect(within(secondDataRow).getByText("LLM Fine-tuning")).toBeInTheDocument()
    expect(within(thirdDataRow).getByText("Edge AI Deployment")).toBeInTheDocument()
  })

  it("sorts by name ascending when name header clicked", async () => {
    const user = userEvent.setup()
    render(<ThemeTableView themes={mockThemes} />)

    // Click the Name column header to sort by name ascending
    await user.click(screen.getByText("Name"))

    const rows = screen.getAllByRole("row")
    // Alphabetical order: Edge AI Deployment, LLM Fine-tuning, RAG Architecture
    expect(within(rows[1]).getByText("Edge AI Deployment")).toBeInTheDocument()
    expect(within(rows[2]).getByText("LLM Fine-tuning")).toBeInTheDocument()
    expect(within(rows[3]).getByText("RAG Architecture")).toBeInTheDocument()
  })

  it("filters by category when category badge clicked", async () => {
    const user = userEvent.setup()
    render(<ThemeTableView themes={mockThemes} />)

    // Click the DevOps/Infra category filter badge
    // The filter badges are in the filter area above the table, not in the table rows.
    // There will be multiple "DevOps/Infra" badges (filter + row). Get the first one (filter).
    const filterBadges = screen.getAllByText("DevOps/Infra")
    await user.click(filterBadges[0])

    // Only Edge AI Deployment should remain visible
    expect(screen.getByText("Edge AI Deployment")).toBeInTheDocument()
    expect(screen.queryByText("RAG Architecture")).not.toBeInTheDocument()
    expect(screen.queryByText("LLM Fine-tuning")).not.toBeInTheDocument()
  })

  it("filters by trend when trend badge clicked", async () => {
    const user = userEvent.setup()
    render(<ThemeTableView themes={mockThemes} />)

    // Click the Emerging trend filter badge
    const trendBadges = screen.getAllByText("Emerging")
    await user.click(trendBadges[0])

    // Only LLM Fine-tuning (trend: emerging) should remain
    expect(screen.getByText("LLM Fine-tuning")).toBeInTheDocument()
    expect(screen.queryByText("RAG Architecture")).not.toBeInTheDocument()
    expect(screen.queryByText("Edge AI Deployment")).not.toBeInTheDocument()
  })

  it("expands row to show details on click", async () => {
    const user = userEvent.setup()
    render(<ThemeTableView themes={mockThemes} />)

    // Description should not be visible before expanding
    expect(
      screen.queryByText("Retrieval-Augmented Generation patterns and best practices")
    ).not.toBeInTheDocument()

    // Click the RAG Architecture row to expand it
    await user.click(screen.getByText("RAG Architecture"))

    // Description should now be visible
    expect(
      screen.getByText("Retrieval-Augmented Generation patterns and best practices")
    ).toBeInTheDocument()

    // Key points should also appear
    expect(
      screen.getByText("Hybrid retrieval combining BM25 and vector search")
    ).toBeInTheDocument()
    expect(
      screen.getByText("Chunk size optimization is critical for quality")
    ).toBeInTheDocument()
  })

  it("shows historical context in expanded row when available", async () => {
    const user = userEvent.setup()
    render(<ThemeTableView themes={mockThemes} />)

    // Click Edge AI Deployment row (has historical_context)
    await user.click(screen.getByText("Edge AI Deployment"))

    // Evolution summary should be visible
    expect(
      screen.getByText(
        "Growing interest since Nvidia and Qualcomm pushed edge inference SDKs"
      )
    ).toBeInTheDocument()
  })

  it("shows related themes in expanded row", async () => {
    const user = userEvent.setup()
    render(<ThemeTableView themes={mockThemes} />)

    // Expand RAG Architecture row
    await user.click(screen.getByText("RAG Architecture"))

    // Related themes should appear as badges.
    // "LLM Fine-tuning" also appears as a table row name, so find within the expanded detail area.
    // "Vector Databases" is only in related themes, so it's unique.
    expect(screen.getByText("Vector Databases")).toBeInTheDocument()
    // Verify "LLM Fine-tuning" appears at least twice (row + related badge)
    expect(screen.getAllByText("LLM Fine-tuning").length).toBeGreaterThanOrEqual(2)
  })

  it("displays relevance scores as percentages", () => {
    render(<ThemeTableView themes={mockThemes} />)

    // Each row shows relevance, strategic, and tactical as percentages.
    // Verify specific percentages exist in the correct rows.
    const rows = screen.getAllByRole("row")

    // RAG Architecture (row 1): relevance 85%, strategic 90%, tactical 80%
    expect(within(rows[1]).getByText("85%")).toBeInTheDocument()
    expect(within(rows[1]).getByText("90%")).toBeInTheDocument()
    expect(within(rows[1]).getByText("80%")).toBeInTheDocument()

    // LLM Fine-tuning (row 2): relevance 72%, strategic 60%, tactical 85%
    expect(within(rows[2]).getByText("72%")).toBeInTheDocument()

    // Edge AI Deployment (row 3): relevance 45%
    expect(within(rows[3]).getByText("45%")).toBeInTheDocument()
  })
})
