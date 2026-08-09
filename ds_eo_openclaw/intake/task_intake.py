"""
DS-EO Task Intake Manager.

Handles PM-driven task intake: receiving user requests, creating organized
task workspaces (both dispatcher state and reports), duplicate detection,
and CTO handoff preparation.

This module is intentionally independent of the dispatcher's gate machinery.
It creates workspace artifacts; the Dispatcher handles lifecycle transitions.
"""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Optional


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

TASK_ID_PATTERN = re.compile(r"^TASK_(\d{8})_(\d+)$")
DUPLICATE_THRESHOLD = 0.7          # Keyword overlap ratio to flag as duplicate
INTAKE_STATES = ["NEW", "INTAKE", "AWAITING_USER_INPUT", "READY_FOR_CTO"]
REPORTS_DIR_NAME = "docs/development/reports"


class IntakeBoundaryError(Exception):
    """Raised when a PM attempts to continue task intake beyond its role boundary.
    
    This is a mechanical enforcement of the DS-EO delegation protocol:
    the TaskIntakeManager is designed for administrative workspace creation only.
    After it returns READY_FOR_CTO, no further actions are permitted — 
    CTO must independently perform all planning work.
    
    See protocols/delegation_protocol.md §5.0 (Role Boundary Enforcement During Task Intake)
    and agents/pm.md lines 174-228 (Mechanical Boundary Enforcement).
    """
    pass


class IntakeBoundaryState:
    """Tracks whether the current intake session has already returned READY_FOR_CTO.
    
    Prevents post-intake role collapse where a PM continues to perform CTO duties
    after receiving the handoff signal.
    """
    
    def __init__(self):
        self._intake_complete = False
    
    def is_complete(self) -> bool:
        return self._intake_complete
    
    def mark_complete(self):
        self._intake_complete = True
    
    def raise_if_complete(self):
        if self._intake_complete:
            raise IntakeBoundaryError(
                "Task intake already completed. Status is READY_FOR_CTO. "
                "The PM must NOT continue with any additional work beyond intake artifact creation. "
                "This is a role-boundary violation per delegation_protocol.md §5.0. "
                "Please dispatch to the CTO for independent technical analysis and planning."
            )



DISPATCHERS_DIR_NAME = "docs/dispatchers"


# --------------------------------------------------------------------------- #
# Helper: text similarity
# --------------------------------------------------------------------------- #

