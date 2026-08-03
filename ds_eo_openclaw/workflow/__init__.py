# DS-EO Workflow Module — Execution Mode Architecture
#
# Public API across all phases:
#   Phase 1 (State Machine): StateEngine, State
#   Phase 2 (Audit Trail): AuditLog, AuditEntry, ProjectAuditIndex
#   Phase 3 (Mode Selector): WorkflowConfig, ModeSelector, AUTO_MODE_NOTIFICATIONS
#   Phase 4 (Failure/Stall Handling): TimeoutConfig, StallDetector, EscalationChain, FailureDetector

from .state_engine import StateEngine, State
from .audit_log import AuditLog, AuditEntry, ProjectAuditIndex
from .config import WorkflowConfig, DEFAULT_CONFIG
from .selector import ModeSelector, create_selector
from .notifications import (
    AUTO_MODE_NOTIFICATIONS,
    MODE_NOTIFICATIONS,
    FAILURE_NOTIFICATIONS,
    get_mode_switch_notification,
    get_auto_mode_notification,
    get_failure_notification,
)
from .timeout_config import TimeoutConfig, DEFAULT_TIMEOUT_CONFIG
from .stall_detection import StallDetector, create_stall_detector
from .escalation import EscalationChain, create_escalation_chain
from .failure_detector import FailureDetector, create_failure_detector

__all__ = [
    # Phase 1 — State Machine
    "StateEngine", "State",
    # Phase 2 — Audit Trail
    "AuditLog", "AuditEntry", "ProjectAuditIndex",
    # Phase 3 — Mode Selector + Notifications
    "WorkflowConfig", "DEFAULT_CONFIG",
    "ModeSelector", "create_selector",
    "AUTO_MODE_NOTIFICATIONS", "MODE_NOTIFICATIONS",
    "get_mode_switch_notification", "get_auto_mode_notification",
    # Phase 4 — Failure/Stall Handling
    "FAILURE_NOTIFICATIONS", "get_failure_notification",
    "TimeoutConfig", "DEFAULT_TIMEOUT_CONFIG",
    "StallDetector", "create_stall_detector",
    "EscalationChain", "create_escalation_chain",
    "FailureDetector", "create_failure_detector",
]
