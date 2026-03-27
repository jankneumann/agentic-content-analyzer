"""Type stub for Settings extension — contract for wp-config.

Shows the DELTA to the existing Settings class. Only new fields are listed.
"""


class SettingsExtension:
    """New fields added to src/config/settings.py Settings class."""

    # Feature flag — disabled by default, zero-cost when off
    enable_kreuzberg: bool  # default: False
    # env: ENABLE_KREUZBERG

    # Comma-separated format list for Kreuzberg routing preference
    # e.g. "docx,epub,html" — only these formats route to Kreuzberg
    kreuzberg_preferred_formats: str  # default: ""
    # env: KREUZBERG_PREFERRED_FORMATS

    # Comma-separated format list for shadow comparison mode
    # e.g. "pdf,docx" — Kreuzberg runs in parallel for these formats
    kreuzberg_shadow_formats: str  # default: ""
    # env: KREUZBERG_SHADOW_FORMATS

    # Size limit matching Docling default
    kreuzberg_max_file_size_mb: int  # default: 100
    # env: KREUZBERG_MAX_FILE_SIZE_MB

    # Lower than Docling (120s vs 300s) since Kreuzberg is faster
    kreuzberg_timeout_seconds: int  # default: 120
    # env: KREUZBERG_TIMEOUT_SECONDS
