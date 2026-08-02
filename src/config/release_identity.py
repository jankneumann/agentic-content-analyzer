"""Closed release revision identity shared by runtime and verification paths."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Literal

_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")


ReleaseRevisionSource = Literal["railway_commit_sha", "local_development", "unavailable"]


def release_identity(
    environ: Mapping[str, str] | None = None,
) -> tuple[str, ReleaseRevisionSource]:
    """Return the immutable platform revision and its trusted provenance."""

    values = os.environ if environ is None else environ
    railway_revision = values.get("RAILWAY_GIT_COMMIT_SHA")
    if railway_revision is not None:
        if _COMMIT_SHA.fullmatch(railway_revision):
            return railway_revision, "railway_commit_sha"
        return "unavailable", "unavailable"
    if values.get("GITHUB_SHA") is not None:
        return "unavailable", "unavailable"
    return "development", "local_development"
