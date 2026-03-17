"""Podcast creator orchestration for two-phase podcast generation.

Orchestrates the complete podcast creation workflow:
- Phase 1: Script generation (ends at SCRIPT_PENDING_REVIEW)
- Phase 2: Audio generation (requires SCRIPT_APPROVED)

This separation enables human review before expensive TTS synthesis.
"""

import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from src.config import settings
from src.config.models import ModelConfig
from src.delivery.audio_generator import (
    PodcastAudioGenerator,
)
from src.models.podcast import (
    Podcast,
    PodcastRequest,
    PodcastScript,
    PodcastScriptRecord,
    PodcastStatus,
    VoicePersona,
    VoiceProvider,
)
from src.processors.podcast_script_generator import PodcastScriptGenerator
from src.services.file_storage import get_storage
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


class PodcastCreator:
    """Orchestrate podcast creation with review workflow.

    Two-phase workflow:
    1. generate_script() - Creates script, saves to DB, status = PENDING_REVIEW
    2. generate_audio() - Creates audio from approved script, saves to DB

    The review step between phases allows human quality control
    before incurring TTS costs.
    """

    def __init__(
        self,
        model_config: ModelConfig | None = None,
    ):
        """Initialize podcast creator.

        Args:
            model_config: Model configuration for script generation
        """
        self.model_config = model_config or settings.get_model_config()
        self.script_generator = PodcastScriptGenerator(model_config=self.model_config)
        self.audio_generator = None  # Initialized per request with voice config

        logger.info("Initialized PodcastCreator")

    # --- Phase 1: Script Generation ---

    async def generate_script(
        self,
        request: PodcastRequest,
    ) -> PodcastScriptRecord:
        """Generate script and save for review. Does NOT generate audio.

        Phase 1 of podcast creation. Script goes to PENDING_REVIEW status
        and must be approved before audio can be generated.

        Args:
            request: Podcast generation request

        Returns:
            PodcastScriptRecord with script content

        Raises:
            ValueError: If digest not found
            RuntimeError: If script generation fails
        """
        start_time = time.time()
        logger.info(
            f"Phase 1: Generating script for digest {request.digest_id}, "
            f"length={request.length.value}"
        )

        # Create initial record
        with get_db() as db:
            script_record = PodcastScriptRecord(
                digest_id=request.digest_id,
                length=request.length,
                status=PodcastStatus.SCRIPT_GENERATING,
            )
            db.add(script_record)
            db.commit()
            db.refresh(script_record)
            script_id = script_record.id

        try:
            # Generate script
            script, metadata = await self.script_generator.generate_script(request)

            processing_time = int(time.time() - start_time)

            # Update record with generated content
            with get_db() as db:
                script_record = (
                    db.query(PodcastScriptRecord)
                    .filter(PodcastScriptRecord.id == script_id)
                    .first()
                )
                script_record.script_json = script.model_dump()
                script_record.title = script.title
                script_record.word_count = script.word_count
                script_record.estimated_duration_seconds = script.estimated_duration_seconds
                script_record.status = PodcastStatus.SCRIPT_PENDING_REVIEW

                # Store content IDs available (for reference)
                # These are the content items in the digest period
                script_record.newsletter_ids_available = [
                    s.get("id") for s in script.sources_summary
                ]
                # Store which ones were actually fetched via get_content tool
                # Note: DB column still named newsletter_ids_fetched for backwards compat
                script_record.newsletter_ids_fetched = metadata.content_ids_fetched
                script_record.web_search_queries = metadata.web_searches
                script_record.tool_call_count = metadata.tool_call_count

                # Generation metadata
                script_record.model_used = self.script_generator.model
                script_record.model_version = self.script_generator.model_version
                script_record.token_usage = {
                    "input_tokens": self.script_generator.input_tokens,
                    "output_tokens": self.script_generator.output_tokens,
                }
                script_record.processing_time_seconds = processing_time

                db.commit()
                db.refresh(script_record)

            logger.info(
                f"Script {script_id} generated successfully in {processing_time}s. "
                f"Word count: {script.word_count}, "
                f"Tool calls: {metadata.tool_call_count}"
            )

            return script_record

        except Exception as e:
            logger.error(f"Script generation failed: {e}")
            with get_db() as db:
                script_record = (
                    db.query(PodcastScriptRecord)
                    .filter(PodcastScriptRecord.id == script_id)
                    .first()
                )
                script_record.status = PodcastStatus.FAILED
                script_record.error_message = "An internal error occurred during script generation."
                db.commit()
            raise

    # --- Phase 2: Audio Generation ---

    async def generate_audio(
        self,
        script_id: int,
        voice_provider: VoiceProvider = VoiceProvider.OPENAI_TTS,
        alex_voice: VoicePersona = VoicePersona.ALEX_MALE,
        sam_voice: VoicePersona = VoicePersona.SAM_FEMALE,
        progress_callback: Callable[[int, int, str], None] | None = None,
        use_v2_generator: bool = True,  # Default to V2 (batched, ffmpeg-based)
        speed: float = 1.3,  # Default to 1.3x speed
    ) -> Podcast:
        """Generate audio from an approved script.

        Phase 2 of podcast creation. Requires script to be in APPROVED status.

        Multiple audio versions can be generated from the same approved script
        with different voice configurations.

        Args:
            script_id: ID of the approved script
            voice_provider: TTS provider to use
            alex_voice: Voice persona for Alex
            sam_voice: Voice persona for Sam
            progress_callback: Optional callback(current, total, message)
            use_v2_generator: Use V2 generator (batched, ffmpeg-based)
            speed: Speech speed (0.25 to 4.0, default 1.5)

        Returns:
            Podcast record with audio information

        Raises:
            ValueError: If script not found or not approved
            RuntimeError: If audio generation fails
        """
        start_time = time.time()
        logger.info(f"Phase 2: Generating audio for script {script_id} with {voice_provider.value}")

        # Load and validate script
        with get_db() as db:
            script_record = (
                db.query(PodcastScriptRecord).filter(PodcastScriptRecord.id == script_id).first()
            )

            if not script_record:
                raise ValueError(f"Script {script_id} not found")

            if script_record.status != PodcastStatus.SCRIPT_APPROVED.value:
                raise ValueError(
                    f"Script must be approved before audio generation. "
                    f"Current status: {script_record.status}"
                )

            # Update script status
            script_record.status = PodcastStatus.AUDIO_GENERATING.value
            db.commit()

            # Create podcast record
            podcast = Podcast(
                script_id=script_id,
                voice_provider=voice_provider,
                alex_voice=alex_voice,
                sam_voice=sam_voice,
                status="generating",
            )
            db.add(podcast)
            db.commit()
            db.refresh(podcast)
            podcast_id = podcast.id

        try:
            # Parse script
            script = PodcastScript.model_validate(script_record.script_json)

            # Initialize audio generator with voice config
            if use_v2_generator:
                from src.delivery.audio_generator_v2 import PodcastAudioGeneratorV2

                self.audio_generator = PodcastAudioGeneratorV2(
                    provider=voice_provider,
                    alex_voice=alex_voice,
                    sam_voice=sam_voice,
                    speed=speed,
                )
                logger.info(f"Using V2 audio generator (batched, ffmpeg-based, speed={speed}x)")
            else:
                self.audio_generator = PodcastAudioGenerator(
                    provider=voice_provider,
                    alex_voice=alex_voice,
                    sam_voice=sam_voice,
                )
                logger.info("Using V1 audio generator (pydub-based, deprecated)")

            # Generate audio to a temporary file first
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)

            # Generate audio to temp file
            audio_meta = await self.audio_generator.generate_audio(
                script,
                tmp_path,
                progress_callback=progress_callback,
            )

            # Upload to storage provider
            storage = get_storage(bucket="podcasts")
            filename = f"podcast_{podcast_id}.mp3"

            # Read audio data from temp file (using Path.read_bytes for simplicity)
            audio_data = tmp_path.read_bytes()

            storage_path = await storage.save(
                data=audio_data,
                filename=filename,
                content_type="audio/mpeg",
            )

            # Clean up temp file
            tmp_path.unlink(missing_ok=True)

            generation_time = time.time() - start_time

            # Update podcast record
            with get_db() as db:
                podcast = db.query(Podcast).filter(Podcast.id == podcast_id).first()
                podcast.audio_url = storage_path  # Store the storage path, not local path
                podcast.audio_format = audio_meta.format
                podcast.duration_seconds = audio_meta.duration_seconds
                podcast.file_size_bytes = audio_meta.file_size_bytes
                podcast.voice_config = self.audio_generator.get_voice_config()
                podcast.status = "completed"
                podcast.completed_at = datetime.now(UTC)

                # Update script status
                script_record = (
                    db.query(PodcastScriptRecord)
                    .filter(PodcastScriptRecord.id == script_id)
                    .first()
                )
                script_record.status = PodcastStatus.COMPLETED

                db.commit()
                db.refresh(podcast)

            logger.info(
                f"Podcast {podcast_id} generated successfully in {generation_time:.1f}s. "
                f"Duration: {audio_meta.duration_seconds}s, "
                f"Size: {audio_meta.file_size_bytes / 1024:.1f} KB, "
                f"Storage: {storage_path}"
            )

            return podcast

        except Exception as e:
            logger.error(f"Audio generation failed: {e}")
            with get_db() as db:
                podcast = db.query(Podcast).filter(Podcast.id == podcast_id).first()
                podcast.status = "failed"
                podcast.error_message = "An internal error occurred during audio generation."

                # Revert script status to approved (so user can retry)
                script_record = (
                    db.query(PodcastScriptRecord)
                    .filter(PodcastScriptRecord.id == script_id)
                    .first()
                )
                script_record.status = PodcastStatus.SCRIPT_APPROVED

                db.commit()
            raise RuntimeError(f"Audio generation failed: {e}")

    # --- Convenience Methods ---

    async def estimate_costs(
        self,
        request: PodcastRequest,
        voice_provider: VoiceProvider = VoiceProvider.OPENAI_TTS,
    ) -> dict:
        """Estimate costs for script and audio generation.

        Args:
            request: Podcast request
            voice_provider: TTS provider for audio cost estimate

        Returns:
            Dict with cost breakdown
        """
        from src.processors.podcast_script_generator import WORD_COUNT_TARGETS

        word_target = WORD_COUNT_TARGETS[request.length]
        avg_words = (word_target["min"] + word_target["max"]) // 2
        avg_chars = avg_words * 5  # Rough estimate

        # LLM costs (script generation)
        # Estimate based on typical token usage
        estimated_input_tokens = 15000  # Context + prompts
        estimated_output_tokens = avg_words * 2  # Script output

        model = self.script_generator.model
        llm_cost = 0
        try:
            llm_cost = self.model_config.calculate_cost(
                model_id=model,
                input_tokens=estimated_input_tokens,
                output_tokens=estimated_output_tokens,
            )
        except Exception:
            pass

        # TTS costs
        if voice_provider == VoiceProvider.OPENAI_TTS:
            tts_cost = avg_chars * 0.000015  # $15 per 1M chars
        elif voice_provider == VoiceProvider.ELEVENLABS:
            tts_cost = avg_chars * 0.00030  # $0.30 per 1k chars
        else:
            tts_cost = avg_chars * 0.000004  # Google/AWS

        return {
            "length": request.length.value,
            "estimated_words": avg_words,
            "estimated_duration_minutes": word_target["duration_mins"],
            "script_generation": {
                "model": model,
                "estimated_input_tokens": estimated_input_tokens,
                "estimated_output_tokens": estimated_output_tokens,
                "estimated_cost_usd": llm_cost,
            },
            "audio_generation": {
                "provider": voice_provider.value,
                "estimated_characters": avg_chars,
                "estimated_cost_usd": tts_cost,
            },
            "total_estimated_cost_usd": llm_cost + tts_cost,
        }

    def get_script_status(self, script_id: int) -> dict:
        """Get current status of a script.

        Args:
            script_id: Script ID

        Returns:
            Dict with status information
        """
        with get_db() as db:
            script_record = (
                db.query(PodcastScriptRecord).filter(PodcastScriptRecord.id == script_id).first()
            )

            if not script_record:
                return {"error": f"Script {script_id} not found"}

            podcasts = db.query(Podcast).filter(Podcast.script_id == script_id).all()

            return {
                "script_id": script_id,
                "digest_id": script_record.digest_id,
                "title": script_record.title,
                "length": script_record.length,
                "status": script_record.status,
                "word_count": script_record.word_count,
                "revision_count": script_record.revision_count or 0,
                "created_at": script_record.created_at.isoformat()
                if script_record.created_at
                else None,
                "approved_at": script_record.approved_at.isoformat()
                if script_record.approved_at
                else None,
                "podcasts": [
                    {
                        "podcast_id": p.id,
                        "status": p.status,
                        "audio_url": p.audio_url,
                        "duration_seconds": p.duration_seconds,
                        "voice_provider": p.voice_provider.value if p.voice_provider else None,
                    }
                    for p in podcasts
                ],
            }

    def get_podcast_status(self, podcast_id: int) -> dict:
        """Get current status of a podcast.

        Args:
            podcast_id: Podcast ID

        Returns:
            Dict with status information
        """
        with get_db() as db:
            podcast = db.query(Podcast).filter(Podcast.id == podcast_id).first()

            if not podcast:
                return {"error": f"Podcast {podcast_id} not found"}

            return {
                "podcast_id": podcast_id,
                "script_id": podcast.script_id,
                "status": podcast.status,
                "audio_url": podcast.audio_url,
                "audio_format": podcast.audio_format,
                "duration_seconds": podcast.duration_seconds,
                "file_size_bytes": podcast.file_size_bytes,
                "voice_provider": podcast.voice_provider.value if podcast.voice_provider else None,
                "alex_voice": podcast.alex_voice.value if podcast.alex_voice else None,
                "sam_voice": podcast.sam_voice.value if podcast.sam_voice else None,
                "created_at": podcast.created_at.isoformat() if podcast.created_at else None,
                "completed_at": podcast.completed_at.isoformat() if podcast.completed_at else None,
                "error_message": podcast.error_message,
            }
