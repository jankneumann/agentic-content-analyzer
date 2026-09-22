## ADDED Requirements

### Requirement: Bounded On-Demand Refresh

The OpenBao module SHALL offer an on-demand refresh that re-reads the configured KV
v2 secret and atomically replaces the in-memory cache, for both token and AppRole
authentication. It SHALL reuse the client authenticated at load time, SHALL
re-authenticate and retry at most once when the read fails, and SHALL read at most
once per caller-supplied minimum interval process-wide, counting every fetch attempt
(initial load, token-manager refresh, earlier on-demand refreshes, failed or not).
A failed refresh SHALL keep the previous cache, SHALL log only the exception type,
and SHALL NOT raise.

#### Scenario: Token auth refresh
- **WHEN** OpenBao uses `BAO_TOKEN` auth, the KV secret changes, and a refresh is requested outside the interval
- **THEN** the cache holds the new values and no new hvac client was constructed

#### Scenario: Burst of refresh requests
- **WHEN** ten threads request a refresh with a 60-second interval at the same moment, 120 seconds after the last fetch
- **THEN** exactly one KV read is performed and exactly one caller reports a reload

#### Scenario: Refresh right after boot is throttled
- **WHEN** a refresh with a 60-second interval is requested 30 seconds after the initial load
- **THEN** no KV read is performed and the call reports no reload

#### Scenario: Expired AppRole token
- **WHEN** the first read of an on-demand refresh fails
- **THEN** the module re-authenticates via AppRole once and retries the read once

### Requirement: Local Write-Back Updates the Cache

After this process writes keys to OpenBao through the secret sink, the OpenBao
module SHALL merge those keys into the in-memory cache by building a new dictionary
and swapping the reference under the cache lock, without reading OpenBao. Cache
fetch-and-swap by the token manager and by on-demand refresh SHALL hold the same
lock, so a read that began before the write cannot overwrite the merged values.

#### Scenario: Written ct0 is visible immediately
- **WHEN** the process applies a local write of `X_CT0`
- **THEN** the next resolution of `X_CT0` returns the new value with no KV read
- **AND** every other cached key is unchanged
- **AND** a snapshot taken before the write still shows the old value
