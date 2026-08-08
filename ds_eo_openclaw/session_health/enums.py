"""
DS-EO Session Health — Enumerations (§5, §11)

Defines the health state model and lifecycle actions for session health
monitoring. All states are deterministic and non-overlapping.
"""

from enum import Enum, auto


class SessionHealthState(str, Enum):
    """Health classification for a single session."""
    HEALTHY = "HEALTHY"
    ACTIVE = "ACTIVE"
    STALE = "STALE"
    OVERSIZED = "OVERSIZED"
    STUCK = "STUCK"
    COMPACTION_REQUIRED = "COMPACTION_REQUIRED"
    COMPACTION_FAILED = "COMPACTION_FAILED"
    ERRORING = "ERRORING"
    ORPHANED = "ORPHANED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    UNKNOWN = "UNKNOWN"

    @property
    def is_critical(self) -> bool:
        """Returns True for states requiring immediate attention."""
        return self in (
            SessionHealthState.RECOVERY_REQUIRED,
            SessionHealthState.COMPACTION_FAILED,
            SessionHealthState.ERRORING,
        )

    @property
    def requires_action(self) -> bool:
        """True for any state other than HEALTHY or ACTIVE."""
        return self not in (SessionHealthState.HEALTHY, SessionHealthState.ACTIVE)


class LifecycleAction(str, Enum):
    """Possible lifecycle actions for an unhealthy session."""
    NO_ACTION = "NO_ACTION"
    WARN = "WARN"
    MONITOR = "MONITOR"
    COMPACT = "COMPACT"
    RETRY_COMPACTION = "RETRY_COMPACTION"
    MARK_STALE = "MARK_STALE"
    ARCHIVE = "ARCHIVE"
    CLOSE = "CLOSE"
    ESCALATE = "ESCALATE"

    @property
    def is_destructive(self) -> bool:
        """True for actions that may destroy session state."""
        return self in (self.ARCHIVE, self.CLOSE)

    @property
    def is_execution_action(self) -> bool:
        """True for actions that perform actual work (not just reporting)."""
        return self not in (LifecycleAction.NO_ACTION, LifecycleAction.WARN, LifecycleAction.MONITOR)


class MonitorStatus(str, Enum):
    """Overall monitoring mode."""
    OBSERVING = "OBSERVING"       # dry-run: report but don't execute
    ACTIVE = "ACTIVE"             # normal operation
    PAUSED = "PAUSED"             # manual override active

    @property
    def allows_execution(self) -> bool:
        """True when the monitor is allowed to perform actions."""
        return self == MonitorStatus.ACTIVE


class HealthSignal(str, Enum):
    """Individual health signal types collected by the Discoverer."""
    AGE_SECONDS = "AGE_SECONDS"
    INACTIVITY_SECONDS = "INACTIVITY_SECONDS"
    CONTEXT_SIZE_KB = "CONTEXT_SIZE_KB"
    COMPACTION_STATUS = "COMPACTION_STATUS"  # OK / FAILED / UNDETERMINED
    EXECUTION_STATE = "EXECUTION_STATE"      # RUNNING / STUCK / IDLE / UNKNOWN
    ERROR_COUNT = "ERROR_COUNT"
    TASK_ASSOCIATION = "TASK_ASSOCIATION"     # ACTIVE / INACTIVE / NONE
    RECOVERY_HISTORY = "RECOVERY_HISTORY"     # list of recent recovery events
