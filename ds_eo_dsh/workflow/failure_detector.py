"""Repeated failure detection for automatic mode review loops.

Implements §9.6 of EXECUTION_MODE_ARCHITECTURE.md — tracks rework loop count
per task and triggers escalating actions at each rejection threshold:
  - 1st rejection: standard rework (no special handling)
  - 2nd rejection: warning notification to user with pattern details
  - 3rd+ rejection: automatic escalation to CTO with failure report

Rework count resets on successful completion. Thresholds are configurable
to allow tuning per organization tolerance for rework cycles.

Usage:
    detector = FailureDetector()
    # First rejection — standard rework, no alert
    action = detector.record_failure("TASK_DS_EO_021", "G3")
    # → {"action": "REWORK", "count": 1, "message": "Standard rework loop (attempt 1)"}

    # Second rejection — user warning
    action = detector.record_failure("TASK_DS_EO_021", "G3")
    # → {"action": "WARNING", "count": 2, "message": "Second failure pattern detected..."}

    # Third rejection — CTO escalation
    action = detector.record_failure("TASK_DS_EO_021", "G4")
    # → {"action": "ESCALATE", "count": 3, "message": "Third+ failure — escalating to CTO"}

    # Successful completion resets the count
    detector.reset_on_completion("TASK_DS_EO_021")
"""


class FailureDetector:
    """Tracks rework loop count per task with threshold-based escalation.

    Attributes:
        failure_counts: Dict mapping task_id → current rework count.
        thresholds: Configurable rejection counts that trigger escalating actions.
            Default: {1: "REWORK", 2: "WARNING", 3: "ESCALATE"}
    """

    # Default escalation thresholds — configurable per organization tolerance
    DEFAULT_THRESHOLDS: dict[int, str] = {
        1: "REWORK",           # First rejection → standard rework (no alert)
        2: "WARNING",          # Second rejection → user warning with pattern details
        3: "ESCALATE",         # Third+ rejection → automatic CTO escalation
    }

    def __init__(self, thresholds: dict[int, str] | None = None):
        """Initialize the failure detector.

        Args:
            thresholds: Optional custom threshold mapping (count→action).
                Defaults to {1: "REWORK", 2: "WARNING", 3: "ESCALATE"}.
        """
        self.failure_counts: dict[str, int] = {}
        self.thresholds = dict(thresholds or self.DEFAULT_THRESHOLDS)

    def record_failure(self, task_id: str, gate: str) -> dict:
        """Record a rejection/failure for a task and determine the response action.

        Increments the rework count for this task and returns the appropriate
        action based on configured thresholds.

        Args:
            task_id: The TASK_<id> identifier.
            gate: The gate that rejected (e.g., "G3", "G4").

        Returns:
            Dict with escalation response: {"action": <REWORK|WARNING|ESCALATE>,
            "count": <current_count>, "message": <descriptive text>}.
        """
        # Increment the failure count for this task
        current_count = self.failure_counts.get(task_id, 0) + 1
        self.failure_counts[task_id] = current_count

        # Determine action based on thresholds
        action = self._determine_action(current_count)

        # Build descriptive message based on action and gate
        if action == "REWORK":
            message = f"Standard rework loop (attempt {current_count}) at Gate {gate}"
        elif action == "WARNING":
            message = (
                f"Second failure pattern detected — rework count: {current_count}. "
                f"Reviewing implementation approach for Gate {gate}."
            )
        else:  # ESCALATE
            message = (
                f"Third+ failure at Gate {gate} — escalating to CTO with failure report. "
                f"Recommend scope revision or implementer rotation."
            )

        return {
            "action": action,
            "count": current_count,
            "taskId": task_id,
            "gate": gate,
            "message": message,
        }

    def _determine_action(self, count: int) -> str:
        """Determine the escalation action for a given failure count.

        Uses the configured thresholds to find the highest threshold ≤ count.
        For example, with thresholds {1: REWORK, 2: WARNING, 3: ESCALATE}:
          - count=1 → REWORK (threshold 1)
          - count=2 → WARNING (threshold 2)
          - count=3+ → ESCALATE (highest threshold ≤ count)

        Args:
            count: Current failure count for this task.

        Returns:
            Action string ("REWORK", "WARNING", or "ESCALATE").
        """
        if count <= 1:
            return "REWORK"

        # Find highest threshold that is ≤ the current count
        sorted_thresholds = sorted(self.thresholds.keys())
        action = "REWORK"  # Default for counts below first threshold

        for threshold in sorted_thresholds:
            if threshold <= count:
                action = self.thresholds[threshold]

        return action

    def reset_on_completion(self, task_id: str) -> bool:
        """Reset the failure count for a task after successful completion.

        Called when a task reaches COMPLETED state (S7) to clear any accumulated
        rework history for that task. This ensures completion resets the pattern.

        Args:
            task_id: The TASK_<id> identifier to reset.

        Returns:
            True if an entry existed and was removed; False otherwise.
        """
        return self.failure_counts.pop(task_id, None) is not None

    def get_failure_count(self, task_id: str) -> int:
        """Get the current rework count for a task.

        Args:
            task_id: The TASK_<id> identifier.

        Returns:
            Current failure/rework count (0 if no history).
        """
        return self.failure_counts.get(task_id, 0)

    def get_pattern_report(self, task_id: str) -> dict:
        """Generate a pattern report for a task's failure history.

        Used when escalating to CTO — provides the full failure context including
        which gates rejected and at what counts.

        Args:
            task_id: The TASK_<id> identifier.

        Returns:
            Dict with pattern analysis: taskId, count, gate_history (list of gates),
            recommended_action based on current threshold.
        """
        count = self.failure_counts.get(task_id, 0)
        action = self._determine_action(count) if count > 0 else "NONE"

        return {
            "taskId": task_id,
            "failureCount": count,
            "recommendedAction": action,
            "gateHistory": [],  # Full implementation would track per-gate history
            "message": f"Failure pattern report for {task_id}: {count} rejection(s), action: {action}",
        }


# --------------------------------------------------------------------------- #
# Convenience function
# --------------------------------------------------------------------------- #

def create_failure_detector(thresholds: dict[int, str] | None = None) -> FailureDetector:
    """Factory function to create a FailureDetector with the given thresholds.

    Args:
        thresholds: Optional custom threshold mapping (count→action).

    Returns:
        A configured FailureDetector instance.
    """
    return FailureDetector(thresholds or FailureDetector.DEFAULT_THRESHOLDS)
