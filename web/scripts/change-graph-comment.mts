/**
 * Build the pull request comment for a rendered change document.
 *
 * Every string in the document was written from a diff, and a pull request can
 * carry whatever text an author likes into that diff. So none of it may reach
 * GitHub as markup. Escaping the HTML is only half the job: markdown would
 * still turn `[Security update](http://…)` into a link that looks like ours,
 * and an `@name` or `#42` in a summary would notify a person or cross-link an
 * issue on the say-so of a diff.
 *
 * Each string therefore lands inside an HTML element, on a single line, where
 * markdown is not parsed at all, with a zero-width space after any `@` or `#`.
 *
 * The comment is identified by a marker so a pull request keeps one comment
 * rather than collecting one per push.
 */

import type { GraphDoc, RenderManifest } from "@coldtea/pr-lens-schema";

/** Nothing else may spell this: a marker that drifts orphans every comment. */
export const COMMENT_MARKER = "<!-- change-graph -->";

export type CommentOptions = {
  document: GraphDoc;
  manifest: RenderManifest;
  /** Where the rendered assets are published, e.g. a raw content URL. */
  assetBaseUrl: string;
};

const escape = (value: string): string =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

/**
 * Model-authored prose, rendered as the words it is: collapsed to one line so
 * a blank line cannot end the HTML block and let the rest through as markdown,
 * and with mentions and issue references defused.
 */
const text = (value: string): string =>
  escape(value.replace(/\s+/g, " ").trim()).replace(
    /([@#])(?=[\w-])/g,
    "$1&#8203;",
  );

type Asset = RenderManifest["assets"][number];

const assetsByView = (manifest: RenderManifest): Map<string, Asset[]> => {
  const found = new Map<string, Asset[]>();
  for (const asset of manifest.assets) {
    const list = found.get(asset.view) ?? [];
    list.push(asset);
    found.set(asset.view, list);
  }
  return found;
};

/**
 * A `<picture>` is what makes one comment readable in both GitHub themes: an
 * image cannot see the theme of the page it lands in, so the two are rendered
 * separately and paired. The whole thing links to the image itself, because a
 * comment column is far narrower than a diagram of several lanes; it arrives
 * scaled to fit, and one click gives the size the labels were drawn at.
 */
const picture = (assets: Asset[], alt: string, base: string): string => {
  const light = assets.find((a) => a.theme === "light");
  const dark = assets.find((a) => a.theme === "dark");
  const fallback = light ?? dark;
  if (!fallback) return "";

  const url = (asset: Asset) =>
    escape(`${base.replace(/\/+$/, "")}/${asset.path.replace(/^\/+/, "")}`);
  const img = `<img alt="${text(alt)}" src="${url(fallback)}" width="${fallback.width}">`;
  const shown =
    light && dark
      ? [
          "<picture>",
          `<source media="(prefers-color-scheme: dark)" srcset="${url(dark)}">`,
          img,
          "</picture>",
        ].join("")
      : img;
  return `<a href="${url(fallback)}">${shown}</a>`;
};

/**
 * The stats line is read straight off the document.
 *
 * Coverage is not recomputed here: the projector already counted the changed
 * files the graph never saw and wrote it in as a chip. Deriving the same
 * number twice is how two places end up disagreeing about it.
 */
const statsLine = (document: GraphDoc): string => {
  const stats = document.stats;
  const chips: string[] = [];
  if (stats?.filesChanged !== undefined) {
    chips.push(`${stats.filesChanged} ${stats.filesChanged === 1 ? "file" : "files"}`);
  }
  if (stats?.additions !== undefined) chips.push(`+${stats.additions}`);
  if (stats?.deletions !== undefined) chips.push(`−${stats.deletions}`);
  for (const chip of stats?.chips ?? []) chips.push(`${chip.label} ${chip.value}`);
  if (!chips.length) return "";
  return `<p>${chips.map((c) => `<code>${text(c)}</code>`).join(" · ")}</p>`;
};

type View = GraphDoc["views"][number];

const section = (
  view: View,
  assets: Map<string, Asset[]>,
  base: string,
  depth: number,
): string => {
  const body = [
    view.summary ? `<p>${text(view.summary)}</p>` : "",
    picture(assets.get(view.id) ?? [], view.title, base),
    ...view.children.map((child) => section(child, assets, base, depth + 1)),
  ]
    .filter(Boolean)
    .join("\n");

  // The root view is open; everything below it is a disclosure, so the comment
  // opens on the blast radius rather than on ten diagrams.
  if (depth === 0 && view.defaultOpen) {
    return [`<h4>${text(view.title)}</h4>`, body].join("\n");
  }
  return [
    "<details>",
    `<summary>${text(view.title)}</summary>`,
    "",
    body,
    "</details>",
  ].join("\n");
};

export const buildComment = ({
  document,
  manifest,
  assetBaseUrl,
}: CommentOptions): string => {
  const assets = assetsByView(manifest);
  return [
    COMMENT_MARKER,
    `<h3>${text(document.title)}</h3>`,
    document.summary ? `<p>${text(document.summary)}</p>` : "",
    statsLine(document),
    ...document.views.map((view) => section(view, assets, assetBaseUrl, 0)),
  ]
    .filter(Boolean)
    .join("\n\n");
};
