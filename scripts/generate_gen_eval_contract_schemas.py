#!/usr/bin/env python3
"""Generate the vendored gen-eval contract schemas from the pinned runner source.

This is a *maintenance-time* tool, not a runtime or CI dependency. It reaches the
gen-eval package through ``uvx`` at the ref recorded in
``evaluation/contract/pin.json``, so gen-eval never enters this project's
environment (``establish-cli-gen-eval-coverage`` D1/D2). Everything downstream —
the contract validator, the report validator, CI — reads the checked-in JSON only.

Two schemas are generated from pydantic models. The third, the evaluation report,
is assembled here because upstream ``GenEvalReport`` is a plain dataclass and
cannot emit its own schema; its shape mirrors ``reports.generate_json_report()``
with the generated ``ScenarioVerdict`` embedded. See UPSTREAM.md UP-2 — once that
lands, this script's hand-assembled branch is replaced by a straight copy of the
published schemas.

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

DESCRIPTOR_SCHEMA = "interface-descriptor.schema.json"
SCENARIO_SCHEMA = "scenario.schema.json"
REPORT_SCHEMA = "eval-report.schema.json"

# Emitted inside the uvx subprocess. Keeps the gen-eval import off this process.
_EMITTER = """
import json
from gen_eval.descriptor import InterfaceDescriptor
from gen_eval.models import Scenario, ScenarioVerdict

print(json.dumps({
    "descriptor": InterfaceDescriptor.model_json_schema(),
    "scenario": Scenario.model_json_schema(),
    "verdict": ScenarioVerdict.model_json_schema(),
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


def build_report_schema(verdict_schema: dict[str, Any], pin: dict[str, Any]) -> dict[str, Any]:
    """Assemble the evaluation-report schema around the generated verdict model.

    Mirrors ``gen_eval.reports.generate_json_report``. ``per_visibility`` is
    optional there — it is only written when non-empty — so it is not required
    here. Every other key is written unconditionally and is therefore required:
    a report missing one is malformed, which is exactly what the ri-06 validator
    needs to be able to say.
    """
    counts = {
        "type": "object",
        "additionalProperties": {"type": "integer", "minimum": 0},
    }
    verdict = dict(verdict_schema)
    verdict_defs = verdict.pop("$defs", {})

    schema: dict[str, Any] = {
        "title": "GenEvalReport",
        "description": (
            "Evaluation report emitted as gen-eval-report.json. Hand-assembled from "
            "gen_eval.reports.generate_json_report because upstream GenEvalReport is a "
            "dataclass; see UPSTREAM.md UP-2."
        ),
        "type": "object",
        "additionalProperties": True,
        "required": [
            "total_scenarios",
            "passed",
            "failed",
            "errors",
            "skipped",
            "pass_rate",
            "coverage_pct",
            "duration_seconds",
            "budget_exhausted",
            "iterations_completed",
            "cost_summary",
            "per_interface",
            "per_category",
            "unevaluated_interfaces",
            "verdicts",
        ],
        "properties": {
            "total_scenarios": {"type": "integer", "minimum": 0},
            "passed": {"type": "integer", "minimum": 0},
            "failed": {"type": "integer", "minimum": 0},
            "errors": {"type": "integer", "minimum": 0},
            "skipped": {"type": "integer", "minimum": 0},
            "pass_rate": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "coverage_pct": {"type": "number", "minimum": 0.0, "maximum": 100.0},
            "duration_seconds": {"type": "number", "minimum": 0.0},
            "budget_exhausted": {"type": "boolean"},
            "iterations_completed": {"type": "integer", "minimum": 0},
            "cost_summary": {
                "type": "object",
                "additionalProperties": {"type": "number"},
            },
            "per_interface": {"type": "object", "additionalProperties": counts},
            "per_category": {"type": "object", "additionalProperties": counts},
            "unevaluated_interfaces": {"type": "array", "items": {"type": "string"}},
            "verdicts": {"type": "array", "items": {"$ref": "#/$defs/ScenarioVerdict"}},
            "per_visibility": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "required": ["total", "passed", "failed", "errors", "skipped", "pass_rate"],
                    "properties": {
                        "total": {"type": "integer", "minimum": 0},
                        "passed": {"type": "integer", "minimum": 0},
                        "failed": {"type": "integer", "minimum": 0},
                        "errors": {"type": "integer", "minimum": 0},
                        "skipped": {"type": "integer", "minimum": 0},
                        "pass_rate": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    },
                },
            },
        },
        "$defs": {**verdict_defs, "ScenarioVerdict": verdict},
    }
    return _annotate(schema, pin, "gen_eval.reports.generate_json_report (hand-assembled)")


def render(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def build_all(pin: dict[str, Any]) -> dict[str, str]:
    upstream = emit_upstream_schemas(pin)
    return {
        DESCRIPTOR_SCHEMA: render(
            _annotate(upstream["descriptor"], pin, "gen_eval.descriptor.InterfaceDescriptor")
        ),
        SCENARIO_SCHEMA: render(_annotate(upstream["scenario"], pin, "gen_eval.models.Scenario")),
        REPORT_SCHEMA: render(build_report_schema(upstream["verdict"], pin)),
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
