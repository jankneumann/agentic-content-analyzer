#!/usr/bin/env python3
"""Active GX-10 role readiness: local dependencies, exporter, and proxy policy."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from time import monotonic
from urllib.request import ProxyHandler, Request, build_opener

# Podman gives this probe five seconds and runs it every ten, for four roles.
# A probe that cannot answer inside its own budget is a failing probe, so it
# spends the budget rather than letting one hung dependency stretch past it.
BUDGET_SECONDS = 4.0
STEP_SECONDS = 1.5

CORE_DEPENDENCIES = (
    ("app-postgres", 5432),
    ("redis", 6379),
    ("langfuse-web", 3000),
    ("openbao", 8200),
    ("squid", 3128),
    ("falkordb", 6379),
)
ROLE_DEPENDENCIES = {
    "api": CORE_DEPENDENCIES,
    "worker": CORE_DEPENDENCIES,
    "scheduler": CORE_DEPENDENCIES,
    "maintenance": CORE_DEPENDENCIES,
}


def get(url: str, *, timeout: float) -> bytes:
    opener = build_opener(ProxyHandler({}))
    # All callers pass the fixed HTTP GX-10 health endpoints below.
    with opener.open(
        Request(url, headers={"User-Agent": "aca-gx10-readiness"}),  # noqa: S310
        timeout=timeout,
    ) as response:
        if response.status >= 400:
            raise RuntimeError(f"HTTP {response.status}")
        return bytes(response.read(65536))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--role", required=True, choices=("api", "worker", "scheduler", "maintenance")
    )
    args = parser.parse_args()
    deadline = monotonic() + BUDGET_SECONDS

    def remaining() -> float:
        left = deadline - monotonic()
        if left <= 0:
            raise TimeoutError("readiness budget exhausted")
        return min(left, STEP_SECONDS)

    try:
        for host, port in ROLE_DEPENDENCIES[args.role]:
            with socket.create_connection((host, port), timeout=remaining()):
                pass
        health = json.loads(
            get(
                "http://openbao:8200/v1/sys/health?standbyok=true&perfstandbyok=true",
                timeout=remaining(),
            )
        )
        if not health.get("initialized") or health.get("sealed"):
            raise RuntimeError("OpenBao not ready")
        get("http://langfuse-web:3000/api/public/health", timeout=remaining())
        # Configuration only. Proving egress means a TLS handshake with a site
        # on the internet, and doing that per role every ten seconds made the
        # probe slower than its own timeout: the four roles flapped between
        # healthy and unhealthy roughly half the time. Squid's own healthcheck
        # already performs that handshake, and squid:3128 is in the list above,
        # so an egress outage still reaches these roles.
        if not os.environ.get("HTTPS_PROXY"):
            raise RuntimeError("authenticated proxy missing")
    except Exception as exc:
        print(f"gx10 {args.role} readiness denied: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
