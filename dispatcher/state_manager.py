"""
DS-EO Dispatcher — State Manager

Persistent per-task state with atomic writes, immutable event logs,
and agent registry checksum validation. All state lives in the task directory.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class PhaseSnapshot:
    """Immutable record of a phase stay."""
    phase: str
    entered_at: str       # ISO8601 UTC
    left_at: Optional[str]  # None = currently active
    agent: str

@dataclass
class TransitionSnapshot:
    """Immutable record of a gate transition."""
    id: str
    transition_name: str
    from_phase: Optional[str]
    to_phase: str
    timestamp: str        # ISO8601 UTC
    triggered_by_agent: str
    event_type: str
    payload_summary: str = ""
    artifacts_verified: list = field(default_factory=list)
    result: str = "success"
    error: Optional[str] = None

@dataclass 
class StallCheckSnapshot:
    """Stall detection tracking."""
    last_check: str        # ISO8601 UTC
    last_artifact_update: Optional[str]  # ISO8601 UTC or null
    stalled: bool = False
    stall_alert_sent_at: Optional[str] = None
    current_phase_entered: Optional[str] = None


@dataclass
class PendingWorkSnapshot:
    """What the active agent is currently doing."""
    task_id: str
    assigned_to: str
    work_type: str = ""
    spawn_session_key: Optional[str] = None
    spawned_at: Optional[str] = None  # ISO8601 UTC


class TaskStateManager:
    """
    Manage persistent state for a single DS-EO task.
    
    State lives at: docs/dispatcher/<TASK_ID>/dispatcher_state.json
    
    All writes are atomic (write to temp, fsync, rename).
    All reads reload from disk — no in-memory caching beyond the instance.
    """

    # Required fields in state file; enforced on create and validate()
    REQUIRED_FIELDS = ["version", "taskId", "current_phase", "workflow_version",
                       "agent_registry_checksum", "created_at", "updated_at"]

    def __init__(self, task_id: str, workspace_root: str = None):
        """
        Initialize the state manager for a specific task.

        Args:
            task_id: Task ID (e.g., "TASK_20260805_001")
            workspace_root: Workspace root; defaults to dispatcher parent dir's parent
        """
        self.task_id = task_id
        
        if workspace_root is None:
            # Default: go up two levels from this file (dispatcher/ -> ds-eo-openclaw/)
            ws = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            workspace_root = ws

        self.base_path = os.path.join(workspace_root, "docs", "dispatchers", task_id)
        self.state_path = os.path.join(self.base_path, "dispatcher_state.json")
        self.log_path = os.path.join(self.base_path, "dispatch_log.jsonl")
        
        # In-memory working state (cleared on read/write)
        self._state_cache: dict = {}

    def ensure_directory(self) -> tuple[bool, str]:
        """
        Create the task directory structure if it doesn't exist.

        Returns:
            (success, message)
        """
        try:
            os.makedirs(self.base_path, mode=0o755, exist_ok=True)
            return True, f"Directory ready at {self.base_path}"
        except OSError as e:
            return False, f"Failed to create directory {self.base_path}: {e}"

    def get_workspace_root(self) -> str:
        """Return the workspace root path (alias for computing base_path)."""
        return os.path.dirname(self.base_path)  # ds-eo-openclaw/

    def create_state(
        self,
        current_phase: str,
        workflow_version: str = "1.0",
        registry_checksum: str = "",
        extra_metadata: dict = None,
    ) -> tuple[bool, str]:
        """
        Create a new dispatcher state file for this task.

        Args:
            current_phase: Phase ID (e.g., "S0_OPEN")
            workflow_version: Which workflow definition is active
            registry_checksum: SHA256 of agents_list.json at time of creation
            extra_metadata: Optional additional fields to include

        Returns:
            (success, error_message_or_id)
        """
        # Ensure directory exists
        ok, msg = self.ensure_directory()
        if not ok:
            return False, msg

        now = datetime.now(timezone.utc).isoformat()

        state = {
            "version": "0.1.0",
            "taskId": self.task_id,
            "current_phase": current_phase,
            "workflow_version": workflow_version,
            "agent_registry_checksum": registry_checksum,
            "registry_agents": [],  # populated by caller via snapshot
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
            "phase_history": [
                {
                    "phase": current_phase,
                    "entered_at": now,
                    "left_at": None,
                    "agent": ""  # populated by caller
                }
            ],
            "transition_history": [],
            "stall_checks": {
                "last_check": now,
                "last_artifact_update": None,
                "stalled": False,
                "stall_alert_sent_at": None,
                "current_phase_entered": now,
            },
            "pending_work": {
                "task_id": self.task_id,
                "assigned_to": "",  # populated by caller
                "work_type": "",
                "spawn_session_key": None,
                "spawned_at": None,
            }
        }

        if extra_metadata:
            state.update(extra_metadata)

        ok = self._atomic_write(self.state_path, json.dumps(state, indent=2))
        if not ok:
            return False, "Failed to write dispatcher_state.json"

        # Initialize empty dispatch log
        if not os.path.exists(self.log_path):
            with open(self.log_path, "w") as f:
                pass  # create empty file

        return True, self.task_id

    def read_state(self) -> tuple[Optional[dict], Optional[str]]:
        """
        Read and validate the current dispatcher state from disk.

        Returns:
            (state_dict_or_None, error_message_or_None)
        """
        if not os.path.exists(self.state_path):
            return None, f"State file not found: {self.state_path}"

        try:
            with open(self.state_path, "r") as f:
                state = json.load(f)
        except json.JSONDecodeError as e:
            return None, f"Invalid JSON in dispatcher_state.json: {e}"
        except OSError as e:
            return None, f"Cannot read state file: {e}"

        # Validate required fields
        missing = [f for f in self.REQUIRED_FIELDS if f not in state]
        if missing:
            return None, f"State file missing required fields: {', '.join(missing)}"

        # Cache the loaded state
        self._state_cache = state
        return state, None

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate the current state file for completeness and consistency.

        Returns:
            (is_valid, list_of_issue_messages)
        """
        state, err = self.read_state()
        if err:
            return False, [err]

        issues = []

        # Check required fields present
        missing = [f for f in self.REQUIRED_FIELDS if f not in state]
        if missing:
            issues.append(f"Missing required fields: {', '.join(missing)}")

        # Validate current_phase is non-empty string
        if not isinstance(state.get("current_phase"), str) or not state["current_phase"]:
            issues.append("'current_phase' must be a non-empty string")

        # Validate workflow_version format
        wv = state.get("workflow_version", "0.0.0")
        if not isinstance(wv, str):
            issues.append("'workflow_version' must be a string")

        # Validate timestamp formats (best-effort ISO8601 check)
        for ts_field in ["created_at", "updated_at"]:
            ts = state.get(ts_field, "")
            if not self._is_valid_timestamp(str(ts)):
                issues.append(f"'{ts_field}' has invalid timestamp format: {ts}")

        # Validate phase_history is a list of objects with required fields
        ph = state.get("phase_history", [])
        if isinstance(ph, list):
            for i, entry in enumerate(ph):
                if not isinstance(entry, dict):
                    issues.append(f"phase_history[{i}] must be an object")
                    continue
                for pf in ["phase", "entered_at"]:
                    if pf not in entry:
                        issues.append(f"phase_history[{i}] missing '{pf}'")

        # Validate transition_history is a list of objects
        th = state.get("transition_history", [])
        if isinstance(th, list):
            for i, entry in enumerate(th):
                if not isinstance(entry, dict):
                    issues.append(f"transition_history[{i}] must be an object")
                    continue

        return len(issues) == 0, issues

    def update_phase(self, new_phase: str, transition_record: TransitionSnapshot) -> tuple[bool, str]:
        """
        Update the current phase with a transition record.

        Atomic write: writes to temp file, syncs, then renames.

        Args:
            new_phase: The phase we're transitioning TO
            transition_record: The completed transition metadata

        Returns:
            (success, error_message_or_id)
        """
        state, err = self.read_state()
        if err:
            return False, err

        now = datetime.now(timezone.utc).isoformat()

        # Update current phase
        old_phase = state.get("current_phase", "unknown")
        state["current_phase"] = new_phase
        state["updated_at"] = now

        # Update the last phase entry in history (mark it as left)
        ph = state.get("phase_history", [])
        if isinstance(ph, list) and len(ph) > 0:
            last_entry = ph[-1]
            if isinstance(last_entry, dict):
                if last_entry.get("left_at") is None:
                    last_entry["left_at"] = now

        # Append the phase we're moving into (if not already in history)
        new_phase_entry = {
            "phase": new_phase,
            "entered_at": now,
            "left_at": None,
            "agent": transition_record.triggered_by_agent if transition_record else "",
        }

        # Don't duplicate if we just entered this phase in this transition
        if len(ph) == 0 or ph[-1].get("phase") != new_phase:
            ph.append(new_phase_entry)
        state["phase_history"] = ph

        # Append transition to history
        th = state.get("transition_history", [])
        if not isinstance(th, list):
            th = []
        
        record_dict = {
            "id": transition_record.id,
            "transition_name": transition_record.transition_name,
            "from_phase": transition_record.from_phase,
            "to_phase": transition_record.to_phase,
            "timestamp": transition_record.timestamp,
            "triggered_by_agent": transition_record.triggered_by_agent,
            "event_type": transition_record.event_type,
            "payload_summary": transition_record.payload_summary,
            "artifacts_verified": transition_record.artifacts_verified,
            "result": transition_record.result,
        }
        if transition_record.error:
            record_dict["error"] = transition_record.error
        
        th.append(record_dict)
        state["transition_history"] = th

        # Update stall detection
        sc = state.get("stall_checks", {})
        sc["last_check"] = now
        sc["current_phase_entered"] = now
        state["stall_checks"] = sc

        return self._atomic_write(self.state_path, json.dumps(state, indent=2))

    def mark_complete(self) -> tuple[bool, str]:
        """
        Mark the task as complete (set completed_at timestamp).

        Returns:
            (success, error_message_or_status)
        """
        state, err = self.read_state()
        if err:
            return False, err

        now = datetime.now(timezone.utc).isoformat()
        state["completed_at"] = now
        state["updated_at"] = now
        state["current_phase"] = "S5_COMPLETE"

        ok = self._atomic_write(self.state_path, json.dumps(state, indent=2))
        if not ok:
            return False, "Failed to write completed_at"

        return True, f"Task {self.task_id} marked complete at {now}"

    def append_dispatch_log(self, event_record: dict) -> tuple[bool, str]:
        """
        Append an event record to the dispatch log (JSON Lines format).

        Appends atomically (open append mode, flush, fsync).

        Args:
            event_record: Dict with at minimum "seq" and "ts" fields

        Returns:
            (success, error_message_or_seq)
        """
        if not os.path.exists(self.log_path):
            return False, f"Dispatch log not found: {self.log_path}"

        try:
            # Read last sequence number to determine next
            seq = 0
            if os.path.getsize(self.log_path) > 0:
                with open(self.log_path, "r") as f:
                    for line in f:
                        if line.strip():
                            try:
                                rec = json.loads(line.strip())
                                seq = max(seq, rec.get("seq", 0))
                            except json.JSONDecodeError:
                                continue

            next_seq = seq + 1
            event_record["seq"] = next_seq

            # Write append with fsync
            with open(self.log_path, "a") as f:
                line = json.dumps(event_record, separators=(",", ":")) + "\n"
                f.write(line)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass  # Some filesystems don't support fsync on append mode

            return True, str(next_seq)
        except OSError as e:
            return False, f"Failed to append dispatch log: {e}"

    def get_current_phase(self) -> Optional[str]:
        """Get current phase from state file."""
        state, err = self.read_state()
        if err:
            return None
        return state.get("current_phase")

    def get_transition_history(self) -> list[dict]:
        """Get all transitions for this task."""
        state, err = self.read_state()
        if err:
            return []
        return state.get("transition_history", [])

    def get_stall_info(self) -> dict:
        """Get current stall detection info."""
        state, err = self.read_state()
        if err:
            return {"stalled": False, "error": str(err)}
        return state.get("stall_checks", {})

    def update_stall_artifact_update(self, timestamp_str: str) -> tuple[bool, str]:
        """Update the last artifact update timestamp."""
        state, err = self.read_state()
        if err:
            return False, err
        
        sc = state.get("stall_checks", {})
        sc["last_artifact_update"] = timestamp_str
        sc["stalled"] = False  # clear stall flag on new activity
        state["stall_checks"] = sc

        ok = self._atomic_write(self.state_path, json.dumps(state, indent=2))
        return ok

    def update_pending_work(self, pending: PendingWorkSnapshot) -> tuple[bool, str]:
        """Update the pending work record."""
        state, err = self.read_state()
        if err:
            return False, err

        pw = {
            "task_id": pending.task_id,
            "assigned_to": pending.assigned_to,
            "work_type": pending.work_type,
            "spawn_session_key": pending.spawn_session_key,
            "spawned_at": pending.spawned_at,
        }
        state["pending_work"] = pw

        ok = self._atomic_write(self.state_path, json.dumps(state, indent=2))
        return ok

    def clear_pending_work(self) -> tuple[bool, str]:
        """Clear the pending work record after completion."""
        state, err = self.read_state()
        if err:
            return False, err

        state["pending_work"] = {
            "task_id": self.task_id,
            "assigned_to": "",
            "work_type": "",
            "spawn_session_key": None,
            "spawned_at": None,
        }

        ok = self._atomic_write(self.state_path, json.dumps(state, indent=2))
        return ok

    def get_registry_checksum(self) -> Optional[str]:
        """Get the registry checksum from state."""
        state, err = self.read_state()
        if err:
            return None
        return state.get("agent_registry_checksum")

    def verify_registry_integrity(self, current_checksum: str) -> tuple[bool, list[str]]:
        """
        Verify that the agent registry hasn't changed since task creation.

        Args:
            current_checksum: Current SHA256 of agents_list.json

        Returns:
            (intact, list_of_messages)
        """
        state, err = self.read_state()
        if err:
            return False, [f"Cannot read state: {err}"]

        stored = state.get("agent_registry_checksum", "")
        if not stored:
            return False, ["No registry checksum in state — task was created without validation"]

        if stored != current_checksum:
            return False, [
                f"Registry checksum mismatch! Task may be using stale agent list.",
                f"  Stored (at creation): {stored}",
                f"  Current:              {current_checksum}",
                f"  Action required: Re-create the task with updated registry",
            ]

        return True, ["Registry checksum intact — no drift detected"]

    def get_task_dir_contents(self) -> list[str]:
        """List all files in the task directory."""
        if not os.path.exists(self.base_path):
            return []
        try:
            return [f for f in os.listdir(self.base_path) if not f.startswith('.')]
        except OSError:
            return []

    # ====================================================================
    # Utility methods
    # ====================================================================

    def _atomic_write(self, path: str, content: str) -> tuple[bool, str]:
        """
        Write content atomically using temp file + rename pattern.

        Returns:
            (success, error_message_or_target_path)
        """
        try:
            # Write to temp file in same directory (ensures same filesystem for rename)
            dir_name = os.path.dirname(path)
            fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
            try:
                os.write(fd, content.encode("utf-8"))
                os.fsync(fd)
            finally:
                os.close(fd)

            # Atomic rename
            os.replace(path + ".tmp", path)
            return True, path
        except OSError as e:
            # Clean up temp file if it exists
            try:
                os.unlink(path + ".tmp")
            except OSError:
                pass
            return False, f"Atomic write failed at {path}: {e}"

    def _is_valid_timestamp(self, ts_str: str) -> bool:
        """Best-effort ISO8601 timestamp validation."""
        if not ts_str:
            return False
        try:
            # Accept any string with a T separator (basic ISO8601 check)
            return "T" in ts_str and len(ts_str) >= 19
        except Exception:
            return False


