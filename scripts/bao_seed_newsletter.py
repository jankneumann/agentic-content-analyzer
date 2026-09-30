#!/usr/bin/env python3
"""Seed OpenBao with newsletter-aggregator secrets.

Reads ``.secrets.yaml`` from the project root and writes all secrets to
OpenBao KV v2 under the ``newsletter`` path (configurable).  Optionally
creates an AppRole for the application and configures a database secrets
engine for dynamic PostgreSQL credentials.

Central deployment pattern::

    secret/coordinator/*    -> agent-coordinator
    secret/newsletter/*     -> this project
    secret/shared/*         -> cross-project keys

Usage::

    # Dry run
    BAO_ADDR=http://localhost:8200 BAO_TOKEN=dev-root-token \\
        python scripts/bao_seed_newsletter.py --dry-run

    # Seed secrets
    BAO_ADDR=http://localhost:8200 BAO_TOKEN=dev-root-token \\
        python scripts/bao_seed_newsletter.py

    # Full setup: secrets + shared keys + AppRole + dynamic DB
    BAO_ADDR=http://localhost:8200 BAO_TOKEN=dev-root-token \\
        POSTGRES_DSN=postgresql://newsletter_user:newsletter_password@localhost:5432/newsletters \\
        python scripts/bao_seed_newsletter.py \\
            --shared-keys ANTHROPIC_API_KEY,OPENAI_API_KEY \\
            --with-approle --with-db-engine

    # Session-credential roles: patch-only workstation role, and read+patch
    # for the app/worker role (implies --with-approle)
    BAO_ADDR=http://localhost:8200 BAO_TOKEN=dev-root-token \\
        python scripts/bao_seed_newsletter.py --with-session-roles

Environment variables:
    BAO_ADDR:        OpenBao server URL (required)
    BAO_TOKEN:       Root/admin token for seeding (required)
    BAO_MOUNT_PATH:  KV v2 mount path (default: "secret")
    BAO_SECRET_PATH: Secret data path (default: "newsletter")
    BAO_TOKEN_TTL:   newsletter-app token TTL in seconds (default: 3600)
    POSTGRES_DSN:    PostgreSQL DSN for database engine (with --with-db-engine)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


def _repo_root() -> Path:
    """Find the repository root."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path(__file__).parent,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        pass
    return Path(__file__).resolve().parent.parent


REPO_ROOT = _repo_root()
DEFAULT_SECRETS_PATH = REPO_ROOT / ".secrets.yaml"


def _get_client():  # type: ignore[no-untyped-def]
    """Create an hvac client authenticated with the root/admin token."""
    import hvac  # type: ignore[import-untyped]

    addr = os.environ.get("BAO_ADDR")
    token = os.environ.get("BAO_TOKEN")

    if not addr:
        print("ERROR: BAO_ADDR environment variable is required", file=sys.stderr)
        sys.exit(1)
    if not token:
        print("ERROR: BAO_TOKEN environment variable is required", file=sys.stderr)
        sys.exit(1)

    client = hvac.Client(url=addr, token=token)
    if not client.is_authenticated():
        print(
            f"ERROR: Authentication failed at {addr} -- check BAO_TOKEN",
            file=sys.stderr,
        )
        sys.exit(1)

    return client


