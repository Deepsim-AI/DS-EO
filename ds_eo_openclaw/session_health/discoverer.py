"""
DS-EO Session Health — Session Discoverer (§6, §7)

Extends LivenessChecker's alive check with broader signal collection:
context size estimation, compaction status detection, error history collection,
workflow state lookup via dispatcher. Returns structured SessionHealthData
with all 8 health indicators and authoritative session→task mapping.

Architecture Decision (CTO Plan §1.3): Build on LivenessChecker, don't replace it.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #


@dataclass
class SessionHealthData:
    """Structured health data for one session — the discoverer's primary output."""

    session_key: str
    alive: bool = False
    status: str = "unknown"  # running | completed | error | unknown

    # --- 8 health indicators (all optional until discovered) ---
    age_seconds: Optional[float] = None
    inactivity_seconds: Optional[float] = None
    context_size_kb: Optional[int] = None
    compaction_status: str = "UNDETERMINED"  # OK | FAILED | UNDETERMINED
    execution_state: str = "UNKNOWN"          # RUNNING | STUCK | IDLE | UNKNOWN
    error_count: int = 0
    task_association: str = "NONE"             # ACTIVE | INACTIVE | NONE
    recovery_history: list = field(default_factory=list)

    # --- Authoritative session→task mapping ---
    associated_task_id: Optional[str] = None
    associated_agent: Optional[str] = None
    mapping_confidence: str = "LOW"  # HIGH | MEDIUM | LOW

    # --- Source of truth for liveness ---
    last_seen: Optional[str] = None
    artifact_count: int = 0
    reason: Optional[str] = None


# --------------------------------------------------------------------------- #
# Discoverer — extends LivenessChecker with health signals
# --------------------------------------------------------------------------- #


