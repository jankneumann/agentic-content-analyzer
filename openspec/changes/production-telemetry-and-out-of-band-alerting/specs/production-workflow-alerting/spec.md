# production-workflow-alerting Specification

## ADDED Requirements

### Requirement: Terminal outcomes use a closed classification policy

The system SHALL classify committed terminal evidence from canonical lifecycle
state and strict typed persisted results using the closed
`success|partial|zero_items|cancelled|failed|unknown|reconciled` outcome set.
Lifecycle failure and cancellation SHALL take precedence over stored result
claims. The classifier SHALL NOT infer a typed ingestion or pipeline outcome
from legacy free-form payloads.

#### Scenario: Completed ingestion has a partial typed result

- **WHEN** an ingestion operation commits `completed` with a valid V2 result
  whose outcome is `partial`
- **THEN** its terminal event SHALL classify as `partial` with warning severity
- **AND** it SHALL be eligible for external delivery

#### Scenario: Completed ingestion has no valid typed result

- **WHEN** an ingestion operation commits `completed` without a valid V2 result
- **THEN** its terminal event SHALL classify as `unknown` with warning severity
- **AND** no raw or inferred result fields SHALL enter the alert envelope

#### Scenario: Lifecycle state contradicts a stored result

- **WHEN** an operation commits `failed` or `cancelled` while its stored result
  claims success
- **THEN** the committed lifecycle state SHALL determine `failed` or
  `cancelled`, respectively

#### Scenario: Successful and cancelled work is observed

- **WHEN** work classifies as `success` or `cancelled`
- **THEN** structured telemetry SHALL be emitted at info severity
- **AND** no external delivery SHALL be created

### Requirement: External alert envelopes are closed and safe

Every external delivery SHALL validate against version 1 of the checked-in
alert-envelope schema. Construction SHALL be allowlist-first and SHALL exclude
operation input, arbitrary result fields, checkpoints, problem detail, raw
errors, natural source keys, content, email addresses, prompts, arbitrary URLs,
headers, and secrets. Every string, collection, and serialized envelope SHALL
have a finite schema bound.

#### Scenario: Typed ingestion evidence contains hostile diagnostics

- **WHEN** a terminal result contains a secret, email address, natural source
  locator, URL, or user content in a diagnostic or extension field
- **THEN** none of those values SHALL appear in the external envelope, logs,
  telemetry attributes, delivery error state, or verification evidence
- **AND** only opaque source keys, bounded counts, and allowlisted codes MAY be
  projected

#### Scenario: An unexpected field is presented to the envelope

- **WHEN** envelope validation receives a field outside the versioned schema
- **THEN** validation SHALL fail closed before any sink invocation

### Requirement: Diagnostic links are constructed from trusted components

An external envelope SHALL contain one absolute same-origin diagnostic URL
constructed from a configured trusted origin and an allowlisted route. The
origin SHALL contain no userinfo, path, query, or fragment and SHALL use HTTPS
outside explicit development/test mode. Routes SHALL reject traversal, encoded
separators, query, fragment, and caller-supplied URLs.

#### Scenario: An operation event receives a valid origin

- **WHEN** a positive operation ID is projected with a valid trusted origin
- **THEN** the diagnostic URL SHALL be exactly the origin plus
  `/api/v1/operations/{operation_id}`

#### Scenario: Link input contains an untrusted component

- **WHEN** the origin or route contains userinfo, a query, a fragment,
  traversal, an encoded separator, or a non-HTTPS production scheme
- **THEN** event projection SHALL fail closed
- **AND** the untrusted value SHALL NOT be logged

### Requirement: Webhook delivery is durable and attempt-aware

The system SHALL persist one delivery per terminal event and configured sink,
claim due deliveries with recoverable leases and `SKIP LOCKED`, and send the
same stable idempotency key on every retry. It SHALL treat 2xx as success;
408, 429, 5xx, timeouts, and connection failures as retryable; and other 4xx
responses as permanent. Retry delay, `Retry-After`, attempts, lease age, and
retention SHALL be bounded.

#### Scenario: A transient delivery fails and then succeeds

- **WHEN** a webhook returns a retryable response and later returns 2xx
- **THEN** the delivery SHALL persist a bounded next-attempt time
- **AND** every attempt SHALL use the same envelope and idempotency key
- **AND** the receiver contract SHALL collapse the attempts into one
  notification

#### Scenario: A worker dies around an ambiguous response

- **WHEN** a delivery lease expires without a persisted success result
- **THEN** another worker SHALL recover the delivery after the lease
- **AND** it SHALL reuse the original idempotency key

#### Scenario: Delivery reaches its retry ceiling

- **WHEN** the configured attempt or age ceiling is reached
- **THEN** the delivery SHALL become exhausted with a closed error code
- **AND** local telemetry SHALL expose exhaustion without recursively creating
  another external alert

### Requirement: Webhook configuration and transport fail closed

Webhook alerting SHALL default to disabled. Enabling it SHALL require a valid
trusted origin, HTTPS endpoint, outbound host policy, and bounded transport
settings. Sink secrets SHALL be resolved through environment/profile/secret
providers and SHALL NOT be stored or returned by generic database-backed
settings. The client SHALL disable redirects and reject credentials and
disallowed loopback, private, link-local, or metadata destinations.

#### Scenario: Webhook alerting is disabled

- **WHEN** terminal evidence is committed while the sink is `noop`
- **THEN** telemetry processing SHALL continue
- **AND** no network request SHALL occur

#### Scenario: Webhook configuration is unsafe

- **WHEN** an enabled endpoint violates scheme, credential, redirect, address,
  or host policy
- **THEN** startup or delivery SHALL fail closed with a safe code
- **AND** the endpoint and secret SHALL NOT be logged or persisted

### Requirement: Alert routing bounds operation graph noise

The system SHALL emit telemetry for every terminal operation event but SHALL
route at most one aggregate external alert for a pipeline graph outcome when a
terminal root can represent its children. A terminal child without such a root
MAY be delivered independently. Event and delivery identities SHALL include the
operation attempt so retries remain distinct without duplicating an attempt.

#### Scenario: Multiple pipeline children fail

- **WHEN** child operations fail and a terminal pipeline root records their
  aggregate partial or failed outcome
- **THEN** child telemetry SHALL remain observable
- **AND** external child deliveries SHALL be suppressed in favor of one bounded
  root alert

#### Scenario: A retried operation fails again

- **WHEN** an operation has a second claim generation that reaches failure
- **THEN** it SHALL produce a new terminal event identity
- **AND** replay of either generation SHALL NOT create a duplicate delivery for
  that generation

### Requirement: Staging verification is sanitized and correlated

The repository SHALL provide a bounded staging verification that correlates a
controlled persisted terminal operation, its terminal event/classification,
and one idempotent receiver receipt. Checked-in evidence SHALL validate against
a versioned schema and exclude endpoints, headers, bodies, errors, operation
input/result, source locators, user content, and secrets.

#### Scenario: Controlled staging alert arrives

- **WHEN** the verifier creates an alert-eligible controlled outcome and the
  receiver acknowledges it within the deadline
- **THEN** evidence SHALL record opaque operation/attempt and event IDs,
  outcome/severity, bounded timestamps, a hashed receipt ID, delivery count,
  and successful redaction assertions

#### Scenario: Staging receipt is missing or duplicated

- **WHEN** no matching receipt arrives or the receiver reports more than one
  notification for the idempotency key
- **THEN** verification SHALL fail non-zero
- **AND** it SHALL NOT print sink credentials or payload bodies
