#!/usr/bin/env python3
"""
Validation script for Docling parser integration.

Run this script after pulling the add-docling-parser changes to verify
the implementation works correctly in your environment.

Usage:
    python scripts/validate_docling.py [--skip-tests] [--skip-migration]
"""

import argparse
import subprocess
import sys
from pathlib import Path


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(msg: str) -> None:
    """Print a section header."""
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BLUE}{Colors.BOLD}{msg}{Colors.RESET}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'=' * 60}{Colors.RESET}\n")


def print_success(msg: str) -> None:
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")


def print_error(msg: str) -> None:
    """Print an error message."""
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")


def print_warning(msg: str) -> None:
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.RESET}")


def run_command(cmd: list[str], description: str, check: bool = True) -> bool:
    """Run a command and report results."""
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
        )
        if result.returncode == 0:
            print_success(description)
            return True
        else:
            print_error(f"{description} (exit code: {result.returncode})")
            if result.stderr:
                print(f"  stderr: {result.stderr[:500]}")
            return False
    except subprocess.CalledProcessError as e:
        print_error(f"{description} failed")
        if e.stderr:
            print(f"  stderr: {e.stderr[:500]}")
        return False
    except FileNotFoundError:
        print_error(f"Command not found: {cmd[0]}")
        return False


def check_dependencies() -> bool:
    """Check that required dependencies are installed."""
    print_header("Checking Dependencies")

    all_ok = True

    # Check docling
    try:
        import docling  # noqa: F401

        print_success("docling is installed")
    except ImportError:
        print_error("docling is not installed")
        print("  Run: pip install docling>=2.60.0")
        all_ok = False

    # Check markitdown
    try:
        import markitdown  # noqa: F401

        print_success("markitdown is installed")
    except ImportError:
        print_error("markitdown is not installed")
        all_ok = False

    # Check pytest
    try:
        import pytest  # noqa: F401

        print_success("pytest is installed")
    except ImportError:
        print_warning("pytest is not installed (tests will be skipped)")

    # Check mypy
    result = subprocess.run(["mypy", "--version"], capture_output=True)
    if result.returncode == 0:
        print_success("mypy is installed")
    else:
        print_warning("mypy is not installed (type checking will be skipped)")

    # Check ruff
    result = subprocess.run(["ruff", "--version"], capture_output=True)
    if result.returncode == 0:
        print_success("ruff is installed")
    else:
        print_warning("ruff is not installed (linting will be skipped)")

    return all_ok


def check_imports() -> bool:
    """Check that new modules can be imported."""
    print_header("Checking Module Imports")

    all_ok = True

    # Check DoclingParser import
    try:
        from src.parsers import DoclingParser

        print_success("DoclingParser imports successfully")

        # Check instantiation
        parser = DoclingParser(enable_ocr=False)
        print_success(f"DoclingParser instantiates (name: {parser.name})")
    except Exception as e:
        print_error(f"DoclingParser import failed: {e}")
        all_ok = False

    # Check FileIngestionService import
    try:
        from src.ingestion.files import FileIngestionService

        print_success("FileIngestionService imports successfully")
    except Exception as e:
        print_error(f"FileIngestionService import failed: {e}")
        all_ok = False

    # Check upload routes import
    try:
        from src.api.upload_routes import router

        print_success("upload_routes imports successfully")
        print_success(f"  Routes registered: {len(router.routes)}")
    except Exception as e:
        print_error(f"upload_routes import failed: {e}")
        all_ok = False

    # Check settings
    try:
        from src.config.settings import settings

        print_success("Settings load successfully")
        print(f"  enable_docling: {settings.enable_docling}")
        print(f"  docling_enable_ocr: {settings.docling_enable_ocr}")
        print(f"  max_upload_size_mb: {settings.max_upload_size_mb}")
    except Exception as e:
        print_error(f"Settings load failed: {e}")
        all_ok = False

    return all_ok


def run_linting() -> bool:
    """Run ruff linting on new files."""
    print_header("Running Linting (ruff)")

    new_files = [
        "src/parsers/docling_parser.py",
        "src/ingestion/files.py",
        "src/api/upload_routes.py",
    ]

    return run_command(
        ["ruff", "check"] + new_files,
        "Linting passed",
        check=False,
    )


def run_type_checking() -> bool:
    """Run mypy type checking on new files."""
    print_header("Running Type Checking (mypy)")

    new_files = [
        "src/parsers/docling_parser.py",
        "src/ingestion/files.py",
        "src/api/upload_routes.py",
    ]

    return run_command(
        ["mypy"] + new_files,
        "Type checking passed",
        check=False,
    )


