"""Tests for Neon branch management CLI commands.

Tests cover all 5 commands:
- list: default table output, JSON mode, empty results
- create: success, JSON mode, --force flag, API errors
- delete: with/without --force, confirmation abort
- connection: pooled (default), direct, JSON mode
- clean: stale branches, dry-run, empty results, force, partial failure

All tests mock NeonBranchManager via _get_manager to avoid real API calls.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from src.cli.app import app
from src.storage.providers.neon_branch import NeonAPIError, NeonBranch

runner = CliRunner()


def _make_branch(
    name: str = "claude/test-branch",
    id: str = "br-test-123",
    parent_id: str | None = "br-main-001",
    created_at: datetime | None = None,
    connection_string: str | None = "postgresql://user:pass@host/db",
) -> NeonBranch:
    """Create a sample NeonBranch for testing."""
    return NeonBranch(
        id=id,
        name=name,
        parent_id=parent_id,
        created_at=created_at or datetime.now(UTC),
        connection_string=connection_string,
    )


def _mock_manager(**method_overrides) -> MagicMock:
    """Create a mock NeonBranchManager that supports async context manager.

    Args:
        **method_overrides: Override specific async methods with return values or side effects.
            Use AsyncMock(return_value=...) for return values.
            Use AsyncMock(side_effect=...) for exceptions.
    """
    manager = MagicMock()
    manager.__aenter__ = AsyncMock(return_value=manager)
    manager.__aexit__ = AsyncMock(return_value=False)

    # Set up default async methods
    manager.list_branches = AsyncMock(return_value=[])
    manager.create_branch = AsyncMock(return_value=_make_branch())
    manager.delete_branch = AsyncMock()
    manager.get_connection_string = AsyncMock(return_value="postgresql://user:pass@host/db")

    # Apply overrides
    for method_name, mock_value in method_overrides.items():
        setattr(manager, method_name, mock_value)

    return manager


class TestListBranches:
    """Tests for `aca neon list`."""

    def test_list_default_output(self):
        """Test default table output with branches."""
        branches = [
            _make_branch(name="main", id="br-main-001"),
            _make_branch(name="claude/feature-x", id="br-feat-002"),
        ]
        mgr = _mock_manager(list_branches=AsyncMock(return_value=branches))

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "list"])

        assert result.exit_code == 0
        assert "main" in result.output
        assert "claude/feature-x" in result.output
        assert "br-main-001" in result.output

    def test_list_empty(self):
        """Test output when no branches exist."""
        mgr = _mock_manager(list_branches=AsyncMock(return_value=[]))

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "list"])

        assert result.exit_code == 0
        assert "No branches found" in result.output

    def test_list_json_mode(self):
        """Test JSON output mode."""
        branches = [
            _make_branch(name="main", id="br-main-001", parent_id=None),
        ]
        mgr = _mock_manager(list_branches=AsyncMock(return_value=branches))

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["--json", "neon", "list"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "branches" in data
        assert len(data["branches"]) == 1
        assert data["branches"][0]["name"] == "main"
        assert data["branches"][0]["id"] == "br-main-001"
        assert data["branches"][0]["parent_id"] is None
        assert "created_at" in data["branches"][0]

    def test_list_json_empty(self):
        """Test JSON output with no branches."""
        mgr = _mock_manager(list_branches=AsyncMock(return_value=[]))

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["--json", "neon", "list"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["branches"] == []


class TestCreateBranch:
    """Tests for `aca neon create`."""

    def test_create_success(self):
        """Test basic branch creation."""
        branch = _make_branch(name="claude/my-feature")
        mgr = _mock_manager(create_branch=AsyncMock(return_value=branch))

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "create", "claude/my-feature"])

        assert result.exit_code == 0
        assert "Created branch: claude/my-feature" in result.output
        assert "Connection:" in result.output
        mgr.create_branch.assert_awaited_once_with("claude/my-feature", parent="main")

    def test_create_with_parent(self):
        """Test branch creation with custom parent."""
        branch = _make_branch(name="claude/child")
        mgr = _mock_manager(create_branch=AsyncMock(return_value=branch))

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "create", "claude/child", "--parent", "staging"])

        assert result.exit_code == 0
        mgr.create_branch.assert_awaited_once_with("claude/child", parent="staging")

    def test_create_json_mode(self):
        """Test JSON output for create."""
        branch = _make_branch(
            name="claude/test",
            id="br-new-456",
            connection_string="postgresql://neon.tech/test",
        )
        mgr = _mock_manager(create_branch=AsyncMock(return_value=branch))

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["--json", "neon", "create", "claude/test"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "br-new-456"
        assert data["name"] == "claude/test"
        assert data["connection_string"] == "postgresql://neon.tech/test"

    def test_create_no_connection_string(self):
        """Test create when branch has no connection string."""
        branch = _make_branch(name="claude/no-conn", connection_string=None)
        mgr = _mock_manager(create_branch=AsyncMock(return_value=branch))

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "create", "claude/no-conn"])

        assert result.exit_code == 0
        assert "Created branch: claude/no-conn" in result.output
        assert "<see Neon console>" in result.output

    def test_create_force_deletes_existing(self):
        """Test --force deletes existing branch before creating."""
        branch = _make_branch(name="claude/force-test")
        mgr = _mock_manager(
            create_branch=AsyncMock(return_value=branch),
            delete_branch=AsyncMock(),
        )

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "create", "claude/force-test", "--force"])

        assert result.exit_code == 0
        assert "Deleted existing branch: claude/force-test" in result.output
        assert "Created branch: claude/force-test" in result.output
        mgr.delete_branch.assert_awaited_once_with("claude/force-test")
        mgr.create_branch.assert_awaited_once()

    def test_create_force_ignores_not_found(self):
        """Test --force gracefully handles non-existent branch."""
        branch = _make_branch(name="claude/new-branch")
        mgr = _mock_manager(
            create_branch=AsyncMock(return_value=branch),
            delete_branch=AsyncMock(side_effect=NeonAPIError("Not found", status_code=404)),
        )

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "create", "claude/new-branch", "--force"])

        assert result.exit_code == 0
        assert "Created branch: claude/new-branch" in result.output

    def test_create_force_propagates_other_errors(self):
        """Test --force re-raises non-404 errors during delete."""
        mgr = _mock_manager(
            delete_branch=AsyncMock(side_effect=NeonAPIError("Server error", status_code=500)),
        )

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "create", "claude/fail", "--force"])

        assert result.exit_code != 0

    def test_create_api_error(self):
        """Test create handles API errors."""
        mgr = _mock_manager(
            create_branch=AsyncMock(
                side_effect=NeonAPIError("Branch limit reached", status_code=409)
            ),
        )

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "create", "claude/over-limit"])

        assert result.exit_code != 0


class TestDeleteBranch:
    """Tests for `aca neon delete`."""

    def test_delete_with_force(self):
        """Test delete with --force skips confirmation."""
        mgr = _mock_manager()

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "delete", "claude/old-branch", "--force"])

        assert result.exit_code == 0
        assert "Deleted branch: claude/old-branch" in result.output
        mgr.delete_branch.assert_awaited_once_with("claude/old-branch")

    def test_delete_with_confirmation(self):
        """Test delete prompts for confirmation."""
        mgr = _mock_manager()

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "delete", "claude/old-branch"], input="y\n")

        assert result.exit_code == 0
        assert "Deleted branch: claude/old-branch" in result.output

    def test_delete_abort_confirmation(self):
        """Test delete aborts when user says no."""
        mgr = _mock_manager()

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "delete", "claude/keep-this"], input="n\n")

        assert result.exit_code != 0  # Aborted
        mgr.delete_branch.assert_not_awaited()

    def test_delete_json_mode(self):
        """Test JSON output for delete."""
        mgr = _mock_manager()

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["--json", "neon", "delete", "claude/gone", "--force"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["deleted"] == "claude/gone"

    def test_delete_json_mode_skips_confirmation(self):
        """Test JSON mode skips confirmation prompt (no --force needed)."""
        mgr = _mock_manager()

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["--json", "neon", "delete", "claude/auto"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["deleted"] == "claude/auto"
        mgr.delete_branch.assert_awaited_once_with("claude/auto")

    def test_delete_not_found_error(self):
        """Test delete handles branch not found."""
        mgr = _mock_manager(
            delete_branch=AsyncMock(side_effect=NeonAPIError("Not found", status_code=404)),
        )

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "delete", "nonexistent", "--force"])

        assert result.exit_code != 0


class TestConnectionString:
    """Tests for `aca neon connection`."""

    def test_connection_pooled_default(self):
        """Test default pooled connection string."""
        mgr = _mock_manager(
            get_connection_string=AsyncMock(
                return_value="postgresql://user:pass@pooler.neon.tech/db"
            ),
        )

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "connection", "claude/branch"])

        assert result.exit_code == 0
        assert "postgresql://user:pass@pooler.neon.tech/db" in result.output
        mgr.get_connection_string.assert_awaited_once_with("claude/branch", pooled=True)

    def test_connection_direct(self):
        """Test --direct connection string for migrations."""
        mgr = _mock_manager(
            get_connection_string=AsyncMock(
                return_value="postgresql://user:pass@direct.neon.tech/db"
            ),
        )

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "connection", "claude/branch", "--direct"])

        assert result.exit_code == 0
        assert "postgresql://user:pass@direct.neon.tech/db" in result.output
        mgr.get_connection_string.assert_awaited_once_with("claude/branch", pooled=False)

    def test_connection_json_mode(self):
        """Test JSON output for connection."""
        mgr = _mock_manager(
            get_connection_string=AsyncMock(return_value="postgresql://neon.tech/db"),
        )

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["--json", "neon", "connection", "claude/branch"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["branch"] == "claude/branch"
        assert data["pooled"] is True
        assert data["connection_string"] == "postgresql://neon.tech/db"

    def test_connection_json_direct(self):
        """Test JSON output with --direct flag."""
        mgr = _mock_manager(
            get_connection_string=AsyncMock(return_value="postgresql://direct.neon.tech/db"),
        )

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(
                app, ["--json", "neon", "connection", "claude/branch", "--direct"]
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["pooled"] is False


class TestCleanBranches:
    """Tests for `aca neon clean`."""

    def _make_stale_branches(self) -> list[NeonBranch]:
        """Create branches with varying ages for testing."""
        now = datetime.now(UTC)
        return [
            _make_branch(
                name="claude/old-one",
                id="br-old-1",
                created_at=now - timedelta(hours=48),
            ),
            _make_branch(
                name="claude/old-two",
                id="br-old-2",
                created_at=now - timedelta(hours=36),
            ),
            _make_branch(
                name="main",
                id="br-main",
                created_at=now - timedelta(days=365),
            ),
            _make_branch(
                name="claude/fresh",
                id="br-fresh",
                created_at=now - timedelta(hours=1),
            ),
        ]

    def test_clean_finds_stale_branches(self):
        """Test clean identifies stale branches matching prefix and age."""
        branches = self._make_stale_branches()
        mgr = _mock_manager(list_branches=AsyncMock(return_value=branches))

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "clean", "--force"])

        assert result.exit_code == 0
        assert "claude/old-one" in result.output
        assert "claude/old-two" in result.output
        # "main" should not match (wrong prefix)
        # "claude/fresh" should not match (too new)
        assert mgr.delete_branch.await_count == 2

    def test_clean_dry_run(self):
        """Test --dry-run shows but doesn't delete."""
        branches = self._make_stale_branches()
        mgr = _mock_manager(list_branches=AsyncMock(return_value=branches))

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "clean", "--dry-run"])

        assert result.exit_code == 0
        assert "dry run" in result.output
        assert "claude/old-one" in result.output
        mgr.delete_branch.assert_not_awaited()

    def test_clean_no_stale_branches(self):
        """Test clean with no stale branches."""
        fresh = _make_branch(
            name="claude/new",
            created_at=datetime.now(UTC) - timedelta(minutes=5),
        )
        mgr = _mock_manager(list_branches=AsyncMock(return_value=[fresh]))

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "clean"])

        assert result.exit_code == 0
        assert "No stale branches found" in result.output

    def test_clean_custom_prefix_and_age(self):
        """Test clean with custom --prefix and --older-than."""
        now = datetime.now(UTC)
        branches = [
            _make_branch(
                name="test/old",
                id="br-test-1",
                created_at=now - timedelta(hours=6),
            ),
            _make_branch(
                name="claude/old",
                id="br-claude-1",
                created_at=now - timedelta(hours=6),
            ),
        ]
        mgr = _mock_manager(list_branches=AsyncMock(return_value=branches))

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(
                app,
                [
                    "neon",
                    "clean",
                    "--prefix",
                    "test/",
                    "--older-than",
                    "4",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        # Should only delete test/old, not claude/old
        mgr.delete_branch.assert_awaited_once_with("test/old")

    def test_clean_json_mode(self):
        """Test JSON output for clean."""
        branches = self._make_stale_branches()
        mgr = _mock_manager(list_branches=AsyncMock(return_value=branches))

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["--json", "neon", "clean", "--force"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "deleted" in data
        assert "count" in data
        assert data["count"] == 2
        assert "claude/old-one" in data["deleted"]
        assert "claude/old-two" in data["deleted"]

    def test_clean_json_dry_run(self):
        """Test JSON output includes dry_run flag when --dry-run is used."""
        branches = self._make_stale_branches()
        mgr = _mock_manager(list_branches=AsyncMock(return_value=branches))

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["--json", "neon", "clean", "--dry-run"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["count"] == 2
        assert "claude/old-one" in data["deleted"]
        mgr.delete_branch.assert_not_awaited()

    def test_clean_json_no_dry_run(self):
        """Test JSON output omits dry_run field when not in dry-run mode."""
        branches = self._make_stale_branches()
        mgr = _mock_manager(list_branches=AsyncMock(return_value=branches))

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["--json", "neon", "clean", "--force"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "dry_run" not in data

    def test_clean_partial_failure(self):
        """Test clean continues when individual deletes fail."""
        now = datetime.now(UTC)
        branches = [
            _make_branch(
                name="claude/fail",
                id="br-fail",
                created_at=now - timedelta(hours=48),
            ),
            _make_branch(
                name="claude/succeed",
                id="br-ok",
                created_at=now - timedelta(hours=48),
            ),
        ]

        delete_mock = AsyncMock(
            side_effect=[
                NeonAPIError("Delete failed", status_code=500),
                None,  # Second delete succeeds
            ]
        )
        mgr = _mock_manager(
            list_branches=AsyncMock(return_value=branches),
            delete_branch=delete_mock,
        )

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "clean", "--force"])

        assert result.exit_code == 0
        assert "Failed to delete claude/fail" in result.output
        assert "Deleted: claude/succeed" in result.output

    def test_clean_confirmation_abort(self):
        """Test clean aborts when user says no."""
        branches = self._make_stale_branches()
        mgr = _mock_manager(list_branches=AsyncMock(return_value=branches))

        with patch("src.cli.neon_commands._get_manager", return_value=mgr):
            result = runner.invoke(app, ["neon", "clean"], input="n\n")

        assert result.exit_code != 0  # Aborted
        mgr.delete_branch.assert_not_awaited()


class TestMissingCredentials:
    """Tests for missing Neon credentials error handling."""

    def test_list_without_credentials(self):
        """Test list command fails gracefully without credentials."""
        with patch("src.cli.neon_commands.settings", create=True) as mock_settings:
            mock_settings.neon_api_key = None
            mock_settings.neon_project_id = None
            mock_settings.neon_default_branch = "main"

            # Need to reimport _get_manager so it picks up the patched settings
            with patch(
                "src.cli.neon_commands._get_manager",
                side_effect=SystemExit(1),
            ):
                result = runner.invoke(app, ["neon", "list"])

        assert result.exit_code != 0

    def test_create_without_credentials(self):
        """Test create command fails gracefully without credentials."""
        with patch(
            "src.cli.neon_commands._get_manager",
            side_effect=SystemExit(1),
        ):
            result = runner.invoke(app, ["neon", "create", "test-branch"])

        assert result.exit_code != 0
