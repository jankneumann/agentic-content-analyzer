"""Settings-level coverage for the Gemini batch kill switch."""

from src.config.settings import Settings


def test_batch_kill_switch_defaults_false_without_env_file(monkeypatch):
    monkeypatch.delenv("GEMINI_BATCH_ENABLED", raising=False)

    settings = Settings(_env_file=None)

    assert settings.gemini_batch_enabled is False


def test_batch_kill_switch_reads_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_BATCH_ENABLED", "true")

    settings = Settings(_env_file=None)

    assert settings.gemini_batch_enabled is True
