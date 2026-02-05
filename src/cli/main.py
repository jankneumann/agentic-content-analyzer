"""Legacy newsletter-cli entrypoint (deprecated).

This module preserves backward compatibility for the `newsletter-cli` command.
It emits a deprecation warning and delegates to the main `aca` app.

Usage (deprecated):
    newsletter-cli profile list   ->  aca profile list
"""

from __future__ import annotations

import warnings

from src.cli.app import app as _aca_app

# Emit deprecation warning when this module is used as an entrypoint
warnings.warn(
    "The 'newsletter-cli' command is deprecated. Use 'aca' instead. Example: 'aca profile list'",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export the same app so all commands are available
app = _aca_app

if __name__ == "__main__":
    app()
