#!/usr/bin/env python3
"""Write a schema-valid gen-eval report without raw target observations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.cli_gen_eval.contract import validate_report as validate_schema  # noqa: E402
from src.cli_gen_eval.report import load_json, minimize_for_artifact  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    document, load_error = load_json(args.source)
    if load_error is not None:
        print(load_error, file=sys.stderr)
        return 1
    schema_errors = validate_schema(document)
    if schema_errors:
        print(f"{args.source}: report is not schema-valid", file=sys.stderr)
        for error in schema_errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    if not isinstance(document, dict):
        print(f"{args.source}: report must be a JSON object", file=sys.stderr)
        return 1

    minimized = minimize_for_artifact(document)
    minimized_errors = validate_schema(minimized)
    if minimized_errors:
        print("minimized report is not schema-valid", file=sys.stderr)
        for error in minimized_errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(
        json.dumps(minimized, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
