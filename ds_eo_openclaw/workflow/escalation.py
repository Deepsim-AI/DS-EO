"""Blocker escalation chain for automatic mode failure handling.

Implements §9.2 of EXECUTION_MODE_ARCHITECTURE.md — when a blocker is detected,
the PM escalates through the chain: PM → CTO (immediate alert with context) → User
(if no resolution within timeout). Rate limiting prevents spam (max 1 escalation
per 5 minutes for the same blocker).

Usage:
    chain = EscalationChain()
    # First escalation: PM alerts CTO immediately
    result = chain.escalate("TASK_DS_EO_021", "Waiting on external API key")
    # → {"level": "CTO", "message": "CTO alerted with blocker details"}

    # Second attempt too soon (< 5 minutes): rate-limited, returns previous level
    result = chain.escalate("TASK_DS_EO_021", "Waiting on external API key")
    # → {"level": "CTO", "message": "Rate limited — last escalation < 5min ago"}

    # After timeout: escalates to User
    import time; time.sleep(301)  # simulate waiting
    result = chain.escalate("TASK_DS_EO_021", "Waiting on external API key")
    # → {"level": "USER", "message": "User escalated — CTO did not resolve"}

The escalation chain is task-scoped: each TASK_ID maintains its own rate limit
state. Completing a task resets the blocker state for that task.
"""

import time
from datetime import datetime, timezone


class EscalationChain:
    """Blocker escalation path with rate limiting.

    Manages the PM→CTO→User escalation chain for blocked tasks. Each task
    maintains its own escalation history to prevent spam and track progress.

    Attributes:
        escalation_history: Dict mapping task_id → last escalation info dict.
            Used for rate limiting and tracking escalation level.
        RATE_LIMIT_SECONDS: Minimum seconds between escalations for same blocker.
    """

    # Rate limit: max one escalation per 5 minutes for the same blocker
    RATE_LIMIT_SECONDS = 300  # 5 minutes

    def __init__(self):
        self.escalation_history: dict[str, dict] = {}

    def escalate(
        self,
        task_id: str,
        blocker_details: str | None = None,
        previous_level: str | None = None,
    ) -> dict:
        """Escalate a blocker to the next level in the chain.

        Applies rate limiting — if the last escalation for this task was within
        5 minutes, returns the current level without escalating further.

        Args:
            task_id: The TASK_<id> identifier.
            blocker_details: Description of the blocker (for audit trail).
            previous_level: Current escalation level. If None, uses the tracked
                history level (or defaults to "PM" for first-time escalations).

        Returns:
            Dict with escalation result: {"level": <new_level>, "message": <desc>}.
        """
        now = datetime.now(timezone.utc)
        history_entry = self.escalation_history.get(task_id, {})

        # Determine the effective previous level
        if previous_level is None:
            previous_level = history_entry.get("level", "PM")

        # Rate limiting check
        last_escalated_at = history_entry.get("lastEscalatedAt")
        if last_escalated_at is not None:
            elapsed = (now - last_escalated_at).total_seconds()
            if elapsed < self.RATE_LIMIT_SECONDS:
                return {
                    "level": previous_level,
                    "message": f"Rate limited — last escalation {int(elapsed)}s ago (< {self.RATE_LIMIT_SECONDS}s threshold)",
                    "taskId": task_id,
                    "blockerDetails": blocker_details,
                }

        # Determine next level in the chain
        if previous_level == "PM":
            new_level = "CTO"
            message = f"CTO alerted with blocker details for {task_id}"
        elif previous_level == "CTO":
            new_level = "USER"
            message = f"User escalated — CTO did not resolve within timeout for {task_id}"
        else:
            # Already at USER level — no further escalation possible
            return {
                "level": "USER",
                "message": f"Already at maximum escalation level (USER) for {task_id}",
                "taskId": task_id,
                "blockerDetails": blocker_details,
            }

        # Record the escalation in history
        self.escalation_history[task_id] = {
            "level": new_level,
            "lastEscalatedAt": now,
            "blockerDetails": blocker_details,
        }

        return {
            "level": new_level,
            "message": message,
            "taskId": task_id,
            "blockerDetails": blocker_details,
        }

    def get_current_level(self, task_id: str) -> str:
        """Get the current escalation level for a task.

        Args:
            task_id: The TASK_<id> identifier.

        Returns:
            Current level string ("PM", "CTO", or "USER"), or "PM" if no history.
        """
        entry = self.escalation_history.get(task_id)
        return entry["level"] if entry else "PM"

    def reset(self, task_id: str) -> bool:
        """Reset the escalation chain for a task (e.g., after resolution).

        Args:
            task_id: The TASK_<id> identifier to reset.

        Returns:
            True if an entry existed and was removed; False otherwise.
        """
        return self.escalation_history.pop(task_id, None) is not None

    def get_escalation_history(self, task_id: str) -> list[dict]:
        """Get the full escalation history for a task.

        Args:
            task_id: The TASK_<id> identifier.

        Returns:
            List of escalation dicts (most recent first). Empty if no history.
        """
        entry = self.escalation_history.get(task_id)
        if not entry:
            return []
        return [entry]  # Simplified — full implementation would accumulate history


# --------------------------------------------------------------------------- #
# Convenience function
# --------------------------------------------------------------------------- #

def create_escalation_chain() -> EscalationChain:
    """Factory function to create a new EscalationChain.

    Returns:
        A new EscalationChain instance with empty history.
    """
    return EscalationChain()
