# Obsidian Vault Ingestion

Ingests notes clipped by the [Obsidian Web Clipper](https://obsidian.md/clipper)
from a worker-local vault folder into canonical `Content` rows.

This is **vault ingress only**. It is unrelated to knowledge-base export or any
vault sync feature: nothing is ever written back into the vault, and no note is
mirrored out of the aggregator into Obsidian. The two directions are deliberately
separate, and this source owns only the inbound half.

## How it works

One scan is one bounded durable operation, submitted through `OperationService`
like every other ingestion. There is no watcher, no poller, and no long-lived
process holding the vault open:

1. A scan is submitted (CLI, HTTP, MCP, or the UI) naming a vault by its opaque
   `source_key`.
2. The worker that owns the mount enumerates `ingest_folder` under `vault_path`,
   bounded by every ceiling in the source config.
3. Each note is parsed against the strict clip contract below, normalized, and
   persisted as `ContentSource.OBSIDIAN`.
4. The operation terminates with typed counts and stable diagnostic codes.

If a scan reaches a ceiling before the folder is exhausted it returns a cursor
and terminates cleanly; the next scan resumes. A large backlog drains across
several scans rather than one unbounded run.

### Incremental behavior

Ingestion state is keyed by *file version* — the path digest plus the content
hash — so scanning repeatedly is cheap and safe:

| Situation | Result |
|---|---|
| New note | Persisted; one new `Content` row |
| Unchanged note re-scanned | Skipped; nothing committed |
| Note edited after ingestion | New immutable file version persisted as a new row, linked to the same canonical primary |
| Two notes clipping one page | Both kept with their own annotations; both link to one canonical primary via `Content.canonical_id` |

Because distinct notes of one page each keep their own row, `items_ingested`
counts **rows** while the operation's `content_ids` lists **canonical
identities** — for a vault with duplicate clips the second number is smaller.
That is intended, not a persistence mismatch.

### Failure handling

A note that fails validation is recorded in `obsidian_ingest_events` with a
stable code and retried on later scans against a bounded budget
(`max_attempts`, default 3). Once that budget is spent and the file has not
changed, later scans stop retrying it: the note is skipped and its code is
restated as a **warning**, not an error. A single permanently invalid note
therefore cannot fail every future scan of the vault or re-alert an operator on
every poll. The original failure stays queryable in the event row.

## Setup

### 1. Approve a root

`vault_path` must resolve inside a deployment-owned allowed root. This is set on
the worker, not in the source config, so a source override can never widen the
filesystem the worker will read:

```bash
OBSIDIAN_ALLOWED_ROOTS=/srv/obsidian          # comma-separated absolute paths
OBSIDIAN_COMPATIBLE_WORKER=true               # this worker owns the mount
CONFIGURED_SOURCE_KEY_SECRET=<32+ byte secret>  # derives opaque source keys
```

Readiness is **fail-closed and path-free**: if the roots are unset, the worker is
not flagged compatible, or the vault does not resolve inside a root, the source
reports not-ready and no scan runs. The reason never contains a path.

### 2. Configure the vault

Copy [`sources.d/obsidian-vault.yaml.example`](../sources.d/obsidian-vault.yaml.example)
to `sources.d/obsidian-vault.yaml` and edit `vault_id`, `vault_path`, and
`ingest_folder`. Every other key is a ceiling with a safe default.

### 3. Scan

```bash
aca configured-sources --json     # confirm the vault is discovered and ready
aca ingest obsidian-vault --wait  # submit one scan per configured vault
aca operations list               # observe the durable operations
```

Each configured vault gets its own command carrying its own opaque key and a
config-version fingerprint, so several vaults can be configured side by side.
A scan queued before the vault's configuration changed is rejected on pickup
with "Configured source changed; resubmit the command" rather than scanning a
stale location.

### Mount topologies

| Topology | Supported | Notes |
|---|---|---|
| Vault on the same host as the worker | Yes | The intended v1 deployment |
| Vault on a volume mounted into the worker container | Yes | Mount read-only; approve the mount point as a root |
| Vault on a laptop, backend on Railway | **No** | Railway has no access to a device path. Run a worker where the vault lives, or clip into a synced folder that a worker can read |
| Network/remote filesystem bridge | **No** | Deferred; see below |

### Sync providers

A vault backed by iCloud, Dropbox, or Syncthing is eventually consistent: a note
can be visible while still being written, or be a placeholder that materializes
on read. Set `settle_seconds` above your provider's typical write window (5–15s
is usually enough) so a scan ignores notes touched too recently. Notes that
change while being read are rejected for that scan with a stability diagnostic
and picked up by the next one, so an unstable file is never half-ingested.

## The clip contract

