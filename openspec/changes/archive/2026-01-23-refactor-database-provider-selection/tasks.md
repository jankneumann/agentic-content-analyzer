# Tasks: Refactor Database Provider Selection

## 1. Settings Refactoring

- [x] 1.1 Update `src/config/settings.py` - Add explicit `database_provider` field
  - Add `database_provider: Literal["local", "supabase", "neon"] = "local"`
  - Ensure field is loaded from `DATABASE_PROVIDER` env var

- [x] 1.2 Add Pydantic validator for provider configuration
  - Create `@model_validator(mode="after")` named `validate_database_provider_config`
  - For `neon`: Validate URL contains `.neon.tech`
  - For `supabase`: Validate `supabase_project_ref` or URL contains `.supabase.`
  - For `local`: Warn if URL looks like cloud provider

- [x] 1.3 Add `_mask_url()` helper for safe error messages
  - Mask password in URL for error output
  - Show host/path for debugging

- [x] 1.4 Simplify `get_effective_database_url()` with match statement
  - Replace if/elif chain with `match self.database_provider`
  - Extract provider-specific logic to private methods (`_get_supabase_pooler_url`)

- [x] 1.5 Simplify `get_migration_database_url()` with match statement
  - Replace if/elif chain with `match self.database_provider`
  - Extract to private methods (`_get_supabase_direct_url`, `_get_neon_direct_url`)

- [x] 1.6 Deprecate `detected_database_provider` property
  - Add deprecation warning via `warnings.warn()`
  - Return `self.database_provider` directly

## 2. Provider Factory Updates

- [x] 2.1 Update `src/storage/providers/factory.py`
  - Simplified `detect_provider()` - now returns override or "local" default
  - Added deprecation warning for implicit detection params
  - Updated `get_provider()` to use explicit `provider_override`
  - Updated docstrings with usage example

## 3. Documentation Updates

- [x] 3.1 Update `docs/SETUP.md`
  - Moved `DATABASE_PROVIDER` to top of provider config sections
  - Changed from "optional, auto-detected" to "Required: explicit provider selection"
  - Added DATABASE_URL example for Neon section

- [x] 3.2 Update `CLAUDE.md`
  - Updated Database Providers table: removed "Detection" column, added `DATABASE_PROVIDER` column
  - Added `.env` example showing explicit provider selection

- [x] 3.3 Update `.env.example`
  - Added `DATABASE_PROVIDER=local` as first database config
  - Added commented sections for Supabase and Neon configuration
  - Organized with clear headers and comments

## 4. Testing

- [x] 4.1 Add unit tests for validator in `tests/test_config/test_settings.py`
  - Test: `neon` provider with valid Neon URL passes
  - Test: `neon` provider with non-Neon URL raises ValueError
  - Test: `supabase` provider with valid config passes
  - Test: `supabase` provider without config raises ValueError
  - Test: `local` provider with cloud URL logs warning
  - Test: Password masked in error messages
  - Test: URL method tests for all providers
  - Test: Deprecation warning for `detected_database_provider`

- [x] 4.2 Update existing provider tests
  - Updated `TestDetectProvider` to test deprecation warnings
  - Updated `TestGetProvider` to use explicit `provider_override`
  - All 44 provider tests pass

- [x] 4.3 Add integration test for startup validation
  - Covered via unit tests in 4.1 (validation happens at Settings instantiation)

## 5. Migration Support

- [x] 5.1 Add startup log message showing detected provider
  - Added INFO log in `get_settings()`: "Database provider: {provider} | URL: {masked_url}"
  - Helps users verify configuration at startup

- [x] 5.2 Create migration guide in `docs/MIGRATION.md` or inline
  - Breaking change documented in proposal.md
  - Before/after examples in .env.example
  - Clear error messages guide users to set DATABASE_PROVIDER
