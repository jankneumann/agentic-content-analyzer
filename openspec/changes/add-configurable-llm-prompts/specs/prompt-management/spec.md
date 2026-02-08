## ADDED Requirements

### Requirement: Prompt Storage and Override System

The system SHALL provide a centralized prompt management service that loads prompts from a YAML seed file and supports database overrides for user customization.

#### Scenario: Load prompt from YAML default
- **WHEN** a prompt is requested via `PromptService` for a key with no database override
- **THEN** the prompt value SHALL be loaded from `src/config/prompts.yaml`
- **AND** the YAML file SHALL be cached in memory after first load

#### Scenario: Load prompt with database override
- **WHEN** a prompt is requested via `PromptService` for a key that has a database override in `prompt_overrides`
- **THEN** the database override value SHALL be returned
- **AND** the YAML default SHALL NOT be used

#### Scenario: Template variable interpolation
- **WHEN** a prompt template contains `{variable}` placeholders
- **AND** the caller provides variable values via `PromptService.render(key, **variables)`
- **THEN** known variables SHALL be substituted into the template
- **AND** unknown variables (not provided by caller) SHALL be left as literal `{variable}` text
- **AND** no code execution or evaluation SHALL occur during interpolation

#### Scenario: Set prompt override
- **WHEN** a prompt override is set via `PromptService.set_override(key, value)`
- **THEN** the override SHALL be stored in the `prompt_overrides` table
- **AND** the `version` column SHALL be incremented
- **AND** the `updated_at` timestamp SHALL be set to the current time

#### Scenario: Clear prompt override
- **WHEN** a prompt override is cleared via `PromptService.clear_override(key)`
- **THEN** the database row for that key SHALL be deleted
- **AND** subsequent requests for that key SHALL return the YAML default

#### Scenario: List all prompts with override status
- **WHEN** `PromptService.list_all_prompts()` is called
- **THEN** all prompts defined in `prompts.yaml` SHALL be returned
- **AND** each entry SHALL indicate whether a database override exists
- **AND** both the default and override values SHALL be included

### Requirement: Prompt Override Database Schema

The `prompt_overrides` table SHALL store user customizations with versioning support.

#### Scenario: Schema includes version tracking
- **GIVEN** the `prompt_overrides` table
- **THEN** it SHALL have columns: `id` (PK), `key` (unique indexed), `value` (text), `version` (integer, default 1), `description` (text, nullable), `created_at`, `updated_at`

#### Scenario: Version auto-increments on update
- **WHEN** an existing prompt override is updated
- **THEN** the `version` column SHALL be incremented by 1
- **AND** the `updated_at` timestamp SHALL be refreshed

### Requirement: Prompt Seed Configuration File

The system SHALL use `src/config/prompts.yaml` as the seed file containing all default prompt values.

#### Scenario: YAML contains all pipeline prompts
- **GIVEN** the `prompts.yaml` file
- **THEN** it SHALL contain entries for all pipeline steps: `summarization`, `theme_analysis`, `digest_creation`, `digest_revision`, `historical_context`, `podcast_script`, `script_revision`
- **AND** each entry SHALL contain at minimum a `system` prompt
- **AND** prompt text SHALL be identical to the previously hardcoded values

#### Scenario: YAML contains all chat prompts
- **GIVEN** the `prompts.yaml` file
- **THEN** it SHALL contain entries for all chat artifact types: `summary`, `digest`, `script`
- **AND** each entry SHALL contain a `system` prompt

#### Scenario: New prompts added to YAML are available without migration
- **WHEN** a developer adds a new prompt key to `prompts.yaml`
- **AND** the application starts
- **THEN** the new prompt SHALL be available via `PromptService` without any database migration or seeding step

### Requirement: Prompt Configuration Settings API

The system SHALL provide REST API endpoints for managing prompt overrides via the existing `/api/v1/settings/prompts` routes.

#### Scenario: List prompts via API
- **WHEN** `GET /api/v1/settings/prompts` is called
- **THEN** all prompts SHALL be returned with: key, category, name, default_value, current_value, has_override
- **AND** the response SHALL include prompts from both chat and pipeline categories

#### Scenario: Get single prompt via API
- **WHEN** `GET /api/v1/settings/prompts/{key}` is called
- **THEN** the prompt details SHALL be returned including default and current values

#### Scenario: Update prompt via API
- **WHEN** `PUT /api/v1/settings/prompts/{key}` is called with a value
- **THEN** a database override SHALL be created or updated
- **AND** the response SHALL confirm the new current_value

#### Scenario: Reset prompt via API
- **WHEN** `DELETE /api/v1/settings/prompts/{key}` is called
- **THEN** the database override SHALL be removed
- **AND** the response SHALL show the YAML default as current_value

### Requirement: Frontend Prompt Editor

The Settings page SHALL include a prompt configuration section for viewing and editing prompts.

#### Scenario: Display prompt list
- **WHEN** the Settings page is loaded
- **THEN** a "Prompt Configuration" section SHALL display all prompts grouped by category
- **AND** prompts with overrides SHALL show a visual indicator (badge)

#### Scenario: Edit a prompt
- **WHEN** a user clicks on a prompt in the list
- **THEN** a textarea editor SHALL expand showing the current prompt value
- **AND** a "Show diff" toggle SHALL compare the current value against the default
- **AND** "Save" and "Reset to default" buttons SHALL be available

#### Scenario: Save prompt override
- **WHEN** a user edits a prompt and clicks "Save"
- **THEN** the override SHALL be saved via the settings API
- **AND** a success notification SHALL be displayed
- **AND** the override indicator SHALL appear on the prompt

#### Scenario: Reset prompt to default
- **WHEN** a user clicks "Reset to default" on an overridden prompt
- **THEN** the override SHALL be deleted via the settings API
- **AND** the editor SHALL show the YAML default value
- **AND** the override indicator SHALL be removed
