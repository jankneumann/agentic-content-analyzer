"""API endpoints for unified file storage access.

Provides REST endpoints for:
- File retrieval from any storage bucket
- Content-Type detection
- Range request support for audio/video streaming
- Signed URL redirect for cloud storage
"""

import mimetypes
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response

from src.services.file_storage import get_storage
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/files", tags=["files"])

# Valid bucket names
VALID_BUCKETS = {"images", "podcasts", "audio-digests"}


def get_content_type(path: str) -> str:
    """Detect content type from file path using mimetypes.

    Args:
        path: File path or filename

    Returns:
        MIME type string, defaults to application/octet-stream
    """
    content_type, _ = mimetypes.guess_type(path)
    return content_type or "application/octet-stream"


def parse_range_header(range_header: str, file_size: int) -> tuple[int, int]:
    """Parse HTTP Range header.

    Args:
        range_header: Range header value (e.g., "bytes=0-1023")
        file_size: Total file size in bytes

    Returns:
        Tuple of (start, end) byte positions

    Raises:
        HTTPException: If range is invalid
    """
    if not range_header.startswith("bytes="):
        raise HTTPException(status_code=416, detail="Invalid range format")

    range_spec = range_header[6:]  # Remove "bytes="

    if "-" not in range_spec:
        raise HTTPException(status_code=416, detail="Invalid range format")

    start_str, end_str = range_spec.split("-", 1)

    if start_str == "":
        # Suffix range: "-500" means last 500 bytes
        suffix_length = int(end_str)
        start = max(0, file_size - suffix_length)
        end = file_size - 1
    elif end_str == "":
        # Open-ended range: "500-" means from byte 500 to end
        start = int(start_str)
        end = file_size - 1
    else:
        start = int(start_str)
        end = min(int(end_str), file_size - 1)

    if start > end or start >= file_size:
        raise HTTPException(
            status_code=416,
            detail="Range not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    return start, end


@router.get("/{bucket}/{path:path}")
async def get_file(
    bucket: str,
    path: str,
    request: Request,
    range: Annotated[str | None, Header()] = None,
):
    """Retrieve a file from storage.

    Supports:
    - Multiple storage buckets (images, podcasts, audio-digests)
    - Content-Type detection via file extension
    - Range requests for audio/video streaming
    - Signed URL redirect for cloud storage (S3, Supabase)

    Args:
        bucket: Storage bucket name
        path: File path within the bucket
        range: Optional HTTP Range header for partial content

    Returns:
        File content or redirect to signed URL
    """
    # Validate bucket
    if bucket not in VALID_BUCKETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid bucket. Valid buckets: {', '.join(VALID_BUCKETS)}",
        )

    # Get storage provider
    storage = get_storage(bucket=bucket)

    # Construct full storage path
    storage_path = f"{bucket}/{path}"

    # Check if file exists
    if not await storage.exists(storage_path):
        raise HTTPException(status_code=404, detail="File not found")

    # For cloud providers, redirect to signed URL (better for large files)
    if hasattr(storage, "get_signed_url") and storage.provider_name in ("s3", "supabase"):
        signed_url = await storage.get_signed_url(storage_path, expires_in=3600)
        return RedirectResponse(url=signed_url, status_code=302)

    # Check for local file optimization (prevents DoS from loading large files into RAM)
    local_path = storage.get_local_path(storage_path)
    content_type = get_content_type(path)

    if local_path and local_path.exists():
        # Let FastAPI/Starlette handle the streaming and ranges
        return FileResponse(
            path=local_path,
            media_type=content_type,
            filename=path.split("/")[-1],
            headers={
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=3600",
            },
        )

    # Fallback for non-redirecting cloud storage or if local path resolution failed
    # WARNING: This loads the entire file into memory. Ensure S3/Cloud providers use signed URLs.
    file_data = await storage.get(storage_path)
    file_size = len(file_data)

    # Handle range requests manually for memory-loaded content
    if range:
        start, end = parse_range_header(range, file_size)
        content_length = end - start + 1
        partial_data = file_data[start : end + 1]

        return Response(
            content=partial_data,
            status_code=206,
            media_type=content_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(content_length),
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=3600",
            },
        )

    # Return full file
    return Response(
        content=file_data,
        media_type=content_type,
        headers={
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
        },
    )


@router.head("/{bucket}/{path:path}")
async def head_file(bucket: str, path: str):
    """Get file metadata without downloading content.

    Useful for checking file existence and size before download.

    Args:
        bucket: Storage bucket name
        path: File path within the bucket

    Returns:
        Empty response with Content-Length and Content-Type headers
    """
    # Validate bucket
    if bucket not in VALID_BUCKETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid bucket. Valid buckets: {', '.join(VALID_BUCKETS)}",
        )

    # Get storage provider
    storage = get_storage(bucket=bucket)

    # Construct full storage path
    storage_path = f"{bucket}/{path}"

    # Check if file exists
    if not await storage.exists(storage_path):
        raise HTTPException(status_code=404, detail="File not found")

    # Get file metadata
    content_type = get_content_type(path)
    local_path = storage.get_local_path(storage_path)

    if local_path and local_path.exists():
        file_size = local_path.stat().st_size
    else:
        # Fallback: load file to check size (expensive!)
        # Ideally storage provider should support get_metadata(path)
        file_data = await storage.get(storage_path)
        file_size = len(file_data)

    return Response(
        content=b"",
        media_type=content_type,
        headers={
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
        },
    )
