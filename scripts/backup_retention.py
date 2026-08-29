#!/usr/bin/env python3
"""Render and (optionally) apply backup-target lifecycle rules.

DRY RUN BY DEFAULT. Without `--apply` this prints the rules it would set and
touches nothing. That is not politeness: this is the only tool in the repository
that can be pointed at the backup target with write authority over its lifecycle
configuration, and a lifecycle rule with a wrong prefix deletes backups rather
than data.

It is also NOT a deletion tool. It sets provider-side expiry policy; the provider
does the expiring, on its own schedule, and keeps doing so while gx-10 is down. No
scheduled process in this repository deletes a backup object, and nothing here
issues a delete call.

Usage::

    python scripts/backup_retention.py                    # dry run, R2 dialect
    python scripts/backup_retention.py --dialect aws      # dry run, AWS dialect
    python scripts/backup_retention.py --apply            # actually set the rules
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from src.clients.operational_observability import operational_entrypoint

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = REPO_ROOT / "deploy" / "backup" / "retention.yaml"

#: R2 accepts the S3 lifecycle API but ignores tag-based filters, so both dialects
#: are expressed purely as prefix + age. Keeping them structurally identical is
#: what makes "the same policy on either provider" checkable rather than hoped for.
DIALECTS = ("r2", "aws")


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text())
    if not isinstance(document, dict) or "tiers" not in document:
        raise ValueError(f"{path} is not a retention policy document")
    return document


def build_rules(policy: dict[str, Any], *, prefix: str, dialect: str) -> list[dict[str, Any]]:
    """Render the policy into S3 lifecycle rules for one dialect.

    Deliberately prefix-and-age only. R2 supports no tag filters, so a tag-based
    rule would silently apply to nothing there while appearing to work on AWS.
    """
    if dialect not in DIALECTS:
        raise ValueError(f"unknown dialect {dialect!r}; expected one of {DIALECTS}")

    base = prefix.strip("/")
    rules: list[dict[str, Any]] = []
    for tier in policy["tiers"]:
        rules.append(
            {
                "ID": f"aca-backup-{tier['name']}",
                "Status": "Enabled",
                "Filter": {"Prefix": f"{base}/{tier['prefix_suffix']}"},
                "Expiration": {"Days": int(tier["retain_days"])},
            }
        )

    if dialect == "aws":
        # AWS charges for incomplete multipart uploads indefinitely; R2 does not.
        # This is the only place the two dialects differ, and it is an addition
        # rather than a change, so the expiry policy itself stays identical.
        rules.append(
            {
                "ID": "aca-backup-abort-incomplete-uploads",
                "Status": "Enabled",
                "Filter": {"Prefix": f"{base}/"},
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
            }
        )
    return rules


def _excluded_prefixes(policy: dict[str, Any], prefix: str) -> list[str]:
    base = prefix.strip("/")
    return [f"{base}/{item['prefix_suffix']}" for item in policy.get("exclusions", [])]


def _assert_no_rule_covers_an_exclusion(rules: list[dict[str, Any]], excluded: list[str]) -> None:
    """Refuse to emit a rule that would expire the manifest.

    An expired manifest reports `no_history`, which is indistinguishable from a
    backup that never ran — so this failure mode is silent and would make the
    freshness check lie in the safe-looking direction.
    """
    for rule in rules:
        rule_prefix = rule["Filter"]["Prefix"]
        for exclusion in excluded:
            if exclusion.startswith(rule_prefix) or rule_prefix.startswith(exclusion):
                raise ValueError(
                    f"lifecycle rule {rule['ID']} (prefix {rule_prefix!r}) would cover "
                    f"excluded prefix {exclusion!r}"
                )


def render(policy: dict[str, Any], *, prefix: str, dialect: str) -> dict[str, Any]:
    rules = build_rules(policy, prefix=prefix, dialect=dialect)
    _assert_no_rule_covers_an_exclusion(rules, _excluded_prefixes(policy, prefix))
    return {"Rules": rules}


def apply_rules(bucket: str, configuration: dict[str, Any], settings: Any) -> None:
    """Set the lifecycle configuration. Only ever reached via an explicit --apply."""
    import boto3

    def plain(value: object) -> str | None:
        if value is None:
            return None
        if hasattr(value, "get_secret_value"):
            return str(value.get_secret_value())
        return str(value) or None

    client = boto3.client(
        "s3",
        endpoint_url=plain(getattr(settings, "backup_s3_endpoint", None)),
        region_name=str(getattr(settings, "backup_s3_region", None) or "auto"),
        aws_access_key_id=plain(getattr(settings, "backup_s3_access_key_id", None)),
        aws_secret_access_key=plain(getattr(settings, "backup_s3_secret_access_key", None)),
    )
    client.put_bucket_lifecycle_configuration(
        Bucket=bucket,
        LifecycleConfiguration=configuration,
    )


@operational_entrypoint("script.backup_retention", stage="cleanup", service_name="aca-script")
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually set the lifecycle rules. Without this the script only prints them.",
    )
    parser.add_argument("--dialect", choices=DIALECTS, default="r2")
    parser.add_argument("--prefix", default=None, help="Override BACKUP_S3_PREFIX.")
    parser.add_argument("--bucket", default=None, help="Override BACKUP_S3_BUCKET.")
    args = parser.parse_args(argv)

    from src.config.settings import get_settings

    settings = get_settings()
    prefix = args.prefix or str(getattr(settings, "backup_s3_prefix", None) or "aca")
    bucket = args.bucket or getattr(settings, "backup_s3_bucket", None)

    configuration = render(load_policy(), prefix=prefix, dialect=args.dialect)

    if not args.apply:
        print("DRY RUN — no changes made. Re-run with --apply to set these rules.")
        print(f"bucket:  {bucket or '(BACKUP_S3_BUCKET is not set)'}")
        print(f"dialect: {args.dialect}")
        print(json.dumps(configuration, indent=2))
        return 0

    if not bucket:
        print("BACKUP_S3_BUCKET is not set; refusing to apply.", file=sys.stderr)
        return 1

    apply_rules(str(bucket), configuration, settings)
    print(f"Applied {len(configuration['Rules'])} lifecycle rules to {bucket}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