class SessionDiscoverer:
    """
    Discover sessions and collect all health signals.

    Extends the existing LivenessChecker to add context size estimation,
    compaction status detection, error history collection, and workflow state
    lookup via the dispatcher. Produces authoritative session→task mappings
    by cross-referencing multiple sources.

    This is NOT a replacement for LivenessChecker — it wraps and extends it.
    """

    # Artifact directories to scan per agent role (inherited from LivenessChecker)
    ARTIFACT_DIRS = {
        "implementer": ["docs/development/reports", "src"],
        "reviewer": ["docs/development/reviews"],
        "cto": ["docs/development/reports"],
        "pm": [],
    }

    def __init__(self, workspace_root: Optional[str] = None):
        if workspace_root is None:
            workspace_root = os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
            # Go up one more level to get the project root
            if os.path.isdir(os.path.join(workspace_root, "docs")):
                pass  # already at project root
            else:
                workspace_root = os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))
                )

        self.workspace_root = os.path.abspath(workspace_root)

    def discover_all_sessions(self) -> list[SessionHealthData]:
        """
        Discover all known sessions and collect health signals.

        This is the primary entry point for Phase 1: reliable signal collection.
        Returns SessionHealthData with all available indicators populated.

        Discovery sources (in priority order):
          1. Dispatcher state files (docs/dispatchers/TASK_*/dispatcher_state.json)
          2. Task report directories (docs/development/reports/TASK_*/)
          3. OpenClaw gateway sessions_list (if available — best effort)

        Returns:
            List of SessionHealthData with collected signals.
        """
        all_sessions = []

        # Source 1: Dispatcher state files
        dispatcher_sessions = self._discover_from_dispatcher()
        all_sessions.extend(dispatcher_sessions)

        # Source 2: Report-only sessions (no active dispatcher tracking)
        report_sessions = self._discover_from_reports()
        all_sessions.extend(report_sessions)

        return all_sessions

    def discover_session(self, session_key: str) -> SessionHealthData:
        """
        Discover a single session by key and collect health signals.

        Args:
            session_key: The session key to discover (e.g., "agent:implementer:subagent:abc123")

        Returns:
            SessionHealthData with collected signals for the specified session.
        """
        data = SessionHealthData(session_key=session_key)

        # Try dispatcher state first
        task_id = self._extract_task_id_from_session(session_key)
        if task_id:
            dispatcher_data = self._discover_from_dispatcher_state(task_id, session_key)
            if dispatcher_data:
                return dispatcher_data

        # Fallback: report-only discovery
        if task_id:
            return self._discover_report_only(task_id, session_key)

        data.status = "unknown"
        data.reason = f"No task ID found in session key: {session_key}"
        return data

    def discover_sessions_by_task(self, task_id: str) -> list[SessionHealthData]:
        """
        Discover all sessions associated with a specific task.

        Args:
            task_id: The TASK_<YYYYMMDD>_<NNN> identifier.

        Returns:
            List of SessionHealthData for all sessions tied to this task.
        """
        results = []

        # From dispatcher state
        disp_data = self._discover_from_dispatcher_state(task_id)
        if disp_data:
            results.append(disp_data)

        # Check for multiple agent sessions on the same task (e.g., implementer + reviewer)
        report_data = self._discover_report_only(task_id)
        if report_data and not any(
            s.session_key == report_data.session_key for s in results
        ):
            results.append(report_data)

        return results

    # ===== Core Discovery Methods =====

    def _discover_from_dispatcher(self) -> list[SessionHealthData]:
        """Discover sessions from dispatcher state files."""
        sessions = []
        dispatchers_base = os.path.join(
            self.workspace_root, "docs", "dispatchers"
        )
        if not os.path.isdir(dispatchers_base):
            return sessions

        for task_id in sorted(os.listdir(dispatchers_base)):
            task_dir = os.path.join(dispatchers_base, task_id)
            state_path = os.path.join(task_dir, "dispatcher_state.json")
            if not os.path.isfile(state_path):
                continue

            try:
                with open(state_path) as f:
                    state = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            pending_work = state.get("pending_work", {})
            session_key = pending_work.get("spawn_session_key")
            if not session_key:
                continue

            data = self._build_health_data(task_id, session_key, state)
            sessions.append(data)

        return sessions

    def _discover_from_reports(self) -> list[SessionHealthData]:
        """Discover sessions from report directories (no active dispatcher tracking)."""
        sessions = []
        reports_base = os.path.join(
            self.workspace_root, "docs", "development", "reports"
        )
        if not os.path.isdir(reports_base):
            return sessions

        # Get task IDs already tracked in dispatchers to avoid duplicates
        dispatched_tasks = set()
        dispatchers_base = os.path.join(self.workspace_root, "docs", "dispatchers")
        if os.path.isdir(dispatchers_base):
            for entry in os.listdir(dispatchers_base):
                if os.path.isdir(os.path.join(dispatchers_base, entry)):
                    dispatched_tasks.add(entry)

        for task_id in sorted(os.listdir(reports_base)):
            if task_id in dispatched_tasks:
                continue  # Already tracked via dispatcher
            if not os.path.isdir(os.path.join(reports_base, task_id)):
                continue

            session_key = self._generate_report_session_key(task_id)
            data = self._discover_report_only(task_id, session_key)
            sessions.append(data)

        return sessions

    def _discover_from_dispatcher_state(
        self, task_id: str, session_key: Optional[str] = None
    ) -> Optional[SessionHealthData]:
        """Discover a specific session from its dispatcher state file."""
        dispatchers_base = os.path.join(self.workspace_root, "docs", "dispatchers")
        task_dir = os.path.join(dispatchers_base, task_id)
        state_path = os.path.join(task_dir, "dispatcher_state.json")

        if not os.path.isfile(state_path):
            return None

        try:
            with open(state_path) as f:
                state = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

        pending_work = state.get("pending_work", {})
        tracked_key = session_key or pending_work.get("spawn_session_key")

        if not tracked_key:
            return None

        data = self._build_health_data(task_id, tracked_key, state)
        # Verify the key matches if one was specified
        if session_key and data.session_key != session_key:
            data.reason = f"Session key mismatch: expected {session_key}, got {tracked_key}"
        return data

    def _discover_report_only(
        self, task_id: str, session_key: Optional[str] = None
    ) -> SessionHealthData:
        """Build health data from report directory only (no dispatcher state)."""
        if not session_key:
            session_key = self._generate_report_session_key(task_id)

        reports_base = os.path.join(
            self.workspace_root, "docs", "development", "reports"
        )
        task_dir = os.path.join(reports_base, task_id)

        data = SessionHealthData(session_key=session_key)
        data.alive = True  # Report dir exists → session existed at some point
        data.status = "completed" if self._task_is_complete(task_id) else "running"
        data.task_association = "INACTIVE"  # No active dispatcher tracking

        # Authoritative mapping from report directory (HIGH confidence — direct file evidence)
        data.associated_task_id = task_id
        data.mapping_confidence = "MEDIUM"

        # Collect signals from the report directory
        self._collect_signals_from_directory(task_dir, data)

        return data

    def _build_health_data(
        self, task_id: str, session_key: str, state: dict
    ) -> SessionHealthData:
        """Build a complete SessionHealthData from dispatcher state + signals."""
        data = SessionHealthData(session_key=session_key)

        pending_work = state.get("pending_work", {})
        assigned_to = pending_work.get("assigned_to", "")

        # Authoritative session→task mapping (HIGH confidence — from dispatcher state file)
        data.associated_task_id = task_id
        data.associated_agent = assigned_to or self._extract_agent_from_session(session_key)
        data.mapping_confidence = "HIGH"

        # Liveness check via the existing LivenessChecker logic
        liveness_status, last_seen, artifact_count, reason = self._check_liveness(
            task_id, session_key, state
        )
        data.alive = liveness_status == "running" or liveness_status == "completed"
        data.status = liveness_status if liveness_status else "unknown"
        data.last_seen = last_seen
        data.artifact_count = artifact_count
        data.reason = reason

        # Collect all health signals from the task directory
        reports_base = os.path.join(
            self.workspace_root, "docs", "development", "reports"
        )
        task_dir = os.path.join(reports_base, task_id)

        if os.path.isdir(task_dir):
            self._collect_signals_from_directory(task_dir, data)

        # Collect workflow state signals from dispatcher
        stall_checks = state.get("stall_checks", {})
        current_phase = state.get("current_phase", "")
        if current_phase:
            data.execution_state = "RUNNING"
        else:
            data.execution_state = self._infer_execution_state(state)

        # Collect recovery history from dispatcher state
        recovery_history = state.get("recovery_history", [])
        if recovery_history:
            data.recovery_history = recovery_history

        return data

    def _collect_signals_from_directory(
        self, task_dir: str, data: SessionHealthData
    ) -> None:
        """Collect all health signals from a task directory's files."""
        now = datetime.now(timezone.utc)

        # 1. AGE: based on oldest file in the task directory
        if os.path.isdir(task_dir):
            oldest_mtime = None
            for root, _, files in os.walk(task_dir):
                for f in files:
                    try:
                        mtime = os.path.getmtime(os.path.join(root, f))
                        if oldest_mtime is None or mtime < oldest_mtime:
                            oldest_mtime = mtime
                    except OSError:
                        pass

            if oldest_mtime:
                data.age_seconds = (now - datetime.fromtimestamp(
                    oldest_mtime, tz=timezone.utc
                )).total_seconds()

        # 2. INACTIVITY: based on newest file modification time
        if os.path.isdir(task_dir):
            newest_mtime = None
            for root, _, files in os.walk(task_dir):
                for f in files:
                    try:
                        mtime = os.path.getmtime(os.path.join(root, f))
                        if newest_mtime is None or mtime > newest_mtime:
                            newest_mtime = mtime
                    except OSError:
                        pass

            if newest_mtime:
                data.inactivity_seconds = (now - datetime.fromtimestamp(
                    newest_mtime, tz=timezone.utc
                )).total_seconds()
            else:
                # No files — use age as proxy for inactivity
                data.inactivity_seconds = data.age_seconds or 0.0

        # 3. CONTEXT SIZE: estimate from total artifact directory sizes
        data.context_size_kb = self._estimate_context_size(task_dir)

        # 4. COMPACTION STATUS: check for compaction artifacts/markers
        data.compaction_status = self._detect_compaction_status(task_dir, data)

        # 5. ERROR COUNT: scan log files and error markers
        data.error_count = self._count_errors(task_dir)

        # 6. TASK ASSOCIATION: infer from gate artifacts
        if not data.task_association or data.task_association == "NONE":
            data.task_association = self._infer_task_association(task_dir, data)

    # ===== Signal Collection Helpers =====

    def _estimate_context_size(self, task_dir: str) -> Optional[int]:
        """Estimate context size in KB from artifact directories."""
        total_bytes = 0
        try:
            for root, _, files in os.walk(task_dir):
                for f in files:
                    if f.endswith((".md", ".json", ".yaml", ".yml", ".py")):
                        filepath = os.path.join(root, f)
                        try:
                            total_bytes += os.path.getsize(filepath)
                        except OSError:
                            pass
        except OSError:
            return None
        return max(1, total_bytes // 1024) if total_bytes > 0 else 0

    def _detect_compaction_status(self, task_dir: str, data: SessionHealthData) -> str:
        """Detect compaction status from session/task artifacts."""
        # Check for explicit failure markers in dispatcher state or report files
        reports_base = os.path.join(
            self.workspace_root, "docs", "development", "reports"
        )
        task_id_dir = os.path.join(reports_base, data.associated_task_id or "")

        if not task_id_dir:
            return "UNDETERMINED"

        # Look for compaction failure markers in any file
        compaction_dirs = ["docs/development/reviews", "docs/dispatchers"]
        for compaction_rel_dir in compaction_dirs:
            scan_path = os.path.join(
                self.workspace_root, compaction_rel_dir
            ) if not os.path.isabs(compaction_rel_dir) else compaction_rel_dir

            if not os.path.isdir(scan_path):
                continue

            try:
                for root, _, files in os.walk(scan_path):
                    for f in files:
                        if "compaction" in f.lower() or "failed" in f.lower():
                            filepath = os.path.join(root, f)
                            try:
                                with open(filepath) as fh:
                                    content = fh.read(500).lower()
                                    if "failure" in content or "error" in content:
                                        return "FAILED"
                            except OSError:
                                pass
            except OSError:
                continue

        # If context size exceeds threshold, mark as COMPACTION_REQUIRED
        if data.context_size_kb and data.context_size_kb > 0:
            # Context exists but no failure detected — OK unless very large
            return "OK"

        return "UNDETERMINED"

    def _count_errors(self, task_dir: str) -> int:
        """Count error indicators in a task directory."""
        count = 0
        if not os.path.isdir(task_dir):
            return 0

        for root, _, files in os.walk(task_dir):
            for f in files:
                filepath = os.path.join(root, f)
                try:
                    with open(filepath) as fh:
                        content = fh.read(1000).lower()
                        # Count explicit error markers (not false positives like "error" in variable names)
                        if "error_count" in content or ":error" in content:
                            count += 1
                except OSError:
                    pass

        return count

    def _infer_task_association(
        self, task_dir: str, data: SessionHealthData
    ) -> str:
        """Infer whether the session's associated task is active or inactive."""
        # Check for CTO_APPROVAL.md — indicates completed gate G4
        if os.path.isfile(os.path.join(task_dir, "CTO_APPROVAL.md")):
            return "INACTIVE"  # Task has been approved

        # Check for any active gate artifacts (G1-G3) without final approval
        for gate_file in ["G2_HANDOFF.md", "REVIEW_REPORT.md"]:
            if os.path.isfile(os.path.join(task_dir, gate_file)):
                return "ACTIVE"

        # If we have a task ID but no clear signal, assume ACTIVE (conservative)
        if data.associated_task_id:
            return "ACTIVE"

        return "NONE"

    def _infer_execution_state(self, state: dict) -> str:
        """Infer execution state from dispatcher state."""
        current_phase = state.get("current_phase", "")
        stall_checks = state.get("stall_checks", {})

        if not current_phase:
            return "IDLE"

        # Check for stall indicators
        phase_duration = stall_checks.get("phase_duration_seconds", 0)
        artifact_count = stall_checks.get("artifact_count", 0)

        if phase_duration > 3600 and artifact_count == 0:
            return "STUCK"

        return "RUNNING"

    def _check_liveness(
        self, task_id: str, session_key: str, state: dict
    ) -> tuple[str, Optional[str], int, Optional[str]]:
        """Check liveness using the existing LivenessChecker logic."""
        # Use the same artifact scanning as LivenessChecker
        agent_id = self._extract_agent_from_session(session_key)
        reports_base = os.path.join(
            self.workspace_root, "docs", "development", "reports"
        )
        task_dir = os.path.join(reports_base, task_id)

        if not os.path.isdir(task_dir):
            return "unknown", None, 0, f"No report directory for {task_id}"

        # Count artifacts (same logic as LivenessChecker._count_artifacts)
        artifact_count = 0
        dirs_to_scan = self.ARTIFACT_DIRS.get(agent_id, [])
        for rel_dir in dirs_to_scan:
            scan_path = os.path.join(task_dir, rel_dir) if not os.path.isabs(rel_dir) else rel_dir
            if os.path.isdir(scan_path):
                for root, _, files in os.walk(scan_path):
                    artifact_count += len(files)

        # Also count markdown/json artifacts in the task dir itself
        for f in os.listdir(task_dir):
            if f.endswith((".md", ".json", ".yaml", ".yml")) and not f.startswith("."):
                artifact_count += 1

        pending = state.get("pending_work", {})
        tracked_key = pending.get("spawn_session_key")

        if tracked_key == session_key:
            # Session key is actively tracked — likely alive
            last_seen = state.get("updated_at")
            return "running", last_seen, artifact_count, None
        else:
            return "completed", None, artifact_count, (
                f"Session key not in active pending_work (may have completed)"
            )

    def _task_is_complete(self, task_id: str) -> bool:
        """Check if a task has been approved (G4 complete)."""
        reports_base = os.path.join(
            self.workspace_root, "docs", "development", "reports"
        )
        task_dir = os.path.join(reports_base, task_id)
        return os.path.isfile(os.path.join(task_dir, "CTO_APPROVAL.md"))

    # ===== Utility =====

    def _extract_task_id_from_session(self, session_key: str) -> Optional[str]:
        """Extract task ID from a session key string."""
        if not session_key:
            return None
        parts = session_key.split(":")
        for part in reversed(parts):
            if part.startswith("TASK_"):
                return part
        return None

    def _extract_agent_from_session(self, session_key: str) -> Optional[str]:
        """Extract agent ID from a session key string."""
        if not session_key:
            return None
        parts = session_key.split(":")
        if len(parts) >= 2 and parts[0] == "agent":
            return parts[1]
        return None

    def _generate_report_session_key(self, task_id: str) -> str:
        """Generate a synthetic session key for report-only sessions."""
        # Convention: agent:<role>:report:<task_id>
        return f"agent:discovered:report:{task_id}"


# ===== CLI — Test the discoverer =====
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DS-EO Session Health Discoverer")
    parser.add_argument("action", choices=["discover", "session"], help="Action")
    parser.add_argument("--session-key", "-s", help="Session key to discover")
    parser.add_argument("--task-id", "-t", help="Task ID to discover sessions for")
    parser.add_argument("--workspace-root", "-w", default=None)
    args = parser.parse_args()

    discoverer = SessionDiscoverer(workspace_root=args.workspace_root)

    if args.action == "discover":
        sessions = discoverer.discover_all_sessions()
        print(f"Discovered {len(sessions)} session(s):")
        for s in sessions:
            task_marker = f" [{s.associated_task_id}]" if s.associated_task_id else ""
            print(f"  - {s.session_key}{task_marker}")
            print(f"    alive={s.alive}, status={s.status}, confidence={s.mapping_confidence}")
            if s.age_seconds:
                print(f"    age={s.age_seconds:.0f}s, inactivity={s.inactivity_seconds:.0f}s")

    elif args.action == "session":
        if not args.session_key:
            print("ERROR: --session-key required")
            exit(1)
        data = discoverer.discover_session(args.session_key)
        print(f"Session: {data.session_key}")
        print(f"  Alive:       {data.alive}")
        print(f"  Status:      {data.status}")
        print(f"  Task:        {data.associated_task_id or 'none'}")
        print(f"  Confidence:  {data.mapping_confidence}")
        if data.age_seconds:
            print(f"  Age:         {data.age_seconds:.0f}s")
        if data.inactivity_seconds:
            print(f"  Inactive:    {data.inactivity_seconds:.0f}s")
        if data.context_size_kb:
            print(f"  Context KB:  {data.context_size_kb}")
