#!/usr/bin/env python3
"""Setup test database for integration tests.

Creates a separate test database and runs migrations.
Safe to run multiple times - will recreate if exists.

Usage:
    python scripts/setup_test_db.py
"""

import os
import subprocess
import sys

# Test database configuration
DB_USER = os.getenv("DB_USER", "newsletter_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "newsletter_password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
TEST_DB_NAME = "newsletters_test"


def run_command(cmd: list[str], check: bool = True) -> bool:
    """Run shell command and return success status."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=check)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        if check:
            print(f"Error: {e.stderr}")
            return False
        return False


def check_postgres_running() -> bool:
    """Check if PostgreSQL is running."""
    print("Checking if PostgreSQL is running...")
    # Check if Docker container is running
    return run_command(
        ["docker", "ps", "--filter", "name=newsletter-postgres", "--format", "{{.Names}}"],
        check=False,
    )


def database_exists(db_name: str) -> bool:
    """Check if database exists."""
    # Use docker exec to run psql inside the container
    cmd = [
        "docker",
        "exec",
        "-e",
        f"PGPASSWORD={DB_PASSWORD}",  # Set password as env var
        "newsletter-postgres",
        "psql",
        "-U",
        DB_USER,
        "-lqt",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return db_name in result.stdout
    except subprocess.CalledProcessError:
        return False


def drop_database(db_name: str) -> bool:
    """Drop database if it exists."""
    print(f"Dropping existing database '{db_name}'...")

    cmd = [
        "docker",
        "exec",
        "-e",
        f"PGPASSWORD={DB_PASSWORD}",
        "newsletter-postgres",
        "psql",
        "-U",
        DB_USER,
        "-d",
        "postgres",  # Connect to postgres database
        "-c",
        f"DROP DATABASE IF EXISTS {db_name};",
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"✓ Dropped database '{db_name}'")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to drop database: {e.stderr.decode()}")
        return False


def create_database(db_name: str) -> bool:
    """Create test database."""
    print(f"Creating database '{db_name}'...")

    cmd = [
        "docker",
        "exec",
        "-e",
        f"PGPASSWORD={DB_PASSWORD}",
        "newsletter-postgres",
        "psql",
        "-U",
        DB_USER,
        "-d",
        "postgres",  # Connect to postgres database
        "-c",
        f"CREATE DATABASE {db_name};",
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"✓ Created database '{db_name}'")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to create database: {e.stderr.decode()}")
        return False


def run_migrations(db_name: str) -> bool:
    """Run database migrations on test database."""
    print(f"Running migrations on '{db_name}'...")

    # Set environment variable for Alembic
    env = os.environ.copy()
    test_db_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{db_name}"
    env["DATABASE_URL"] = test_db_url

    cmd = ["alembic", "upgrade", "head"]

    try:
        subprocess.run(cmd, env=env, check=True, capture_output=True)
        print("✓ Migrations completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to run migrations: {e.stderr.decode()}")
        return False


def main():
    """Setup test database."""
    print("=" * 80)
    print("TEST DATABASE SETUP")
    print("=" * 80)
    print()

    # Check PostgreSQL
    if not check_postgres_running():
        print("✗ PostgreSQL is not running")
        print("  Start it with: docker compose up -d postgres")
        sys.exit(1)
    print("✓ PostgreSQL is running")
    print()

    # Drop existing test database
    if database_exists(TEST_DB_NAME):
        if not drop_database(TEST_DB_NAME):
            sys.exit(1)

    # Create test database
    if not create_database(TEST_DB_NAME):
        sys.exit(1)

    # Run migrations
    if not run_migrations(TEST_DB_NAME):
        sys.exit(1)

    print()
    print("=" * 80)
    print("TEST DATABASE READY")
    print("=" * 80)
    print()
    print(f"Database: {TEST_DB_NAME}")
    print(f"Host: {DB_HOST}:{DB_PORT}")
    print(f"User: {DB_USER}")
    print()
    print("Run integration tests with:")
    print("  pytest tests/integration/ -v")
    print()
    print("Set TEST_DATABASE_URL environment variable to override:")
    print(
        f"  export TEST_DATABASE_URL=postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{TEST_DB_NAME}"
    )
    print()


if __name__ == "__main__":
    main()
