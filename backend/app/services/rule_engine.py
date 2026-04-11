"""
Monolith ``services.rule_engine`` compatibility — re-exports ``app.core.pipeline_rules``.

Import from ``app.services.rule_engine`` or ``app.core.pipeline_rules`` (same symbols).
"""

from __future__ import annotations

from app.core.pipeline_rules import (
    CALL_STATUS_INTERESTED_BUCKET,
    CALL_STATUS_NO_RESPONSE_BUCKET,
    CALL_STATUS_NOT_INTERESTED_BUCKET,
    CALL_STATUS_VALUES,
    CLAIM_GATE_EXIT_STATUSES,
    PIPELINE_AUTO_EXPIRE_STATUSES,
    SLA_SOFT_WATCH_EXCLUDE,
    STATUS_FLOW_ORDER,
    STATUS_TO_STAGE,
    STAGE_TO_DEFAULT_STATUS,
    TEAM_ALLOWED_STATUSES,
    TEAM_CALL_STATUS_VALUES,
    TEAM_FORBIDDEN_STATUSES,
    TRACKS,
    is_valid_forward_status_transition,
    normalize_flow_status,
    validate_lead_business_rules,
)

__all__ = [
    "CALL_STATUS_INTERESTED_BUCKET",
    "CALL_STATUS_NO_RESPONSE_BUCKET",
    "CALL_STATUS_NOT_INTERESTED_BUCKET",
    "CALL_STATUS_VALUES",
    "CLAIM_GATE_EXIT_STATUSES",
    "PIPELINE_AUTO_EXPIRE_STATUSES",
    "SLA_SOFT_WATCH_EXCLUDE",
    "STATUS_FLOW_ORDER",
    "STATUS_TO_STAGE",
    "STAGE_TO_DEFAULT_STATUS",
    "TEAM_ALLOWED_STATUSES",
    "TEAM_CALL_STATUS_VALUES",
    "TEAM_FORBIDDEN_STATUSES",
    "TRACKS",
    "is_valid_forward_status_transition",
    "normalize_flow_status",
    "validate_lead_business_rules",
]
