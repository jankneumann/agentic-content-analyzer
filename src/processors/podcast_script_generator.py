"""Podcast script generator for converting digests to audio content.

This module generates conversational podcast scripts from digest content using
an agentic approach with tool-based content retrieval. The model can fetch
full newsletter content on-demand and perform web searches as needed.

Supports multiple LLM providers via LLMRouter:
- Anthropic (Claude)
- Google (Gemini)
- OpenAI (GPT)

Two personas drive the conversation:
- Alex Chen: VP of Engineering (strategic perspective)
- Dr. Sam Rodriguez: Distinguished Engineer (technical deep-dives)
"""

import json
import os
import time
from typing import Any

from src.config import settings
from src.config.models import ModelConfig, ModelFamily, ModelStep, Provider
from src.models.content import Content, ContentStatus
from src.models.digest import Digest
from src.models.podcast import (
    DialogueTurn,
    PodcastGenerationMetadata,
    PodcastLength,
    PodcastRequest,
    PodcastScript,
    PodcastSection,
)
from src.models.summary import Summary
from src.services.llm_router import ToolDefinition
from src.services.prompt_service import PromptService
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


# Word count targets per podcast length
WORD_COUNT_TARGETS = {
    PodcastLength.BRIEF: {"min": 750, "max": 1000, "duration_mins": 5},
    PodcastLength.STANDARD: {"min": 2250, "max": 3000, "duration_mins": 15},
    PodcastLength.EXTENDED: {"min": 4500, "max": 6000, "duration_mins": 30},
}


# Map PodcastLength enum to YAML prompt key suffix
_LENGTH_KEY_MAP = {
    PodcastLength.BRIEF: "length_brief",
    PodcastLength.STANDARD: "length_standard",
    PodcastLength.EXTENDED: "length_extended",
}


