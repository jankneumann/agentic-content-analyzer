/**
 * Render a change document to self-contained, content-addressed SVGs.
 *
 * The renderer is used rather than reimplemented because its hard part is
 * determinism, not drawing: text measured from a table so a CI runner with no
 * fonts lays out like a laptop, fixed lane widths so adding a node to one lane
 * moves nothing in another, every coordinate rounded before it is written.
 * Reproducing that in Python would mean reproducing its bugs too.
 *
 * Assets are addressed by a hash of their own content because GitHub's image
 * proxy caches hard: a changed diagram has to arrive as a new URL, not as new
 * bytes at an old one.
 *
 * Usage:
 *   node --experimental-strip-types scripts/render-change-graph.mts \
 *     <document.json> --out <dir> [--corrections ../settings/change-graph.yaml]
 */

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { parseArgs } from "node:util";

import { parseConfig, parseGraphDoc } from "@coldtea/pr-lens-schema";
import type { Config, GraphDoc } from "@coldtea/pr-lens-schema";
import { renderAll } from "@coldtea/pr-lens-renderer";

/**
 * The overlay is YAML in this repository and JSON to the schema package, so it
 * is converted here rather than kept in two formats. Only `map` is read: the
 * other keys in the upstream config are the hosted app's concern.
 */
const loadCorrections = async (path: string | undefined): Promise<Config | undefined> => {
  if (!path) return undefined;
  let raw: string;
  try {
    raw = readFileSync(path, "utf8");
  } catch {
    return undefined; // A missing overlay is the ordinary case, not an error.
  }
  const { parse } = await import("yaml");
  const parsed = parse(raw) ?? {};
  return parseConfig(parsed);
};

const main = async (): Promise<number> => {
  const { values, positionals } = parseArgs({
    allowPositionals: true,
    options: {
      out: { type: "string", short: "o" },
      corrections: { type: "string" },
      "asset-base-url": { type: "string" },
    },
  });

  const source = positionals[0];
  if (!source) {
    console.error("usage: render-change-graph <document.json> --out <dir>");
    return 2;
  }

  let document: GraphDoc;
  try {
    document = parseGraphDoc(JSON.parse(readFileSync(source, "utf8")));
  } catch (error) {
    // The Python projector validates against the same vendored schema, so
    // reaching here means the two validators disagree -- which is the failure
    // vendoring exists to prevent. Say so plainly.
    console.error(
      `the document at ${source} does not satisfy the contract this renderer ` +
        `was pinned against: ${(error as Error).message}`,
    );
    return 1;
  }

  const outDir = resolve(values.out ?? dirname(source));
  const config = await loadCorrections(values.corrections);
  const { assets, manifest } = renderAll(document, config ? { config } : {});

  mkdirSync(outDir, { recursive: true });
  for (const rendered of assets) {
    // The manifest entry, not the render, owns the file name: it carries the
    // hash of the SVG's own bytes, which is what makes a changed diagram
    // arrive at a new URL instead of as new bytes at the old one.
    const target = join(outDir, rendered.asset.path);
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(target, rendered.svg, "utf8");
  }
  writeFileSync(
    join(outDir, "manifest.json"),
    `${JSON.stringify(manifest, null, 2)}\n`,
    "utf8",
  );

  console.log(
    `✓ ${outDir} — ${assets.length} assets across ${assets.length / 2} views`,
  );
  return 0;
};

main().then(
  (code) => process.exit(code),
  (error) => {
    console.error(error);
    process.exit(1);
  },
);
