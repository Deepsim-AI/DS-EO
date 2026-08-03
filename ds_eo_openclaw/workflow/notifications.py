"""Auto-mode state notifications per EXECUTION_MODE_ARCHITECTURE.md §6.3.

Maps workflow states to user-facing notification messages for automatic mode.
All notification text matches §6.3 exactly (word-for-word).

Usage:
    from ds_eo_openclaw.workflow.notifications import AUTO_MODE_NOTIFICATIONS, MODE_NOTIFICATIONS

    # Look up state notification
    msg = AUTO_MODE_NOTIFICATIONS.get("G1_WAITING")
    # → "Plan submitted for review"

    # Look up mode switch notification
    msg = MODE_NOTIFICATIONS.get(("manual", "automatic"))
    # → "Auto mode enabled — PM will auto-advance eligible transitions"
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


def get_mode_switch_notification(from_mode: str, to_mode: str) -> str | None:
    """Return the notification message for a mode switch, or None if not defined."""
    return MODE_NOTIFICATIONS.get((from_mode, to_mode))


def get_auto_mode_notification(state_id: str) -> str | None:
    """Return the notification message for an auto-mode state entry, or None."""
    return AUTO_MODE_NOTIFICATIONS.get(state_id)
