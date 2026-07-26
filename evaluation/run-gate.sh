#!/usr/bin/env bash
# CLI gen-eval gate.
#
# Thin wrapper over scripts/run_gen_eval_gate.py. The resolution and state-
# classification logic lives in Python (src/cli_gen_eval/runner.py) because it is
# subtle enough to deserve unit tests and type checking; this script exists so CI,
# Make, and operators have one stable command to call.
#
# Environment:
#   ACA_GEN_EVAL_REQUIRE  Set in CI. Makes an absent runner fatal, refuses an
#                         unverifiable one, and removes the adjacent checkout from
#                         the resolution precedence entirely.
#   ACA_GEN_EVAL_BIN      Explicit runner command line. Highest precedence.
#   ACA_GEN_EVAL_PROJECT  Adjacent gen-eval checkout. Developer convenience only —
#                         ignored whenever ACA_GEN_EVAL_REQUIRE is set.
#
# Exit codes:
#   0  contract valid, and the suite passed or the runner is absent locally
#   1  contract invalid, or the suite failed
#   2  usage error
#   3  runner broken, or absent under ACA_GEN_EVAL_REQUIRE
#   4  the backend target the selection needs is absent or unreachable
#   5  the run finished but its report is not credible
#
# The gate never treats a broken runner as an absent one, and never treats an
# unbelievable report as a failing one. Both distinctions are the same idea: a
# prerequisite that did not hold is not a result. See src/cli_gen_eval/runner.py and
# src/cli_gen_eval/report.py.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v uv >/dev/null 2>&1; then
    exec uv run --frozen --extra gen-eval python \
        "${REPO_ROOT}/scripts/run_gen_eval_gate.py" "$@"
fi

exec python3 "${REPO_ROOT}/scripts/run_gen_eval_gate.py" "$@"
