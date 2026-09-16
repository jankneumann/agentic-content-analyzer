"""Lock the scheduled live-ingest job against unnamed 30-minute cancels."""

from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "real-ingestion-scheduled.yml"
)


def test_scheduled_real_ingest_uses_per_test_timeout() -> None:
    text = WORKFLOW.read_text()
    assert "--timeout=180" in text
    assert "--timeout-method=signal" in text


def test_scheduled_workflow_warns_when_live_credentials_are_empty() -> None:
    """Empty GitHub secrets used to skip Gmail/YouTube with no job annotation."""

    text = WORKFLOW.read_text()
    assert "::warning" in text
    assert "GMAIL_OAUTH_TOKEN_JSON" in text
    assert "YOUTUBE_API_KEY" in text
    assert "Surface missing live credentials" in text
