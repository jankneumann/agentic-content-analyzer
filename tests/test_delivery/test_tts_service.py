"""Tests for TTSService long-form synthesis methods."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.delivery.tts_service import TTSService
from src.models.podcast import VoicePersona, VoiceProvider


class TestTTSServiceProviderNameMapping:
    """Tests for provider name mapping to TextChunker."""

    def test_openai_provider_name(self):
        """Test OpenAI provider maps correctly."""
        service = TTSService(provider=VoiceProvider.OPENAI_TTS)
        assert service._get_provider_name() == "openai"

    def test_elevenlabs_provider_name(self):
        """Test ElevenLabs provider maps correctly."""
        service = TTSService(provider=VoiceProvider.ELEVENLABS)
        assert service._get_provider_name() == "elevenlabs"

    def test_google_provider_name(self):
        """Test Google TTS provider maps correctly."""
        service = TTSService(provider=VoiceProvider.GOOGLE_TTS)
        assert service._get_provider_name() == "google"

    def test_aws_polly_provider_name(self):
        """Test AWS Polly provider maps correctly."""
        service = TTSService(provider=VoiceProvider.AWS_POLLY)
        assert service._get_provider_name() == "aws_polly"


class TestSynthesizeLongSingleChunk:
    """Tests for synthesize_long with text that fits in a single chunk."""

    @pytest.fixture
    def mock_service(self):
        """Create a TTSService with mocked provider."""
        service = TTSService(provider=VoiceProvider.OPENAI_TTS)
        # Mock the underlying provider's synthesize method
        service._provider.synthesize = AsyncMock(return_value=b"mock_audio_data")
        return service

    @pytest.mark.asyncio
    async def test_short_text_single_chunk(self, mock_service):
        """Test short text that fits in one chunk."""
        text = "This is a short piece of text."

        result = await mock_service.synthesize_long(text, speaker="alex")

        # Should call synthesize once with the full text
        mock_service._provider.synthesize.assert_called_once()
        assert result == b"mock_audio_data"

    @pytest.mark.asyncio
    async def test_empty_text_returns_empty_bytes(self, mock_service):
        """Test empty text returns empty bytes."""
        result = await mock_service.synthesize_long("", speaker="alex")

        assert result == b""
        mock_service._provider.synthesize.assert_not_called()

    @pytest.mark.asyncio
    async def test_whitespace_only_returns_empty_bytes(self, mock_service):
        """Test whitespace-only text returns empty bytes."""
        result = await mock_service.synthesize_long("   \n\n  ", speaker="sam")

        assert result == b""
        mock_service._provider.synthesize.assert_not_called()

    @pytest.mark.asyncio
    async def test_progress_callback_single_chunk(self, mock_service):
        """Test progress callback is called for single chunk."""
        text = "Short text."
        callback = MagicMock()

        await mock_service.synthesize_long(
            text,
            speaker="alex",
            progress_callback=callback,
        )

        # Should be called once with (1, 1, message)
        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == 1  # current
        assert args[1] == 1  # total
        assert "chunk" in args[2].lower()  # message


class TestSynthesizeLongMultipleChunks:
    """Tests for synthesize_long with text requiring multiple chunks."""

    @pytest.fixture
    def mock_service(self):
        """Create a TTSService with mocked provider."""
        service = TTSService(provider=VoiceProvider.OPENAI_TTS)
        # Each call returns unique audio data
        call_count = [0]

        async def mock_synthesize(text, voice_id, **kwargs):
            call_count[0] += 1
            return f"audio_chunk_{call_count[0]}".encode()

        service._provider.synthesize = mock_synthesize
        return service

    @pytest.mark.asyncio
    async def test_long_text_multiple_chunks(self, mock_service):
        """Test long text is split into multiple chunks."""
        # Create text longer than OpenAI's 3800 char limit
        text = "This is a sentence. " * 300  # ~6000 chars

        with patch("src.delivery.audio_utils.concatenate_mp3_files") as mock_concat:
            # Make concatenate write mock output
            def write_mock_output(segments, output_path):
                output_path.write_bytes(b"concatenated_audio")

            mock_concat.side_effect = write_mock_output

            result = await mock_service.synthesize_long(text, speaker="alex")

            # Should have called concatenate with multiple segments
            mock_concat.assert_called_once()
            segments = mock_concat.call_args[0][0]
            assert len(segments) >= 2  # At least 2 chunks for 6000 chars

            # Result should be the concatenated output
            assert result == b"concatenated_audio"

    @pytest.mark.asyncio
    async def test_progress_callback_multiple_chunks(self, mock_service):
        """Test progress callback is called for each chunk."""
        # Create text that will be split
        text = "This is a test sentence. " * 200  # ~5000 chars

        callback = MagicMock()

        with patch("src.delivery.audio_utils.concatenate_mp3_files") as mock_concat:

            def write_mock_output(segments, output_path):
                output_path.write_bytes(b"concatenated_audio")

            mock_concat.side_effect = write_mock_output

            await mock_service.synthesize_long(
                text,
                speaker="sam",
                progress_callback=callback,
            )

            # Callback should be called multiple times
            assert callback.call_count >= 2

            # Verify progress tracking is correct
            calls = callback.call_args_list
            total = calls[0][0][1]  # total from first call

            for i, call in enumerate(calls):
                current, call_total, message = call[0]
                assert current == i + 1
                assert call_total == total
                assert f"{current}/{total}" in message

    @pytest.mark.asyncio
    async def test_kwargs_passed_to_synthesize(self, mock_service):
        """Test that kwargs are passed to synthesize method."""
        text = "Short text for single chunk."

        # Track kwargs passed to synthesize
        captured_kwargs = {}

        async def capturing_synthesize(text, voice_id, **kwargs):
            captured_kwargs.update(kwargs)
            return b"audio"

        mock_service._provider.synthesize = capturing_synthesize

        await mock_service.synthesize_long(
            text,
            speaker="alex",
            speed=1.5,
            model="tts-1-hd",
        )

        assert captured_kwargs.get("speed") == 1.5
        assert captured_kwargs.get("model") == "tts-1-hd"


class TestSynthesizeLongStream:
    """Tests for synthesize_long_stream async generator."""

    @pytest.fixture
    def mock_service(self):
        """Create a TTSService with mocked provider."""
        service = TTSService(provider=VoiceProvider.OPENAI_TTS)
        call_count = [0]

        async def mock_synthesize(text, voice_id, **kwargs):
            call_count[0] += 1
            return f"chunk_{call_count[0]}".encode()

        service._provider.synthesize = mock_synthesize
        return service

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self, mock_service):
        """Test streaming yields audio for each text chunk."""
        # Text that will be split into multiple chunks
        text = "This is a sentence. " * 300  # ~6000 chars

        chunks_received = []
        async for audio in mock_service.synthesize_long_stream(text, speaker="alex"):
            chunks_received.append(audio)

        # Should yield multiple chunks
        assert len(chunks_received) >= 2

        # Each chunk should be unique audio data
        assert all(isinstance(chunk, bytes) for chunk in chunks_received)
        assert len(set(chunks_received)) == len(chunks_received)

    @pytest.mark.asyncio
    async def test_stream_empty_text(self, mock_service):
        """Test streaming with empty text yields nothing."""
        chunks_received = []
        async for audio in mock_service.synthesize_long_stream("", speaker="sam"):
            chunks_received.append(audio)

        assert chunks_received == []

    @pytest.mark.asyncio
    async def test_stream_single_chunk(self, mock_service):
        """Test streaming with short text yields single chunk."""
        text = "Short text."

        chunks_received = []
        async for audio in mock_service.synthesize_long_stream(text, speaker="alex"):
            chunks_received.append(audio)

        assert len(chunks_received) == 1
        assert chunks_received[0] == b"chunk_1"

    @pytest.mark.asyncio
    async def test_stream_kwargs_passed(self, mock_service):
        """Test streaming passes kwargs to synthesize."""
        text = "Short text."
        captured_kwargs = {}

        async def capturing_synthesize(text, voice_id, **kwargs):
            captured_kwargs.update(kwargs)
            return b"audio"

        mock_service._provider.synthesize = capturing_synthesize

        async for _ in mock_service.synthesize_long_stream(
            text,
            speaker="sam",
            speed=0.8,
            stability=0.7,
        ):
            pass

        assert captured_kwargs.get("speed") == 0.8
        assert captured_kwargs.get("stability") == 0.7


class TestSynthesizeLongWithDifferentProviders:
    """Tests for provider-specific behavior in long synthesis."""

    @pytest.mark.asyncio
    async def test_elevenlabs_uses_correct_chunk_size(self):
        """Test ElevenLabs uses its specific chunk size."""
        service = TTSService(provider=VoiceProvider.ELEVENLABS)
        service._provider.synthesize = AsyncMock(return_value=b"audio")

        # Text that fits in ElevenLabs limit (4500) but not OpenAI (3800)
        text = "A" * 4000 + " B" * 10

        result = await service.synthesize_long(text, speaker="alex")

        # Should be single chunk for ElevenLabs
        service._provider.synthesize.assert_called_once()

    @pytest.mark.asyncio
    async def test_openai_chunks_at_3800(self):
        """Test OpenAI chunks at 3800 chars."""
        service = TTSService(provider=VoiceProvider.OPENAI_TTS)
        call_count = [0]

        async def mock_synthesize(text, voice_id, **kwargs):
            call_count[0] += 1
            return f"chunk_{call_count[0]}".encode()

        service._provider.synthesize = mock_synthesize

        # Text that's 4000 chars - over OpenAI's 3800 limit
        text = "word " * 800  # ~4000 chars

        with patch("src.delivery.audio_utils.concatenate_mp3_files") as mock_concat:

            def write_mock_output(segments, output_path):
                output_path.write_bytes(b"concatenated")

            mock_concat.side_effect = write_mock_output

            await service.synthesize_long(text, speaker="sam")

            # Should have multiple chunks
            assert call_count[0] >= 2


class TestSynthesizeLongSpeakerMapping:
    """Tests for speaker name to voice persona mapping."""

    @pytest.fixture
    def service(self):
        """Create a TTSService with specific voice personas."""
        service = TTSService(
            provider=VoiceProvider.OPENAI_TTS,
            alex_voice=VoicePersona.ALEX_MALE,
            sam_voice=VoicePersona.SAM_FEMALE,
        )
        service._provider.synthesize = AsyncMock(return_value=b"audio")
        return service

    @pytest.mark.asyncio
    async def test_alex_uses_alex_voice(self, service):
        """Test 'alex' speaker uses Alex voice persona."""
        await service.synthesize_long("Hello.", speaker="alex")

        call_args = service._provider.synthesize.call_args
        voice_id = call_args[0][1]  # Second positional arg is voice_id

        # OpenAI voice for ALEX_MALE is "onyx"
        assert voice_id == "onyx"

    @pytest.mark.asyncio
    async def test_sam_uses_sam_voice(self, service):
        """Test 'sam' speaker uses Sam voice persona."""
        await service.synthesize_long("Hello.", speaker="sam")

        call_args = service._provider.synthesize.call_args
        voice_id = call_args[0][1]

        # OpenAI voice for SAM_FEMALE is "shimmer"
        assert voice_id == "shimmer"

    @pytest.mark.asyncio
    async def test_speaker_case_insensitive(self, service):
        """Test speaker name is case-insensitive."""
        await service.synthesize_long("Hello.", speaker="ALEX")

        call_args = service._provider.synthesize.call_args
        voice_id = call_args[0][1]
        assert voice_id == "onyx"


class TestSynthesizeLongErrorHandling:
    """Tests for error handling in long synthesis."""

    @pytest.mark.asyncio
    async def test_synthesis_error_propagates(self):
        """Test synthesis errors are propagated."""
        service = TTSService(provider=VoiceProvider.OPENAI_TTS)
        service._provider.synthesize = AsyncMock(side_effect=RuntimeError("API error"))

        with pytest.raises(RuntimeError, match="API error"):
            await service.synthesize_long("Hello.", speaker="alex")

    @pytest.mark.asyncio
    async def test_stream_synthesis_error_propagates(self):
        """Test streaming synthesis errors are propagated."""
        service = TTSService(provider=VoiceProvider.OPENAI_TTS)
        service._provider.synthesize = AsyncMock(side_effect=RuntimeError("Stream error"))

        with pytest.raises(RuntimeError, match="Stream error"):
            async for _ in service.synthesize_long_stream("Hello.", speaker="sam"):
                pass

    @pytest.mark.asyncio
    async def test_concatenation_error_propagates(self):
        """Test concatenation errors are propagated."""
        service = TTSService(provider=VoiceProvider.OPENAI_TTS)

        async def mock_synthesize(text, voice_id, **kwargs):
            return b"audio"

        service._provider.synthesize = mock_synthesize

        # Text that requires multiple chunks
        text = "word " * 1000

        with patch("src.delivery.audio_utils.concatenate_mp3_files") as mock_concat:
            mock_concat.side_effect = RuntimeError("ffmpeg failed")

            with pytest.raises(RuntimeError, match="ffmpeg failed"):
                await service.synthesize_long(text, speaker="alex")


class TestSynthesizeLongTempFileCleanup:
    """Tests for temporary file cleanup."""

    @pytest.mark.asyncio
    async def test_temp_file_cleaned_up_on_success(self):
        """Test temp file is cleaned up after successful synthesis."""
        service = TTSService(provider=VoiceProvider.OPENAI_TTS)

        async def mock_synthesize(text, voice_id, **kwargs):
            return b"audio_chunk"

        service._provider.synthesize = mock_synthesize

        # Text requiring multiple chunks
        text = "word " * 1000
        created_paths = []

        with patch("src.delivery.audio_utils.concatenate_mp3_files") as mock_concat:

            def capture_and_write(segments, output_path):
                created_paths.append(output_path)
                output_path.write_bytes(b"concatenated")

            mock_concat.side_effect = capture_and_write

            await service.synthesize_long(text, speaker="alex")

            # Temp file should be deleted
            assert len(created_paths) == 1
            assert not created_paths[0].exists()

    @pytest.mark.asyncio
    async def test_temp_file_cleaned_up_on_error(self):
        """Test temp file is cleaned up even on error."""
        service = TTSService(provider=VoiceProvider.OPENAI_TTS)

        async def mock_synthesize(text, voice_id, **kwargs):
            return b"audio_chunk"

        service._provider.synthesize = mock_synthesize

        text = "word " * 1000
        created_paths = []

        with patch("src.delivery.audio_utils.concatenate_mp3_files") as mock_concat:

            def capture_and_fail(segments, output_path):
                created_paths.append(output_path)
                # Write file then fail
                output_path.write_bytes(b"partial")
                raise RuntimeError("Concat failed")

            mock_concat.side_effect = capture_and_fail

            with pytest.raises(RuntimeError):
                await service.synthesize_long(text, speaker="alex")

            # Temp file should still be deleted
            assert len(created_paths) == 1
            assert not created_paths[0].exists()
