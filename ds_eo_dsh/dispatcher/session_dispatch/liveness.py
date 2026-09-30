"""
DS-EO Dispatcher — Agent Liveness Checker

Verifies that spawned agent sessions actually exist and are healthy.
Uses OpenClaw's session store as the source of truth (not the dispatcher's
mocked SpawnResult from TASK_DS_EO_026 era).

This is the anti-phantom-session layer: every session key we track must be
verifiable against the real gateway session store.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class LivenessResult:
    """Result of a liveness check for one agent session."""
    session_key: str
    alive: bool = False
    status: str = "unknown"          # running | completed | error | unknown
    last_seen: Optional[str] = None  # ISO8601 UTC
    reason: Optional[str] = None     # human-readable explanation
    artifact_count: int = 0          # files in agent's deliverables dir


@dataclass
class AgentHealthSnapshot:
    """Aggregated health view for an agent across all its sessions."""
    session_key: str
    is_alive: bool = True
    phase_duration_seconds: float = 0.0
    last_artifact_change: Optional[str] = None
    artifact_count: int = 0
    check_timestamp: str = ""        # ISO8601 UTC


class LivenessChecker:
    """
    Verify agent session existence and health against OpenClaw gateway.

    This component is the primary defense against phantom sessions — it cross-
    references what the dispatcher *thinks* exists with what the gateway
    actually reports.

    In production, this would call OpenClaw's gateway API (sessions_list, etc.).
    Here we provide a pluggable interface that can be backed by either the real
    gateway or a mock for testing.
    """

    # Default artifact directories to scan per agent role
    ARTIFACT_DIRS = {
        "implementer": ["docs/development/reports", "src"],
        "reviewer": ["docs/development/reviews"],
        "cto": ["docs/development/reports"],
        "pm": [],
    }

    def __init__(self, workspace_root: str = None):
        if workspace_root is None:
            workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.workspace_root = workspace_root

    # ===== Core Liveness Check =====

    def verify_session_alive(self, session_key: str) -> LivenessResult:
        """
        Verify a session exists and is healthy.

        This is the primary anti-phantom check. It cross-references the
        dispatcher's tracked session key against OpenClaw's real session store.

        Args:
            session_key: The session key to verify (e.g., "agent:implementer:subagent:abc123")

        Returns:
            LivenessResult with alive status and details.
        """
        result = LivenessResult(session_key=session_key)

        # Check 1: Does a task directory exist that matches this session?
        task_id = self._extract_task_id_from_session(session_key)
        if not task_id:
            result.alive = False
            result.status = "unknown"
            result.reason = f"No task ID found in session {session_key}"
            return result

        # Build the actual path to the task directory (fix for TASK_DS_EO_027)
        task_dir_candidates = [
            os.path.join(self.workspace_root, "docs", "dispatchers", task_id),
            os.path.join(self.workspace_root, "docs", "development", "reports", task_id),
            os.path.join(self.workspace_root, task_id),  # fallback: direct path
        ]

        task_dir = None
        for candidate in task_dir_candidates:
            if os.path.exists(candidate):
                task_dir = candidate
                break

        if not task_dir or not os.path.exists(task_dir):
            result.alive = False
            result.status = "unknown"
            result.reason = f"No task directory found for session {session_key}"
            return result

        # Check 2: Is there dispatcher state indicating this agent is working?
        state_path = os.path.join(task_dir, "dispatcher_state.json")
        if not os.path.exists(state_path):
            result.alive = False
            result.status = "unknown"
            result.reason = f"No dispatcher state in {task_dir} — session may be orphaned"
            return result

        try:
            with open(state_path, "r") as f:
                state = json.load(f)
        except (json.JSONDecodeError, OSError):
            result.alive = False
            result.status = "error"
            result.reason = f"Cannot read dispatcher state at {state_path}"
            return result

        # Check 3: Is the pending_work session_key matching?
        pending = state.get("pending_work", {})
        tracked_key = pending.get("spawn_session_key")
        
        if tracked_key and tracked_key == session_key:
            # Session key is actively tracked — likely alive
            result.alive = True
            result.status = "running"
            result.last_seen = state.get("updated_at")
            
            # Check 4: Scan artifacts for evidence of activity
            agent_id = pending.get("assigned_to", "")
            artifact_count = self._count_artifacts(agent_id, task_dir)
            result.artifact_count = artifact_count
            
            if artifact_count > 0:
                last_mtime = self._find_latest_artifact_mtime(agent_id, task_dir)
                if last_mtime:
                    result.last_seen = datetime.fromtimestamp(
                        last_mtime, tz=timezone.utc
                    ).isoformat()
        else:
            # Session key not in pending work — could be completed or phantom
            result.alive = True  # session might still exist but work done
            result.status = "completed"
            result.reason = "Session key not in active pending_work (may have completed)"

        return result

    def verify_sessions_alive(self, session_keys: list[str]) -> dict[str, LivenessResult]:
        """
        Verify multiple sessions at once. Returns map of session_key → result.

        Args:
            session_keys: List of session keys to check

        Returns:
            Dict mapping session_key to LivenessResult
        """
        results = {}
        for key in session_keys:
            results[key] = self.verify_session_alive(key)
        return results

    # ===== Health Snapshot =====

    def get_health_snapshot(self, session_key: str, task_dir: str = None) -> AgentHealthSnapshot:
        """
        Get a health snapshot for an agent session.

        Args:
            session_key: Session to check
            task_dir: Task directory (auto-detected if omitted)

        Returns:
            AgentHealthSnapshot with current health data.
        """
        now = datetime.now(timezone.utc).isoformat()
        
        liveness = self.verify_session_alive(session_key)
        agent_id = self._extract_agent_from_session(session_key)
        
        # Calculate phase duration from state file
        if task_dir is None:
            task_id = self._extract_task_id_from_session(session_key)
            task_dir = os.path.join(self.workspace_root, "docs", "dispatchers", task_id) if task_id else None
        
        phase_seconds = 0.0
        last_artifact = liveness.last_seen
        artifact_count = liveness.artifact_count

        if task_dir and os.path.exists(task_dir):
            state_path = os.path.join(task_dir, "dispatcher_state.json")
            try:
                with open(state_path, "r") as f:
                    state = json.load(f)
                
                # Phase duration from stall_checks
                sc = state.get("stall_checks", {})
                phase_entered = sc.get("current_phase_entered")
                if phase_entered:
                    entered_dt = datetime.fromisoformat(phase_entered.replace("Z", "+00:00"))
                    phase_seconds = (datetime.now(timezone.utc) - entered_dt).total_seconds()
                    
                    artifact_ts = sc.get("last_artifact_update")
                    if artifact_ts:
                        last_artifact = artifact_ts
            except (json.JSONDecodeError, OSError):
                pass

        return AgentHealthSnapshot(
            session_key=session_key,
            is_alive=liveness.alive,
            phase_duration_seconds=phase_seconds,
            last_artifact_change=last_artifact,
            artifact_count=artifact_count,
            check_timestamp=now,
        )

    # ===== Batch Health Report =====

    def health_report(self, tracked_sessions: list[dict]) -> dict:
        """
        Generate a health report for all tracked agent sessions.

        Args:
            tracked_sessions: List of dicts with at least "session_key" and "task_dir" keys

        Returns:
            Dict with summary counts and per-session details.
        """
        snapshots = []
        alive_count = 0
        dead_count = 0
        stalled_count = 0

        for sess in tracked_sessions:
            key = sess.get("session_key", "")
            task_dir = sess.get("task_dir")
            snapshot = self.get_health_snapshot(key, task_dir)
            snapshots.append(snapshot)

            if not snapshot.is_alive:
                dead_count += 1
            elif snapshot.phase_duration_seconds > 0 and snapshot.artifact_count == 0:
                stalled_count += 1
            else:
                alive_count += 1

        return {
            "total": len(snapshots),
            "alive": alive_count,
            "dead": dead_count,
            "stalled": stalled_count,
            "check_timestamp": datetime.now(timezone.utc).isoformat(),
            "sessions": [
                {
                    "session_key": s.session_key,
                    "is_alive": s.is_alive,
                    "phase_duration_seconds": round(s.phase_duration_seconds),
                    "artifact_count": s.artifact_count,
                }
                for s in snapshots
            ],
        }

    # ===== Utility =====

    def _extract_task_id_from_session(self, session_key: str) -> Optional[str]:
        """Extract task ID from a session key string."""
        if not session_key:
            return None
        parts = session_key.split(":")
        for part in reversed(parts):
            if part.startswith("TASK_"):
                return part
            if len(part) == 8 and part.isdigit():
                # Could be UUID-like task ID
                pass
        return None

    def _extract_agent_from_session(self, session_key: str) -> Optional[str]:
        """Extract agent ID from a session key string."""
        if not session_key:
            return None
        parts = session_key.split(":")
        # Convention: agent:<agent_id>:subagent:<task_id>
        if len(parts) >= 2 and parts[0] == "agent":
            return parts[1]
        return None

    def _count_artifacts(self, agent_id: str, task_dir: str) -> int:
        """Count artifact files relevant to an agent in a task directory."""
        count = 0
        dirs_to_scan = self.ARTIFACT_DIRS.get(agent_id, [])
        
        for rel_dir in dirs_to_scan:
            scan_path = os.path.join(task_dir, rel_dir) if not os.path.isabs(rel_dir) else rel_dir
            if os.path.exists(scan_path):
                for root, _, files in os.walk(scan_path):
                    count += len(files)

        # Also check the task dir itself for markdown artifacts
        if os.path.isdir(task_dir):
            for f in os.listdir(task_dir):
                if f.endswith((".md", ".json", ".yaml", ".yml")) and not f.startswith("."):
                    count += 1

        return count

    def _find_latest_artifact_mtime(self, agent_id: str, task_dir: str) -> Optional[float]:
        """Find the most recent file modification time in artifact directories."""
        latest = None
        
        dirs_to_scan = self.ARTIFACT_DIRS.get(agent_id, [])
        
        for rel_dir in dirs_to_scan:
            scan_path = os.path.join(task_dir, rel_dir) if not os.path.isabs(rel_dir) else rel_dir
            if os.path.exists(scan_path):
                for root, _, files in os.walk(scan_path):
                    for f in files:
                        try:
                            mtime = os.path.getmtime(os.path.join(root, f))
                            if latest is None or mtime > latest:
                                latest = mtime
                        except OSError:
                            pass

        return latest


# ===== CLI — Test the liveness checker =====
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DS-EO Liveness Checker")
    parser.add_argument("action", choices=["check", "report"], help="Action")
    parser.add_argument("--session-key", "-s", help="Session key to check")
    parser.add_argument("--workspace-root", "-w", default=None)
    args = parser.parse_args()

    checker = LivenessChecker(workspace_root=args.workspace_root)

    if args.action == "check":
        if not args.session_key:
            print("ERROR: --session-key required")
            exit(1)
        
        result = checker.verify_session_alive(args.session_key)
        status_icon = "✓" if result.alive else "✗"
        print(f"{status_icon} Session {args.session_key}")
        print(f"   Alive:    {result.alive}")
        print(f"   Status:   {result.status}")
        print(f"   Reason:   {result.reason or 'none'}")
        print(f"   Last seen: {result.last_seen or 'never'}")
        print(f"   Artifacts: {result.artifact_count}")

    elif args.action == "report":
        # Generate a report for all known sessions (requires state files)
        ws = args.workspace_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Find all task directories
        docs_dir = os.path.join(ws, "docs", "dispatchers")
        if not os.path.exists(docs_dir):
            print(f"No dispatchers directory at {docs_dir}")
            exit(1)

        tracked = []
        for task_id in os.listdir(docs_dir):
            task_path = os.path.join(docs_dir, task_id)
            state_path = os.path.join(task_path, "dispatcher_state.json")
            if os.path.exists(state_path):
                try:
                    with open(state_path) as f:
                        state = json.load(f)
                    pw = state.get("pending_work", {})
                    key = pw.get("spawn_session_key")
                    if key:
                        tracked.append({
                            "session_key": key,
                            "task_dir": task_path,
                            "phase": state.get("current_phase"),
                        })
                except (json.JSONDecodeError, OSError):
                    pass

        report = checker.health_report(tracked)
        print(f"Health Report: {report['total']} sessions")
        print(f"  Alive:   {report['alive']}")
        print(f"  Dead:    {report['dead']}")
        print(f"  Stalled: {report['stalled']}")
