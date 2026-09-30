"""
DS-EO Session Health — Monitoring Loop (§15)

Scheduling loop that orchestrates the full session health pipeline:
  discover_all_sessions() → classify → policy → execute → audit

Default status is OBSERVING (dry-run). Must be explicitly set to ACTIVE
by the operator before any actions are actually executed.

The monitor is intentionally lightweight — it does not block or interfere
with active agent execution. It runs on a configurable interval and
produces immutable audit records for every cycle.

Architecture Decision (CTO Plan §1.3): The monitor ties together all
previous phases (discoverer, classifier, policy) without introducing new
side effects of its own. It is the only component that has timing/state
semantics — everything else is pure or side-effect-free until execution.
"""

import os
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Callable, List

from .enums import SessionHealthState, LifecycleAction, MonitorStatus
from .config import SessionHealthConfig
from .discoverer import SessionDiscoverer, SessionHealthData
from .classifier import HealthClassifier, ClassificationResult
from .policy import HealthPolicy, PolicyDecision
from .executor import SessionHealthExecutor, ActionResult
from .audit import SessionHealthAuditLog, SessionHealthAuditEvent


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #


@dataclass
class CycleReport:
    """Summary of one monitoring cycle iteration."""

    timestamp: str = ""
    session_count: int = 0
    classifications: dict = field(default_factory=dict)  # state → count
    actions_taken: dict = field(default_factory=dict)     # action → count
    executions_succeeded: int = 0
    executions_failed: int = 0
    audit_events_recorded: int = 0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "session_count": self.session_count,
            "classifications": self.classifications,
            "actions_taken": self.actions_taken,
            "executions_succeeded": self.executions_succeeded,
            "executions_failed": self.executions_failed,
            "audit_events_recorded": self.audit_events_recorded,
        }


@dataclass
class SessionActionRecord:
    """Per-session result from one cycle — what was done and why."""

    session_key: str
    classification: str = ""
    action: str = ""
    safety_override: bool = False
    execution_success: Optional[bool] = None
    verified: Optional[bool] = None
    error_message: Optional[str] = None
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "session_key": self.session_key,
            "classification": self.classification,
            "action": self.action,
            "safety_override": self.safety_override,
            "execution_success": self.execution_success,
            "verified": self.verified,
            "error_message": self.error_message,
            "details": self.details,
        }


# --------------------------------------------------------------------------- #
# SessionHealthMonitor — scheduling loop orchestrating the pipeline
# --------------------------------------------------------------------------- #