# Tool definitions (provider-agnostic)
PODCAST_TOOLS = [
    ToolDefinition(
        name="get_content",
        description=(
            "Retrieve the full original text of a content item by ID. "
            "Use when you need direct quotes, more context, or specific details "
            "from a particular source."
        ),
        parameters={
            "type": "object",
            "properties": {
                "content_id": {
                    "type": "integer",
                    "description": "The database ID of the content item to retrieve",
                }
            },
            "required": ["content_id"],
        },
    ),
    ToolDefinition(
        name="web_search",
        description=(
            "Search the web for recent information about a topic. "
            "Use for latest updates, competitor info, or external context. "
            "Returns top 3 search results with titles, snippets, and URLs."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant information",
                }
            },
            "required": ["query"],
        },
    ),
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
        model_config: ModelConfig | None = None,
        model: str | None = None,
        prompt_service: PromptService | None = None,
    ):
        """Initialize podcast script generator.

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

        # Track usage for cost calculation
        self.provider_used: Provider | None = None
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.model_version: str | None = None

        # Track tool usage
        self.content_ids_fetched: list[int] = []
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
        self.content_ids_fetched = []
        self.web_search_queries = []
        self.tool_call_count = 0

        # 1. Load digest and lightweight context (NO full content text)
        context = await self._assemble_lightweight_context(request)

        if context["digest"] is None:
            raise ValueError(f"Digest {request.digest_id} not found")

        # 2. Generate script via agentic LLM loop (with tool use)
        script = await self._generate_script_with_tools(context, request)

        # 3. Build metadata
        processing_time = int(time.time() - start_time)
        metadata = PodcastGenerationMetadata(
            content_ids_fetched=self.content_ids_fetched,
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
        """Assemble lightweight context - metadata only, no full content text.

        Args:
            request: Podcast generation request

        Returns:
            Context dictionary with digest, content metadata, and summaries
        """
        logger.debug(f"Assembling lightweight context for digest {request.digest_id}")

        with get_db() as db:
            # Load digest
            digest = db.query(Digest).filter(Digest.id == request.digest_id).first()

            if not digest:
                return {"digest": None}

            # Load content METADATA only (not full text)
            contents = (
                db.query(Content)
                .filter(
                    Content.published_date >= digest.period_start,
                    Content.published_date <= digest.period_end,
                    Content.status == ContentStatus.COMPLETED,
                )
                .order_by(Content.published_date.desc())
                .all()
            )

            # Create lightweight content list for the prompt
            content_metadata = [
                {
                    "id": c.id,
                    "title": c.title,
                    "publication": c.publication,
                    "date": c.published_date.isoformat() if c.published_date else None,
                    "url": c.source_url,
                    "source_type": c.source_type.value if c.source_type else None,
                }
                for c in contents
            ]

            # Load summaries (these ARE included - they're already condensed)
            content_ids = [c.id for c in contents]
            summaries = (
                (db.query(Summary).filter(Summary.content_id.in_(content_ids)).all())
                if content_ids
                else []
            )

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
            f"Assembled context: {len(content_metadata)} content items, {len(summaries)} summaries"
        )

        return {
            "digest": digest_data,
            "content_metadata": content_metadata,
            "summaries": summaries,
            "length": request.length,
            "custom_focus_topics": request.custom_focus_topics,
            "custom_instructions": request.custom_instructions,
        }

    async def _generate_script_with_tools(
        self,
        context: dict,
        request: PodcastRequest,
    ) -> PodcastScript:
        """Run agentic loop with tool use to generate script.

        Routes to the appropriate provider-specific implementation based on model family.

        Args:
            context: Lightweight context dictionary
            request: Podcast generation request

        Returns:
            Generated PodcastScript
        """
        # Determine model family for routing
        model_info = self.model_config.get_model_info(self.model)

        if model_info.family == ModelFamily.GEMINI:
            return await self._generate_script_with_gemini(context, request)
        elif model_info.family == ModelFamily.CLAUDE:
            return await self._generate_script_with_anthropic(context, request)
        else:
            raise RuntimeError(
                f"Unsupported model family for podcast generation: {model_info.family}"
            )

    async def _generate_script_with_anthropic(
        self,
        context: dict,
        request: PodcastRequest,
    ) -> PodcastScript:
        """Run agentic loop with Anthropic/Claude.

        Args:
            context: Lightweight context dictionary
            request: Podcast generation request

        Returns:
            Generated PodcastScript
        """
        from anthropic import Anthropic

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
        tool_defs = PODCAST_TOOLS.copy()
        if not request.enable_web_search:
            tool_defs = [t for t in tool_defs if t.name != "web_search"]

        # Convert to Anthropic tool format
        tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tool_defs
        ]

        # Agentic loop - model can call tools as needed
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
        max_iterations = 20  # Safety limit

        for iteration in range(max_iterations):
            logger.debug(f"Agentic loop iteration {iteration + 1}")

            response = client.messages.create(
                model=provider_model_id,
                system=self.prompt_service.get_pipeline_prompt("podcast_script"),
                messages=messages,
                tools=tools if tools else None,
                max_tokens=12000,
                temperature=0.7,  # Higher for conversational variety
            )

            # Track token usage
            self.input_tokens += response.usage.input_tokens
            self.output_tokens += response.usage.output_tokens
            self.provider_used = provider_config.provider
            self.model_version = self.model_config.get_model_version(self.model, self.provider_used)

            # Check if model wants to use tools
            if response.stop_reason == "tool_use":
                # Process tool calls
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        self.tool_call_count += 1
                        result = await self._execute_tool(block)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            }
                        )

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

    async def _generate_script_with_gemini(
        self,
        context: dict,
        request: PodcastRequest,
    ) -> PodcastScript:
        """Run agentic loop with Google Gemini.

        Uses the google-genai SDK for function calling support.

        Args:
            context: Lightweight context dictionary
            request: Podcast generation request

        Returns:
            Generated PodcastScript
        """
        from google import genai
        from google.genai import types

        # Build initial prompt with lightweight context
        user_prompt = self._build_user_prompt(context, request.length)

        # Get API key
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY environment variable not set")

        client = genai.Client(api_key=api_key)

        # Get provider-specific model ID
        provider_model_id = self.model_config.get_provider_model_id(self.model, Provider.GOOGLE_AI)
        self.provider_used = Provider.GOOGLE_AI
        self.model_version = self.model_config.get_model_version(self.model, Provider.GOOGLE_AI)

        # Build Gemini tool declarations
        tool_declarations = [
            types.FunctionDeclaration(
                name="get_content",
                description=(
                    "Retrieve the full original text of a content item by ID. "
                    "Use when you need direct quotes, more context, or specific details "
                    "from a particular source."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "content_id": {
                            "type": "integer",
                            "description": "The database ID of the content item to retrieve",
                        }
                    },
                    "required": ["content_id"],
                },
            ),
        ]

        # Conditionally add web_search tool
        if request.enable_web_search:
            tool_declarations.append(
                types.FunctionDeclaration(
                    name="web_search",
                    description=(
                        "Search the web for recent information about a topic. "
                        "Use for latest updates, competitor info, or external context. "
                        "Returns top 3 search results with titles, snippets, and URLs."
                    ),
                    parameters_json_schema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query to find relevant information",
                            }
                        },
                        "required": ["query"],
                    },
                )
            )

        gemini_tools = types.Tool(function_declarations=tool_declarations)

        # Build initial contents
        contents = [types.Content(role="user", parts=[types.Part.from_text(user_prompt)])]

        # Configure generation
        config = types.GenerateContentConfig(
            system_instruction=self.prompt_service.get_pipeline_prompt("podcast_script"),
            tools=[gemini_tools],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            max_output_tokens=12000,
            temperature=0.7,
        )

        # Agentic loop
        max_iterations = 20

        for iteration in range(max_iterations):
            logger.debug(f"Gemini agentic loop iteration {iteration + 1}")

            response = client.models.generate_content(
                model=provider_model_id,
                contents=contents,
                config=config,
            )

            # Track token usage
            if response.usage_metadata:
                self.input_tokens += response.usage_metadata.prompt_token_count or 0
                self.output_tokens += response.usage_metadata.candidates_token_count or 0

            # Check for function calls
            if response.function_calls:
                # Process function calls
                function_response_parts = []

                for fc in response.function_calls:
                    self.tool_call_count += 1
                    logger.debug(f"Gemini function call: {fc.name}({fc.args})")

                    # Execute the function
                    result = await self._execute_gemini_tool(fc.name, fc.args or {})

                    function_response_parts.append(
                        types.Part.from_function_response(
                            name=fc.name,
                            response={"result": result},
                        )
                    )

                # Add model's function call to contents
                contents.append(response.candidates[0].content)

                # Add tool responses
                contents.append(types.Content(role="tool", parts=function_response_parts))

            else:
                # Model finished - extract script from response
                logger.info(
                    f"Gemini script generation completed after {iteration + 1} iterations, "
                    f"{self.tool_call_count} tool calls"
                )
                return self._parse_gemini_response(response, request.length)

        # Safety: if we hit max iterations, parse whatever we have
        logger.warning(f"Hit max iterations ({max_iterations}), parsing current response")
        return self._parse_gemini_response(response, request.length)

    async def _execute_gemini_tool(self, name: str, args: dict) -> str:
        """Execute a tool call from Gemini.

        Args:
            name: Tool name
            args: Tool arguments

        Returns:
            Tool result string
        """
        if name == "get_content":
            content_id = args.get("content_id")
            return await self._handle_get_content(content_id)
        elif name == "web_search":
            query = args.get("query")
            return await self._handle_web_search(query)
        else:
            return f"Unknown tool: {name}"

    def _parse_gemini_response(self, response, length: PodcastLength) -> PodcastScript:
        """Parse Gemini response into a PodcastScript.

        Args:
            response: Gemini API response
            length: Target podcast length

        Returns:
            Parsed PodcastScript
        """
        # Extract text content
        raw_content = ""
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    raw_content = part.text.strip()
                    break

        if not raw_content:
            logger.error("No text content in Gemini response")
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
            logger.error(f"Failed to parse Gemini script JSON: {e}")
            logger.debug(f"Raw content: {raw_content[:500]}")
            return self._create_fallback_script(length)

        # Parse sections (reuse existing logic)
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
                    pause_after=turn.get("pause_after", 0.0),
                )
                for turn in section_data.get("dialogue", [])
            ]

            section_words = sum(len(turn.text.split()) for turn in dialogue)
            total_words += section_words

            section = PodcastSection(
                section_type=section_data.get("section_type", "content"),
                title=section_data.get("title", "Untitled Section"),
                dialogue=dialogue,
                sources_cited=section_data.get("sources_cited", []),
            )
            sections.append(section)

            if section.section_type == "intro":
                intro_section = section
            elif section.section_type == "outro":
                outro_section = section

        estimated_duration = int((total_words / settings.podcast_words_per_minute) * 60)
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

        if tool_name == "get_content":
            content_id = tool_input.get("content_id")
            return await self._handle_get_content(content_id)

        elif tool_name == "web_search":
            query = tool_input.get("query")
            return await self._handle_web_search(query)

        else:
            return f"Unknown tool: {tool_name}"

    async def _handle_get_content(self, content_id: int) -> str:
        """Tool handler: Fetch full content from database.

        Args:
            content_id: Content ID to fetch

        Returns:
            Content text or error message
        """
        logger.debug(f"Fetching content for ID: {content_id}")
        self.content_ids_fetched.append(content_id)

        with get_db() as db:
            content = db.query(Content).filter(Content.id == content_id).first()

            if not content:
                return f"Content with ID {content_id} not found."

            # Get the markdown content (preferred) or raw text
            text = content.markdown_content or content.raw_text or ""

            # Limit to avoid context overflow (roughly 15k chars ~ 4k tokens)
            if len(text) > 15000:
                text = text[:15000] + "\n\n[Content truncated...]"

            return f"""
