#!/usr/bin/env python3
"""Generate podcast from a digest with full voice and length configuration.

This script demonstrates the complete two-phase podcast generation:
1. Script generation from a digest
2. Audio generation from approved script

Usage:
    # Generate with defaults (OpenAI TTS, male Alex, female Sam, brief length)
    python -m scripts.generate_podcast

    # Specify digest ID
    python -m scripts.generate_podcast --digest-id 5

    # Use ElevenLabs TTS with custom voices
    python -m scripts.generate_podcast --elevenlabs --alex-gender female --sam-gender male

    # Generate extended podcast
    python -m scripts.generate_podcast --type extended

    # Use V1 generator (requires pydub)
    python -m scripts.generate_podcast --v1
"""

import argparse
import asyncio
from pathlib import Path

from src.config import settings
from src.models.podcast import (
    PodcastLength,
    PodcastRequest,
    PodcastStatus,
    VoicePersona,
    VoiceProvider,
)
from src.processors.podcast_creator import PodcastCreator
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


def list_available_scripts():
    """List all available podcast scripts."""
    from src.models.podcast import PodcastScriptRecord

    with get_db() as db:
        scripts = (
            db.query(PodcastScriptRecord).order_by(PodcastScriptRecord.created_at.desc()).all()
        )

        if not scripts:
            print("\n📝 No scripts found in database.\n")
            return

        print("\n" + "=" * 100)
        print("AVAILABLE PODCAST SCRIPTS")
        print("=" * 100)
        print(f"\n{'ID':<6} {'Title':<50} {'Words':<8} {'Duration':<10} {'Status':<20}")
        print("-" * 100)

        for script in scripts:
            duration = (
                f"{script.estimated_duration_seconds // 60}m {script.estimated_duration_seconds % 60}s"
                if script.estimated_duration_seconds
                else "N/A"
            )
            status = script.status.value if script.status else "unknown"
            title = script.title[:47] + "..." if len(script.title) > 50 else script.title

            print(
                f"{script.id:<6} {title:<50} {script.word_count or 0:<8} {duration:<10} {status:<20}"
            )

        print("\n" + "=" * 100)
        print(f"Total: {len(scripts)} scripts")
        print("\nTo use a script: python -m scripts.generate_podcast --script-id <ID>\n")


