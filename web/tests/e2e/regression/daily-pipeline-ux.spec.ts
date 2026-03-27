/**
 * Regression: Daily Pipeline UX Workflow
 *
 * Verifies the full daily pipeline workflow through the web UX:
 *   1. Dashboard shows pipeline stages
 *   2. Content page shows ingested items
 *   3. Summaries page shows generated summaries
 *   4. Themes page shows analysis results
 *   5. Digests page shows generated digest
 *   6. Digest can be reviewed/approved
 *   7. Scripts page shows generated script
 *   8. Script can be approved
 *   9. Podcasts page shows generated podcast
 *
 * These tests use stateful mocks that evolve as the pipeline progresses,
 * catching regressions where UI pages break after upstream pipeline changes.
 */

import { test, expect } from "../fixtures"
import { WorkflowState, setupDailyPipelineWorkflow } from "./workflow-mocks"

test.describe("Daily Pipeline UX Workflow @regression", () => {
  let state: WorkflowState

  test.beforeEach(async ({ page }) => {
    state = new WorkflowState()
    await setupDailyPipelineWorkflow(page, state)
  })

  // ─── Stage 1: Dashboard Overview ──────────────────────────

  test("dashboard loads with pipeline stage cards", async ({
    dashboardPage,
  }) => {
    state.advance("content_ingested")
    await dashboardPage.navigate()

    // Dashboard should render pipeline cards for the main stages
    await expect(dashboardPage.statsSection).toBeVisible()
    // At minimum, the main content area should load without errors
    await expect(dashboardPage.page.locator("main")).toBeVisible()
  })

  // ─── Stage 2: Content Ingestion ───────────────────────────

  test("content page shows ingested items after ingestion", async ({
    contentsPage,
  }) => {
    state.advance("content_ingested")
    await contentsPage.navigate()

    await expect(contentsPage.table).toBeVisible()
    const rowCount = await contentsPage.getRowCount()
    expect(rowCount).toBe(3)

    // Verify content titles are visible
    await expect(
      contentsPage.page.getByText("AI Weekly: GPT-5 Announced")
    ).toBeVisible()
    await expect(
      contentsPage.page.getByText("ML Ops Digest: Kubernetes for ML")
    ).toBeVisible()
  })

  test("content page shows empty state before ingestion", async ({
    contentsPage,
  }) => {
    // state is "empty" — no content ingested yet
    await contentsPage.navigate()

    // Should show empty state or zero rows
    const rowCount = await contentsPage.getRowCount()
    expect(rowCount).toBe(0)
  })

  // ─── Stage 3: Summarization ───────────────────────────────

  test("summaries page shows items after summarization", async ({
    summariesPage,
  }) => {
    state.advance("content_summarized")
    await summariesPage.navigate()

    await expect(summariesPage.table).toBeVisible()
    const rowCount = await summariesPage.getRowCount()
    expect(rowCount).toBe(3)
  })

  test("summaries page is empty before summarization", async ({
    summariesPage,
  }) => {
    state.advance("content_ingested") // Content exists but not yet summarized
    await summariesPage.navigate()

    const rowCount = await summariesPage.getRowCount()
    expect(rowCount).toBe(0)
  })

  // ─── Stage 4: Theme Analysis ──────────────────────────────

  test("themes page shows analysis after theme analysis", async ({
    themesPage,
  }) => {
    state.advance("themes_analyzed")
    await themesPage.navigate()

    // Should not show empty state
    await expect(themesPage.emptyState).not.toBeVisible()
    // Main content area should have theme data
    await expect(themesPage.themeList).toBeVisible()
  })

  test("themes page shows empty state before analysis", async ({
    themesPage,
  }) => {
    state.advance("content_summarized") // Summaries exist but no theme analysis
    await themesPage.navigate()

    // Should show empty or "no analysis" state
    // The analyze button should still be available
    await expect(themesPage.analyzeButton).toBeVisible()
  })

  // ─── Stage 5: Digest Generation ──────────────────────────

  test("digests page shows digest after generation", async ({
    digestsPage,
  }) => {
    state.advance("digest_generated")
    await digestsPage.navigate()

    const rowCount = await digestsPage.getRowCount()
    expect(rowCount).toBe(1)

    // Verify the digest title and status
    await expect(
      digestsPage.page.getByText("Daily AI & Data Digest - Regression Test")
    ).toBeVisible()
  })

  test("digests page is empty before generation", async ({
    digestsPage,
  }) => {
    state.advance("themes_analyzed")
    await digestsPage.navigate()

    const rowCount = await digestsPage.getRowCount()
    expect(rowCount).toBe(0)
  })

  test("digest detail shows sections and content", async ({
    digestsPage,
    page,
  }) => {
    state.advance("digest_generated")
    await digestsPage.navigate()

    // Click on the digest row to view details
    await digestsPage.clickTableRow(0)

    // Digest detail should show key sections
    await expect(
      page.getByText(/strategic insight|technical development|emerging trend/i)
        .first()
    ).toBeVisible()
  })

  // ─── Stage 6: Digest Review ──────────────────────────────

  test("digest shows PENDING_REVIEW status before approval", async ({
    digestsPage,
  }) => {
    state.advance("digest_generated") // Generated but not reviewed
    await digestsPage.navigate()

    await expect(
      digestsPage.page.getByText(/pending.review/i).first()
    ).toBeVisible()
  })

  test("digest shows APPROVED status after review", async ({
    digestsPage,
  }) => {
    state.advance("digest_reviewed")
    await digestsPage.navigate()

    await expect(
      digestsPage.page.getByText(/approved/i).first()
    ).toBeVisible()
  })

  // ─── Stage 7: Script Generation ──────────────────────────

  test("scripts page shows script after generation", async ({
    scriptsPage,
  }) => {
    state.advance("script_generated")
    await scriptsPage.navigate()

    const rowCount = await scriptsPage.getRowCount()
    expect(rowCount).toBe(1)
  })

  test("scripts page is empty before script generation", async ({
    scriptsPage,
  }) => {
    state.advance("digest_reviewed")
    await scriptsPage.navigate()

    const rowCount = await scriptsPage.getRowCount()
    expect(rowCount).toBe(0)
  })

  // ─── Stage 8: Script Approval ─────────────────────────────

  test("script shows pending_review status before approval", async ({
    scriptsPage,
  }) => {
    state.advance("script_generated")
    await scriptsPage.navigate()

    await expect(
      scriptsPage.page.getByText(/pending.review/i).first()
    ).toBeVisible()
  })

  test("script shows approved status after approval", async ({
    scriptsPage,
  }) => {
    state.advance("script_approved")
    await scriptsPage.navigate()

    await expect(
      scriptsPage.page.getByText(/approved/i).first()
    ).toBeVisible()
  })

  // ─── Stage 9: Podcast Generation ──────────────────────────

  test("podcasts page shows podcast after generation", async ({
    podcastsPage,
  }) => {
    state.advance("podcast_generated")
    await podcastsPage.navigate()

    const rowCount = await podcastsPage.getRowCount()
    expect(rowCount).toBe(1)

    await expect(
      podcastsPage.page.getByText(/completed/i).first()
    ).toBeVisible()
  })

  test("podcasts page is empty before podcast generation", async ({
    podcastsPage,
  }) => {
    state.advance("script_approved")
    await podcastsPage.navigate()

    const rowCount = await podcastsPage.getRowCount()
    expect(rowCount).toBe(0)
  })
})

