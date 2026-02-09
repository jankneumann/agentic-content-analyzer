# Change: Add direct URL ingest via UI and CLI

## Why
Users need a fast way to ingest individual URLs without relying on the browser extension or bookmarklet.

## What Changes
- Add a web UI form to submit a URL for ingestion using the existing save-url workflow.
- Add an `aca ingest url` CLI command to submit a URL for ingestion.
- Reuse the existing save-url API and content capture pipeline for deduplication and status.

## Impact
- Affected specs: content-capture, cli-interface
- Affected code: web UI ingestion components, CLI ingest commands, shared content capture service
