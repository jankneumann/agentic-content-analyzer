/**
 * Digest Follow-Up Prompts E2E Tests
 *
 * Tests that follow-up prompts render in the digest detail dialog,
 * can be expanded via collapsible trigger, and have working copy buttons.
 */

import { test, expect } from "../fixtures"
import { createDigestDetail } from "../fixtures/mock-data"

test.describe("Digest Follow-Up Prompts", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockDigestDetail()
  })

  async function openDigestDialog(digestsPage: Awaited<ReturnType<typeof test.info>["fixme"]> extends never ? any : any) {
    await digestsPage.navigate()
    const viewButton = digestsPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view digest/i })
    await viewButton.click()
    const dialog = digestsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()
    return dialog
  }

  test("shows follow-up prompts trigger in strategic insights section", async ({
    digestsPage,
  }) => {
    const dialog = await openDigestDialog(digestsPage)

    // Strategic tab is active by default — expand the first section
    const sectionTitle = dialog.getByText("GPT-5 Changes Enterprise AI Landscape")
    await expect(sectionTitle).toBeVisible()

    // Look for the follow-up prompts trigger button
    const promptsTrigger = dialog.getByRole("button", {
      name: /follow-up prompts \(2\)/i,
    })
    await expect(promptsTrigger).toBeVisible()
  })

  test("expands follow-up prompts on click and shows prompt text", async ({
    digestsPage,
  }) => {
    const dialog = await openDigestDialog(digestsPage)

    // Click the follow-up prompts trigger to expand
    const promptsTrigger = dialog.getByRole("button", {
      name: /follow-up prompts \(2\)/i,
    })
    await promptsTrigger.click()

    // Should show the prompt text from mock data
    await expect(
      dialog.getByText(/analyze how this changes the build-vs-buy decision/i)
    ).toBeVisible()
    await expect(
      dialog.getByText(/Compare the enterprise AI strategies/i)
    ).toBeVisible()
  })

  test("shows copy button on prompt hover", async ({ digestsPage }) => {
    const dialog = await openDigestDialog(digestsPage)

    // Expand follow-up prompts
    const promptsTrigger = dialog.getByRole("button", {
      name: /follow-up prompts \(2\)/i,
    })
    await promptsTrigger.click()

    // Copy buttons should exist (they have title="Copy prompt")
    const copyButtons = dialog.getByRole("button", { name: /copy prompt/i })
    // Should have 2 copy buttons (one per prompt)
    await expect(copyButtons).toHaveCount(2)
  })

  test("technical tab shows follow-up prompts", async ({ digestsPage }) => {
    const dialog = await openDigestDialog(digestsPage)

    // Switch to Technical tab
    await dialog.getByRole("tab", { name: /technical/i }).click()

    // Technical section has 1 follow-up prompt in mock data
    const promptsTrigger = dialog.getByRole("button", {
      name: /follow-up prompts \(1\)/i,
    })
    await expect(promptsTrigger).toBeVisible()

    // Expand and verify content
    await promptsTrigger.click()
    await expect(
      dialog.getByText(/Mixture-of-Experts vs dense transformer/i)
    ).toBeVisible()
  })

  test("trends tab shows follow-up prompts", async ({ digestsPage }) => {
    const dialog = await openDigestDialog(digestsPage)

    // Switch to Trends tab
    await dialog.getByRole("tab", { name: /trends/i }).click()

    // Emerging trends section has 1 follow-up prompt in mock data
    const promptsTrigger = dialog.getByRole("button", {
      name: /follow-up prompts \(1\)/i,
    })
    await expect(promptsTrigger).toBeVisible()

    // Expand and verify content
    await promptsTrigger.click()
    await expect(
      dialog.getByText(/brief for engineering leadership/i)
    ).toBeVisible()
  })

  test("does not show follow-up prompts when section has none", async ({
    digestsPage,
    apiMocks,
  }) => {
    // Override with digest that has no follow-up prompts
    await apiMocks.mockDigestDetail(
      createDigestDetail({
        strategic_insights: [
          {
            title: "AI Trends Overview",
            summary: "Summary without prompts.",
            details: ["Detail 1"],
            themes: ["AI"],
            continuity: null,
            followup_prompts: [],
          },
        ],
      })
    )

    const dialog = await openDigestDialog(digestsPage)

    // Should show the section title
    await expect(dialog.getByText("AI Trends Overview")).toBeVisible()

    // Should NOT show follow-up prompts trigger
    const promptsTrigger = dialog.getByRole("button", {
      name: /follow-up prompts/i,
    })
    await expect(promptsTrigger).toHaveCount(0)
  })
})
