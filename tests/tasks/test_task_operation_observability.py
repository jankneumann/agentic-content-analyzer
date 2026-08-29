from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.tasks.content import register_content_tasks


class _Registry:
    def __init__(self) -> None:
        self.registered: dict[str, Callable[..., Any]] = {}

    def entrypoint(self, name: str):
        def decorate(function: Callable[..., Any]) -> Callable[..., Any]:
            self.registered[name] = function
            return function

        return decorate


def test_all_content_tasks_declare_operational_roots() -> None:
    registry = _Registry()

    register_content_tasks(registry)  # type: ignore[arg-type]

    assert set(registry.registered) == {
        "extract_url_content",
        "process_content",
        "scan_newsletters",
        "summarize_content",
        "ingest_content",
    }
    expected_stages = {
        "extract_url_content": "extract",
        "process_content": "model",
        "scan_newsletters": "fetch",
        "summarize_content": "model",
        "ingest_content": "fetch",
    }
    for name, function in registry.registered.items():
        assert function.__aca_operational_entrypoint__ == (
            f"task.{name}",
            expected_stages[name],
            "aca-task",
        )
