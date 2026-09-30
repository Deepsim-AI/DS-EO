"""
DS-EO Recovery State Persistence — Persistent Recovery State Management

Manages persistence of recovery state to survive process interruptions.
Stores recovery-specific information alongside existing dispatcher state.

Usage:
    from ds_eo_openclaw.workflow.recovery_state import RecoveryStateManager
    mgr = RecoveryStateManager(task_dir)
    mgr.save(task_id, mode, current_gate, status, failure, recovery)
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional


class RecoveryStateManager:
    """Persistent storage for recovery state.

    Manages read/write of recovery_state.json alongside dispatcher_state.json.
    Never modifies existing workflow state files — only adds new persistence layer.
    
    Args:
        task_dir: Directory containing the task's artifacts
    """

    FILENAME = "recovery_state.json"

    def __init__(self, task_dir: str):
        self.task_dir = task_dir
        self.filepath = os.path.join(task_dir, self.FILENAME)

    def save(self, task_id: str, mode: str, current_gate: str,
             status: str, failure: Dict[str, Any] = None, recovery: Dict[str, Any] = None) -> bool:
        """Save recovery state to disk.

        Args:
            task_id: Task identifier for the workflow being persisted
            mode: Current execution mode (automatic/manual)
            current_gate: Current gate in the workflow
            status: Current workflow status
            failure: Dict with failure information
            recovery: Dict with recovery information

        Returns:
            True if save was successful, False otherwise
        """
        try:
            persistence_data = {
                "task_id": task_id,
                "mode": mode,
                "current_gate": current_gate,
                "status": status,
                "failure": failure,
                "recovery": recovery,
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }

            os.makedirs(self.task_dir, exist_ok=True)
            with open(self.filepath, 'w') as f:
                json.dump(persistence_data, f, indent=2)

            return True
        except (IOError, OSError) as e:
            print(f"Failed to save recovery state for {task_id}: {e}")
            return False

    def load(self, task_id: str = None) -> Optional[Dict[str, Any]]:
        """Load recovery state from disk.

        Args:
            task_id: Task identifier to load state for

        Returns:
            Dict with loaded persistence data, or None if no state exists
        """
        try:
            if not os.path.isfile(self.filepath):
                return None

            with open(self.filepath, 'r') as f:
                data = json.load(f)

            # Validate task_id matches (safety check — only when provided)
            if task_id is not None and data.get("task_id") != task_id:
                print(f"Warning: Loaded state is for {data.get('task_id')}, not {task_id}")
                return None

            return data
        except (IOError, json.JSONDecodeError) as e:
            print(f"Failed to load recovery state for {task_id}: {e}")
            return None

    def can_resume(self, task_id: str = None) -> tuple[bool, str]:
        """Validate that persisted state is safe to resume.

        Checks integrity of loaded state before allowing resume.
        Verifies all required fields are present and consistent.

        Args:
            task_id: Task identifier to validate for resumption (optional)

        Returns:
            Tuple of (can_resume: bool, reason: str). reason is empty string on success.
        """
        loaded = self.load(task_id) if task_id else self._load_raw()
        if not loaded:
            return False, "No persisted recovery state found"

        # Check required fields per spec §8
        required_fields = ["task_id", "mode", "current_gate", "status"]
        for field in required_fields:
            if field not in loaded:
                return False, f"Missing required field '{field}' in recovery state"

        # Cannot resume from COMPLETED status (spec §12: no silent discard)
        if loaded.get("status") == "COMPLETED":
            return False, "Cannot resume COMPLETED workflow"

        # Cannot auto-resume manual mode (spec: manual is human-driven)
        if loaded.get("mode") == "manual":
            return False, "Manual mode cannot be auto-resumed"

        return True, ""

    def _load_raw(self) -> Optional[Dict[str, Any]]:
        """Load raw JSON from disk without task_id validation."""
        try:
            if not os.path.isfile(self.filepath):
                return None
            with open(self.filepath, 'r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            return None

    def clear(self) -> bool:
        """Delete persisted recovery state file."""
        try:
            if os.path.isfile(self.filepath):
                os.remove(self.filepath)
            return True
        except (IOError, OSError):
            return False

    def get_state_file_path(self) -> str:
        """Return the full path to the recovery state file."""
        return self.filepath

    def delete(self, task_id: str = None) -> bool:
        """Delete persisted recovery state for a completed/aborted task."""
        return self.clear()


def create_recovery_state_manager(task_dir: str) -> RecoveryStateManager:
    """Factory function to create RecoveryStateManager instance."""
    return RecoveryStateManager(task_dir)
