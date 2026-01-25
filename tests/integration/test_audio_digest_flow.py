"""Integration tests for digest → audio generation flow.

Tests the complete flow:
1. Create digest with markdown content
2. Generate audio digest using AudioDigestGenerator
3. Verify text preparation (markdown → speech-ready text)
4. Verify TTS synthesis (mocked)
5. Verify storage upload (mocked)
6. Verify database state updates through all stages
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.audio_digest import AudioDigest, AudioDigestStatus
from src.models.digest import Digest, DigestStatus, DigestType
from src.processors.audio_digest_generator import AudioDigestGenerator


@pytest.fixture
def sample_digest_with_markdown(db_session) -> Digest:
    """Create a sample digest with realistic markdown content."""
    markdown = """# AI Weekly Digest - January 15, 2025

## Executive Overview

This week saw significant advances in large language model capabilities,
with context windows expanding to 1 million tokens and costs decreasing by 40%.

## Key Themes

### 1. Context Window Expansion

Large language models are now capable of processing entire codebases
in a single context. This enables new use cases in:

- Code analysis and refactoring
- Document summarization
- Long-form content generation

### 2. Cost Reduction Trends

API costs continue to fall, making AI more accessible:

| Provider | Previous Cost | New Cost | Reduction |
|----------|---------------|----------|-----------|
| OpenAI   | $15/1M       | $10/1M   | 33%       |
| Anthropic| $12/1M       | $8/1M    | 33%       |

## Strategic Insights

1. **Evaluate new pricing** - Reassess AI workloads given cost reductions
2. **Prototype long-context** - Test million-token context windows for your use case

## Technical Developments

The release of Claude 4 Opus introduces improved reasoning capabilities
with enhanced tool use and better structured output generation.

```python
# Example: New tool use pattern
result = client.messages.create(
    model="claude-opus-4-5",
    tools=[{"name": "calculator", "description": "..."}]
)
```

## Actionable Items

