# settings-management Delta Spec

## ADDED Requirements

### Requirement: Notification Preferences UI

The Settings page SHALL include a Notifications section for per-event-type notification preferences.

#### Scenario: Display notification preferences
- **WHEN** the Settings page is loaded
- **THEN** a Notifications section SHALL display toggles for each notification event type
- **AND** each toggle SHALL show the event type name and a brief description

#### Scenario: Toggle event type
- **WHEN** a user toggles a notification event type on or off
- **THEN** the preference SHALL be saved with key `notification.<event_type>` via the settings override API
- **AND** a success toast SHALL be displayed

#### Scenario: Default preferences
- **WHEN** no notification preferences have been set
- **THEN** all event types SHALL default to enabled (`"true"`)

#### Scenario: Source badges
- **WHEN** notification preferences are displayed
- **THEN** each toggle SHALL show a source badge (env/db/default) indicating where the current value comes from

#### Scenario: Reset preference
- **WHEN** a user resets a notification preference
- **THEN** the database override SHALL be removed
- **AND** the default value (`"true"`) SHALL be restored
