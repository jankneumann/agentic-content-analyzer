/**
 * Capture the atlas at a given view, for reviewing a rendering change by eye.
 *
 * Not a test: the assertions live in atlas.spec.ts. This exists because a
 * canvas renderer is one of the few things a screenshot judges better than an
 * assertion, and regenerating one by hand each time is the reason nobody does.
 *
 *   node tests/atlas/screenshot.mjs <page.html> "<hash>=<out.png>" ...
 *   node tests/atlas/screenshot.mjs /tmp/atlas.html "mode=coverage=/tmp/cov.png"
 */

import { chromium } from "@playwright/test";

const INSTALLED = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const browser = await chromium.launch({ executablePath: INSTALLED });
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });

const [source, ...captures] = process.argv.slice(2);
for (const capture of captures) {
  const at = capture.lastIndexOf("=");
  const hash = capture.slice(0, at);
  const out = capture.slice(at + 1);

  // A hash-only navigation does not reload, so the page would never re-read
  // its state; go somewhere else first.
  await page.goto("about:blank");
  await page.goto(`file://${source}#${hash}`, { waitUntil: "load", timeout: 180000 });
  await page.waitForSelector("#color-chips button", { timeout: 90000 });
  await page.waitForTimeout(8000);
  await page.screenshot({ path: out });
  console.log(`captured #${hash} -> ${out}`);
}

await browser.close();
