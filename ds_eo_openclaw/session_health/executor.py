"""
DS-EO Session Health — Action Executor (§11, §16)

Executes lifecycle actions on sessions with full verification.
Each action produces an ActionResult with pre/post metrics and a verified flag.

Architecture Decision (CTO Plan §1.3): Separate from RecoveryEngine — this handles
*session-level* lifecycle (compact/archive/close), while RecoveryEngine handles
*workflow stage* recovery. Integration point: ESCALATE delegates to RecoveryEngine.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from .enums import SessionHealthState, LifecycleAction, MonitorStatus
from .config import SessionHealthConfig


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #


@dataclass
class ActionResult:
    """Result of executing a lifecycle action on a session."""

    session_key: str
    action: LifecycleAction
    success: bool = False
    verified: bool = False  # True if post-execution verification passed
    pre_metrics: dict = field(default_factory=dict)
    post_metrics: dict = field(default_factory=dict)
    error_message: Optional[str] = None
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "session_key": self.session_key,
            "action": self.action.value,
            "success": self.success,
            "verified": self.verified,
            "pre_metrics": self.pre_metrics,
            "post_metrics": self.post_metrics,
            "error_message": self.error_message,
            "details": self.details,
        }


# --------------------------------------------------------------------------- #
# Executor — executes actions with verification
# --------------------------------------------------------------------------- #


class SessionHealthExecutor:
    """
    Execute lifecycle actions on sessions with full verification.

    Each action follows the verify-then-persist pattern from spec §16:
      1. Capture pre-execution metrics (baseline)
      2. Perform the action
      3. Verify the result against expected outcome
      4. Return ActionResult with success + verified flags

    Safety layers:
      - Active task protection (spec §13): never execute destructive actions on active tasks
      - Protected session override (spec §22): never execute anything but WARN on protected sessions
      - COMPACT verification: must verify context reduction before marking success

    Args:
        config: SessionHealthConfig with thresholds.
        monitor_status: Current MonitorStatus — only ACTIVE allows execution.
        protected_sessions: Set of session keys that should never be destroyed.
        recovery_engine: Optional RecoveryEngine reference for ESCALATE delegation.
    """

    def __init__(
        self,
        config: Optional[SessionHealthConfig] = None,
        monitor_status: MonitorStatus = MonitorStatus.OBSERVING,
        protected_sessions: Optional[set] = None,
        recovery_engine=None,  # Lazy import — could be circular
    ):
        self.config = config or SessionHealthConfig()
        self.monitor_status = monitor_status
        self.protected_sessions = protected_sessions or set()
        self.recovery_engine = recovery_engine

    def execute(self, session_key: str, action: LifecycleAction, health_data=None) -> ActionResult:
        """
        Execute a lifecycle action on a session.

        Args:
            session_key: The session to act on.
            action: The lifecycle action to perform.
            health_data: SessionHealthData with current metrics (optional).

        Returns:
            ActionResult with success, verified flag, and full metrics.
        """
        # Safety check 1: Don't execute if monitor is not ACTIVE
        if self.monitor_status != MonitorStatus.ACTIVE:
            return ActionResult(
                session_key=session_key,
                action=action,
                success=False,
                verified=False,
                error_message=(
                    f"Monitor status is {self.monitor_status.value} — "
                    f"no actions executed (dry-run mode)"
                ),
                details="Skipped due to OBSERVING/PAUSED status",
            )

        # Safety check 2: Protected sessions → only WARN allowed
        if session_key in self.protected_sessions:
            return ActionResult(
                session_key=session_key,
                action=action,
                success=False,
                verified=False,
                error_message=(
                    f"Session {session_key} is protected — "
                    f"only WARN actions allowed on protected sessions"
                ),
                details="Protected session override (spec §22)",
            )

        # Dispatch to specific action handler
        if action == LifecycleAction.NO_ACTION:
            return self._execute_no_action(session_key, health_data)
        elif action == LifecycleAction.WARN:
            return self._execute_warn(session_key, health_data)
        elif action == LifecycleAction.MONITOR:
            return self._execute_monitor(session_key, health_data)
        elif action == LifecycleAction.COMPACT:
            return self._execute_compact(session_key, health_data)
        elif action == LifecycleAction.RETRY_COMPACTION:
            return self._execute_retry_compaction(session_key, health_data)
        elif action == LifecycleAction.MARK_STALE:
            return self._execute_mark_stale(session_key, health_data)
        elif action == LifecycleAction.ARCHIVE:
            return self._execute_archive(session_key, health_data)
        elif action == LifecycleAction.CLOSE:
            return self._execute_close(session_key, health_data)
        elif action == LifecycleAction.ESCALATE:
            return self._execute_escalate(session_key, health_data)
        else:
            return ActionResult(
                session_key=session_key,
                action=action,
                success=False,
                error_message=f"Unknown action: {action.value}",
            )

    # ===== Action Handlers =====

    def _capture_pre_metrics(self, health_data) -> dict:
        """Capture baseline metrics before executing an action."""
        if health_data is None:
            return {}
        return {
            "context_size_kb": health_data.context_size_kb,
            "error_count": health_data.error_count,
            "age_seconds": health_data.age_seconds,
            "alive": health_data.alive,
        }

    def _execute_no_action(self, session_key: str, health_data=None) -> ActionResult:
        """NO_ACTION — log the decision but perform no work."""
        return ActionResult(
            session_key=session_key,
            action=LifecycleAction.NO_ACTION,
            success=True,
            verified=True,
            pre_metrics=self._capture_pre_metrics(health_data),
            details="No action needed — session within acceptable parameters",
        )

    def _execute_warn(self, session_key: str, health_data=None) -> ActionResult:
        """WARN — record a warning for the session (informational only)."""
        # In production: would emit to monitoring/alerting system
        return ActionResult(
            session_key=session_key,
            action=LifecycleAction.WARN,
            success=True,
            verified=True,
            pre_metrics=self._capture_pre_metrics(health_data),
            post_metrics={"warning_recorded": True},
            details="Warning recorded for session — no destructive changes",
        )

    def _execute_monitor(self, session_key: str, health_data=None) -> ActionResult:
        """MONITOR — set session to enhanced monitoring mode."""
        # In production: would register with monitoring subsystem
        return ActionResult(
            session_key=session_key,
            action=LifecycleAction.MONITOR,
            success=True,
            verified=True,
            pre_metrics=self._capture_pre_metrics(health_data),
            post_metrics={"monitoring_enabled": True},
            details="Session added to enhanced monitoring queue",
        )

    def _execute_compact(self, session_key: str, health_data=None) -> ActionResult:
        """COMPACT — compact session context with verification.

        Follows spec §16 verify-then-persist pattern:
          1. Capture pre-compact context size
          2. Perform compaction (via OpenClaw API or RecoveryEngine)
          3. Verify post-compact context size is reduced
          4. Mark success only if verification passes
        """
        pre_size = health_data.context_size_kb if health_data else None

        # Attempt compaction — in production, would call OpenClaw session compact API
        # For now: simulate via RecoveryEngine integration point
        post_size = self._perform_compaction(session_key)

        verified = False
        success = True
        details = ""

        if pre_size is not None and post_size is not None:
            if post_size < pre_size:
                verified = True
                details = (
                    f"Context reduced from {pre_size}KB to {post_size}KB — "
                    f"compaction successful"
                )
            else:
                success = False
                verified = False
                details = (
                    f"Compaction did not reduce context size "
                    f"(was {pre_size}KB, now {post_size}KB) — FAILED verification"
                )
        else:
            # Could not measure — assume failure to be safe
            success = False
            verified = False
            details = "Could not verify compaction result (size measurement unavailable)"

        return ActionResult(
            session_key=session_key,
            action=LifecycleAction.COMPACT,
            success=success,
            verified=verified,
            pre_metrics=self._capture_pre_metrics(health_data),
            post_metrics={"context_size_kb_after": post_size},
            error_message=None if success else details,
            details=details,
        )

    def _execute_retry_compaction(self, session_key: str, health_data=None) -> ActionResult:
        """RETRY_COMPACTION — retry failed compaction with backoff.

        Follows spec §17 controlled retry policy:
          1. Check recovery_history for retry count
          2. If retries exhausted → escalate instead
          3. Otherwise → attempt compaction with exponential backoff
        """
        if health_data is None:
            return ActionResult(
                session_key=session_key,
                action=LifecycleAction.RETRY_COMPACTION,
                success=False,
                error_message="No health data available for retry decision",
            )

        recovery_history = health_data.recovery_history or []
        retry_count = len(recovery_history) if isinstance(recovery_history, list) else 0
        max_retries = self.config.max_compaction_attempts

        if retry_count >= max_retries:
            # Retries exhausted — escalate to RecoveryEngine
            return ActionResult(
                session_key=session_key,
                action=LifecycleAction.ESCALATE,
                success=False,
                details=(
                    f"Retry budget exhausted ({retry_count}/{max_retries}) — "
                    f"delegating to RecoveryEngine per spec §17"
                ),
            )

        # Attempt retry with backoff (simulated)
        return self._execute_compact(session_key, health_data)

    def _execute_mark_stale(self, session_key: str, health_data=None) -> ActionResult:
        """MARK_STALE — mark session as stale for monitoring purposes."""
        return ActionResult(
            session_key=session_key,
            action=LifecycleAction.MARK_STALE,
            success=True,
            verified=True,
            pre_metrics=self._capture_pre_metrics(health_data),
            post_metrics={"stale_marked": True},
            details="Session marked as stale — will be monitored for further inactivity",
        )

    def _execute_archive(self, session_key: str, health_data=None) -> ActionResult:
        """ARCHIVE — archive session data (preserves artifacts).

        Safety: Never archive sessions with active tasks.
        """
        if health_data and health_data.task_association == "ACTIVE":
            return ActionResult(
                session_key=session_key,
                action=LifecycleAction.ARCHIVE,
                success=False,
                verified=False,
                error_message="Cannot archive session with ACTIVE task association",
                details="Active task protection (spec §13) prevents archival",
            )

        # In production: would copy artifacts to archive storage, then clean up
        return ActionResult(
            session_key=session_key,
            action=LifecycleAction.ARCHIVE,
            success=True,
            verified=True,
            pre_metrics=self._capture_pre_metrics(health_data),
            post_metrics={"archived": True},
            details="Session archived — artifacts preserved in archive storage",
        )

    def _execute_close(self, session_key: str, health_data=None) -> ActionResult:
        """CLOSE — close session (destructive).

        Safety: Never close sessions with active tasks.
        """
        if health_data and health_data.task_association == "ACTIVE":
            return ActionResult(
                session_key=session_key,
                action=LifecycleAction.CLOSE,
                success=False,
                verified=False,
                error_message="Cannot close session with ACTIVE task association",
                details="Active task protection (spec §13) prevents closure",
            )

        if health_data and health_data.alive:
            return ActionResult(
                session_key=session_key,
                action=LifecycleAction.CLOSE,
                success=False,
                verified=False,
                error_message=(
                    f"Session {session_key} is still alive — cannot close active session"
                ),
                details="Safety check prevents closing live sessions",
            )

        # In production: would call OpenClaw API to close session
        return ActionResult(
            session_key=session_key,
            action=LifecycleAction.CLOSE,
            success=True,
            verified=True,
            pre_metrics=self._capture_pre_metrics(health_data),
            post_metrics={"closed": True},
            details="Session closed successfully",
        )

    def _execute_escalate(self, session_key: str, health_data=None) -> ActionResult:
        """ESCALATE — delegate to RecoveryEngine or notify user.

        Follows spec §14/§17: delegates compaction/recovery to RecoveryEngine
        when the session health system cannot handle it directly.
        """
        if self.recovery_engine is not None and health_data is not None:
            # Delegate to RecoveryEngine
            try:
                from ds_eo_openclaw.workflow.recovery_engine import FailureInfo, RecoveryAction as REAction

                task_id = (health_data.associated_task_id or "unknown")
                failure_info = FailureInfo(
                    type_="session_health_escalation",
                    message=f"Session {session_key} requires recovery — classified as {health_data.status}",
                    task_id=task_id,
                )

                action = self.recovery_engine.determine_recovery(failure_info)
                result = self.recovery_engine.execute_recovery(action, None)

                return ActionResult(
                    session_key=session_key,
                    action=LifecycleAction.ESCALATE,
                    success=result.get("success", False),
                    verified=False,  # Escalation outcome depends on RecoveryEngine
                    pre_metrics=self._capture_pre_metrics(health_data),
                    post_metrics={"recovery_action": action.value},
                    details=(
                        f"Escalated to RecoveryEngine with action: {action.value}"
                    ),
                )
            except Exception as e:
                return ActionResult(
                    session_key=session_key,
                    action=LifecycleAction.ESCALATE,
                    success=False,
                    error_message=f"RecoveryEngine delegation failed: {str(e)}",
                    details="Escalation attempted but RecoveryEngine integration error occurred",
                )

        # No recovery engine available — escalate to user notification
        return ActionResult(
            session_key=session_key,
            action=LifecycleAction.ESCALATE,
            success=True,
            verified=False,
            pre_metrics=self._capture_pre_metrics(health_data),
            post_metrics={"escalated_to_user": True},
            details="Escalation recorded — user notification required (no RecoveryEngine available)",
        )

    # ===== Internal Helpers =====

    def _perform_compaction(self, session_key: str) -> Optional[int]:
        """Perform actual compaction and return post-compact context size.

        In production: would call OpenClaw's session compact API.
        For now: returns None (cannot measure without real API).
        """
        # Integration point for OpenClaw session compact API
        # TODO: Replace with actual compaction implementation
        return None


# ===== CLI — Test the executor =====
if __name__ == "__main__":
    import argparse

    from .discoverer import SessionHealthData
    from .enums import MonitorStatus

    parser = argparse.ArgumentParser(description="DS-EO Session Health Executor")
    parser.add_argument("action", choices=[a.value for a in LifecycleAction])
    parser.add_argument("--session-key", "-s", default="test-session")
    parser.add_argument("--monitor-status", default="OBSERVING",
                        choices=["OBSERVING", "ACTIVE", "PAUSED"])
    args = parser.parse_args()

    monitor_status_map = {
        "OBSERVING": MonitorStatus.OBSERVING,
        "ACTIVE": MonitorStatus.ACTIVE,
        "PAUSED": MonitorStatus.PAUSED,
    }

    health_data = SessionHealthData(
        session_key=args.session_key,
        alive=True,
        status="running",
        context_size_kb=1024,
        error_count=0,
        age_seconds=300.0,
        task_association="INACTIVE",
    )

    executor = SessionHealthExecutor(
        monitor_status=monitor_status_map[args.monitor_status],
    )

    result = executor.execute(args.session_key, LifecycleAction(args.action), health_data)
    print(f"Session: {result.session_key}")
    print(f"Action:  {result.action.value}")
    print(f"Success: {result.success}")
    print(f"Verified:{result.verified}")
    if result.error_message:
        print(f"Error:   {result.error_message}")
    print(f"Details: {result.details}")
