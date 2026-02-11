## ADDED Requirements

### Requirement: Prompt Management CLI Commands

The system SHALL provide `aca prompts` subcommands for managing LLM prompt configuration from the command line.

#### Scenario: List all prompts
- **WHEN** `aca prompts list` is executed
- **THEN** all prompts SHALL be displayed grouped by category (chat, pipeline)
- **AND** each prompt SHALL show: key, category, name, whether it has an override
- **AND** overridden prompts SHALL be visually distinguished (e.g., badge or color)

#### Scenario: List prompts filtered by category
- **WHEN** `aca prompts list --category pipeline` is executed
- **THEN** only pipeline prompts SHALL be displayed
- **AND** chat prompts SHALL be excluded

#### Scenario: Show a specific prompt
- **WHEN** `aca prompts show pipeline.summarization.system` is executed
- **THEN** the full prompt text SHALL be displayed
- **AND** if an override exists, both the override and default SHALL be shown
- **AND** the prompt version number SHALL be displayed

#### Scenario: Set a prompt override
- **WHEN** `aca prompts set pipeline.summarization.system --value "New prompt text"` is executed
- **THEN** the prompt override SHALL be stored in the database
- **AND** a confirmation message SHALL be displayed with the new value preview

#### Scenario: Set a prompt override from file
- **WHEN** `aca prompts set pipeline.summarization.system --file prompt.txt` is executed
- **THEN** the prompt text SHALL be read from the specified file
- **AND** the prompt override SHALL be stored in the database

#### Scenario: Reset a prompt to default
- **WHEN** `aca prompts reset pipeline.summarization.system` is executed
- **THEN** the database override SHALL be deleted
- **AND** a confirmation SHALL show the prompt will revert to the YAML default

#### Scenario: Export all prompts
- **WHEN** `aca prompts export --output prompts-backup.yaml` is executed
- **THEN** all current prompt values (including overrides) SHALL be written to the specified YAML file
- **AND** the file format SHALL match the `prompts.yaml` structure

#### Scenario: Import prompts
- **WHEN** `aca prompts import --file prompts-backup.yaml` is executed
- **THEN** prompts from the file SHALL be loaded as database overrides
- **AND** a confirmation SHALL show how many prompts were imported
- **AND** existing overrides SHALL be updated, not duplicated

#### Scenario: Test a prompt
- **WHEN** `aca prompts test pipeline.summarization.system` is executed
- **THEN** the prompt SHALL be rendered with sample content (most recent or specified via `--content-id`)
- **AND** the rendered prompt SHALL be sent to the LLM
- **AND** the LLM response text and token usage SHALL be displayed
- **AND** no pipeline artifacts SHALL be persisted

#### Scenario: Test a prompt with specific content
- **WHEN** `aca prompts test pipeline.summarization.system --content-id 42` is executed
- **THEN** content item 42 SHALL be used as sample input for the test

#### Scenario: Invalid prompt key
- **WHEN** `aca prompts show nonexistent.key` is executed
- **THEN** an error message SHALL indicate the prompt key is not recognized
- **AND** available keys SHALL be suggested
