"""
DS-EO Session Health — Audit Trail (§21)

Persistent per-cycle audit log following spec §21 format. Extends existing
`workflow.audit_log` patterns with session-health-specific event records.

Every lifecycle action produces an immutable audit entry that can be used to:
  - Replay the decision history for a session
  - Debug unexpected classifications or actions
  - Comply with operational logging requirements
"""

import json
import os as _os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import uuid


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #


@dataclass
class SessionHealthAuditEvent:
    """Immutable audit event for one session health cycle iteration."""

    event_id: str = ""
    timestamp: str = ""
    session_key: str = ""

    # Classification
    classification: str = "UNKNOWN"  # SessionHealthState value
    confidence: float = 0.0

    # Policy decision
    action_taken: str = "NO_ACTION"  # LifecycleAction value
    safety_override: bool = False
    reason: str = ""

    # Execution result (if action was executed)
    execution_success: Optional[bool] = None
    verified: Optional[bool] = None
    error_message: Optional[str] = None

    # Signals that contributed to the decision
    signals_observed: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.event_id:
            self.event_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    @classmethod
    def from_action_result(cls, session_key: str, action_result_dict: dict) -> "SessionHealthAuditEvent":
        """Create an audit event from a completed ActionResult."""
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_key=session_key,
            classification=action_result_dict.get("classification", "UNKNOWN"),
            confidence=action_result_dict.get("confidence", 0.0),
            action_taken=action_result_dict.get("action", "NO_ACTION"),
            safety_override=action_result_dict.get("is_safety_override", False),
            reason=action_result_dict.get("reason", ""),
            execution_success=action_result_dict.get("success"),
            verified=action_result_dict.get("verified"),
            error_message=action_result_dict.get("error_message"),
        )

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "session_key": self.session_key,
            "classification": self.classification,
            "confidence": self.confidence,
            "action_taken": self.action_taken,
            "safety_override": self.safety_override,
            "reason": self.reason,
            "execution_success": self.execution_success,
            "verified": self.verified,
            "error_message": self.error_message,
            "signals_observed": self.signals_observed,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# --------------------------------------------------------------------------- #
# SessionHealthAuditLog — persistent audit trail
# --------------------------------------------------------------------------- #


