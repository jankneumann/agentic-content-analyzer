"""Per-store dump commands, expressed as pure argv builders.

Every function here returns a :class:`Stage` (or a skip reason) and touches
nothing. That is what makes the "no credential in argv" requirement testable as a
property of the code rather than as a property of one mocked call: a test can build
every stage this module can produce and assert no secret appears in any of them,
without a subprocess ever running.

The four adapters share one shape on purpose. Decomposing them into four packages
was attempted at plan time and rejected — they all depend on the same Stage
contract, so splitting them would have produced four packages each waiting on it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlsplit

from src.services.backup.executor import Stage
from src.services.backup.models import (
    SKIP_MANAGED_PROVIDER,
    SKIP_NO_ARTIFACT_DIRECTORIES,
    SKIP_NOT_CONFIGURED,
    StoreName,
)


@dataclass(frozen=True)
class StorePlan:
    """What a store intends to do this run.

    Exactly one of ``stage`` / ``skip_reason`` is set. A store that cannot run says
    so with a named reason rather than producing an empty artifact.
    """

    store: StoreName
    artifact_name: str
    stage: Stage | None = None
    skip_reason: str | None = None
    #: Declared, audited exception to the read-only requirement. Only FalkorDB's
    #: BGSAVE sets this, and it writes a snapshot file — never application data.
    writes_snapshot: bool = False

    @property
    def runnable(self) -> bool:
        return self.stage is not None


def _pg_connection_env(database_url: str) -> tuple[dict[str, str], list[str]]:
    """Split a Postgres URL into env (secret) and argv (not secret).

    ``pg_dump --dbname=postgres://user:pass@host/db`` puts the password in argv,
    where every local user can read it out of /proc for the life of the dump. The
    password goes in ``PGPASSWORD``; everything else is safe on the command line.
    """
    parts = urlsplit(database_url)
    env: dict[str, str] = {}
    argv: list[str] = []
    if parts.password:
        env["PGPASSWORD"] = unquote(parts.password)
    if parts.username:
        argv += ["--username", unquote(parts.username)]
    if parts.hostname:
        argv += ["--host", parts.hostname]
    if parts.port:
        argv += ["--port", str(parts.port)]
    database = parts.path.lstrip("/")
    if database:
        argv += ["--dbname", database]
    return env, argv


def plan_postgres(settings: Any) -> StorePlan:
    """`pg_dump -Fc` — the portable, version-tolerant custom format."""
    database_url = getattr(settings, "database_url", None)
    if not database_url:
        return StorePlan(
            store=StoreName.POSTGRES,
            artifact_name="postgres.dump",
            skip_reason=SKIP_NOT_CONFIGURED,
        )
    env, connection_argv = _pg_connection_env(str(database_url))
    return StorePlan(
        store=StoreName.POSTGRES,
        artifact_name="postgres.dump",
        stage=Stage(
            name="pg_dump",
            argv=(
                "pg_dump",
                "--format=custom",
                "--no-owner",
                "--no-privileges",
                "--compress=0",  # age compresses nothing; rclone streams. Keep one pass.
                *connection_argv,
            ),
            env=env,
        ),
    )


def plan_graphdb(settings: Any) -> StorePlan:
    """Branch on (provider, mode) — design A4.

    `neo4j-admin database dump` requires a stopped database and is impossible
    against AuraDB, which `graphdb_mode: cloud` supports. Rather than emit a
    silently incomplete dump, the managed path records a named skip and the runbook
    points at the provider-native snapshot that covers it.
    """
    provider = str(getattr(settings, "graphdb_provider", "neo4j"))
    mode = str(getattr(settings, "graphdb_mode", "local"))

    if provider == "falkordb":
        host = str(getattr(settings, "falkordb_host", "localhost"))
        port = str(getattr(settings, "falkordb_port", 6379))
        env: dict[str, str] = {}
        password = getattr(settings, "falkordb_password", None)
        if password:
            # redis-cli reads REDISCLI_AUTH from the environment precisely so the
            # password stays out of argv; -a warns about exactly this.
            env["REDISCLI_AUTH"] = str(password)
        return StorePlan(
            store=StoreName.GRAPHDB,
            artifact_name="falkordb.rdb",
            stage=Stage(
                name="redis-cli",
                argv=("redis-cli", "-h", host, "-p", port, "--rdb", "-"),
                env=env,
            ),
            # Declared write exception: --rdb triggers a snapshot. It writes no
            # application data and mutates no key.
            writes_snapshot=True,
        )

    if mode == "cloud":
        return StorePlan(
            store=StoreName.GRAPHDB,
            artifact_name="neo4j.dump",
            skip_reason=SKIP_MANAGED_PROVIDER,
        )

    return StorePlan(
        store=StoreName.GRAPHDB,
        artifact_name="neo4j.dump",
        stage=Stage(
            name="neo4j-admin",
            argv=(
                "neo4j-admin",
                "database",
                "dump",
                str(getattr(settings, "neo4j_database", None) or "neo4j"),
                "--to-stdout",
            ),
        ),
    )


def artifact_directories(settings: Any) -> list[str]:
    """Local directories holding artifacts that exist nowhere else.

    Files on disk that no database row references are included deliberately: an
    orphaned artifact is still the only copy, and a backup that only captures
    referenced files silently loses them.
    """
    candidates = [
        getattr(settings, "image_storage_path", None) or "data/images",
        getattr(settings, "podcast_storage_path", None) or "data/podcasts",
        getattr(settings, "audio_digest_storage_path", None) or "data/audio-digests",
    ]
    seen: list[str] = []
    for candidate in candidates:
        value = str(candidate)
        if value not in seen:
            seen.append(value)
    return seen


def plan_artifacts(settings: Any, *, existing: list[str] | None = None) -> StorePlan:
    """One tar stream over every artifact directory that exists."""
    directories = existing if existing is not None else artifact_directories(settings)
    if not directories:
        return StorePlan(
            store=StoreName.ARTIFACTS,
            artifact_name="artifacts.tar",
            skip_reason=SKIP_NO_ARTIFACT_DIRECTORIES,
        )
    return StorePlan(
        store=StoreName.ARTIFACTS,
        artifact_name="artifacts.tar",
        stage=Stage(
            name="tar",
            argv=("tar", "--create", "--file", "-", *sorted(directories)),
        ),
    )


def plan_openbao(settings: Any) -> StorePlan:
    """`bao operator raft snapshot save -` — streamed, never staged on disk."""
    address = getattr(settings, "bao_addr", None) or getattr(settings, "vault_addr", None)
    token = getattr(settings, "bao_token", None) or getattr(settings, "vault_token", None)
    if not address or not token:
        return StorePlan(
            store=StoreName.OPENBAO,
            artifact_name="openbao.snap",
            skip_reason=SKIP_NOT_CONFIGURED,
        )
    secret = token.get_secret_value() if hasattr(token, "get_secret_value") else str(token)
    return StorePlan(
        store=StoreName.OPENBAO,
        artifact_name="openbao.snap",
        stage=Stage(
            name="bao",
            argv=("bao", "operator", "raft", "snapshot", "save", "-"),
            # BAO_TOKEN is the documented env form. `-token=` would place a root
            # token in argv, readable by every local user.
            env={"BAO_ADDR": str(address), "BAO_TOKEN": secret},
        ),
    )


def plan_all(settings: Any) -> list[StorePlan]:
    """Every store, in a stable order so manifests diff cleanly."""
    return [
        plan_postgres(settings),
        plan_graphdb(settings),
        plan_artifacts(settings),
        plan_openbao(settings),
    ]
