import { existsSync } from "node:fs";

import { defineConfig, devices } from "@playwright/test";

/**
 * The environment ships a Chromium build that may not match the one this
 * Playwright version would download, and downloading is disabled here. Point
 * at the installed binary when it exists, and otherwise let Playwright resolve
 * its own, so this config still works on a developer machine.
 */
const INSTALLED = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const executablePath = existsSync(INSTALLED) ? INSTALLED : undefined;

/**
 * The atlas is a single self-contained file opened from disk, not a page the
 * dev server serves, so this config deliberately starts no web server. Running
 * it under the main config would boot Vite for a test that never talks to it.
 */
export default defineConfig({
  testDir: "./tests/atlas",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? "line" : "list",
  use: { ...devices["Desktop Chrome"], launchOptions: { executablePath } },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], launchOptions: { executablePath } },
    },
  ],
});
