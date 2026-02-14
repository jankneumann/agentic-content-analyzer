"""Verify that the local development environment is set up correctly."""

import os
import sys

import psycopg2
from neo4j import GraphDatabase

from src.config import settings


def check_env_file() -> bool:
    """Check if .env file exists."""
    if not os.path.exists(".env"):
        print("❌ .env file not found")
        print("   Run: cp .env.example .env")
        return False
    print("✓ .env file exists")
    return True


def check_api_keys() -> bool:
    """Check if required API keys are set."""
    success = True

    if not settings.anthropic_api_key or settings.anthropic_api_key.startswith("sk-ant-xxx"):
        print("❌ ANTHROPIC_API_KEY not set in .env")
        success = False
    else:
        print("✓ ANTHROPIC_API_KEY is set")

    return success


def check_postgres() -> bool:
    """Check PostgreSQL connection."""
    try:
        conn = psycopg2.connect(settings.database_url)
        conn.close()
        print("✓ PostgreSQL connection successful")
        return True
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        print("   Run: docker compose up -d postgres")
        return False


def check_neo4j() -> bool:
    """Check Neo4j connection."""
    try:
        driver = GraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )
        with driver.session() as session:
            result = session.run("RETURN 1")
            result.single()
        driver.close()
        print("✓ Neo4j connection successful")
        return True
    except Exception as e:
        print(f"❌ Neo4j connection failed: {e}")
        print("   Run: docker compose up -d neo4j")
        return False


def check_gmail_credentials() -> bool:
    """Check if Gmail credentials exist."""
    if not os.path.exists("credentials.json"):
        print("❌ credentials.json not found")
        print("   Download from Google Cloud Console and place in project root")
        return False
    print("✓ credentials.json exists")
    return True


def main() -> None:
    """Run all verification checks."""
    print("Verifying local development setup...\n")

    checks = [
        check_env_file(),
        check_api_keys(),
        check_postgres(),
        check_neo4j(),
        check_gmail_credentials(),
    ]

    print("\n" + "=" * 50)
    if all(checks):
        print("✓ All checks passed! Setup is complete.")
        print("\nNext steps:")
        print("1. Run: python scripts/setup_gmail.py (to authenticate Gmail)")
        print("2. Run: alembic upgrade head (to initialize database)")
        print("3. Start building! See PROJECT_PLAN.md for next tasks")
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
