"""MCP composition root with an explicit stable tool manifest."""

from __future__ import annotations

from typing import Any

from src.mcp_tools import content, ingestion, knowledge, operations, review, workflows

TOOLSETS = (
    ingestion.TOOLS,
    content.TOOLS,
    workflows.TOOLS,
    review.TOOLS,
    operations.TOOLS,
    knowledge.TOOLS,
)
CANONICAL_TOOLS = tuple(tool for toolset in TOOLSETS for tool in toolset)
CANONICAL_TOOL_NAMES = (
    "upload_content",
    "ingest_gmail",
    "ingest_rss",
    "ingest_blog",
    "ingest_substack",
    "ingest_youtube_playlist",
    "ingest_youtube_rss",
    "ingest_podcast",
    "ingest_x_search",
    "ingest_perplexity_search",
    "ingest_files",
    "ingest_url",
    "ingest_scholar_search",
    "ingest_scholar_paper",
    "ingest_scholar_references",
    "ingest_arxiv_search",
    "ingest_arxiv_paper",
    "ingest_huggingface_papers",
    "ingest_readwise",
    "search_content",
    "summarize_pending",
    "analyze_themes",
    "create_digest",
    "run_pipeline",
    "generate_podcast_script",
    "generate_podcast_audio",
    "generate_audio_digest",
    "finalize_review",
    "get_capabilities",
    "list_configured_sources",
    "list_operations",
    "get_operation_status",
    "wait_for_operation",
    "retry_operation",
    "cancel_operation",
    "search_knowledge_graph",
    "extract_references",
    "resolve_references",
)

if tuple(tool.__name__ for tool in CANONICAL_TOOLS) != CANONICAL_TOOL_NAMES:
    raise RuntimeError("MCP tool registration drifted from the explicit canonical manifest")


def register_toolsets(server: Any) -> None:
    for tool in CANONICAL_TOOLS:
        server.tool()(tool)
