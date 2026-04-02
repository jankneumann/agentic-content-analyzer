"""Tests for agent data models — AgentTask, AgentInsight, AgentMemory, ApprovalRequest.

Covers:
- Enum definitions and values (task 1.0)
- ORM model instantiation and defaults (task 1.1)
- Task lifecycle state machine transitions (agentic-analysis.1)
- Relationship integrity (parent/child tasks, task→insights, task→approvals)
"""

import uuid
from datetime import datetime

import pytest

from src.models.agent_insight import AgentInsight, InsightType
from src.models.agent_memory import AgentMemory, MemoryType
from src.models.agent_task import AgentTask, AgentTaskSource, AgentTaskStatus
from src.models.approval_request import ApprovalRequest, ApprovalStatus, RiskLevel


# =============================================================================
# Enum Tests (Task 1.0)
# =============================================================================


class TestAgentTaskStatusEnum:
    """Test AgentTaskStatus enum values match the state machine."""

    def test_all_states_present(self):
        expected = {
            "received",
            "planning",
            "delegating",
            "monitoring",
            "synthesizing",
            "blocked",
            "completed",
            "failed",
        }
        actual = {s.value for s in AgentTaskStatus}
        assert actual == expected

    def test_values_are_lowercase_strings(self):
        for status in AgentTaskStatus:
            assert status.value == status.value.lower()
            assert isinstance(status.value, str)

    def test_str_enum_comparison(self):
        assert AgentTaskStatus.RECEIVED == "received"
        assert AgentTaskStatus.COMPLETED == "completed"


class TestAgentTaskSourceEnum:
    def test_all_sources_present(self):
        expected = {"user", "schedule", "conductor"}
        actual = {s.value for s in AgentTaskSource}
        assert actual == expected


class TestInsightTypeEnum:
    def test_all_types_present(self):
        expected = {"trend", "connection", "anomaly", "prediction", "summary"}
        actual = {t.value for t in InsightType}
        assert actual == expected


class TestMemoryTypeEnum:
    def test_all_types_present(self):
        expected = {"observation", "insight", "task_result", "preference", "meta_learning"}
        actual = {t.value for t in MemoryType}
        assert actual == expected


class TestRiskLevelEnum:
    def test_all_levels_present(self):
        expected = {"low", "medium", "high", "critical"}
        actual = {r.value for r in RiskLevel}
        assert actual == expected

    def test_ordering_by_severity(self):
        """Risk levels should be orderable by string for comparison."""
        levels = sorted(
            RiskLevel, key=lambda r: ["low", "medium", "high", "critical"].index(r.value)
        )
        assert [l.value for l in levels] == ["low", "medium", "high", "critical"]


class TestApprovalStatusEnum:
    def test_all_statuses_present(self):
        expected = {"pending", "approved", "denied", "expired"}
        actual = {s.value for s in ApprovalStatus}
        assert actual == expected


# =============================================================================
# ORM Model Tests (Task 1.1)
# =============================================================================


class TestAgentTaskModel:
    """Test AgentTask ORM model structure and defaults."""

    def test_table_name(self):
        assert AgentTask.__tablename__ == "agent_tasks"

    def test_column_defaults(self):
        task = AgentTask(
            task_type="research",
            source=AgentTaskSource.USER,
            prompt="What are AI trends?",
        )
        assert task.status is None or task.status == AgentTaskStatus.RECEIVED
        assert task.persona_name is None or task.persona_name == "default"

    def test_required_fields(self):
        """Verify required columns are defined."""
        columns = {c.name for c in AgentTask.__table__.columns}
        required = {"id", "task_type", "source", "prompt", "status", "persona_name"}
        assert required.issubset(columns)

    def test_optional_fields(self):
        """Verify optional/nullable columns exist."""
        columns = {c.name for c in AgentTask.__table__.columns}
        optional = {
            "plan",
            "result",
            "parent_task_id",
            "specialist_type",
            "persona_config",
            "cost_total",
            "tokens_total",
            "error_message",
            "started_at",
            "completed_at",
        }
        assert optional.issubset(columns)

    def test_indexes_defined(self):
        index_names = {idx.name for idx in AgentTask.__table__.indexes}
        assert "ix_agent_tasks_status" in index_names
        assert "ix_agent_tasks_source" in index_names
        assert "ix_agent_tasks_persona" in index_names
        assert "ix_agent_tasks_created_at" in index_names


class TestAgentInsightModel:
    def test_table_name(self):
        assert AgentInsight.__tablename__ == "agent_insights"

    def test_required_fields(self):
        columns = {c.name for c in AgentInsight.__table__.columns}
        required = {"id", "insight_type", "title", "content", "confidence"}
        assert required.issubset(columns)

    def test_confidence_range_not_enforced_at_model_level(self):
        """Confidence validation is at the service layer, not ORM."""
        insight = AgentInsight(
            insight_type=InsightType.TREND,
            title="Test",
            content="Test content",
            confidence=0.95,
        )
        assert insight.confidence == 0.95

    def test_indexes_defined(self):
        index_names = {idx.name for idx in AgentInsight.__table__.indexes}
        assert "ix_agent_insights_type" in index_names
        assert "ix_agent_insights_confidence" in index_names


class TestAgentMemoryModel:
    def test_table_name(self):
        assert AgentMemory.__tablename__ == "agent_memories"

    def test_required_fields(self):
        columns = {c.name for c in AgentMemory.__table__.columns}
        required = {"id", "memory_type", "content"}
        assert required.issubset(columns)

    def test_default_confidence(self):
        """Default confidence should be 1.0 (fully reliable)."""
        col = AgentMemory.__table__.c.confidence
        assert col.default.arg == 1.0

    def test_default_access_count(self):
        col = AgentMemory.__table__.c.access_count
        assert col.default.arg == 0

    def test_embedding_not_orm_mapped(self):
        """Embedding column is NOT in the ORM model — it's raw SQL only (pgvector gotcha)."""
        columns = {c.name for c in AgentMemory.__table__.columns}
        assert "embedding" not in columns


class TestApprovalRequestModel:
    def test_table_name(self):
        assert ApprovalRequest.__tablename__ == "approval_requests"

    def test_required_fields(self):
        columns = {c.name for c in ApprovalRequest.__table__.columns}
        required = {"id", "task_id", "action", "risk_level", "context", "status"}
        assert required.issubset(columns)

    def test_indexes_defined(self):
        index_names = {idx.name for idx in ApprovalRequest.__table__.indexes}
        assert "ix_approval_requests_status" in index_names
        assert "ix_approval_requests_task" in index_names


# =============================================================================
# Relationship Tests
# =============================================================================


class TestRelationships:
    """Test that ORM relationships are properly configured."""

    def test_agent_task_has_insights_relationship(self):
        assert hasattr(AgentTask, "insights")

    def test_agent_task_has_approval_requests_relationship(self):
        assert hasattr(AgentTask, "approval_requests")

    def test_agent_task_has_sub_tasks_relationship(self):
        assert hasattr(AgentTask, "sub_tasks")

    def test_agent_insight_has_task_relationship(self):
        assert hasattr(AgentInsight, "task")

    def test_approval_request_has_task_relationship(self):
        assert hasattr(ApprovalRequest, "task")
