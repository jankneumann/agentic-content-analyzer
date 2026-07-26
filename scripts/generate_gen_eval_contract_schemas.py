#!/usr/bin/env python3
"""Generate the vendored gen-eval contract schemas from the pinned runner source.

This is a *maintenance-time* tool, not a runtime or CI dependency. It reaches the
gen-eval package through ``uvx`` at the ref recorded in
``evaluation/contract/pin.json``, so gen-eval never enters this project's
environment (``establish-cli-gen-eval-coverage`` D1/D2). Everything downstream —
the contract validator, the report validator, CI — reads the checked-in JSON only.

As of runner ref 600744a5 (UPSTREAM.md UP-2) gen-eval publishes its own versioned
JSON Schema in ``gen_eval.contracts``. This script now copies those files verbatim
and adds provenance annotations; it derives nothing. That matters because a derived
schema can disagree with the code that produces the data, while a published one is
generated upstream from the very models that do — and is drift-tested there.

The generator refuses to write when the upstream ``CONTRACT_VERSION`` disagrees with
``contract_version`` in the pin, so bumping the runner ref cannot silently change the
contract underneath the vendored copies.

Usage:
    python3 scripts/generate_gen_eval_contract_schemas.py            # write
    python3 scripts/generate_gen_eval_contract_schemas.py --check    # drift only
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PIN_PATH = REPO_ROOT / "evaluation" / "contract" / "pin.json"
DURABLE_DIR = REPO_ROOT / "openspec" / "contracts" / "cli-gen-eval"
RUNTIME_DIR = REPO_ROOT / "src" / "cli_gen_eval" / "schemas"

# Upstream logical schema name -> the filename we vendor it under. Identical today;
# stated explicitly so a rename upstream is a visible edit here rather than silent
# churn in the durable contract directory.
FILENAMES = {
    "interface-descriptor": "interface-descriptor.schema.json",
    "scenario": "scenario.schema.json",
    "eval-report": "eval-report.schema.json",
}

# Emitted inside the uvx subprocess. Keeps the gen-eval import off this process.
_EMITTER = """
import json
from gen_eval.contracts import CONTRACT_VERSION, SCHEMA_FILENAMES, load_schema

print(json.dumps({
    "contract_version": CONTRACT_VERSION,
    "schemas": {name: load_schema(name) for name in SCHEMA_FILENAMES},
}))
"""


def load_pin() -> dict[str, Any]:
    pin: dict[str, Any] = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    for key in ("contract_version", "runner_source", "runner_subdirectory", "runner_ref"):
        if not pin.get(key):
            raise SystemExit(f"{PIN_PATH}: missing required key {key!r}")
    return pin


def runner_requirement(pin: dict[str, Any]) -> str:
    return (
        f"{pin['runner_package']} @ {pin['runner_source']}"
        f"@{pin['runner_ref']}#subdirectory={pin['runner_subdirectory']}"
    )


def emit_upstream_schemas(pin: dict[str, Any]) -> dict[str, Any]:
    """Run the emitter against the pinned gen-eval and return its three schemas."""
    # Resolve uvx to an absolute path rather than relying on PATH lookup at exec time,
    # and fail with an actionable message when it is absent instead of an OSError.
    uvx = shutil.which("uvx")
    if uvx is None:
        raise SystemExit(
            "uvx not found on PATH. It is required to reach the pinned gen-eval ref "
            "without adding gen-eval to this project's environment. Install uv: "
            "https://docs.astral.sh/uv/"
        )
    completed = subprocess.run(
        [uvx, "--from", runner_requirement(pin), "python", "-c", _EMITTER],
        capture_output=True,
        text=True,
        timeout=600,
        cwd=REPO_ROOT,
        check=False,
    )
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr)
        raise SystemExit(
            f"gen-eval schema emission failed (exit {completed.returncode}). "
            f"Pinned ref: {pin['runner_ref']}"
        )
    # uvx writes install progress to stderr, so stdout is the JSON document alone.
    return dict(json.loads(completed.stdout))


def _annotate(schema: dict[str, Any], pin: dict[str, Any], source: str) -> dict[str, Any]:
    """Prepend provenance so a vendored copy is never mistaken for hand-written."""
    annotated = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "x-gen-eval-contract-version": pin["contract_version"],
        "x-generated-from-ref": pin["runner_ref"],
        "x-generated-from": source,
        "x-generator": "scripts/generate_gen_eval_contract_schemas.py",
    }
    annotated.update(schema)
    return annotated


def render(schema: dict[str, Any]) -> str:
    """Serialize deterministically so byte-parity and drift checks are meaningful."""
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def build_all(pin: dict[str, Any]) -> dict[str, str]:
    """Copy the published schemas verbatim, annotated with provenance.

    Refuses to proceed when upstream's contract version disagrees with the pin. That
    guard is the point of the handshake: bumping ``runner_ref`` must never silently
    swap the contract underneath artifacts that were validated against the old one.
    """
    emitted = emit_upstream_schemas(pin)

    upstream_version = str(emitted["contract_version"])
    pinned_version = str(pin["contract_version"])
    if upstream_version != pinned_version:
        raise SystemExit(
            f"contract version mismatch: gen-eval at {pin['runner_ref'][:12]} publishes "
            f"{upstream_version!r} but evaluation/contract/pin.json pins "
            f"{pinned_version!r}. Review the upstream changelog, then update "
            f"contract_version in the pin and the changelog in "
            f"openspec/contracts/cli-gen-eval/README.md."
        )

    schemas: dict[str, dict[str, Any]] = emitted["schemas"]
    return {
        FILENAMES[name]: render(
            _annotate(schema, pin, f"gen_eval.contracts published schema {name!r}")
        )
        for name, schema in schemas.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail on drift instead of writing. Requires network access to the pinned ref.",
    )
    args = parser.parse_args()

    pin = load_pin()
    rendered = build_all(pin)

    drift: list[str] = []
    for target_dir in (DURABLE_DIR, RUNTIME_DIR):
        # --check must stay read-only: no directory creation, no writes.
        if not args.check:
            target_dir.mkdir(parents=True, exist_ok=True)
        for name, text in rendered.items():
            path = target_dir / name
            current = path.read_text(encoding="utf-8") if path.exists() else None
            if current == text:
                continue
            if args.check:
                drift.append(str(path.relative_to(REPO_ROOT)))
                continue
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path.relative_to(REPO_ROOT)}")

    if drift:
        print("gen-eval contract schemas are stale:", file=sys.stderr)
        for stale in drift:
            print(f"  - {stale}", file=sys.stderr)
        print(
            "Regenerate with: python3 scripts/generate_gen_eval_contract_schemas.py",
            file=sys.stderr,
        )
        return 1

    print(f"gen-eval contract schemas OK (contract_version={pin['contract_version']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
