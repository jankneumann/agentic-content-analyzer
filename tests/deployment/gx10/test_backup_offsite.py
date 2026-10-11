"""The off-site leg: ship only a proven generation, never overwrite, read back."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from scripts.gx10.backup import offsite

ROOT = Path(__file__).resolve().parents[3]
GENERATION = "20261010T030000Z"
COMPONENTS = (
    "application_postgresql",
    "falkordb",
    "langfuse_postgresql",
    "clickhouse",
    "minio",
    "configuration_metadata",
)
ENVELOPE = b"age-encryption.org/v1\n"


class FakeBucket:
    """The four calls the uploader makes, with S3's 404 shape."""

    def __init__(self, *, truncate: bool = False) -> None:
        self.objects: dict[str, bytes] = {}
        self.uploads: list[str] = []
        self.truncate = truncate

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, int]:  # noqa: N803
        if Key not in self.objects:
            raise ClientError(
                {"Error": {"Code": "404"}, "ResponseMetadata": {"HTTPStatusCode": 404}},
                "HeadObject",
            )
        return {"ContentLength": len(self.objects[Key])}

    def upload_file(self, filename: str, bucket: str, key: str, ExtraArgs: dict) -> None:  # noqa: N803
        body = Path(filename).read_bytes()
        self.objects[key] = body[:-1] if self.truncate else body
        self.uploads.append(key)

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> None:  # noqa: N803
        self.objects[Key] = Body
        self.uploads.append(Key)


def _write_generation(directory: Path, *, outcome: str = "succeeded") -> None:
    components = []
    for component in COMPONENTS:
        name = f"{component}-{GENERATION}.age"
        payload = ENVELOPE + component.encode() * 100
        (directory / name).write_bytes(payload)
        components.append(
            {
                "component": component,
                "outcome": "succeeded",
                "stage": "backup",
                "operation_id": "op",
                "trace_id": "t",
                "artifact_name": name,
                "bytes": len(payload),
                "checksum_sha256": hashlib.sha256(payload).hexdigest(),
                "encryption_recipient": "age1" + "q" * 58,
            }
        )
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "started_at": "2026-10-10T03:00:00Z",
                "completed_at": "2026-10-10T03:20:00Z",
                "outcome": outcome,
                "operation_id": "op",
                "trace_id": "t",
                "components": components,
            }
        )
    )


def _target() -> offsite.OffsiteTarget:
    return offsite.OffsiteTarget(
        endpoint="https://acct.r2.cloudflarestorage.com",
        bucket="aca-gx10-backups",
        access_key_id="id",
        secret_access_key="secret",
    )


def test_a_good_generation_lands_under_one_prefix_with_its_manifest_last(tmp_path: Path) -> None:
    _write_generation(tmp_path)
    bucket = FakeBucket()

    summary = offsite.ship_generation(tmp_path, _target(), bucket)

    assert summary["generation"] == GENERATION
    assert all(key.startswith(f"aca/gx10/{GENERATION}/") for key in bucket.objects)
    assert len(bucket.objects) == len(COMPONENTS) + 1
    assert bucket.uploads[-1] == f"aca/gx10/{GENERATION}/manifest.json"


def test_a_rerun_resumes_without_rewriting_anything(tmp_path: Path) -> None:
    _write_generation(tmp_path)
    bucket = FakeBucket()
    offsite.ship_generation(tmp_path, _target(), bucket)
    bucket.uploads.clear()

    summary = offsite.ship_generation(tmp_path, _target(), bucket)

    assert bucket.uploads == []
    assert set(summary["objects"].values()) == {"present"}


def test_an_existing_object_of_another_size_is_never_overwritten(tmp_path: Path) -> None:
    _write_generation(tmp_path)
    bucket = FakeBucket()
    key = f"aca/gx10/{GENERATION}/clickhouse-{GENERATION}.age"
    bucket.objects[key] = b"something else"

    with pytest.raises(offsite.OffsiteError, match="not overwriting"):
        offsite.ship_generation(tmp_path, _target(), bucket)
    assert bucket.objects[key] == b"something else"


def test_a_truncated_upload_is_caught_by_read_back(tmp_path: Path) -> None:
    _write_generation(tmp_path)

    with pytest.raises(offsite.OffsiteError, match="stored"):
        offsite.ship_generation(tmp_path, _target(), FakeBucket(truncate=True))


def test_an_artifact_that_rotted_locally_never_leaves(tmp_path: Path) -> None:
    _write_generation(tmp_path)
    victim = tmp_path / f"minio-{GENERATION}.age"
    victim.write_bytes(victim.read_bytes()[:-1] + b"X")
    bucket = FakeBucket()

    with pytest.raises(offsite.OffsiteError, match="no longer matches"):
        offsite.ship_generation(tmp_path, _target(), bucket)
    assert bucket.uploads == []


def test_a_partial_local_run_is_not_shipped(tmp_path: Path) -> None:
    _write_generation(tmp_path, outcome="partial")

    with pytest.raises(offsite.OffsiteError, match="partial"):
        offsite.ship_generation(tmp_path, _target(), FakeBucket())