Content: {content.title}
Publication: {content.publication}
Date: {content.published_date}
Source: {content.source_type.value if content.source_type else "unknown"}

{text}
"""

    async def _handle_web_search(self, query: str) -> str:
        """Tool handler: Perform web search.

        Uses the configured web search provider (Tavily, Perplexity, or Grok).

        Args:
            query: Search query

        Returns:
            Search results or placeholder
        """
        from src.services.web_search import get_web_search_provider

        logger.debug(f"Web search requested for query: {query}")
        self.web_search_queries.append(query)

        provider = get_web_search_provider()
        results = provider.search(query)

        return provider.format_results(results)

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

        # Format content list
        content_list = self._format_content_list(context["content_metadata"])

        # Format summaries
        summaries_text = self._format_summaries(context["summaries"])

        # Get length-specific instructions
        length_key = _LENGTH_KEY_MAP[length]
        length_prompt = self.prompt_service.render(
            f"pipeline.podcast_script.{length_key}", period=digest["digest_type"]
        )

        # Format custom focus topics if any
        focus_topics_text = ""
        if context.get("custom_focus_topics"):
            topics = ", ".join(context["custom_focus_topics"])
            focus_topics_text = (
                f"\n## Custom Focus Topics\nPlease emphasize these topics: {topics}\n"
            )

        # Format custom instructions if any
        instructions_text = ""
        if context.get("custom_instructions"):
            instructions_text = f"\n## Custom Instructions\n{context['custom_instructions']}\n"

        word_target = WORD_COUNT_TARGETS[length]

        return f"""
