"""DS-EO Multi-Project Architecture — Project-scoped Task ID Manager.

Manages unique, project-isolated task IDs with the TASK_<PREFIX>_<NNN> convention.
Each project maintains its own independent sequential counter.
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


TASK_ID_PATTERN = re.compile(r"^TASK_(\w+)_(\d+)$")


@dataclass
class TaskIDInfo:
    """Parsed task ID components."""
    prefix: str        # e.g. "DAL"
    date_str: str      # e.g. "20260813" (date part, if any)
    sequence: int      # e.g. 2
    full_id: str       # e.g. "TASK_DAL_002"


class TaskIDManager:
    """Project-scoped task ID generation and validation.

    Unlike the old _next_task_id() in TaskIntakeManager which scanned a single
    global dispatchers directory, this manager works per-project with independent
    sequences.
    """

    def __init__(self, project_id: str, workspace_root: str = None):
        self.project_id = project_id
        self.workspace_root = workspace_root
        self._dispatchers_base = os.path.join(
            workspace_root or ".", "docs", "dispatchers"
        ) if not workspace_root else os.path.join(workspace_root, "docs", "dispatchers")

    def _get_task_prefix(self) -> Optional[str]:
        """Get the task prefix for this project from the catalog."""
        import yaml as _yaml

        catalog_path = os.path.join(os.path.expanduser("~/.openclaw"), "ds_eo", "projects.yaml")
        if not os.path.exists(catalog_path):
            return None

        with open(catalog_path) as f:
            data = _yaml.safe_load(f)

        for proj in data.get("projects", []):
            if proj.get("id") == self.project_id:
                return proj.get("task_prefix")
        return None

    def next_id(self, date_override: Optional[datetime] = None) -> str:
        """Get the next sequential task ID for this project.

        Scans only tasks with matching PREFIX in docs/dispatchers/.
        Each project has its own independent sequence regardless of date.
        """
        prefix = self._get_task_prefix() or self.project_id.upper()
        max_nnn = 0

        if os.path.isdir(self._dispatchers_base):
            for entry in os.listdir(self._dispatchers_base):
                full_match = f"TASK_{prefix}_"
                if entry.startswith(full_match) and "_" in entry:
                    try:
                        nnn_str = entry[len(full_match):]
                        # Validate it's all digits
                        if nnn_str.isdigit():
                            nnn = int(nnn_str)
                            max_nnn = max(max_nnn, nnn)
                    except ValueError:
                        pass

        return f"TASK_{prefix}_{max_nnn + 1:03d}"

    def next_id_with_date(self, date_override: Optional[datetime] = None) -> str:
        """Get the next task ID with a full date component (YYYYMMDD).

        Format: TASK_<PREFIX>_<YYYYMMDD>_<NNN>
        Used for tasks that span multiple days.
        """
        prefix = self._get_task_prefix() or self.project_id.upper()
        now = date_override or datetime.now(timezone.utc)
        date_str = now.strftime("%Y%m%d")

        # Scan only today's entries for this project
        pattern_full = re.compile(rf"^TASK_{prefix}_{date_str}_\d+$")
        max_nnn = 0

        if os.path.isdir(self._dispatchers_base):
            for entry in os.listdir(self._dispatchers_base):
                if pattern_full.match(entry):
                    nnn_str = entry.split("_")[-1]
                    try:
                        nnn = int(nnn_str)
                        max_nnn = max(max_nnn, nnn)
                    except ValueError:
                        pass

        return f"TASK_{prefix}_{date_str}_{max_nnn + 1:03d}"

    def validate_task_id(self, task_id: str) -> tuple[bool, Optional[str]]:
        """Validate a task ID format.

        Returns (is_valid, error_message_or_none).
        Also checks if the sequence number exceeds the current maximum.
        """
        match = TASK_ID_PATTERN.match(task_id)
        if not match:
            return False, f"Invalid format: {task_id}. Expected TASK_<PREFIX>_<NNN>"

        prefix = match.group(1)
        nnn = int(match.group(2))

        # Check against registered project prefixes
        catalog_path = os.path.join(os.path.expanduser("~/.openclaw"), "ds_eo", "projects.yaml")
        valid_prefixes = set()
        if os.path.exists(catalog_path):
            import yaml as _yaml
            with open(catalog_path) as f:
                data = _yaml.safe_load(f)
            valid_prefixes = {p.get("task_prefix", "").upper() for p in data.get("projects", [])}

        if valid_prefixes and prefix.upper() not in valid_prefixes:
            return False, f"Unknown project prefix '{prefix}'. Valid: {sorted(valid_prefixes)}"

        # Check sequence doesn't exceed current max by too much (>10 is suspicious)
        if self.workspace_root and os.path.isdir(self._dispatchers_base):
            current_max = 0
            for entry in os.listdir(self._dispatchers_base):
                full_match = f"TASK_{prefix}_"
                if entry.startswith(full_match) and "_" in entry:
                    try:
                        n_str = entry.split("_")[-1]
                        if n_str.isdigit():
                            current_max = max(current_max, int(n_str))
                    except ValueError:
                        pass

            if nnn > current_max + 10:
                return False, f"Sequence {nnn} exceeds current max {current_max} by too much"

        return True, None

    def parse_task_id(self, task_id: str) -> Optional[TaskIDInfo]:
        """Parse a task ID string into components."""
        match = TASK_ID_PATTERN.match(task_id)
        if not match:
            return None
        return TaskIDInfo(
            prefix=match.group(1),
            date_str="",  # Not in simple format
            sequence=int(match.group(2)),
            full_id=task_id,
        )


# ── CLI usage ──

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        proj_id = sys.argv[1]
        tid_manager = TaskIDManager(proj_id, workspace_root="/home/deepsim/ds_eo_openclaw")
        next_tid = tid_manager.next_id()
        print(f"Next task ID for project '{proj_id}': {next_tid}")

        # Also try with date
        next_with_date = tid_manager.next_id_with_date()
        print(f"With date:                      {next_with_date}")
    else:
        print("Usage: python3 task_id_manager.py <project_id>")
        print("  project_id: e.g. 'dal', 'framework'")
