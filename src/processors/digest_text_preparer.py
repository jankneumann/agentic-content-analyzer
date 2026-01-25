"""Digest text preparer for TTS conversion.

Converts markdown digest content into clean text suitable for TTS narration,
with optional SSML markup for pauses and speech control.
"""

import re
from typing import TYPE_CHECKING

from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.models.digest import Digest

logger = get_logger(__name__)

# Average speaking rate for duration estimation (words per minute)
WORDS_PER_MINUTE = 150


class DigestTextPreparer:
    """Prepares digest content for text-to-speech synthesis.

    Converts markdown content into plain text suitable for TTS engines,
    optionally adding SSML markup for improved speech control.

    Example:
        >>> preparer = DigestTextPreparer(use_ssml=True)
        >>> text = preparer.prepare("# Heading\\n\\nSome **bold** text.")
        >>> print(text)
        <break time="500ms"/> Heading. <break time="300ms"/> Some bold text.
    """

    # Regex patterns for markdown elements
    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
    ITALIC_PATTERN = re.compile(r"(?<!\*)\*([^*]+?)\*(?!\*)")
    LINK_PATTERN = re.compile(r"\[([^\]]+)\]\([^)]+\)")
    CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```")
    INLINE_CODE_PATTERN = re.compile(r"`([^`]+)`")
    BLOCKQUOTE_PATTERN = re.compile(r"^>\s*(.*)$", re.MULTILINE)
    LIST_ITEM_PATTERN = re.compile(r"^[-*]\s+(.+)$", re.MULTILINE)
    NUMBERED_LIST_PATTERN = re.compile(r"^(\d+)\.\s+(.+)$", re.MULTILINE)
    HORIZONTAL_RULE_PATTERN = re.compile(r"^[-*_]{3,}\s*$", re.MULTILINE)
    IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\([^)]+\)")

    # SSML break durations
    BREAK_HEADING_H1 = "500ms"
    BREAK_HEADING_H2 = "400ms"
    BREAK_HEADING_OTHER = "300ms"
    BREAK_PARAGRAPH = "400ms"
    BREAK_LIST_ITEM = "200ms"
    BREAK_SECTION = "600ms"

    def __init__(self, use_ssml: bool = False):
        """Initialize the text preparer.

        Args:
            use_ssml: If True, add SSML markup for pauses between sections.
                     SSML is supported by providers like ElevenLabs and Google
                     Cloud TTS, but not by OpenAI TTS.
        """
        self.use_ssml = use_ssml
        logger.debug(f"DigestTextPreparer initialized: use_ssml={use_ssml}")

    def prepare(self, markdown_content: str) -> str:
        """Convert markdown to TTS-friendly text.

        Processes markdown content to produce clean, readable text suitable
        for text-to-speech synthesis. Handles headings, lists, links, code
        blocks, and other markdown formatting.

        Args:
            markdown_content: Raw markdown content to convert.

        Returns:
            Plain text suitable for TTS, optionally with SSML markup for
            pauses and speech control.
        """
        if not markdown_content or not markdown_content.strip():
            logger.debug("Empty markdown content provided")
            return ""

        text = markdown_content

        # Process in specific order to handle nested elements correctly
        text = self._process_code_blocks(text)
        text = self._process_images(text)
        text = self._process_horizontal_rules(text)
        text = self._process_headings(text)
        text = self._process_blockquotes(text)
        text = self._process_numbered_lists(text)
        text = self._process_unordered_lists(text)
        text = self._process_links(text)
        text = self._process_bold(text)
        text = self._process_italic(text)
        text = self._process_inline_code(text)

        # Clean up whitespace
        text = self._cleanup_whitespace(text)

        logger.debug(f"Prepared {len(markdown_content)} chars -> {len(text)} chars")
        return text

    def prepare_digest(self, digest: "Digest") -> str:
        """Extract and prepare text from a Digest model.

        Extracts the markdown_content field from the digest and prepares it
        for TTS. If markdown_content is not available, falls back to
        constructing text from the structured fields.

        Args:
            digest: Digest SQLAlchemy model instance.

        Returns:
            Prepared text for TTS.
        """
        # Prefer markdown_content if available
        if digest.markdown_content:
            logger.debug(f"Using markdown_content from digest {digest.id}")
            return self.prepare(digest.markdown_content)

        # Fall back to constructing from structured fields
        logger.debug(f"Constructing text from structured fields for digest {digest.id}")
        return self._construct_from_fields(digest)

    def estimate_duration(self, text: str) -> float:
        """Estimate audio duration in seconds.

        Uses an average speaking rate of 150 words per minute, which is
        typical for professional narration.

        Args:
            text: Text to estimate duration for.

        Returns:
            Estimated duration in seconds, rounded to 2 decimal places.
        """
        if not text or not text.strip():
            return 0.0

        # Remove SSML tags for word count if present
        clean_text = re.sub(r"<[^>]+>", "", text)

        # Count words (split on whitespace)
        words = len(clean_text.split())

        # Calculate duration: words / (words_per_minute / 60)
        duration = words / (WORDS_PER_MINUTE / 60)

        return round(duration, 2)

    def _add_break(self, duration: str) -> str:
        """Generate an SSML break tag or plain pause marker.

        Args:
            duration: Break duration (e.g., "500ms", "1s").

        Returns:
            SSML break tag if use_ssml is True, otherwise a period for pause.
        """
        if self.use_ssml:
            return f'<break time="{duration}"/>'
        return ""

    def _process_code_blocks(self, text: str) -> str:
        """Process and remove code blocks.

        Code blocks are replaced with a brief announcement that a code
        example was omitted, since reading code verbatim is not useful
        for audio content.

        Args:
            text: Text containing code blocks.

        Returns:
            Text with code blocks replaced.
        """

        def replace_code_block(match: re.Match) -> str:
            if self.use_ssml:
                return f" {self._add_break(self.BREAK_LIST_ITEM)} Code example omitted. {self._add_break(self.BREAK_LIST_ITEM)}"
            return " Code example omitted. "

        return self.CODE_BLOCK_PATTERN.sub(replace_code_block, text)

    def _process_images(self, text: str) -> str:
        """Process and remove image references.

        Images are either replaced with their alt text or removed entirely.

        Args:
            text: Text containing image references.

        Returns:
            Text with images processed.
        """

        def replace_image(match: re.Match) -> str:
            alt_text = match.group(1).strip()
            if alt_text:
                return f"Image: {alt_text}."
            return ""

        return self.IMAGE_PATTERN.sub(replace_image, text)

    def _process_horizontal_rules(self, text: str) -> str:
        """Process and remove horizontal rules.

        Horizontal rules are replaced with a section break pause.

        Args:
            text: Text containing horizontal rules.

        Returns:
            Text with horizontal rules replaced.
        """
        if self.use_ssml:
            return self.HORIZONTAL_RULE_PATTERN.sub(
                f"\n{self._add_break(self.BREAK_SECTION)}\n", text
            )
        return self.HORIZONTAL_RULE_PATTERN.sub("\n\n", text)

    def _process_headings(self, text: str) -> str:
        """Process markdown headings into natural pauses.

        Headings are converted to plain text with appropriate pauses
        before and after based on heading level.

        Args:
            text: Text containing markdown headings.

        Returns:
            Text with headings processed.
        """

        def replace_heading(match: re.Match) -> str:
            level = len(match.group(1))
            heading_text = match.group(2).strip()

            # Choose break duration based on heading level
            if level == 1:
                break_before = self._add_break(self.BREAK_SECTION)
                break_after = self._add_break(self.BREAK_HEADING_H1)
            elif level == 2:
                break_before = self._add_break(self.BREAK_HEADING_H1)
                break_after = self._add_break(self.BREAK_HEADING_H2)
            else:
                break_before = self._add_break(self.BREAK_HEADING_H2)
                break_after = self._add_break(self.BREAK_HEADING_OTHER)

            # Add period if heading doesn't end with punctuation
            if heading_text and heading_text[-1] not in ".!?:":
                heading_text += "."

            if self.use_ssml:
                return f"\n{break_before} {heading_text} {break_after}\n"
            return f"\n\n{heading_text}\n\n"

        return self.HEADING_PATTERN.sub(replace_heading, text)

    def _process_blockquotes(self, text: str) -> str:
        """Process blockquotes, removing the > markers.

        Args:
            text: Text containing blockquotes.

        Returns:
            Text with blockquotes processed.
        """

        def replace_blockquote(match: re.Match) -> str:
            quote_text = match.group(1).strip()
            return quote_text

        return self.BLOCKQUOTE_PATTERN.sub(replace_blockquote, text)

    def _process_numbered_lists(self, text: str) -> str:
        """Process numbered list items for natural reading.

        Numbers are preserved for natural flow, with slight pauses
        between items.

        Args:
            text: Text containing numbered lists.

        Returns:
            Text with numbered lists processed.
        """

        def replace_numbered_item(match: re.Match) -> str:
            number = match.group(1)
            item_text = match.group(2).strip()
            break_tag = self._add_break(self.BREAK_LIST_ITEM)

            if self.use_ssml:
                return f"{break_tag} {number}. {item_text}"
            return f"{number}. {item_text}"

        return self.NUMBERED_LIST_PATTERN.sub(replace_numbered_item, text)

    def _process_unordered_lists(self, text: str) -> str:
        """Process unordered list items for natural reading.

        Bullet markers are removed, with slight pauses between items.

        Args:
            text: Text containing unordered lists.

        Returns:
            Text with unordered lists processed.
        """

        def replace_list_item(match: re.Match) -> str:
            item_text = match.group(1).strip()
            break_tag = self._add_break(self.BREAK_LIST_ITEM)

            if self.use_ssml:
                return f"{break_tag} {item_text}"
            return item_text

        return self.LIST_ITEM_PATTERN.sub(replace_list_item, text)

    def _process_links(self, text: str) -> str:
        """Process links, keeping text but removing URLs.

        Args:
            text: Text containing markdown links.

        Returns:
            Text with links processed.
        """

        def replace_link(match: re.Match) -> str:
            link_text = match.group(1).strip()
            return link_text

        return self.LINK_PATTERN.sub(replace_link, text)

    def _process_bold(self, text: str) -> str:
        """Remove bold markers but keep text.

        Args:
            text: Text containing bold formatting.

        Returns:
            Text with bold markers removed.
        """
        return self.BOLD_PATTERN.sub(r"\1", text)

    def _process_italic(self, text: str) -> str:
        """Remove italic markers but keep text.

        Args:
            text: Text containing italic formatting.

        Returns:
            Text with italic markers removed.
        """
        return self.ITALIC_PATTERN.sub(r"\1", text)

    def _process_inline_code(self, text: str) -> str:
        """Process inline code, keeping the text content.

        Args:
            text: Text containing inline code.

        Returns:
            Text with inline code markers removed.
        """
        return self.INLINE_CODE_PATTERN.sub(r"\1", text)

    def _cleanup_whitespace(self, text: str) -> str:
        """Clean up excess whitespace.

        Normalizes multiple spaces, blank lines, and leading/trailing
        whitespace while preserving paragraph structure.

        Args:
            text: Text to clean up.

        Returns:
            Cleaned text.
        """
        # Replace multiple spaces with single space
        text = re.sub(r"[ \t]+", " ", text)

        # Replace multiple newlines with double newline (paragraph break)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Clean up spaces around SSML tags
        if self.use_ssml:
            text = re.sub(r"\s*(<break[^>]*/>)\s*", r" \1 ", text)
            text = re.sub(r"(<break[^>]*/>)\s+(<break[^>]*/>)", r"\1\2", text)

        # Strip leading/trailing whitespace from each line
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)

        # Final strip
        text = text.strip()

        return text

    def _construct_from_fields(self, digest: "Digest") -> str:
        """Construct TTS text from structured digest fields.

        Used as a fallback when markdown_content is not available.

        Args:
            digest: Digest model instance.

        Returns:
            Constructed text for TTS.
        """
        parts = []

        # Title
        if digest.title:
            title_text = digest.title
            if not title_text.endswith((".", "!", "?")):
                title_text += "."
            if self.use_ssml:
                parts.append(
                    f"{self._add_break(self.BREAK_SECTION)} {title_text} {self._add_break(self.BREAK_HEADING_H1)}"
                )
            else:
                parts.append(title_text)

        # Executive overview
        if digest.executive_overview:
            if self.use_ssml:
                parts.append(
                    f"{self._add_break(self.BREAK_HEADING_H2)} Executive Overview. {self._add_break(self.BREAK_HEADING_OTHER)}"
                )
            else:
                parts.append("Executive Overview.")
            parts.append(digest.executive_overview)

        # Strategic insights
        if digest.strategic_insights:
            if self.use_ssml:
                parts.append(
                    f"{self._add_break(self.BREAK_SECTION)} Strategic Insights. {self._add_break(self.BREAK_HEADING_H1)}"
                )
            else:
                parts.append("\n\nStrategic Insights.")
            for insight in digest.strategic_insights:
                if isinstance(insight, dict):
                    title = insight.get("title", "")
                    summary = insight.get("summary", "")
                    if title:
                        if self.use_ssml:
                            parts.append(f"{self._add_break(self.BREAK_HEADING_OTHER)} {title}.")
                        else:
                            parts.append(f"{title}.")
                    if summary:
                        parts.append(summary)

        # Technical developments
        if digest.technical_developments:
            if self.use_ssml:
                parts.append(
                    f"{self._add_break(self.BREAK_SECTION)} Technical Developments. {self._add_break(self.BREAK_HEADING_H1)}"
                )
            else:
                parts.append("\n\nTechnical Developments.")
            for dev in digest.technical_developments:
                if isinstance(dev, dict):
                    title = dev.get("title", "")
                    summary = dev.get("summary", "")
                    if title:
                        if self.use_ssml:
                            parts.append(f"{self._add_break(self.BREAK_HEADING_OTHER)} {title}.")
                        else:
                            parts.append(f"{title}.")
                    if summary:
                        parts.append(summary)

        # Emerging trends
        if digest.emerging_trends:
            if self.use_ssml:
                parts.append(
                    f"{self._add_break(self.BREAK_SECTION)} Emerging Trends. {self._add_break(self.BREAK_HEADING_H1)}"
                )
            else:
                parts.append("\n\nEmerging Trends.")
            for trend in digest.emerging_trends:
                if isinstance(trend, dict):
                    title = trend.get("title", "")
                    summary = trend.get("summary", "")
                    if title:
                        if self.use_ssml:
                            parts.append(f"{self._add_break(self.BREAK_HEADING_OTHER)} {title}.")
                        else:
                            parts.append(f"{title}.")
                    if summary:
                        parts.append(summary)

        # Join parts with appropriate spacing
        if self.use_ssml:
            text = " ".join(parts)
        else:
            text = "\n\n".join(parts)

        return self._cleanup_whitespace(text)
