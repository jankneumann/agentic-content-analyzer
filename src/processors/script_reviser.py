"""Script reviser for section-based podcast script revisions.

This module provides functionality to revise specific sections of a
podcast script based on reviewer feedback, leaving other sections unchanged.
"""

import json
import math
from datetime import datetime

from anthropic import Anthropic

from src.config import settings
from src.config.models import ModelConfig, ModelStep, Provider
from src.models.podcast import (
    DialogueTurn,
    PodcastScript,
    PodcastScriptRecord,
    PodcastSection,
    PodcastStatus,
)
from src.services.prompt_service import PromptService
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


class PodcastScriptReviser:
    """Revise specific sections of a podcast script based on feedback.

    Supports section-level granularity for efficient review workflow:
    - Revise a single section while keeping others unchanged
    - Track revision history for transparency
    - Maintain dialogue quality and persona consistency
    """

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        model: str | None = None,
        prompt_service: PromptService | None = None,
    ):
        """Initialize script reviser.

        Args:
            model_config: Model configuration (defaults to settings.get_model_config())
            model: Optional model override (defaults to PODCAST_SCRIPT step model)
            prompt_service: Optional PromptService for configurable prompts
        """
        if model_config is None:
            model_config = settings.get_model_config()

        self.model_config = model_config
        self.model = model or model_config.get_model_for_step(ModelStep.PODCAST_SCRIPT)
        self.prompt_service = prompt_service or PromptService()

        # Track usage
        self.provider_used: Provider | None = None
        self.input_tokens: int = 0
        self.output_tokens: int = 0

        logger.info(f"Initialized PodcastScriptReviser with {self.model}")

    async def revise_section(
        self,
        script_record: PodcastScriptRecord,
        section_index: int,
        feedback: str,
    ) -> PodcastSection:
        """Revise a single section based on feedback, leaving others unchanged.

        Args:
            script_record: The script record containing the full script
            section_index: Index of section to revise (0-based)
            feedback: Reviewer feedback for this section

        Returns:
            Revised PodcastSection

        Raises:
            ValueError: If script_json is missing or section_index is out of range
            RuntimeError: If LLM call fails
        """
        logger.info(
            f"Revising section {section_index} of script {script_record.id} "
            f"based on feedback: {feedback[:100]}..."
        )

        if not script_record.script_json:
            raise ValueError(f"Script {script_record.id} has no script_json content")

        # Parse the current script
        script = PodcastScript.model_validate(script_record.script_json)

        if section_index < 0 or section_index >= len(script.sections):
            raise ValueError(
                f"Section index {section_index} out of range. "
                f"Script has {len(script.sections)} sections."
            )

        section = script.sections[section_index]

        # Build revision prompt
        prompt = self._build_revision_prompt(section, feedback, script)

        # Call LLM for revision
        revised_section = await self._generate_revision(prompt)

        logger.info(
            f"Section {section_index} revised successfully. "
            f"Original: {len(section.dialogue)} turns, "
            f"Revised: {len(revised_section.dialogue)} turns"
        )

        return revised_section

    async def apply_revision(
        self,
        script_id: int,
        section_index: int,
        feedback: str,
    ) -> PodcastScriptRecord:
        """Apply a revision and update the script record in the database.

        Args:
            script_id: ID of the script to revise
            section_index: Index of section to revise (0-based)
            feedback: Reviewer feedback for this section

        Returns:
            Updated PodcastScriptRecord

        Raises:
            ValueError: If script not found or section_index is invalid
        """
        logger.info(f"Applying revision to script {script_id}, section {section_index}")

        with get_db() as db:
            script_record = (
                db.query(PodcastScriptRecord).filter(PodcastScriptRecord.id == script_id).first()
            )

            if not script_record:
                raise ValueError(f"Script {script_id} not found")

            # Get current script
            script = PodcastScript.model_validate(script_record.script_json)
            original_section = script.sections[section_index]

            # Generate revision
            revised_section = await self.revise_section(script_record, section_index, feedback)

            # Update script with revised section
            script.sections[section_index] = revised_section

            # Update intro/outro references if applicable
            if original_section.section_type == "intro":
                script.intro = revised_section
            elif original_section.section_type == "outro":
                script.outro = revised_section

            # Recalculate word count
            total_words = sum(
                sum(len(turn.text.split()) for turn in section.dialogue)
                for section in script.sections
            )
            script.word_count = total_words

            # Recalculate estimated duration
            script.estimated_duration_seconds = int(
                (total_words / settings.podcast_words_per_minute) * 60
            )

            # Track revision history
            revision_entry = {
                "section_index": section_index,
                "section_type": original_section.section_type,
                "section_title": original_section.title,
                "feedback": feedback,
                "timestamp": datetime.utcnow().isoformat(),
                "original_word_count": sum(
                    len(turn.text.split()) for turn in original_section.dialogue
                ),
                "revised_word_count": sum(
                    len(turn.text.split()) for turn in revised_section.dialogue
                ),
            }
            history = script_record.revision_history or []
            history.append(revision_entry)

            # Update record
            script_record.script_json = script.model_dump()
            script_record.word_count = total_words
            script_record.estimated_duration_seconds = script.estimated_duration_seconds
            script_record.revision_history = history
            script_record.revision_count = (script_record.revision_count or 0) + 1
            script_record.status = PodcastStatus.SCRIPT_PENDING_REVIEW

            db.commit()
            db.refresh(script_record)

            logger.info(
                f"Revision applied. Script {script_id} now has "
                f"{script_record.revision_count} revisions"
            )

            # Cast to correct type (db.refresh ensures it's populated)
            return script_record  # type: ignore[no-any-return]

    async def apply_multiple_revisions(
        self,
        script_id: int,
        section_feedback: dict[int, str],
    ) -> PodcastScriptRecord:
        """Apply multiple section revisions in sequence.

        Args:
            script_id: ID of the script to revise
            section_feedback: Dict mapping section indices to feedback

        Returns:
            Updated PodcastScriptRecord with all revisions applied

        Raises:
            ValueError: If section_feedback is empty
        """
        if not section_feedback:
            raise ValueError("section_feedback cannot be empty")

        logger.info(f"Applying {len(section_feedback)} revisions to script {script_id}")

        script_record: PodcastScriptRecord | None = None
        for section_index, feedback in sorted(section_feedback.items()):
            script_record = await self.apply_revision(script_id, int(section_index), feedback)

        # At this point script_record is guaranteed to be set (non-empty dict)
        assert script_record is not None
        return script_record

    def _build_revision_prompt(
        self,
        section: PodcastSection,
        feedback: str,
        full_script: PodcastScript,
    ) -> str:
        """Build the revision prompt for a section.

        Args:
            section: The section to revise
            feedback: Reviewer feedback
            full_script: The full script for context

        Returns:
            Prompt string for LLM
        """
        # Format current dialogue
        dialogue_text = self._format_dialogue(section.dialogue)

        # Get adjacent sections for context
        section_idx = full_script.sections.index(section)
        context_before = ""
        context_after = ""

        if section_idx > 0:
            prev_section = full_script.sections[section_idx - 1]
            if prev_section.dialogue:
                last_turn = prev_section.dialogue[-1]
                context_before = f'\n[Previous section ends with {last_turn.speaker.upper()} saying: "{last_turn.text[:100]}..."]\n'

        if section_idx < len(full_script.sections) - 1:
            next_section = full_script.sections[section_idx + 1]
            if next_section.dialogue:
                first_turn = next_section.dialogue[0]
                context_after = f'\n[Next section starts with {first_turn.speaker.upper()} saying: "{first_turn.text[:100]}..."]\n'

        return f"""
Revise this podcast section based on the reviewer feedback.

## SECTION TO REVISE

**Section Type:** {section.section_type}
**Title:** {section.title}
**Sources Cited:** {section.sources_cited if section.sources_cited else "None"}
{context_before}
**Current Dialogue:**
{dialogue_text}
{context_after}
## REVIEWER FEEDBACK

{feedback}

## INSTRUCTIONS

1. Revise ONLY this section to address the feedback
2. Maintain the same speakers (Alex and Sam)
3. Keep the conversational style and persona voices
4. Preserve any source citations in [id] format
5. Ensure natural flow with adjacent sections
6. Include appropriate emphasis and pause_after values

## OUTPUT FORMAT

Return a JSON object with this exact structure:

```json
{{
  "section_type": "{section.section_type}",
  "title": "Updated or original title",
  "dialogue": [
    {{
      "speaker": "alex",
      "text": "Revised dialogue...",
      "emphasis": "thoughtful",
      "pause_after": 0.5
    }},
    {{
      "speaker": "sam",
      "text": "Response...",
      "emphasis": null,
      "pause_after": 0.5
    }}
  ],
  "sources_cited": [1, 2]
}}
```

Respond with ONLY the JSON object, no additional text.
"""

    def _format_dialogue(self, dialogue: list[DialogueTurn]) -> str:
        """Format dialogue turns as readable text.

        Args:
            dialogue: List of DialogueTurn objects

        Returns:
            Formatted dialogue string
        """
        lines = []
        for turn in dialogue:
            speaker = turn.speaker.upper()
            emphasis = f" [{turn.emphasis}]" if turn.emphasis else ""
            # Use isclose for float comparison to avoid RUF069
            pause = (
                f" (pause: {turn.pause_after}s)" if not math.isclose(turn.pause_after, 0.5) else ""
            )
            lines.append(f"{speaker}{emphasis}: {turn.text}{pause}")

        return "\n\n".join(lines)

    async def _generate_revision(self, prompt: str) -> PodcastSection:
        """Generate a revised section using LLM.

        Args:
            prompt: The revision prompt

        Returns:
            Revised PodcastSection

        Raises:
            RuntimeError: If LLM call fails or response cannot be parsed
        """
        # Get provider and client
        providers = self.model_config.get_providers_for_model(self.model)
        anthropic_providers = [p for p in providers if p.provider == Provider.ANTHROPIC]

        if not anthropic_providers:
            raise RuntimeError(f"No Anthropic providers available for {self.model}")

        provider_config = anthropic_providers[0]
        client = Anthropic(api_key=provider_config.api_key)

        provider_model_id = self.model_config.get_provider_model_id(
            self.model, provider_config.provider
        )

        try:
            response = client.messages.create(
                model=provider_model_id,
                system=self.prompt_service.get_pipeline_prompt("script_revision"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4000,
                temperature=0.6,  # Moderate creativity for revisions
            )

            # Track usage
            self.input_tokens += response.usage.input_tokens
            self.output_tokens += response.usage.output_tokens
            self.provider_used = provider_config.provider

            # Parse response
            raw_content = response.content[0].text.strip()

            # Extract JSON from markdown if present
            if "```json" in raw_content:
                start = raw_content.find("```json") + 7
                end = raw_content.find("```", start)
                raw_content = raw_content[start:end].strip()
            elif "```" in raw_content:
                start = raw_content.find("```") + 3
                end = raw_content.find("```", start)
                raw_content = raw_content[start:end].strip()

            section_json = json.loads(raw_content)

            # Parse dialogue turns
            dialogue = [
                DialogueTurn(
                    speaker=turn.get("speaker", "alex"),
                    text=turn.get("text", ""),
                    emphasis=turn.get("emphasis"),
                    pause_after=turn.get("pause_after", 0.0),
                )
                for turn in section_json.get("dialogue", [])
            ]

            return PodcastSection(
                section_type=section_json.get("section_type", "content"),
                title=section_json.get("title", "Revised Section"),
                dialogue=dialogue,
                sources_cited=section_json.get("sources_cited", []),
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse revision response: {e}")
            logger.debug(f"Raw response: {raw_content[:500]}")
            raise RuntimeError(f"Failed to parse revision response: {e}")

        except Exception as e:
            logger.error(f"LLM revision failed: {e}")
            raise RuntimeError(f"LLM revision failed: {e}")

    async def replace_section_dialogue(
        self,
        script_id: int,
        section_index: int,
        replacement_dialogue: list[DialogueTurn],
        reviewer: str = "manual",
    ) -> PodcastScriptRecord:
        """Directly replace section dialogue without LLM regeneration.

        Useful when reviewer provides exact replacement text.

        Args:
            script_id: ID of the script
            section_index: Index of section to replace
            replacement_dialogue: New dialogue to use
            reviewer: Identifier of who made the change

        Returns:
            Updated PodcastScriptRecord
        """
        logger.info(f"Directly replacing dialogue in script {script_id}, section {section_index}")

        with get_db() as db:
            script_record = (
                db.query(PodcastScriptRecord).filter(PodcastScriptRecord.id == script_id).first()
            )

            if not script_record:
                raise ValueError(f"Script {script_id} not found")

            # Get current script
            script = PodcastScript.model_validate(script_record.script_json)

            if section_index < 0 or section_index >= len(script.sections):
                raise ValueError(
                    f"Section index {section_index} out of range. "
                    f"Script has {len(script.sections)} sections."
                )

            original_section = script.sections[section_index]

            # Create updated section
            updated_section = PodcastSection(
                section_type=original_section.section_type,
                title=original_section.title,
                dialogue=replacement_dialogue,
                sources_cited=original_section.sources_cited,
            )

            # Update script
            script.sections[section_index] = updated_section

            # Update intro/outro references if applicable
            if original_section.section_type == "intro":
                script.intro = updated_section
            elif original_section.section_type == "outro":
                script.outro = updated_section

            # Recalculate word count
            total_words = sum(
                sum(len(turn.text.split()) for turn in section.dialogue)
                for section in script.sections
            )
            script.word_count = total_words
            script.estimated_duration_seconds = int(
                (total_words / settings.podcast_words_per_minute) * 60
            )

            # Track revision history
            revision_entry = {
                "section_index": section_index,
                "section_type": original_section.section_type,
                "section_title": original_section.title,
                "feedback": f"Manual replacement by {reviewer}",
                "timestamp": datetime.utcnow().isoformat(),
                "original_word_count": sum(
                    len(turn.text.split()) for turn in original_section.dialogue
                ),
                "revised_word_count": sum(len(turn.text.split()) for turn in replacement_dialogue),
            }
            history = script_record.revision_history or []
            history.append(revision_entry)

            # Update record
            script_record.script_json = script.model_dump()
            script_record.word_count = total_words
            script_record.estimated_duration_seconds = script.estimated_duration_seconds
            script_record.revision_history = history
            script_record.revision_count = (script_record.revision_count or 0) + 1
            script_record.status = PodcastStatus.SCRIPT_PENDING_REVIEW

            db.commit()
            db.refresh(script_record)

            # Cast to correct type (db.refresh ensures it's populated)
            return script_record  # type: ignore[no-any-return]
