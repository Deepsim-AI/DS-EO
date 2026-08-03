# DS-EO Workflow Module — Execution Mode Architecture
#
# Public API across all phases:
#   Phase 1 (State Machine): StateEngine, State
#   Phase 2 (Audit Trail): AuditLog, AuditEntry, ProjectAuditIndex
#   Phase 3 (Mode Selector): WorkflowConfig, ModeSelector, AUTO_MODE_NOTIFICATIONS

from .state_engine import StateEngine, State
from .audit_log import AuditLog, AuditEntry, ProjectAuditIndex
from .config import WorkflowConfig, DEFAULT_CONFIG
from .selector import ModeSelector, create_selector
from .notifications import (
    AUTO_MODE_NOTIFICATIONS,
    MODE_NOTIFICATIONS,
    get_mode_switch_notification,
    get_auto_mode_notification,
)

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
]