class SessionHealthMonitor:
    """
    Scheduling loop that orchestrates the full session health pipeline.

    Pipeline per cycle:
      1. discover_all_sessions()     → collect signals (Phase 1)
      2. classify(data)              → determine health state (Phase 2)
      3. evaluate(classification)    → decide action + safety layers (Phase 3)
      4. execute(action, data)       → perform with verification (Phase 4)
      5. audit_events                → record immutable trail (Phase 5)

    Status management:
      - OBSERVING (default): run the full pipeline but executor refuses to act
        — produces reports and audit entries only
      - ACTIVE: run pipeline AND execute actions
      - PAUSED: skip pipeline entirely until resumed

    Args:
        config: SessionHealthConfig with thresholds.
        monitor_status: Initial MonitorStatus — defaults to OBSERVING (§23).
        workspace_root: Path to project root for audit log storage.
        protected_sessions: Set of session keys that should never be destroyed.
        recovery_engine: Optional RecoveryEngine reference for ESCALATE delegation.
    """

    def __init__(
        self,
        config: Optional[SessionHealthConfig] = None,
        monitor_status: MonitorStatus = MonitorStatus.OBSERVING,
        workspace_root: Optional[str] = None,
        protected_sessions: Optional[set] = None,
        recovery_engine=None,
    ):
        self.config = config or SessionHealthConfig()
        self._status = monitor_status
        self.protected_sessions = protected_sessions or set()

        # Pipeline components (initialized lazily so the class is constructable
        # without a real workspace — useful for testing)
        self._discoverer: Optional[SessionDiscoverer] = None
        self._classifier: Optional[HealthClassifier] = None
        self._policy: Optional[HealthPolicy] = None
        self._executor: Optional[SessionHealthExecutor] = None
        self._audit_log: Optional[SessionHealthAuditLog] = None

        if workspace_root is not None:
            self._init_pipeline(workspace_root)

    def _init_pipeline(self, workspace_root: str):
        """Initialize all pipeline components with the given workspace root."""
        self._discoverer = SessionDiscoverer(workspace_root=workspace_root)
        self._classifier = HealthClassifier(config=self.config)
        self._policy = HealthPolicy(
            config=self.config,
            protected_sessions=self.protected_sessions,
        )
        self._executor = SessionHealthExecutor(
            config=self.config,
            monitor_status=self._status,
            protected_sessions=self.protected_sessions,
            recovery_engine=self.recovery_engine,
        )
        self._audit_log = SessionHealthAuditLog(workspace_root=workspace_root)

    # Properties for lazy initialization and external access

    @property
    def status(self) -> MonitorStatus:
        """Current monitor status."""
        return self._status

    @status.setter
    def status(self, new_status: MonitorStatus):
        """Change monitor status — propagates to executor."""
        old = self._status
        self._status = new_status
        if self._executor is not None:
            self._executor.monitor_status = new_status

    @property
    def recovery_engine(self):
        return self._executor.recovery_engine if self._executor else None

    @recovery_engine.setter
    def recovery_engine(self, engine):
        if self._executor:
            self._executor.recovery_engine = engine

    # ===== Pipeline Orchestration =====

    def run_cycle(self) -> CycleReport:
        """
        Execute one full monitoring cycle.

        Runs the pipeline regardless of status (for reporting purposes),
        but the executor will refuse to perform actions when not ACTIVE.

        Returns:
            CycleReport summarizing what happened in this iteration.
        """
        if self._discoverer is None or self._classifier is None:
            raise RuntimeError(
                "Monitor pipeline not initialized — pass workspace_root to constructor"
            )

        cycle_start = datetime.now(timezone.utc)
        report = CycleReport(timestamp=cycle_start.isoformat())

        # Step 1: Discover all sessions (Phase 1 deliverable)
        health_data_list = self._discoverer.discover_all_sessions()
        report.session_count = len(health_data_list)

        if not health_data_list:
            return report

        # Prepare per-cycle data structures
        audit_events: List[SessionHealthAuditEvent] = []
        session_records: List[SessionActionRecord] = []

        # Steps 2-5: For each discovered session
        for health_data in health_data_list:
            record = self._process_session(health_data)
            if record is not None:
                session_records.append(record)

        report.executions_succeeded = sum(
            1 for r in session_records if r.execution_success is True
        )
        report.executions_failed = sum(
            1 for r in session_records if r.execution_success is False
        )

        # Step 6: Record audit trail (Phase 5 deliverable)
        if audit_events and self._audit_log is not None:
            try:
                path = self._audit_log.append_events(audit_events)
                report.audit_events_recorded = len(audit_events)
            except OSError:
                pass  # Audit directory may not exist yet — that's OK

        return report

    def _process_session(self, health_data) -> Optional[SessionActionRecord]:
        """Process one session through the full pipeline. Returns record or None on error."""
        try:
            # Step 2: Classify (Phase 2 deliverable)
            classification = self._classifier.classify(health_data)

            # Step 3: Evaluate policy with safety layers (Phase 3 deliverable)
            decision = self._policy.evaluate(health_data.session_key, classification)

            # Step 4: Execute action with verification (Phase 4 deliverable)
            result = self._executor.execute(
                health_data.session_key,
                decision.action,
                health_data,
            )

            # Build audit event from the full pipeline output
            audit_event = SessionHealthAuditEvent(
                session_key=health_data.session_key,
                classification=classification.state.value,
                confidence=classification.confidence,
                action_taken=decision.action.value,
                safety_override=decision.is_safety_override,
                reason=decision.reason,
                execution_success=result.success,
                verified=result.verified,
                error_message=result.error_message,
            )

            # Capture signals observed during classification for audit traceability
            if hasattr(classification, 'evidence'):
                audit_event.signals_observed = {
                    e.signal_name: str(e.value)
                    for e in classification.evidence
                }

            return SessionActionRecord(
                session_key=health_data.session_key,
                classification=classification.state.value,
                action=decision.action.value,
                safety_override=decision.is_safety_override,
                execution_success=result.success,
                verified=result.verified,
                error_message=result.error_message,
                details=result.details,
            )

        except Exception as e:
            # Never let one session's failure break the whole cycle
            return SessionActionRecord(
                session_key=health_data.session_key if health_data else "unknown",
                classification="UNKNOWN",
                action="NO_ACTION",
                execution_success=False,
                error_message=str(e),
                details=f"Pipeline error processing {health_data.session_key if health_data else 'unknown'}: {e}",
            )

    def run_once(self) -> CycleReport:
        """Alias for run_cycle — same behavior."""
        return self.run_cycle()

    # ===== Scheduling (background loop) =====

    def start_background_loop(self, callback: Optional[Callable[[CycleReport], None]] = None):
        """
        Start a background scheduling loop that runs the pipeline at
        the configured interval.

        Args:
            callback: Optional function called with each CycleReport after completion.
                      Useful for logging, alerting, or dashboard updates.

        Returns:
            Thread handle (caller is responsible for join/daemon as needed).
        """
        if self.config.monitoring_interval_seconds is None:
            raise RuntimeError("Monitoring interval is disabled — cannot start background loop")

        def _loop():
            while self._status != MonitorStatus.PAUSED:
                try:
                    report = self.run_cycle()
                    if callback:
                        try:
                            callback(report)
                        except Exception:
                            pass  # Don't let callback errors break the loop
                except Exception:
                    pass  # Never crash the background thread

                time.sleep(self.config.monitoring_interval_seconds)

        thread = threading.Thread(target=_loop, daemon=True)
        thread.start()
        return thread

    def stop_background_loop(self):
        """Pause the monitoring loop (sets status to PAUSED)."""
        self.status = MonitorStatus.PAUSED

    # ===== Reporting & Inspection =====

    def get_status_summary(self) -> dict:
        """Get current monitor state summary — useful for dashboards and debugging."""
        return {
            "status": self._status.value,
            "protected_sessions": list(self.protected_sessions),
            "config": self.config.to_dict(),
        }

    def get_recent_audit_summary(self, hours: int = 24) -> dict:
        """Get the most recent audit log summary."""
        if self._audit_log is None:
            return {"error": "Audit log not initialized"}
        return self._audit_log.get_summary(hours=hours)

    def get_session_history(self, session_key: str, hours: int = 168) -> List[dict]:
        """Get all audit events for a specific session."""
        if self._audit_log is None:
            return []
        events = self._audit_log.get_events_for_session(session_key, hours=hours)
        return [e.to_dict() for e in events]


