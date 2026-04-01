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

Environment variables:
    BAO_ADDR:        OpenBao server URL (required)
    BAO_TOKEN:       Root/admin token for seeding (required)
    BAO_MOUNT_PATH:  KV v2 mount path (default: "secret")
    BAO_SECRET_PATH: Secret data path (default: "newsletter")
    POSTGRES_DSN:    PostgreSQL DSN for database engine (with --with-db-engine)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml


def _repo_root() -> Path:
    """Find the repository root."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
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
    client,  # type: ignore[no-untyped-def]
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
        print(
            f"[DRY RUN] Would write {len(secrets)} secrets "
            f"to {mount_path}/{secret_path}:"
        )
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
    client,  # type: ignore[no-untyped-def]
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
            f"WARNING: keys not found in .secrets.yaml: "
            f"{', '.join(sorted(missing))}",
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
    except Exception:  # noqa: BLE001
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


def seed_approle(
    client,  # type: ignore[no-untyped-def]
    mount_path: str,
    secret_path: str,
    token_ttl: int,
    dry_run: bool = False,
) -> None:
    """Create an AppRole for the newsletter application."""
    role_name = "newsletter-app"
    policy_name = "newsletter-read"
    policy_hcl = (
        f'path "{mount_path}/data/{secret_path}" {{\n'
        f'  capabilities = ["read"]\n'
        f"}}\n"
        f'path "{mount_path}/data/shared" {{\n'
        f'  capabilities = ["read"]\n'
        f"}}\n"
    )

    if dry_run:
        print(f"[DRY RUN] Would create policy '{policy_name}'")
        print(f"[DRY RUN] Would create AppRole '{role_name}'")
        return

    client.sys.create_or_update_policy(name=policy_name, policy=policy_hcl)
    print(f"Created policy: {policy_name}")

    auth_methods = client.sys.list_auth_methods()
    if "approle/" not in auth_methods:
        client.sys.enable_auth_method("approle")
        print("Enabled AppRole auth method")

    client.auth.approle.create_or_update_approle(
        role_name=role_name,
        token_policies=[policy_name],
        token_ttl=f"{token_ttl}s",
        token_max_ttl=f"{24 * 3600}s",
    )
    print(f"Created AppRole: {role_name}")

    role_id_resp = client.auth.approle.read_role_id(role_name=role_name)
    role_id = role_id_resp.get("data", {}).get("role_id", "")
    print(f"  Role ID: {role_id}")
    print("  Generate a secret ID with:")
    print(f"    bao write auth/approle/role/{role_name}/secret-id \\")
    print('      metadata="project=newsletter-aggregator"')


def seed_db_engine(
    client,  # type: ignore[no-untyped-def]
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
        print(
            "[DRY RUN] Would create role 'newsletter-app' (TTL: 1h, max: 24h)"
        )
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
        connection_url = (
            f"postgresql://{{{{username}}}}:{{{{password}}}}"
            f"@{host_port}/{db_name}"
        )

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
        "CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' "
        "VALID UNTIL '{{expiration}}';",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES "
        'IN SCHEMA public TO "{{name}}";',
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
    parser = argparse.ArgumentParser(
        description="Seed OpenBao with newsletter-aggregator secrets."
    )
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
    secrets = seed_secrets(
        client, args.secrets_path, mount_path, secret_path, dry_run=args.dry_run
    )
    print()

    # Step 2: Seed shared keys (optional)
    if args.shared_keys:
        shared_keys = [k.strip() for k in args.shared_keys.split(",") if k.strip()]
        print("--- Seeding shared keys ---")
        seed_shared_keys(
            client, secrets, shared_keys, mount_path, dry_run=args.dry_run
        )
        print()

    # Step 3: Create AppRole (optional)
    if args.with_approle:
        print("--- Creating AppRole ---")
        seed_approle(
            client, mount_path, secret_path, token_ttl, dry_run=args.dry_run
        )
        print()

    # Step 4: Configure database engine (optional)
    if args.with_db_engine:
        print("--- Configuring database secrets engine ---")
        seed_db_engine(client, dry_run=args.dry_run)
        print()

    print("Done.")


if __name__ == "__main__":
    main()
