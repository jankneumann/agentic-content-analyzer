"""Check that Alembic migrations have exactly one head.

Zero-dependency script (stdlib only) that parses migration files using ast
to find revision/down_revision variables and compute heads. Designed for CI
where installing the full project + alembic is unnecessary.

Usage:
    python scripts/check_alembic_heads.py [versions_dir]
"""

import ast
import os
import sys


def parse_revision_info(filepath: str) -> tuple[str | None, list[str]]:
    """Extract revision and down_revision from a migration file via AST."""
    with open(filepath) as f:
        tree = ast.parse(f.read())

    revision = None
    down_revisions: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue

        # Get target name
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
            value = node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                name = target.id
                value = node.value
            else:
                continue
        else:
            continue

        if name == "revision" and isinstance(value, ast.Constant) and isinstance(value.value, str):
            revision = value.value
        elif name == "down_revision":
            if isinstance(value, ast.Constant):
                if isinstance(value.value, str):
                    down_revisions = [value.value]
                # None means initial migration
            elif isinstance(value, ast.Tuple):
                down_revisions = [
                    e.value
                    for e in value.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)
                ]

    return revision, down_revisions


def find_heads(versions_dir: str) -> list[str]:
    """Find all head revisions (revisions not referenced as down_revision by any other)."""
    revisions: dict[str, list[str]] = {}

    for filename in sorted(os.listdir(versions_dir)):
        if not filename.endswith(".py") or filename.startswith("__"):
            continue
        filepath = os.path.join(versions_dir, filename)
        rev, down_revs = parse_revision_info(filepath)
        if rev:
            revisions[rev] = down_revs

    # A head is a revision that no other revision points to as its down_revision
    all_down_revisions: set[str] = set()
    for down_revs in revisions.values():
        all_down_revisions.update(down_revs)

    return [rev for rev in revisions if rev not in all_down_revisions]


def main() -> None:
    versions_dir = sys.argv[1] if len(sys.argv) > 1 else "alembic/versions"

    if not os.path.isdir(versions_dir):
        print(f"::error::Versions directory not found: {versions_dir}")
        sys.exit(1)

    heads = find_heads(versions_dir)

    if len(heads) == 1:
        print(f"OK: Single Alembic head: {heads[0]}")
    else:
        print(f"::error::Expected 1 Alembic head, found {len(heads)}: {heads}")
        print('Fix with: alembic merge heads -m "merge migration branches"')
        sys.exit(1)


if __name__ == "__main__":
    main()
