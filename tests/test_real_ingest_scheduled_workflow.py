"""Lock the scheduled live-ingest job against unnamed 30-minute cancels."""

from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "real-ingestion-scheduled.yml"
)


def test_scheduled_real_ingest_uses_per_test_timeout() -> None:
    text = WORKFLOW.read_text()
    assert "--timeout=180" in text
    assert "--timeout-method=signal" in text