- [ ] Review current AI spend and identify optimization opportunities
- [ ] Schedule team training on new model capabilities
- [ ] Update evaluation benchmarks for new models
"""

    digest = Digest(
        digest_type=DigestType.DAILY,
        period_start=datetime(2025, 1, 15, 0, 0, 0, tzinfo=UTC),
        period_end=datetime(2025, 1, 15, 23, 59, 59, tzinfo=UTC),
        title="AI Weekly Digest - January 15, 2025",
        executive_overview="Major advances in LLM capabilities this week.",
        strategic_insights=[
            {"title": "Cost Reduction", "summary": "API costs decreasing"},
        ],
        technical_developments=[],
        emerging_trends=[],
        actionable_recommendations={},
        sources=[],
        newsletter_count=5,
        markdown_content=markdown,
        status=DigestStatus.APPROVED,
        agent_framework="claude",
        model_used="claude-sonnet-4-5",
    )
    db_session.add(digest)
    db_session.commit()
    db_session.refresh(digest)
    return digest


@pytest.mark.integration
class TestDigestToAudioFlow:
    """Integration tests for complete digest → audio workflow."""

    @pytest.mark.asyncio
    async def test_full_flow_short_digest(
        self,
        db_session,
        sample_digest_with_markdown,
        mock_get_db,
    ):
        """Test complete flow for a short digest (single TTS chunk)."""
        digest = sample_digest_with_markdown

        # Mock external dependencies
        mock_tts_provider = MagicMock()
        mock_tts_provider.supports_ssml.return_value = False
        mock_tts_provider.synthesize = AsyncMock(return_value=b"fake_audio_mp3_data")

        mock_storage = MagicMock()
        mock_storage.save = AsyncMock(return_value="audio-digests/2025/01/15/test.mp3")

        with (
            patch(
                "src.processors.audio_digest_generator.get_db",
                mock_get_db,
            ),
            patch("src.processors.audio_digest_generator.TTSService") as mock_tts_class,
            patch(
                "src.processors.audio_digest_generator.get_storage",
                return_value=mock_storage,
            ),
            patch("src.processors.audio_digest_generator.settings") as mock_settings,
        ):
            # Configure mocks
            mock_settings.audio_digest_default_voice = "nova"
            mock_settings.get_audio_digest_voice_id.return_value = "nova"

            mock_tts_instance = MagicMock()
            mock_tts_instance._provider = mock_tts_provider
            mock_tts_class.return_value = mock_tts_instance

            # Run generation
            generator = AudioDigestGenerator(
                provider="openai",
                voice="nova",
                speed=1.0,
            )

            # Track progress
            progress_updates = []

            def progress_callback(current, total, message):
                progress_updates.append((current, total, message))

            result = await generator.generate(
                digest_id=digest.id,
                progress_callback=progress_callback,
            )

            # Verify result
            assert result is not None
            assert result.status == AudioDigestStatus.COMPLETED
            assert result.voice == "nova"
            assert result.speed == 1.0
            assert result.provider == "openai"
            assert result.audio_url == "audio-digests/2025/01/15/test.mp3"
            assert result.file_size_bytes > 0
            assert result.text_char_count > 0
            assert result.completed_at is not None

            # Verify TTS was called
            mock_tts_provider.synthesize.assert_called_once()
            call_kwargs = mock_tts_provider.synthesize.call_args[1]
            assert call_kwargs["voice_id"] == "nova"
            assert call_kwargs["speed"] == 1.0

            # Verify storage was called
            mock_storage.save.assert_called_once()
            storage_kwargs = mock_storage.save.call_args[1]
            assert storage_kwargs["content_type"] == "audio/mpeg"
            assert "audio_digest_" in storage_kwargs["filename"]

            # Verify progress callbacks
            assert len(progress_updates) >= 4
            assert progress_updates[0][2] == "Preparing text..."
            assert progress_updates[-1] == (100, 100, "Complete!")

    @pytest.mark.asyncio
    async def test_text_preparation_strips_code_blocks(
        self,
        db_session,
        sample_digest_with_markdown,
        mock_get_db,
    ):
        """Test that code blocks are stripped from prepared text."""
        from src.processors.digest_text_preparer import DigestTextPreparer

        digest = sample_digest_with_markdown
        preparer = DigestTextPreparer(use_ssml=False)

        prepared_text = preparer.prepare_digest(digest)

        # Verify code blocks are removed
        assert "```python" not in prepared_text
        assert "client.messages.create" not in prepared_text

        # Verify readable content is preserved
        assert "Executive Overview" in prepared_text or "AI Weekly Digest" in prepared_text
        assert "context windows" in prepared_text.lower() or "key themes" in prepared_text.lower()

    @pytest.mark.asyncio
    async def test_generation_failure_updates_status(
        self,
        db_session,
        sample_digest_with_markdown,
        mock_get_db,
    ):
        """Test that generation failure properly updates AudioDigest status."""
        digest = sample_digest_with_markdown

        # Mock TTS to fail
        mock_tts_provider = MagicMock()
        mock_tts_provider.supports_ssml.return_value = False
        mock_tts_provider.synthesize = AsyncMock(
            side_effect=Exception("TTS API rate limit exceeded")
        )

        with (
            patch(
                "src.processors.audio_digest_generator.get_db",
                mock_get_db,
            ),
            patch("src.processors.audio_digest_generator.TTSService") as mock_tts_class,
            patch("src.processors.audio_digest_generator.settings") as mock_settings,
        ):
            mock_settings.audio_digest_default_voice = "nova"
            mock_settings.get_audio_digest_voice_id.return_value = "nova"

            mock_tts_instance = MagicMock()
            mock_tts_instance._provider = mock_tts_provider
            mock_tts_class.return_value = mock_tts_instance

            generator = AudioDigestGenerator(provider="openai", voice="nova")

            # Expect RuntimeError
            with pytest.raises(RuntimeError, match="Audio digest generation failed"):
                await generator.generate(digest_id=digest.id)

            # Verify AudioDigest was created and marked as FAILED
            audio_digest = (
                db_session.query(AudioDigest).filter(AudioDigest.digest_id == digest.id).first()
            )

            assert audio_digest is not None
            assert audio_digest.status == AudioDigestStatus.FAILED
            assert "rate limit" in audio_digest.error_message.lower()

    @pytest.mark.asyncio
    async def test_generation_with_different_voices(
        self,
        db_session,
        sample_digest_with_markdown,
        mock_get_db,
    ):
        """Test generation with different voice presets."""
        digest = sample_digest_with_markdown

        mock_tts_provider = MagicMock()
        mock_tts_provider.supports_ssml.return_value = False
        mock_tts_provider.synthesize = AsyncMock(return_value=b"audio_data")

        mock_storage = MagicMock()
        mock_storage.save = AsyncMock(return_value="path/to/audio.mp3")

        with (
            patch(
                "src.processors.audio_digest_generator.get_db",
                mock_get_db,
            ),
            patch("src.processors.audio_digest_generator.TTSService") as mock_tts_class,
            patch(
                "src.processors.audio_digest_generator.get_storage",
                return_value=mock_storage,
            ),
            patch("src.processors.audio_digest_generator.settings") as mock_settings,
        ):
            mock_settings.audio_digest_default_voice = "nova"
            mock_settings.get_audio_digest_voice_id.return_value = "onyx"

            mock_tts_instance = MagicMock()
            mock_tts_instance._provider = mock_tts_provider
            mock_tts_class.return_value = mock_tts_instance

            generator = AudioDigestGenerator(
                provider="openai",
                voice="onyx",  # Deep male voice
                speed=1.25,  # Slightly faster
            )

            result = await generator.generate(digest_id=digest.id)

            assert result.voice == "onyx"
            assert result.speed == 1.25

            # Verify TTS was called with correct voice
            call_kwargs = mock_tts_provider.synthesize.call_args[1]
            assert call_kwargs["voice_id"] == "onyx"
            assert call_kwargs["speed"] == 1.25


@pytest.mark.integration
class TestDigestToAudioDatabaseState:
    """Tests for database state through audio generation."""

    @pytest.mark.asyncio
    async def test_audio_digest_record_created_on_start(
        self,
        db_session,
        sample_digest_with_markdown,
        mock_get_db,
    ):
        """Test that AudioDigest record is created immediately on generation start."""
        digest = sample_digest_with_markdown

        # Mock TTS to be slow so we can check intermediate state
        mock_tts_provider = MagicMock()
        mock_tts_provider.supports_ssml.return_value = False

        # Track when record is created vs when TTS is called
        record_id_at_tts_time = []

        async def slow_synthesize(**kwargs):
            # Check database state when TTS is called
            audio_digest = (
                db_session.query(AudioDigest).filter(AudioDigest.digest_id == digest.id).first()
            )
            if audio_digest:
                record_id_at_tts_time.append(audio_digest.id)
            return b"audio_data"

        mock_tts_provider.synthesize = slow_synthesize

        mock_storage = MagicMock()
        mock_storage.save = AsyncMock(return_value="path.mp3")

        with (
            patch(
                "src.processors.audio_digest_generator.get_db",
                mock_get_db,
            ),
            patch("src.processors.audio_digest_generator.TTSService") as mock_tts_class,
            patch(
                "src.processors.audio_digest_generator.get_storage",
                return_value=mock_storage,
            ),
            patch("src.processors.audio_digest_generator.settings") as mock_settings,
        ):
            mock_settings.audio_digest_default_voice = "nova"
            mock_settings.get_audio_digest_voice_id.return_value = "nova"

            mock_tts_instance = MagicMock()
            mock_tts_instance._provider = mock_tts_provider
            mock_tts_class.return_value = mock_tts_instance

            generator = AudioDigestGenerator()
            await generator.generate(digest_id=digest.id)

            # Verify record existed before TTS was called
            assert len(record_id_at_tts_time) > 0

    @pytest.mark.asyncio
    async def test_multiple_audio_digests_per_digest(
        self,
        db_session,
        sample_digest_with_markdown,
        mock_get_db,
    ):
        """Test that multiple audio digests can be created for same digest."""
        digest = sample_digest_with_markdown

        mock_tts_provider = MagicMock()
        mock_tts_provider.supports_ssml.return_value = False
        mock_tts_provider.synthesize = AsyncMock(return_value=b"audio")

        mock_storage = MagicMock()
        mock_storage.save = AsyncMock(return_value="path.mp3")

        with (
            patch(
                "src.processors.audio_digest_generator.get_db",
                mock_get_db,
            ),
            patch("src.processors.audio_digest_generator.TTSService") as mock_tts_class,
            patch(
                "src.processors.audio_digest_generator.get_storage",
                return_value=mock_storage,
            ),
            patch("src.processors.audio_digest_generator.settings") as mock_settings,
        ):
            mock_settings.audio_digest_default_voice = "nova"
            mock_settings.get_audio_digest_voice_id.return_value = "nova"

            mock_tts_instance = MagicMock()
            mock_tts_instance._provider = mock_tts_provider
            mock_tts_class.return_value = mock_tts_instance

            # Generate first audio digest
            generator1 = AudioDigestGenerator(voice="nova")
            result1 = await generator1.generate(digest_id=digest.id)

            # Generate second audio digest with different voice
            mock_settings.get_audio_digest_voice_id.return_value = "onyx"
            generator2 = AudioDigestGenerator(voice="onyx")
            result2 = await generator2.generate(digest_id=digest.id)

            # Verify both exist
            assert result1.id != result2.id
            assert result1.voice == "nova"
            assert result2.voice == "onyx"

            # Query all audio digests for this digest
            audio_digests = (
                db_session.query(AudioDigest).filter(AudioDigest.digest_id == digest.id).all()
            )

            assert len(audio_digests) == 2


@pytest.mark.integration
class TestTextPreparationQuality:
    """Tests for text preparation quality and edge cases."""

    def test_handles_empty_digest(self, db_session):
        """Test handling of digest with minimal content."""
        from src.processors.digest_text_preparer import DigestTextPreparer

        digest = Digest(
            digest_type=DigestType.DAILY,
            period_start=datetime(2025, 1, 15, tzinfo=UTC),
            period_end=datetime(2025, 1, 15, tzinfo=UTC),
            title="Empty Digest",
            executive_overview="",
            strategic_insights=[],
            technical_developments=[],
            emerging_trends=[],
            actionable_recommendations={},
            sources=[],
            newsletter_count=0,
            markdown_content="",
            status=DigestStatus.APPROVED,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        )
        db_session.add(digest)
        db_session.commit()

        preparer = DigestTextPreparer(use_ssml=False)
        prepared = preparer.prepare_digest(digest)

        # Should return something (even if minimal)
        assert isinstance(prepared, str)

    def test_handles_markdown_tables(self, db_session):
        """Test that markdown tables are processed and content preserved.

        Note: Tables are currently preserved as-is in the prepared text.
        TTS providers will read them as-is, which may not be ideal.
        Future enhancement: Convert tables to more readable format.
        """
        from src.processors.digest_text_preparer import DigestTextPreparer

        digest = Digest(
            digest_type=DigestType.DAILY,
            period_start=datetime(2025, 1, 15, tzinfo=UTC),
            period_end=datetime(2025, 1, 15, tzinfo=UTC),
            title="Table Test",
            executive_overview="Test",
            strategic_insights=[],
            technical_developments=[],
            emerging_trends=[],
            actionable_recommendations={},
            sources=[],
            newsletter_count=1,
            markdown_content="""# Pricing

