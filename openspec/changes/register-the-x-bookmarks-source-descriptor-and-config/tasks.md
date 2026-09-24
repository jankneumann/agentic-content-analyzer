# Tasks: Register the x_bookmarks source descriptor and config

> Change ID: `register-the-x-bookmarks-source-descriptor-and-config`

## 1. Configuration

- [x] 1.1 Tests for `XBookmarksSource` defaults, bounds, the fixed `x_bookmarks:account` key, the union, and the enabled-only accessor
- [x] 1.2 Add `XBookmarksSource`, `X_BOOKMARKS_LOCATOR`, `get_x_bookmarks_sources()`, the locator map entry, and the docstring source list in `src/config/sources.py`
- [x] 1.3 Ship `sources.d/x_bookmarks.yaml` (one entry, disabled, `max_entries: 100`, `expand_links: false`, credential comment); test that it loads and plans nothing

## 2. Registry

- [x] 2.1 Tests for the descriptor, the planner (max_entries to max_items, expand_links, period ignored), and dispatch kwargs
- [x] 2.2 Register the `x_bookmarks` `SourceDescriptor` with `_bulk_plan`, matcher, accessor, and `supports_force`
- [x] 2.3 Tests for readiness: either cookie missing, pair present (OpenBao or Settings through the provider), either rejected, rotation clears, provider failure, value-free listing
- [x] 2.4 Implement `_x_bookmarks_readiness` through `get_credential_provider()`; allowlist `expand_links` in the public configuration projection

## 3. Fail-closed orchestrator and policy

- [x] 3.1 Add `ingest_x_bookmarks` returning `status=error` with `source_unavailable`; test the envelope and the durable handler result
- [x] 3.2 Add `requires_all_credentials` to `LiveAdapterPolicy` and the `x_bookmarks` policy on `X_AUTH_TOKEN` + `X_CT0`, with tests
- [x] 3.3 Add the network-free `x_bookmarks` fixture to `tests/fixtures/sources/library.py` and `x_bookmarks` to the registry key set test

## 4. Validation

- [x] 4.1 `uvx ruff@0.15.15 check` and `format`, `mypy` on the changed source files
- [x] 4.2 Capability, registry, source matrix, contract canonical, MCP conformance, CLI canonical, config sources, real-ingestion, and `pytest tests/contract/ -m contract`
- [x] 4.3 `openspec validate register-the-x-bookmarks-source-descriptor-and-config --type change --strict`