Create a {length.value} podcast script for the {digest["digest_type"]} digest.

## Digest Overview
**Title:** {digest["title"]}
**Period:** {period}

**Executive Overview:**
{digest["executive_overview"]}

**Strategic Insights:**
{json.dumps(digest["strategic_insights"], indent=2)}

**Technical Developments:**
{json.dumps(digest["technical_developments"], indent=2)}

**Emerging Trends:**
{json.dumps(digest["emerging_trends"], indent=2)}

## Available Content
You can use the `get_content` tool to retrieve full text for any of these:

{content_list}

## Content Summaries
{summaries_text}
{focus_topics_text}
{instructions_text}
## Instructions
{length_prompt}

**Word Count Target:** {word_target["min"]}-{word_target["max"]} words
**Duration Target:** {word_target["duration_mins"]} minutes

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
    {{"id": 1, "title": "Content Title", "publication": "Publication Name"}}
  ]
}}
```

Section types should include: intro, strategic, technical, trend, outro

Generate the podcast script now. Use the tools to fetch content or web search
when you need more detail for compelling quotes or to verify/enrich specific points.
"""

    def _format_content_list(self, content_metadata: list[dict]) -> str:
        """Format content metadata as a numbered list.

        Args:
            content_metadata: List of content metadata dicts

        Returns:
            Formatted string
        """
        if not content_metadata:
            return "(No content available)"

        lines = []
        for c in content_metadata:
            date = c.get("date", "")[:10] if c.get("date") else "Unknown"
            source = c.get("source_type", "")
            source_suffix = f" [{source}]" if source else ""
            lines.append(f"- [{c['id']}] {c['publication']} - {c['title']} ({date}){source_suffix}")

        return "\n".join(lines)

    def _format_summaries(self, summaries: list) -> str:
        """Format content summaries for the prompt.

        Args:
            summaries: List of Summary objects

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
**[{s.content_id}] Summary**
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
                    pause_after=turn.get("pause_after", 0.0),
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
        estimated_duration = int((total_words / settings.podcast_words_per_minute) * 60)

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
                pause_after=0.0,
            ),
            DialogueTurn(
                speaker="sam",
                text="Unfortunately, we encountered an issue generating the full script.",
                emphasis="concerned",
                pause_after=0.0,
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