def _normalize_text(text: str) -> set[str]:
    """Tokenize and normalize text for comparison."""
    if not text:
        return set()
    tokens = re.findall(r"\w+", text.lower())
    return set(tokens)


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    """Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


# --------------------------------------------------------------------------- #
# Main class
# --------------------------------------------------------------------------- #

class TaskIntakeManager:
    """
    Manages PM-level task intake operations.

    Responsibilities:
      - Receive user requests and preserve them verbatim
      - Create organized task workspaces (dispatcher + reports)
      - Detect duplicate/ambiguous tasks against existing ones
      - Organize user-provided files into INPUTS/
      - Prepare task packages for CTO handoff
      - Accept additional materials after initial intake

    Does NOT:
      - Modify gate mechanics or workflow state machine
      - Make architectural decisions (CTO responsibility)
      - Implement source code changes
    """

    def __init__(self, workspace_root: str):
        """
        Initialize with workspace root path.

        Args:
            workspace_root: Root of the DS-EO repository/workspace.
        """
        self.workspace_root = os.path.abspath(workspace_root)
        self._reports_base = os.path.join(self.workspace_root, REPORTS_DIR_NAME)
        self._dispatchers_base = os.path.join(self.workspace_root, DISPATCHERS_DIR_NAME)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def create_task_intake(
        self,
        request_text: str,
        user_files: Optional[list[str]] = None,
        mode: str = "manual",
        pm_analysis: str = "",
    ) -> tuple[bool, dict]:
        """
        Create a complete task workspace from a user request.

        This is the primary entry point for PM-driven task intake. It:
          1. Checks for semantic duplicates against existing tasks.
          2. Assigns the next available task ID per convention.
          3. Creates both dispatcher state directory and reports directory.
          4. Writes TASK_REQUEST.md (verbatim user request), PM_ANALYSIS.md,
             INPUTS/ (user files), and MANIFEST.md (metadata).

        Args:
            request_text: The user's verbatim original request/specification.
            user_files: Optional list of file paths to incorporate into INPUTS/.
            mode: "manual" or "automatic" — affects post-intake behavior only;
                  intake output is identical regardless of mode.
            pm_analysis: Optional PM interpretation/summary. If empty, a default
                         placeholder is written instead.

        Returns:
            (success, result_dict) where result_dict contains:
              - task_id: Assigned TASK_<YYYYMMDD>_<NNN> identifier
              - workspace_path: Full path to the reports directory
              - dispatcher_state_path: Full path to the dispatcher state dir
              - duplicate_found: Whether a potential duplicate was detected
              - matching_task: Info about any matching existing task (if found)
              - error: Error message if success is False

        Raises:
            ValueError: If request_text is empty or whitespace-only.
        """
        if not request_text or not request_text.strip():
            raise ValueError("request_text must be non-empty")

        request_text = request_text.strip()

        # 1. Deduplication check
        dedup_result = self._deduplicate(request_text)
        is_duplicate, matching_task_info = dedup_result

        if is_duplicate and matching_task_info:
            return True, {
                "task_id": None,
                "duplicate_found": True,
                "matching_task": matching_task_info,
                "workspace_path": None,
                "dispatcher_state_path": None,
                "error": (
                    f"Potential duplicate detected. Task '{matching_task_info['task_id']}' "
                    f"({matching_task_info['similarity']:.0%} similarity) already exists with a similar request. "
                    f"Consider using add_materials_to_existing() instead."
                ),
            }

        # 2. Assign next task ID
        task_id = self._next_task_id()

        # 3. Create both workspace locations atomically
        reports_dir = os.path.join(self.workspace_root, REPORTS_DIR_NAME, task_id)
        dispatcher_dir = os.path.join(self._dispatchers_base, task_id)

        try:
            os.makedirs(reports_dir, exist_ok=True)
            os.makedirs(dispatcher_dir, exist_ok=True)

            # 4. Write intake artifacts in reports dir
            self._create_intake_artifacts(task_id, request_text, user_files or [], pm_analysis)

            return True, {
                "task_id": task_id,
                "duplicate_found": False,
                "matching_task": None,
                "workspace_path": reports_dir,
                "dispatcher_state_path": dispatcher_dir,
                "error": None,
            }

        except Exception as exc:
            # Rollback on failure — try to remove what we created
            self._cleanup_partial(task_id, reports_dir)
            return False, {
                "task_id": task_id,
                "duplicate_found": False,
                "matching_task": None,
                "workspace_path": reports_dir if os.path.exists(reports_dir) else None,
                "dispatcher_state_path": dispatcher_dir if os.path.exists(dispatcher_dir) else None,
                "error": str(exc),
            }

    def add_materials_to_existing(
        self,
        task_id: str,
        materials: dict[str, str],
    ) -> tuple[bool, dict]:
        """
        Add files or text notes to an existing task workspace.

        Args:
            task_id: The TASK_<YYYYMMDD>_<NNN> identifier of the target task.
            materials: Dict mapping material names (filenames or keys) to content/paths:
                - If value is a file path that exists, it will be copied into INPUTS/.
                - If value is a string (not an existing file), it's treated as text
                  content and written under INPUTS/<name>.txt.

        Returns:
            (success, result_dict) with:
              - success: bool
              - added_items: list of items that were successfully added
              - error: Error message if failed

        Raises:
            FileNotFoundError: If the task_id doesn't correspond to an existing workspace.
        """
        reports_dir = os.path.join(self.workspace_root, REPORTS_DIR_NAME, task_id)
        if not os.path.isdir(reports_dir):
            raise FileNotFoundError(
                f"Task workspace not found for {task_id}. "
                f"Searched: {reports_dir}"
            )

        inputs_dir = os.path.join(reports_dir, "INPUTS")
        os.makedirs(inputs_dir, exist_ok=True)

        added_items = []
        errors = []

        for name, content in materials.items():
            safe_name = self._sanitize_filename(name)

            if isinstance(content, str):
                # Check if it's an existing file path
                if os.path.isfile(content):
                    dest = os.path.join(inputs_dir, f"{safe_name}_{os.path.basename(content)}")
                    try:
                        with open(content, "rb") as src, open(dest, "wb") as dst:
                            dst.write(src.read())
                        added_items.append({"name": name, "dest": dest, "source": content})
                    except OSError as exc:
                        errors.append(f"Failed to copy {content}: {exc}")
                else:
                    # Treat as text content
                    if not safe_name.endswith((".txt", ".md")):
                        safe_name += ".txt"
                    dest = os.path.join(inputs_dir, safe_name)
                    try:
                        with open(dest, "w") as f:
                            f.write(content)
                        added_items.append({"name": name, "dest": dest, "source": "<text content>"})
                    except OSError as exc:
                        errors.append(f"Failed to write {dest}: {exc}")

        # Update MANIFEST.md with new materials
        self._append_materials_to_manifest(task_id, added_items)

        if not errors and added_items:
            return True, {"success": True, "added_items": added_items, "error": None}
        elif added_items:
            return True, {"success": True, "added_items": added_items, "error": f"Partial: {errors}"}
        else:
            return False, {"success": False, "added_items": [], "error": "; ".join(errors)}

    def find_semantic_matches(
        self,
        request_text: str,
        max_results: int = 3,
    ) -> list[dict]:
        """
        Check for potential duplicate tasks by semantic similarity.

        Args:
            request_text: The user's request to check against existing tasks.
            max_results: Maximum number of matching tasks to return (default 3).

        Returns:
            List of dicts with keys:
              - task_id: The existing task ID
              - similarity: Jaccard keyword overlap ratio
              - description: Brief info about the matching task
              - status: Current intake state if available
        """
        matches = []
        tokens_new = _normalize_text(request_text)

        for entry in self._iter_existing_tasks():
            existing_req = self._extract_request_text(entry["task_id"])
            if not existing_req:
                continue

            tokens_existing = _normalize_text(existing_req)
            similarity = _jaccard_similarity(tokens_new, tokens_existing)

            if similarity >= DUPLICATE_THRESHOLD:
                matches.append({
                    "task_id": entry["task_id"],
                    "similarity": similarity,
                    "description": existing_req[:120] + ("..." if len(existing_req) > 120 else ""),
                    "status": self._get_task_intake_status(entry["task_id"]),
                })

        matches.sort(key=lambda m: m["similarity"], reverse=True)
        return matches[:max_results]

    def prepare_cto_handoff(self, task_id: str) -> tuple[bool, dict]:
        """
        Ensure the task workspace is ready for CTO reading.

        Verifies that all required artifacts exist in the reports directory
        and returns a summary of what's available. Does NOT advance any gate.

        Args:
            task_id: The TASK_<YYYYMMDD>_<NNN> identifier.

        Returns:
            (success, result_dict) with:
              - ready: bool — whether all required artifacts are present
              - missing_artifacts: list of artifact names that are absent
              - available_artifacts: list of artifact names that exist
              - workspace_path: Full path to the reports directory
        """
        reports_dir = os.path.join(self.workspace_root, REPORTS_DIR_NAME, task_id)

        if not os.path.isdir(reports_dir):
            return False, {
                "ready": False,
                "missing_artifacts": [],
                "available_artifacts": [],
                "workspace_path": None,
                "error": f"Task workspace not found: {reports_dir}",
            }

        # Required artifacts for CTO handoff
        required = ["TASK_REQUEST.md"]
        recommended = ["PM_ANALYSIS.md", "MANIFEST.md"]

        available = []
        missing = list(required)  # Start with all required as potentially missing

        for artifact in required + recommended:
            path = os.path.join(reports_dir, artifact)
            if os.path.exists(path):
                available.append(artifact)
                if artifact in missing:
                    missing.remove(artifact)

        ready = len(missing) == 0
        return ready, {
            "ready": ready,
            "missing_artifacts": missing,
            "available_artifacts": available,
            "workspace_path": reports_dir,
        }

    # ------------------------------------------------------------------ #
    # Internal: Task ID management
    # ------------------------------------------------------------------ #

    def _next_task_id(self, date_override: Optional[datetime] = None) -> str:
        """
        Get the next available task ID per TASK_<YYYYMMDD>_<NNN> convention.

        Scans docs/dispatchers/ for all existing TASK_* directories and finds
        the maximum NNN for today's date. If no tasks exist today, starts at 001.

        Returns:
            Task ID string (e.g., "TASK_20260807_003")
        """
        now = date_override or datetime.now(timezone.utc)
        date_str = now.strftime("%Y%m%d")

        # Scan existing task directories in dispatchers dir
        max_nnn = 0

        if not os.path.isdir(self._dispatchers_base):
            return f"TASK_{date_str}_001"

        for entry in os.listdir(self._dispatchers_base):
            match = TASK_ID_PATTERN.match(entry)
            if not match:
                continue
            entry_date = match.group(1)
            nnn = int(match.group(2))
            if entry_date == date_str and nnn > max_nnn:
                max_nnn = nnn

        return f"TASK_{date_str}_{max_nnn + 1:03d}"

    # ------------------------------------------------------------------ #
    # Internal: Duplicate detection
    # ------------------------------------------------------------------ #

    def _deduplicate(self, request_text: str) -> tuple[bool, Optional[dict]]:
        """
        Check if the given request matches any existing task.

        Args:
            request_text: The user's request to check for duplicates.

        Returns:
            (is_duplicate, matching_task_info or None)
            is_duplicate is True when similarity >= DUPLICATE_THRESHOLD.
        """
        matches = self.find_semantic_matches(request_text, max_results=1)
        if matches:
            return True, matches[0]
        return False, None

    # ------------------------------------------------------------------ #
    # Internal: Artifact creation
    # ------------------------------------------------------------------ #

    def _create_intake_artifacts(
        self,
        task_id: str,
        request_text: str,
        user_files: list[str],
        pm_analysis: str,
    ) -> None:
        """
        Write all intake artifacts into the reports directory.

        Creates: TASK_REQUEST.md, PM_ANALYSIS.md (if provided), INPUTS/, MANIFEST.md
        """
        reports_dir = os.path.join(self.workspace_root, REPORTS_DIR_NAME, task_id)
        now = datetime.now(timezone.utc).isoformat()

        # 1. TASK_REQUEST.md — preserve user's verbatim request
        self._write_task_request(task_id, request_text, now)

        # 2. PM_ANALYSIS.md — PM interpretation (optional)
        if pm_analysis.strip():
            self._write_pm_analysis(task_id, pm_analysis, now)
        else:
            self._write_pm_analysis_placeholder(task_id, now)

        # 3. INPUTS/ — organize user-provided files
        inputs_dir = os.path.join(reports_dir, "INPUTS")
        if user_files:
            os.makedirs(inputs_dir, exist_ok=True)
            for filepath in user_files:
                self._copy_user_file(filepath, inputs_dir)

        # 4. MANIFEST.md — task metadata (written after other artifacts so it can reference them)
        intake_status = "INTAKE"
        self._write_manifest(task_id, request_text, now, intake_status)

    def _write_task_request(self, task_id: str, request_text: str, timestamp: str) -> None:
        """Write TASK_REQUEST.md preserving user's verbatim request."""
        reports_dir = os.path.join(
            self.workspace_root, REPORTS_DIR_NAME, task_id
        )
        content = f"""---
produced_by: pm
role: PM
task_id: {task_id}
gate: G0 (intake)
created_at: {timestamp}
---

# Task Request — {task_id}

## User's Original Request

> {request_text}

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | `{task_id}` |
| **Created** | {timestamp} |
| **Source** | Direct user request to PM |
"""
        path = os.path.join(reports_dir, "TASK_REQUEST.md")
        with open(path, "w") as f:
            f.write(content)

    def _write_pm_analysis(self, task_id: str, analysis: str, timestamp: str) -> None:
        """Write PM_ANALYSIS.md with PM's interpretation."""
        reports_dir = os.path.join(
            self.workspace_root, REPORTS_DIR_NAME, task_id
        )
        content = f"""---
produced_by: pm
role: PM
task_id: {task_id}
gate: G0 (intake)
created_at: {timestamp}
---

# PM Analysis — {task_id}

## Interpretation of User Request

{analysis}
"""
        path = os.path.join(reports_dir, "PM_ANALYSIS.md")
        with open(path, "w") as f:
            f.write(content)

    def _write_pm_analysis_placeholder(self, task_id: str, timestamp: str) -> None:
        """Write a placeholder PM_ANALYSIS.md when no analysis is provided."""
        reports_dir = os.path.join(
            self.workspace_root, REPORTS_DIR_NAME, task_id
        )
        content = f"""---
produced_by: pm
role: PM
task_id: {task_id}
gate: G0 (intake)
created_at: {timestamp}
---

# PM Analysis — {task_id}

## Status

No PM analysis has been written yet. The user's original request is preserved in `TASK_REQUEST.md`.
"""
        path = os.path.join(reports_dir, "PM_ANALYSIS.md")
        with open(path, "w") as f:
            f.write(content)

    def _write_manifest(
        self,
        task_id: str,
        request_text: str,
        timestamp: str,
        intake_status: str = "INTAKE",
    ) -> None:
        """Write MANIFEST.md with task metadata."""
        reports_dir = os.path.join(
            self.workspace_root, REPORTS_DIR_NAME, task_id
        )

        # Build available artifacts list
        available_files = []
        if os.path.exists(os.path.join(reports_dir, "TASK_REQUEST.md")):
            available_files.append("TASK_REQUEST.md")
        if os.path.isdir(os.path.join(reports_dir, "INPUTS")):
            inputs_path = os.path.join(reports_dir, "INPUTS")
            for f in sorted(os.listdir(inputs_path)):
                fp = os.path.join(inputs_path, f)
                if os.path.isfile(fp):
                    available_files.append(f"INPUTS/{f}")

        # Build tree lines outside f-string to avoid backslash-in-fstring error
        box_char = '\u251c\u2500\u2500 '
        pipe_char = '\u2502   '
        tee_down = '\u2514\u2500\u2500 '
        arrow = '\u2190 '

        if available_files:
            dir_tree_lines = [box_char + f for f in available_files]
            input_dir_line = (pipe_char + box_char).join(dir_tree_lines)
        else:
            input_dir_line = '        (empty)'

        # Build request summary outside f-string
        req_summary = request_text[:500]
        if len(request_text) > 500:
            req_summary += '...'

        # Session health metadata section for protection tracking (Phase 5: C10)
        session_health_section = (
            "## Session Health Protection\n\n"
            "Sessions associated with this task are tracked by the session health system.\n"
            "Protected sessions never receive automatic destructive actions (ARCHIVE/CLOSE).\n\n"
            "| Field | Value |\n"
            "|-------|-------|\n"
            "| **Protection Status** | Active — task-associated sessions are protected |\n"
            "| **Health Monitoring** | Enabled (OBSERVING mode by default) |\n"
            "| **Destructive Actions** | Blocked for sessions with ACTIVE task association |\n"
        )

        # Build the content string using explicit concatenation to avoid syntax issues
        header = (
            "---\n"
            f"produced_by: pm\n"
            f"role: PM\n"
            f"task_id: {task_id}\n"
            f"gate: G0 (intake)\n"
            f"created_at: {timestamp}\n"
            "---\n\n"
        )
        
        title = f"# Task Manifest {arrow} {task_id}\n\n"
        
        metadata_header = (
            "## Metadata\n\n"
            "| Field | Value |\n"
            "|-------|-------|\n"
            f"| **Task ID** | `{task_id}` |\n"
            f"| **Created** | {timestamp} |\n"
            f"| **Intake Status** | {intake_status} |\n"
            "| **Mode** | manual (default) |\n"
            f"| **Dispatcher State Path** | `docs/dispatchers/{task_id}/` |\n"
            f"| **Reports Directory** | `docs/development/reports/{task_id}/` |\n\n"
        )
        
        content = header + title + metadata_header + session_health_section
        
        # Add artifacts section
        artifacts_header = "## Available Artifacts\n\n```\n"
        task_dir_line = f"{task_id}/\n"
        
        if available_files:
            dir_tree_lines = [box_char + f for f in available_files]
            input_dir_line = (pipe_char + box_char).join(dir_tree_lines)
        else:
            input_dir_line = '        (empty)'
        
        artifacts_tree = (
            task_dir_line
            + box_char + "TASK_REQUEST.md          " + arrow + "User's verbatim request (preserved)\n"
            + box_char + "PM_ANALYSIS.md           " + arrow + "PM interpretation/summary\n"
            + box_char + "INPUTS/                  " + arrow + "User-provided files\n"
            f"{pipe_char}{input_dir_line}\n"
            + tee_down + "MANIFEST.md              " + arrow + "This file (task metadata)\n"
        )
        
        request_summary = (
            "```\n\n"
            "## Request Summary\n\n"
            f"{req_summary}\n"
        )
        
        content += artifacts_header + artifacts_tree + request_summary

        path = os.path.join(reports_dir, "MANIFEST.md")
        with open(path, "w") as f:
            f.write(content)

    # ------------------------------------------------------------------ #
    # Internal: File helpers
    # ------------------------------------------------------------------ #

    def _append_materials_to_manifest(
        self,
        task_id: str,
        added_items: list[dict],
    ) -> None:
        """Append new material entries to the existing MANIFEST.md."""
        reports_dir = os.path.join(self.workspace_root, REPORTS_DIR_NAME, task_id)
        manifest_path = os.path.join(reports_dir, "MANIFEST.md")

        if not os.path.exists(manifest_path):
            return  # No manifest to update — that's a different problem

        now = datetime.now(timezone.utc).isoformat()

        # Read existing content, find the Available Artifacts section, and append
        with open(manifest_path) as f:
            lines = f.readlines()

        new_lines = []
        in_artifacts_section = False
        artifacts_inserted = False

        for i, line in enumerate(lines):
            if "## Available Artifacts" in line:
                in_artifacts_section = True
            elif in_artifacts_section and line.startswith("## "):
                # New section starting — insert before it
                new_lines.append("\n")
                new_lines.append(f"**Updated {now}:** Added {len(added_items)} item(s)\n\n")
                for item in added_items:
                    dest = item.get("dest", "")
                    name = os.path.basename(dest) if dest else item.get("name", "?")
                    source_type = "file" if item.get("source") != "<text content>" else "text"
                    new_lines.append(f"- **{name}** ({source_type})\n")
                new_lines.append("\n---\n\n")
                in_artifacts_section = False
                artifacts_inserted = True

            new_lines.append(line)

        if not artifacts_inserted:
            # Append at end
            new_lines.append(f"\n**Updated {now}:** Added {len(added_items)} item(s)\n\n")
            for item in added_items:
                dest = item.get("dest", "")
                name = os.path.basename(dest) if dest else item.get("name", "?")
                source_type = "file" if item.get("source") != "<text content>" else "text"
                new_lines.append(f"- **{name}** ({source_type})\n")

        with open(manifest_path, "w") as f:
            f.writelines(new_lines)

    def _copy_user_file(self, filepath: str, dest_dir: str) -> None:
        """Copy a user file into the INPUTS directory."""
        if not os.path.isfile(filepath):
            return  # Silently skip non-existent files (robustness)

        basename = os.path.basename(filepath)
        dest_path = os.path.join(dest_dir, basename)

        with open(filepath, "rb") as src:
            with open(dest_path, "wb") as dst:
                dst.write(src.read())

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string to be safe as a filename."""
        # Replace unsafe characters with underscores
        sanitized = re.sub(r'[^\w.\-]', '_', name)
        # Remove leading/trailing whitespace and dots
        sanitized = sanitized.strip('. ')
        if not sanitized:
            sanitized = "unnamed"
        return sanitized

    def _cleanup_partial(self, task_id: str, reports_dir: str) -> None:
        """Remove partially-created directories on failure."""
        import shutil
        for d in [reports_dir, os.path.join(self._dispatchers_base, task_id)]:
            if os.path.isdir(d):
                try:
                    shutil.rmtree(d)
                except OSError:
                    pass

    # ------------------------------------------------------------------ #
    # Internal: Task enumeration helpers
    # ------------------------------------------------------------------ #

    def _iter_existing_tasks(self) -> list[dict]:
        """Iterate over existing task directories with basic info."""
        tasks = []
        if not os.path.isdir(self._dispatchers_base):
            return tasks

        for entry in sorted(os.listdir(self._dispatchers_base)):
            match = TASK_ID_PATTERN.match(entry)
            if not match:
                continue
            tasks.append({"task_id": entry})
        return tasks

    def _extract_request_text(self, task_id: str) -> Optional[str]:
        """Extract the user's original request text from a task workspace."""
        reports_dir = os.path.join(
            self.workspace_root, REPORTS_DIR_NAME, task_id
        )

        # Try TASK_REQUEST.md first (new convention)
        request_path = os.path.join(reports_dir, "TASK_REQUEST.md")
        if os.path.exists(request_path):
            return self._read_request_from_task_request(request_path)

        # Fallback: read from the task definition file (e.g., TASK_DS_EO_029.md)
        pattern = re.compile(rf"^{re.escape(task_id)}\.md$", re.IGNORECASE)
        for entry in os.listdir(reports_dir):
            if pattern.match(entry):
                with open(os.path.join(reports_dir, entry)) as f:
                    content = f.read()
                # Extract first non-yaml paragraph
                lines = content.split("\n")
                body_lines = []
                past_yaml = False
                for line in lines:
                    if line.startswith("---"):
                        past_yaml = True
                        continue
                    if past_yaml and line.strip():
                        body_lines.append(line)
                return "\n".join(body_lines)[:500]

        # Last fallback: read OBJECTIVE section from spec file
        for entry in os.listdir(reports_dir):
            if entry.endswith(".md") and "TASK" in entry.upper():
                with open(os.path.join(reports_dir, entry)) as f:
                    content = f.read()
                return content[:500]

        return None

    def _read_request_from_task_request(self, path: str) -> Optional[str]:
        """Extract the verbatim request from a TASK_REQUEST.md file."""
        try:
            with open(path) as f:
                lines = f.readlines()

            # Find content after yaml frontmatter (between --- delimiters)
            in_yaml = True
            past_frontmatter = False
            body_lines = []
            for line in lines:
                if line.strip() == "---":
                    if in_yaml:
                        in_yaml = False
                    else:
                        past_frontmatter = True  # second --- closes frontmatter
                    continue
                if not past_frontmatter:
                    continue
                # Skip headers and metadata table rows — extract only blockquote content
                stripped = line.strip()
                if stripped.startswith("> ") or stripped == "":
                    body_lines.append(line)

            text = "\n".join(body_lines).strip()
            return text[:500] if text else None

        except (OSError, IOError):
            return None

    def _get_task_intake_status(self, task_id: str) -> Optional[str]:
        """Get the current intake status of a task from its MANIFEST.md."""
        reports_dir = os.path.join(
            self.workspace_root, REPORTS_DIR_NAME, task_id
        )
        manifest_path = os.path.join(reports_dir, "MANIFEST.md")

        if not os.path.exists(manifest_path):
            return None

        try:
            with open(manifest_path) as f:
                for line in f:
                    if "**Intake Status**" in line:
                        # Extract the value after |
                        parts = line.split("|")
                        if len(parts) >= 3:
                            return parts[2].strip()
        except (OSError, IOError):
            pass

        return None


    # --------------------------------------------------------------------------- #
    # Convenience function — single-call API for PM agents
    # --------------------------------------------------------------------------- #

def create_task_intake(
    workspace_root: str,
    request_text: str,
    user_files: Optional[list[str]] = None,
    mode: str = "manual",
) -> tuple[bool, dict]:
    """
    One-shot convenience function for PM task intake.

    Creates a TaskIntakeManager and calls create_task_intake().
    
    WARNING: This is designed as a single-invocation entry point for PM agents.
    Once it returns READY_FOR_CTO, it will refuse further calls to enforce
    the role boundary (PM must NOT continue with CTO duties).
    For multiple task creations in the same process, use TaskIntakeManager directly.

    Args:
        workspace_root: DS-EO workspace root path.
        request_text: User's verbatim original request.
        user_files: Optional list of file paths to include.
        mode: "manual" or "automatic".

    Returns:
        (success, result_dict) — same as TaskIntakeManager.create_task_intake().
    """
    _global_boundary.raise_if_complete()
    mgr = TaskIntakeManager(workspace_root=workspace_root)
    success, result = mgr.create_task_intake(
        request_text=request_text,
        user_files=user_files,
        mode=mode,
    )
    if success:
        _global_boundary.mark_complete()
    return success, result
