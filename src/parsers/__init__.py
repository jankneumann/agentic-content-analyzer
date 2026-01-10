"""Document parsing module with pluggable parser backends."""

from src.parsers.base import DocumentParser
from src.parsers.markitdown_parser import MarkItDownParser
from src.parsers.router import ParserRouter

__all__ = [
    "DocumentParser",
    "MarkItDownParser",
    "ParserRouter",
]
