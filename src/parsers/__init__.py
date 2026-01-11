"""Document parsing module with pluggable parser backends."""

from src.parsers.base import DocumentParser
from src.parsers.docling_parser import DoclingParser
from src.parsers.markitdown_parser import MarkItDownParser
from src.parsers.router import ParserRouter
from src.parsers.youtube_parser import YouTubeParser

__all__ = [
    "DocumentParser",
    "DoclingParser",
    "MarkItDownParser",
    "ParserRouter",
    "YouTubeParser",
]