| Model | Price |
|-------|-------|
| GPT-4 | $10   |
| Claude | $8   |
""",
            status=DigestStatus.APPROVED,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        )
        db_session.add(digest)
        db_session.commit()

        preparer = DigestTextPreparer(use_ssml=False)
        prepared = preparer.prepare_digest(digest)

        # Prepared text should have content
        assert len(prepared) > 0
        # Title/heading should be preserved
        assert "Pricing" in prepared
        # Table data should be present (GPT-4 or Claude pricing info)
        assert "GPT-4" in prepared or "Claude" in prepared

    def test_preserves_important_content(self, db_session, sample_digest_with_markdown):
        """Test that important content is preserved in preparation."""
        from src.processors.digest_text_preparer import DigestTextPreparer

        digest = sample_digest_with_markdown
        preparer = DigestTextPreparer(use_ssml=False)
        prepared = preparer.prepare_digest(digest)

        # Key content should be preserved (case-insensitive check)
        prepared_lower = prepared.lower()

        # Title or theme references
        assert "ai" in prepared_lower or "weekly" in prepared_lower

        # Should have substantial content
        assert len(prepared) > 100

    def test_ssml_pauses_added_when_enabled(self, db_session, sample_digest_with_markdown):
        """Test that SSML pauses are added between sections when enabled."""
        from src.processors.digest_text_preparer import DigestTextPreparer

        digest = sample_digest_with_markdown
        preparer = DigestTextPreparer(use_ssml=True)
        prepared = preparer.prepare_digest(digest)

        # Should contain SSML break tags
        assert "<break" in prepared


# =============================================================================
# Live API Tests (require OPENAI_API_KEY, cost money, run with: pytest -m live_api)
# =============================================================================


@pytest.mark.live_api
@pytest.mark.integration
class TestLiveOpenAITTS:
    """Live integration tests that call the real OpenAI TTS API.

    These tests:
    - Require OPENAI_API_KEY environment variable
    - Cost approximately $0.001-$0.005 per run
    - Verify actual API integration works
    - Test real audio file generation and concatenation

    Run with: pytest -m live_api tests/integration/test_audio_digest_flow.py -v
    """

    @pytest.fixture
    def openai_api_key(self):
        """Get OpenAI API key or skip test."""
        import os

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set - skipping live API test")
        return api_key

    @pytest.fixture
    def minimal_digest(self, db_session) -> Digest:
        """Create a minimal digest with very short content for cheap TTS testing."""
        digest = Digest(
            digest_type=DigestType.DAILY,
            period_start=datetime(2025, 1, 15, tzinfo=UTC),
            period_end=datetime(2025, 1, 15, tzinfo=UTC),
            title="Test Digest",
            executive_overview="AI advances continue.",
            strategic_insights=[],
            technical_developments=[],
            emerging_trends=[],
            actionable_recommendations={},
            sources=[],
            newsletter_count=1,
            markdown_content="# AI Update\n\nToday we cover recent advances in AI technology.",
            status=DigestStatus.APPROVED,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        )
        db_session.add(digest)
        db_session.commit()
        db_session.refresh(digest)
        return digest

    @pytest.mark.asyncio
    async def test_live_tts_synthesis_short_text(self, openai_api_key):
        """Test real OpenAI TTS synthesis with a single short sentence.

        This is the minimal live test - synthesizes ~15 words.
        Cost: ~$0.0003 (OpenAI TTS is $15/1M chars, this is ~100 chars)
        """
        from src.delivery.tts_service import TTSService
        from src.models.podcast import VoiceProvider

        tts = TTSService(provider=VoiceProvider.OPENAI_TTS)

        # Very short test text (~100 characters, ~15 words)
        test_text = (
            "Welcome to this test audio digest. This verifies the TTS integration works correctly."
        )

        audio_bytes = await tts.synthesize(
            text=test_text,
            speaker="host",  # Uses default voice mapping
        )

        # Verify we got actual audio data
        assert audio_bytes is not None
        assert len(audio_bytes) > 1000  # MP3 should be at least 1KB
        # Check MP3 magic bytes (ID3 tag or MPEG frame sync)
        assert audio_bytes[:3] == b"ID3" or audio_bytes[:2] == b"\xff\xfb"

    @pytest.mark.asyncio
    async def test_live_tts_synthesis_with_chunking(self, openai_api_key):
        """Test real OpenAI TTS synthesis with text that requires chunking.

        This tests the TextChunker and audio concatenation with real API calls.
        Cost: ~$0.001 (tests with ~500 characters split into 2 chunks)
        """
        from src.delivery.tts_service import TTSService
        from src.models.podcast import VoiceProvider

        tts = TTSService(provider=VoiceProvider.OPENAI_TTS)

        # Text long enough to potentially require chunking verification
        # but short enough to keep costs minimal
        test_text = """
        Welcome to the AI Weekly Digest. This week saw significant developments
        in large language model technology. Context windows expanded dramatically.
        API costs continued their downward trend. New multimodal capabilities emerged.
        Strategic implications for enterprise adoption are substantial.
        Technical teams should evaluate updated benchmarks. Individual developers
        can now access more powerful tools at lower costs. The future of AI
        continues to evolve rapidly with these impressive advancements.
        """

        audio_bytes = await tts.synthesize_long(
            text=test_text,
            speaker="host",
        )

        # Verify we got actual audio data
        assert audio_bytes is not None
        assert len(audio_bytes) > 5000  # Should be several KB for this length
        # Check MP3 magic bytes
        assert audio_bytes[:3] == b"ID3" or audio_bytes[:2] == b"\xff\xfb"

    @pytest.mark.asyncio
    async def test_live_full_digest_to_audio_flow(
        self,
        openai_api_key,
        db_session,
        minimal_digest,
        mock_get_db,
    ):
        """Test the complete digest → audio flow with real OpenAI TTS.

        This is the full end-to-end test with real API calls.
        Cost: ~$0.002-$0.005 depending on digest content length
        """
        import tempfile
        from unittest.mock import MagicMock, patch

        from src.processors.audio_digest_generator import AudioDigestGenerator

        # Use real TTS but mock storage (we don't want to upload to real storage)
        mock_storage = MagicMock()
        saved_audio = {}

        async def capture_save(data, filename, content_type):
            saved_audio["data"] = data
            saved_audio["filename"] = filename
            return f"test-storage/{filename}"

        mock_storage.save = capture_save

        with (
            patch(
                "src.processors.audio_digest_generator.get_db",
                mock_get_db,
            ),
            patch(
                "src.processors.audio_digest_generator.get_storage",
                return_value=mock_storage,
            ),
        ):
            generator = AudioDigestGenerator(
                provider="openai",
                voice="nova",
                speed=1.0,
            )

            # Track progress
            progress_updates = []

            def progress_callback(current, total, message):
                progress_updates.append((current, total, message))
                print(f"  Progress: {current}% - {message}")

            result = await generator.generate(
                digest_id=minimal_digest.id,
                progress_callback=progress_callback,
            )

            # Verify result
            assert result is not None
            assert result.status.value == "completed"
            assert result.audio_url is not None
            assert result.file_size_bytes > 0
            assert result.duration_seconds > 0

            # Verify we captured real audio
            assert "data" in saved_audio
            audio_data = saved_audio["data"]
            assert len(audio_data) > 5000  # Real audio should be several KB

            # Verify it's valid MP3
            assert audio_data[:3] == b"ID3" or audio_data[:2] == b"\xff\xfb"

            # Verify progress was tracked
            assert len(progress_updates) >= 4
            assert progress_updates[-1][2] == "Complete!"

            # Optionally save to temp file for manual verification
            with tempfile.NamedTemporaryFile(
                suffix=".mp3", delete=False, prefix="test_audio_digest_"
            ) as f:
                f.write(audio_data)
                print(f"\n  Audio saved to: {f.name}")
                print(f"  File size: {len(audio_data):,} bytes")
                print(f"  Duration estimate: {result.duration_seconds:.1f}s")
