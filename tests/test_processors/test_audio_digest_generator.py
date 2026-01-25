"""Tests for AudioDigestGenerator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.audio_digest import AudioDigestStatus
from src.processors.audio_digest_generator import (
    SINGLE_CHUNK_THRESHOLD,
    AudioDigestGenerator,
)


class TestAudioDigestGeneratorInitialization:
    """Tests for AudioDigestGenerator initialization."""

    @patch("src.processors.audio_digest_generator.TTSService")
    @patch("src.processors.audio_digest_generator.settings")
    def test_default_initialization(self, mock_settings, mock_tts_service):
        """Test default initialization with OpenAI provider."""
        mock_settings.audio_digest_default_voice = "nova"
        mock_provider = MagicMock()
        mock_provider.supports_ssml.return_value = False
        mock_tts_service.return_value._provider = mock_provider

        generator = AudioDigestGenerator()

        assert generator.provider == "openai"
        assert generator.voice == "nova"
        assert generator.speed == 1.0
        assert generator.use_ssml is False

    @patch("src.processors.audio_digest_generator.TTSService")
    @patch("src.processors.audio_digest_generator.settings")
    def test_initialization_with_custom_voice(self, mock_settings, mock_tts_service):
        """Test initialization with custom voice."""
        mock_settings.audio_digest_default_voice = "nova"
        mock_provider = MagicMock()
        mock_provider.supports_ssml.return_value = False
        mock_tts_service.return_value._provider = mock_provider

        generator = AudioDigestGenerator(voice="onyx")

        assert generator.voice == "onyx"

    @patch("src.processors.audio_digest_generator.TTSService")
    @patch("src.processors.audio_digest_generator.settings")
    def test_initialization_with_elevenlabs(self, mock_settings, mock_tts_service):
        """Test initialization with ElevenLabs provider."""
        mock_settings.audio_digest_default_voice = "nova"
        mock_provider = MagicMock()
        mock_provider.supports_ssml.return_value = True
        mock_tts_service.return_value._provider = mock_provider

        generator = AudioDigestGenerator(provider="elevenlabs")

        assert generator.provider == "elevenlabs"
        assert generator.use_ssml is True

    @patch("src.processors.audio_digest_generator.TTSService")
    @patch("src.processors.audio_digest_generator.settings")
    def test_initialization_with_custom_speed(self, mock_settings, mock_tts_service):
        """Test initialization with custom speed."""
        mock_settings.audio_digest_default_voice = "nova"
        mock_provider = MagicMock()
        mock_provider.supports_ssml.return_value = False
        mock_tts_service.return_value._provider = mock_provider

        generator = AudioDigestGenerator(speed=1.5)

        assert generator.speed == 1.5


class TestAudioDigestGeneratorGenerate:
    """Tests for AudioDigestGenerator.generate() method."""

    def _create_mock_session(self, digest, audio_digest):
        """Create a mock database session with proper context manager behavior."""
        mock_session = MagicMock()

        # Track query calls to return different objects
        call_count = [0]

        def query_side_effect(*args):
            mock_query = MagicMock()

            def filter_side_effect(*args, **kwargs):
                mock_filter = MagicMock()

                def first_side_effect():
                    call_count[0] += 1
                    if call_count[0] == 1:
                        return digest
                    return audio_digest

                mock_filter.first = first_side_effect
                return mock_filter

            mock_query.filter = filter_side_effect
            return mock_query

        mock_session.query = query_side_effect
        mock_session.add = MagicMock()
        mock_session.commit = MagicMock()
        mock_session.refresh = MagicMock()

        return mock_session

    @pytest.mark.asyncio
    @patch("src.processors.audio_digest_generator.get_storage")
    @patch("src.processors.audio_digest_generator.get_db")
    @patch("src.processors.audio_digest_generator.TTSService")
    @patch("src.processors.audio_digest_generator.settings")
    async def test_generate_digest_not_found(
        self, mock_settings, mock_tts, mock_get_db, mock_get_storage
    ):
        """Test generate raises ValueError when digest not found."""
        mock_settings.audio_digest_default_voice = "nova"
        mock_provider = MagicMock()
        mock_provider.supports_ssml.return_value = False
        mock_tts.return_value._provider = mock_provider

        # Configure mock session to return None for digest
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        generator = AudioDigestGenerator()
        with pytest.raises(ValueError, match="Digest 999 not found"):
            await generator.generate(digest_id=999)

    @pytest.mark.asyncio
    @patch("src.processors.audio_digest_generator.get_storage")
    @patch("src.processors.audio_digest_generator.get_db")
    @patch("src.processors.audio_digest_generator.TTSService")
    @patch("src.processors.audio_digest_generator.settings")
    async def test_generate_success_short_text(
        self, mock_settings, mock_tts, mock_get_db, mock_get_storage
    ):
        """Test successful generation for short text (single chunk)."""
        mock_settings.audio_digest_default_voice = "nova"
        mock_settings.get_audio_digest_voice_id.return_value = "nova"

        mock_provider = MagicMock()
        mock_provider.supports_ssml.return_value = False
        mock_provider.synthesize = AsyncMock(return_value=b"fake_audio_data")
        mock_tts.return_value._provider = mock_provider

        mock_storage = MagicMock()
        mock_storage.save = AsyncMock(return_value="audio-digests/test.mp3")
        mock_get_storage.return_value = mock_storage

        # Create mock digest
        mock_digest = MagicMock()
        mock_digest.id = 1
        mock_digest.markdown_content = "# Short Digest\n\nThis is short content."

        # Create mock audio digest with id property
        mock_audio_digest = MagicMock()
        mock_audio_digest.id = 100

        mock_session = self._create_mock_session(mock_digest, mock_audio_digest)
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        generator = AudioDigestGenerator()
        result = await generator.generate(digest_id=1)

        # Verify TTS was called
        mock_provider.synthesize.assert_called_once()

        # Verify storage was called
        mock_storage.save.assert_called_once()
        call_kwargs = mock_storage.save.call_args[1]
        assert call_kwargs["content_type"] == "audio/mpeg"

    @pytest.mark.asyncio
    @patch("src.processors.audio_digest_generator.get_storage")
    @patch("src.processors.audio_digest_generator.get_db")
    @patch("src.processors.audio_digest_generator.TTSService")
    @patch("src.processors.audio_digest_generator.settings")
    async def test_generate_with_progress_callback(
        self, mock_settings, mock_tts, mock_get_db, mock_get_storage
    ):
        """Test generate calls progress callback at each stage."""
        mock_settings.audio_digest_default_voice = "nova"
        mock_settings.get_audio_digest_voice_id.return_value = "nova"

        mock_provider = MagicMock()
        mock_provider.supports_ssml.return_value = False
        mock_provider.synthesize = AsyncMock(return_value=b"audio_data")
        mock_tts.return_value._provider = mock_provider

        mock_storage = MagicMock()
        mock_storage.save = AsyncMock(return_value="path.mp3")
        mock_get_storage.return_value = mock_storage

        mock_digest = MagicMock()
        mock_digest.id = 1
        mock_digest.markdown_content = "Short content."

        mock_audio_digest = MagicMock()
        mock_audio_digest.id = 100

        mock_session = self._create_mock_session(mock_digest, mock_audio_digest)
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        # Track progress calls
        progress_calls = []

        def progress_callback(current, total, message):
            progress_calls.append((current, total, message))

        generator = AudioDigestGenerator()
        await generator.generate(digest_id=1, progress_callback=progress_callback)

        # Verify progress callbacks were called
        assert len(progress_calls) >= 4
        assert progress_calls[0][2] == "Preparing text..."
        assert progress_calls[-1] == (100, 100, "Complete!")

    @pytest.mark.asyncio
    @patch("src.processors.audio_digest_generator.get_storage")
    @patch("src.processors.audio_digest_generator.get_db")
    @patch("src.processors.audio_digest_generator.TTSService")
    @patch("src.processors.audio_digest_generator.settings")
    async def test_generate_failure_updates_status(
        self, mock_settings, mock_tts, mock_get_db, mock_get_storage
    ):
        """Test that generation failure updates AudioDigest status to FAILED."""
        mock_settings.audio_digest_default_voice = "nova"
        mock_settings.get_audio_digest_voice_id.return_value = "nova"

        mock_provider = MagicMock()
        mock_provider.supports_ssml.return_value = False
        mock_provider.synthesize = AsyncMock(side_effect=Exception("TTS API error"))
        mock_tts.return_value._provider = mock_provider

        mock_digest = MagicMock()
        mock_digest.id = 1
        mock_digest.markdown_content = "Content."

        mock_audio_digest = MagicMock()
        mock_audio_digest.id = 100

        mock_session = self._create_mock_session(mock_digest, mock_audio_digest)
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        generator = AudioDigestGenerator()
        with pytest.raises(RuntimeError, match="Audio digest generation failed"):
            await generator.generate(digest_id=1)

        # Verify status was set to FAILED
        assert mock_audio_digest.status == AudioDigestStatus.FAILED
        assert "TTS API error" in mock_audio_digest.error_message

    @pytest.mark.asyncio
    @patch("src.processors.audio_digest_generator.get_storage")
    @patch("src.processors.audio_digest_generator.get_db")
    @patch("src.processors.audio_digest_generator.TTSService")
    @patch("src.processors.audio_digest_generator.settings")
    async def test_generate_stores_metadata(
        self, mock_settings, mock_tts, mock_get_db, mock_get_storage
    ):
        """Test that generation stores correct metadata."""
        mock_settings.audio_digest_default_voice = "nova"
        mock_settings.get_audio_digest_voice_id.return_value = "nova"

        mock_provider = MagicMock()
        mock_provider.supports_ssml.return_value = False
        mock_provider.synthesize = AsyncMock(return_value=b"audio_data")
        mock_tts.return_value._provider = mock_provider

        mock_storage = MagicMock()
        mock_storage.save = AsyncMock(return_value="path.mp3")
        mock_get_storage.return_value = mock_storage

        mock_digest = MagicMock()
        mock_digest.id = 1
        mock_digest.markdown_content = "# Test\n\nContent here with some words."

        mock_audio_digest = MagicMock()
        mock_audio_digest.id = 100

        mock_session = self._create_mock_session(mock_digest, mock_audio_digest)
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        generator = AudioDigestGenerator()
        await generator.generate(digest_id=1)

        # Verify metadata was set
        assert mock_audio_digest.status == AudioDigestStatus.COMPLETED
        assert mock_audio_digest.text_char_count > 0
        assert mock_audio_digest.file_size_bytes > 0
        assert mock_audio_digest.chunk_count == 1
        assert mock_audio_digest.completed_at is not None


class TestAudioDigestGeneratorLongText:
    """Tests for long text chunking and concatenation."""

    def _create_mock_session(self, digest, audio_digest):
        """Create a mock database session."""
        mock_session = MagicMock()
        call_count = [0]

        def query_side_effect(*args):
            mock_query = MagicMock()

            def filter_side_effect(*args, **kwargs):
                mock_filter = MagicMock()

                def first_side_effect():
                    call_count[0] += 1
                    if call_count[0] == 1:
                        return digest
                    return audio_digest

                mock_filter.first = first_side_effect
                return mock_filter

            mock_query.filter = filter_side_effect
            return mock_query

        mock_session.query = query_side_effect
        mock_session.add = MagicMock()
        mock_session.commit = MagicMock()
        mock_session.refresh = MagicMock()

        return mock_session

    @pytest.mark.asyncio
    @patch("src.processors.audio_digest_generator.concatenate_mp3_files")
    @patch("src.processors.audio_digest_generator.TextChunker")
    @patch("src.processors.audio_digest_generator.get_storage")
    @patch("src.processors.audio_digest_generator.get_db")
    @patch("src.processors.audio_digest_generator.TTSService")
    @patch("src.processors.audio_digest_generator.settings")
    async def test_long_text_is_chunked(
        self, mock_settings, mock_tts, mock_get_db, mock_get_storage, mock_chunker, mock_concat
    ):
        """Test that long text is properly chunked."""
        mock_settings.audio_digest_default_voice = "nova"
        mock_settings.get_audio_digest_voice_id.return_value = "nova"

        mock_provider = MagicMock()
        mock_provider.supports_ssml.return_value = False
        mock_provider.synthesize = AsyncMock(return_value=b"chunk_audio")
        mock_tts.return_value._provider = mock_provider

        mock_storage = MagicMock()
        mock_storage.save = AsyncMock(return_value="path.mp3")
        mock_get_storage.return_value = mock_storage

        # Create chunks
        mock_chunk1 = MagicMock()
        mock_chunk1.text = "Chunk 1 text"
        mock_chunk2 = MagicMock()
        mock_chunk2.text = "Chunk 2 text"
        mock_chunker.return_value.chunk.return_value = [mock_chunk1, mock_chunk2]

        # Create mock digest with long content
        long_content = "A" * (SINGLE_CHUNK_THRESHOLD + 100)
        mock_digest = MagicMock()
        mock_digest.id = 1
        mock_digest.markdown_content = long_content

        mock_audio_digest = MagicMock()
        mock_audio_digest.id = 100

        mock_session = self._create_mock_session(mock_digest, mock_audio_digest)
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        generator = AudioDigestGenerator()
        await generator.generate(digest_id=1)

        # Verify chunking was used
        mock_chunker.return_value.chunk.assert_called_once()

        # Verify synthesize was called for each chunk
        assert mock_provider.synthesize.call_count == 2

    @pytest.mark.asyncio
    @patch("src.processors.audio_digest_generator.concatenate_mp3_files")
    @patch("src.processors.audio_digest_generator.TextChunker")
    @patch("src.processors.audio_digest_generator.get_storage")
    @patch("src.processors.audio_digest_generator.get_db")
    @patch("src.processors.audio_digest_generator.TTSService")
    @patch("src.processors.audio_digest_generator.settings")
    async def test_chunks_are_concatenated(
        self, mock_settings, mock_tts, mock_get_db, mock_get_storage, mock_chunker, mock_concat
    ):
        """Test that multiple audio chunks are concatenated."""
        mock_settings.audio_digest_default_voice = "nova"
        mock_settings.get_audio_digest_voice_id.return_value = "nova"

        mock_provider = MagicMock()
        mock_provider.supports_ssml.return_value = False
        mock_provider.synthesize = AsyncMock(return_value=b"chunk_audio")
        mock_tts.return_value._provider = mock_provider

        mock_storage = MagicMock()
        mock_storage.save = AsyncMock(return_value="path.mp3")
        mock_get_storage.return_value = mock_storage

        # Create multiple chunks
        chunks = [MagicMock(text=f"Chunk {i}") for i in range(3)]
        mock_chunker.return_value.chunk.return_value = chunks

        long_content = "A" * (SINGLE_CHUNK_THRESHOLD + 100)
        mock_digest = MagicMock()
        mock_digest.id = 1
        mock_digest.markdown_content = long_content

        mock_audio_digest = MagicMock()
        mock_audio_digest.id = 100

        mock_session = self._create_mock_session(mock_digest, mock_audio_digest)
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        generator = AudioDigestGenerator()
        await generator.generate(digest_id=1)

        # Verify concatenation was called with 3 audio segments
        mock_concat.assert_called_once()
        call_args = mock_concat.call_args[0]
        assert len(call_args[0]) == 3

    @pytest.mark.asyncio
    @patch("src.processors.audio_digest_generator.concatenate_mp3_files")
    @patch("src.processors.audio_digest_generator.TextChunker")
    @patch("src.processors.audio_digest_generator.get_storage")
    @patch("src.processors.audio_digest_generator.get_db")
    @patch("src.processors.audio_digest_generator.TTSService")
    @patch("src.processors.audio_digest_generator.settings")
    async def test_chunk_count_stored(
        self, mock_settings, mock_tts, mock_get_db, mock_get_storage, mock_chunker, mock_concat
    ):
        """Test that chunk count is stored in AudioDigest."""
        mock_settings.audio_digest_default_voice = "nova"
        mock_settings.get_audio_digest_voice_id.return_value = "nova"

        mock_provider = MagicMock()
        mock_provider.supports_ssml.return_value = False
        mock_provider.synthesize = AsyncMock(return_value=b"chunk_audio")
        mock_tts.return_value._provider = mock_provider

        mock_storage = MagicMock()
        mock_storage.save = AsyncMock(return_value="path.mp3")
        mock_get_storage.return_value = mock_storage

        # Create 5 chunks
        chunks = [MagicMock(text=f"Chunk {i}") for i in range(5)]
        mock_chunker.return_value.chunk.return_value = chunks

        long_content = "A" * (SINGLE_CHUNK_THRESHOLD + 100)
        mock_digest = MagicMock()
        mock_digest.id = 1
        mock_digest.markdown_content = long_content

        mock_audio_digest = MagicMock()
        mock_audio_digest.id = 100

        mock_session = self._create_mock_session(mock_digest, mock_audio_digest)
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        generator = AudioDigestGenerator()
        await generator.generate(digest_id=1)

        assert mock_audio_digest.chunk_count == 5


class TestAudioDigestGeneratorVoicePresets:
    """Tests for voice preset resolution."""

    def _create_mock_session(self, digest, audio_digest):
        """Create a mock database session."""
        mock_session = MagicMock()
        call_count = [0]

        def query_side_effect(*args):
            mock_query = MagicMock()

            def filter_side_effect(*args, **kwargs):
                mock_filter = MagicMock()

                def first_side_effect():
                    call_count[0] += 1
                    if call_count[0] == 1:
                        return digest
                    return audio_digest

                mock_filter.first = first_side_effect
                return mock_filter

            mock_query.filter = filter_side_effect
            return mock_query

        mock_session.query = query_side_effect
        mock_session.add = MagicMock()
        mock_session.commit = MagicMock()
        mock_session.refresh = MagicMock()

        return mock_session

    @pytest.mark.asyncio
    @patch("src.processors.audio_digest_generator.get_storage")
    @patch("src.processors.audio_digest_generator.get_db")
    @patch("src.processors.audio_digest_generator.TTSService")
    @patch("src.processors.audio_digest_generator.settings")
    async def test_voice_preset_resolved(
        self, mock_settings, mock_tts, mock_get_db, mock_get_storage
    ):
        """Test that voice presets are resolved via settings."""
        mock_settings.audio_digest_default_voice = "nova"
        mock_settings.get_audio_digest_voice_id.return_value = "resolved_voice_id"

        mock_provider = MagicMock()
        mock_provider.supports_ssml.return_value = False
        mock_provider.synthesize = AsyncMock(return_value=b"audio")
        mock_tts.return_value._provider = mock_provider

        mock_storage = MagicMock()
        mock_storage.save = AsyncMock(return_value="path.mp3")
        mock_get_storage.return_value = mock_storage

        mock_digest = MagicMock()
        mock_digest.id = 1
        mock_digest.markdown_content = "Content"

        mock_audio_digest = MagicMock()
        mock_audio_digest.id = 100

        mock_session = self._create_mock_session(mock_digest, mock_audio_digest)
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        generator = AudioDigestGenerator(voice="professional")
        await generator.generate(digest_id=1)

        # Verify get_audio_digest_voice_id was called with the voice preset
        mock_settings.get_audio_digest_voice_id.assert_called_with("professional")

        # Verify synthesize was called with resolved voice ID
        call_kwargs = mock_provider.synthesize.call_args[1]
        assert call_kwargs["voice_id"] == "resolved_voice_id"


class TestAudioDigestGeneratorHelperMethods:
    """Tests for helper methods."""

    @pytest.mark.asyncio
    @patch("src.processors.audio_digest_generator.get_db")
    @patch("src.processors.audio_digest_generator.TTSService")
    @patch("src.processors.audio_digest_generator.settings")
    async def test_get_audio_digest(self, mock_settings, mock_tts, mock_get_db):
        """Test get_audio_digest retrieves record."""
        mock_settings.audio_digest_default_voice = "nova"
        mock_provider = MagicMock()
        mock_provider.supports_ssml.return_value = False
        mock_tts.return_value._provider = mock_provider

        mock_audio_digest = MagicMock()
        mock_audio_digest.id = 100

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_audio_digest
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        generator = AudioDigestGenerator()
        result = await generator.get_audio_digest(100)

        assert result == mock_audio_digest

    @pytest.mark.asyncio
    @patch("src.processors.audio_digest_generator.get_db")
    @patch("src.processors.audio_digest_generator.TTSService")
    @patch("src.processors.audio_digest_generator.settings")
    async def test_get_audio_digest_not_found(self, mock_settings, mock_tts, mock_get_db):
        """Test get_audio_digest returns None when not found."""
        mock_settings.audio_digest_default_voice = "nova"
        mock_provider = MagicMock()
        mock_provider.supports_ssml.return_value = False
        mock_tts.return_value._provider = mock_provider

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        generator = AudioDigestGenerator()
        result = await generator.get_audio_digest(999)

        assert result is None

    @pytest.mark.asyncio
    @patch("src.processors.audio_digest_generator.get_db")
    @patch("src.processors.audio_digest_generator.TTSService")
    @patch("src.processors.audio_digest_generator.settings")
    async def test_list_audio_digests(self, mock_settings, mock_tts, mock_get_db):
        """Test list_audio_digests with filters."""
        mock_settings.audio_digest_default_voice = "nova"
        mock_provider = MagicMock()
        mock_provider.supports_ssml.return_value = False
        mock_tts.return_value._provider = mock_provider

        mock_digests = [MagicMock() for _ in range(3)]

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_digests

        mock_session = MagicMock()
        mock_session.query.return_value = mock_query
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        generator = AudioDigestGenerator()
        result = await generator.list_audio_digests(digest_id=1, status=AudioDigestStatus.COMPLETED)

        assert result == mock_digests
        mock_query.limit.assert_called_with(50)

    @pytest.mark.asyncio
    @patch("src.processors.audio_digest_generator.get_db")
    @patch("src.processors.audio_digest_generator.TTSService")
    @patch("src.processors.audio_digest_generator.settings")
    async def test_list_audio_digests_no_filters(self, mock_settings, mock_tts, mock_get_db):
        """Test list_audio_digests without filters."""
        mock_settings.audio_digest_default_voice = "nova"
        mock_provider = MagicMock()
        mock_provider.supports_ssml.return_value = False
        mock_tts.return_value._provider = mock_provider

        mock_digests = [MagicMock() for _ in range(2)]

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_digests

        mock_session = MagicMock()
        mock_session.query.return_value = mock_query
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        generator = AudioDigestGenerator()
        result = await generator.list_audio_digests(limit=10)

        assert result == mock_digests
        mock_query.limit.assert_called_with(10)


class TestAudioDigestGeneratorStorageBucket:
    """Tests for correct storage bucket usage."""

    def _create_mock_session(self, digest, audio_digest):
        """Create a mock database session."""
        mock_session = MagicMock()
        call_count = [0]

        def query_side_effect(*args):
            mock_query = MagicMock()

            def filter_side_effect(*args, **kwargs):
                mock_filter = MagicMock()

                def first_side_effect():
                    call_count[0] += 1
                    if call_count[0] == 1:
                        return digest
                    return audio_digest

                mock_filter.first = first_side_effect
                return mock_filter

            mock_query.filter = filter_side_effect
            return mock_query

        mock_session.query = query_side_effect
        mock_session.add = MagicMock()
        mock_session.commit = MagicMock()
        mock_session.refresh = MagicMock()

        return mock_session

    @pytest.mark.asyncio
    @patch("src.processors.audio_digest_generator.get_storage")
    @patch("src.processors.audio_digest_generator.get_db")
    @patch("src.processors.audio_digest_generator.TTSService")
    @patch("src.processors.audio_digest_generator.settings")
    async def test_uses_audio_digests_bucket(
        self, mock_settings, mock_tts, mock_get_db, mock_get_storage
    ):
        """Test that audio-digests bucket is used for storage."""
        mock_settings.audio_digest_default_voice = "nova"
        mock_settings.get_audio_digest_voice_id.return_value = "nova"

        mock_provider = MagicMock()
        mock_provider.supports_ssml.return_value = False
        mock_provider.synthesize = AsyncMock(return_value=b"audio")
        mock_tts.return_value._provider = mock_provider

        mock_storage = MagicMock()
        mock_storage.save = AsyncMock(return_value="path.mp3")
        mock_get_storage.return_value = mock_storage

        mock_digest = MagicMock()
        mock_digest.id = 1
        mock_digest.markdown_content = "Content"

        mock_audio_digest = MagicMock()
        mock_audio_digest.id = 100

        mock_session = self._create_mock_session(mock_digest, mock_audio_digest)
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        generator = AudioDigestGenerator()
        await generator.generate(digest_id=1)

        # Verify get_storage was called with audio-digests bucket
        mock_get_storage.assert_called_with(bucket="audio-digests")
