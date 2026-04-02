"""Tests for memory domain models — MemoryEntry, MemoryFilter.

Covers Task 1.4: MemoryStrategy ABC and MemoryProvider composition models.
"""

from datetime import datetime

import pytest

from src.agents.memory.models import MemoryEntry, MemoryFilter, MemoryType


class TestMemoryEntry:
    def test_create_minimal(self):
        entry = MemoryEntry(content="Test observation", memory_type=MemoryType.OBSERVATION)
        assert entry.content == "Test observation"
        assert entry.memory_type == MemoryType.OBSERVATION
        assert entry.confidence == 1.0
        assert entry.access_count == 0
        assert entry.score == 0.0
        assert entry.tags == []

    def test_create_full(self):
        entry = MemoryEntry(
            id="mem-123",
            content="AI agents are trending",
            memory_type=MemoryType.INSIGHT,
            source_task_id="task-456",
            tags=["ai", "agents"],
            confidence=0.85,
            access_count=3,
            score=0.92,
        )
        assert entry.id == "mem-123"
        assert entry.source_task_id == "task-456"
        assert entry.tags == ["ai", "agents"]
        assert entry.confidence == 0.85

    def test_confidence_validation_min(self):
        with pytest.raises(Exception):
            MemoryEntry(content="test", memory_type=MemoryType.OBSERVATION, confidence=-0.1)

    def test_confidence_validation_max(self):
        with pytest.raises(Exception):
            MemoryEntry(content="test", memory_type=MemoryType.OBSERVATION, confidence=1.1)

    def test_confidence_boundary_values(self):
        low = MemoryEntry(content="test", memory_type=MemoryType.OBSERVATION, confidence=0.0)
        high = MemoryEntry(content="test", memory_type=MemoryType.OBSERVATION, confidence=1.0)
        assert low.confidence == 0.0
        assert high.confidence == 1.0


class TestMemoryFilter:
    def test_empty_filter(self):
        f = MemoryFilter()
        assert f.memory_types is None
        assert f.tags is None
        assert f.min_confidence is None
        assert f.source_task_id is None
        assert f.since is None

    def test_filter_with_types(self):
        f = MemoryFilter(memory_types=[MemoryType.OBSERVATION, MemoryType.INSIGHT])
        assert len(f.memory_types) == 2

    def test_filter_with_all_fields(self):
        f = MemoryFilter(
            memory_types=[MemoryType.TASK_RESULT],
            tags=["ai"],
            min_confidence=0.5,
            source_task_id="task-1",
            since=datetime(2026, 1, 1),
        )
        assert f.min_confidence == 0.5
        assert f.since == datetime(2026, 1, 1)


class TestMemoryType:
    def test_all_types(self):
        expected = {"observation", "insight", "task_result", "preference", "meta_learning"}
        assert {t.value for t in MemoryType} == expected