# ====================================================================
# CLI usage — quick state file inspection
# ====================================================================
if __name__ == "__main__":
    import sys

    task_id = sys.argv[1] if len(sys.argv) > 1 else "TASK_20260805_001"
    
    sm = TaskStateManager(task_id, workspace_root="/home/deepsim/ds-eo-openclaw")
    
    print(f"Task: {task_id}")
    print(f"Base path: {sm.base_path}")
    print(f"State file: {sm.state_path}")
    print()

    # Check if state exists
    ok, msg = sm.ensure_directory()
    print(f"Directory: {'ready' if ok else 'needs creation'}")

    state, err = sm.read_state()
    if err:
        print(f"State: not found ({err})")
        
        # Offer to create one
        ask = input("Create test state? [y/N]: ").strip().lower()
        if ask == "y":
            ok2, msg2 = sm.create_state("S0_OPEN", "1.0", "test_checksum_abc123")
            print(f"Created: {'OK' if ok2 else 'FAIL'} ({msg2})")
    else:
        print(f"Current phase: {state['current_phase']}")
        print(f"Workflow: v{state.get('workflow_version')}")
        print(f"Transitions: {len(state.get('transition_history', []))}")
        print(f"Phase history: {len(state.get('phase_history', []))}")
        
        # Validate
        valid, issues = sm.validate()
        status = "VALID" if valid else "ISSUES"
        print(f"Validation: [{status}]")
        for issue in issues:
            print(f"  - {issue}")