def seed_secrets(
    client: Any,
    secrets_path: Path,
    mount_path: str,
    secret_path: str,
    dry_run: bool = False,
) -> dict[str, str]:
    """Write secrets from .secrets.yaml to OpenBao KV v2.

    Returns:
        The secrets dict that was written (for shared-key extraction).
    """
    if not secrets_path.is_file():
        print(f"ERROR: {secrets_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(secrets_path) as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict):
        print(f"ERROR: {secrets_path} is not a valid YAML mapping", file=sys.stderr)
        sys.exit(1)

    secrets = {k: v for k, v in data.items() if isinstance(v, str)}

    if dry_run:
        print(f"[DRY RUN] Would write {len(secrets)} secrets to {mount_path}/{secret_path}:")
        for key in sorted(secrets):
            print(f"  - {key}")
        return secrets

    client.secrets.kv.v2.create_or_update_secret(
        path=secret_path,
        secret=secrets,
        mount_point=mount_path,
    )
    print(f"Wrote {len(secrets)} secrets to {mount_path}/{secret_path}:")
    for key in sorted(secrets):
        print(f"  - {key}")

    return secrets


def seed_shared_keys(
    client: Any,
    secrets: dict[str, str],
    shared_keys: list[str],
    mount_path: str,
    dry_run: bool = False,
) -> None:
    """Write selected keys to the shared path for cross-project access.

    Merge semantics: newsletter values win on key conflicts, but keys
    from other projects are preserved.
    """
    shared_path = "shared"
    shared_secrets = {k: secrets[k] for k in shared_keys if k in secrets}

    missing = set(shared_keys) - set(shared_secrets)
    if missing:
        print(
            f"WARNING: keys not found in .secrets.yaml: {', '.join(sorted(missing))}",
            file=sys.stderr,
        )

    if not shared_secrets:
        print("No shared keys to write.")
        return

    if dry_run:
        print(
            f"[DRY RUN] Would write {len(shared_secrets)} shared keys "
            f"to {mount_path}/{shared_path}:"
        )
        for key in sorted(shared_secrets):
            print(f"  - {key}")
        return

    # Read existing shared secrets first (merge, don't overwrite)
    try:
        existing = client.secrets.kv.v2.read_secret_version(
            path=shared_path,
            mount_point=mount_path,
        )
        existing_data = existing.get("data", {}).get("data", {})
    except Exception:
        existing_data = {}

    # Newsletter values win on conflict; other projects' keys preserved
    merged = {**existing_data, **shared_secrets}
    client.secrets.kv.v2.create_or_update_secret(
        path=shared_path,
        secret=merged,
        mount_point=mount_path,
    )
    print(
        f"Wrote {len(shared_secrets)} shared keys to {mount_path}/{shared_path} "
        f"(merged with {len(existing_data)} existing):"
    )
    for key in sorted(shared_secrets):
        print(f"  - {key}")


# ---------------------------------------------------------------------------
# Policies and AppRoles
# ---------------------------------------------------------------------------
#
# Capability matrix on ``<mount>/data/<secret_path>`` (default
# ``secret/data/newsletter``), which is the only path any of these touch
# besides the existing shared read:
#
#   policy                       read   patch   create/update   delete/destroy/list
#   newsletter-read              yes    --      --              --
#   newsletter-worker            yes    yes     --              --
#   newsletter-session-writer    --     yes     --              --
#
# ``patch`` is the KV v2 server-side merge (HTTP PATCH with
# ``application/merge-patch+json``). It is deliberately NOT hvac's
# ``kv.v2.patch()``, which is a client-side ``read_secret_version`` followed by
# ``create_or_update_secret`` and would need ``read`` + ``update``; see
# ``src/cli/secret_sinks.py`` (``BaoSink``).

READ_POLICY = "newsletter-read"
APP_ROLE = "newsletter-app"
WORKER_POLICY = "newsletter-worker"
WORKSTATION_POLICY = "newsletter-session-writer"
WORKSTATION_ROLE = "newsletter-workstation"

# Workstation tokens only live long enough for one ``aca auth ... --to bao``.
WORKSTATION_TOKEN_TTL = "900s"
WORKSTATION_TOKEN_MAX_TTL = "3600s"
# A leaked workstation secret-id stops working after 90 days; re-issue it with
# the wrapped secret-id command printed below.
WORKSTATION_SECRET_ID_TTL = "2160h"


def _render_policy(rules: list[tuple[str, list[str]]]) -> str:
    """Render ``(path, capabilities)`` pairs as deterministic OpenBao HCL."""
    blocks = []
    for path, capabilities in rules:
        caps = ", ".join(f'"{cap}"' for cap in capabilities)
        blocks.append(f'path "{path}" {{\n  capabilities = [{caps}]\n}}\n')
    return "".join(blocks)


def _data_path(mount_path: str, secret_path: str) -> str:
    return f"{mount_path.strip('/')}/data/{secret_path.strip('/')}"


def read_policy_hcl(mount_path: str, secret_path: str) -> str:
    """HCL for ``newsletter-read``: read the app secret and the shared keys."""
    return _render_policy(
        [
            (_data_path(mount_path, secret_path), ["read"]),
            (_data_path(mount_path, "shared"), ["read"]),
        ]
    )


def worker_policy_hcl(mount_path: str, secret_path: str) -> str:
    """HCL for ``newsletter-worker``: read plus server-side patch on the app secret.

    Lets adapters persist a rotated cookie (e.g. X ``ct0``) without being able
    to replace, delete, or destroy the secret.
    """
    return _render_policy([(_data_path(mount_path, secret_path), ["read", "patch"])])


def workstation_policy_hcl(mount_path: str, secret_path: str) -> str:
    """HCL for ``newsletter-session-writer``: patch only, no read.

    The workstation pushes browser-session cookies and OAuth tokens but can
    never read the LLM keys stored alongside them.
    """
    return _render_policy([(_data_path(mount_path, secret_path), ["patch"])])


def _ensure_policy(client: Any, name: str, hcl: str) -> str:
    """Write policy ``name`` unless it already holds exactly ``hcl``.

    Returns ``"created"``, ``"updated"`` or ``"unchanged"`` so re-runs can be
    shown to be idempotent.
    """
    current = None
    try:
        resp = client.sys.read_policy(name=name)
        if isinstance(resp, dict):
            current = resp.get("rules") or (resp.get("data") or {}).get("rules")
    except Exception:  # a missing policy raises hvac InvalidPath
        current = None

    if isinstance(current, str) and current.strip() == hcl.strip():
        status = "unchanged"
    else:
        client.sys.create_or_update_policy(name=name, policy=hcl)
        status = "updated" if isinstance(current, str) else "created"
    print(f"Policy {name}: {status}")
    return status


def _ensure_approle_auth(client: Any) -> None:
    auth_methods = client.sys.list_auth_methods()
    if "approle/" not in auth_methods:
        client.sys.enable_auth_method("approle")
        print("Enabled AppRole auth method")


def _existing_role_policies(client: Any, role_name: str) -> list[str]:
    """Return the role's current ``token_policies`` or ``[]`` if it does not exist."""
    try:
        resp = client.auth.approle.read_role(role_name=role_name)
    except Exception:  # a missing role raises hvac InvalidPath
        return []
    policies = resp.get("data", {}).get("token_policies") if isinstance(resp, dict) else None
    if not isinstance(policies, list):
        return []
    return [p for p in policies if isinstance(p, str)]


def _print_role_id(client: Any, role_name: str, metadata: str) -> None:
    """Print the (non-secret) role_id and how to mint a secret_id.

    The secret_id itself is never generated or printed here.
    """
    role_id_resp = client.auth.approle.read_role_id(role_name=role_name)
    role_id = role_id_resp.get("data", {}).get("role_id", "")
    print(f"  Role ID: {role_id}")
    print("  Generate a secret ID with:")
    print(f"    bao write auth/approle/role/{role_name}/secret-id \\")
    print(f'      metadata="{metadata}"')


def seed_approle(
    client: Any,
    mount_path: str,
    secret_path: str,
    token_ttl: int,
    dry_run: bool = False,
    extra_policies: tuple[str, ...] = (),
) -> None:
    """Create the AppRole for the newsletter application (API + worker).

    ``extra_policies`` is how ``--with-session-roles`` attaches
    ``newsletter-worker``. A plain ``--with-approle`` re-run keeps an already
    attached ``newsletter-worker`` instead of silently revoking the worker's
    patch right.
    """
    role_name = APP_ROLE
    policy_name = READ_POLICY
    policy_hcl = read_policy_hcl(mount_path, secret_path)

    if dry_run:
        print(f"[DRY RUN] Would create policy '{policy_name}'")
        print(f"[DRY RUN] Would create AppRole '{role_name}'")
        if extra_policies:
            print(f"[DRY RUN]   with extra policies: {', '.join(extra_policies)}")
        return

    _ensure_policy(client, policy_name, policy_hcl)
    _ensure_approle_auth(client)

    policies = [policy_name, *extra_policies]
    if WORKER_POLICY not in policies and WORKER_POLICY in _existing_role_policies(
        client, role_name
    ):
        policies.append(WORKER_POLICY)
        print(
            f"NOTE: keeping '{WORKER_POLICY}' on AppRole '{role_name}' "
            "(attached by an earlier --with-session-roles run)",
            file=sys.stderr,
        )

    client.auth.approle.create_or_update_approle(
        role_name=role_name,
        token_policies=policies,
        token_ttl=f"{token_ttl}s",
        token_max_ttl=f"{24 * 3600}s",
    )
    print(f"Created AppRole: {role_name} (policies: {', '.join(policies)})")
    _print_role_id(client, role_name, "project=newsletter-aggregator")


def seed_session_roles(
    client: Any,
    mount_path: str,
    secret_path: str,
    token_ttl: int,
    dry_run: bool = False,
) -> None:
    """Create the workstation and worker session-credential policies and roles.

    * ``newsletter-session-writer`` + AppRole ``newsletter-workstation``:
      ``patch`` only on the app secret, short-lived tokens.
    * ``newsletter-worker``: ``read`` + ``patch`` on the app secret, attached
      to the existing ``newsletter-app`` role next to ``newsletter-read``.
    """
    workstation_hcl = workstation_policy_hcl(mount_path, secret_path)
    worker_hcl = worker_policy_hcl(mount_path, secret_path)

    if dry_run:
        print(f"[DRY RUN] Would create policy '{WORKSTATION_POLICY}':")
        print(workstation_hcl, end="")
        print(f"[DRY RUN] Would create policy '{WORKER_POLICY}':")
        print(worker_hcl, end="")
        print(
            f"[DRY RUN] Would create AppRole '{WORKSTATION_ROLE}' "
            f"(token TTL {WORKSTATION_TOKEN_TTL}, max {WORKSTATION_TOKEN_MAX_TTL}, "
            f"secret-id TTL {WORKSTATION_SECRET_ID_TTL})"
        )
        seed_approle(
            None,
            mount_path,
            secret_path,
            token_ttl,
            dry_run=True,
            extra_policies=(WORKER_POLICY,),
        )
        return

    _ensure_policy(client, WORKSTATION_POLICY, workstation_hcl)
    _ensure_policy(client, WORKER_POLICY, worker_hcl)
    _ensure_approle_auth(client)

    client.auth.approle.create_or_update_approle(
        role_name=WORKSTATION_ROLE,
        token_policies=[WORKSTATION_POLICY],
        token_ttl=WORKSTATION_TOKEN_TTL,
        token_max_ttl=WORKSTATION_TOKEN_MAX_TTL,
        secret_id_ttl=WORKSTATION_SECRET_ID_TTL,
    )
    print(f"Created AppRole: {WORKSTATION_ROLE} (policies: {WORKSTATION_POLICY})")
    _print_role_id(client, WORKSTATION_ROLE, "project=newsletter-aggregator,host=workstation")
    print("  To hand it to the workstation without exposing it, wrap it instead:")
    print(f"    bao write -wrap-ttl=5m -f auth/approle/role/{WORKSTATION_ROLE}/secret-id")
    print("  and unwrap on the workstation: bao unwrap -field=secret_id <wrapping-token>")
    print()

    seed_approle(
        client,
        mount_path,
        secret_path,
        token_ttl,
        extra_policies=(WORKER_POLICY,),
    )


def seed_db_engine(
    client: Any,
    dry_run: bool = False,
) -> None:
    """Configure database secrets engine for dynamic PostgreSQL credentials.

    Creates a role that generates credentials with:
    - Default TTL: 1 hour
    - Max TTL: 24 hours
    - Grants: SELECT, INSERT, UPDATE, DELETE on all tables in public schema
    """
    db_dsn = os.environ.get("POSTGRES_DSN")
    if not db_dsn:
        print(
            "ERROR: POSTGRES_DSN env var required for --with-db-engine",
            file=sys.stderr,
        )
        sys.exit(1)

    if dry_run:
        print("[DRY RUN] Would enable database secrets engine at 'database/'")
        print("[DRY RUN] Would configure PostgreSQL connection from POSTGRES_DSN")
        print("[DRY RUN] Would create role 'newsletter-app' (TTL: 1h, max: 24h)")
        return

    secrets_engines = client.sys.list_mounted_secrets_engines()
    if "database/" not in secrets_engines:
        client.sys.enable_secrets_engine("database")
        print("Enabled database secrets engine")

    parsed = urlparse(db_dsn)
    db_username = parsed.username or "postgres"
    db_password = parsed.password or "postgres"

    if "{{username}}" in db_dsn:
        connection_url = db_dsn
    else:
        host_port = parsed.hostname or "localhost"
        if parsed.port:
            host_port = f"{host_port}:{parsed.port}"
        db_name = parsed.path.lstrip("/") or "postgres"
        connection_url = f"postgresql://{{{{username}}}}:{{{{password}}}}@{host_port}/{db_name}"

    client.secrets.database.configure(
        name="newsletter-postgres",
        plugin_name="postgresql-database-plugin",
        connection_url=connection_url,
        allowed_roles=["newsletter-app"],
        username=db_username,
        password=db_password,
    )
    print("Configured PostgreSQL connection: newsletter-postgres")

    creation_statements = [
        "CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';",
        'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{{name}}";',
    ]
    client.secrets.database.create_role(
        name="newsletter-app",
        db_name="newsletter-postgres",
        creation_statements=creation_statements,
        default_ttl="1h",
        max_ttl="24h",
    )
    print("Created database role: newsletter-app (TTL: 1h, max: 24h)")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Seed OpenBao with newsletter-aggregator secrets.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to OpenBao",
    )
    parser.add_argument(
        "--with-db-engine",
        action="store_true",
        help="Configure the database secrets engine for PostgreSQL",
    )
    parser.add_argument(
        "--with-approle",
        action="store_true",
        help="Create an AppRole for the newsletter application",
    )
    parser.add_argument(
        "--with-session-roles",
        action="store_true",
        help=(
            "Create the patch-only 'newsletter-workstation' AppRole and attach the "
            "read+patch 'newsletter-worker' policy to 'newsletter-app' (implies --with-approle)"
        ),
    )
    parser.add_argument(
        "--shared-keys",
        type=str,
        default="",
        help="Comma-separated list of keys to also write to secret/shared/",
    )
    parser.add_argument(
        "--secrets-path",
        type=Path,
        default=DEFAULT_SECRETS_PATH,
        help="Path to .secrets.yaml (default: project root)",
    )
    args = parser.parse_args()

    mount_path = os.environ.get("BAO_MOUNT_PATH", "secret")
    secret_path = os.environ.get("BAO_SECRET_PATH", "newsletter")
    token_ttl = int(os.environ.get("BAO_TOKEN_TTL", "3600"))

    if args.dry_run:
        print("=== DRY RUN MODE ===\n")
        client = None
    else:
        client = _get_client()

    # Step 1: Seed project secrets
    print("--- Seeding newsletter secrets ---")
    secrets = seed_secrets(client, args.secrets_path, mount_path, secret_path, dry_run=args.dry_run)
    print()

    # Step 2: Seed shared keys (optional)
    if args.shared_keys:
        shared_keys = [k.strip() for k in args.shared_keys.split(",") if k.strip()]
        print("--- Seeding shared keys ---")
        seed_shared_keys(client, secrets, shared_keys, mount_path, dry_run=args.dry_run)
        print()

    # Step 3: Create AppRole(s) (optional). --with-session-roles also (re)writes
    # newsletter-app, so it replaces the plain --with-approle step.
    if args.with_session_roles:
        print("--- Creating session-credential AppRoles ---")
        seed_session_roles(client, mount_path, secret_path, token_ttl, dry_run=args.dry_run)
        print()
    elif args.with_approle:
        print("--- Creating AppRole ---")
        seed_approle(client, mount_path, secret_path, token_ttl, dry_run=args.dry_run)
        print()

    # Step 4: Configure database engine (optional)
    if args.with_db_engine:
        print("--- Configuring database secrets engine ---")
        seed_db_engine(client, dry_run=args.dry_run)
        print()

    print("Done.")


if __name__ == "__main__":
    main()
