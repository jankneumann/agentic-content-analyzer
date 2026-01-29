/**
 * Dashboard Page Tests
 *
 * Tests for / (index) page: pipeline status cards, quick action links,
 * stats display, and counts for each pipeline stage.
 */

import { test, expect } from "../../fixtures"

test.describe("Dashboard Page", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("page shows Dashboard heading", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(dashboardPage.page.getByText("Dashboard")).toBeVisible()
  })

  test("page shows pipeline description", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(
      dashboardPage.page.getByText(/overview of your newsletter aggregation pipeline/i)
    ).toBeVisible()
  })

  test("Pipeline Status section is visible", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(dashboardPage.page.getByText("Pipeline Status")).toBeVisible()
    await expect(
      dashboardPage.page.getByText(/current state of each processing step/i)
    ).toBeVisible()
  })

  test("Content pipeline card renders", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(dashboardPage.page.getByText("Content")).toBeVisible()
    await expect(
      dashboardPage.page.getByText("Ingested from Gmail, RSS, and YouTube")
    ).toBeVisible()
  })

  test("Summaries pipeline card renders", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(dashboardPage.page.getByText("Summaries")).toBeVisible()
    await expect(
      dashboardPage.page.getByText("AI-generated extractions")
    ).toBeVisible()
  })

  test("Themes pipeline card renders", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(dashboardPage.page.getByText("Themes")).toBeVisible()
    await expect(
      dashboardPage.page.getByText("Knowledge graph analysis")
    ).toBeVisible()
  })

  test("Digests pipeline card renders", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(dashboardPage.page.getByText("Digests")).toBeVisible()
    await expect(
      dashboardPage.page.getByText("Aggregated reports")
    ).toBeVisible()
  })

  test("Scripts pipeline card renders", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(dashboardPage.page.getByText("Scripts")).toBeVisible()
    await expect(
      dashboardPage.page.getByText("Podcast dialogue")
    ).toBeVisible()
  })

  test("Podcasts pipeline card renders", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(dashboardPage.page.getByText("Podcasts")).toBeVisible()
    await expect(
      dashboardPage.page.getByText("Generated audio")
    ).toBeVisible()
  })

  test("each pipeline card has a View link", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const viewLinks = dashboardPage.page.getByRole("link", { name: /view/i })
    const count = await viewLinks.count()
    // 6 pipeline cards each have a View link
    expect(count).toBeGreaterThanOrEqual(6)
  })

  test("Content card links to /contents", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    // Find the Content card's View link
    const contentCard = dashboardPage.page.locator("a[href='/contents']").first()
    await expect(contentCard).toBeVisible()
  })

  test("Summaries card links to /summaries", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const summariesLink = dashboardPage.page.locator("a[href='/summaries']").first()
    await expect(summariesLink).toBeVisible()
  })

  test("Digests card links to /digests", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const digestsLink = dashboardPage.page.locator("a[href='/digests']").first()
    await expect(digestsLink).toBeVisible()
  })

  test("Scripts card links to /scripts", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const scriptsLink = dashboardPage.page.locator("a[href='/scripts']").first()
    await expect(scriptsLink).toBeVisible()
  })

  test("Podcasts card links to /podcasts", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const podcastsLink = dashboardPage.page.locator("a[href='/podcasts']").first()
    await expect(podcastsLink).toBeVisible()
  })

  test("Pipeline Summary section displays stats", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(dashboardPage.page.getByText("Pipeline Summary")).toBeVisible()
    await expect(
      dashboardPage.page.getByText(/key metrics across your pipeline/i)
    ).toBeVisible()
  })

  test("stats cards show Pending Summarization count", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(
      dashboardPage.page.getByText("Pending Summarization")
    ).toBeVisible()
  })

  test("stats cards show Summaries Generated count", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(
      dashboardPage.page.getByText("Summaries Generated")
    ).toBeVisible()
  })

  test("stats cards show Digests Pending Review count", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(
      dashboardPage.page.getByText("Digests Pending Review")
    ).toBeVisible()
  })

  test("stats cards show Scripts Pending Review count", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(
      dashboardPage.page.getByText("Scripts Pending Review")
    ).toBeVisible()
  })

  test("stats cards show Podcasts Generated count", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(
      dashboardPage.page.getByText("Podcasts Generated")
    ).toBeVisible()
  })

  test("Quick Actions section is visible", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(dashboardPage.page.getByText("Quick Actions")).toBeVisible()
    await expect(
      dashboardPage.page.getByText(/common tasks you might want to perform/i)
    ).toBeVisible()
  })

  test("quick action links render", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(dashboardPage.page.getByText("Ingest Content")).toBeVisible()
    await expect(dashboardPage.page.getByText("Generate Summaries")).toBeVisible()
    await expect(dashboardPage.page.getByText("Create Digest")).toBeVisible()
    await expect(dashboardPage.page.getByText("Review Scripts")).toBeVisible()
  })

  test("Recent Activity section is visible", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    await expect(dashboardPage.page.getByText("Recent Activity")).toBeVisible()
  })

  test("pipeline cards show status badges", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    // Each pipeline card has a status badge (Ready, Processing, or Error)
    const readyBadges = dashboardPage.page.getByText("Ready")
    const count = await readyBadges.count()
    expect(count).toBeGreaterThanOrEqual(1)
  })

  test("Ingest action button in header links to contents", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const ingestButton = dashboardPage.page.getByRole("link", { name: /ingest/i }).first()
    await expect(ingestButton).toBeVisible()
  })

  test("Generate Digest action button in header links to digests", async ({ dashboardPage }) => {
    await dashboardPage.navigate()

    const generateButton = dashboardPage.page.getByRole("link", { name: /generate digest/i })
    await expect(generateButton).toBeVisible()
  })
})
