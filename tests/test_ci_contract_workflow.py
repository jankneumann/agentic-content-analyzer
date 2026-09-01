"""Lock the contract-test job against hang-without-output (#507, #521)."""

from pathlib import Path

from hypothesis import settings

from tests.contract.hypothesis_profile import CONTRACT_PROFILE, activate_contract_profile

CI = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
CONFTEST = Path(__file__).resolve().parents[1] / "tests" / "contract" / "conftest.py"


def test_contract_job_isolates_hangs_and_keeps_hypothesis_examples() -> None:
    text = CI.read_text()
    assert "timeout-minutes: 45" in text
    assert "--timeout=300" in text
    assert "timeout-method: thread" in text
    assert "fail-fast: false" in text
    assert "tests/contract/test_schema_conformance.py" in text
    assert "--ignore=tests/contract/test_schema_conformance.py" in text
    assert "hypothesis-contract-" in text
    assert ".hypothesis/examples" in text
    assert "derandomize" not in text.lower() or "Do not derandomize" in text


def test_fuzz_leg_uses_signal_timeout_and_captures_stderr() -> None:
    """Silent interpreter death bypasses thread timeouts (#521)."""
    text = CI.read_text()
    assert "timeout-method: signal" in text
    assert "--timeout-method=${{ matrix.timeout-method }}" in text
    assert "PYTHONFAULTHANDLER" in text
    assert "-X faulthandler" in text
    assert "faulthandler_timeout=120" in text
    assert "pytest-stderr.log" in text
    assert "tee pytest-stderr.log" in text


def test_contract_conftest_activates_hypothesis_profile() -> None:
    text = CONFTEST.read_text()
    assert "activate_contract_profile()" in text


def test_contract_hypothesis_profile_overrides_ci_derandomize() -> None:
    previous = settings.get_current_profile_name()
    try:
        settings.load_profile("ci")
        assert settings().derandomize is True
        assert settings().database is None

        activate_contract_profile()

        assert settings.get_current_profile_name() == CONTRACT_PROFILE
        assert settings().derandomize is False
        assert settings().database is not None
    finally:
        settings.load_profile(previous)
