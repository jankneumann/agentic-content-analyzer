"""Every repository path and make target a visualization skill names must exist.

Both skill documents drifted from the repository before this test existed:
`codebase-atlas/SKILL.md` documented `make atlas` and `make atlas-check`, which
the Makefile did not define, and cited a proposal document that was never
committed.  Neither is visible to a reader who trusts the document, and neither
breaks anything that would be noticed, so both survived indefinitely.

The extractor is deliberately conservative.  A false negative here costs a
missed doc bug; a false positive blocks the suite on a code span that was never
a path, so anything ambiguous -- a placeholder, a glob, a shell variable -- is
skipped rather than guessed at.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
SKILLS = REPO_ROOT / ".claude" / "skills"

DOCS = [
    SKILLS / "codebase-atlas" / "SKILL.md",
    SKILLS / "refresh-architecture" / "SKILL.md",
]

#: Inline code shaped like a path: at least one separator, no placeholder
#: syntax.  A bare filename is deliberately not a candidate -- it names no
#: location, so checking it would mean guessing where the author meant.
_PATH_SHAPED = re.compile(r"^[A-Za-z0-9_.@-]+(?:/[A-Za-z0-9_.@-]+)+/?$")


def _repo_top_level() -> set[str]:
    return {entry.name for entry in REPO_ROOT.iterdir()}


def _gitignored(paths: list[str]) -> set[str]:
    """Return the subset of *paths* that git ignores.

    A gitignored path is generated or runtime state, so its absence says
    nothing about the document naming it.  Asking git is more honest than a
    hand-maintained allowlist, which drifts in exactly the way this test
    exists to catch.
    """
    if not paths:
        return set()
    result = subprocess.run(  # noqa: S603
        ["git", "check-ignore", "--stdin"],  # noqa: S607
        input="\n".join(paths),
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _inline_code(text: str) -> list[str]:
    """Return inline code spans, ignoring fenced blocks (which hold commands)."""
    without_fences = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.findall(r"`([^`\n]+)`", without_fences)


def _is_path_candidate(span: str) -> bool:
    if any(ch in span for ch in "<>*$|\"'"):
        return False
    if span.startswith("-") or span.startswith("/"):
        return False
    if " " in span:
        return False
    if not _PATH_SHAPED.match(span):
        return False
    # A first segment that is not a top-level entry here is a path into a
    # consumer repository (for example `database/migrations/`), which this
    # repository is not obliged to have.
    return span.split("/", 1)[0] in _repo_top_level()


def _make_targets(text: str) -> set[str]:
    """Return every `make <target>` the document tells a reader to run."""
    fenced = " ".join(re.findall(r"```.*?```", text, flags=re.S))
    spans = " ".join(_inline_code(text))
    return set(re.findall(r"\bmake\s+([a-z][a-z0-9-]*)", f"{fenced} {spans}"))


def _declared_make_targets() -> set[str]:
    makefile = (REPO_ROOT / "Makefile").read_text()
    return set(re.findall(r"^([a-zA-Z][a-zA-Z0-9_-]*):", makefile, re.M))


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.parent.name)
def test_referenced_paths_exist(doc: Path) -> None:
    text = doc.read_text()
    candidates = [span for span in _inline_code(text) if _is_path_candidate(span)]
    ignored = _gitignored(candidates)

    missing = []
    for span in candidates:
        if span in ignored:
            continue
        # A path may be written relative to the skill that documents it, and
        # the skills keep their executables under `scripts/`.
        if any(
            (root / span).exists()
            for root in (doc.parent, doc.parent / "scripts", REPO_ROOT)
        ):
            continue
        missing.append(span)

    assert not missing, (
        f"{doc.relative_to(REPO_ROOT)} names paths that do not exist: "
        f"{sorted(set(missing))}"
    )


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.parent.name)
def test_referenced_make_targets_exist(doc: Path) -> None:
    declared = _declared_make_targets()
    referenced = _make_targets(doc.read_text())
    missing = sorted(referenced - declared)

    assert not missing, (
        f"{doc.relative_to(REPO_ROOT)} tells the reader to run make targets the "
        f"Makefile does not define: {missing}"
    )
