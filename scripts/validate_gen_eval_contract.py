#!/usr/bin/env python3
"""Validate the checked-in gen-eval evaluation contract without an evaluation runner.

Validates the interface descriptor and every scenario it declares against the schemas
vendored at the pinned contract version. This is the enforcing half of ri-06's contract
layer (D1): it imports no gen-eval, spawns no subprocess, touches no network, and
therefore always returns a definite verdict — never a skip. CI runs it unconditionally,
so a failed runner acquisition reduces coverage visibly instead of passing silently.

Exit codes:
    0  every artifact is schema-valid
    1  at least one artifact is invalid, unreadable, or missing
    2  usage error (argparse)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.cli_gen_eval import CONTRACT_VERSION  # noqa: E402
from src.cli_gen_eval.contract import (  # noqa: E402
    ContractError,
    validate_descriptor,
    validate_scenario,
)
from src.cli_gen_eval.runner import load_pin  # noqa: E402
from src.cli_gen_eval.suite import (  # noqa: E402
    SuiteAccount,
    account_template,
    iter_templates,
)

DEFAULT_DESCRIPTOR = REPO_ROOT / "evaluation" / "descriptors" / "aca-cli.yaml"


def load_document(path: Path) -> tuple[Any | None, list[str]]:
    """Load YAML or JSON. Returns (document, errors); document is None on failure."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [f"{path}: unreadable ({exc.strerror or exc})"]
    try:
        return yaml.safe_load(text), []
    except yaml.YAMLError as exc:
        return None, [f"{path}: not valid YAML or JSON ({exc.__class__.__name__})"]


def resolve_scenario_paths(descriptor_path: Path, document: Any) -> tuple[list[Path], list[str]]:
    """Expand the descriptor's ``scenario_dirs``, resolved relative to the descriptor.

    An empty or absent ``scenario_dirs`` is not an error here — a descriptor may
    legitimately declare no suites yet. A declared directory that does not exist is an
    error, because that silently evaluates nothing.
    """
    if not isinstance(document, dict):
        return [], []

    errors: list[str] = []
    paths: list[Path] = []
    for entry in document.get("scenario_dirs") or []:
        directory = (descriptor_path.parent / str(entry)).resolve()
        if not directory.is_dir():
            errors.append(f"scenario_dirs: {entry!r} does not resolve to a directory")
            continue
        paths.extend(sorted(p for p in directory.rglob("*.yaml") if p.is_file()))
        paths.extend(sorted(p for p in directory.rglob("*.yml") if p.is_file()))
    return sorted(set(paths)), errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--descriptor",
        type=Path,
        default=DEFAULT_DESCRIPTOR,
        help=f"Interface descriptor to validate (default: {DEFAULT_DESCRIPTOR.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--require-scenarios",
        action="store_true",
        help="Fail when the descriptor resolves to zero scenarios.",
    )
    parser.add_argument("--json", action="store_true", help="Emit a JSON summary on stdout.")
    args = parser.parse_args()

    findings: dict[str, list[str]] = {}

    if not args.descriptor.exists():
        findings[str(args.descriptor)] = ["descriptor does not exist"]
        return report(findings, CONTRACT_VERSION, SuiteAccount([]), args.json)

    document, load_errors = load_document(args.descriptor)
    descriptor_key = str(args.descriptor)

    try:
        descriptor_errors = load_errors or validate_descriptor(document)
    except ContractError as exc:
        # The vendored contract itself is broken — distinct from an invalid artifact,
        # and not something a caller can fix by editing their descriptor.
        print(f"gen-eval contract: UNUSABLE — {exc}", file=sys.stderr)
        return 1

    if descriptor_errors:
        findings[descriptor_key] = descriptor_errors

    scenario_paths, scenario_dir_errors = resolve_scenario_paths(args.descriptor, document)
    if scenario_dir_errors:
        findings.setdefault(descriptor_key, []).extend(scenario_dir_errors)

    max_expansions = int(
        load_pin().get("runner_limits", {}).get("max_expansions_per_template", 100)
    )
    accounts = []
    for path in scenario_paths:
        document, errors = load_document(path)
        if errors:
            findings[str(path)] = errors
            continue
        # A scenario file holds one template or a list of them; the runner accepts both.
        for index, template in enumerate(iter_templates(document)):
            template_errors = validate_scenario(template)
            # Account even when the template is schema-invalid, so the expected scenario
            # count is reported alongside the reason it is wrong.
            account = account_template(template, path, max_expansions)
            accounts.append(account)
            template_errors = template_errors + account.errors
            if template_errors:
                key = str(path) if isinstance(document, dict) else f"{path}[{index}]"
                findings.setdefault(key, []).extend(template_errors)

    if args.require_scenarios and not scenario_paths:
        findings.setdefault(descriptor_key, []).append(
            "resolved zero scenarios but --require-scenarios was set"
        )

    return report(findings, CONTRACT_VERSION, SuiteAccount(accounts), args.json)


def report(
    findings: dict[str, list[str]],
    contract_version: str,
    account: SuiteAccount,
    as_json: bool,
) -> int:
    """Print the verdict. Machine-readable output stays on stdout alone."""
    ok = not findings
    templates = len(account.templates)
    expected = account.expected_scenarios()
    if as_json:
        print(
            json.dumps(
                {
                    "valid": ok,
                    "contract_version": contract_version,
                    "templates_validated": templates,
                    "scenarios_expected": expected,
                    "scenarios_expected_per_category": account.per_category,
                    "findings": findings,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if ok else 1

    if ok:
        print(
            f"gen-eval contract: VALID "
            f"(contract_version={contract_version}, templates={templates}, "
            f"scenarios={expected})"
        )
        return 0

    print(f"gen-eval contract: INVALID (contract_version={contract_version})")
    for location, errors in sorted(findings.items()):
        print(f"- {location}")
        for error in errors:
            print(f"    {error}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
