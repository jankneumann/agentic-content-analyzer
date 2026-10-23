from __future__ import annotations

from src.mcp_tools import operations


def test_mcp_tool_boundary_declares_its_operational_root() -> None:
    assert operations.wait_for_operation.__aca_operational_entrypoint__ == (
        "mcp.wait_for_operation",
        "submit",
        "aca-mcp",
    )
    assert operations.wait_for_operation.__name__ == "wait_for_operation"
    assert not hasattr(operations.wait_for_operation, "__aca_capture_arguments__")
