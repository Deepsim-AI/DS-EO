# DS-EO Run Reliability Module
#
# Provides run-state reconciliation, orphaned-run detection, and structured error classification.
# This is the N1 (Run Execution Reliability) implementation layer for TASK_DS_EO_040.
#
# Boundary classification per BOUNDARY_ANALYSIS.md:
#   - N1-2 (Explicit Lifecycle States): DS-EO-only — protocol spec + state model enforcement
#   - N1-3 (Structured Error Classification): DS-EO-only — error interceptor using pattern matching
#   - N1-6 (Orphan Detection): DS-EO-only — detectable via available APIs
#   - N1-1, N1-4, N1-5, N1-7: Hybrid — DS-EO protocol layer + upstream API stubs

from .reconciler import (
    RunState,
    ErrorClassification,
    check_run_state,
    reconcile_states,
    classify_error,
    detect_orphaned_runs,
)
from .error_mapper import (
    ERROR_PATTERNS,
    map_raw_message_to_classification,
    format_structured_error,
)
from .recovery_protocol import (
    RecoveryAction,
    get_recovery_steps,
    is_recoverable,
)

__all__ = [
    # Core reconciler
    "RunState", "ErrorClassification",
    "check_run_state", "reconcile_states",
    "classify_error", "detect_orphaned_runs",
    # Error mapper
    "ERROR_PATTERNS", "map_raw_message_to_classification", "format_structured_error",
    # Recovery protocol
    "RecoveryAction", "get_recovery_steps", "is_recoverable",
]
