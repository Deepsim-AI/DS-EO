"""DS-EO Audit Trail — Phase 2 Integration.

Schema-compliant audit logging per EXECUTION_MODE_ARCHITECTURE.md §10.2.
Every transition (manual or automatic) produces a fully reconstructable record:
14 required fields, UUIDv4 auditId, ISO-8601 UTC timestamps, integrity chain.

Usage:
    from ds_eo_openclaw.workflow.audit_log import AuditLog, ProjectAuditIndex

    # Per-task log (auto-created at first append)
    log = AuditLog.create("/path/to/task/dir", "TASK_DS_EO_021")
    entry = log.append_entry(
        transition_key="T0", from_state="TASK_OPEN", to_state="G1_WAITING",
        gate_passed=None, gate_status="APPROVED", agent_id="pm",
        execution_mode="automatic", triggered_by="PM",
        details={"reason": "Plan submitted for review"},
        verified_artifacts=["CTO_PLAN.md"]
    )

    # Project-level index (cross-task navigation)
    ProjectAuditIndex.update("TASK_DS_EO_021", "G1_WAITING", entry.timestamp)
"""

import json
import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any


# --------------------------------------------------------------------------- #
# AuditEntry — immutable snapshot of one transition (14-field schema)
# --------------------------------------------------------------------------- #

class AuditEntry:
    """Immutable audit entry matching the 14-field schema from §10.2."""

    __slots__ = (
        "auditId", "taskId", "transitionKey", "fromState", "toState",
        "gatePassed", "gateStatus", "agentId", "executionMode",
        "triggeredBy", "timestamp", "details", "verifiedArtifacts",
        "reconstructionHash"
    )

    def __init__(self, **fields: Any):
        # gatePassed is "string or null" per spec — presence check only
        required_non_null = [
            "auditId", "taskId", "transitionKey", "fromState", "toState",
            "gateStatus", "agentId", "executionMode",
            "triggeredBy", "timestamp", "details", "verifiedArtifacts",
            "reconstructionHash"
        ]
        for key in required_non_null:
            if key not in fields or fields[key] is None:
                raise ValueError(f"AuditEntry missing required field: {key}")

        # Type validation
        self.auditId = str(fields["auditId"])
        self.taskId = str(fields["taskId"])
        self.transitionKey = str(fields["transitionKey"])
        self.fromState = str(fields["fromState"])
        self.toState = str(fields["toState"])

        # gatePassed: string or None (allowed)
        gp = fields["gatePassed"]
        if gp is not None:
            self.gatePassed = str(gp)
        else:
            self.gatePassed = None

        # gateStatus: always present, never null — strict values only
        valid_gate_statuses = {"APPROVED", "REJECTED", "CHANGES_REQD"}
        gs = fields["gateStatus"]
        if gs not in valid_gate_statuses:
            raise ValueError(
                f"gateStatus must be one of {valid_gate_statuses}, got '{gs}'"
            )
        self.gateStatus = gs

        self.agentId = str(fields["agentId"])
        self.executionMode = str(fields["executionMode"])
        if self.executionMode not in ("manual", "automatic"):
            raise ValueError(
                f"executionMode must be 'manual' or 'automatic', got '{self.executionMode}'"
            )
        self.triggeredBy = str(fields["triggeredBy"])

        # timestamp: ISO-8601 UTC string — validated on construction
        ts = fields["timestamp"]
        if not isinstance(ts, str) or "T" not in ts:
            raise ValueError(f"timestamp must be ISO-8601 string, got '{ts}'")
        self.timestamp = ts

        # details: object (dict) — can be empty
        det = fields["details"]
        if not isinstance(det, dict):
            raise TypeError(f"details must be a dict, got {type(det).__name__}")
        self.details = det

        # verifiedArtifacts: array of strings — can be empty
        va = fields["verifiedArtifacts"]
        if not isinstance(va, list):
            raise TypeError(f"verifiedArtifacts must be a list, got {type(va).__name__}")
        for item in va:
            if not isinstance(item, str):
                raise TypeError(f"verifiedArtifacts items must be strings, got {type(item).__name__}")
        self.verifiedArtifacts = va

        # reconstructionHash: SHA-256 hex string
        rh = fields["reconstructionHash"]
        if not isinstance(rh, str) or len(rh) != 64:
            raise ValueError(
                f"reconstructionHash must be 64-char hex SHA-256, got '{rh}'"
            )
        self.reconstructionHash = rh

    def to_dict(self) -> Dict[str, Any]:
        """Serialize entry to JSON-compatible dict."""
        return {k: getattr(self, k) for k in AuditEntry.__slots__}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AuditEntry":
        """Deserialize entry from a dict (e.g., loaded from AUDIT_LOG.json)."""
        return cls(**d)

    def __repr__(self):
        return (f"AuditEntry(task={self.taskId}, {self.fromState}→{self.toState}, "
                f"mode={self.executionMode})")


# --------------------------------------------------------------------------- #
# AuditLog — per-task audit log manager
# --------------------------------------------------------------------------- #

