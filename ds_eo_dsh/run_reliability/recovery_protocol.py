# TASK_DS_EO_040 — Recovery Protocol Module
#
# Agent-facing recovery procedures for each failure mode.
# This is the DS-EO protocol layer for hybrid requirements (N1-1, N1-4, N1-5, N1-7).
# Works with available APIs; upstream dependencies are stubbed as TODO items.

from dataclasses import dataclass, field
from enum import Enum


class RecoveryAction(Enum):
    """Recovery actions agents can take."""
    CLEAR_STALE_STATE = "clear_stale_state"
    RESET_CONTROL_PLANE = "reset_control_plane"
    NEW_SESSION = "new_session"
    WAIT_FOR_ENGINE = "wait_for_engine"
    MANUAL_INTERVENTION = "manual_intervention"


@dataclass
class RecoveryStep:
    """A single step in a recovery procedure."""
    order: int
    action: str
    rationale: str
    command: str | None = None  # OpenClaw CLI/Gateway command if applicable


@dataclass
class RecoveryProcedure:
    """Complete recovery procedure for a specific failure mode."""
    name: str
    diagnosis: str
    steps: list[RecoveryStep]
    is_automated: bool
    upstream_dependency: str | None = None  # If this requires an upstream patch


# ---------------------------------------------------------------------------
# Recovery procedures by failure mode
# ---------------------------------------------------------------------------

RECOVERY_PROCEDURES = {
    "orphaned_run": RecoveryProcedure(
        name="Orphaned Run Cleanup",
        diagnosis=(
            "Runtime engine has no active run, but control plane still shows an active session. "
            "This is the 'impossible state' — neither side will advance without external intervention."
        ),
        steps=[
            RecoveryStep(1, "Clear stale control-plane run-id",
                        "Remove the orphaned reference so the control plane can accept a new run.",
                        "/new"),
            RecoveryStep(2, "Verify clean state",
                        "Confirm no active runs remain in either runtime or control plane.",
                        None),  # Use sessions_list to verify
            RecoveryStep(3, "Bootstrap fresh session if needed",
                        "If the stale run was blocking new work, issue /new now.",
                        "/new"),
        ],
        is_automated=False,
    ),
    "engine_ahead": RecoveryProcedure(
        name="Engine-Ahead Sync",
        diagnosis=(
            "Runtime engine shows an active run but control plane reports idle. "
            "The control plane hasn't caught up with engine reality."
        ),
        steps=[
            RecoveryStep(1, "Acknowledge active run exists",
                        "Update the control plane to recognize the running session.",
                        None),  # Will be automated once upstream API U1 lands
            RecoveryStep(2, "Continue normal operation",
                        "No data loss risk — just sync state forward.",
                        None),
        ],
        is_automated=False,
        upstream_dependency="U1: resolveActiveRunState() API in run-state module",
    ),
    "timeout_in_progress": RecoveryProcedure(
        name="Starting Timeout Handling",
        diagnosis=(
            "A run was started but the engine hasn't transitioned to ACTIVE within the expected timeout. "
            "Could be a slow startup or an actual failure."
        ),
        steps=[
            RecoveryStep(1, "Wait for completion (30s)",
                        "Give the engine time to complete STARTING → ACTIVE.",
                        None),  # Poll session_status periodically
            RecoveryStep(2, "Re-check state",
                        "If still in STARTING after timeout, treat as orphaned run.",
                        None),
        ],
        is_automated=True,
    ),
    "invalid_run_id": RecoveryProcedure(
        name="Invalid Run ID Cleanup",
        diagnosis=(
            "Control plane references a run ID that doesn't exist in the engine. "
            "Usually caused by stale state from a previous failed run."
        ),
        steps=[
            RecoveryStep(1, "Clear stale control-plane state",
                        "Remove the invalid run reference.",
                        "/new"),
            RecoveryStep(2, "Reset to IDLE",
                        "Ensure both runtime and control plane are in consistent idle state.",
                        None),  # Will be automated with upstream API U1
            RecoveryStep(3, "Start fresh",
                        "Issue /new for a clean bootstrap.",
                        "/new"),
        ],
        is_automated=False,
    ),
    "compaction_abort_failure": RecoveryProcedure(
        name="Compaction/Abort Failure Recovery",
        diagnosis=(
            "Auto-compaction failed (context overflow) and the abort flow didn't clean up properly. "
            "This compounds the desync problem — both compaction and abort left partial state."
        ),
        steps=[
            RecoveryStep(1, "Stop all activity on this session",
                        "Prevent further context pressure.",
                        None),  # Agent should not make more tool calls
            RecoveryStep(2, "Document what was completed before failure",
                        "Save in-progress work to the task directory.",
                        None),
            RecoveryStep(3, "Request user intervention for session reset",
                        "Ask the user to /compact or /reset this session.",
                        "/compact" if False else None),  # Session-level command
            RecoveryStep(4, "After reset: verify clean state",
                        "Confirm no orphaned runs remain before continuing.",
                        None),
        ],
        is_automated=False,
    ),
}


def get_recovery_steps(diagnosis_key: str) -> list[RecoveryStep] | None:
    """
    Get the recovery procedure steps for a specific diagnosis.

    Args:
        diagnosis_key: The failure mode key (e.g., "orphaned_run", "engine_ahead").

    Returns:
        List of RecoveryStep objects, or None if no recovery is defined.
    """
    proc = RECOVERY_PROCEDURES.get(diagnosis_key)
    return proc.steps if proc else None


def get_recovery_procedure(diagnosis_key: str):
    """Get the full RecoveryProcedure for a diagnosis key."""
    return RECOVERY_PROCEDURES.get(diagnosis_key)


def is_recoverable(diagnosis_key: str) -> bool:
    """
    Check whether a given failure mode has a defined recovery procedure.

    Args:
        diagnosis_key: The failure mode key.

    Returns:
        True if recovery is possible through DS-EO protocols, False otherwise.
    """
    return diagnosis_key in RECOVERY_PROCEDURES


def format_recovery_procedure(diagnosis_key: str) -> str | None:
    """Format a recovery procedure as a human-readable string."""
    proc = get_recovery_procedure(diagnosis_key)
    if not proc:
        return None

    lines = [
        f"=== {proc.name} ===",
        f"Diagnosis: {proc.diagnosis}",
        "",
        "Steps:",
    ]

    for step in proc.steps:
        cmd_prefix = f"\n  Command: `{step.command}`" if step.command else ""
        lines.append(f"  {step.order}. {step.action}{cmd_prefix}")
        lines.append(f"     Why: {step.rationale}")

    if proc.upstream_dependency:
        lines.append("")
        lines.append(f"[UPSTREAM DEPENDENCY] Requires: {proc.upstream_dependency}")

    return "\n".join(lines)
