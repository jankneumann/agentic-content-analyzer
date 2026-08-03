import AxeBuilder from "@axe-core/playwright"
import { test, expect } from "./fixtures"

const SOURCE_KEYS = [
  "gmail", "rss", "blog", "substack", "youtube_playlist", "youtube_rss",
  "podcast", "x_search", "perplexity_search", "files", "url", "scholar_search",
  "scholar_paper", "scholar_references", "arxiv_search", "arxiv_paper",
  "huggingface_papers", "readwise",
  "obsidian_vault",
]

const operation = {
  schema_version: 2,
  operation_id: "op-1",
  operation_type: "digest.create",
  status: "completed",
  progress: 100,
  message: "Digest ready",
  cancellable: false,
  retry_count: 0,
  status_url: "/api/v1/operations/op-1",
  events_url: "/api/v1/operations/op-1/events",
  resource: { type: "digest", id: "42", url: "https://api.invalid/private/digests/42" },
  created_at: "2026-07-16T12:00:00Z",
  completed_at: "2026-07-16T12:01:00Z",
}

test("canonical workflow surface is responsive and agent-contract driven", async ({ page }, testInfo) => {
  const requests: Array<Record<string, unknown>> = []
  await page.route("**/api/v1/**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }))
  await page.route(/\/api\/v1\/operations(?:\?.*)?$/, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: [operation], next_cursor: null }) }))
  await page.route(/\/api\/v1\/capabilities(?:\?.*)?$/, (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      contract_version: "2.0.0",
      source_commands: SOURCE_KEYS.map((key) => ({
        key,
        display_name: key.replaceAll("_", " "),
        emitted_sources: [key === "url" ? "webpage" : key],
        scheduled: !["files", "url", "scholar_paper", "arxiv_paper"].includes(key),
        supports_force: true,
        supports_date_range: false,
        supports_preview: false,
        requires_identifier: key.endsWith("paper"),
        transports: ["frontend"],
        fields: key === "url" ? [
            { name: "kind", type: "string", required: true, enum: ["url"] },
            { name: "configured_sources", type: "array", required: false },
            { name: "url", type: "string", format: "uri", required: true },
            { name: "notes", type: "string", required: false },
          ] : key === "obsidian_vault" ? [
            { name: "kind", type: "string", required: true, enum: ["obsidian_vault"] },
            { name: "configured_sources", type: "array", required: false },
            { name: "configured_source_version", type: "string", required: false },
            { name: "source_key", type: "string", required: true },
            { name: "max_items", type: "integer", required: false, constraints: { minimum: 1, maximum: 10000 } },
            { name: "force_reprocess", type: "boolean", required: false, default: false },
          ] : [],
      })),
      operation_types: ["ingestion.execute", "pipeline.run"],
      resource_types: ["digest"],
      next_cursor: null,
    }),
  }))
  await page.route(/\/api\/v1\/configured-sources(?:\?.*)?$/, (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      data: [
        {
          key: "src_11111111111111111111",
          command_key: "obsidian_vault",
          source_type: "obsidian_vault",
          name: null,
          enabled: true,
          origin: "db",
          configuration: { type: "obsidian_vault" },
          ready: true,
          readiness_code: null,
        },
        {
          key: "src_22222222222222222222",
          command_key: "obsidian_vault",
          source_type: "obsidian_vault",
          name: null,
          enabled: true,
          origin: "db",
          configuration: { type: "obsidian_vault" },
          ready: false,
          readiness_code: "source_unavailable",
        },
      ],
      next_cursor: null,
    }),
  }))
  await page.route("**/api/v1/ingestions", async (route) => {
    requests.push(await route.request().postDataJSON())
    await route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ ...operation, operation_id: "op-ingest", operation_type: "ingestion.execute", status: "queued", progress: 0, resource: null, completed_at: null }) })
  })
  await page.route("**/api/v1/pipeline-runs", async (route) => {
    requests.push(await route.request().postDataJSON())
    await route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ ...operation, operation_id: "op-pipeline", operation_type: "pipeline.run", status: "queued", progress: 0, resource: null, completed_at: null }) })
  })

  await page.goto("/ingest")
  await expect(page.getByRole("heading", { name: "Ingestion" })).toBeVisible()
  await page.getByRole("combobox", { name: "Source" }).click()
  await expect(page.getByRole("option")).toHaveCount(19)
  await page.getByRole("option", { name: "url", exact: true }).click()
  await expect(page.getByLabel("URL *")).toBeVisible()
  await expect(page.getByText("Configured Sources")).toHaveCount(0)
  await page.getByLabel("URL *").fill("https://example.com/article")
  await page.getByLabel("Notes").fill("Review for the weekly digest")
  await page.getByRole("button", { name: "Run", exact: true }).click()
  await expect.poll(() => requests.length).toBe(1)
  expect(requests[0]).toEqual({ kind: "url", url: "https://example.com/article", notes: "Review for the weekly digest" })

  await page.getByRole("combobox", { name: "Source" }).click()
  await page.getByRole("option", { name: "obsidian vault", exact: true }).click()
  await expect(page.getByLabel("Configured source *")).toContainText(
    "src_11111111111111111111"
  )
  await page.getByLabel("Configured source *").click()
  await expect(
    page.getByRole("option", {
      name: "src_22222222222222222222 — source_unavailable",
    })
  ).toBeDisabled()
  await page.keyboard.press("Escape")
  await expect(
    page.getByText(
      /vault_path|ingest_folder|private-vault|configured_source_version|configured_sources/i
    )
  ).toHaveCount(0)
  await page.getByRole("button", { name: "Run", exact: true }).click()
  await expect.poll(() => requests.length).toBe(2)
  expect(requests[1]).toEqual({
    kind: "obsidian_vault",
    source_key: "src_11111111111111111111",
    force_reprocess: false,
  })
  expect(requests[1]).not.toHaveProperty("configured_sources")
  expect(requests[1]).not.toHaveProperty("configured_source_version")
  expect(JSON.stringify(requests[1])).not.toMatch(/vault_path|ingest_folder/)

  await page.getByRole("button", { name: "Run pipeline" }).click()
  await expect.poll(() => requests.length).toBe(3)
  expect(requests[2]).not.toHaveProperty("sources")

  await page.getByRole("button", { name: "Toggle operations" }).click()
  await expect(page.getByText("Digest ready").first()).toBeVisible()
  await page.getByRole("button", { name: "Open result" }).first().click()
  await expect(page).toHaveURL(/\/review\/digest\/42$/)

  await page.goto("/ingest")
  const accessibility = await new AxeBuilder({ page }).analyze()
  expect(accessibility.violations).toEqual([])
  await page.screenshot({ path: testInfo.outputPath("workflow-surface.png"), fullPage: true })
})