// ─── Cross-Page Navigation Workflow ─────────────────────────

test.describe("Daily Pipeline Cross-Page Navigation @regression", () => {
  let state: WorkflowState

  test.beforeEach(async ({ page }) => {
    state = new WorkflowState()
    await setupDailyPipelineWorkflow(page, state)
    // Set up a fully completed pipeline
    state.advance("podcast_generated")
  })

  test("can navigate through all pipeline stages via sidebar", async ({
    basePage,
    page,
  }) => {
    // Start at dashboard
    await basePage.goto("/")
    await expect(page.locator("main")).toBeVisible()

    // Navigate to Content
    await basePage.navLinks.content.click()
    await expect(page.locator("main")).toBeVisible()
    await expect(page.locator("tbody tr")).toHaveCount(3)

    // Navigate to Summaries
    await basePage.navLinks.summaries.click()
    await expect(page.locator("main")).toBeVisible()
    await expect(page.locator("tbody tr")).toHaveCount(3)

    // Navigate to Themes
    await basePage.navLinks.themes.click()
    await expect(page.locator("main")).toBeVisible()

    // Navigate to Digests
    await basePage.navLinks.digests.click()
    await expect(page.locator("main")).toBeVisible()
    await expect(page.locator("tbody tr")).toHaveCount(1)

    // Navigate to Scripts
    await basePage.navLinks.scripts.click()
    await expect(page.locator("main")).toBeVisible()
    await expect(page.locator("tbody tr")).toHaveCount(1)

    // Navigate to Podcasts
    await basePage.navLinks.podcasts.click()
    await expect(page.locator("main")).toBeVisible()
    await expect(page.locator("tbody tr")).toHaveCount(1)
  })

  test("each page loads without JS errors during navigation", async ({
    basePage,
    page,
  }) => {
    const jsErrors: string[] = []
    page.on("pageerror", (err) => jsErrors.push(err.message))

    await basePage.goto("/")
    await basePage.navLinks.content.click()
    await page.waitForLoadState("domcontentloaded")
    await basePage.navLinks.summaries.click()
    await page.waitForLoadState("domcontentloaded")
    await basePage.navLinks.themes.click()
    await page.waitForLoadState("domcontentloaded")
    await basePage.navLinks.digests.click()
    await page.waitForLoadState("domcontentloaded")
    await basePage.navLinks.scripts.click()
    await page.waitForLoadState("domcontentloaded")
    await basePage.navLinks.podcasts.click()
    await page.waitForLoadState("domcontentloaded")

    expect(jsErrors).toEqual([])
  })
})

