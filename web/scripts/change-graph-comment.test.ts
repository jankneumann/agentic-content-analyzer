/**
 * The comment is the one surface where model-authored text meets a system that
 * renders markup and notifies people. These tests are about that boundary far
 * more than about layout.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { parseGraphDoc } from "@coldtea/pr-lens-schema";
import type { GraphDoc } from "@coldtea/pr-lens-schema";
import { renderAll } from "@coldtea/pr-lens-renderer";
import { describe, expect, it } from "vitest";

import { COMMENT_MARKER, buildComment } from "./change-graph-comment.mts";

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

const BASE = "https://raw.githubusercontent.com/acme/webapp/assets/42/abc1234";

const load = (name = "recent-fixes.graph.json"): GraphDoc =>
  parseGraphDoc(JSON.parse(readFileSync(join(FIXTURES, name), "utf8")));

const compose = (document: GraphDoc) =>
  buildComment({
    document,
    manifest: renderAll(document, {}).manifest,
    assetBaseUrl: BASE,
  });

describe("identity", () => {
  it("carries the marker that keeps one comment per pull request", () => {
    expect(compose(load())).toContain(COMMENT_MARKER);
  });

  it("puts the marker first, where an updater looks for it", () => {
    expect(compose(load()).startsWith(COMMENT_MARKER)).toBe(true);
  });
});

describe("untrusted text", () => {
  it("cannot notify a person or cross-link an issue", () => {
    const document = load();
    document.summary = "Thanks @octocat, this closes #42 and #7.";

    const comment = compose(document);

    expect(comment).not.toMatch(/@octocat/);
    expect(comment).not.toMatch(/#42/);
    // The characters survive; only their power to link does.
    expect(comment).toContain("@&#8203;octocat");
    expect(comment).toContain("#&#8203;42");
  });

  it("cannot smuggle markup", () => {
    const document = load();
    document.title = '<img src=x onerror="alert(1)">';

    const comment = compose(document);

    expect(comment).not.toContain("<img src=x");
    expect(comment).toContain("&lt;img src=x");
  });

  it("cannot end its own HTML block with a blank line", () => {
    const document = load();
    document.summary = "First line.\n\n[A link](http://evil.example)";

    const comment = compose(document);
    const summaryLine = comment
      .split("\n")
      .find((line) => line.includes("First line."));

    // Collapsed to one line, so markdown never gets a paragraph break to
    // resume parsing at.
    expect(summaryLine).toContain("[A link](http://evil.example)");
    expect(summaryLine).not.toContain("\n");
  });
});

describe("structure", () => {
  it("opens on the root view and collapses the rest", () => {
    const comment = compose(load());

    expect(comment).toContain("<h4>Blast radius</h4>");
    expect(comment).toContain("<details>");
    expect(comment.indexOf("<h4>")).toBeLessThan(comment.indexOf("<details>"));
  });

  it("pairs a light and a dark image so both themes read", () => {
    const comment = compose(load());

    expect(comment).toContain("<picture>");
    expect(comment).toContain('media="(prefers-color-scheme: dark)"');
  });

  it("points every image at the published assets", () => {
    const comment = compose(load());
    const sources = [...comment.matchAll(/src="([^"]+)"/g)].map((m) => m[1]);

    expect(sources.length).toBeGreaterThan(0);
    expect(sources.every((src) => src?.startsWith(BASE))).toBe(true);
  });
});

describe("coverage", () => {
  it("shows how much of the change is outside the graph", () => {
    // The number comes from the document's own chip, written by the projector.
    // Recomputing it here would give the comment a second source that can
    // disagree with the diagram beside it.
    const comment = compose(load());

    expect(comment).toContain("Files outside the graph");
  });

  it("stays quiet when the projector recorded no gap", () => {
    const document = load();
    document.stats = { ...document.stats, chips: [] };

    expect(compose(document)).not.toContain("outside the graph");
  });
});
