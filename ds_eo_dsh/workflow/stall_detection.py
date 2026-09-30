"""Stall detection engine for PM monitoring cycle.

Implements §9.3 + §10.4 of EXECUTION_MODE_ARCHITECTURE.md — compares activity
timestamps against configured timeouts to detect stalled tasks. Human-owned
states are always exempt from stall detection regardless of elapsed time.

Usage:
    detector = StallDetector()  # uses DEFAULT_TIMEOUT_CONFIG
    result = detector.check("TASK_DS_EO_021", "IMPLEMENTATION", last_activity)
    if result is not None:
        print(f"Stalled! Elapsed {result['elapsedSeconds']}s > timeout {result['timeoutSeconds']}s")

The PM monitoring cycle calls check() per-state on each iteration. When a stall
is detected, the engine transitions to STALLED state (S10) with audit entry
and notification dispatch.
"""

from datetime import datetime, timezone
from .timeout_config import TimeoutConfig, DEFAULT_TIMEOUT_CONFIG


class StallDetector:
    """PM monitoring cycle stall detection engine.

    Compares last-activity timestamps against configured timeouts per state.
    Human-owned states (§6.1) are always exempt — they never trigger a stall
    alert regardless of elapsed time.

    Attributes:
        config: TimeoutConfig instance for timeout lookups. Defaults to global default.
    """

    def __init__(self, config: TimeoutConfig | None = None):
        self.config = config or DEFAULT_TIMEOUT_CONFIG

    def check(
        self,
        task_id: str,
        current_state: str,
        last_activity_time: datetime,
    ) -> dict | None:
        """Check if a task is stalled based on timeout configuration.

        Returns stall info dict if the task has exceeded its configured timeout,
        or None if not stalled (including exempt states and within-timeout states).

        Args:
            task_id: The TASK_<id> identifier.
            current_state: Current state name (e.g., "IMPLEMENTATION").
            last_activity_time: UTC datetime of the last activity on this task.

        Returns:
            Dict with stall details if stalled, or None if not stalled.
            Stall dict contains: taskId, currentState, elapsedSeconds,
            timeoutSeconds, lastActivityTimestamp.
        """
        # Human-owned states are always exempt from stall detection
        if self.config.is_exempt(current_state):
            return None

        timeout = self.config.get_timeout(current_state)
        if timeout is None:
            return None  # Should not happen — is_exempt already checked, but defensive

        now = datetime.now(timezone.utc)
        elapsed = (now - last_activity_time).total_seconds()

        if elapsed >= timeout:
            return {
                "taskId": task_id,
                "currentState": current_state,
                "elapsedSeconds": int(elapsed),
                "timeoutSeconds": timeout,
                "lastActivityTimestamp": last_activity_time.isoformat(),
            }
        return None

    def check_all_states(
        self,
        task_id: str,
        state_timestamps: dict[str, datetime],
    ) -> list[dict]:
        """Check all tracked states for stall conditions.

        Used by the PM monitoring cycle to scan a task's full history.

        Args:
            task_id: The TASK_<id> identifier.
            state_timestamps: Dict mapping state name → last activity datetime.

        Returns:
            List of stall info dicts (one per stalled state). Empty if none stalled.
        """
        stalls = []
        for state, timestamp in state_timestamps.items():
            result = self.check(task_id, state, timestamp)
            if result is not None:
                stalls.append(result)
        return stalls

    def is_stalled(
        self,
        task_id: str,
        current_state: str,
        last_activity_time: datetime,
    ) -> bool:
        """Quick boolean check — returns True if the task is stalled.

        Convenience wrapper around check() for simple stall queries.

        Args:
            task_id: The TASK_<id> identifier.
            current_state: Current state name.
            last_activity_time: UTC datetime of last activity.

        Returns:
            True if stalled, False otherwise (including exempt states).
        """
        return self.check(task_id, current_state, last_activity_time) is not None


# --------------------------------------------------------------------------- #
# Convenience function
# --------------------------------------------------------------------------- #

def create_stall_detector(config: TimeoutConfig | None = None) -> StallDetector:
    """Factory function to create a StallDetector with the given config.

    Args:
        config: Optional TimeoutConfig. Defaults to DEFAULT_TIMEOUT_CONFIG if None.

    Returns:
        A configured StallDetector instance.
    """
    return StallDetector(config or DEFAULT_TIMEOUT_CONFIG)
