/**
 * The atlas in a real browser.
 *
 * The page has no build step and no server, so these tests build it from a
 * small fixture graph and open the file. What they check is the behaviour that
 * cannot be asserted from the view-model: that a colour mode reaches the
 * canvas, that hiding test files removes nodes, that a pasted URL restores a
 * view, and that none of it moves a node the reader did not drag.
 */

import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const REPO = resolve(import.meta.dirname, "..", "..", "..");
const SKILL = join(REPO, ".claude", "skills", "codebase-atlas", "scripts");
const FIXTURES = join(SKILL, "tests", "fixtures");

/** Build the page once, from the fixture graph, into a temp file. */
const buildPage = (args: string[] = []): string => {
  const out = join(mkdtempSync(join(tmpdir(), "atlas-")), "index.html");
  execFileSync(
    "python3",
    [
      join(SKILL, "build_atlas.py"),
      "--graph",
      join(FIXTURES, "small.graph.json"),
      "--output",
      out,
      "--repo-root",
      REPO,
      "--no-coverage",
      ...args,
    ],
    { stdio: "pipe" },
  );
  return out;
};

const PLAIN = buildPage();
const WITH_CHANGE = buildPage(["--change", join(FIXTURES, "small.change.json")]);

const open = async (page: Page, file: string, hash = ""): Promise<void> => {
  await page.goto(`file://${file}${hash}`);
  await page.waitForSelector("#color-chips button");
};

/** Read the canvas node positions the page is currently drawing. */
const positions = (page: Page) =>
  page.evaluate(() => {
    const atlas = (globalThis as Record<string, any>).__atlas;
    return atlas.nodes() as { key: string; x: number; y: number }[];
  });

test.describe("colour modes", () => {
  test("offers language and coverage, and delta only with a change", async ({
    page,
  }) => {
    await open(page, PLAIN);
    await expect(page.locator("#color-chips button")).toHaveText([
      "language",
      "coverage",
    ]);

    await open(page, WITH_CHANGE);
    await expect(page.locator("#color-chips button")).toHaveText([
      "language",
      "delta",
      "coverage",
    ]);
  });

  test("the legend names which coverage source is in use", async ({ page }) => {
    await open(page, PLAIN);
    await page.locator('#color-chips [data-mode="coverage"]').click();

    // Without a line report the scale is a count of tests, and saying so is
    // the difference between a number and a misread percentage.
    await expect(page.locator("#legend")).toContainText("test linkage");
    await expect(page.locator("#legend")).toContainText("no test reaches it");
  });

  test("the delta legend distinguishes unchanged from out of frame", async ({
    page,
  }) => {
    await open(page, WITH_CHANGE);
    await page.locator('#color-chips [data-mode="delta"]').click();

    await expect(page.locator("#legend")).toContainText("unchanged");
    await expect(page.locator("#legend")).toContainText("not in this change");
  });
});

const drawnKeys = (page: Page) =>
  page.evaluate(() => {
    const atlas = (globalThis as Record<string, any>).__atlas;
    return atlas.nodes().map((n: { key: string }) => n.key);
  });

test.describe("test files", () => {
  test("are not drawn until asked for", async ({ page }) => {
    await open(page, PLAIN);
    await expect(page.locator("#show-tests")).toHaveAttribute(
      "aria-pressed",
      "false",
    );

    const hidden = await drawnKeys(page);
    expect(hidden.some((k) => k.includes("test_user.py"))).toBe(false);
    expect(hidden.some((k) => k.includes("user.py"))).toBe(true);

    await page.locator("#show-tests").click();
    const shown = await drawnKeys(page);

    expect(shown.length).toBeGreaterThan(hidden.length);
    expect(shown.some((k) => k.includes("test_user.py"))).toBe(true);
  });

  test("are detected by path where the analyzer marks no test kind", async ({
    page,
  }) => {
    // ts-morph emits ordinary `function` kinds for a spec file, so a rule that
    // only read symbol kinds would hide Python tests and leave this one drawn.
    await open(page, PLAIN);
    const hidden = await drawnKeys(page);

    expect(hidden.some((k) => k.includes("user.test.ts"))).toBe(false);

    await page.locator("#show-tests").click();
    const shown = await drawnKeys(page);

    expect(shown.some((k) => k.includes("user.test.ts"))).toBe(true);
  });
});