class SessionHealthAuditLog:
    """
    Persistent per-cycle audit log for session health monitoring.

    Stores one JSON file per cycle containing all events from that iteration.
    Follows the same patterns as ds_eo_openclaw.workflow.audit_log but scoped
    to session health decisions.

    File layout:
        <workspace>/docs/session_health/audit/<YYYY-MM-DD>_<HHMMSS>.json

    Args:
        audit_dir: Directory for storing audit files (default: workspace/docs/session_health/audit/)
        max_retention_days: Number of days to retain audit files (default: 90)
    """

    DEFAULT_AUDIT_DIR = "docs/session_health/audit"

    def __init__(
        self,
        workspace_root: Optional[str] = None,
        audit_dir: Optional[str] = None,
        max_retention_days: int = 90,
    ):
        if workspace_root is None:
            workspace_root = _os.path.dirname(
                _os.path.dirname(_os.path.abspath(__file__))
            )
            # Go up one more level to get the project root
            if not _os.path.isdir(_os.path.join(workspace_root, "docs")):
                workspace_root = _os.path.dirname(
                    _os.path.dirname(_os.path.abspath(__file__))
                )

        self.workspace_root = _os.path.abspath(workspace_root)

        if audit_dir is None:
            self.audit_dir = _os.path.join(self.workspace_root, self.DEFAULT_AUDIT_DIR)
        else:
            self.audit_dir = _os.path.abspath(audit_dir)

        self.max_retention_days = max_retention_days

    def append_events(self, events: List[SessionHealthAuditEvent]) -> str:
        """
        Append a batch of audit events (one cycle's worth) to the log.

        Creates a new file for each cycle with ISO timestamp in filename.
        Returns the path of the created file.

        Args:
            events: List of SessionHealthAuditEvent from one monitoring cycle.

        Returns:
            Path to the written audit file.
        """
        _os.makedirs(self.audit_dir, exist_ok=True)

        now = datetime.now(timezone.utc)
        filename = now.strftime("%Y-%m-%d_%H%M%S") + ".json"
        filepath = _os.path.join(self.audit_dir, filename)

        audit_record = {
            "cycle_timestamp": now.isoformat(),
            "event_count": len(events),
            "events": [e.to_dict() for e in events],
        }

        with open(filepath, "w") as f:
            json.dump(audit_record, f, indent=2)

        return filepath

    def get_recent_events(self, hours: int = 24) -> List[SessionHealthAuditEvent]:
        """
        Get audit events from the last N hours.

        Args:
            hours: Number of recent hours to look back (default: 24).

        Returns:
            List of SessionHealthAuditEvent sorted by timestamp descending.
        """
        events = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        if not _os.path.isdir(self.audit_dir):
            return events

        for filename in sorted(_os.listdir(self.audit_dir), reverse=True):
            if not filename.endswith(".json"):
                continue

            filepath = _os.path.join(self.audit_dir, filename)
            try:
                with open(filepath) as f:
                    record = json.load(f)

                cycle_ts_str = record.get("cycle_timestamp", "")
                if cycle_ts_str:
                    cycle_ts = datetime.fromisoformat(cycle_ts_str).replace(tzinfo=timezone.utc)
                    if cycle_ts < cutoff:
                        continue  # Too old

                for event_dict in record.get("events", []):
                    event = SessionHealthAuditEvent(**event_dict)
                    events.append(event)
            except (json.JSONDecodeError, OSError, KeyError):
                continue

        return sorted(events, key=lambda e: e.timestamp, reverse=True)

    def get_events_for_session(self, session_key: str, hours: int = 168) -> List[SessionHealthAuditEvent]:
        """
        Get all audit events for a specific session.

        Args:
            session_key: The session key to filter by.
            hours: Number of recent hours (default: 7 days).

        Returns:
            List of SessionHealthAuditEvent for the specified session.
        """
        return [
            e for e in self.get_recent_events(hours)
            if e.session_key == session_key
        ]

    def get_summary(self, hours: int = 24) -> dict:
        """
        Get a summary of audit activity over the last N hours.

        Returns:
            Dict with counts by action type and classification.
        """
        events = self.get_recent_events(hours)

        by_action: dict[str, int] = {}
        by_classification: dict[str, int] = {}
        total_executed = 0
        total_verified = 0
        total_errors = 0

        for event in events:
            # Count by action type
            act = event.action_taken
            by_action[act] = by_action.get(act, 0) + 1

            # Count by classification
            cls = event.classification
            by_classification[cls] = by_classification.get(cls, 0) + 1

            if event.execution_success is True:
                total_executed += 1
            if event.verified is True:
                total_verified += 1
            if event.error_message is not None and event.execution_success is False:
                total_errors += 1

        return {
            "total_events": len(events),
            "by_action": by_action,
            "by_classification": by_classification,
            "total_executed": total_executed,
            "total_verified": total_verified,
            "total_errors": total_errors,
        }

    def cleanup_old_files(self):
        """Remove audit files older than max_retention_days."""
        if not _os.path.isdir(self.audit_dir):
            return 0

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_retention_days)
        removed = 0

        for filename in _os.listdir(self.audit_dir):
            if not filename.endswith(".json"):
                continue

            filepath = _os.path.join(self.audit_dir, filename)
            try:
                with open(filepath) as f:
                    record = json.load(f)

                cycle_ts_str = record.get("cycle_timestamp", "")
                if cycle_ts_str:
                    cycle_ts = datetime.fromisoformat(cycle_ts_str).replace(tzinfo=timezone.utc)
                    if cycle_ts < cutoff:
                        _os.remove(filepath)
                        removed += 1
            except (json.JSONDecodeError, OSError):
                continue

        return removed


# ===== CLI — Test the audit log =====
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DS-EO Session Health Audit Log")
    parser.add_argument("action", choices=["append", "summary", "recent"])
    parser.add_argument("--workspace-root", "-w", default=None)
    args = parser.parse_args()

    audit_log = SessionHealthAuditLog(workspace_root=args.workspace_root)

    if args.action == "summary":
        summary = audit_log.get_summary(hours=24)
        print(json.dumps(summary, indent=2))
    elif args.action == "recent":
        events = audit_log.get_recent_events(hours=24)
        print(f"Recent events ({len(events)}):")
        for e in events:
            print(f"  [{e.timestamp}] {e.session_key}: {e.classification} → {e.action_taken}")
    elif args.action == "append":
        # Demo: create a sample event and append it
        demo_event = SessionHealthAuditEvent(
            session_key="demo-session",
            classification="STALE",
            confidence=1.0,
            action_taken="MARK_STALE",
            safety_override=False,
            reason="Inactive 3700s exceeds stale threshold of 3600s",
        )
        path = audit_log.append_events([demo_event])
        print(f"Audit event appended to: {path}")
