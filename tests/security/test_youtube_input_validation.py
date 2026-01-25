
import pytest

from src.parsers.youtube_parser import YouTubeParser
from src.utils.youtube_links import extract_video_id


def test_extract_video_id_valid():
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

@pytest.mark.asyncio
async def test_parser_accepts_valid_id():
    parser = YouTubeParser()
    # Mock fetch to return None (simulating no transcript) but validation passes
    parser._fetch_transcript = lambda x: None

    valid_id = "dQw4w9WgXcQ"

    try:
        await parser.parse(valid_id)
    except ValueError as e:
        # It should fail because no transcript found, but NOT validation error
        assert "Invalid YouTube video ID" not in str(e)
        assert "Transcript not available" in str(e) or "No transcript available" in str(e)

@pytest.mark.asyncio
async def test_parser_rejects_invalid_chars():
    parser = YouTubeParser()
    # Mock fetch to return None so we only check validation
    parser._fetch_transcript = lambda x: None

    # Length 11 but invalid chars
    invalid_id = "abcde@#$%^&"

    try:
        await parser.parse(invalid_id)
        pytest.fail("Should have raised ValueError")
    except ValueError as e:
        assert "Invalid YouTube video ID" in str(e)
