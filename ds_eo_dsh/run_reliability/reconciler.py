# TASK_DS_EO_040 — Run State Reconciliation Module
#
# Core module for detecting and classifying run-state desync between:
#   - Runtime engine state (what OpenClaw's engine actually thinks is running)
#   - Control-plane state (what TUI / command dispatch sees)
#
# Boundary classification (see BOUNDARY_ANALYSIS.md):
#   - Fully DS-EO-only: N1-2 (lifecycle states), N1-3 (error classification), N1-6 (orphan detection)
#   - Hybrid (DS-EO protocol + upstream stubs): N1-1, N1-4, N1-5, N1-7
#
# Design principle: DS-EO never writes to OpenClaw internal state. It only reads and classifies.
# When a mismatch is detected, it produces instructions — not direct fixes.

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RunState(Enum):
    """Authoritative run lifecycle states per CTO_PLAN.md §4."""
    IDLE = "idle"
    STARTING = "starting"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
    TIMEOUT = "timeout"
    ORPHAN_DETECTED = "orphan_detected"


class ErrorClassification(Enum):
    """Structured error codes per CTO_PLAN.md §3, N1-3."""
    RUN_STATE_MISMATCH = "RUN_STATE_MISMATCH"
    ORPHANED_RUN = "ORPHANED_RUN"
    COMPACTION_ABORT_FAILURE = "COMPACTION_ABORT_FAILURE"
    ABORT_DURING_FINALIZATION = "ABORT_DURING_FINALIZATION"
    INVALID_RUN_ID = "INVALID_RUN_ID"
    RETRYABLE_ERROR = "RETRYABLE_ERROR"
    IRRECOVERABLE_ERROR = "IRRECOVERABLE_ERROR"
    UNKNOWN = "UNKNOWN"


class Diagnosis(Enum):
    """Diagnosis results from state comparison per CTO_PLAN.md §5."""
    CONSISTENT = "CONSISTENT"
    ORPHANED_RUN = "ORPHANED_RUN"
    ENGINE_AHEAD = "ENGINE_AHEAD"
    TIMEOUT_IN_PROGRESS = "TIMEOUT_IN_PROGRESS"
    INVALID_RUN_ID = "INVALID_RUN_ID"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RunStateReport:
    """Result of checking run state consistency."""
    diagnosis: Diagnosis
    runtime_state: Optional[RunState]
    control_plane_state: Optional[str]  # "active", "idle", or None
    active_run_id: Optional[str]
    error_classification: Optional[ErrorClassification] = None
    recovery_action: Optional[str] = None  # human-readable action suggestion

    @property
    def is_consistent(self) -> bool:
        return self.diagnosis == Diagnosis.CONSISTENT


@dataclass
class OrphanedRunInfo:
    """Information about a detected orphaned run."""
    session_id: str
    stale_run_id: Optional[str]
    control_plane_active: bool
    runtime_has_process: bool
    last_seen_timestamp: Optional[float] = None  # Unix timestamp


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def check_run_state(
    runtime_state: RunState,
    control_plane_state: str,
    active_run_id: Optional[str] = None,
) -> RunStateReport:
    """
    Compare runtime engine state against control-plane state.

    This is the primary reconciliation entry point. It returns a diagnosis
    of whether the two sources are consistent and what recovery action (if any)
    is needed.

    Args:
        runtime_state: What the run engine actually reports (or None if unknown).
        control_plane_state: "active", "idle", or None for the control plane's view.
        active_run_id: The current run ID from the control plane, if any.

    Returns:
        RunStateReport with diagnosis and suggested recovery action.

    Examples:
        >>> check_run_state(RunState.IDLE, "idle")
        RunStateReport(diagnosis=Diagnosis.CONSISTENT, ...)

        >>> check_run_state(RunState.IDLE, "active", active_run_id="run-123")
        RunStateReport(diagnosis=Diagnosis.ORPHANED_RUN, ...)
    """
    # Case 1: Both idle — consistent
    if runtime_state == RunState.IDLE and control_plane_state == "idle":
        return RunStateReport(
            diagnosis=Diagnosis.CONSISTENT,
            runtime_state=runtime_state,
            control_plane_state=control_plane_state,
            active_run_id=None,
        )

    # Case 2: Runtime idle but control plane says active — ORPHANED_RUN
    if runtime_state == RunState.IDLE and control_plane_state == "active":
        return _build_orphaned_report(active_run_id)

    # Case 3: Runtime active but control plane says idle — ENGINE_AHEAD
    if runtime_state == RunState.ACTIVE and control_plane_state == "idle":
        return RunStateReport(
            diagnosis=Diagnosis.ENGINE_AHEAD,
            runtime_state=runtime_state,
            control_plane_state=control_plane_state,
            active_run_id=None,
            error_classification=ErrorClassification.RETRYABLE_ERROR,
            recovery_action="Sync control plane forward to ACTIVE state. No data loss risk.",
        )

    # Case 4: Both active — consistent (may have stale run-id)
    if runtime_state == RunState.ACTIVE and control_plane_state == "active":
        return RunStateReport(
            diagnosis=Diagnosis.CONSISTENT,
            runtime_state=runtime_state,
            control_plane_state=control_plane_state,
            active_run_id=active_run_id,
        )

    # Case 5: Starting state — check for timeout
    if runtime_state == RunState.STARTING and control_plane_state == "active":
        return _build_timeout_in_progress_report(active_run_id)

    # Case 6: Runtime completed/failed but control plane still active
    if runtime_state in (RunState.COMPLETED, RunState.FAILED) and control_plane_state == "active":
        return _build_orphaned_report(active_run_id)

    # Case 7: Runtime aborted — check for stale state
    if runtime_state == RunState.ABORTED and control_plane_state == "active":
        return _build_orphaned_report(
            active_run_id,
            error_classification=ErrorClassification.ORPHANED_RUN,
            recovery_action="Abort left stale state. Clear control-plane run-id to IDLE.",
        )

    # Case 8: Any other combination — classify as unknown mismatch
    return RunStateReport(
        diagnosis=Diagnosis.INVALID_RUN_ID,
        runtime_state=runtime_state,
        control_plane_state=control_plane_state,
        active_run_id=active_run_id,
        error_classification=ErrorClassification.RUN_STATE_MISMATCH,
        recovery_action="Unknown state combination. Reset control plane to IDLE and start fresh.",
    )


