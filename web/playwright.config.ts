import { defineConfig, devices } from "@playwright/test"

/**
 * Playwright E2E Test Configuration
 *
 * Projects:
 * - chromium, Mobile Chrome, Mobile Safari: Default test suite (API mocked)
 * - smoke: Integration tests requiring a real backend (excluded from default run)
 *
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  testDir: "./tests/e2e",
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI */
  workers: process.env.CI ? 1 : undefined,
  /* Reporter to use */
  reporter: [["html", { open: "never" }], ["list"]],
  /* Global test timeout */
  timeout: 30_000,
  /* Shared settings for all the projects below */
  use: {
    /* Base URL to use in actions like `await page.goto('/')` */
    baseURL: "http://localhost:5173",
    /* Timeout for individual actions (click, fill, etc.) */
    actionTimeout: 10_000,
    /* Collect trace when retrying the failed test */
    trace: "on-first-retry",
    /* Screenshot on failure */
    screenshot: "only-on-failure",
    /* Record video on CI for debugging failures */
    video: process.env.CI ? "on-first-retry" : "off",
  },
  /* Expect timeout */
  expect: {
    timeout: 5_000,
  },

  /* Configure projects for major browsers, mobile devices, and smoke tests */
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      grepInvert: /@smoke/,
    },
    {
      name: "Mobile Chrome",
      use: { ...devices["Pixel 7"] },
      grepInvert: /@smoke/,
    },
    {
      name: "Mobile Safari",
      use: { ...devices["iPhone 14"] },
      grepInvert: /@smoke/,
    },
    {
      name: "smoke",
      use: { ...devices["Desktop Chrome"] },
      grep: /@smoke/,
      testDir: "./tests/e2e/smoke",
    },
  ],

  /* Run your local dev server before starting the tests */
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
})
