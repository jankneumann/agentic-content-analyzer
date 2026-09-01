"""Hypothesis profile for contract/fuzz tests.

GitHub Actions sets ``CI=true``, so Hypothesis auto-loads its built-in ``ci``
profile: ``derandomize=True`` and ``database=None``. That contradicts #507
(keep the random draw; persist ``.hypothesis/examples`` so failures replay)
and makes the Actions cache of that directory inert.

Load this profile before collecting contract tests so it wins over ``ci``.
"""

from __future__ import annotations

from hypothesis import HealthCheck, settings

CONTRACT_PROFILE = "contract"


def activate_contract_profile() -> None:
    """Replace the auto-loaded ``ci`` profile with a replayable random draw."""
    settings.register_profile(
        CONTRACT_PROFILE,
        parent=settings.get_profile("default"),
        derandomize=False,
        deadline=None,
        print_blob=True,
        suppress_health_check=(HealthCheck.too_slow,),
    )
    settings.load_profile(CONTRACT_PROFILE)
