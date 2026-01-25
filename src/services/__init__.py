"""Services for the Newsletter Aggregator."""

from src.services.chat_service import ChatMetadata, ChatService
from src.services.content_service import ContentService
from src.services.file_storage import (
    FileStorageProvider,
    # Backward-compatible aliases
    ImageStorageProvider,
    LocalFileStorage,
    LocalImageStorage,
    S3FileStorage,
    S3ImageStorage,
    SupabaseFileStorage,
    SupabaseImageStorage,
    compute_file_hash,
    get_image_storage,
    get_storage,
)
from src.services.image_extractor import ImageExtractor, compute_phash_similarity
from src.services.prompt_service import PromptService
from src.services.review_service import ReviewService
from src.services.script_review_service import ScriptReviewService

__all__ = [
    "ChatMetadata",
    "ChatService",
    "ContentService",
    "ImageExtractor",
    # New generic file storage exports
    "FileStorageProvider",
    "LocalFileStorage",
    "S3FileStorage",
    "SupabaseFileStorage",
    "get_storage",
    # Backward-compatible image storage aliases
    "ImageStorageProvider",
    "LocalImageStorage",
    "S3ImageStorage",
    "SupabaseImageStorage",
    "get_image_storage",
    "compute_file_hash",
    "compute_phash_similarity",
    "PromptService",
    "ReviewService",
    "ScriptReviewService",
]
