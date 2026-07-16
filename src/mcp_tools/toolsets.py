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
CANONICAL_TOOL_NAMES = tuple(tool.__name__ for tool in CANONICAL_TOOLS)

if len(CANONICAL_TOOL_NAMES) != len(set(CANONICAL_TOOL_NAMES)):
    raise RuntimeError("MCP tool names must be globally unique")


def register_toolsets(server: Any) -> None:
    for tool in CANONICAL_TOOLS:
        server.tool()(tool)
