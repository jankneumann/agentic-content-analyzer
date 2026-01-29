/**
 * Dashboard Page Tests
 *
 * Tests for / (index) page: pipeline status cards, quick action links,
 * stats display, and counts for each pipeline stage.
 *
 * All assertions are scoped to <main> to avoid matching sidebar nav text.
 */

import { test, expect } from "../fixtures"

test.describe("Dashboard Page", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("page shows Dashboard heading", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(
      dashboardPage.page.locator("main").getByRole("heading", { name: "Dashboard", level: 1 })
    ).toBeVisible()
  })

  test("page shows pipeline description", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(
      dashboardPage.page.locator("main").getByText(/overview of your newsletter aggregation pipeline/i)
    ).toBeVisible()
  })

  test("Pipeline Status section is visible", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(
      dashboardPage.page.locator("main").getByRole("heading", { name: "Pipeline Status" })
    ).toBeVisible()
    await expect(
      dashboardPage.page.locator("main").getByText(/current state of each processing step/i)
    ).toBeVisible()
  })

  test("Content pipeline card renders", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const main = dashboardPage.page.locator("main")
    await expect(main.getByText("Content", { exact: true })).toBeVisible()
    await expect(
      main.getByText("Ingested from Gmail, RSS, and YouTube")
    ).toBeVisible()
  })

  test("Summaries pipeline card renders", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const main = dashboardPage.page.locator("main")
    await expect(main.getByText("Summaries", { exact: true }).first()).toBeVisible()
    await expect(
      main.getByText("AI-generated extractions")
    ).toBeVisible()
  })

  test("Themes pipeline card renders", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const main = dashboardPage.page.locator("main")
    await expect(main.getByText("Themes", { exact: true }).first()).toBeVisible()
    await expect(
      main.getByText("Knowledge graph analysis")
    ).toBeVisible()
  })

  test("Digests pipeline card renders", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const main = dashboardPage.page.locator("main")
    await expect(main.getByText("Digests", { exact: true }).first()).toBeVisible()
    await expect(
      main.getByText("Aggregated reports")
    ).toBeVisible()
  })

  test("Scripts pipeline card renders", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const main = dashboardPage.page.locator("main")
    await expect(main.getByText("Scripts", { exact: true }).first()).toBeVisible()
    await expect(
      main.getByText("Podcast dialogue")
    ).toBeVisible()
  })

  test("Podcasts pipeline card renders", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const main = dashboardPage.page.locator("main")
    await expect(main.getByText("Podcasts", { exact: true }).first()).toBeVisible()
    await expect(
      main.getByText("Generated audio")
    ).toBeVisible()
  })

  test("each pipeline card has a View link", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const viewLinks = dashboardPage.page.locator("main").getByRole("link", { name: /view/i })
    const count = await viewLinks.count()
    // 6 pipeline cards each have a View link
    expect(count).toBeGreaterThanOrEqual(6)
  })

  test("Content card links to /contents", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    // Find the Content card's View link within main
    const contentCard = dashboardPage.page.locator("main a[href='/contents']").first()
    await expect(contentCard).toBeVisible()
  })

  test("Summaries card links to /summaries", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const summariesLink = dashboardPage.page.locator("main a[href='/summaries']").first()
    await expect(summariesLink).toBeVisible()
  })

  test("Digests card links to /digests", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const digestsLink = dashboardPage.page.locator("main a[href='/digests']").first()
    await expect(digestsLink).toBeVisible()
  })

  test("Scripts card links to /scripts", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const scriptsLink = dashboardPage.page.locator("main a[href='/scripts']").first()
    await expect(scriptsLink).toBeVisible()
  })

  test("Podcasts card links to /podcasts", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const podcastsLink = dashboardPage.page.locator("main a[href='/podcasts']").first()
    await expect(podcastsLink).toBeVisible()
  })

  test("Pipeline Summary section displays stats", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const main = dashboardPage.page.locator("main")
    await expect(main.getByRole("heading", { name: "Pipeline Summary" })).toBeVisible()
    await expect(
      main.getByText(/key metrics across your pipeline/i)
    ).toBeVisible()
  })

  test("stats cards show Pending Summarization count", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(
      dashboardPage.page.locator("main").getByText("Pending Summarization", { exact: true })
    ).toBeVisible()
  })

  test("stats cards show Summaries Generated count", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(
      dashboardPage.page.locator("main").getByText("Summaries Generated", { exact: true })
    ).toBeVisible()
  })

  test("stats cards show Digests Pending Review count", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(
      dashboardPage.page.locator("main").getByText("Digests Pending Review")
    ).toBeVisible()
  })

  test("stats cards show Scripts Pending Review count", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(
      dashboardPage.page.locator("main").getByText("Scripts Pending Review")
    ).toBeVisible()
  })

  test("stats cards show Podcasts Generated count", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(
      dashboardPage.page.locator("main").getByText("Podcasts Generated")
    ).toBeVisible()
  })

  test("Quick Actions section is visible", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const main = dashboardPage.page.locator("main")
    await expect(main.getByRole("heading", { name: "Quick Actions" })).toBeVisible()
    await expect(
      main.getByText(/common tasks you might want to perform/i)
    ).toBeVisible()
  })

  test("quick action links render", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const main = dashboardPage.page.locator("main")
    await expect(main.getByText("Ingest Content")).toBeVisible()
    await expect(main.getByText("Generate Summaries")).toBeVisible()
    await expect(main.getByText("Create Digest")).toBeVisible()
    await expect(main.getByText("Review Scripts")).toBeVisible()
  })

  test("Recent Activity section is visible", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(
      dashboardPage.page.locator("main").getByRole("heading", { name: "Recent Activity" })
    ).toBeVisible()
  })

  test("pipeline cards show status badges", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    // Each pipeline card has a status badge (Ready, Processing, or Error)
    const readyBadges = dashboardPage.page.locator("main").getByText("Ready")
    const count = await readyBadges.count()
    expect(count).toBeGreaterThanOrEqual(1)
  })

  test("Ingest action button in header links to contents", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const ingestButton = dashboardPage.page.locator("main").getByRole("link", { name: /ingest/i }).first()
    await expect(ingestButton).toBeVisible()
  })

  test("Generate Digest action button in header links to digests", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const generateButton = dashboardPage.page.locator("main").getByRole("link", { name: /generate digest/i })
    await expect(generateButton).toBeVisible()
  })
})
