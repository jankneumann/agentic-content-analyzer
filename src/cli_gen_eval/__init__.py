"""Repository-local gen-eval contract layer for the ``aca`` CLI evaluation suite.

This package owns the *contract* half of ri-06's two-layer design: the pinned
descriptor, scenario, and report schemas plus their validators. It deliberately has
no dependency on the gen-eval package — nothing here imports ``gen_eval``, and every
function in this package works with no evaluation runner installed. That is what lets
CI enforce schema conformance and thresholds even when runner acquisition fails, so an
unreachable runner reduces coverage loudly instead of passing silently.

The *runner* half lives in ``evaluation/run-gate.sh``.
"""

from __future__ import annotations

# Pinned gen-eval artifact contract version. Must match ``contract_version`` in
# evaluation/contract/pin.json and the ``x-gen-eval-contract-version`` annotation on
# every vendored schema; tests/cli_gen_eval/test_contract.py enforces all three.
#
# Held here as well as in pin.json so runtime code can assert the version without
# depending on the repository layout — an installed wheel ships this module and the
# schemas, but not evaluation/.
CONTRACT_VERSION = "1"

__all__ = ["CONTRACT_VERSION"]
