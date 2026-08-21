"""Prerequisite checks that run BEFORE anything is contacted.

Design A6.4: the missing-binary preflight was originally attached only to `verify`,
which the timer deliberately does not invoke. `run` — the only path that ever
executes unattended — had none, so a missing `age` on the host would have been
discovered mid-run, after `pg_dump` had already read a production database.

`run` therefore performs the binary subset of this check first. `verify` performs
the whole of it, including the decryption identity, because verify is the path an
operator invokes to answer "could I actually restore from this?".
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass

from src.services.backup.stores import StorePlan


@dataclass(frozen=True)
class PreflightReport:
    missing_binaries: tuple[str, ...] = ()
    missing_settings: tuple[str, ...] = ()
    #: Populated by `verify` only; `run` never needs — and must never hold — the
    #: decryption identity.
    identity_problem: str | None = None

    @property
    def ok(self) -> bool:
        return not (self.missing_binaries or self.missing_settings or self.identity_problem)

    def describe(self) -> str:
        parts: list[str] = []
        if self.missing_binaries:
            parts.append("missing binaries: " + ", ".join(self.missing_binaries))
        if self.missing_settings:
            parts.append("missing settings: " + ", ".join(self.missing_settings))
        if self.identity_problem:
            parts.append(self.identity_problem)
        return "; ".join(parts)


#: Always needed: everything that runs regardless of which stores are configured.
BASE_BINARIES: tuple[str, ...] = ("age", "rclone", "tee", "sha256sum", "wc")


def required_binaries(plans: list[StorePlan]) -> tuple[str, ...]:
    """Only the binaries this run will actually invoke.

    A deployment with no OpenBao must not be told to install `bao`. Naming
    irrelevant prerequisites is how a preflight becomes noise operators route
    around.
    """
    names = list(BASE_BINARIES)
    for plan in plans:
        if plan.stage is not None and plan.stage.program not in names:
            names.append(plan.stage.program)
    return tuple(names)


def check_binaries(names: tuple[str, ...], *, which: object = None) -> tuple[str, ...]:
    resolver = which or shutil.which
    return tuple(name for name in names if resolver(name) is None)  # type: ignore[operator]


def check_run_prerequisites(
    settings: object,
    plans: list[StorePlan],
    *,
    which: object = None,
) -> PreflightReport:
    """The `run` preflight: binaries and settings only, never the identity."""
    missing_settings: list[str] = []
    if not getattr(settings, "backup_s3_bucket", None):
        missing_settings.append("BACKUP_S3_BUCKET")
    if not getattr(settings, "backup_age_recipient", None):
        missing_settings.append("BACKUP_AGE_RECIPIENT")
    return PreflightReport(
        missing_binaries=check_binaries(required_binaries(plans), which=which),
        missing_settings=tuple(missing_settings),
    )
