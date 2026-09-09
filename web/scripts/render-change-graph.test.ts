/**
 * Rendering a change document must be boring: same document, same bytes.
 *
 * The goldens exist because a change to what a reviewer sees should be
 * reviewed by a person. A diff in these files is not a test failure to be
 * regenerated away; it is the diagram changing, and it wants reading.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { parseGraphDoc } from "@coldtea/pr-lens-schema";
import type { GraphDoc } from "@coldtea/pr-lens-schema";
import { renderAll } from "@coldtea/pr-lens-renderer";
import { describe, expect, it } from "vitest";

const FIXTURES = join(
  import.meta.dirname,
  "..",
  "..",
  ".claude",
  "skills",
  "refresh-architecture",
  "scripts",
  "tests",
  "fixtures",
  "change",
);
const GOLDENS = join(import.meta.dirname, "__goldens__");

const load = (name: string): GraphDoc =>
  parseGraphDoc(JSON.parse(readFileSync(join(FIXTURES, name), "utf8")));

const assetsOf = (name: string) => renderAll(load(name), {}).assets;

const byId = (name: string) =>
  new Map(assetsOf(name).map((asset) => [asset.asset.id, asset]));

describe("the contract both validators share", () => {
  it.each(["recent-fixes.graph.json", "repo-wide.graph.json"])(
    "accepts %s, which the Python projector produced",
    (fixture) => {
      // Reaching a throw here means the vendored schema and the pinned package
      // have drifted, which is the failure vendoring exists to prevent.
      expect(() => load(fixture)).not.toThrow();
    },
  );
});

describe("rendering", () => {
  it("draws both themes for every view", () => {
    const assets = assetsOf("recent-fixes.graph.json");
    const themes = new Set(assets.map((asset) => asset.theme));

    expect(themes).toEqual(new Set(["light", "dark"]));
    expect(assets.length % 2).toBe(0);
  });

  it.each(["light", "dark"])(
    "matches the reviewed %s golden",
    (theme) => {
      const rendered = byId("recent-fixes.graph.json").get(
        `blast-radius-${theme}`,
      );
      const golden = readFileSync(
        join(GOLDENS, `small-blast-radius-${theme}.svg`),
        "utf8",
      );

      expect(rendered?.svg).toBe(golden);
    },
  );

  it("produces the same bytes twice", () => {
    const first = assetsOf("repo-wide.graph.json").map((asset) => asset.svg);
    const second = assetsOf("repo-wide.graph.json").map((asset) => asset.svg);

    expect(first).toEqual(second);
  });
});

describe("self-containment", () => {
  /**
   * GitHub serves comment images through a proxy, where the surrounding page
   * does not exist. Anything the file needs from that page is simply absent,
   * and the diagram degrades silently rather than failing.
   */
  const forbidden: [string, RegExp][] = [
    ["script tags", /<script/i],
    ["external stylesheets", /<link\b/i],
    ["stylesheet imports", /@import/i],
    ["remote url() references", /url\(\s*['"]?https?:/i],
    ["embedded images", /<image\b/i],
    ["CSS custom properties", /var\(--/],
    ["remote hrefs", /(?:href|xlink:href)=["']https?:/i],
  ];

  it.each(forbidden)("contains no %s", (_label, pattern) => {
    for (const asset of assetsOf("repo-wide.graph.json")) {
      expect(asset.svg).not.toMatch(pattern);
    }
  });
});

describe("content addressing", () => {
  it("gives a changed view a new file name and leaves the others alone", () => {
    const document = load("recent-fixes.graph.json");
    const before = new Map(
      renderAll(document, {}).assets.map((asset) => [
        asset.asset.id,
        asset.asset.path,
      ]),
    );

    // One label, on one node, in one view.
    const edited = JSON.parse(JSON.stringify(document)) as GraphDoc;
    edited.nodes[0]!.label = "A Deliberately Different Label";
    const after = new Map(
      renderAll(parseGraphDoc(edited), {}).assets.map((asset) => [
        asset.asset.id,
        asset.asset.path,
      ]),
    );

    const moved = [...before.keys()].filter(
      (id) => before.get(id) !== after.get(id),
    );

    expect(moved.length).toBeGreaterThan(0);
    expect(moved.length).toBeLessThan(before.size);
  });

  it("names every asset after a hash of its own bytes", () => {
    for (const asset of assetsOf("recent-fixes.graph.json")) {
      expect(asset.asset.path).toContain(asset.asset.contentHash);
    }
  });
});