async def interactive_script_review(review_service, script_id: int, script) -> bool:
    """Interactive CLI review workflow for podcast scripts.

    Shows each section and allows user to approve, revise, or reject.

    Args:
        review_service: ScriptReviewService instance
        script_id: Script ID to review
        script: PodcastScript object

    Returns:
        True if approved, False if rejected or aborted
    """
    from src.models.podcast import ScriptReviewAction, ScriptReviewRequest, ScriptRevisionRequest

    print("\n" + "=" * 80)
    print("SCRIPT REVIEW")
    print("=" * 80)
    print(f"\nScript ID: {script_id}")
    print(f"Title: {script.title}")
    print(f"Word Count: {script.word_count}")
    print(f"Duration: ~{script.estimated_duration_seconds // 60} minutes")
    print("\n" + "=" * 80)

    # Show each section
    for i, section in enumerate(script.sections):
        print(f"\n{'─' * 80}")
        print(f"SECTION {i + 1}: {section.title}")
        print(f"Type: {section.section_type}")
        print(f"{'─' * 80}\n")

        for turn in section.dialogue:
            speaker = turn.speaker.upper()
            emphasis = f" [{turn.emphasis}]" if turn.emphasis else ""
            print(f"{speaker}{emphasis}: {turn.text}\n")

    print("=" * 80)

    # Review prompt
    while True:
        print("\nReview Options:")
        print("  [a] Approve script and proceed to audio generation")
        print("  [r] Request revision for a specific section")
        print("  [x] Reject script and exit")
        print("  [v] View script again")

        choice = input("\nYour choice (a/r/x/v): ").strip().lower()

        if choice == "a":
            # Approve script
            request = ScriptReviewRequest(
                script_id=script_id,
                action=ScriptReviewAction.APPROVE,
                reviewer="cli-user",
                general_notes="Approved via CLI",
            )
            await review_service.submit_review(request)
            print("\n✅ Script approved!")
            return True

        elif choice == "r":
            # Request revision for a section
            print(f"\nSections available: 1-{len(script.sections)}")
            try:
                section_num = int(input("Enter section number to revise: ").strip())
                section_index = section_num - 1

                if section_index < 0 or section_index >= len(script.sections):
                    print(f"❌ Invalid section number. Must be 1-{len(script.sections)}")
                    continue

                print(f"\nRevising Section {section_num}: {script.sections[section_index].title}")
                print("\nProvide your feedback for this section:")
                feedback = input("> ").strip()

                if not feedback:
                    print("❌ Feedback cannot be empty")
                    continue

                # Apply revision
                print("\n⏳ Applying revision (this may take 10-20 seconds)...")
                revision_request = ScriptRevisionRequest(
                    script_id=script_id,
                    section_index=section_index,
                    feedback=feedback,
                )
                updated_script = await review_service.revise_section(revision_request)

                # Reload script to show updated version
                from src.models.podcast import PodcastScript

                script = PodcastScript.model_validate(updated_script.script_json)

                print("✅ Section revised! Showing updated section:\n")
                print(f"{'─' * 80}")
                print(f"SECTION {section_num}: {script.sections[section_index].title}")
                print(f"{'─' * 80}\n")

                for turn in script.sections[section_index].dialogue:
                    speaker = turn.speaker.upper()
                    emphasis = f" [{turn.emphasis}]" if turn.emphasis else ""
                    print(f"{speaker}{emphasis}: {turn.text}\n")

                print("Continue reviewing...\n")

            except ValueError:
                print("❌ Invalid section number")
                continue
            except Exception as e:
                print(f"❌ Revision failed: {e}")
                continue

        elif choice == "x":
            # Reject script
            confirm = (
                input("\n⚠️  Are you sure you want to reject this script? (yes/no): ")
                .strip()
                .lower()
            )
            if confirm == "yes":
                request = ScriptReviewRequest(
                    script_id=script_id,
                    action=ScriptReviewAction.REJECT,
                    reviewer="cli-user",
                    general_notes="Rejected via CLI",
                )
                await review_service.submit_review(request)
                print("\n❌ Script rejected")
                return False
            else:
                print("Rejection cancelled. Continue reviewing...")

        elif choice == "v":
            # View script again
            print("\n" + "=" * 80)
            print("SCRIPT REVIEW")
            print("=" * 80)

            for i, section in enumerate(script.sections):
                print(f"\n{'─' * 80}")
                print(f"SECTION {i + 1}: {section.title}")
                print(f"{'─' * 80}\n")

                for turn in section.dialogue:
                    speaker = turn.speaker.upper()
                    emphasis = f" [{turn.emphasis}]" if turn.emphasis else ""
                    print(f"{speaker}{emphasis}: {turn.text}\n")

            print("=" * 80)

        else:
            print("❌ Invalid choice. Please enter a, r, x, or v")


def get_voice_persona(speaker: str, gender: str) -> VoicePersona:
    """Get VoicePersona enum from speaker name and gender.

    Args:
        speaker: "alex" or "sam"
        gender: "male" or "female"

    Returns:
        VoicePersona enum value
    """
    if speaker.lower() == "alex":
        return VoicePersona.ALEX_MALE if gender.lower() == "male" else VoicePersona.ALEX_FEMALE
    else:  # sam
        return VoicePersona.SAM_MALE if gender.lower() == "male" else VoicePersona.SAM_FEMALE


