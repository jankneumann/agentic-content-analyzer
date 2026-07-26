"""Resolve the backend target the discovery and validation scenarios need.

`src/cli/workflow_commands.py` is, in its own words, "backed exclusively by the HTTP
API". There is no `--direct` path for the canonical workflow surface, so `capabilities`,
`configured-sources`, and `operations list` exit 1 with "Workflow API unavailable" when
nothing is listening. Roughly a quarter of the checked-in suite therefore needs a
reachable backend, and the gate has to decide what to do when there is not one.

It applies the same rule it applies to the runner, for the same reason: **never report a
missing prerequisite as success.** A run that quietly drops the scenarios needing a
target reports a pass rate over whatever remained, and the number looks identical to a
run that covered everything. That is the defect this whole roadmap item exists to
remove, and it does not become acceptable just because the missing piece is a server
rather than a runner.

Two design choices are worth stating because the obvious alternatives are worse.

**Why not gen-eval's `startup` block.** The framework can own service lifecycle: give it
`command`, `health_check`, and `teardown` and it boots what it needs. Rejected on the
teardown. `teardown` is mandatory when `startup` is present and runs unconditionally, so
an evaluation run would stop whatever backend the developer already had going — a gate
that breaks your dev stack as a side effect gets disabled by its users. It also cannot
supply Postgres, so it would only ever solve half the problem.

**Why probe `/health` rather than the CLI.** Using `aca capabilities` as the probe is
tempting: it needs no URL resolution and tests exactly what the scenarios do. But it
puts a command under test inside the gate's own precondition check, so a genuine bug in
`capabilities` — a 500, a serialization regression — would be classified "target
unreachable" and refused rather than surfacing as the failing scenario it is. The probe
must not be part of the suite. So the URL is resolved from the same settings the CLI
reads (no second source of truth) and `/health` is probed instead (not under test).
"""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

# Scenarios tagged this way need a reachable backend; those tagged `no-target` do not.
# gen-eval's category filter also matches tags, so `--categories no-target` selects
# exactly the hermetic subset — which is what `--offline` below exploits.
REQUIRES_TARGET_TAG = "requires-target"
NO_TARGET_TAG = "no-target"

PROBE_PATH = "/health"
PROBE_TIMEOUT_SECONDS = 5.0


class TargetState(StrEnum):
    REACHABLE = "reachable"
    ABSENT = "absent"
    UNREACHABLE = "unreachable"


@dataclass(frozen=True)
class TargetResolution:
    state: TargetState
    base_url: str | None
    detail: str

    @property
    def ok(self) -> bool:
        return self.state is TargetState.REACHABLE


def resolve_base_url(env: Mapping[str, str] | None = None) -> tuple[str | None, str]:
    """Resolve the base URL the CLI itself will use.

    Deliberately reads the project's settings rather than an evaluation-specific
    variable. If the gate probed one URL while the CLI dialled another, a green probe
    would prove nothing about the scenarios that follow.
    """
    try:
        from src.config.settings import get_settings

        base_url = str(get_settings().api_base_url).rstrip("/")
    except Exception as exc:
        return None, f"settings resolution failed ({exc.__class__.__name__}: {exc})"
    if not base_url:
        return None, "settings resolved an empty api_base_url"
    return base_url, f"api_base_url={base_url}"


def probe(base_url: str, timeout: float = PROBE_TIMEOUT_SECONDS) -> tuple[bool, str]:
    """Probe the target's health endpoint. Returns (reachable, detail)."""
    url = f"{base_url}{PROBE_PATH}"
    request = urllib.request.Request(url, method="GET")  # noqa: S310 - scheme is from settings
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            status = int(response.status)
    except urllib.error.HTTPError as exc:
        return False, f"{url} responded {exc.code}"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        return False, f"{url} is not answering ({reason})"
    if 200 <= status < 300:
        return True, f"{url} responded {status}"
    return False, f"{url} responded {status}"


def resolve(env: Mapping[str, str] | None = None) -> TargetResolution:
    base_url, detail = resolve_base_url(env)
    if base_url is None:
        return TargetResolution(TargetState.ABSENT, None, detail)
    reachable, probe_detail = probe(base_url)
    if reachable:
        return TargetResolution(TargetState.REACHABLE, base_url, probe_detail)
    return TargetResolution(TargetState.UNREACHABLE, base_url, probe_detail)