def test_credentials_must_be_complete_and_https(tmp_path: Path) -> None:
    path = tmp_path / "offsite.json"
    path.write_text(json.dumps({"endpoint": "https://x", "bucket": "b"}))
    with pytest.raises(offsite.OffsiteError) as missing:
        offsite.OffsiteTarget.from_file(path)
    assert "secret" not in str(missing.value).replace("secret_access_key", "")

    path.write_text(
        json.dumps(
            {
                "endpoint": "http://x",
                "bucket": "b",
                "access_key_id": "i",
                "secret_access_key": "s",
            }
        )
    )
    with pytest.raises(offsite.OffsiteError, match="https"):
        offsite.OffsiteTarget.from_file(path)


def test_offsite_runs_only_after_a_good_local_backup_and_holds_keys_briefly() -> None:
    systemd = ROOT / "deploy/gx10/systemd"
    backup = (systemd / "aca-gx10-backup.service").read_text(encoding="utf-8")
    unit = (systemd / "aca-gx10-backup-offsite.service").read_text(encoding="utf-8")

    assert "OnSuccess=aca-gx10-backup-offsite.service" in backup
    # The local backup must never see the bucket keys.
    assert "offsite" not in backup.replace("OnSuccess=aca-gx10-backup-offsite.service", "")
    assert "OnFailure=aca-gx10-maintenance-alert@%n.service" in unit
    assert "render-offsite-secrets.sh" in unit
    assert "ExecStopPost=/usr/bin/rm -f /run/aca/gx10/backup/offsite.json" in unit
    assert "ReadOnlyPaths=/var/lib/aca/gx10/backups" in unit

    policy = (ROOT / "deploy/gx10/openbao/aca-gx10-backup.hcl").read_text(encoding="utf-8")
    assert 'path "secret/data/newsletter/gx10/backup-offsite"' in policy


def _render(tmp_path: Path, secret: dict[str, str]) -> subprocess.CompletedProcess[str]:
    backup_runtime = tmp_path / "runtime" / "backup"
    backup_runtime.mkdir(parents=True)
    (backup_runtime / "backup-openbao-token").write_text("token")
    tools = tmp_path / "bin"
    tools.mkdir()
    curl = tools / "curl"
    response = json.dumps({"data": {"data": secret}})
    curl.write_text("#!/usr/bin/env bash\nprintf '%s\\n' '" + response + "'\n")
    curl.chmod(0o700)
    return subprocess.run(
        [ROOT / "deploy/gx10/openbao/render-offsite-secrets.sh"],
        env=os.environ
        | {
            "PATH": f"{tools}:{os.environ['PATH']}",
            "GX10_RUNTIME_DIR": str(tmp_path / "runtime"),
            "GX10_BAO_ADDR": "http://openbao.test/v1",
        },
        capture_output=True,
        text=True,
    )


def test_renderer_writes_a_0600_file_the_uploader_accepts(tmp_path: Path) -> None:
    result = _render(
        tmp_path,
        {
            "endpoint": "https://acct.r2.cloudflarestorage.com",
            "bucket": "aca-gx10-backups",
            "access_key_id": "id",
            "secret_access_key": "secret",
        },
    )

    assert result.returncode == 0, result.stderr
    rendered = tmp_path / "runtime/backup/offsite.json"
    assert stat.S_IMODE(rendered.stat().st_mode) == 0o600
    target = offsite.OffsiteTarget.from_file(rendered)
    assert (target.prefix, target.region) == ("aca", "auto")


def test_renderer_refuses_a_secret_without_a_key_pair(tmp_path: Path) -> None:
    result = _render(tmp_path, {"endpoint": "https://x", "bucket": "b"})

    assert result.returncode != 0
    assert "key pair" in result.stderr
    assert not (tmp_path / "runtime/backup/offsite.json").exists()


def test_seed_script_stores_a_secret_the_renderer_accepts(tmp_path: Path) -> None:
    """Values come from stdin, never argv, and the policy is re-uploaded with them."""
    token = tmp_path / "token"
    token.write_text("root")
    tools = tmp_path / "bin"
    tools.mkdir()
    log = tmp_path / "calls"
    # Record each request's URL and body; curl reads the body from @file.
    (tools / "curl").write_text(
        "#!/usr/bin/env bash\n"
        'for a in "$@"; do case "$a" in @*) body="${a#@}";; http*) url="$a";; esac; done\n'
        f'printf "%s %s\\n" "$url" "$(jq -c . "$body")" >> {log}\n'
    )
    (tools / "curl").chmod(0o700)
    account = "a" * 32

    result = subprocess.run(
        [ROOT / "deploy/gx10/openbao/seed-offsite-secret.sh"],
        input=f"{account}\n\nKEYID\nSEKRET\n",
        env=os.environ
        | {
            "PATH": f"{tools}:{os.environ['PATH']}",
            "GX10_BAO_TOKEN_FILE": str(token),
            "GX10_BAO_ADDR": "http://openbao.test/v1",
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    calls = log.read_text().splitlines()
    secret_url, secret_body = calls[0].split(" ", 1)
    assert secret_url.endswith("/secret/data/newsletter/gx10/backup-offsite")
    assert json.loads(secret_body)["data"] == {
        "endpoint": f"https://{account}.r2.cloudflarestorage.com",
        "bucket": "aca-gx10-backups",
        "access_key_id": "KEYID",
        "secret_access_key": "SEKRET",
        "prefix": "aca",
        "region": "auto",
    }
    assert calls[1].split(" ", 1)[0].endswith("/sys/policies/acl/aca-gx10-backup")
    assert "backup-offsite" in json.loads(calls[1].split(" ", 1)[1])["policy"]
    assert "SEKRET" not in result.stdout + result.stderr
