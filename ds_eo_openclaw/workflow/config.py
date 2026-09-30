"""Execution mode configuration management.

Provides the WorkflowConfig class that holds the global execution_mode
and optional per-task overrides. Used by ModeSelector and StateEngine
to determine which mode applies to a given task.

Usage:
    config = WorkflowConfig(execution_mode="automatic", task_overrides={"TASK_DS_EO_021": "manual"})
    mode = config.get_task_mode("TASK_DS_EO_021")  # → "manual" (override wins)
    mode = config.get_task_mode("OTHER_TASK")      # → "automatic" (global default)

Defaults:
    DEFAULT_CONFIG = WorkflowConfig()  # execution_mode="manual", no overrides
"""


class WorkflowConfig:
    """Global workflow configuration with optional per-task overrides.

    Attributes:
        execution_mode: Current global mode — "manual" or "automatic".
            Defaults to "manual" if unset or invalid (never silent fallback).
        task_overrides: Dict mapping TASK_ID → override mode string.
            Empty dict by default; populated via constructor or switch_task_mode().
    """

    VALID_MODES = ("manual", "automatic")

    def __init__(self, execution_mode: str = "manual", task_overrides: dict[str, str] | None = None):
        self.execution_mode = self._validate(execution_mode)
        self.task_overrides: dict[str, str] = dict(task_overrides or {})

    @staticmethod
    def _validate(mode: str) -> str:
        """Validate execution mode value. Raises ValueError for invalid input."""
        if mode not in WorkflowConfig.VALID_MODES:
            raise ValueError(
                f"Invalid execution_mode '{mode}'. Must be one of {WorkflowConfig.VALID_MODES}"
            )
        return mode

    def switch(self, new_mode: str) -> str:
        """Switch the global execution mode. Returns previous mode for audit trail.

        Args:
            new_mode: New mode value ("manual" or "automatic").

        Returns:
            The previous mode string before the change.

        Raises:
            ValueError: If new_mode is not valid.
        """
        old = self.execution_mode
        self.execution_mode = self._validate(new_mode)
        return old

    def get_task_mode(self, task_id: str) -> str:
        """Get the effective execution mode for a specific task.

        Per-task overrides take precedence over the global default.
        This implements §7.4 of EXECUTION_MODE_ARCHITECTURE.md.

        Args:
            task_id: The TASK_<id> identifier to look up.

        Returns:
            The effective mode string (override if set, else global).
        """
        return self.task_overrides.get(task_id, self.execution_mode)

    def set_task_override(self, task_id: str, mode: str) -> str | None:
        """Set or update a per-task execution mode override.

        Args:
            task_id: The TASK_<id> identifier.
            mode: New mode value ("manual" or "automatic").

        Returns:
            Previous override value if one existed, else None.

        Raises:
            ValueError: If mode is not valid.
        """
        validated = self._validate(mode)
        old = self.task_overrides.get(task_id)
        self.task_overrides[task_id] = validated
        return old

    def remove_task_override(self, task_id: str) -> bool:
        """Remove a per-task override, reverting to global default.

        Args:
            task_id: The TASK_<id> identifier to clear.

        Returns:
            True if an override existed and was removed; False otherwise.
        """
        return self.task_overrides.pop(task_id, None) is not None


# --------------------------------------------------------------------------- #
# Default config instance
# --------------------------------------------------------------------------- #

DEFAULT_CONFIG = WorkflowConfig()
"""Global default configuration — manual mode with no task overrides."""
