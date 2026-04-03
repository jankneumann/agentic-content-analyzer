"""Tests for approval gates — risk-tiered action control."""

import logging

import pytest

from src.agents.approval.gates import ApprovalGate
from src.models.approval_request import RiskLevel


@pytest.fixture()
def base_config() -> dict[str, RiskLevel]:
    """Base approval config matching settings/approval.yaml."""
    return {
        "search_content": RiskLevel.LOW,
        "query_knowledge_graph": RiskLevel.LOW,
        "analyze_themes": RiskLevel.LOW,
        "ingest_source": RiskLevel.MEDIUM,
        "ingest_url": RiskLevel.MEDIUM,
        "run_pipeline": RiskLevel.MEDIUM,
        "create_digest": RiskLevel.HIGH,
        "send_email": RiskLevel.HIGH,
        "publish_digest": RiskLevel.HIGH,
        "delete_content": RiskLevel.CRITICAL,
        "modify_agent_config": RiskLevel.CRITICAL,
    }


class TestGetRiskLevel:
    """Tests for risk level resolution logic."""

    def test_base_config_returns_configured_level(self, base_config: dict[str, RiskLevel]) -> None:
        gate = ApprovalGate(base_config=base_config)
        assert gate.get_risk_level("search_content") == RiskLevel.LOW
        assert gate.get_risk_level("ingest_source") == RiskLevel.MEDIUM
        assert gate.get_risk_level("create_digest") == RiskLevel.HIGH
        assert gate.get_risk_level("delete_content") == RiskLevel.CRITICAL

    def test_unknown_action_defaults_to_medium(self, base_config: dict[str, RiskLevel]) -> None:
        gate = ApprovalGate(base_config=base_config)
        assert gate.get_risk_level("unknown_action") == RiskLevel.MEDIUM

    def test_override_takes_precedence_over_base(self, base_config: dict[str, RiskLevel]) -> None:
        overrides = {"create_digest": RiskLevel.MEDIUM}
        gate = ApprovalGate(base_config=base_config, overrides=overrides)
        assert gate.get_risk_level("create_digest") == RiskLevel.MEDIUM

    def test_override_lowering_risk_is_allowed(self, base_config: dict[str, RiskLevel]) -> None:
        overrides = {
            "send_email": RiskLevel.MEDIUM,  # HIGH -> MEDIUM
            "delete_content": RiskLevel.HIGH,  # CRITICAL -> HIGH
        }
        gate = ApprovalGate(base_config=base_config, overrides=overrides)
        assert gate.get_risk_level("send_email") == RiskLevel.MEDIUM
        assert gate.get_risk_level("delete_content") == RiskLevel.HIGH

    def test_override_escalation_is_ignored(
        self,
        base_config: dict[str, RiskLevel],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        overrides = {"search_content": RiskLevel.HIGH}  # LOW -> HIGH = escalation
        gate = ApprovalGate(base_config=base_config, overrides=overrides)

        with caplog.at_level(logging.WARNING):
            level = gate.get_risk_level("search_content")

        assert level == RiskLevel.LOW  # Escalation ignored
        assert "escalate" in caplog.text.lower()

    def test_override_same_level_is_allowed(self, base_config: dict[str, RiskLevel]) -> None:
        overrides = {"ingest_source": RiskLevel.MEDIUM}  # MEDIUM -> MEDIUM (no change)
        gate = ApprovalGate(base_config=base_config, overrides=overrides)
        assert gate.get_risk_level("ingest_source") == RiskLevel.MEDIUM

    def test_no_overrides_uses_base_only(self, base_config: dict[str, RiskLevel]) -> None:
        gate = ApprovalGate(base_config=base_config, overrides=None)
        assert gate.get_risk_level("create_digest") == RiskLevel.HIGH


class TestCheckAction:
    """Tests for auto-approve / block decisions."""

    def test_low_risk_auto_approved(self, base_config: dict[str, RiskLevel]) -> None:
        gate = ApprovalGate(base_config=base_config)
        auto_approved, risk_level = gate.check_action("search_content")
        assert auto_approved is True
        assert risk_level == RiskLevel.LOW

    def test_medium_risk_auto_approved(self, base_config: dict[str, RiskLevel]) -> None:
        gate = ApprovalGate(base_config=base_config)
        auto_approved, risk_level = gate.check_action("ingest_source")
        assert auto_approved is True
        assert risk_level == RiskLevel.MEDIUM

    def test_high_risk_blocked(self, base_config: dict[str, RiskLevel]) -> None:
        gate = ApprovalGate(base_config=base_config)
        auto_approved, risk_level = gate.check_action("create_digest")
        assert auto_approved is False
        assert risk_level == RiskLevel.HIGH

    def test_critical_risk_blocked(self, base_config: dict[str, RiskLevel]) -> None:
        gate = ApprovalGate(base_config=base_config)
        auto_approved, risk_level = gate.check_action("delete_content")
        assert auto_approved is False
        assert risk_level == RiskLevel.CRITICAL

    def test_unknown_action_defaults_medium_auto_approved(
        self, base_config: dict[str, RiskLevel]
    ) -> None:
        gate = ApprovalGate(base_config=base_config)
        auto_approved, risk_level = gate.check_action("some_new_action")
        assert auto_approved is True
        assert risk_level == RiskLevel.MEDIUM

    def test_override_lowers_high_to_medium_auto_approves(
        self, base_config: dict[str, RiskLevel]
    ) -> None:
        overrides = {"create_digest": RiskLevel.MEDIUM}
        gate = ApprovalGate(base_config=base_config, overrides=overrides)
        auto_approved, risk_level = gate.check_action("create_digest")
        assert auto_approved is True
        assert risk_level == RiskLevel.MEDIUM

    def test_escalation_override_still_blocks(self, base_config: dict[str, RiskLevel]) -> None:
        """If an override tries to escalate LOW to HIGH, it's ignored — stays LOW."""
        overrides = {"search_content": RiskLevel.HIGH}
        gate = ApprovalGate(base_config=base_config, overrides=overrides)
        auto_approved, risk_level = gate.check_action("search_content")
        assert auto_approved is True
        assert risk_level == RiskLevel.LOW
