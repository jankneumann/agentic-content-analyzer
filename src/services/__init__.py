"""Services for the Newsletter Aggregator."""

from src.services.chat_service import ChatMetadata, ChatService
from src.services.content_service import ContentService
from src.services.image_extractor import ImageExtractor, compute_phash_similarity
from src.services.image_storage import (
    ImageStorageProvider,
    LocalImageStorage,
    S3ImageStorage,
    get_image_storage,
)
from src.services.prompt_service import PromptService
from src.services.review_service import ReviewService
from src.services.script_review_service import ScriptReviewService

__all__ = [
    "ChatMetadata",
    "ChatService",
    "ContentService",
    "ImageExtractor",
    "ImageStorageProvider",
    "LocalImageStorage",
    "S3ImageStorage",
    "get_image_storage",
    "compute_phash_similarity",
    "PromptService",
    "ReviewService",
    "ScriptReviewService",
]