# ===== CLI — Test the monitor =====
if __name__ == "__main__":
    import argparse
    from .enums import MonitorStatus

    parser = argparse.ArgumentParser(description="DS-EO Session Health Monitor")
    parser.add_argument("action", choices=["cycle", "status", "audit"])
    parser.add_argument("--workspace-root", "-w", default=None)
    parser.add_argument("--monitor-status", default="OBSERVING",
                        choices=["OBSERVING", "ACTIVE", "PAUSED"])
    args = parser.parse_args()

    monitor_status_map = {
        "OBSERVING": MonitorStatus.OBSERVING,
        "ACTIVE": MonitorStatus.ACTIVE,
        "PAUSED": MonitorStatus.PAUSED,
    }

    if args.workspace_root is None:
        # Default to the project root (parent of ds_eo_openclaw/)
        import os as _os
        args.workspace_root = _os.path.dirname(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        )

    monitor = SessionHealthMonitor(
        workspace_root=args.workspace_root,
        monitor_status=monitor_status_map[args.monitor_status],
    )

    if args.action == "cycle":
        report = monitor.run_cycle()
        print(f"Cycle completed at {report.timestamp}")
        print(f"Sessions discovered: {report.session_count}")
        print(f"Actions succeeded:   {report.executions_succeeded}")
        print(f"Actions failed:      {report.executions_failed}")
        if report.classifications:
            print("\nClassifications:")
            for state, count in report.classifications.items():
                print(f"  {state}: {count}")
        if report.audit_events_recorded > 0:
            print(f"Audit events recorded: {report.audit_events_recorded}")

    elif args.action == "status":
        import json
        print(json.dumps(monitor.get_status_summary(), indent=2))

    elif args.action == "audit":
        import json
        summary = monitor.get_recent_audit_summary(hours=24)
        print(json.dumps(summary, indent=2))
