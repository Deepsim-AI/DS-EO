"""Auto-mode state notifications per EXECUTION_MODE_ARCHITECTURE.md §6.3.

Maps workflow states to user-facing notification messages for automatic mode.
All notification text matches §6.3 exactly (word-for-word).

Phase 4 additions: failure notification types for blocker, stalled, and
repeated failure escalation paths (§9.2–§9.6).

Usage:
    from ds_eo_openclaw.workflow.notifications import AUTO_MODE_NOTIFICATIONS, MODE_NOTIFICATIONS, FAILURE_NOTIFICATIONS

    # Look up state notification
    msg = AUTO_MODE_NOTIFICATIONS.get("G1_WAITING")
    # → "Plan submitted for review"

    # Look up failure notification (Phase 4)
    msg = FAILURE_NOTIFICATIONS.get("blocker_detected", {}).get("message")
"""


# --------------------------------------------------------------------------- #
# Auto-mode state notifications (§6.3)
# --------------------------------------------------------------------------- #

AUTO_MODE_NOTIFICATIONS: dict[str, str] = {
    "G1_WAITING": "Plan submitted for review",
    "REVIEW": "G2 passed automatically — Reviewer assigned",
    "G3_PENDING": "Review complete. Awaiting CTO G3 evaluation.",
    "COMPLETED": "Task completed, cleanup in progress",
    "CHANGES_REQD": "Changes requested: [reason] — rework required",
    "BLOCKED": "BLOCKER: [details]",
    "STALLED": "STALLED: last activity [timestamp], exceeded timeout",
}


# --------------------------------------------------------------------------- #
# Mode switch notifications (both directions)
# --------------------------------------------------------------------------- #

MODE_NOTIFICATIONS: dict[tuple[str, str], str] = {
    ("manual", "automatic"): "Auto mode enabled — PM will auto-advance eligible transitions",
    ("automatic", "manual"): "Mode switched to manual — all transitions require explicit action",
}

# Phase 4: Failure notification types (§9.2–§9.6)
FAILURE_NOTIFICATIONS = {
    "blocker_detected": {
        "message": "BLOCKER: [details]",
        "priority": "urgent",
    },
    "task_stalled": {
        "message": "STALLED: last activity [timestamp], exceeded timeout",
        "priority": "warning",
    },
    "repeated_failure_escalated": {
        "message": "Repeated failure pattern detected — escalating to CTO with report",
        "priority": "high",
    },
}


def get_mode_switch_notification(from_mode: str, to_mode: str) -> str | None:
    """Return the notification message for a mode switch, or None if not defined."""
    return MODE_NOTIFICATIONS.get((from_mode, to_mode))


def get_auto_mode_notification(state_id: str) -> str | None:
    """Return the notification message for an auto-mode state entry, or None."""
    return AUTO_MODE_NOTIFICATIONS.get(state_id)


def get_failure_notification(failure_type: str) -> dict | None:
    """Return the failure notification config (message + priority), or None.

    Phase 4 integration — looks up failure-type notifications for automatic mode.

    Args:
        failure_type: Failure category (blocker_detected, task_stalled,
            repeated_failure_escalated).

    Returns:
        Dict with 'message' and 'priority' keys, or None if type not found.
    """
    return FAILURE_NOTIFICATIONS.get(failure_type)
