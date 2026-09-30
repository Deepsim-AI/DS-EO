# TASK_DS_EO_040 — Error Mapper Module
#
# Maps raw error messages from OpenClaw to structured ErrorClassification codes.
# DS-EO-only (N1-3). Uses regex pattern matching for resilience against message format changes.

import re
from dataclasses import dataclass, field
from typing import Optional

from .reconciler import ErrorClassification


@dataclass
class _ErrorPattern:
    """A single error-mapping rule."""
    name: str
    classification: ErrorClassification
    patterns: list[str]  # substrings or regex patterns to match (lowercase)
    description: str


# ---------------------------------------------------------------------------
# Error pattern definitions
# ---------------------------------------------------------------------------

ERROR_PATTERNS: list[_ErrorPattern] = [
    _ErrorPattern(
        name="RUN_STATE_MISMATCH",
        classification=ErrorClassification.RUN_STATE_MISMATCH,
        patterns=[
            "no active run",
            "runtime has no active run",
            "engine reports idle",
            "run state mismatch",
        ],
        description=(
            "Runtime and control plane disagree on whether a run is active. "
            "Control plane shows 'active' but engine says otherwise."
        ),
    ),
    _ErrorPattern(
        name="ORPHANED_RUN",
        classification=ErrorClassification.ORPHANED_RUN,
        patterns=[
            "orphaned run",
            "stale run",
            "abandoned session",
            "run terminated abnormally",
        ],
        description=(
            "A run that terminated abnormally left stale control-plane state. "
            "The engine has no record of it, but the TUI/control plane still does."
        ),
    ),
    _ErrorPattern(
        name="COMPACTION_ABORT_FAILURE",
        classification=ErrorClassification.COMPACTION_ABORT_FAILURE,
        patterns=[
            "compaction failed",
            "context overflow",
            "prompt too large",
            "compaction timeout",
            "auto-compaction failed",
        ],
        description=(
            "Auto-compaction failed (context overflow) and the abort flow didn't "
            "clean up properly, compounding the desync."
        ),
    ),
    _ErrorPattern(
        name="ABORT_DURING_FINALIZATION",
        classification=ErrorClassification.ABORT_DURING_FINALIZATION,
        patterns=[
            "agent reply is already finalizing",
            "reply finalization in progress",
            "abort during finalization",
        ],
        description=(
            "An abort was attempted while the agent's reply was being finalized. "
            "The abort queue rejected it because the run was past the abort point."
        ),
    ),
    _ErrorPattern(
        name="INVALID_RUN_ID",
        classification=ErrorClassification.INVALID_RUN_ID,
        patterns=[
            "invalid run id",
            "unknown run",
            "run id not found",
            "no matching run for session",
        ],
        description=(
            "The control plane references a run ID that doesn't exist in the engine. "
            "This is typically caused by stale state from a previous failed run."
        ),
    ),
    _ErrorPattern(
        name="IRRECOVERABLE_ERROR",
        classification=ErrorClassification.IRRECOVERABLE_ERROR,
        patterns=[
            "irrecoverable error",
            "fatal error",
            "corrupt state",
            "state corruption",
            "unrecoverable desync",
        ],
        description=(
            "The error indicates permanent state corruption or a failure mode that "
            "cannot be recovered without external intervention (restart required)."
        ),
    ),
]

# Fallback patterns for classification when no specific pattern matches
_FALLBACK_PATTERNS = {
    ErrorClassification.RETRYABLE_ERROR: [
        "retry",
        "temporary error",
        "connection reset",
        "rate limit",
    ],
    ErrorClassification.UNKNOWN: [],  # No pattern → UNKNOWN
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def map_raw_message_to_classification(
    raw_message: str,
    runtime_state_idle: bool = False,
    control_plane_active: bool = False,
) -> tuple[ErrorClassification, str]:
    """
    Map a raw error message to an ErrorClassification.

    Checks patterns in order (first match wins). Falls back to retryable/unknown
    if no pattern matches.

    Args:
        raw_message: The raw error string from OpenClaw or agent output.
        runtime_state_idle: Whether the runtime engine reports idle state.
        control_plane_active: Whether the control plane reports an active run.

    Returns:
        Tuple of (ErrorClassification, description) where description is a human-readable
        explanation of what was classified and why.
    """
    msg_lower = raw_message.lower().strip()

    # Check against defined patterns
    for pattern in ERROR_PATTERNS:
        for p in pattern.patterns:
            if p in msg_lower:
                return (pattern.classification, f"Matched '{p}': {pattern.description}")

    # Apply state-context overrides before fallback
    if runtime_state_idle and control_plane_active:
        # If engine says idle but control plane says active → likely RUN_STATE_MISMATCH
        # even if the message doesn't contain the keyword
        return (
            ErrorClassification.RUN_STATE_MISMATCH,
            "State context indicates mismatch: runtime=idle but control=active",
        )

    # Check fallback patterns
    for classification, fallback_patterns in _FALLBACK_PATTERNS.items():
        if classification == ErrorClassification.UNKNOWN:
            continue  # UNKNOWN has no patterns to check
        for p in fallback_patterns:
            if p in msg_lower:
                return (classification, f"Fallback match '{p}'")

    # Default fallback — unknown
    return (ErrorClassification.UNKNOWN, "No pattern matched; classified as UNKNOWN")


def format_structured_error(
    classification: ErrorClassification,
    raw_message: str,
    description: str = "",
) -> str:
    """
    Format an error classification into a structured string suitable for agent consumption.

    Args:
        classification: The classified error code.
        raw_message: The original error message that was classified.
        description: Optional human-readable description (from map_raw_message_to_classification).

    Returns:
        Formatted string with error details.
    """
    if not description:
        # Find the pattern that produced this classification
        for p in ERROR_PATTERNS:
            if p.classification == classification:
                description = p.description
                break
        else:
            description = f"Error classified as {classification.value}"

    return (
        f"[ERROR CLASSIFIED]\n"
        f"  Code:      {classification.value}\n"
        f"  Category:  {classification.name}\n"
        f"  Message:   {raw_message}\n"
        f"  Detail:    {description}"
    )