// ─── State Transition Consistency ───────────────────────────

test.describe("Pipeline State Transitions @regression", () => {
  let state: WorkflowState

  test.beforeEach(async ({ page }) => {
    state = new WorkflowState()
    await setupDailyPipelineWorkflow(page, state)
  })

  test("content stats update after ingestion", async ({ page }) => {
    // Before ingestion: 0 content
    state.advance("empty")
    await page.goto("/contents")
    let rowCount = await page.locator("tbody tr").count()
    expect(rowCount).toBe(0)

    // After ingestion: 3 content items
    state.advance("content_ingested")
    await page.goto("/contents")
    rowCount = await page.locator("tbody tr").count()
    expect(rowCount).toBe(3)
  })

  test("digest status transitions from PENDING_REVIEW to APPROVED", async ({
    page,
  }) => {
    // Generated but not reviewed
    state.advance("digest_generated")
    await page.goto("/digests")
    await expect(page.getByText(/pending.review/i).first()).toBeVisible()

    // After review
    state.advance("digest_reviewed")
    await page.goto("/digests")
    await expect(page.getByText(/approved/i).first()).toBeVisible()
  })

  test("script becomes available only after digest is reviewed", async ({
    page,
  }) => {
    // Digest generated but not reviewed — no scripts yet
    state.advance("digest_generated")
    await page.goto("/scripts")
    let rowCount = await page.locator("tbody tr").count()
    expect(rowCount).toBe(0)

    // After digest review and script generation
    state.advance("script_generated")
    await page.goto("/scripts")
    rowCount = await page.locator("tbody tr").count()
    expect(rowCount).toBe(1)
  })

  test("podcast becomes available only after script is approved", async ({
    page,
  }) => {
    // Script generated but not approved — no podcasts
    state.advance("script_generated")
    await page.goto("/podcasts")
    let rowCount = await page.locator("tbody tr").count()
    expect(rowCount).toBe(0)

    // After script approval and podcast generation
    state.advance("podcast_generated")
    await page.goto("/podcasts")
    rowCount = await page.locator("tbody tr").count()
    expect(rowCount).toBe(1)
  })
})