def reconcile_states(report: RunStateReport) -> str:
    """
    Given a RunStateReport from check_run_state(), return the recommended action.

    This is the reconciliation decision function. It translates diagnosis into
    concrete steps for agents to execute.

    Args:
        report: Output from check_run_state().

    Returns:
        A string describing the recommended recovery action, or None if no action needed.
    """
    if report.diagnosis == Diagnosis.CONSISTENT:
        return "No action needed — states are consistent."

    # Each diagnosis maps to a specific recovery path
    actions = {
        Diagnosis.ORPHANED_RUN: (
            "ORPHANED RUN DETECTED:\n"
            "  1. Clear the stale control-plane run-id\n"
            "  2. Transition control plane to IDLE state\n"
            "  3. If needed, issue /new to bootstrap a fresh session\n"
            "  Do NOT restart OpenClaw."
        ),
        Diagnosis.ENGINE_AHEAD: (
            "ENGINE AHEAD OF CONTROL PLANE:\n"
            "  1. Sync control plane forward — acknowledge the active run exists\n"
            "  2. Continue normal operation; no data loss risk"
        ),
        Diagnosis.TIMEOUT_IN_PROGRESS: (
            "RUN STARTING WITH TIMEOUT IN PROGRESS:\n"
            "  1. Wait up to 30 seconds for engine to complete STARTING → ACTIVE\n"
            "  2. If still starting after timeout, treat as ORPHANED_RUN and recover"
        ),
        Diagnosis.INVALID_RUN_ID: (
            "INVALID RUN ID:\n"
            "  1. Clear stale control-plane state\n"
            "  2. Transition to IDLE\n"
            "  3. Issue /new for a clean bootstrap"
        ),
    }

    return actions.get(report.diagnosis, "Unknown diagnosis — manual intervention required.")


