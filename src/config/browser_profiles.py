"""Where persistent browser profiles live, and the rule that nothing copies them.

A Playwright persistent profile (``launch_persistent_context``) holds live session
cookies for the site it logged into. It is a credential, not an artifact: it must
never be captured off-site by ``aca backup`` or copied between machines by
``aca sync``. The cookies extracted from it are stored in OpenBao, which the backup
already covers through the raft snapshot.

This module is the single place both sides agree on:

* the capture command (``aca auth session``) creates per-site profiles under
  :func:`browser_profiles_dir`;
* every backup and sync path consults :func:`excluded_roots` and
  :data:`EXCLUDED_PATH_PATTERNS` before copying a file.

Two independent checks, deliberately. The configured root is matched by resolved
path, which covers an operator who points ``BROWSER_PROFILES_DIR`` somewhere
unusual. The component pattern matches the default layout wherever it appears,
which covers the case the configured root cannot: ``~`` expands per user, so a
backup that runs as a dedicated service account resolves a different home than the
operator who logged in.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePath
from typing import Any

#: Default root for per-site persistent browser profiles.
DEFAULT_BROWSER_PROFILES_DIR = "~/.aca/browser-profiles"

#: Path-component sequences that no backup or sync path may copy, wherever they
#: appear in a tree. Each entry is matched component-wise, never as a substring:
#: ``xaca/browser-profiles`` does not match ``.aca/browser-profiles``.
EXCLUDED_PATH_PATTERNS: tuple[str, ...] = (".aca/browser-profiles",)


def browser_profiles_dir(settings: Any | None = None) -> Path:
    """The configured profiles root, with ``~`` expanded (not resolved).

    ``settings`` defaults to the application settings. Any object without a
    ``browser_profiles_dir`` attribute falls back to the default, so callers that
    pass a narrow settings stand-in still get the exclusion.
    """
    if settings is None:
        from src.config.settings import get_settings

        settings = get_settings()
    raw = getattr(settings, "browser_profiles_dir", None) or DEFAULT_BROWSER_PROFILES_DIR
    return Path(str(raw)).expanduser()


def excluded_roots(settings: Any | None = None) -> tuple[Path, ...]:
    """Resolved directories no backup or sync path may copy from or into.

    The denylist hook: a future credential-bearing directory is added here, and
    every consumer picks it up.
    """
    return (browser_profiles_dir(settings).resolve(),)


def _pattern_parts(pattern: str) -> tuple[str, ...]:
    return tuple(part for part in pattern.split("/") if part)


def matches_excluded_pattern(path: str | PurePath) -> bool:
    """True when ``path`` contains an :data:`EXCLUDED_PATH_PATTERNS` sequence."""
    parts = PurePath(path).parts
    for pattern in EXCLUDED_PATH_PATTERNS:
        needle = _pattern_parts(pattern)
        width = len(needle)
        if any(parts[i : i + width] == needle for i in range(len(parts) - width + 1)):
            return True
    return False


def is_excluded_path(path: str | Path, roots: tuple[Path, ...]) -> bool:
    """True when ``path`` is inside an excluded root or matches an excluded pattern.

    ``roots`` must already be resolved (see :func:`excluded_roots`); ``path`` is
    resolved here so a symlinked or relative spelling cannot slip past.
    """
    if matches_excluded_pattern(path):
        return True
    resolved = Path(path).resolve()
    return any(resolved.is_relative_to(root) for root in roots)


def excluded_subpaths(root: str, roots: tuple[Path, ...]) -> list[str]:
    """Excluded roots that sit INSIDE ``root``, spelled the way ``tar`` sees them.

    ``tar`` names members by the operand as given, so an exclusion must use the
    same spelling: the operand, then the path from its resolved form to the
    excluded directory. Comparing resolved paths means a symlinked operand or a
    symlinked profiles root is still detected.
    """
    base = Path(root).resolve()
    found: list[str] = []
    for excluded in roots:
        if excluded != base and excluded.is_relative_to(base):
            # os.path.join, not Path: Path("./x") drops the "./" that tar keeps.
            spelled = os.path.join(root, str(excluded.relative_to(base)))
            if spelled not in found:
                found.append(spelled)
    return found
