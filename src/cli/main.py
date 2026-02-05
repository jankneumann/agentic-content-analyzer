"""Main CLI entrypoint for newsletter aggregator.

Usage:
    newsletter-cli profile list
    newsletter-cli profile show <name>
    newsletter-cli profile validate <name>
    newsletter-cli profile inspect
    newsletter-cli profile migrate

Or run as module:
    python -m src.cli profile list
"""

from __future__ import annotations

import typer

from src.cli.profile_commands import app as profile_app

# Main CLI application
app = typer.Typer(
    name="newsletter-cli",
    help="Newsletter Aggregator CLI",
    no_args_is_help=True,
)

# Register sub-commands
app.add_typer(profile_app, name="profile")


@app.callback()
def main_callback() -> None:
    """Newsletter Aggregator CLI.

    Manage profiles, validate configurations, and run migrations.
    """
    pass


if __name__ == "__main__":
    app()
