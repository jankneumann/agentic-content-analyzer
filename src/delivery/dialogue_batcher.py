"""Logic for batching dialogue turns to reduce TTS API calls.

Batches consecutive same-speaker turns together to minimize the number
of TTS API requests while maintaining natural pacing and dialogue flow.
"""

from dataclasses import dataclass

from src.models.podcast import DialogueTurn, PodcastSection
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DialogueBatch:
    """A batch of consecutive same-speaker dialogue turns.

    Batching reduces TTS API calls by combining multiple turns
    from the same speaker into a single synthesis request.
    """

    speaker: str
    """Speaker identifier ('alex' or 'sam')"""

    turns: list[DialogueTurn]
    """Individual turns in this batch"""

    combined_text: str
    """Plain text with all turns joined by spaces"""

    combined_text_ssml: str
    """Text with SSML <break> tags for pauses (if provider supports SSML)"""

    total_pause_after: float
    """Final pause duration after this batch (seconds)"""


class DialogueBatcher:
    """Batches dialogue turns to minimize TTS API calls.

    Groups consecutive same-speaker turns together and adds appropriate
    pauses between turns using SSML markup (when supported) or separate
    silent MP3 segments.
    """

    def batch_section(
        self,
        section: PodcastSection,
        use_ssml: bool = False,
    ) -> list[DialogueBatch]:
        """Group consecutive same-speaker turns into batches.

        Args:
            section: Podcast section with dialogue turns
            use_ssml: Whether to use SSML markup for pauses

        Returns:
            List of batched turns for this section

        Example:
            Input turns:
                Alex: "Welcome..."       (pause 0.5s)
                Sam: "Thanks..."         (pause 0.5s)
                Alex: "Let's dive in..." (pause 0.8s)
                Alex: "Today we're..."   (pause 1.0s)  <-- consecutive!

            Output batches (3 instead of 4 API calls):
                Alex batch 1: "Welcome... <break time='0.5s'/>"
                Sam batch 1: "Thanks... <break time='0.5s'/>"
                Alex batch 2: "Let's dive in... <break time='0.8s'/> Today we're... <break time='1.0s'/>"
        """
        if not section.dialogue:
            logger.debug(f"Section '{section.title}' has no dialogue turns")
            return []

        batches = []
        current_speaker = section.dialogue[0].speaker
        current_turns = []

        for turn in section.dialogue:
            if turn.speaker == current_speaker:
                # Same speaker - add to current batch
                current_turns.append(turn)
            else:
                # Speaker changed - save current batch and start new one
                batches.append(self._create_batch(current_turns, use_ssml))
                current_speaker = turn.speaker
                current_turns = [turn]

        # Add final batch
        if current_turns:
            batches.append(self._create_batch(current_turns, use_ssml))

        reduction_pct = (
            (len(section.dialogue) - len(batches)) / len(section.dialogue) * 100
        )
        logger.debug(
            f"Batched {len(section.dialogue)} turns into {len(batches)} batches "
            f"for section '{section.title}' ({reduction_pct:.0f}% API call reduction)"
        )

        return batches

    def _create_batch(
        self,
        turns: list[DialogueTurn],
        use_ssml: bool,
    ) -> DialogueBatch:
        """Create a batch from a list of same-speaker turns.

        Args:
            turns: List of consecutive same-speaker turns
            use_ssml: Whether to use SSML markup for pauses

        Returns:
            DialogueBatch with combined text and metadata
        """
        if not turns:
            raise ValueError("Cannot create batch from empty turn list")

        speaker = turns[0].speaker

        # Build combined plain text (all turns joined)
        text_parts = [turn.text for turn in turns]
        combined_text = ' '.join(text_parts)

        # Build combined text with SSML pauses (if supported)
        if use_ssml:
            # Add SSML <break> tags between turns (but not after the last one)
            ssml_parts = []
            for turn in turns[:-1]:  # All but last
                ssml_parts.append(turn.text)
                if turn.pause_after > 0:
                    ssml_parts.append(f'<break time="{turn.pause_after}s"/>')

            # Add last turn without pause (pause handled separately)
            ssml_parts.append(turns[-1].text)
            combined_text_ssml = ''.join(ssml_parts)
        else:
            # No SSML support - just use plain text
            # Pauses will be added as separate silent MP3 segments
            combined_text_ssml = combined_text

        # Only preserve the final turn's pause
        # (pauses between batches/sections are handled by audio generator)
        total_pause = turns[-1].pause_after

        batch = DialogueBatch(
            speaker=speaker,
            turns=turns,
            combined_text=combined_text,
            combined_text_ssml=combined_text_ssml,
            total_pause_after=total_pause,
        )

        logger.debug(
            f"Created batch for {speaker}: {len(turns)} turns, "
            f"{len(combined_text)} chars, pause={total_pause}s"
        )

        return batch
