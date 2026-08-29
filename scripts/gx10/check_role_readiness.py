#!/usr/bin/env python3
"""Active GX-10 role readiness: local dependencies, exporter, and proxy policy."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from urllib.request import ProxyHandler, Request, build_opener

CORE_DEPENDENCIES = (
    ("app-postgres", 5432),
    ("redis", 6379),
    ("langfuse-web", 3000),
    ("openbao", 8200),
    ("squid", 3128),
)
ROLE_DEPENDENCIES = {
    "api": (*CORE_DEPENDENCIES, ("neo4j", 7687)),
    "worker": (*CORE_DEPENDENCIES, ("neo4j", 7687)),
    "scheduler": CORE_DEPENDENCIES,
    "maintenance": (*CORE_DEPENDENCIES, ("neo4j", 7687)),
}


def get(url: str, *, proxy: bool = False) -> bytes:
    opener = build_opener() if proxy else build_opener(ProxyHandler({}))
    # All callers pass the fixed HTTP(S) GX-10 health/proxy endpoints below.
    with opener.open(
        Request(url, headers={"User-Agent": "aca-gx10-readiness"}),  # noqa: S310
        timeout=5,
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
    try:
        for host, port in ROLE_DEPENDENCIES[args.role]:
            with socket.create_connection((host, port), timeout=3):
                pass
        health = json.loads(
            get("http://openbao:8200/v1/sys/health?standbyok=true&perfstandbyok=true")
        )
        if not health.get("initialized") or health.get("sealed"):
            raise RuntimeError("OpenBao not ready")
        get("http://langfuse-web:3000/api/public/health")
        if not os.environ.get("HTTPS_PROXY"):
            raise RuntimeError("authenticated proxy missing")
        get("https://api.github.com/", proxy=True)
    except Exception as exc:
        print(f"gx10 {args.role} readiness denied: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
