#!/usr/bin/env python3
"""Sync environment variables from .env to Railway.

This script reads your local .env file, compares it with Railway's current
variables, and only updates the ones that need to change.

Usage:
    python scripts/railway_env_sync.py          # Dry run (shows what would change)
    python scripts/railway_env_sync.py --apply  # Actually set the variables

Prerequisites:
    - Railway CLI installed (brew install railway)
    - Logged in to Railway (railway login)
    - Project and service linked (railway link && railway service)
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# ANSI colors
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
NC = "\033[0m"  # No Color

# Variables to SKIP (local-only, test, or not needed in production)
SKIP_PATTERNS = [
    r"^LOCAL_",
    r"^TEST_",
    r"^REDIS_",  # Not using Redis in production (PGQueuer uses Postgres)
    r"^CELERY_",  # Not using Celery (using PGQueuer)
    r"^NEO4J_LOCAL_",  # Local Neo4j settings
    r"^GMAIL_",  # Local file paths
    r"^YOUTUBE_CREDENTIALS",
    r"^YOUTUBE_TOKEN",
    r"^RSS_FEEDS_FILE",
    r"^DOCLING_CACHE_DIR",
    r"^YOUTUBE_TEMP_DIR",
]

# Variables to TRANSFORM for production
TRANSFORMS = {
    "ENVIRONMENT": "production",
    "DATABASE_PROVIDER": "supabase",
    "NEO4J_PROVIDER": "auradb",
    "LOG_LEVEL": "INFO",
}


def should_skip(var_name: str) -> bool:
    """Check if a variable should be skipped."""
    return any(re.match(pattern, var_name) for pattern in SKIP_PATTERNS)


def mask_value(var_name: str, value: str) -> str:
    """Mask sensitive values for display."""
    sensitive_patterns = ["PASSWORD", "KEY", "SECRET", "TOKEN"]
    if any(p in var_name.upper() for p in sensitive_patterns):
        if len(value) > 8:
            return f"{value[:4]}****{value[-4:]}"
        return "****"
    return value


def parse_env_file(env_path: Path) -> dict[str, str]:
    """Parse .env file into a dictionary."""
    if not env_path.exists():
        print(f"{RED}Error: {env_path} not found{NC}")
        sys.exit(1)

    variables = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Parse KEY=value
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
            if match:
                key, value = match.groups()

                # Remove inline comments (but preserve # in URLs)
                if not value.startswith(
                    ("http://", "https://", "postgresql://", "redis://", "bolt://", "neo4j")
                ):
                    value = re.split(r"\s+#", value)[0]

                # Remove surrounding quotes
                value = value.strip().strip("\"'")

                # Skip empty values
                if value:
                    variables[key] = value

    return variables


def get_railway_variables() -> dict[str, str] | None:
    """Get current Railway variables as a dictionary."""
    try:
        result = subprocess.run(
            ["railway", "variables", "list", "--json"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        # Railway returns a list of {name, value} objects or a dict
        if isinstance(data, list):
            return {item["name"]: item["value"] for item in data}
        elif isinstance(data, dict):
            return data
        return {}
    except subprocess.CalledProcessError as e:
        if "No service linked" in e.stderr:
            return None
        print(f"{RED}Error getting Railway variables: {e.stderr}{NC}")
        return None
    except json.JSONDecodeError:
        print(f"{RED}Error parsing Railway variables JSON{NC}")
        return None


def check_railway_status() -> tuple[bool, str | None]:
    """Check Railway project and service status."""
    try:
        result = subprocess.run(
            ["railway", "status"],  # noqa: S607
            capture_output=True,
            text=True,
        )
        output = result.stdout + result.stderr

        if "Project:" not in output:
            return False, "no_project"
        if "Service: None" in output or "No service linked" in output:
            return False, "no_service"
        return True, None
    except FileNotFoundError:
        return False, "no_cli"


def set_railway_variable(name: str, value: str) -> tuple[bool, str]:
    """Set a single Railway variable.

    Returns:
        Tuple of (success, error_message)
    """
    try:
        # Use environment variable approach for complex values
        # This avoids shell escaping issues
        result = subprocess.run(
            ["railway", "variables", "set", f"{name}={value}"],  # noqa: S607
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return False, result.stderr.strip()
        return True, ""
    except subprocess.CalledProcessError as e:
        return False, str(e)


def print_service_instructions() -> None:
    """Print instructions for creating a Railway service."""
    print(f"\n{YELLOW}You need to create and link a service first:{NC}\n")
    print(f"  {BLUE}Option 1: Deploy to create service automatically{NC}")
    print("    railway up              # Creates service from Dockerfile")
    print("    railway service         # Link to the new service")
    print("    python scripts/railway_env_sync.py --apply")
    print("    railway up              # Redeploy with variables")
    print()
    print(f"  {BLUE}Option 2: Create empty service first{NC}")
    print("    railway service create  # Create empty service")
    print("    railway service         # Link to it")
    print("    python scripts/railway_env_sync.py --apply")
    print("    railway up              # Deploy")
    print()
    print(f"  {BLUE}Option 3: Via Railway Dashboard{NC}")
    print("    1. Go to railway.app → Your project")
    print("    2. Click '+ New Service' → 'Empty Service' or 'GitHub Repo'")
    print("    3. Run: railway service")
    print("    4. Run: python scripts/railway_env_sync.py --apply")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync environment variables from .env to Railway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/railway_env_sync.py          # Dry run
    python scripts/railway_env_sync.py --apply  # Apply changes
        """,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually set the variables (default is dry run)",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Path to .env file (default: .env)",
    )
    args = parser.parse_args()

    print(f"{BLUE}{'=' * 50}{NC}")
    print(f"{BLUE}Railway Environment Variable Sync{NC}")
    print(f"{BLUE}{'=' * 50}{NC}\n")

    # Check Railway status
    if args.apply:
        _ok, error = check_railway_status()
        if error == "no_cli":
            print(f"{RED}Error: Railway CLI not installed{NC}")
            print("Install with: brew install railway")
            sys.exit(1)
        elif error == "no_project":
            print(f"{RED}Error: Not linked to a Railway project{NC}")
            print("\nRun these commands first:")
            print("  railway login    # Login to Railway")
            print("  railway link     # Link to your project")
            sys.exit(1)
        elif error == "no_service":
            print(f"{RED}Error: No service linked{NC}")
            print_service_instructions()
            sys.exit(1)

    mode = f"{YELLOW}APPLY{NC}" if args.apply else f"{GREEN}DRY RUN{NC}"
    print(f"Mode: {mode}")

    # Parse local .env file
    local_vars = parse_env_file(args.env_file)

    # Get current Railway variables (if applying)
    railway_vars = {}
    if args.apply:
        railway_vars = get_railway_variables() or {}
        print(f"Current Railway variables: {len(railway_vars)}")

    print()

    # Process variables
    to_set = []
    to_skip = []
    unchanged = []

    for name, value in sorted(local_vars.items()):
        # Check if should skip
        if should_skip(name):
            to_skip.append(name)
            continue

        # Apply transforms
        final_value = TRANSFORMS.get(name, value)
        transformed = final_value != value

        # Check if already set correctly in Railway
        if args.apply and name in railway_vars and railway_vars[name] == final_value:
            unchanged.append(name)
            continue

        to_set.append((name, final_value, transformed))

    # Display skipped
    for name in to_skip:
        print(f"  {YELLOW}SKIP{NC} {name} (local-only)")

    print()

    # Display unchanged (only in apply mode)
    if args.apply and unchanged:
        print(f"{CYAN}Unchanged ({len(unchanged)} variables already set correctly):{NC}")
        for name in unchanged[:5]:  # Show first 5
            print(f"  {CYAN}={NC} {name}")
        if len(unchanged) > 5:
            print(f"  {CYAN}... and {len(unchanged) - 5} more{NC}")
        print()

    # Display/apply changes
    applied_vars = []
    if to_set:
        action = "Setting" if args.apply else "Would set"
        print(f"{GREEN}{action} {len(to_set)} variables:{NC}")

        for name, value, transformed in to_set:
            masked = mask_value(name, value)
            transform_note = f" {BLUE}(transformed){NC}" if transformed else ""

            if args.apply:
                _success, _error = set_railway_variable(name, value)
                # Railway CLI sometimes returns errors even on success
                # We'll verify at the end
                applied_vars.append((name, value))
                print(f"  {CYAN}→{NC} {name}={masked}{transform_note}")
            else:
                print(f"  {GREEN}SET{NC} {name}={masked}{transform_note}")
    else:
        print(f"{GREEN}No changes needed - all variables are up to date!{NC}")

    # Verify changes by re-fetching Railway variables
    verified_count = 0
    failed_vars = []
    if args.apply and applied_vars:
        print(f"\n{CYAN}Verifying changes...{NC}")
        final_vars = get_railway_variables() or {}

        for name, expected_value in applied_vars:
            actual_value = final_vars.get(name)
            if actual_value == expected_value:
                verified_count += 1
            else:
                failed_vars.append(name)

        if failed_vars:
            print(f"  {RED}Failed to set {len(failed_vars)} variables:{NC}")
            for name in failed_vars[:5]:
                print(f"    {RED}✗{NC} {name}")
            if len(failed_vars) > 5:
                print(f"    ... and {len(failed_vars) - 5} more")
        print(
            f"  {GREEN}✓ Verified {verified_count}/{len(applied_vars)} variables set correctly{NC}"
        )

    # Summary
    print(f"\n{BLUE}{'=' * 50}{NC}")
    print("Summary:")
    print(f"  To set/update: {GREEN}{len(to_set)}{NC}")
    print(f"  Skipped (local-only): {YELLOW}{len(to_skip)}{NC}")
    if args.apply:
        print(f"  Already correct: {CYAN}{len(unchanged)}{NC}")
        if applied_vars:
            print(f"  Verified set: {GREEN}{verified_count}{NC}")
            if failed_vars:
                print(f"  Failed: {RED}{len(failed_vars)}{NC}")
    print(f"  Transformed: {BLUE}{sum(1 for _, _, t in to_set if t)}{NC}")
    print(f"{BLUE}{'=' * 50}{NC}")

    if not args.apply and to_set:
        print(f"\n{YELLOW}This was a dry run. To apply changes, run:{NC}")
        print("  python scripts/railway_env_sync.py --apply")
    elif args.apply and to_set:
        print(f"\n{GREEN}Variables synced! Deploy with:{NC}")
        print("  railway up")


if __name__ == "__main__":
    main()
