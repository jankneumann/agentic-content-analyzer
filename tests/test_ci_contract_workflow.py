"""Lock the contract-test job against hang-without-output (issue #507)."""

from pathlib import Path

CI = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def test_contract_job_isolates_hangs_and_keeps_hypothesis_examples() -> None:
    text = CI.read_text()
    assert "timeout-minutes: 45" in text
    assert "--timeout=300" in text
    assert "--timeout-method=thread" in text
    assert "fail-fast: false" in text
    assert "tests/contract/test_schema_conformance.py" in text
    assert "--ignore=tests/contract/test_schema_conformance.py" in text
    assert "hypothesis-contract-" in text
    assert ".hypothesis/examples" in text
    assert "derandomize" not in text.lower() or "Do not derandomize" in text
