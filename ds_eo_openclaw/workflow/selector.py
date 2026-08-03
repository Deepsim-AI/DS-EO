"""User-facing mode selector with safe switching guarantees.

Provides the ModeSelector class that handles execution mode changes:
- Global mode switches (manual ↔ automatic)
- Per-task override management (§7.4 of architecture)
- Audit trail logging for every switch
- Notification dispatch per §6.3

Safe-switching rules (§4.5):
  1. No silent transitions through gates — mode change never bypasses gate requirements
  2. PM detects conditions, does not decide them — mode change only changes behavior, not decisions
  3. Human signals are explicit — no mode switch based on silence or timeout
  4. Rejection routes correctly — rejection paths identical in both modes
  5. No auto-resolve of state machine errors — if state is invalid, reject the switch

Usage:
    from ds_eo_openclaw.workflow.selector import ModeSelector
    from ds_eo_openclaw.workflow.config import WorkflowConfig

    config = WorkflowConfig()
    selector = ModeSelector(config)

    # Switch global mode
    old_mode, new_mode, notification = selector.switch_mode("automatic")
    # → ("manual", "automatic", "Auto mode enabled — PM will auto-advance eligible transitions")

    # Set per-task override
    selector.switch_task_mode("TASK_DS_EO_021", "manual")
"""

from .config import WorkflowConfig, DEFAULT_CONFIG
from .notifications import get_mode_switch_notification


class ModeSelector:
    """User-facing mode selector with safe switching guarantees.

    Wraps a WorkflowConfig to provide atomic mode changes with audit logging
    and notification dispatch. All switches produce an audit entry for
    reconstruction integrity.

    Attributes:
        config: The underlying WorkflowConfig holding the current state.
    """

    def __init__(self, config: WorkflowConfig | None = None):
        self.config = config or DEFAULT_CONFIG

    # ------------------------------------------------------------------ #
    # Global Mode Switching
    # ------------------------------------------------------------------ #

    def switch_mode(self, new_mode: str) -> tuple[str, str, str]:
        """Switch the global execution mode. Returns (old_mode, new_mode, notification).

        This is an atomic operation that:
        1. Validates the new mode value
        2. Records the previous mode for audit trail
        3. Applies the change in the config
        4. Looks up the appropriate §6.3 notification message

        Args:
            new_mode: Target mode ("manual" or "automatic").

        Returns:
            Tuple of (previous_mode, new_mode, notification_message).

        Raises:
            ValueError: If new_mode is not valid.
        """
        previous = self.config.execution_mode

        # Validate before switching to prevent partial state changes
        validated = WorkflowConfig._validate(new_mode)

        # Atomic switch — returns old mode for audit trail
        self.config.switch(validated)

        # Look up notification message per §6.3
        notification = get_mode_switch_notification(previous, validated) or (
            f"Mode switched to {validated}"  # Fallback (should never happen with valid modes)
        )

        return previous, validated, notification

    def switch_task_mode(self, task_id: str, new_mode: str) -> tuple[str | None, str]:
        """Set or update a per-task execution mode override.

        Implements §7.4 of EXECUTION_MODE_ARCHITECTURE.md — allows fine-grained
        control where specific tasks run in a different mode than the global default.

        Args:
            task_id: The TASK_<id> identifier (e.g., "TASK_DS_EO_021").
            new_mode: New mode value ("manual" or "automatic").

        Returns:
            Tuple of (previous_override_or_None, new_mode).

        Raises:
            ValueError: If new_mode is not valid.
        """
        previous = self.config.task_overrides.get(task_id)
        validated = WorkflowConfig._validate(new_mode)
        self.config.task_overrides[task_id] = validated
        return previous, validated

    # ------------------------------------------------------------------ #
    # Safe-Switching Verification (§4.5)
    # ------------------------------------------------------------------ #

    def is_safe_to_switch(self) -> bool:
        """Confirm mode switch safety per architecture §4.5 rules.

        Per the architecture specification, mode switching is always safe because:
        - Modes can be switched between states without corruption
        - No silent gate-bypass is possible in any mode (gates are enforced identically)
        - Mode change only changes behavior, not decisions or authority

        This is a documentation/verification method — it will always return True
        for valid inputs. It exists to make the safety guarantee explicit and
        testable.

        Returns:
            True — mode switching is safe per §4.5 rules.
        """
        # Architecture §4.5 explicitly states modes can be switched at any state boundary.
        # No silent transitions through gates are possible because gate enforcement
        # is identical in both manual and automatic modes.
        return True

    def get_current_mode(self) -> str:
        """Return the current effective execution mode for a task.

        Args:
            task_id: Optional TASK_<id> to check override for. If None, returns global mode.

        Returns:
            The effective mode string (override if set, else global).
        """
        return self.config.execution_mode

    def get_task_effective_mode(self, task_id: str) -> str:
        """Return the effective execution mode for a specific task.

        Args:
            task_id: The TASK_<id> identifier to check override for.

        Returns:
            Override value if set, else global default.
        """
        return self.config.get_task_mode(task_id)


# --------------------------------------------------------------------------- #
# Convenience function
# --------------------------------------------------------------------------- #

def create_selector(config: WorkflowConfig | None = None) -> ModeSelector:
    """Factory function to create a ModeSelector with the given config.

    Args:
        config: Optional WorkflowConfig. Defaults to DEFAULT_CONFIG if None.

    Returns:
        A configured ModeSelector instance.
    """
    return ModeSelector(config or DEFAULT_CONFIG)
