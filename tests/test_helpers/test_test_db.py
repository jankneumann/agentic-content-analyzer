"""Tests for the shared test database helper.

Covers worktree detection, DB name generation, URL resolution,
safety checks, and auto-creation logic.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.helpers.test_db import (
    _MAX_PG_IDENTIFIER,
    _PREFIX,
    create_test_engine,
    ensure_test_db_exists,
    get_test_database_url,
    get_test_db_name,
    get_worktree_name,
)

# =============================================================================
# get_worktree_name()
# =============================================================================


class TestGetWorktreeName:
    """Tests for worktree detection from .git file."""

    def test_main_repo_returns_none(self, tmp_path: Path):
        """In the main repo, .git is a directory — should return None."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        with patch("tests.helpers.test_db.Path.cwd", return_value=tmp_path):
            assert get_worktree_name() is None

    def test_worktree_returns_name(self, tmp_path: Path):
        """In a worktree, .git is a file with gitdir pointer."""
        git_file = tmp_path / ".git"
        git_file.write_text("gitdir: /home/user/repo/.git/worktrees/my-feature-branch\n")
        with patch("tests.helpers.test_db.Path.cwd", return_value=tmp_path):
            assert get_worktree_name() == "my-feature-branch"

    def test_worktree_with_slashes_in_name(self, tmp_path: Path):
        """Worktree names can contain slashes (from branch names)."""
        git_file = tmp_path / ".git"
        git_file.write_text("gitdir: /home/user/repo/.git/worktrees/openspec/add-feature\n")
        with patch("tests.helpers.test_db.Path.cwd", return_value=tmp_path):
            # Only the part after the last /worktrees/ matters
            assert get_worktree_name() == "openspec/add-feature"

    def test_corrupted_git_file_returns_none(self, tmp_path: Path):
        """Corrupted .git file should return None gracefully."""
        git_file = tmp_path / ".git"
        git_file.write_text("garbage content\n")
        with patch("tests.helpers.test_db.Path.cwd", return_value=tmp_path):
            assert get_worktree_name() is None

    def test_missing_git_returns_none(self, tmp_path: Path):
        """No .git file/directory at all — return None."""
        with patch("tests.helpers.test_db.Path.cwd", return_value=tmp_path):
            assert get_worktree_name() is None

    def test_unreadable_git_file_returns_none(self, tmp_path: Path):
        """If .git file can't be read, return None."""
        git_file = tmp_path / ".git"
        git_file.write_text("gitdir: something")
        with (
            patch("tests.helpers.test_db.Path.cwd", return_value=tmp_path),
            patch.object(Path, "read_text", side_effect=OSError("permission denied")),
        ):
            assert get_worktree_name() is None

    def test_strips_trailing_slash(self, tmp_path: Path):
        """Trailing slashes in worktree path should be stripped."""
        git_file = tmp_path / ".git"
        git_file.write_text("gitdir: /home/user/repo/.git/worktrees/my-branch/\n")
        with patch("tests.helpers.test_db.Path.cwd", return_value=tmp_path):
            assert get_worktree_name() == "my-branch"


# =============================================================================
# get_test_db_name()
# =============================================================================


class TestGetTestDbName:
    """Tests for worktree-aware database name generation."""

    def test_main_repo_default_name(self):
        """Main repo (no worktree) returns default name."""
        with patch("tests.helpers.test_db.get_worktree_name", return_value=None):
            assert get_test_db_name() == "newsletters_test"

    def test_worktree_name_appended(self):
        """Worktree name is sanitized and appended to prefix."""
        with patch(
            "tests.helpers.test_db.get_worktree_name",
            return_value="add-parallel-test-databases",
        ):
            assert get_test_db_name() == "newsletters_test_add_parallel_test_databases"

    def test_special_characters_sanitized(self):
        """Non-alphanumeric characters replaced with underscore."""
        with patch(
            "tests.helpers.test_db.get_worktree_name",
            return_value="openspec/add-feature.v2",
        ):
            assert get_test_db_name() == "newsletters_test_openspec_add_feature_v2"

    def test_uppercase_lowered(self):
        """Uppercase characters are lowered."""
        with patch(
            "tests.helpers.test_db.get_worktree_name",
            return_value="MyFeature",
        ):
            assert get_test_db_name() == "newsletters_test_myfeature"

    def test_leading_trailing_underscores_stripped(self):
        """Leading/trailing underscores from sanitization are stripped."""
        with patch(
            "tests.helpers.test_db.get_worktree_name",
            return_value="--my-branch--",
        ):
            assert get_test_db_name() == "newsletters_test_my_branch"

    def test_63_char_truncation(self):
        """Long worktree names are truncated to fit PG's 63-char limit."""
        long_name = "a" * 100
        with patch(
            "tests.helpers.test_db.get_worktree_name",
            return_value=long_name,
        ):
            result = get_test_db_name()
            assert len(result) <= _MAX_PG_IDENTIFIER
            assert result.startswith(_PREFIX)
            # Verify it's exactly at the limit
            assert len(result) == _MAX_PG_IDENTIFIER

    def test_prefix_length(self):
        """Verify the prefix constant is correct."""
        assert _PREFIX == "newsletters_test_"
        assert len(_PREFIX) == 17


