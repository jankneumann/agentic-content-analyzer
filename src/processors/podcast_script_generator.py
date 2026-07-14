"""Digest-bound, provider-neutral podcast script generation."""

from __future__ import annotations

import json
import time
from typing import Any

from src.config import settings
from src.config.models import ModelConfig, ModelStep, Provider
from src.models.content import Content
from src.models.podcast import (
    DialogueTurn,
    PodcastGenerationMetadata,
    PodcastLength,
    PodcastRequest,
    PodcastScript,
    PodcastSection,
)
from src.processors.provenance import ExactContentSetLoader, ProvenanceViolationError
from src.services.llm_router import LLMResponse, LLMRouter, ToolDefinition
from src.services.prompt_service import PromptService
from src.storage.database import get_db
from src.telemetry.decorators import observe
from src.utils.logging import get_logger

logger = get_logger(__name__)

WORD_COUNT_TARGETS = {
    PodcastLength.BRIEF: {"min": 750, "max": 1000, "duration_mins": 5},
    PodcastLength.STANDARD: {"min": 2250, "max": 3000, "duration_mins": 15},
    PodcastLength.EXTENDED: {"min": 4500, "max": 6000, "duration_mins": 30},
}

_LENGTH_KEY_MAP = {
    PodcastLength.BRIEF: "length_brief",
    PodcastLength.STANDARD: "length_standard",
    PodcastLength.EXTENDED: "length_extended",
}