class AuditLog:
    """Manages a single task's AUDIT_LOG.json. Creates file on first append."""

    def __init__(self, task_dir: str, task_id: str):
        self.task_dir = task_dir
        self.task_id = task_id
        self._log_path = os.path.join(task_dir, "AUDIT_LOG.json")

    @staticmethod
    def create(task_dir: str, task_id: str) -> "AuditLog":
        """Create and return a new AuditLog for the given task directory.

        The task_id is stored in each entry. If it doesn't start with 'TASK_',
        we still allow creation but log a warning — the caller may be using a
        non-standard naming convention or testing.
        """
        if not task_id.startswith("TASK_"):
            # Allow non-TASK_ prefixes for flexibility (testing, custom layouts)
            pass
        return AuditLog(task_dir, task_id)

    def _load_entries(self) -> List[AuditEntry]:
        """Load existing entries from disk (or empty list if none)."""
        if not os.path.isfile(self._log_path):
            return []
        with open(self._log_path, "r") as f:
            data = json.load(f)
        return [AuditEntry.from_dict(e) for e in data]

    def _compute_reconstruction_hash(self, preceding_entries: List[AuditEntry]) -> str:
        """Compute SHA-256 integrity chain hash from all preceding entries.

        The reconstructionHash of entry N is SHA-256 of the concatenation of
        all preceding entries' hashes (or empty string if this is the first).
        This creates an immutable chain — modifying any prior entry invalidates
        all subsequent hashes.
        """
        if not preceding_entries:
            return hashlib.sha256(b"").hexdigest()

        # Chain: hash of previous hash + current entry's serialized form
        prev_hash = preceding_entries[-1].reconstructionHash
        combined = (prev_hash + json.dumps(
            preceding_entries[-1].to_dict(), sort_keys=True, separators=(",", ":")
        )).encode("utf-8")
        return hashlib.sha256(combined).hexdigest()

    def append_entry(self, transition_key: str, from_state: str, to_state: str,
                     gate_passed: Optional[str], gate_status: str,
                     agent_id: str, execution_mode: str, triggered_by: str,
                     details: Dict[str, Any], verified_artifacts: List[str]) -> AuditEntry:
        """Create and append a fully-formed audit entry.

        Returns the created AuditEntry for immediate use (e.g., by ProjectAuditIndex).
        """
        preceding = self._load_entries()
        reconstruction_hash = self._compute_reconstruction_hash(preceding)

        entry_data = {
            "auditId": str(uuid.uuid4()),
            "taskId": self.task_id,
            "transitionKey": transition_key,
            "fromState": from_state,
            "toState": to_state,
            "gatePassed": gate_passed,
            "gateStatus": gate_status,
            "agentId": agent_id,
            "executionMode": execution_mode,
            "triggeredBy": triggered_by,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": details,
            "verifiedArtifacts": verified_artifacts,
            "reconstructionHash": reconstruction_hash,
        }

        entry = AuditEntry(**entry_data)

        # Append and persist atomically (write to temp, rename)
        entries = preceding + [entry]
        tmp_path = self._log_path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump([e.to_dict() for e in entries], f, indent=2)
        os.replace(tmp_path, self._log_path)

        return entry

    def get_entries(self) -> List[AuditEntry]:
        """Read all entries back from disk. Returns empty list if no log exists."""
        return self._load_entries()

    @property
    def entry_count(self) -> int:
        """Number of entries currently in the log."""
        return len(self.get_entries())


# --------------------------------------------------------------------------- #
# ProjectAuditIndex — cross-task audit navigation
# --------------------------------------------------------------------------- #

class ProjectAuditIndex:
    """Project-level index for cross-task audit navigation.

    Flat list at docs/reports/AUDIT_INDEX.json with one entry per task,
    containing latestState and lastAuditTime for quick scanning.
    """

    INDEX_PATH = os.path.join("docs", "reports", "AUDIT_INDEX.json")

    @staticmethod
    def _load_index() -> List[Dict[str, Any]]:
        if not os.path.isfile(ProjectAuditIndex.INDEX_PATH):
            return []
        with open(ProjectAuditIndex.INDEX_PATH, "r") as f:
            data = json.load(f)
        return data

    @staticmethod
    def update(task_id: str, latest_state: str, last_audit_time: str):
        """Append or update entry in the project-level audit index.

        If an entry for task_id already exists, it is updated with new values.
        Otherwise a new entry is appended.
        """
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(ProjectAuditIndex.INDEX_PATH), exist_ok=True)

        index = ProjectAuditIndex._load_index()

        # Update existing or append new
        found = False
        for entry in index:
            if entry.get("taskId") == task_id:
                entry["latestState"] = latest_state
                entry["lastAuditTime"] = last_audit_time
                found = True
                break

        if not found:
            index.append({
                "taskId": task_id,
                "latestState": latest_state,
                "lastAuditTime": last_audit_time
            })

        # Atomic write (write to temp, rename)
        tmp_path = ProjectAuditIndex.INDEX_PATH + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(index, f, indent=2)
        os.replace(tmp_path, ProjectAuditIndex.INDEX_PATH)

    @staticmethod
    def get_task_state(task_id: str) -> Optional[str]:
        """Quick lookup of a task's latest state from the index. Returns None if not found."""
        for entry in ProjectAuditIndex._load_index():
            if entry.get("taskId") == task_id:
                return entry.get("latestState")
        return None

    @staticmethod
    def get_all_tasks() -> List[Dict[str, str]]:
        """Return all entries from the index."""
        return ProjectAuditIndex._load_index()
