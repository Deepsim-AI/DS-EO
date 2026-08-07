"""
DS-EO Dispatcher — Workflow Supervisor / Watchdog

Provides reliability layer for automatic mode: heartbeat monitoring, progress
detection, timeout enforcement, retry/recovery, and user escalation.

This is the anti-stall/anti-failure layer that prevents silent pipeline failures.
Only active in automatic mode; observer-only in manual mode.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# Import our liveness checker (same package)
from .liveness import LivenessChecker, LivenessResult


# ====================================================================
# Data Types
# ====================================================================

@dataclass
class HeartbeatResult:
    """Result of a single heartbeat check on an agent."""
    session_key: str
    ok: bool = True
    status: str = "ok"                 # ok | no_progress | stalled | dead
    time_since_last_progress_seconds: float = 0.0
    artifact_age_seconds: float = 0.0
    reason: Optional[str] = None


@dataclass
class SupervisorEvent:
    """A notification-worthy event from the supervisor."""
    type: str                      # STALL_DETECTED | RETRY_INITIATED | ESCALATION | COMPLETION | ABORT
    severity: str                  # INFO | WARNING | CRITICAL
    session_key: Optional[str] = None
    task_id: Optional[str] = None
    phase: Optional[str] = None
    message: str = ""
    agent_summary: dict = field(default_factory=dict)
    timestamp: str = ""            # ISO8601 UTC
    actionable_commands: list = field(default_factory=list)  # e.g. ["/eo.retry", "/eo.abort"]


@dataclass
class RecoveryResult:
    """Result of a recovery attempt on a stalled agent."""
    success: bool = False
    action_taken: str = ""         # retried | escalated | aborted
    new_session_key: Optional[str] = None
    retry_number: int = 0
    reason: Optional[str] = None


@dataclass
class SupervisorConfig:
    """Configuration for the supervisor."""
    heartbeat_interval_seconds: int = 60
    no_progress_timeout_seconds: int = 300
    hard_timeout_seconds: int = 900
    retry_attempts: int = 2
    retry_backoff_seconds: list = field(default_factory=lambda: [60, 180])
    alert_on_first_stall: bool = True
    notification_channels: list = field(default_factory=lambda: ["webchat"])


@dataclass
class TaskSupervisorState:
    """Per-task supervisor tracking state."""
    task_id: str
    overlay_state: str = "SUPERVISING"  # SUPERVISING | AGENT_STALLED | AGENT_FAILED | HUMAN_INTERVENTION | TASK_ABORTED
    mode: str = "automatic"            # automatic | manual
    agents: dict = field(default_factory=dict)   # session_key → AgentState
    events: list = field(default_factory=list)   # SupervisorEvent log
    last_heartbeat_at: Optional[str] = None      # ISO8601 UTC
    retry_count: int = 0                 # current retry attempt number


@dataclass
class AgentState:
    """Per-agent tracking state within the supervisor."""
    session_key: str
    agent_id: str
    phase: str
    spawned_at: str                      # ISO8601 UTC
    last_progress_at: Optional[str]      # ISO8601 UTC
    artifact_baseline: dict = field(default_factory=dict)  # filepath → (hash, mtime)
    retry_count: int = 0
    state: str = "RUNNING"               # RUNNING | NO_PROGRESS | STALLED | FAILED | COMPLETED


# ====================================================================
# Supervisor — Core Watchdog
# ====================================================================

class WorkflowSupervisor:
    """
    Monitor and enforce reliability for DS-EO automatic mode tasks.

    The supervisor runs alongside the workflow engine, watching spawned agent
    sessions for progress. When an agent stalls (no artifact changes), it
    retries; when retries are exhausted or hard timeout hits, it escalates to
    the user with a full summary.

    Key invariant: Supervisor only auto-recovers in automatic mode. In manual
    mode it warns but never triggers automated recovery.
    """

    # Overlay states that map to supervisor actions
    OVERLAY_STATES = [
        "SUPERVISING", "AGENT_STALLED", "AGENT_FAILED",
        "HUMAN_INTERVENTION", "TASK_ABORTED"
    ]

    def __init__(
        self,
        config: SupervisorConfig = None,
        workspace_root: str = None,
        liveness_checker: LivenessChecker = None,
    ):
        self.config = config or SupervisorConfig()
        
        if workspace_root is None:
            workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.workspace_root = workspace_root

        self.liveness = liveness_checker or LivenessChecker(workspace_root=workspace_root)

        # In-memory tracking of active supervisor states (per task_id)
        self._task_states: dict[str, TaskSupervisorState] = {}

    # ===== Lifecycle Management =====

    def start_supervising(self, task_id: str, mode: str = "automatic") -> bool:
        """
        Begin Supervisor monitoring for a task.

        Args:
            task_id: The task to supervise
            mode: "automatic" (full lifecycle) or "manual" (observer-only)

        Returns:
            True if supervision started successfully.
        """
        now = datetime.now(timezone.utc).isoformat()

        state = TaskSupervisorState(
            task_id=task_id,
            overlay_state="SUPERVISING",
            mode=mode,
            last_heartbeat_at=now,
        )
        self._task_states[task_id] = state

        event = SupervisorEvent(
            type="COMPLETION",
            severity="INFO",
            task_id=task_id,
            message=f"Supervisor started in {mode} mode for {task_id}",
            timestamp=now,
        )
        state.events.append(event)

        return True

    def stop_supervising(self, task_id: str) -> bool:
        """Stop monitoring a task (cleanup)."""
        if task_id not in self._task_states:
            return False
        
        del self._task_states[task_id]
        return True

    # ===== Heartbeat / Progress Detection =====

    def check_agent_liveness(self, agent_session_key: str) -> LivenessResult:
        """
        Verify an agent session exists and is healthy.

        This is the primary liveness check — cross-references the dispatcher's
        tracked session key against reality (file evidence + state files).

        Args:
            agent_session_key: Session key to verify

        Returns:
            LivenessResult with alive status and details.
        """
        return self.liveness.verify_session_alive(agent_session_key)

    def detect_stall(self, task_id: str) -> tuple[list[str], dict]:
        """
        Run heartbeat check against all active agents for a task.

        Returns:
            (stalled_agent_keys, progress_report)
        """
        ts = self._task_states.get(task_id)
        if not ts:
            return [], {"error": f"No supervisor state for task {task_id}"}

        stalled_agents = []
        progress_report = {}

        now = datetime.now(timezone.utc)

        for session_key, agent_state in ts.agents.items():
            hb = self._run_heartbeat(agent_state, now)
            progress_report[session_key] = {
                "status": hb.status,
                "time_since_progress_seconds": round(hb.time_since_last_progress_seconds),
                "artifact_age_seconds": round(hb.artifact_age_seconds),
            }

            if hb.ok:
                continue

            stalled_agents.append(session_key)

            # Update agent state based on heartbeat result
            if hb.status == "dead":
                agent_state.state = "FAILED"
            elif hb.status == "no_progress":
                agent_state.state = "NO_PROGRESS"
            else:
                agent_state.state = "STALLED"

        ts.last_heartbeat_at = now.isoformat()
        
        # Update overlay state if we have stalled agents
        if stalled_agents and ts.overlay_state in ("SUPERVISING",):
            ts.overlay_state = "AGENT_STALLED"
            self._emit_event(ts, SupervisorEvent(
                type="STALL_DETECTED",
                severity="WARNING",
                message=f"{len(stalled_agents)} agent(s) stalled: {', '.join(stalled_agents[:3])}",
                timestamp=now.isoformat(),
            ))

        return stalled_agents, progress_report

    def _run_heartbeat(self, agent_state: AgentState, now: datetime) -> HeartbeatResult:
        """Run a single heartbeat check for one agent."""
        hb = HeartbeatResult(session_key=agent_state.session_key)

        # Step 1: Verify session is alive
        liveness = self.liveness.verify_session_alive(agent_state.session_key)
        
        if not liveness.alive:
            hb.ok = False
            hb.status = "dead"
            hb.reason = f"Session {agent_state.session_key} is dead or phantom"
            return hb

        # Step 2: Check progress timeout (no-progress detection)
        time_since_progress = self._time_since_last_progress(agent_state, now)
        
        if time_since_progress > self.config.no_progress_timeout_seconds:
            hb.ok = False
            hb.status = "no_progress"
            hb.time_since_last_progress_seconds = time_since_progress
            
            # Check artifact age as secondary indicator
            if agent_state.last_progress_at:
                last_dt = datetime.fromisoformat(agent_state.last_progress_at.replace("Z", "+00:00"))
                hb.artifact_age_seconds = (now - last_dt).total_seconds()

        # Step 3: Check hard timeout (phase duration)
        spawned_dt = datetime.fromisoformat(agent_state.spawned_at.replace("Z", "+00:00"))
        phase_duration = (now - spawned_dt).total_seconds()

        if phase_duration > self.config.hard_timeout_seconds and hb.ok:
            hb.ok = False
            hb.status = "stalled"
            hb.time_since_last_progress_seconds = phase_duration
            hb.reason = f"Hard timeout exceeded: {phase_duration:.0f}s > {self.config.hard_timeout_seconds}s"

        return hb

    def _time_since_last_progress(self, agent_state: AgentState, now: datetime) -> float:
        """Calculate seconds since last detected progress for an agent."""
        if not agent_state.last_progress_at:
            # No progress recorded at all — use spawn time as baseline
            spawned_dt = datetime.fromisoformat(agent_state.spawned_at.replace("Z", "+00:00"))
            return (now - spawned_dt).total_seconds()

        last_dt = datetime.fromisoformat(agent_state.last_progress_at.replace("Z", "+00:00"))
        return (now - last_dt).total_seconds()

    def record_artifact_change(self, session_key: str, task_id: str) -> bool:
        """
        Record that an artifact was changed for a tracked agent.

        Called when the supervisor detects new/changed files in an agent's
        deliverables directory. This resets the no-progress timer.

        Args:
            session_key: Agent session key
            task_id: Task ID

        Returns:
            True if the record was updated, False if not tracked.
        """
        ts = self._task_states.get(task_id)
        if not ts or session_key not in ts.agents:
            return False

        agent_state = ts.agents[session_key]
        now_iso = datetime.now(timezone.utc).isoformat()
        
        # Update last progress timestamp
        agent_state.last_progress_at = now_iso
        
        # Clear no-progress state if we were in it
        if agent_state.state == "NO_PROGRESS":
            agent_state.state = "RUNNING"

        return True

    def scan_and_record_artifacts(self, session_key: str, task_id: str) -> bool:
        """
        Scan deliverable directory for artifacts and record baseline/changes.

        Args:
            session_key: Agent session key
            task_id: Task ID

        Returns:
            True if artifacts were found and recorded.
        """
        ts = self._task_states.get(task_id)
        if not ts or session_key not in ts.agents:
            return False

        agent_state = ts.agents[session_key]
        
        # Extract task directory from session key
        task_dir = self._find_task_directory(task_id)
        if not task_dir:
            return False

        # Scan for markdown artifacts (our convention for deliverables)
        new_artifacts = {}
        artifact_dirs = ["docs/development/reports", "docs/dispatchers"]
        
        for rel_dir in artifact_dirs:
            scan_path = os.path.join(task_dir, rel_dir) if not os.path.isabs(rel_dir) else rel_dir
            if os.path.exists(scan_path):
                for root, _, files in os.walk(scan_path):
                    for f in files:
                        if f.endswith((".md", ".json")) and not f.startswith("."):
                            full_path = os.path.join(root, f)
                            try:
                                mtime = os.path.getmtime(full_path)
                                new_artifacts[full_path] = {
                                    "size": os.path.getsize(full_path),
                                    "mtime": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
                                }
                            except OSError:
                                pass

        if not new_artifacts:
            return False

        # Check for changes vs baseline
        changed = False
        if agent_state.artifact_baseline:
            old_keys = set(agent_state.artifact_baseline.keys())
            new_keys = set(new_artifacts.keys())
            
            added = new_keys - old_keys
            removed = old_keys - new_keys
            
            if added or removed:
                changed = True

        # Update baseline
        agent_state.artifact_baseline = {k: v["mtime"] for k, v in new_artifacts.items()}
        
        if changed and not agent_state.last_progress_at:
            agent_state.last_progress_at = datetime.now(timezone.utc).isoformat()
        elif changed:
            # Compare mtime strings to detect actual changes
            for key in set(agent_state.artifact_baseline.keys()):
                current_mtime = new_artifacts.get(key, {}).get("mtime", "")
                old_mtime = agent_state.artifact_baseline.get(key, "")
                if current_mtime != old_mtime and current_mtime:
                    agent_state.last_progress_at = datetime.now(timezone.utc).isoformat()
                    break

        return True

    # ===== Retry and Recovery =====

    def attempt_recovery(self, task_id: str, stalled_session_key: str) -> RecoveryResult:
        """
        Attempt to recover a stalled agent.

        Strategy depends on mode and retry configuration:
        - Automatic mode: re-dispatch with original prompt + stall context
        - Manual mode: just notify user (no auto-retry)
        
        Args:
            task_id: Task ID
            stalled_session_key: Session key of the stalled agent

        Returns:
            RecoveryResult with action taken.
        """
        ts = self._task_states.get(task_id)
        if not ts:
            return RecoveryResult(success=False, reason=f"No supervisor state for {task_id}")

        # Manual mode: no automated recovery
        if ts.mode == "manual":
            self._emit_event(ts, SupervisorEvent(
                type="ESCALATION",
                severity="WARNING",
                session_key=stalled_session_key,
                task_id=task_id,
                message=f"Agent stalled in manual mode — user must recover manually. Session: {stalled_session_key}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                actionable_commands=["/eo.retry", "/eo.abort"],
            ))
            return RecoveryResult(
                success=False,
                action_taken="not_recovered_manual_mode",
                reason="Manual mode — no automated recovery. User must intervene.",
            )

        # Check retry budget
        agent_state = ts.agents.get(stalled_session_key)
        if not agent_state:
            return RecoveryResult(success=False, reason=f"Agent state not found for {stalled_session_key}")

        max_retries = self.config.retry_attempts
        
        if agent_state.retry_count >= max_retries:
            # Retries exhausted — escalate to human
            ts.overlay_state = "HUMAN_INTERVENTION"
            
            report_path = os.path.join(self.workspace_root, "docs", "dispatchers", task_id)
            summary = self._generate_escalation_report(task_id, agent_state, report_path)
            
            self._emit_event(ts, SupervisorEvent(
                type="ESCALATION",
                severity="CRITICAL",
                session_key=stalled_session_key,
                task_id=task_id,
                phase=agent_state.phase,
                message=f"Agent stalled after {max_retries} retries. Full report generated.",
                agent_summary=summary,
                timestamp=datetime.now(timezone.utc).isoformat(),
                actionable_commands=["/eo.retry", "/eo.abort", "/eo.continue"],
            ))

            return RecoveryResult(
                success=False,
                action_taken="escalated_to_human",
                reason=f"Retries exhausted ({max_retries}). Escalation report generated.",
            )

        # Attempt retry with exponential backoff
        agent_state.retry_count += 1
        ts.retry_count = agent_state.retry_count
        
        backoff_idx = min(agent_state.retry_count - 1, len(self.config.retry_backoff_seconds) - 1)
        backoff_seconds = self.config.retry_backoff_seconds[backoff_idx]

        # Build retry prompt with stall context
        retry_prompt = self._build_retry_prompt(task_id, agent_state, stalled_session_key)
        
        new_session_key = f"agent:{agent_state.agent_id}:subagent:retry{agent_state.retry_count}:{task_id}"

        event = SupervisorEvent(
            type="RETRY_INITIATED",
            severity="INFO",
            session_key=stalled_session_key,
            task_id=task_id,
            message=f"Retry #{agent_state.retry_count} for {agent_state.agent_id} (backoff: {backoff_seconds}s)",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        ts.events.append(event)

        # Update agent state for new session
        now_iso = datetime.now(timezone.utc).isoformat()
        ts.agents[new_session_key] = AgentState(
            session_key=new_session_key,
            agent_id=agent_state.agent_id,
            phase=agent_state.phase,
            spawned_at=now_iso,
            last_progress_at=None,
            artifact_baseline={},  # Fresh baseline for retry
        )

        return RecoveryResult(
            success=True,
            action_taken="retried",
            new_session_key=new_session_key,
            retry_number=agent_state.retry_count,
        )

    def abort_task(self, task_id: str) -> RecoveryResult:
        """
        Abort a task — clear all sessions and write failure report.

        Args:
            task_id: Task to abort

        Returns:
            RecoveryResult with abort details.
        """
        ts = self._task_states.get(task_id)
        if not ts:
            return RecoveryResult(success=False, reason=f"No supervisor state for {task_id}")

        now_iso = datetime.now(timezone.utc).isoformat()
        
        # Mark all agents as aborted
        for session_key, agent_state in ts.agents.items():
            agent_state.state = "FAILED"
            self._cleanup_agent_session(session_key)

        # Update overlay state
        ts.overlay_state = "TASK_ABORTED"
        
        # Generate failure report
        report_path = os.path.join(self.workspace_root, "docs", "dispatchers", task_id)
        summary = self._generate_failure_report(task_id, ts, report_path)

        event = SupervisorEvent(
            type="ABORT",
            severity="WARNING",
            task_id=task_id,
            message=f"Task aborted by supervisor. {summary.get('work_completed', 0)} of {summary.get('total_required', 0)} deliverables produced.",
            agent_summary=summary,
            timestamp=now_iso,
        )
        ts.events.append(event)

        # Persist the failure report
        self._write_failure_report(task_id, summary, report_path)

        return RecoveryResult(
            success=True,
            action_taken="aborted",
            reason=f"Task aborted. {summary.get('work_completed', 0)} deliverables produced before abort.",
        )

    # ===== User Notifications =====

    def format_notification(self, event: SupervisorEvent) -> str:
        """
        Format a supervisor event for user notification.

        Args:
            event: The event to format

        Returns:
            Formatted notification string.
        """
        severity_icons = {
            "CRITICAL": "🚨",
            "WARNING": "⚠️",
            "INFO": "ℹ️",
        }
        icon = severity_icons.get(event.severity, "📋")

        lines = [f"{icon} **DS-EO Supervisor** — {event.type.replace('_', ' ').title()}"]
        
        if event.task_id:
            lines.append(f"Task: `{event.task_id}`")
        if event.session_key:
            lines.append(f"Session: `{event.session_key}`")
        if event.phase:
            lines.append(f"Phase: {event.phase}")

        lines.append("")
        lines.append(event.message)

        # Add actionable commands
        if event.actionable_commands:
            lines.append("")
            lines.append("**Actions:**")
            for cmd in event.actionable_commands:
                lines.append(f"- `{cmd}`")

        return "\n".join(lines)

    def notify_user(self, task_id: str, event_type: str, message: str, 
                    severity: str = "INFO", session_key: str = None,
                    actionable_commands: list[str] = None) -> SupervisorEvent:
        """
        Emit a user notification for a supervisor event.

        Args:
            task_id: Task ID
            event_type: Event type string
            message: Notification message
            severity: CRITICAL | WARNING | INFO
            session_key: Optional agent session key
            actionable_commands: Optional list of slash commands

        Returns:
            The SupervisorEvent that was emitted.
        """
        ts = self._task_states.get(task_id)
        now_iso = datetime.now(timezone.utc).isoformat()

        event = SupervisorEvent(
            type=event_type,
            severity=severity,
            session_key=session_key,
            task_id=task_id,
            message=message,
            timestamp=now_iso,
            actionable_commands=actionable_commands or [],
        )

        if ts:
            ts.events.append(event)

        return event

    # ===== State Management =====

    def get_task_supervisor_state(self, task_id: str) -> Optional[TaskSupervisorState]:
        """Get current supervisor state for a task."""
        return self._task_states.get(task_id)

    def update_overlay_state(self, task_id: str, new_state: str) -> bool:
        """Update the overlay state for a task. Enforces transition rules."""
        ts = self._task_states.get(task_id)
        if not ts:
            return False
        
        if new_state not in self.OVERLAY_STATES:
            return False

        old_state = ts.overlay_state
        current = old_state
        
        # Validate transition rules per protocol spec
        allowed_transitions = {
            "SUPERVISING": ["AGENT_STALLED", "HUMAN_INTERVENTION"],
            "AGENT_STALLED": ["HUMAN_INTERVENTION", "SUPERVISING"],
            "AGENT_FAILED": ["HUMAN_INTERVENTION", "TASK_ABORTED"],
            "HUMAN_INTERVENTION": ["SUPERVISING", "TASK_ABORTED"],
            "TASK_ABORTED": [],  # Terminal — no outgoing transitions
        }

        if current and new_state not in allowed_transitions.get(current, []):
            return False

        ts.overlay_state = new_state
        
        # Log the transition
        event = SupervisorEvent(
            type="STATE_CHANGE",
            severity="INFO",
            task_id=task_id,
            message=f"Overlay state: {old_state} → {new_state}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        ts.events.append(event)

        return True

    def add_agent_to_supervision(self, task_id: str, agent_session_key: str, 
                                  agent_id: str, phase: str, prompt_text: str = "") -> bool:
        """
        Register an agent session with the supervisor.

        Called when a new agent is spawned for a supervised task.

        Args:
            task_id: Task ID
            agent_session_key: Session key of the new agent
            agent_id: Agent identifier (e.g., "implementer")
            phase: Current phase
            prompt_text: The prompt given to the agent (for retry context)

        Returns:
            True if registration succeeded.
        """
        ts = self._task_states.get(task_id)
        if not ts:
            return False

        now_iso = datetime.now(timezone.utc).isoformat()
        
        # Scan artifacts for baseline
        task_dir = self._find_task_directory(task_id)
        artifact_baseline = {}
        
        if task_dir:
            scan_dirs = ["docs/development/reports", "docs/dispatchers"]
            for rel_dir in scan_dirs:
                scan_path = os.path.join(task_dir, rel_dir) if not os.path.isabs(rel_dir) else rel_dir
                if os.path.exists(scan_path):
                    for root, _, files in os.walk(scan_path):
                        for f in files:
                            full_path = os.path.join(root, f)
                            try:
                                mtime = datetime.fromtimestamp(
                                    os.path.getmtime(full_path), tz=timezone.utc
                                ).isoformat()
                                artifact_baseline[full_path] = mtime
                            except OSError:
                                pass

        agent_state = AgentState(
            session_key=agent_session_key,
            agent_id=agent_id,
            phase=phase,
            spawned_at=now_iso,
            last_progress_at=None,
            artifact_baseline=artifact_baseline,
        )

        ts.agents[agent_session_key] = agent_state
        
        # Ensure we're in SUPERVISING state when adding new agents
        if ts.overlay_state == "HUMAN_INTERVENTION":
            self.update_overlay_state(task_id, "SUPERVISING")
        
        return True

    def get_supervisor_summary(self, task_id: str) -> dict:
        """Get a summary of the supervisor's view of a task."""
        ts = self._task_states.get(task_id)
        if not ts:
            return {"error": f"No supervisor state for {task_id}"}

        agents_info = []
        for key, agent in ts.agents.items():
            liveness = self.liveness.verify_session_alive(key)
            agents_info.append({
                "session_key": key,
                "agent_id": agent.agent_id,
                "phase": agent.phase,
                "state": agent.state,
                "alive": liveness.alive,
                "retry_count": agent.retry_count,
                "spawned_at": agent.spawned_at,
            })

        return {
            "task_id": task_id,
            "overlay_state": ts.overlay_state,
            "mode": ts.mode,
            "agent_count": len(ts.agents),
            "agents": agents_info,
            "event_log_size": len(ts.events),
            "last_heartbeat": ts.last_heartbeat_at,
        }

    # ===== Internal Helpers =====

    def _find_task_directory(self, task_id: str) -> Optional[str]:
        """Find the task directory for a given task ID."""
        # Try docs/dispatchers first (state files live here)
        candidate = os.path.join(self.workspace_root, "docs", "dispatchers", task_id)
        if os.path.exists(candidate):
            return candidate
        
        # Try docs/development/reports (task reports live here)
        candidate = os.path.join(self.workspace_root, "docs", "development", "reports", task_id)
        if os.path.exists(candidate):
            return candidate

        return None

    def _generate_escalation_report(self, task_id: str, agent_state: AgentState, report_path: str) -> dict:
        """Generate a summary report for user escalation."""
        # Count existing artifacts
        work_completed = 0
        if os.path.exists(report_path):
            for f in os.listdir(report_path):
                if f.endswith((".md", ".json")) and not f.startswith("."):
                    work_completed += 1

        return {
            "agent_id": agent_state.agent_id,
            "phase": agent_state.phase,
            "state": agent_state.state,
            "retry_count": agent_state.retry_count,
            "work_completed": work_completed,
            "total_required": "?",  # Depends on task scope
            "session_key": agent_state.session_key,
        }

    def _generate_failure_report(self, task_id: str, ts: TaskSupervisorState, report_path: str) -> dict:
        """Generate a failure summary for aborted tasks."""
        work_completed = 0
        if os.path.exists(report_path):
            for f in os.listdir(report_path):
                if f.endswith((".md", ".json")) and not f.startswith("."):
                    work_completed += 1

        return {
            "work_completed": work_completed,
            "total_required": "?",
            "aborted_agents": [
                {"session_key": k, "agent_id": v.agent_id, "state": v.state}
                for k, v in ts.agents.items()
            ],
            "final_overlay_state": ts.overlay_state,
        }

    def _write_failure_report(self, task_id: str, summary: dict, report_path: str):
        """Write a failure report to the task directory."""
        os.makedirs(report_path, exist_ok=True)
        
        report = {
            "task_id": task_id,
            "status": "ABORTED",
            "work_completed": summary.get("work_completed", 0),
            "total_required": summary.get("total_required", "?"),
            "aborted_agents": summary.get("aborted_agents", []),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        report_file = os.path.join(report_path, "FAILURE_REPORT.json")
        try:
            with open(report_file, "w") as f:
                json.dump(report, f, indent=2)
        except OSError:
            pass  # Best effort — don't fail on write error

    def _build_retry_prompt(self, task_id: str, agent_state: AgentState, stalled_session_key: str) -> str:
        """Build the prompt for a retried agent, including stall context."""
        lines = [
            f"## RETRY DISPATCH — {task_id}",
            "",
            "This is a retry of a previously stalled agent session.",
            f"**Previous session:** `{stalled_session_key}`",
            f"**Agent role:** {agent_state.agent_id}",
            f"**Phase:** {agent_state.phase}",
            f"**Retry attempt:** #{agent_state.retry_count + 1}",
            "",
            "The previous agent session stalled (no progress detected).",
            "Please continue the work from where it left off.",
            "",
            "**Instructions:**",
            "1. Check what artifacts already exist in the task directory",
            "2. Continue implementation without duplicating existing work",
            "3. Produce deliverables efficiently — avoid over-engineering",
            "4. Report completion when all acceptance criteria are met",
        ]
        return "\n".join(lines)

    def _cleanup_agent_session(self, session_key: str):
        """Best-effort cleanup of an agent session."""
        # In production this would call sessions_send to abort the session
        pass  # No-op in our implementation — actual cleanup is handled by OpenClaw

    def _emit_event(self, ts: TaskSupervisorState, event: SupervisorEvent):
        """Emit and log a supervisor event."""
        if not event.timestamp:
            event.timestamp = datetime.now(timezone.utc).isoformat()
        ts.events.append(event)


# ===== CLI — Test the supervisor =====
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DS-EO Supervisor Tester")
    parser.add_argument("action", choices=["start", "check", "summary", "recover", "abort"], help="Action")
    parser.add_argument("--task-id", "-T", required=True, help="Task ID")
    parser.add_argument("--session-key", "-s", help="Session key (for check/recover)")
    parser.add_argument("--mode", "-m", default="automatic", choices=["automatic", "manual"])
    args = parser.parse_args()

    supervisor = WorkflowSupervisor(workspace_root="/home/deepsim/ds-eo-openclaw")

    if args.action == "start":
        ok = supervisor.start_supervising(args.task_id, args.mode)
        print(f"{'✓' if ok else '✗'} Started supervision for {args.task_id} ({args.mode} mode)")

    elif args.action == "check":
        ts = supervisor.get_task_supervisor_state(args.task_id)
        if not ts:
            print("ERROR: Not supervising this task. Run 'start' first.")
            exit(1)
        
        stalled, report = supervisor.detect_stall(args.task_id)
        print(f"Stalled agents: {stalled or 'none'}")
        for key, info in report.items():
            if isinstance(info, dict):
                print(f"  {key}: status={info.get('status', '?')}, progress_age={info.get('time_since_progress_seconds', 0)}s")

    elif args.action == "summary":
        summary = supervisor.get_supervisor_summary(args.task_id)
        if "error" in summary:
            print(summary["error"])
            exit(1)
        print(f"Task: {summary['task_id']}")
        print(f"Overlay state: {summary['overlay_state']}")
        print(f"Mode: {summary['mode']}")
        print(f"Agents: {summary['agent_count']}")
        for agent in summary.get("agents", []):
            alive_icon = "✓" if agent["alive"] else "✗"
            print(f"  {alive_icon} {agent['session_key']}: {agent['state']} (retry #{agent['retry_count']})")

    elif args.action == "recover":
        if not args.session_key:
            print("ERROR: --session-key required")
            exit(1)
        
        result = supervisor.attempt_recovery(args.task_id, args.session_key)
        print(f"Recovery: {result.action_taken}")
        if result.new_session_key:
            print(f"  New session: {result.new_session_key}")
        if result.reason:
            print(f"  Reason: {result.reason}")

    elif args.action == "abort":
        result = supervisor.abort_task(args.task_id)
        print(f"Abort: {'✓' if result.success else '✗'}")
        print(f"  Action: {result.action_taken}")
        if result.reason:
            print(f"  Reason: {result.reason}")