Clips must carry YAML frontmatter. The clipped Markdown is treated as
authoritative — `source_url` is recorded as identity and **never refetched**, so
your annotations and the page as you saw it are what get stored.

```markdown
---
source_url: https://example.com/article
captured_at: 2026-08-02T11:00:00Z
capture_client: obsidian-web-clipper
content_type_hint: article
---

# Article title

Body, annotations, and highlights.
```

| Field | Required | Rules |
|---|---|---|
| `source_url` | Yes | Absolute `http`/`https` only. `utm_*`, `fbclid`, and `gclid` are stripped from canonical identity |
| `captured_at` | Yes | ISO-8601 and **timezone-aware**. A naive timestamp is rejected — provenance must be unambiguous |
| `capture_client` | No | Must be `obsidian-web-clipper` when present |
| `content_type_hint` | No | One of `article`, `thread`, `video`, `paper`, `other` |

### Web Clipper template

Set this as the property template in Web Clipper settings:

```yaml
source_url: "{{url}}"
captured_at: "{{date:YYYY-MM-DDTHH:mm:ssZ}}"
capture_client: "obsidian-web-clipper"
content_type_hint: "article"
```

`{{date:...Z}}` must produce an offset. A bare `{{date}}` yields a naive
timestamp and every clip will fail with `invalid_captured_at`.

### Markdown normalization

Obsidian-specific syntax is made inert so nothing resolves against your vault or
triggers a fetch downstream:

- `[[Note]]` and `[[Note|alias]]` become plain text.
- `![[Embedded]]` embeds are flattened, never expanded or fetched.
- `> [!note] Title` callouts become plain blockquotes with a bold label.
- Content inside code spans and fenced blocks is left untouched.

### Deferred

Not in v1: filesystem watchers, attachment/binary ingestion, following file
moves and renames, remote or network vault bridges, and writing anything back
into the vault (including frontmatter status fields or moving processed notes).

## Privacy and security

The vault is treated as a private, untrusted filesystem.

- **Paths never leave the worker.** `vault_path` and `ingest_folder` are not in
  command payloads, API responses, capability discovery, operation results,
  logs, or alerts. Notes are identified by digests; vaults by an HMAC-derived
  opaque `src_...` key.
- **URLs are redacted in diagnostics** to at most the origin. Never a full URL,
  query string, or userinfo.
- **Read-only.** The worker opens files for reading and nothing else.
- **Symlinks are rejected** outright. Reads are descriptor-relative and
  no-follow, and file identity is revalidated after opening, so a path cannot be
  swapped between the check and the read.
- **Untrusted YAML is bounded** by node, depth, alias, string, and byte ceilings
  before any value is interpreted. Custom tags and aliases beyond the limit are
  refused.
- **Error text is input-free.** Diagnostics carry a stable code and never echo
  frontmatter, body, a path, or a raw exception.

### Database overrides

Obsidian sources can be managed at runtime like any other source, with one
difference: the public boundary refuses the natural key. `aca sources` and
`/api/v1/sources` accept only the opaque `src_...` key; passing
`obsidian_vault:<path>` is rejected. The private natural identity is retained in
the database purely so YAML and override rows merge on a stable key. Deletion
responses never echo a caller-supplied key back.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Source reports not-ready | Root not approved, or worker not flagged | Set `OBSIDIAN_ALLOWED_ROOTS` and `OBSIDIAN_COMPATIBLE_WORKER=true` on the worker owning the mount |
| `invalid_captured_at` on every clip | Template emits a naive timestamp | Use `{{date:YYYY-MM-DDTHH:mm:ssZ}}` |
| `missing_required_metadata` | No frontmatter, or no `source_url` | Set the Web Clipper property template |
| `invalid_url` | Non-HTTP(S) scheme, or a `file:`/relative URL | Only `http`/`https` clips are ingestable |
| `note_too_large` / `body_too_large` | Note exceeds a ceiling | Raise `max_note_bytes`, within its hard bound |
| `yaml_node_limit` and friends | Frontmatter is unusually complex | Simplify it, or raise the matching `max_yaml_*` ceiling |
| `retry_exhausted` warning | A note failed its retry budget and is no longer retried | Fix or remove the note; editing it creates a new file version that is retried fresh |
| Scan ends early with a cursor | A per-scan ceiling was reached | Expected; the next scan resumes. Raise ceilings to drain faster |
| Notes never appear | Wrong `ingest_folder`, or clips land elsewhere | Check the Web Clipper output folder matches |

Every code above is stable and safe to alert on. Per-note history is in
`obsidian_ingest_events`; per-file state is in `obsidian_ingest_state`.

## See also

- [Setup](SETUP.md) — sources, providers, environment
- [Architecture](ARCHITECTURE.md) — ingestion services and the durable workflow model
- [Content Capture](CONTENT_CAPTURE.md) — the browser extension and save-URL paths
