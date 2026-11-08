"""Resolve a note's authored date for file-based ingestion.

Uploaded notes (an Evernote export converted to Markdown, an Obsidian Web
Clipper note, a dated document) usually carry the date they were written,
either in YAML frontmatter or in the title/filename. Without this, a file
upload's ``published_date`` falls back to the ingest time, so a one-time
import of years-old notes lands in *today's* digest instead of in its own
period.

Precedence (first usable value wins):

1. Frontmatter ``created``-style keys (see ``FRONTMATTER_DATE_KEYS``)
2. A date in the resolved title
3. A date in the filename stem
4. The parser's own ``created_date`` metadata
5. The ingest time

A candidate is only used if it is a real calendar date between 1970 and now
(plus one day of clock-skew tolerance); anything else falls through to the
next source. Naive timestamps and date-only values are interpreted as UTC.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import yaml

# Ordered by how directly the key means "when this note was created".
# ``captured_at`` is the Obsidian vault clip contract's creation field;
# ``date`` is the most generic and therefore last.
FRONTMATTER_DATE_KEYS: tuple[str, ...] = (
    "created",
    "created_at",
    "date_created",
    "creation_date",
    "captured_at",
    "date",
)

# Only this much of a file is scanned for frontmatter.
FRONTMATTER_SCAN_BYTES = 64 * 1024

# Formats whose raw bytes may start with YAML frontmatter.
FRONTMATTER_FORMATS = frozenset({"md", "markdown", "txt"})

_MIN_DATE = datetime(1970, 1, 1, tzinfo=UTC)
_FUTURE_TOLERANCE = timedelta(days=1)

_FRONTMATTER_RE = re.compile(
    r"\A(?:\ufeff)?---[ \t]*\r?\n(.*?)\r?\n(?:---|\.\.\.)[ \t]*(?:\r?\n|\Z)", re.S
)

# Dates embedded in a title or filename. Digits on either side disqualify a
# match so order numbers and timestamps are not misread as dates.
_SEPARATED_DATE_RE = re.compile(r"(?<!\d)(\d{4})([-_.])(\d{2})\2(\d{2})(?!\d)")
_COMPACT_DATE_RE = re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)")


@dataclass(frozen=True)
class ResolvedNoteDate:
    """The chosen date and where it came from (for ``metadata_json``)."""

    value: datetime
    source: str


def resolve_note_date(
    *,
    raw_head: bytes | None,
    title: str | None,
    filename_stem: str | None,
    parser_created: datetime | None,
    now: datetime | None = None,
) -> ResolvedNoteDate:
    """Pick the best authored date for a note; never raises."""
    current = now or datetime.now(UTC)

    if raw_head:
        found = date_from_frontmatter(raw_head, now=current)
        if found is not None:
            return found

    for label, text in (("title", title), ("filename", filename_stem)):
        if text:
            value = date_from_text(text, now=current)
            if value is not None:
                return ResolvedNoteDate(value, label)

    if parser_created is not None:
        value = _validated(_as_utc(parser_created), current)
        if value is not None:
            return ResolvedNoteDate(value, "parser")

    return ResolvedNoteDate(current, "ingested_at")


def date_from_frontmatter(raw_head: bytes, *, now: datetime) -> ResolvedNoteDate | None:
    """Return the first usable created-style date in leading YAML frontmatter."""
    text = raw_head[:FRONTMATTER_SCAN_BYTES].decode("utf-8", errors="replace")
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return None
    try:
        loaded = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    if not isinstance(loaded, dict):
        return None

    by_key = {str(key).strip().lower(): value for key, value in loaded.items()}
    for key in FRONTMATTER_DATE_KEYS:
        if key not in by_key:
            continue
        value = _validated(_coerce_datetime(by_key[key]), now)
        if value is not None:
            return ResolvedNoteDate(value, f"frontmatter:{key}")
    return None


def date_from_text(text: str, *, now: datetime) -> datetime | None:
    """Return the leftmost valid calendar date found in a title or filename."""
    for candidate in _text_date_candidates(text):
        value = _validated(candidate, now)
        if value is not None:
            return value
    return None


def _text_date_candidates(text: str) -> list[datetime]:
    """Real calendar dates embedded in ``text``, leftmost first (unvalidated)."""
    candidates: list[tuple[int, datetime]] = []
    for match in _SEPARATED_DATE_RE.finditer(text):
        parsed = _calendar_date(match.group(1), match.group(3), match.group(4))
        if parsed is not None:
            candidates.append((match.start(), parsed))
    for match in _COMPACT_DATE_RE.finditer(text):
        parsed = _calendar_date(match.group(1), match.group(2), match.group(3))
        if parsed is not None:
            candidates.append((match.start(), parsed))
    return [value for _, value in sorted(candidates, key=lambda item: item[0])]


def _coerce_datetime(value: Any) -> datetime | None:
    """Turn a YAML scalar (already-parsed date/datetime or a string) into UTC."""
    if isinstance(value, datetime):
        return _as_utc(value)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=UTC)
    if not isinstance(value, str):
        return None

    raw = value.strip()
    if not raw:
        return None
    # fromisoformat (3.11+) reads ISO basic and extended forms, including
    # Evernote's 20190314T102200Z, but not a lowercase "z" designator.
    normalized = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
    try:
        return _as_utc(datetime.fromisoformat(normalized))
    except ValueError:
        # Free-form values such as "14 March 2019 (2019-03-14)" or "2019.03.14".
        candidates = _text_date_candidates(raw)
        return candidates[0] if candidates else None


def _calendar_date(year: str, month: str, day: str) -> datetime | None:
    try:
        return datetime(int(year), int(month), int(day), tzinfo=UTC)
    except ValueError:
        return None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _validated(value: datetime | None, now: datetime) -> datetime | None:
    if value is None:
        return None
    if value < _MIN_DATE or value > _as_utc(now) + _FUTURE_TOLERANCE:
        return None
    return value