def classify_error(
    raw_message: str,
    runtime_state: Optional[RunState] = None,
    control_plane_active: bool = False,
) -> ErrorClassification:
    """
    Map a raw error message to a structured ErrorClassification.

    This is the DS-EO-only error interceptor (N1-3). It uses pattern matching
    against known error signatures and state context to produce categorized errors.

    Args:
        raw_message: The raw error string from OpenClaw or agent output.
        runtime_state: Current runtime state if known (None = unknown).
        control_plane_active: Whether the control plane reports an active run.

    Returns:
        ErrorClassification enum value for the classified error.

    Examples:
        >>> classify_error("no active run", RunState.IDLE, False)
        <ErrorClassification.RUN_STATE_MISMATCH: 'RUN_STATE_MISMATCH'>

        >>> classify_error("Agent reply is already finalizing", None, True)
        <ErrorClassification.ABORT_DURING_FINALIZATION: ...>
    """
    msg_lower = raw_message.lower().strip()

    # Pattern-based classification — order matters (most specific first)
    if "no active run" in msg_lower and control_plane_active:
        return ErrorClassification.RUN_STATE_MISMATCH

    if "orphaned" in msg_lower or "stale run" in msg_lower:
        return ErrorClassification.ORPHANED_RUN

    # Compaction-related failures
    if any(kw in msg_lower for kw in ("compaction", "context overflow", "prompt too large")):
        if "abort" in msg_lower or "finalizing" in msg_lower:
            return ErrorClassification.COMPACTION_ABORT_FAILURE
        return ErrorClassification.COMPACTION_ABORT_FAILURE

    # Abort-related errors
    if "agent reply is already finalizing" in msg_lower and control_plane_active:
        return ErrorClassification.ABORT_DURING_FINALIZATION

    if "abort" in msg_lower and ("fail" in msg_lower or "error" in msg_lower):
        if runtime_state == RunState.IDLE:
            return ErrorClassification.RUN_STATE_MISMATCH
        return ErrorClassification.RETRYABLE_ERROR

    # Invalid run ID
    if "invalid run id" in msg_lower or "unknown run" in msg_lower:
        return ErrorClassification.INVALID_RUN_ID

    # Generic unknown error — check state context for hints
    if raw_message.strip() == "":
        return ErrorClassification.UNKNOWN

    if runtime_state is None and control_plane_active:
        return ErrorClassification.RUN_STATE_MISMATCH

    # Default: classify as retryable unless it looks fatal
    fatal_keywords = ("irrecoverable", "fatal", "corrupt state", "data loss")
    if any(kw in msg_lower for kw in fatal_keywords):
        return ErrorClassification.IRRECOVERABLE_ERROR

    return ErrorClassification.RETRYABLE_ERROR


def detect_orphaned_runs(
    sessions_active: list,
    runtime_has_run: bool = False,
) -> list[OrphanedRunInfo]:
    """
    Detect orphaned/stale runs where the control plane says active but
    the runtime has no corresponding process.

    This is the DS-EO-only orphan detector (N1-6). It uses available APIs
    (sessions_list with active filter) to probe engine state without
    requiring upstream API changes.

    Args:
        sessions_active: List of session dicts from sessions_list(activeMinutes=1) or similar,
                        each containing at minimum 'id' and optionally 'runId'.
        runtime_has_run: Whether the runtime engine reports having an active run.
                         In production this comes from gateway tools; for testing, pass True/False.

    Returns:
        List of OrphanedRunInfo for each detected orphaned session. Empty if no orphans found.

    Examples:
        >>> detect_orphaned_runs([], runtime_has_run=False)
        []

        >>> detect_orphaned_runs([{"id": "sess-1"}], runtime_has_run=False)
        [OrphanedRunInfo(session_id='sess-1', ...)]
    """
    orphans = []

    for session in sessions_active:
        session_id = session.get("id", "")
        run_id = session.get("runId") or session.get("active_run_id")

        # A session is orphaned if control plane lists it as active but runtime has no process
        if not runtime_has_run and (session_id or run_id):
            orphans.append(OrphanedRunInfo(
                session_id=session_id,
                stale_run_id=run_id,
                control_plane_active=True,
                runtime_has_process=False,
            ))

    return orphans


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_orphaned_report(
    active_run_id: Optional[str],
    error_classification: ErrorClassification = ErrorClassification.ORPHANED_RUN,
    recovery_action: str | None = None,
) -> RunStateReport:
    """Build a report for the ORPHANED_RUN diagnosis."""
    if recovery_action is None:
        recovery_action = "Clear stale control-plane run-id. Transition to IDLE. Issue /new if needed."

    return RunStateReport(
        diagnosis=Diagnosis.ORPHANED_RUN,
        runtime_state=RunState.IDLE,
        control_plane_state="active",
        active_run_id=active_run_id,
        error_classification=error_classification,
        recovery_action=recovery_action,
    )


def _build_timeout_in_progress_report(active_run_id: Optional[str]) -> RunStateReport:
    """Build a report for the TIMEOUT_IN_PROGRESS diagnosis."""
    return RunStateReport(
        diagnosis=Diagnosis.TIMEOUT_IN_PROGRESS,
        runtime_state=RunState.STARTING,
        control_plane_state="active",
        active_run_id=active_run_id,
        error_classification=ErrorClassification.RETRYABLE_ERROR,
        recovery_action=(
            "Wait up to 30s for STARTING→ACTIVE. If timeout exceeded, treat as ORPHANED_RUN."
        ),
    )
