from __future__ import annotations

from src.services.backup.engine import BackupEngine


def test_backup_run_declares_a_non_payload_operational_root() -> None:
    assert BackupEngine.run.__aca_operational_entrypoint__ == (
        "backup.run",
        "backup",
        "aca-backup",
    )
    assert BackupEngine.run.__name__ == "run"
    assert not hasattr(BackupEngine.run, "__aca_capture_arguments__")
