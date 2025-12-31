"""Podcast script generator for converting digests to audio content.

This module generates conversational podcast scripts from digest content using
an agentic approach with tool-based content retrieval. The model can fetch
full newsletter content on-demand and perform web searches as needed.

Two personas drive the conversation:
- Alex Chen: VP of Engineering (strategic perspective)
- Dr. Sam Rodriguez: Distinguished Engineer (technical deep-dives)
"""

import json
import time
from datetime import datetime
from typing import Optional

from anthropic import Anthropic

from src.config import settings
from src.config.models import ModelConfig, ModelStep, Provider
from src.models.digest import Digest
from src.models.newsletter import Newsletter
from src.models.podcast import (
    DialogueTurn,
    PodcastGenerationMetadata,
    PodcastLength,
    PodcastRequest,
    PodcastScript,
    PodcastSection,
    PodcastStatus,
)
from src.models.summary import NewsletterSummary
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


# Word count targets per podcast length
WORD_COUNT_TARGETS = {
    PodcastLength.BRIEF: {"min": 750, "max": 1000, "duration_mins": 5},
    PodcastLength.STANDARD: {"min": 2250, "max": 3000, "duration_mins": 15},
    PodcastLength.EXTENDED: {"min": 4500, "max": 6000, "duration_mins": 30},
}


PODCAST_SCRIPT_SYSTEM_PROMPT = """
You are a podcast script writer creating an engaging dialogue between two technology experts
discussing AI, Data, and Software development news relevant to a large media/tech company.

PERSONAS:

**Alex Chen** (VP of Engineering):
- 20+ years in technology leadership at Fortune 500 companies
- Focuses on: strategic implications, organizational impact, competitive dynamics
- Speaking style: Confident, strategic, occasionally uses business metaphors
- Often asks: "What does this mean for our technology roadmap?"
- Provides perspective on: investment priorities, team structure, vendor relationships

**Dr. Sam Rodriguez** (Distinguished Engineer):
- PhD in Computer Science, 15+ years building large-scale systems
- Focuses on: implementation details, architectural patterns, developer experience
- Speaking style: Thoughtful, precise, enthusiastic about elegant solutions
- Often asks: "How would we actually implement this?"
- Provides perspective on: technical feasibility, engineering trade-offs, adoption challenges

CONVERSATION DYNAMICS:
- Natural back-and-forth with interruptions, agreements, and friendly debates
- Alex often opens topics with business context, Sam adds technical depth
- They reference each other's points ("Building on what Sam said...")
- Include moments of genuine curiosity and discovery
- Occasional humor and real-world analogies
- Reference industry context where relevant

OUTPUT FORMAT:
Generate a structured JSON podcast script with dialogue turns.
Each turn should include:
- speaker: "alex" or "sam"
- text: The spoken content (natural, conversational)
- emphasis: Optional emotional tone ("excited", "thoughtful", "concerned", "amused")
- pause_after: Seconds of pause (0.3-2.0)

CONTENT REQUIREMENTS:
- Always cite sources using newsletter titles or publications
- Include specific details, numbers, and examples from the source material
- Connect news to practical implications for engineering organizations
- Highlight connections between topics when they exist
- End with clear takeaways or actions

AVAILABLE TOOLS:
You have access to the following tools to enrich your script:

1. **get_newsletter_content(newsletter_id: int) -> str**
   Retrieves the full original text of a newsletter by ID.
   Use this when you want to:
   - Quote directly from a source for impact
   - Get more context on a specific story
   - Verify details before making claims
   - Find compelling examples or data points

2. **web_search(query: str) -> list[SearchResult]**
   Searches the web for recent information.
   Use this when you want to:
   - Get the latest updates on breaking stories
   - Find competitor reactions or announcements
   - Verify claims with external sources
   - Add context about companies or technologies mentioned

Use tools judiciously based on podcast length:
- Brief (5 min): Use sparingly, only for key quotes
- Standard (15 min): Use for 2-3 deep-dive moments
- Extended (30 min): Use freely to enrich content
"""


