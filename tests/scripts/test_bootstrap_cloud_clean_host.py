from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_bootstrap_exit_audit_runs_without_project_or_venv_dependencies(tmp_path: Path) -> None:
    project = tmp_path / "clean-project"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    script = scripts / "bootstrap-cloud.sh"
    shutil.copy2(ROOT / "scripts/bootstrap-cloud.sh", script)
    audit_directory = tmp_path / "audit"
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "ACA_BOOTSTRAP_AUDIT_DIR": str(audit_directory),
    }

    completed = subprocess.run(
        ["/usr/bin/env", "bash", str(script), "--check"],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    path = audit_directory / "events.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert records[-1]["entrypoint"] == "bootstrap.bootstrap_cloud"
    assert records[-1]["outcome"] == "succeeded"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    exit_function = script.read_text(encoding="utf-8").split("trap bootstrap_audit_exit", 1)[0]
    assert "src.clients.operational_observability" not in exit_function
    assert ".venv/bin/python" not in exit_function
