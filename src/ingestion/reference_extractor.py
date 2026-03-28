"""Extract academic paper references from existing ingested content."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ReferenceExtractionResult:
    content_scanned: int = 0
    references_found: int = 0
    references_resolved: int = 0
    references_unresolved: int = 0
    papers_ingested: int = 0
    papers_skipped_duplicate: int = 0


# Regex patterns for academic identifiers
ARXIV_PATTERNS = [
    re.compile(r"arXiv:(\d{4}\.\d{4,})", re.IGNORECASE),
    re.compile(r"arxiv\.org/abs/(\d{4}\.\d{4,})"),
    re.compile(r"arxiv\.org/pdf/(\d{4}\.\d{4,})"),
]

DOI_PATTERNS = [
    re.compile(r"doi\.org/(10\.\d{4,}/[^\s)\"'>]+)"),
    re.compile(r"DOI:\s*(10\.\d{4,}/[^\s)\"'>]+)", re.IGNORECASE),
]

S2_URL_PATTERN = re.compile(r"semanticscholar\.org/paper/[^/]+/([0-9a-f]{40})")


class ReferenceExtractor:
    """Extracts academic paper references from Content markdown."""

    def extract_arxiv_ids(self, text: str) -> set[str]:
        ids: set[str] = set()
        for pattern in ARXIV_PATTERNS:
            for match in pattern.finditer(text):
                ids.add(match.group(1))
        return ids

    def extract_dois(self, text: str) -> set[str]:
        dois: set[str] = set()
        for pattern in DOI_PATTERNS:
            for match in pattern.finditer(text):
                # Clean trailing punctuation
                doi = match.group(1).rstrip(".,;:")
                dois.add(doi)
        return dois

    def extract_s2_ids(self, text: str) -> set[str]:
        return {m.group(1) for m in S2_URL_PATTERN.finditer(text)}

    def extract_all(self, text: str) -> dict[str, set[str]]:
        return {
            "arxiv": self.extract_arxiv_ids(text),
            "doi": self.extract_dois(text),
            "s2": self.extract_s2_ids(text),
        }

    def extract_from_contents(
        self,
        contents: list,  # list of Content model instances
        after: str | None = None,
        before: str | None = None,
    ) -> list[str]:
        """Extract unique identifiers from Content records.

        Returns list of identifiers in S2-compatible format:
        - ArXiv:YYMM.NNNNN for arXiv IDs
        - DOI:10.xxx/... for DOIs
        - Raw hex for S2 IDs
        """
        all_ids: set[str] = set()
        scanned = 0

        for content in contents:
            text = content.markdown_content or ""
            if not text:
                continue
            scanned += 1

            refs = self.extract_all(text)
            for arxiv_id in refs["arxiv"]:
                all_ids.add(f"ArXiv:{arxiv_id}")
            for doi in refs["doi"]:
                all_ids.add(f"DOI:{doi}")
            for s2_id in refs["s2"]:
                all_ids.add(s2_id)

        logger.info(
            "Scanned %d content records, found %d unique references",
            scanned,
            len(all_ids),
        )
        return sorted(all_ids)