PODCAST_TOOLS = [
    ToolDefinition(
        name="get_content",
        description="Retrieve the full text of one content item from the digest snapshot.",
        parameters={
            "type": "object",
            "properties": {
                "content_id": {
                    "type": "integer",
                    "description": "A content ID listed in the digest snapshot",
                }
            },
            "required": ["content_id"],
            "additionalProperties": False,
        },
    ),
    ToolDefinition(
        name="web_search",
        description="Search the web for external context or recent verification.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    ),
]


class PodcastScriptGenerator:
    """Generate a script from one validated digest provenance snapshot."""

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        model: str | None = None,
        prompt_service: PromptService | None = None,
        content_loader: ExactContentSetLoader | None = None,
        llm_router: LLMRouter | None = None,
    ) -> None:
        model_config = model_config or settings.get_model_config()
        self.model_config = model_config
        self.model = model or model_config.get_model_for_step(ModelStep.PODCAST_SCRIPT)
        self.model_used = self.model
        self.prompt_service = prompt_service or PromptService()
        self.content_loader = content_loader or ExactContentSetLoader()
        self.llm_router = llm_router or LLMRouter(model_config)

        self.provider_used: Provider | None = None
        self.input_tokens = 0
        self.output_tokens = 0
        self.model_version: str | None = None
        self.content_ids_fetched: list[int] = []
        self.web_search_queries: list[str] = []
        self.tool_call_count = 0
        self.available_content_ids: tuple[int, ...] = ()
        self.cited_content_ids: tuple[int, ...] = ()
        self.selection_fingerprint: str | None = None

    @observe()
    async def generate_script(
        self,
        request: PodcastRequest,
    ) -> tuple[PodcastScript, PodcastGenerationMetadata]:
        """Generate using only the digest's exact content/summary snapshot."""

        started = time.monotonic()
        self._reset_tracking()
        context = await self._assemble_lightweight_context(request)
        script = await self._generate_script_with_tools(context, request)
        self.cited_content_ids = self._validate_script_provenance(script)
        logger.info(
            "Podcast script generated in %.2fs with %s tools and %s citations",
            time.monotonic() - started,
            self.tool_call_count,
            len(self.cited_content_ids),
        )
        return script, PodcastGenerationMetadata(
            content_ids_fetched=self.content_ids_fetched,
            web_searches=self.web_search_queries,
            tool_call_count=self.tool_call_count,
            total_tokens_used=self.input_tokens + self.output_tokens,
        )

    def _reset_tracking(self) -> None:
        self.model_used = self.model
        self.provider_used = None
        self.input_tokens = 0
        self.output_tokens = 0
        self.model_version = None
        self.content_ids_fetched = []
        self.web_search_queries = []
        self.tool_call_count = 0
        self.available_content_ids = ()
        self.cited_content_ids = ()
        self.selection_fingerprint = None

    async def _assemble_lightweight_context(self, request: PodcastRequest) -> dict[str, Any]:
        """Load no period data: only the validated digest snapshot."""

        loaded = self.content_loader.load_digest(request.digest_id)
        digest = loaded.digest
        self.available_content_ids = loaded.resolved_set.content_ids
        self.selection_fingerprint = loaded.resolved_set.fingerprint
        content_metadata = [
            {
                "id": item.content.id,
                "title": item.content.title,
                "publication": item.content.publication,
                "date": resolved.selection_date.isoformat(),
                "url": item.content.source_url,
                "source_type": item.content.source_type.value,
            }
            for item, resolved in zip(loaded.items, loaded.resolved_set.items, strict=True)
        ]
        return {
            "digest": {
                "id": digest.id,
                "digest_type": digest.digest_type.value if digest.digest_type else "daily",
                "period_start": digest.period_start.isoformat(),
                "period_end": digest.period_end.isoformat(),
                "title": digest.title,
                "executive_overview": digest.executive_overview,
                "strategic_insights": digest.strategic_insights or [],
                "technical_developments": digest.technical_developments or [],
                "emerging_trends": digest.emerging_trends or [],
                "actionable_recommendations": digest.actionable_recommendations or {},
            },
            "content_metadata": content_metadata,
            "summaries": [item.summary for item in loaded.items],
            "selection_fingerprint": loaded.resolved_set.fingerprint,
            "selection_policy": loaded.resolved_set.policy.model_dump(mode="json"),
            "length": request.length,
            "custom_focus_topics": request.custom_focus_topics,
            "custom_instructions": request.custom_instructions,
        }

    async def _generate_script_with_tools(
        self,
        context: dict[str, Any],
        request: PodcastRequest,
    ) -> PodcastScript:
        tools = PODCAST_TOOLS
        if not request.enable_web_search:
            tools = [tool for tool in tools if tool.name != "web_search"]

        async def execute(name: str, args: dict[str, Any]) -> str:
            self.tool_call_count += 1
            if name == "get_content":
                return await self._handle_get_content(args.get("content_id"))
            if name == "web_search":
                return await self._handle_web_search(args.get("query", ""))
            return json.dumps(
                {"error": {"type": "unknown_tool", "message": f"Unknown tool: {name}"}},
                separators=(",", ":"),
                sort_keys=True,
            )

        response = await self.llm_router.generate_with_tools(
            model=self.model,
            system_prompt=self.prompt_service.get_pipeline_prompt("podcast_script"),
            user_prompt=self._build_user_prompt(context, request.length),
            tools=tools,
            tool_executor=execute,
            max_tokens=12000,
            temperature=0.7,
            max_iterations=20,
            step=ModelStep.PODCAST_SCRIPT,
        )
        self._record_response(response)
        return self._parse_script_response(response, request.length)

    def _record_response(self, response: LLMResponse) -> None:
        self.provider_used = response.provider
        self.input_tokens += response.input_tokens
        self.output_tokens += response.output_tokens
        self.model_version = response.model_version
        self.model_used = response.selected_model or self.model
        cost = self.model_config.calculate_cost(
            model_id=self.model_used,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            provider=response.provider,
        )
        logger.info(
            "Podcast LLM call: model=%s provider=%s tokens=%s cost=$%.4f",
            self.model_used,
            response.provider.value if response.provider else "unknown",
            response.input_tokens + response.output_tokens,
            cost,
        )

    async def _handle_get_content(self, content_id: int | None) -> str:
        if content_id not in self.available_content_ids:
            return ProvenanceViolationError(
                f"Content {content_id} is not available in the digest snapshot",
                resource_id=content_id,
            ).as_tool_result()

        with get_db() as db:
            content = db.query(Content).filter(Content.id == content_id).first()
            if content is None:
                return json.dumps(
                    {
                        "error": {
                            "type": "missing_content",
                            "message": f"Content {content_id} not found",
                        }
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
            text = content.markdown_content or content.raw_content or ""
            if len(text) > 15000:
                text = f"{text[:15000]}\n\n[Content truncated...]"
            if content_id not in self.content_ids_fetched:
                self.content_ids_fetched.append(content_id)
            return (
                f"Content: {content.title}\nPublication: {content.publication}\n"
                f"Date: {content.published_date}\nSource: {content.source_type.value}\n\n{text}"
            )

    async def _handle_web_search(self, query: str) -> str:
        from src.services.web_search import get_web_search_provider

        if not query:
            return json.dumps(
                {"error": {"type": "invalid_tool_input", "message": "query is required"}},
                separators=(",", ":"),
                sort_keys=True,
            )
        self.web_search_queries.append(query)
        provider = get_web_search_provider()
        return provider.format_results(provider.search(query))

    def _validate_script_provenance(self, script: PodcastScript) -> tuple[int, ...]:
        available = set(self.available_content_ids)
        cited = {content_id for section in script.sections for content_id in section.sources_cited}
        outside = sorted(cited - available)
        if outside:
            raise ProvenanceViolationError(
                f"Podcast citation references content outside digest snapshot: {outside}"
            )
        source_summary_ids: set[int] = set()
        for source in script.sources_summary:
            content_id = source.get("id")
            if content_id is None:
                continue
            if not isinstance(content_id, int):
                raise ProvenanceViolationError(
                    f"Podcast source summary has a non-integer content ID: {content_id!r}"
                )
            source_summary_ids.add(content_id)
        outside_sources = sorted(source_summary_ids - available)
        if outside_sources:
            raise ProvenanceViolationError(
                f"Podcast source summary references content outside digest snapshot: {outside_sources}"
            )
        return tuple(content_id for content_id in self.available_content_ids if content_id in cited)

    def _build_user_prompt(self, context: dict[str, Any], length: PodcastLength) -> str:
        digest = context["digest"]
        content_list = self._format_content_list(context["content_metadata"])
        summaries_text = self._format_summaries(context["summaries"])
        length_prompt = self.prompt_service.render(
            f"pipeline.podcast_script.{_LENGTH_KEY_MAP[length]}",
            period=digest["digest_type"],
        )
        focus = ""
        if context.get("custom_focus_topics"):
            focus = "\nFocus topics: " + ", ".join(context["custom_focus_topics"])
        instructions = ""
        if context.get("custom_instructions"):
            instructions = "\nCustom instructions: " + context["custom_instructions"]
        target = WORD_COUNT_TARGETS[length]
        return f"""
Create a {length.value} podcast script for this {digest["digest_type"]} digest.

Digest: {digest["title"]}
Period: {digest["period_start"]} to {digest["period_end"]}
Selection fingerprint: {context.get("selection_fingerprint", "not-persisted")}

Executive overview:
{digest["executive_overview"]}

Strategic insights:
{json.dumps(digest.get("strategic_insights", []), indent=2)}

Technical developments:
{json.dumps(digest.get("technical_developments", []), indent=2)}

Emerging trends:
{json.dumps(digest.get("emerging_trends", []), indent=2)}

Actionable recommendations:
{json.dumps(digest.get("actionable_recommendations", {}), indent=2)}

Available content (only these IDs may be fetched or cited):
{content_list}

Exact persisted summaries:
{summaries_text}
{focus}
{instructions}

{length_prompt}
Target {target["min"]}-{target["max"]} words. Return one JSON object with title,
sections (section_type, title, dialogue, sources_cited), and sources_summary.
Every sources_cited and sources_summary ID must be from Available content.
"""

    def _format_content_list(self, content_metadata: list[dict[str, Any]]) -> str:
        if not content_metadata:
            return "(No content available)"
        lines = []
        for content in content_metadata:
            date = content.get("date", "")[:10] if content.get("date") else "Unknown"
            source = content.get("source_type")
            suffix = f" [{source}]" if source else ""
            lines.append(
                f"- [{content['id']}] {content['publication']} - "
                f"{content['title']} ({date}){suffix}"
            )
        return "\n".join(lines)

    def _format_summaries(self, summaries: list[Any]) -> str:
        if not summaries:
            return "(No summaries available)"
        parts = []
        for summary in summaries:
            themes = ", ".join(summary.key_themes or []) or "N/A"
            strategic = "\n".join(f"  - {item}" for item in (summary.strategic_insights or [])[:3])
            technical = "\n".join(f"  - {item}" for item in (summary.technical_details or [])[:3])
            parts.append(
                f"**[{summary.content_id}] Summary {getattr(summary, 'id', summary.content_id)}**\n"
                f"Executive: {summary.executive_summary}\nThemes: {themes}\n"
                f"Strategic Insights:\n{strategic}\nTechnical Details:\n{technical}"
            )
        return "\n---\n".join(parts)

    def _parse_script_response(
        self,
        response: LLMResponse | Any,
        length: PodcastLength,
    ) -> PodcastScript:
        raw_content = getattr(response, "text", "") or ""
        if not isinstance(raw_content, str):
            raw_content = ""
        if not raw_content:
            for block in getattr(response, "content", []) or []:
                block_text = getattr(block, "text", "")
                if block_text:
                    raw_content = block_text
                    break
        if not raw_content:
            return self._create_fallback_script(length)
        if "~~~json" in raw_content:
            start = raw_content.find("~~~json") + 7
            end = raw_content.find("~~~", start)
            raw_content = raw_content[start:end].strip()
        elif "~~~" in raw_content:
            start = raw_content.find("~~~") + 3
            end = raw_content.find("~~~", start)
            raw_content = raw_content[start:end].strip()
        else:
            fence = chr(96) * 3
            json_fence = f"{fence}json"
            if json_fence in raw_content:
                start = raw_content.find(json_fence) + len(json_fence)
                end = raw_content.find(fence, start)
                raw_content = raw_content[start:end].strip()
            elif fence in raw_content:
                start = raw_content.find(fence) + len(fence)
                end = raw_content.find(fence, start)
                raw_content = raw_content[start:end].strip()
        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError:
            logger.error("Failed to parse podcast script JSON")
            return self._create_fallback_script(length)

        sections: list[PodcastSection] = []
        total_words = 0
        for section_data in data.get("sections", []):
            dialogue = [
                DialogueTurn.model_validate(turn) for turn in section_data.get("dialogue", [])
            ]
            total_words += sum(len(turn.text.split()) for turn in dialogue)
            sections.append(
                PodcastSection(
                    section_type=section_data.get("section_type", "content"),
                    title=section_data.get("title", "Untitled Section"),
                    dialogue=dialogue,
                    sources_cited=section_data.get("sources_cited", []),
                )
            )
        script = PodcastScript(
            title=data.get("title", f"{length.value.title()} Podcast"),
            length=length,
            estimated_duration_seconds=int((total_words / settings.podcast_words_per_minute) * 60),
            word_count=total_words,
            sections=sections,
            intro=next((section for section in sections if section.section_type == "intro"), None),
            outro=next((section for section in sections if section.section_type == "outro"), None),
            sources_summary=data.get("sources_summary", []),
        )
        self._validate_script_provenance(script)
        return script

    def _create_fallback_script(self, length: PodcastLength) -> PodcastScript:
        intro = PodcastSection(
            section_type="intro",
            title="Introduction",
            dialogue=[
                DialogueTurn(
                    speaker="alex",
                    text="Welcome to this AI and technology digest.",
                    emphasis="thoughtful",
                    pause_after=0.0,
                ),
                DialogueTurn(
                    speaker="sam",
                    text="We encountered an issue generating the complete script.",
                    emphasis="concerned",
                    pause_after=0.0,
                ),
            ],
            sources_cited=[],
        )
        return PodcastScript(
            title=f"Digest Podcast ({length.value})",
            length=length,
            estimated_duration_seconds=30,
            word_count=8,
            sections=[intro],
            intro=intro,
            sources_summary=[],
        )
