#!/usr/bin/python3
"""Fail-closed preflight: every bind mount is usable by the user its container runs as.

Each GX-10 service starts as its image's own user with every capability
dropped, so nothing inside a container can chown its way out of a wrong host
directory. This guard reads the reviewed overlay and, for every ``/srv/aca``
and ``/run/aca/gx10`` bind mount, checks that the host path exists and is
owned (or, for read-only inputs, readable) by that service's ``user:``. It
prints the exact command that fixes each finding and exits non-zero on any.
"""

from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

import yaml

PERSIST_PREFIX = "/srv/aca"
RUNTIME_PREFIX = "/run/aca/gx10"


def service_user(service: dict) -> tuple[int, int]:
    user = service.get("user")
    if not user:
        return 0, 0
    uid, _, gid = str(user).partition(":")
    return int(uid), int(gid or uid)


def bind_mounts(service: dict):
    for volume in service.get("volumes") or []:
        host, _, rest = str(volume).partition(":")
        _, _, options = rest.partition(":")
        yield host, (options or "rw")


def rebase(host: str, persist_root: str, runtime_root: str) -> Path | None:
    if host == PERSIST_PREFIX or host.startswith(PERSIST_PREFIX + "/"):
        return Path(persist_root + host[len(PERSIST_PREFIX) :])
    if host == RUNTIME_PREFIX or host.startswith(RUNTIME_PREFIX + "/"):
        return Path(runtime_root + host[len(RUNTIME_PREFIX) :])
    return None


def readable_by(
    st: os.stat_result, uid: int, gid: int, bit_owner: int, bit_group: int, bit_other: int
) -> bool:
    mode = stat.S_IMODE(st.st_mode)
    if st.st_uid == uid:
        return bool(mode & bit_owner)
    if st.st_gid == gid:
        return bool(mode & bit_group)
    return bool(mode & bit_other)


def check_service(name: str, service: dict, persist_root: str, runtime_root: str) -> list[str]:
    uid, gid = service_user(service)
    errors: list[str] = []
    for host, options in bind_mounts(service):
        path = rebase(host, persist_root, runtime_root)
        if path is None:
            continue
        writable = "ro" not in options.split(",")
        try:
            st = os.stat(path)
        except FileNotFoundError:
            if writable:
                errors.append(
                    f"{name}: {host} is missing; fix: install -d -o {uid} -g {gid} -m 0700 {host}"
                )
            else:
                errors.append(
                    f"{name}: rendered input {host} is missing; run aca-gx10-secrets.service"
                )
            continue
        except PermissionError:
            errors.append(f"{name}: {host} is not inspectable by this preflight; run it as root")
            continue

        if writable:
            if not stat.S_ISDIR(st.st_mode):
                errors.append(f"{name}: {host} must be a directory")
                continue
            if (st.st_uid, st.st_gid) != (uid, gid):
                errors.append(
                    f"{name}: {host} is owned by {st.st_uid}:{st.st_gid}, container runs as {uid}:{gid};"
                    f" fix: install -d -o {uid} -g {gid} -m 0700 {host}"
                )
                continue
            foreign = [child.name for child in path.iterdir() if child.lstat().st_uid != uid]
            if foreign:
                errors.append(
                    f"{name}: {host} holds entries not owned by {uid} ({', '.join(sorted(foreign)[:3])});"
                    f" fix: chown -R {uid}:{gid} {host}"
                )
            continue

        # Read-only rendered inputs: the container user must be able to open them.
        if stat.S_ISDIR(st.st_mode):
            if not readable_by(st, uid, gid, stat.S_IXUSR, stat.S_IXGRP, stat.S_IXOTH):
                errors.append(
                    f"{name}: {host} is not traversable by {uid}:{gid};"
                    f" fix: install -d -o 0 -g {gid} -m 0710 {host}"
                )
                continue
            for child in sorted(path.iterdir()):
                cst = child.lstat()
                if stat.S_ISREG(cst.st_mode) and not readable_by(
                    cst, uid, gid, stat.S_IRUSR, stat.S_IRGRP, stat.S_IROTH
                ):
                    errors.append(
                        f"{name}: {host}/{child.name} is not readable by {uid}:{gid};"
                        " rerun aca-gx10-secrets.service and aca-gx10-proxy-policy.service"
                    )
        elif not readable_by(st, uid, gid, stat.S_IRUSR, stat.S_IRGRP, stat.S_IROTH):
            errors.append(
                f"{name}: {host} is not readable by {uid}:{gid}; rerun aca-gx10-secrets.service"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--compose", default=os.environ.get("GX10_COMPOSE_FILE", "/opt/aca/docker-compose.gx10.yml")
    )
    parser.add_argument(
        "--persist-root", default=os.environ.get("GX10_PERSIST_ROOT", PERSIST_PREFIX)
    )
    parser.add_argument(
        "--runtime-root", default=os.environ.get("GX10_RUNTIME_DIR", RUNTIME_PREFIX)
    )
    parser.add_argument("--service", action="append", help="limit to these services (repeatable)")
    args = parser.parse_args(argv)

    with open(args.compose, encoding="utf-8") as handle:
        compose = yaml.safe_load(handle)
    services = compose["services"]
    selected = args.service or sorted(services)
    unknown = [name for name in selected if name not in services]
    if unknown:
        print(f"gx10 preflight: unknown service(s) {', '.join(unknown)}", file=sys.stderr)
        return 64

    errors: list[str] = []
    for name in selected:
        errors.extend(check_service(name, services[name], args.persist_root, args.runtime_root))
    for error in errors:
        print(f"gx10 persistence preflight: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"gx10 persistence ownership verified for {len(selected)} service(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
