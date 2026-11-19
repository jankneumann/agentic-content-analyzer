"""ClickHouse's own logging stays bounded on the gx-10.

The stock system log tables have no TTL. On 2026-11-16 system.trace_log and
system.text_log held 90 GiB beside ~1 MB of Langfuse data, every nightly backup
copied them, and seven backup generations filled the disk.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET  # noqa: S405 - parses a file from this repository
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "deploy/gx10/clickhouse/system-logs.xml"
MOUNT = (
    "./deploy/gx10/clickhouse/system-logs.xml"
    ":/etc/clickhouse-server/config.d/gx10-system-logs.xml:ro"
)
# Every system log that held data on the host; the image's other logs stay empty
# for Langfuse's workload (backup_log, crash_log, query_views_log ...).
DEFAULT_LOGS = {
    "query_log",
    "part_log",
    "metric_log",
    "asynchronous_metric_log",
    "latency_log",
    "error_log",
    "query_metric_log",
    "opentelemetry_span_log",
    "processors_profile_log",
}
REMOVED_LOGS = {"trace_log", "text_log"}
TTL = re.compile(r"(event_date|finish_date) \+ INTERVAL (\d+) DAY DELETE$")


def _config() -> ET.Element:
    return ET.parse(CONFIG).getroot()  # noqa: S314


def _ttl(element: ET.Element) -> str | None:
    """A log's TTL lives in <ttl>, or inside <engine> when the log has its own engine."""
    if (ttl := element.findtext("ttl")) is not None:
        return ttl.strip()
    engine = " ".join((element.findtext("engine") or "").split())
    _, found, ttl = engine.partition(" TTL ")
    return ttl if found else None


def test_clickhouse_mounts_the_system_log_config_read_only() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.gx10.yml").read_text())
    assert MOUNT in compose["services"]["clickhouse"]["volumes"]


def test_profiler_and_text_logs_are_removed() -> None:
    root = _config()
    for name in REMOVED_LOGS:
        element = root.find(name)
        assert element is not None, name
        assert element.get("remove") == "1", name


def test_every_default_system_log_expires_within_a_week() -> None:
    root = _config()
    for name in DEFAULT_LOGS:
        element = root.find(name)
        assert element is not None, name
        ttl = _ttl(element)
        assert ttl is not None, f"{name} has no TTL"
        match = TTL.fullmatch(ttl)
        assert match, f"{name}: unexpected TTL {ttl!r}"
        assert int(match.group(2)) <= 7, name


def test_no_log_sets_both_engine_and_ttl() -> None:
    """ClickHouse refuses to start when a system log has both (BAD_ARGUMENTS, code 36)."""
    for element in _config():
        assert not (element.find("engine") is not None and element.find("ttl") is not None), (
            element.tag
        )


def test_config_enables_no_system_log_the_image_does_not_create() -> None:
    """A section for an optional log (session_log, zookeeper_log ...) switches it on."""
    configured = {child.tag for child in _config()} - {"logger"}
    assert configured == DEFAULT_LOGS | REMOVED_LOGS


def test_server_log_files_are_capped() -> None:
    logger = _config().find("logger")
    assert logger is not None
    assert logger.findtext("level") == "warning"
    assert logger.findtext("size") == "100M"
    assert int(logger.findtext("count") or "0") <= 3