def run_tests() -> bool:
    """Run pytest on new test files."""
    print_header("Running Tests (pytest)")

    test_files = [
        "tests/test_parsers/test_docling_parser.py",
        "tests/test_ingestion/test_files.py",
    ]

    # Check files exist
    for f in test_files:
        if not Path(f).exists():
            print_error(f"Test file not found: {f}")
            return False

    return run_command(
        ["pytest"] + test_files + ["-v", "--tb=short"],
        "All tests passed",
        check=False,
    )


def run_full_test_suite() -> bool:
    """Run the full test suite to check for regressions."""
    print_header("Running Full Test Suite")

    return run_command(
        ["pytest", "--tb=short", "-q"],
        "Full test suite passed",
        check=False,
    )


def test_migration(skip: bool = False) -> bool:
    """Test the database migration."""
    if skip:
        print_header("Skipping Migration Test")
        print_warning("Migration test skipped (--skip-migration)")
        return True

    print_header("Testing Database Migration")

    # Check migration file exists
    migration_file = Path(
        "alembic/versions/4d78f715c284_add_documents_table.py"
    )
    if not migration_file.exists():
        print_error(f"Migration file not found: {migration_file}")
        return False
    print_success("Migration file exists")

    # Try upgrade
    if not run_command(
        ["alembic", "upgrade", "head"],
        "Migration upgrade succeeded",
        check=False,
    ):
        return False

    # Try downgrade
    if not run_command(
        ["alembic", "downgrade", "-1"],
        "Migration downgrade succeeded",
        check=False,
    ):
        return False

    # Upgrade again
    if not run_command(
        ["alembic", "upgrade", "head"],
        "Migration re-upgrade succeeded",
        check=False,
    ):
        return False

    return True


def test_docling_parsing() -> bool:
    """Test Docling parsing with a simple document."""
    print_header("Testing Docling Parsing")

    try:
        from src.parsers import DoclingParser

        parser = DoclingParser(enable_ocr=False)

        # Test format detection
        assert parser._detect_format("test.pdf") == "pdf"
        assert parser._detect_format("test.docx") == "docx"
        assert parser._detect_format("image.png") == "png"
        print_success("Format detection works")

        # Test can_parse
        assert parser.can_parse("test.pdf") is True
        assert parser.can_parse("test.xyz") is False
        print_success("can_parse works")

        # Test OCR detection
        assert parser._likely_needs_ocr("scanned_doc.pdf") is True
        assert parser._likely_needs_ocr("regular.pdf") is False
        assert parser._likely_needs_ocr("image.png") is True
        print_success("OCR detection works")

        # Test link extraction
        links = parser._extract_links("Check [here](https://example.com)")
        assert "https://example.com" in links
        print_success("Link extraction works")

        return True
    except Exception as e:
        print_error(f"Docling parsing test failed: {e}")
        return False


def print_summary(results: dict[str, bool]) -> None:
    """Print a summary of all validation results."""
    print_header("Validation Summary")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        if result:
            print_success(name)
        else:
            print_error(name)

    print()
    if passed == total:
        print(f"{Colors.GREEN}{Colors.BOLD}All {total} checks passed!{Colors.RESET}")
    else:
        print(
            f"{Colors.YELLOW}{Colors.BOLD}{passed}/{total} checks passed{Colors.RESET}"
        )
        print(
            f"{Colors.RED}{Colors.BOLD}{total - passed} checks failed{Colors.RESET}"
        )


def main() -> int:
    """Run all validation checks."""
    parser = argparse.ArgumentParser(
        description="Validate Docling parser integration"
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip running pytest",
    )
    parser.add_argument(
        "--skip-migration",
        action="store_true",
        help="Skip database migration test",
    )
    parser.add_argument(
        "--skip-full-suite",
        action="store_true",
        help="Skip full test suite (only run new tests)",
    )
    args = parser.parse_args()

    print(f"{Colors.BOLD}Docling Parser Integration Validation{Colors.RESET}")
    print("=" * 40)

    results: dict[str, bool] = {}

    # Check dependencies
    results["Dependencies"] = check_dependencies()

    # Check imports
    results["Module Imports"] = check_imports()

    # Run linting
    results["Linting (ruff)"] = run_linting()

    # Run type checking
    results["Type Checking (mypy)"] = run_type_checking()

    # Test Docling parsing
    results["Docling Parsing"] = test_docling_parsing()

    # Run tests
    if not args.skip_tests:
        results["New Tests"] = run_tests()
        if not args.skip_full_suite:
            results["Full Test Suite"] = run_full_test_suite()
    else:
        print_header("Skipping Tests")
        print_warning("Tests skipped (--skip-tests)")

    # Test migration
    results["Database Migration"] = test_migration(skip=args.skip_migration)

    # Print summary
    print_summary(results)

    # Return exit code
    if all(results.values()):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