async def generate_podcast(
    digest_id: int | None = None,
    script_id: int | None = None,
    podcast_type: PodcastLength = PodcastLength.BRIEF,
    use_elevenlabs: bool = False,
    alex_gender: str = "male",
    sam_gender: str = "female",
    use_v1: bool = False,
    auto_approve: bool = False,
    speed: float = 1.3,
):
    """Generate a podcast from a digest or existing script.

    Args:
        digest_id: ID of digest to convert. If None, uses most recent.
        script_id: ID of existing script to use (skips script generation)
        podcast_type: Length of podcast (BRIEF, STANDARD, EXTENDED)
        use_elevenlabs: If True, use ElevenLabs TTS. Otherwise use OpenAI TTS.
        alex_gender: "male" or "female" for Alex voice
        sam_gender: "male" or "female" for Sam voice
        use_v1: If True, use V1 generator (pydub-based). Otherwise use V2 (ffmpeg-based).
        auto_approve: If True, skip interactive review and auto-approve script.
        speed: Speech speed (0.25 to 4.0, default 1.3)
    """

    # Determine voice provider
    if use_elevenlabs:
        voice_provider = VoiceProvider.ELEVENLABS
        if not settings.elevenlabs_api_key:
            print("\n❌ ERROR: ELEVENLABS_API_KEY not configured in .env")
            print("Please add your ElevenLabs API key to continue.")
            return
    else:
        voice_provider = VoiceProvider.OPENAI_TTS
        if not settings.openai_api_key:
            print("\n❌ ERROR: OPENAI_API_KEY not configured in .env")
            print("Please add your OpenAI API key to continue.")
            return

    # Get voice personas
    alex_voice = get_voice_persona("alex", alex_gender)
    sam_voice = get_voice_persona("sam", sam_gender)

    print("\n🎙️  Podcast Generation")
    print("=" * 60)
    print(f"Voice Provider: {voice_provider.value}")
    print(f"Generator Version: {'V1 (pydub)' if use_v1 else 'V2 (ffmpeg, batched)'}")
    print(f"Podcast Type: {podcast_type.value}")
    print(f"Speech Speed: {speed}x")
    print(f"Alex Voice: {alex_voice.value}")
    print(f"Sam Voice: {sam_voice.value}")
    print("=" * 60)

    from src.models.podcast import PodcastScript, PodcastScriptRecord

    # Check if using existing script
    if script_id:
        # Load existing script
        print(f"\n📄 Loading existing script {script_id}...")
        with get_db() as db:
            script_record = (
                db.query(PodcastScriptRecord).filter(PodcastScriptRecord.id == script_id).first()
            )

            if not script_record:
                print(f"❌ Script ID {script_id} not found.")
                return

            print(f"✅ Loaded script: {script_record.title}")
            print(f"   Word count: {script_record.word_count}")
            print(
                f"   Estimated duration: {script_record.estimated_duration_seconds}s ({script_record.estimated_duration_seconds // 60}m {script_record.estimated_duration_seconds % 60}s)"
            )
            print(f"   Status: {script_record.status.value}")

            script = PodcastScript.model_validate(script_record.script_json)

        # Ensure script is approved
        if script_record.status != PodcastStatus.SCRIPT_APPROVED:
            print("\n📋 Script not yet approved. Auto-approving...")
            with get_db() as db:
                script_rec = (
                    db.query(PodcastScriptRecord)
                    .filter(PodcastScriptRecord.id == script_id)
                    .first()
                )
                script_rec.status = PodcastStatus.SCRIPT_APPROVED
                db.commit()
            print("   Script approved!")

    else:
        # Generate new script from digest
        # Step 1: Find digest to convert
        print("\n📊 Step 1: Finding digest to convert...")
        from src.models.digest import Digest

        with get_db() as db:
            if digest_id:
                digest = db.query(Digest).filter(Digest.id == digest_id).first()
                if not digest:
                    print(f"❌ Digest ID {digest_id} not found.")
                    return
            else:
                digest = db.query(Digest).order_by(Digest.created_at.desc()).first()
                if not digest:
                    print("❌ No digests found. Please create a digest first:")
                    print("   python -m scripts.generate_daily_digest")
                    return

            print(f"✅ Found digest: {digest.title}")
            print(f"   Digest ID: {digest.id}")
            print(f"   Created: {digest.created_at}")
            digest_id = digest.id

        # Step 2: Generate script
        print("\n📝 Step 2: Generating podcast script...")
        print(f"   This may take 30-60 seconds for {podcast_type.value} podcast...")

        request = PodcastRequest(
            digest_id=digest_id,
            length=podcast_type,
            enable_web_search=True,
        )

        try:
            creator = PodcastCreator()
            script_record = await creator.generate_script(request)
            print("✅ Script generated successfully!")
            print(f"   Script ID: {script_record.id}")
            print(f"   Title: {script_record.title}")
            print(f"   Word count: {script_record.word_count}")
            print(
                f"   Estimated duration: {script_record.estimated_duration_seconds}s ({script_record.estimated_duration_seconds // 60}m {script_record.estimated_duration_seconds % 60}s)"
            )
            print(f"   Status: {script_record.status.value}")

            # Show script preview
            script = PodcastScript.model_validate(script_record.script_json)
            print("\n   Script structure:")
            print(f"   └─ Intro: {script.intro.title}")
            for i, section in enumerate(script.sections, 1):
                print(f"   └─ Section {i}: {section.title}")
            print(f"   └─ Outro: {script.outro.title}")

        except Exception as e:
            print(f"❌ Script generation failed: {e}")
            import traceback

            traceback.print_exc()
            return

    # Step 3: Review and approve script (skip if using existing script)
    if not script_id:
        print("\n📋 Step 3: Script review...")

        if auto_approve:
            print("   Auto-approving script (--auto-approve flag set)...")
            with get_db() as db:
                script_rec = (
                    db.query(PodcastScriptRecord)
                    .filter(PodcastScriptRecord.id == script_record.id)
                    .first()
                )
                script_rec.status = PodcastStatus.SCRIPT_APPROVED
                db.commit()
            print("   Script approved!")
        else:
            # Interactive review
            from src.services.script_review_service import ScriptReviewService

            review_service = ScriptReviewService()
            approved = await interactive_script_review(review_service, script_record.id, script)

            if not approved:
                print("\n❌ Script not approved. Exiting.")
                return

    # Step 4: Generate audio
    print(f"\n🎵 Step 4: Generating audio with {voice_provider.value}...")
    print(f"   Alex voice: {alex_voice.value}")
    print(f"   Sam voice: {sam_voice.value}")
    print(f"   This may take 1-3 minutes for {podcast_type.value} podcast...")

    def progress_callback(current: int, total: int, message: str):
        """Show progress during audio generation."""
        print(f"   [{current}/{total}] {message}")

    try:
        creator = PodcastCreator()
        podcast = await creator.generate_audio(
            script_id=script_record.id,
            voice_provider=voice_provider,
            alex_voice=alex_voice,
            sam_voice=sam_voice,
            progress_callback=progress_callback,
            use_v2_generator=not use_v1,  # Default to V2 unless --v1 flag
            speed=speed,
        )

        print("\n✅ Podcast generated successfully!")
        print(f"   Podcast ID: {podcast.id}")
        print(f"   Audio file: {podcast.audio_url}")
        print(
            f"   Duration: {podcast.duration_seconds}s ({podcast.duration_seconds // 60}m {podcast.duration_seconds % 60}s)"
        )
        print(f"   File size: {podcast.file_size_bytes / 1024:.1f} KB")
        print(f"   Format: {podcast.audio_format}")

        # Check if file exists
        audio_path = Path(podcast.audio_url)
        if audio_path.exists():
            print("\n🎧 You can listen to the podcast at:")
            print(f"   {audio_path.absolute()}")
        else:
            print("\n⚠️  Warning: Audio file not found at expected path")

    except Exception as e:
        print(f"❌ Audio generation failed: {e}")
        import traceback

        traceback.print_exc()
        return

    # Summary
    print(f"\n{'=' * 60}")
    print("✅ PODCAST GENERATED!")
    print(f"{'=' * 60}")
    print("\nGenerated content:")
    print(f"  Script: ID {script_record.id} in database")
    print(f"  Audio: {podcast.audio_url}")
    print("\nVoice configuration:")
    print(f"  Provider: {voice_provider.value}")
    print(f"  Alex: {alex_voice.value}")
    print(f"  Sam: {sam_voice.value}")
    print(f"  Type: {podcast_type.value}")
    print("\nNext steps:")
    print("  1. Listen to the podcast to verify quality")
    print("  2. Try different voice configurations:")
    print("     python -m scripts.generate_podcast --alex-gender female --sam-gender male")
    print("  3. Test with longer podcast lengths:")
    print("     python -m scripts.generate_podcast --type standard")
    if not use_elevenlabs:
        print("  4. Test with ElevenLabs:")
        print("     python -m scripts.generate_podcast --elevenlabs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate podcast from digest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all available scripts
  python -m scripts.generate_podcast --list-scripts

  # Generate with interactive review (default)
  python -m scripts.generate_podcast

  # Auto-approve script without review
  python -m scripts.generate_podcast --auto-approve

  # Use specific digest
  python -m scripts.generate_podcast --digest-id 5

  # Reuse existing script with different audio settings
  python -m scripts.generate_podcast --script-id 6 --speed 2.0 --elevenlabs

  # Try different voices on same script
  python -m scripts.generate_podcast --script-id 6 --alex-gender female --sam-gender male

  # Use ElevenLabs with female Alex and male Sam
  python -m scripts.generate_podcast --elevenlabs --alex-gender female --sam-gender male

  # Generate extended podcast with auto-approval
  python -m scripts.generate_podcast --type extended --auto-approve

  # Full custom configuration
  python -m scripts.generate_podcast --digest-id 3 --type standard --alex-gender female --sam-gender male --elevenlabs
        """,
    )

    parser.add_argument(
        "--digest-id",
        type=int,
        help="ID of digest to convert. If not specified, uses most recent digest.",
    )

    parser.add_argument(
        "--script-id",
        type=int,
        help="ID of existing script to use (skips script generation and goes straight to audio).",
    )

    parser.add_argument(
        "--type",
        choices=["brief", "standard", "extended"],
        default="brief",
        help="Podcast length: brief (~5min), standard (~15min), extended (~30min). Default: brief",
    )

    parser.add_argument(
        "--elevenlabs",
        action="store_true",
        help="Use ElevenLabs TTS instead of OpenAI TTS (premium quality)",
    )

    parser.add_argument(
        "--alex-gender",
        choices=["male", "female"],
        default="male",
        help="Gender for Alex voice (VP Engineering). Default: male",
    )

    parser.add_argument(
        "--sam-gender",
        choices=["male", "female"],
        default="female",
        help="Gender for Sam voice (Distinguished Engineer). Default: female",
    )

    parser.add_argument(
        "--v1",
        action="store_true",
        help="Use V1 generator (pydub-based, deprecated). Default is V2 (ffmpeg-based, batched)",
    )

    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Automatically approve script without review. Default is interactive review.",
    )

    parser.add_argument(
        "--speed",
        type=float,
        default=1.3,
        help="Speech speed (0.25 to 4.0). Default: 1.3 (faster than normal)",
    )

    parser.add_argument(
        "--list-scripts",
        action="store_true",
        help="List all available scripts and exit",
    )

    args = parser.parse_args()

    # Handle --list-scripts
    if args.list_scripts:
        list_available_scripts()
        exit(0)

    # Convert podcast type string to enum
    podcast_type_map = {
        "brief": PodcastLength.BRIEF,
        "standard": PodcastLength.STANDARD,
        "extended": PodcastLength.EXTENDED,
    }
    podcast_type = podcast_type_map[args.type]

    asyncio.run(
        generate_podcast(
            digest_id=args.digest_id,
            script_id=args.script_id,
            podcast_type=podcast_type,
            use_elevenlabs=args.elevenlabs,
            alex_gender=args.alex_gender,
            sam_gender=args.sam_gender,
            use_v1=args.v1,
            auto_approve=args.auto_approve,
            speed=args.speed,
        )
    )
