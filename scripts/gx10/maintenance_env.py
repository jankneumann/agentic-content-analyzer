"""The environment a GX-10 maintenance helper is allowed to inherit.

The host maintenance scripts shell out to helpers that drive rootful Podman.
Passing only ``PATH`` is deliberate, so a helper never inherits this process's
credentials. But those helpers call podman-compose, which parses the overlay
on every call, and the overlay makes the application image and the reviewed
digests mandatory. With ``PATH`` alone every container-touching producer died
on "set a reviewed application tag@sha256 digest" before reaching a store,
while the one component that merely tars a directory succeeded.

Image references are public by definition and live in their own root-owned
file. Everything else in the process environment, the database URL included,
stays behind.
"""

from __future__ import annotations

import os

_FORWARDED_SUFFIXES = ("_IMAGE", "_DIGEST")


def component_environment() -> dict[str, str]:
    """PATH plus the GX-10 image pins podman-compose needs to parse the overlay."""

    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    for name, value in os.environ.items():
        if name.startswith("GX10_") and name.endswith(_FORWARDED_SUFFIXES):
            environment[name] = value
    return environment