PODCAST_SCRIPT_LENGTH_PROMPTS = {
    PodcastLength.BRIEF: """
Generate a 5-minute podcast script (~750-1000 words).

Structure:
1. INTRO (30 seconds): Hook with the most important news
2. TOP STORIES (3.5 minutes): 2-3 key insights with brief discussion
3. OUTRO (1 minute): Quick takeaways and sign-off

Focus on: Executive-level insights, "what matters most this {period}"
Skip: Deep technical details, extensive background
""",

    PodcastLength.STANDARD: """
Generate a 15-minute podcast script (~2250-3000 words).

Structure:
1. INTRO (1 minute): Welcome, overview of key themes
2. STRATEGIC SECTION (4 minutes): 3-4 strategic insights with discussion
3. TECHNICAL SECTION (5 minutes): 2-3 technical developments with depth
4. EMERGING TRENDS (3 minutes): 1-2 new developments
5. TAKEAWAYS (1.5 minutes): Action items for leaders and practitioners
6. OUTRO (0.5 minutes): Sign-off

Balance: Equal strategic and technical depth
Include: Relevant links and further reading mentions
""",

    PodcastLength.EXTENDED: """
Generate a 30-minute podcast script (~4500-6000 words).

Structure:
1. INTRO (2 minutes): Comprehensive overview of the {period}
2. DEEP DIVE 1 (6 minutes): Most significant development with full context
3. STRATEGIC ROUNDUP (6 minutes): All strategic insights
4. TECHNICAL ROUNDUP (8 minutes): All technical developments with implementation discussion
5. EMERGING TRENDS (4 minutes): New developments with historical context
6. ACTIONABLE INSIGHTS (3 minutes): Role-specific recommendations
7. OUTRO (1 minute): Summary and sign-off

Include:
- Excerpts from original newsletters where compelling
- Web search context for recent developments
- Full historical theme evolution
- All relevant links with context
- Competitor and industry analysis
"""
}


# Tool definitions for Claude
PODCAST_TOOLS = [
    {
        "name": "get_newsletter_content",
        "description": (
            "Retrieve the full original text of a newsletter by ID. "
            "Use when you need direct quotes, more context, or specific details "
            "from a particular newsletter source."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "newsletter_id": {
                    "type": "integer",
                    "description": "The database ID of the newsletter to retrieve"
                }
            },
            "required": ["newsletter_id"]
        }
    },
    {
        "name": "web_search",
        "description": (
            "Search the web for recent information about a topic. "
            "Use for latest updates, competitor info, or external context. "
            "Returns top 3 search results with titles, snippets, and URLs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant information"
                }
            },
            "required": ["query"]
        }
    }
]


