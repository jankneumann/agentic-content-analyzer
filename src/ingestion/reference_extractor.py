"""Backward-compatibility shim — module moved to src.services.reference_extractor."""

from src.services.reference_extractor import (  # noqa: F401
    ARXIV_PATTERNS,
    DOI_PATTERNS,
    REFERENCE_PATTERNS,
    S2_URL_PATTERN,
    ReferenceExtractionResult,
    ReferenceExtractor,
)

__all__ = ["ReferenceExtractor", "ReferenceExtractionResult"]
