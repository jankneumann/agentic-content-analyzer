## ADDED Requirements

### Requirement: Substack subscription sync writes database source overrides

The system SHALL provide `aca sources sync substack` and `POST /api/v1/sources/sync/substack` that list the operator's Substack subscriptions through the live session and plan database source overrides: a paid publication as a `substack` source and a free publication as an `rss` source at its `/feed` URL. The operation SHALL be a dry run unless `apply` is requested, and SHALL return the same plan in both modes.

#### Scenario: Dry run writes nothing
- **WHEN** the operator runs the sync without `--apply`
- **THEN** the result lists each publication it would add with its type and URL
- **AND** no `source_overrides` row is created or changed

#### Scenario: Apply adds missing publications once
- **WHEN** the operator runs the sync with `--apply`
- **THEN** each subscribed publication with no configured source becomes one override with `managed_by = 'substack-sync'`
- **AND** running it again with the same subscriptions writes nothing

### Requirement: Substack sync never modifies operator-configured sources

A publication already configured in YAML or the database as a `substack` or `rss` source, enabled or disabled, SHALL be left unchanged unless its row is marked `managed_by = 'substack-sync'`. Publications SHALL be matched by host (without `www.`) and path (without a trailing `/` or `/feed`).

#### Scenario: Disabled source stays disabled
- **WHEN** a subscribed publication is configured as a disabled source
- **THEN** the sync reports it as kept disabled and writes nothing for it

#### Scenario: Operator type mismatch is a conflict
- **WHEN** a paid publication is configured by the operator only as an `rss` source
- **THEN** the sync reports a conflict for it and writes nothing for it

#### Scenario: Managed type switch
- **WHEN** a publication the sync added as free becomes paid
- **THEN** applying the sync disables the managed `rss` row and adds a managed `substack` row

### Requirement: Substack sync prunes only its own rows

With `--prune`, the sync SHALL disable enabled overrides marked `managed_by = 'substack-sync'` whose publication is no longer subscribed under that type. It SHALL NOT delete rows and SHALL NOT prune rows without the marker.

#### Scenario: Unsubscribed managed row is disabled
- **WHEN** the operator unsubscribes from a publication the sync added and runs `--apply --prune`
- **THEN** its override is disabled and still present

#### Scenario: Hand-made rows are never pruned
- **WHEN** an override without the marker has no matching subscription
- **THEN** `--prune` leaves it unchanged

### Requirement: Substack sync fails closed

The sync SHALL fail with `credentials_missing` or `session_expired` and the refresh command `aca auth session substack` when the session is missing or rejected, and SHALL refuse to prune when the subscription listing fails or returns no publications.

#### Scenario: Missing session
- **WHEN** no Substack session is configured
- **THEN** the API returns 412 with code `credentials_missing` and the CLI exits non-zero, and nothing is written

#### Scenario: Empty listing never prunes
- **WHEN** the listing returns no publications and `--prune` is requested
- **THEN** the sync refuses and disables nothing