# =============================================================================
# get_test_database_url()
# =============================================================================


class TestGetTestDatabaseUrl:
    """Tests for test database URL resolution."""

    def test_env_var_override(self, monkeypatch):
        """TEST_DATABASE_URL env var always wins."""
        monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://custom:pass@host/my_test_db")
        assert get_test_database_url() == "postgresql://custom:pass@host/my_test_db"

    def test_default_with_worktree_name(self, monkeypatch):
        """Without env var, generates URL from worktree name."""
        monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
        with patch(
            "tests.helpers.test_db.get_test_db_name",
            return_value="newsletters_test_my_branch",
        ):
            url = get_test_database_url()
            assert "newsletters_test_my_branch" in url
            assert url.startswith("postgresql://")

    def test_default_main_repo(self, monkeypatch):
        """Without env var in main repo, uses default newsletters_test."""
        monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
        with patch(
            "tests.helpers.test_db.get_test_db_name",
            return_value="newsletters_test",
        ):
            url = get_test_database_url()
            assert url.endswith("/newsletters_test")


# =============================================================================
# ensure_test_db_exists()
# =============================================================================


class TestEnsureTestDbExists:
    """Tests for auto-creation of test databases."""

    def test_creates_database_when_missing(self):
        """Creates the database when it doesn't exist."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = None  # DB doesn't exist

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("tests.helpers.test_db._sa_create_engine", return_value=mock_engine):
            ensure_test_db_exists(
                "newsletters_test_foo",
                "postgresql://user:pass@localhost/newsletters",
            )

        # Should have executed two statements: SELECT check + CREATE DATABASE
        assert mock_conn.execute.call_count == 2
        # The second call's first arg is a text() clause — check its .text attr
        create_arg = mock_conn.execute.call_args_list[1][0][0]
        assert "CREATE DATABASE" in create_arg.text

    def test_skips_when_exists(self):
        """Does not create when database already exists."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = 1  # DB exists

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("tests.helpers.test_db._sa_create_engine", return_value=mock_engine):
            ensure_test_db_exists(
                "newsletters_test_foo",
                "postgresql://user:pass@localhost/newsletters",
            )

        # Should only execute the SELECT check, not CREATE
        assert mock_conn.execute.call_count == 1

    def test_connects_to_admin_db(self):
        """Should connect to 'postgres' admin database, not the target DB."""
        with patch("tests.helpers.test_db._sa_create_engine") as mock_create:
            mock_engine = MagicMock()
            mock_conn = MagicMock()
            mock_conn.execute.return_value.scalar.return_value = 1
            mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
            mock_create.return_value = mock_engine

            ensure_test_db_exists(
                "newsletters_test",
                "postgresql://user:pass@localhost/newsletters",
            )

            # Verify it connects to postgres admin DB
            call_url = mock_create.call_args[0][0]
            assert call_url.endswith("/postgres")

    def test_raises_on_connection_failure(self):
        """Raises clear error when admin connection fails."""
        with patch(
            "tests.helpers.test_db._sa_create_engine",
            side_effect=Exception("connection refused"),
        ):
            with pytest.raises(RuntimeError, match="Could not auto-create"):
                ensure_test_db_exists(
                    "newsletters_test",
                    "postgresql://user:pass@localhost/newsletters",
                )


# =============================================================================
# create_test_engine()
# =============================================================================


class TestCreateTestEngine:
    """Tests for the combined engine factory with safety checks."""

    def test_rejects_non_test_database(self):
        """Safety check prevents connecting to production databases."""
        with pytest.raises(ValueError, match="does not contain 'test'"):
            create_test_engine("postgresql://user:pass@localhost/newsletters_production")

    def test_rejects_no_database_name(self):
        """Safety check rejects URLs without a database name."""
        with pytest.raises(ValueError, match="does not contain 'test'"):
            create_test_engine("postgresql://user:pass@localhost/")

    def test_accepts_test_database(self):
        """Accepts URLs with 'test' in the database name."""
        with (
            patch("tests.helpers.test_db.ensure_test_db_exists"),
            patch("tests.helpers.test_db._sa_create_engine") as mock_create,
        ):
            mock_engine = MagicMock()
            mock_engine.url.database = "newsletters_test"
            mock_create.return_value = mock_engine

            engine = create_test_engine("postgresql://user:pass@localhost/newsletters_test")
            assert engine is mock_engine
