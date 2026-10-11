"""Copy the newest verified GX-10 backup generation off the host.

The local backup writes age-encrypted artifacts to the same disk as the data
they protect, so one disk failure loses both. This runs after a successful
local run (``OnSuccess=`` on the backup unit) and copies that generation to an
S3-compatible bucket -- Cloudflare R2 in production.

It is a separate process on purpose: the bucket credentials never enter the
process that holds the age material, and an off-site failure alerts as its own
unit instead of failing a local backup that worked.

Three rules, each closing a way this could report success without a copy:

* Every artifact is re-hashed against the manifest BEFORE it leaves. A file
  that rotted on disk would otherwise be faithfully copied off-site.
* An existing key is never overwritten. The bucket carries a lock rule, so an
  overwrite would be refused anyway; a same-size object is a resumed upload,
  a different-size one is an error worth a human.
* The stored size is read back after each upload, and the manifest is written
  LAST, so a generation with a manifest off-site is a complete one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from src.clients.operational_observability import operational_entrypoint
from src.services.backup.gx10 import BackupManifest

_AGE_ENVELOPE = b"age-encryption.org/v1\n"
_ARTIFACT = re.compile(r"^(?P<component>[a-z_]+)-(?P<generation>\d{8}T\d{6}Z)\.age$")
_CHUNK = 8 * 1024 * 1024


class OffsiteError(RuntimeError):
    """The generation could not be proven to exist off-site."""


@dataclass(frozen=True, slots=True)
class OffsiteTarget:
    endpoint: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    prefix: str = "aca"
    region: str = "auto"

    @classmethod
    def from_file(cls, path: Path) -> OffsiteTarget:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise OffsiteError("off-site credentials must be a JSON object")
        missing = [
            key
            for key in ("endpoint", "bucket", "access_key_id", "secret_access_key")
            if not isinstance(payload.get(key), str) or not payload[key]
        ]
        if missing:
            # Names only: the values are secrets.
            raise OffsiteError(f"off-site credentials missing {missing}")
        if not payload["endpoint"].startswith("https://"):
            raise OffsiteError("off-site endpoint must be https")
        return cls(
            endpoint=payload["endpoint"],
            bucket=payload["bucket"],
            access_key_id=payload["access_key_id"],
            secret_access_key=payload["secret_access_key"],
            prefix=str(payload.get("prefix") or "aca").strip("/"),
            region=str(payload.get("region") or "auto"),
        )

    def client(self) -> Any:
        import boto3
        from botocore.config import Config

        return boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            region_name=self.region,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 5, "mode": "standard"},
                # boto3 >= 1.36 adds CRC checksums by default, which R2 has
                # rejected on multipart uploads. Size read-back is the proof.
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )


@dataclass(frozen=True, slots=True)
class PlannedArtifact:
    path: Path
    key: str
    size: int
    sha256: str


def generation_prefix(prefix: str, generation: str) -> str:
    """`<prefix>/gx10/<generation>/` -- one directory per generation, so a
    bucket lock or lifecycle rule on `<prefix>/gx10/` covers every artifact."""
    return f"{prefix}/gx10/{generation}"


def plan_generation(artifact_dir: Path, prefix: str) -> tuple[str, list[PlannedArtifact]]:
    """Read the local manifest and prove every artifact it names is intact."""
    manifest_path = artifact_dir / "manifest.json"
    if not manifest_path.is_file():
        raise OffsiteError(f"no local manifest at {manifest_path}")
    manifest = BackupManifest.from_json(manifest_path.read_text(encoding="utf-8"))
    if manifest.outcome != "succeeded":
        raise OffsiteError(f"refusing to ship a generation whose outcome is {manifest.outcome}")

    generations: set[str] = set()
    planned: list[PlannedArtifact] = []
    for component in manifest.components:
        name = component.artifact_name
        if component.outcome != "succeeded" or not name:
            raise OffsiteError(f"manifest component {component.component} did not succeed")
        match = _ARTIFACT.match(name)
        if not match or match.group("component") != str(component.component):
            raise OffsiteError(f"manifest artifact name {name!r} is not one this backup writes")
        generations.add(match.group("generation"))
        path = artifact_dir / name
        size, digest = _hash_artifact(path)
        if size != component.bytes or digest != component.checksum_sha256:
            raise OffsiteError(f"{name} no longer matches its manifest entry")
        planned.append(PlannedArtifact(path=path, key="", size=size, sha256=digest))

    if len(generations) != 1:
        raise OffsiteError(f"manifest spans generations {sorted(generations)}")
    generation = generations.pop()
    base = generation_prefix(prefix, generation)
    return generation, [
        PlannedArtifact(
            path=item.path,
            key=f"{base}/{item.path.name}",
            size=item.size,
            sha256=item.sha256,
        )
        for item in planned
    ]


def _hash_artifact(path: Path) -> tuple[int, str]:
    if not path.is_file():
        raise OffsiteError(f"{path.name} is missing locally")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        head = handle.read(len(_AGE_ENVELOPE))
        if head != _AGE_ENVELOPE:
            raise OffsiteError(f"refusing to ship {path.name}: not an age artifact")
        digest.update(head)
        size += len(head)
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def _stored_size(client: Any, bucket: str, key: str) -> int | None:
    from botocore.exceptions import ClientError

    try:
        response = client.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status == 404 or exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
            return None
        raise
    return int(response["ContentLength"])


def ship_artifact(
    client: Any, bucket: str, item: PlannedArtifact
) -> Literal["uploaded", "present"]:
    existing = _stored_size(client, bucket, item.key)
    if existing is not None:
        if existing == item.size:
            return "present"
        raise OffsiteError(
            f"{item.key} exists off-site with {existing} bytes, local has {item.size}; "
            "not overwriting"
        )
    client.upload_file(
        str(item.path),
        bucket,
        item.key,
        ExtraArgs={"Metadata": {"sha256": item.sha256}},
    )
    stored = _stored_size(client, bucket, item.key)
    if stored != item.size:
        raise OffsiteError(f"{item.key} stored {stored} bytes, expected {item.size}")
    return "uploaded"


def ship_generation(artifact_dir: Path, target: OffsiteTarget, client: Any) -> dict[str, Any]:
    generation, planned = plan_generation(artifact_dir, target.prefix)
    results = {item.key: ship_artifact(client, target.bucket, item) for item in planned}

    # Last, so its presence off-site means every artifact above is there.
    manifest_body = (artifact_dir / "manifest.json").read_bytes()
    manifest_key = f"{generation_prefix(target.prefix, generation)}/manifest.json"
    if _stored_size(client, target.bucket, manifest_key) is None:
        client.put_object(Bucket=target.bucket, Key=manifest_key, Body=manifest_body)
        results[manifest_key] = "uploaded"
    else:
        results[manifest_key] = "present"
    if _stored_size(client, target.bucket, manifest_key) != len(manifest_body):
        raise OffsiteError(f"{manifest_key} did not read back at {len(manifest_body)} bytes")

    return {
        "generation": generation,
        "bucket": target.bucket,
        "bytes": sum(item.size for item in planned) + len(manifest_body),
        "objects": results,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gx10-backup-offsite")
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--credentials-file", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        target = OffsiteTarget.from_file(args.credentials_file)
        summary = ship_generation(args.artifacts, target, target.client())
    except OffsiteError as exc:
        print(f"gx10 off-site backup failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


@operational_entrypoint(
    "gx10.backup.offsite",
    stage="backup",
    service_name="aca-gx10-backup-offsite",
    result_outcome=lambda code: "succeeded" if code == 0 else "permanent_failure",
)
def scheduled_main(argv: Sequence[str] | None = None) -> int:
    return main(argv)


if __name__ == "__main__":
    raise SystemExit(scheduled_main())
