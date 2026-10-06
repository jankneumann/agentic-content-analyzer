## ADDED Requirements

### Requirement: Auth Commands Push Tokens Through A Secret Sink

`aca auth gmail` and `aca auth youtube` SHALL accept `--to railway|bao|secrets-file`
to push the freshly obtained OAuth token (and, with `--include-credentials`, the
OAuth client JSON) to the selected secret sink after the login flow. Without `--to`
or `--deploy` the commands SHALL save the token locally only and push nothing. The
sink abstraction SHALL be provider-agnostic: a provider contributes only its env-var
names. Sinks SHALL accept a mapping of `KEY -> value` and SHALL print only key names
and the target, never a value, on stdout, stderr, or in logs.

#### Scenario: YouTube uses the same sinks as Gmail
- **WHEN** `aca auth youtube --to bao --include-credentials` completes
- **THEN** `YOUTUBE_OAUTH_TOKEN_JSON` and `YOUTUBE_CREDENTIALS_JSON` are written with no YouTube-specific sink code

#### Scenario: Secrets-file sink preserves other keys and permissions
- **WHEN** `aca auth gmail --to secrets-file` updates `.secrets.yaml` (or the file named by `SECRETS_FILE`)
- **THEN** only `GMAIL_OAUTH_TOKEN_JSON` changes and every other key keeps its value
- **AND** comments are kept whenever the file can be edited in place
- **AND** the file is written atomically with mode 0600

#### Scenario: Default pushes nothing
- **WHEN** `aca auth gmail` runs without `--to` or `--deploy`
- **THEN** no sink is constructed and the output names `--to railway|bao|secrets-file` as the way to push

#### Scenario: No value is printed
- **WHEN** any sink writes a token
- **THEN** the command output and captured logs contain the key name but not the token value

### Requirement: Deprecated Deploy Flag Aliases The Railway Sink

`--deploy` SHALL remain for one release as a deprecated alias for `--to railway`,
producing the same `railway variables --set` invocations, and SHALL print a
deprecation warning to stderr. Combining `--deploy` with `--to` naming another sink,
or `--service` with a non-Railway sink, SHALL exit 2 before the login flow starts.

#### Scenario: Deploy flag matches the Railway sink
- **WHEN** `aca auth gmail --deploy --service api` and `aca auth gmail --to railway --service api` run against a mocked `railway` CLI
- **THEN** both issue identical `railway variables --set GMAIL_OAUTH_TOKEN_JSON=... --service api` calls
- **AND** only the `--deploy` run prints a deprecation warning on stderr naming `--to railway`

#### Scenario: Conflicting flags
- **WHEN** `aca auth gmail --deploy --to bao` runs
- **THEN** the command exits 2 and the OAuth flow is never started