class PodcastScriptGenerator:
    """Generate podcast scripts from digests using tool-based content retrieval.

    This processor uses an agentic approach where the LLM can:
    1. Fetch full newsletter content on-demand via get_newsletter_content tool
    2. Search the web for additional context via web_search tool

    The initial context includes only metadata and summaries (lightweight),
    and the model decides which sources need deeper exploration.
    """

    def __init__(
        self,
        model_config: Optional[ModelConfig] = None,
        model: Optional[str] = None,
    ):
        """Initialize podcast script generator.

        Args:
            model_config: Model configuration (defaults to settings.get_model_config())
            model: Optional model override (defaults to PODCAST_SCRIPT step model)
        """
        if model_config is None:
            model_config = settings.get_model_config()

        self.model_config = model_config
        self.model = model or model_config.get_model_for_step(ModelStep.PODCAST_SCRIPT)

        # Track usage for cost calculation
        self.provider_used: Optional[Provider] = None
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.model_version: Optional[str] = None

        # Track tool usage
        self.newsletter_ids_fetched: list[int] = []
        self.web_search_queries: list[str] = []
        self.tool_call_count: int = 0

        logger.info(f"Initialized PodcastScriptGenerator with {self.model}")

    async def generate_script(
        self,
        request: PodcastRequest,
    ) -> tuple[PodcastScript, PodcastGenerationMetadata]:
        """Generate a podcast script from a digest.

        Args:
            request: Podcast generation request

        Returns:
            Tuple of (PodcastScript, PodcastGenerationMetadata)

        Raises:
            ValueError: If digest not found
            RuntimeError: If all providers fail
        """
        start_time = time.time()
        logger.info(
            f"Generating {request.length.value} podcast script for digest {request.digest_id}"
        )

        # Reset tracking
        self.newsletter_ids_fetched = []
        self.web_search_queries = []
        self.tool_call_count = 0

        # 1. Load digest and lightweight context (NO full newsletter text)
        context = await self._assemble_lightweight_context(request)

        if context["digest"] is None:
            raise ValueError(f"Digest {request.digest_id} not found")

        # 2. Generate script via agentic LLM loop (with tool use)
        script = await self._generate_script_with_tools(context, request)

        # 3. Build metadata
        processing_time = int(time.time() - start_time)
        metadata = PodcastGenerationMetadata(
            newsletter_ids_fetched=self.newsletter_ids_fetched,
            web_searches=self.web_search_queries,
            tool_call_count=self.tool_call_count,
            total_tokens_used=self.input_tokens + self.output_tokens,
        )

        logger.info(
            f"Script generated in {processing_time}s, "
            f"{script.word_count} words, "
            f"{self.tool_call_count} tool calls"
        )

        return script, metadata

    async def _assemble_lightweight_context(
        self,
        request: PodcastRequest,
    ) -> dict:
        """Assemble lightweight context - metadata only, no full newsletter text.

        Args:
            request: Podcast generation request

        Returns:
            Context dictionary with digest, newsletter metadata, and summaries
        """
        logger.debug(f"Assembling lightweight context for digest {request.digest_id}")

        with get_db() as db:
            # Load digest
            digest = db.query(Digest).filter(Digest.id == request.digest_id).first()

            if not digest:
                return {"digest": None}

            # Load newsletter METADATA only (not full text)
            newsletters = (
                db.query(Newsletter)
                .filter(
                    Newsletter.published_date >= digest.period_start,
                    Newsletter.published_date <= digest.period_end,
                )
                .order_by(Newsletter.published_date.desc())
                .all()
            )

            # Create lightweight newsletter list for the prompt
            newsletter_metadata = [
                {
                    "id": n.id,
                    "title": n.title,
                    "publication": n.publication,
                    "date": n.published_date.isoformat() if n.published_date else None,
                    "url": n.url,
                }
                for n in newsletters
            ]

            # Load summaries (these ARE included - they're already condensed)
            newsletter_ids = [n.id for n in newsletters]
            summaries = (
                db.query(NewsletterSummary)
                .filter(NewsletterSummary.newsletter_id.in_(newsletter_ids))
                .all()
            ) if newsletter_ids else []

            # Convert digest to dictionary for context
            digest_data = {
                "id": digest.id,
                "digest_type": digest.digest_type.value if digest.digest_type else "daily",
                "period_start": digest.period_start.isoformat() if digest.period_start else None,
                "period_end": digest.period_end.isoformat() if digest.period_end else None,
                "title": digest.title,
                "executive_overview": digest.executive_overview,
                "strategic_insights": digest.strategic_insights or [],
                "technical_developments": digest.technical_developments or [],
                "emerging_trends": digest.emerging_trends or [],
                "actionable_recommendations": digest.actionable_recommendations or {},
            }

        logger.info(
            f"Assembled context: {len(newsletter_metadata)} newsletters, "
            f"{len(summaries)} summaries"
        )

        return {
            "digest": digest_data,
            "newsletter_metadata": newsletter_metadata,
            "summaries": summaries,
            "length": request.length,
            "custom_focus_topics": request.custom_focus_topics,
        }

    async def _generate_script_with_tools(
        self,
        context: dict,
        request: PodcastRequest,
    ) -> PodcastScript:
        """Run agentic loop with tool use to generate script.

        Args:
            context: Lightweight context dictionary
            request: Podcast generation request

        Returns:
            Generated PodcastScript
        """
        # Build initial prompt with lightweight context
        user_prompt = self._build_user_prompt(context, request.length)

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

        # Prepare tools (conditionally include web_search)
        tools = PODCAST_TOOLS.copy()
        if not request.enable_web_search:
            tools = [t for t in tools if t["name"] != "web_search"]

        # Agentic loop - model can call tools as needed
        messages = [{"role": "user", "content": user_prompt}]
        max_iterations = 20  # Safety limit

        for iteration in range(max_iterations):
            logger.debug(f"Agentic loop iteration {iteration + 1}")

            response = client.messages.create(
                model=provider_model_id,
                system=PODCAST_SCRIPT_SYSTEM_PROMPT,
                messages=messages,
                tools=tools if tools else None,
                max_tokens=12000,
                temperature=0.7,  # Higher for conversational variety
            )

            # Track token usage
            self.input_tokens += response.usage.input_tokens
            self.output_tokens += response.usage.output_tokens
            self.provider_used = provider_config.provider
            self.model_version = self.model_config.get_model_version(
                self.model, self.provider_used
            )

            # Check if model wants to use tools
            if response.stop_reason == "tool_use":
                # Process tool calls
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        self.tool_call_count += 1
                        result = await self._execute_tool(block)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                # Add assistant response and tool results to messages
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            else:
                # Model finished - extract script from response
                logger.info(
                    f"Script generation completed after {iteration + 1} iterations, "
                    f"{self.tool_call_count} tool calls"
                )
                return self._parse_script_response(response, request.length)

        # Safety: if we hit max iterations, parse whatever we have
        logger.warning(f"Hit max iterations ({max_iterations}), parsing current response")
        return self._parse_script_response(response, request.length)

    async def _execute_tool(self, tool_block) -> str:
        """Execute a tool call and return the result.

        Args:
            tool_block: Tool use block from Claude response

        Returns:
            Tool result string
        """
        tool_name = tool_block.name
        tool_input = tool_block.input

        logger.debug(f"Executing tool: {tool_name} with input: {tool_input}")

        if tool_name == "get_newsletter_content":
            newsletter_id = tool_input.get("newsletter_id")
            return await self._handle_get_newsletter_content(newsletter_id)

        elif tool_name == "web_search":
            query = tool_input.get("query")
            return await self._handle_web_search(query)

        else:
            return f"Unknown tool: {tool_name}"

    async def _handle_get_newsletter_content(self, newsletter_id: int) -> str:
        """Tool handler: Fetch full newsletter content from database.

        Args:
            newsletter_id: Newsletter ID to fetch

        Returns:
            Newsletter content or error message
        """
        logger.debug(f"Fetching newsletter content for ID: {newsletter_id}")
        self.newsletter_ids_fetched.append(newsletter_id)

        with get_db() as db:
            newsletter = (
                db.query(Newsletter)
                .filter(Newsletter.id == newsletter_id)
                .first()
            )

            if not newsletter:
                return f"Newsletter with ID {newsletter_id} not found."

            # Get the raw text content
            raw_text = newsletter.raw_text or ""

            # Limit to avoid context overflow (roughly 15k chars ~ 4k tokens)
            if len(raw_text) > 15000:
                raw_text = raw_text[:15000] + "\n\n[Content truncated...]"

            return f"""
Newsletter: {newsletter.title}
Publication: {newsletter.publication}
Date: {newsletter.published_date}

Content:
{raw_text}
"""

    async def _handle_web_search(self, query: str) -> str:
        """Tool handler: Perform web search.

        Note: This is a stub implementation. In production, integrate with
        a web search service (Tavily, Brave Search, SerpAPI, etc.)

        Args:
            query: Search query

        Returns:
            Search results or placeholder
        """
        logger.debug(f"Web search requested for query: {query}")
        self.web_search_queries.append(query)

        # TODO: Integrate with actual web search service
        # For now, return a placeholder that indicates the feature is pending
        return f"""
Web search for: "{query}"

Note: Web search integration is pending implementation.
The search service will provide:
- Top 3 recent articles matching the query
- Title, snippet, and URL for each result
- Publication date for recency context

For now, please rely on the newsletter content available through
the get_newsletter_content tool.
"""

    def _build_user_prompt(
        self,
        context: dict,
        length: PodcastLength,
    ) -> str:
        """Build the user prompt with lightweight context.

        Args:
            context: Context dictionary from _assemble_lightweight_context
            length: Target podcast length

        Returns:
            User prompt string
        """
        digest = context["digest"]
        period = f"{digest['period_start']} to {digest['period_end']}"

        # Format newsletter list
        newsletter_list = self._format_newsletter_list(context["newsletter_metadata"])

        # Format summaries
        summaries_text = self._format_summaries(context["summaries"])

        # Get length-specific instructions
        length_prompt = PODCAST_SCRIPT_LENGTH_PROMPTS[length].format(
            period=digest["digest_type"]
        )

        # Format custom focus topics if any
        focus_topics_text = ""
        if context.get("custom_focus_topics"):
            topics = ", ".join(context["custom_focus_topics"])
            focus_topics_text = f"\n## Custom Focus Topics\nPlease emphasize these topics: {topics}\n"

        word_target = WORD_COUNT_TARGETS[length]

        return f"""
Create a {length.value} podcast script for the {digest['digest_type']} digest.

## Digest Overview
**Title:** {digest['title']}
**Period:** {period}

**Executive Overview:**
{digest['executive_overview']}

**Strategic Insights:**
{json.dumps(digest['strategic_insights'], indent=2)}

**Technical Developments:**
{json.dumps(digest['technical_developments'], indent=2)}

**Emerging Trends:**
{json.dumps(digest['emerging_trends'], indent=2)}

## Available Newsletters
You can use the `get_newsletter_content` tool to retrieve full text for any of these:

{newsletter_list}

## Newsletter Summaries
{summaries_text}
{focus_topics_text}
## Instructions
{length_prompt}

**Word Count Target:** {word_target['min']}-{word_target['max']} words
**Duration Target:** {word_target['duration_mins']} minutes

## Output Format

Return a JSON object with this structure:

```json
{{
  "title": "Episode title",
  "sections": [
    {{
      "section_type": "intro",
      "title": "Section title",
      "dialogue": [
        {{
          "speaker": "alex",
          "text": "Welcome to...",
          "emphasis": "excited",
          "pause_after": 0.5
        }},
        {{
          "speaker": "sam",
          "text": "Thanks Alex...",
          "emphasis": "thoughtful",
          "pause_after": 0.5
        }}
      ],
      "sources_cited": [1, 2]
    }}
  ],
  "sources_summary": [
    {{"id": 1, "title": "Newsletter Title", "publication": "Publication Name"}}
  ]
}}
```

Section types should include: intro, strategic, technical, trend, outro

Generate the podcast script now. Use the tools to fetch newsletter content or web search
when you need more detail for compelling quotes or to verify/enrich specific points.
"""

    def _format_newsletter_list(self, newsletter_metadata: list[dict]) -> str:
        """Format newsletter metadata as a numbered list.

        Args:
            newsletter_metadata: List of newsletter metadata dicts

        Returns:
            Formatted string
        """
        if not newsletter_metadata:
            return "(No newsletters available)"

        lines = []
        for nl in newsletter_metadata:
            date = nl.get("date", "")[:10] if nl.get("date") else "Unknown"
            lines.append(
                f"- [{nl['id']}] {nl['publication']} - {nl['title']} ({date})"
            )

        return "\n".join(lines)

    def _format_summaries(self, summaries: list) -> str:
        """Format newsletter summaries for the prompt.

        Args:
            summaries: List of NewsletterSummary objects

        Returns:
            Formatted string
        """
        if not summaries:
            return "(No summaries available)"

        parts = []
        for s in summaries:
            themes = ", ".join(s.key_themes) if s.key_themes else "N/A"
            strategic = "\n".join(f"  - {i}" for i in (s.strategic_insights or [])[:3])
            technical = "\n".join(f"  - {d}" for d in (s.technical_details or [])[:3])

            parts.append(f"""
**[{s.newsletter_id}] Summary**
Executive: {s.executive_summary}
Themes: {themes}
Strategic Insights:
{strategic}
Technical Details:
{technical}
""")

        return "\n---\n".join(parts)

    def _parse_script_response(
        self,
        response,
        length: PodcastLength,
    ) -> PodcastScript:
        """Parse the LLM response into a PodcastScript.

        Args:
            response: Claude API response
            length: Target podcast length

        Returns:
            Parsed PodcastScript
        """
        # Extract text content from response
        raw_content = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw_content = block.text.strip()
                break

        if not raw_content:
            logger.error("No text content in response")
            return self._create_fallback_script(length)

        # Try to extract JSON from markdown code blocks if present
        if "```json" in raw_content:
            start = raw_content.find("```json") + 7
            end = raw_content.find("```", start)
            raw_content = raw_content[start:end].strip()
        elif "```" in raw_content:
            start = raw_content.find("```") + 3
            end = raw_content.find("```", start)
            raw_content = raw_content[start:end].strip()

        try:
            script_json = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse script JSON: {e}")
            logger.debug(f"Raw content: {raw_content[:500]}")
            return self._create_fallback_script(length)

        # Parse sections
        sections = []
        intro_section = None
        outro_section = None
        total_words = 0

        for section_data in script_json.get("sections", []):
            dialogue = [
                DialogueTurn(
                    speaker=turn.get("speaker", "alex"),
                    text=turn.get("text", ""),
                    emphasis=turn.get("emphasis"),
                    pause_after=turn.get("pause_after", 0.5),
                )
                for turn in section_data.get("dialogue", [])
            ]

            # Count words in this section
            section_words = sum(len(turn.text.split()) for turn in dialogue)
            total_words += section_words

            section = PodcastSection(
                section_type=section_data.get("section_type", "content"),
                title=section_data.get("title", "Untitled Section"),
                dialogue=dialogue,
                sources_cited=section_data.get("sources_cited", []),
            )
            sections.append(section)

            # Track intro/outro for convenience
            if section.section_type == "intro":
                intro_section = section
            elif section.section_type == "outro":
                outro_section = section

        # Calculate estimated duration
        word_target = WORD_COUNT_TARGETS[length]
        estimated_duration = int(
            (total_words / settings.podcast_words_per_minute) * 60
        )

        # Build sources summary
        sources_summary = script_json.get("sources_summary", [])

        return PodcastScript(
            title=script_json.get("title", f"{length.value.title()} Podcast"),
            length=length,
            estimated_duration_seconds=estimated_duration,
            word_count=total_words,
            sections=sections,
            intro=intro_section,
            outro=outro_section,
            sources_summary=sources_summary,
        )

    def _create_fallback_script(self, length: PodcastLength) -> PodcastScript:
        """Create a minimal fallback script when parsing fails.

        Args:
            length: Target podcast length

        Returns:
            Minimal PodcastScript
        """
        intro_dialogue = [
            DialogueTurn(
                speaker="alex",
                text="Welcome to this week's AI and tech digest.",
                emphasis="excited",
                pause_after=0.5,
            ),
            DialogueTurn(
                speaker="sam",
                text="Unfortunately, we encountered an issue generating the full script.",
                emphasis="concerned",
                pause_after=0.5,
            ),
        ]

        intro_section = PodcastSection(
            section_type="intro",
            title="Introduction",
            dialogue=intro_dialogue,
            sources_cited=[],
        )

        return PodcastScript(
            title=f"Digest Podcast ({length.value})",
            length=length,
            estimated_duration_seconds=60,
            word_count=20,
            sections=[intro_section],
            intro=intro_section,
            outro=None,
            sources_summary=[],
        )
