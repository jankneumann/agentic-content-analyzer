"""Tests for the legacy newsletter-cli entrypoint (main.py)."""

from __future__ import annotations

import warnings

from typer.testing import CliRunner

runner = CliRunner()


class TestLegacyEntrypoint:
    def test_import_emits_deprecation_warning(self):
        """Importing the legacy main module should emit a DeprecationWarning."""
        import importlib

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Force re-import to trigger warning
            importlib.reload(__import__("src.cli.main", fromlist=["app"]))

            deprecation_warnings = [
                warning for warning in w if issubclass(warning.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "deprecated" in str(deprecation_warnings[0].message).lower()
            assert "aca" in str(deprecation_warnings[0].message).lower()

    def test_legacy_app_is_same_as_aca_app(self):
        """The legacy app should delegate to the same root app."""
        from src.cli.app import app as aca_app
        from src.cli.main import app as legacy_app

        assert legacy_app is aca_app