test.describe("a view is a URL", () => {
  test("restores the colour mode and the test toggle from the hash", async ({
    page,
  }) => {
    await open(page, WITH_CHANGE, "#mode=delta&tests=1");

    await expect(
      page.locator('#color-chips [data-mode="delta"]'),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator("#show-tests")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  test("writes the mode back into the hash when it changes", async ({ page }) => {
    await open(page, PLAIN);
    await page.locator('#color-chips [data-mode="coverage"]').click();

    expect(page.url()).toContain("mode=coverage");
  });
});

/**
 * Wait until the simulation has stopped, by reading positions until two
 * consecutive samples agree. The page is designed to relax and then stop, so
 * comparing before it has is measuring residual physics rather than the
 * interaction under test.
 */
const settled = async (page: Page): Promise<{ x: number; y: number }[]> => {
  let previous = JSON.stringify(await positions(page));
  for (let attempt = 0; attempt < 40; attempt += 1) {
    await page.waitForTimeout(150);
    const current = JSON.stringify(await positions(page));
    if (current === previous) return JSON.parse(current);
    previous = current;
  }
  throw new Error("the layout never settled");
};

test.describe("the layout is the reader's", () => {
  test("switching colour mode does not move a settled node", async ({ page }) => {
    await open(page, PLAIN);
    const before = await settled(page);

    await page.locator('#color-chips [data-mode="coverage"]').click();
    const after = await positions(page);

    expect(after).toEqual(before);
  });

  test("selecting a node does not move it either", async ({ page }) => {
    await open(page, PLAIN);
    const before = await settled(page);

    // Selection changes what is highlighted, never where anything is.
    await page.evaluate(() => {
      const first = document.querySelector("#tree li [data-key], #tree li");
      (first as HTMLElement | null)?.click();
    });
    const after = await positions(page);

    expect(after).toEqual(before);
  });
});

test.describe("the coverage banner", () => {
  test("cannot be dismissed", async ({ page }) => {
    await open(page, PLAIN);
    const banner = page.locator(".coverage").first();

    if (await banner.count()) {
      await expect(banner).toBeVisible();
      await expect(banner.locator("button")).toHaveCount(0);
    }
  });
});

const drawnSymbols = (page: Page) =>
  page.evaluate(() => {
    const atlas = (globalThis as Record<string, any>).__atlas;
    return atlas.symbols() as string[];
  });

const setZoom = (page: Page, k: number) =>
  page.evaluate((z) => {
    (globalThis as Record<string, any>).__atlas.setZoom(z);
  }, k);

test.describe("node-level zoom", () => {
  test("expands a module into its symbols past the threshold", async ({
    page,
  }) => {
    await open(page, PLAIN);
    await settled(page);

    // A graph this small fits at a zoom that is already past the threshold,
    // which is the behaviour we want; step back out to test the threshold.
    await setZoom(page, 1);
    expect(await drawnSymbols(page)).toEqual([]);

    await setZoom(page, 3);
    const symbols = await drawnSymbols(page);

    expect(symbols.length).toBeGreaterThan(0);
    expect(symbols.some((id) => id.includes("services.user.create"))).toBe(true);
  });

  test("expanding changes the grain, not the layout", async ({ page }) => {
    await open(page, PLAIN);
    await settled(page);
    await setZoom(page, 1);
    const before = await positions(page);

    await setZoom(page, 3);
    const after = await positions(page);

    // Symbols are placed around the centre their module already had, so no
    // module moves to make room for them.
    expect(after).toEqual(before);
  });

  test("collapses again below the threshold", async ({ page }) => {
    await open(page, PLAIN);
    await settled(page);
    await setZoom(page, 3);
    expect((await drawnSymbols(page)).length).toBeGreaterThan(0);

    await setZoom(page, 1.0);

    expect(await drawnSymbols(page)).toEqual([]);
  });

  test("the grain travels in the URL", async ({ page }) => {
    await open(page, PLAIN, "#z=3.000");
    await page.waitForTimeout(300);

    const view = await page.evaluate(
      () => (globalThis as Record<string, any>).__atlas.view().k as number,
    );
    expect(view).toBeCloseTo(3, 2);
    expect((await drawnSymbols(page)).length).toBeGreaterThan(0);
  });
});

test.describe("the walkthrough", () => {
  test("is offered only when the document carries one", async ({ page }) => {
    await open(page, PLAIN);
    await expect(page.locator("#walk")).toBeHidden();

    await open(page, WITH_CHANGE);
    await expect(page.locator("#walk")).toBeVisible();
    await expect(page.locator("#walk-count")).toContainText("1 /");
  });

  test("steps forward and back, and says where it is", async ({ page }) => {
    await open(page, WITH_CHANGE);
    const first = await page.locator("#walk-heading").textContent();

    await page.locator("#walk-next").click();
    const second = await page.locator("#walk-heading").textContent();
    expect(second).not.toBe(first);
    await expect(page.locator("#walk-count")).toContainText("2 /");

    await page.locator("#walk-prev").click();
    await expect(page.locator("#walk-heading")).toHaveText(first ?? "");
  });

  test("the step travels in the URL", async ({ page }) => {
    await open(page, WITH_CHANGE);
    await page.locator("#walk-next").click();
    expect(page.url()).toContain("step=2");

    await open(page, WITH_CHANGE, "#step=2");
    await expect(page.locator("#walk-count")).toContainText("2 /");
  });

  test("playing a step frames the view without moving a node", async ({
    page,
  }) => {
    await open(page, WITH_CHANGE);
    const before = await settled(page);

    await page.locator("#walk-next").click();
    const after = await positions(page);

    // A step changes the viewport, never the layout.
    expect(after).toEqual(before);
  });

  test("advances on the keyboard", async ({ page }) => {
    await open(page, WITH_CHANGE);
    const first = await page.locator("#walk-heading").textContent();

    await page.keyboard.press("w");

    expect(await page.locator("#walk-heading").textContent()).not.toBe(first);
  });
});
