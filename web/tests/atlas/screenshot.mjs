import { chromium } from "@playwright/test";
const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
const [src, ...pairs] = process.argv.slice(2);
for (const pair of pairs) {
  const [mode, out] = pair.split("=");
  // A hash-only navigation does not reload, so the page would never re-read
  // its state. Go somewhere else first.
  await page.goto("about:blank");
  await page.goto(`file://${src}#mode=${mode}`, { waitUntil: "load", timeout: 180000 });
  await page.waitForSelector("#color-chips button", { timeout: 90000 });
  await page.waitForTimeout(7000);
  await page.screenshot({ path: out });
  console.log("captured", mode, "->", out);
}
await browser.close();
