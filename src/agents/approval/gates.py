"""Approval gates for risk-tiered action control.

Actions are classified by risk level. The approval gate system intercepts
high-risk actions before execution:
- LOW: auto-approve silently
- MEDIUM: log + auto-approve
- HIGH: block (requires human approval)
- CRITICAL: block (requires human approval + audit)

Persona overrides can only LOWER risk levels, never escalate.
"""

import logging

from src.models.approval_request import RiskLevel

logger = logging.getLogger(__name__)

# Ordering for risk comparison — higher index = higher risk.
_RISK_ORDER: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


class ApprovalGate:
    """Risk-tiered approval gate with persona override support.

    Resolves effective risk levels for actions and decides whether
    they can proceed automatically or require human approval.
    """

    def __init__(
        self,
        base_config: dict[str, RiskLevel],
        overrides: dict[str, RiskLevel] | None = None,
    ) -> None:
        self.base_config = base_config
        self.overrides = overrides or {}

    def get_risk_level(self, action: str) -> RiskLevel:
        """Resolve effective risk level for an action.

        Resolution order: persona override > base config > default MEDIUM.
        Persona overrides can only lower risk, never escalate.
        """
        base_level = self.base_config.get(action, RiskLevel.MEDIUM)

        if action not in self.overrides:
            return base_level

        override_level = self.overrides[action]

        # Persona overrides can only LOWER risk, never escalate.
        if _RISK_ORDER[override_level] > _RISK_ORDER[base_level]:
            logger.warning(
                "Persona override for '%s' attempted to escalate risk from %s to %s — ignoring override",
                action,
                base_level.value,
                override_level.value,
            )
            return base_level

        return override_level

    def check_action(self, action: str) -> tuple[bool, RiskLevel]:
        """Check whether an action is auto-approved.

        Returns:
            Tuple of (auto_approved, risk_level).
            - LOW: (True, LOW) — auto-approve silently
            - MEDIUM: (True, MEDIUM) — log + auto-approve
            - HIGH: (False, HIGH) — block, requires approval
            - CRITICAL: (False, CRITICAL) — block, requires approval + audit
        """
        risk_level = self.get_risk_level(action)

        if risk_level == RiskLevel.LOW:
            return True, risk_level

        if risk_level == RiskLevel.MEDIUM:
            logger.info(
                "Auto-approving medium-risk action: %s",
                action,
            )
            return True, risk_level

        # HIGH and CRITICAL require human approval.
        logger.info(
            "Blocking %s-risk action for approval: %s",
            risk_level.value,
            action,
        )
        return False, risk_level
