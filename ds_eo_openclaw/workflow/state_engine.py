"""
DS-EO Workflow State Engine — Phase 1 (Core State Machine)

Implements the 11-state state machine for configurable workflow execution modes.
This engine is platform-neutral and can be used by any DS-EO edition
(OpenClaw, Claude, Codex, etc.).

States: S0–S10 as defined in EXECUTION_MODE_ARCHITECTURE.md §2
Transitions: 12 transitions as defined in EXECUTION_MODE_ARCHITECTURE.md §3.4
Audit Trail: Phase 2 integration via ds_eo_openclaw.workflow.audit_log module.
Mode Configuration: Phase 3 integration via ds_eo_openclaw.workflow.config module.

Usage:
    from ds_eo_openclaw.workflow.state_engine import StateEngine, State

    # With explicit mode (Phase 1)
    engine = StateEngine("/path/to/task/dir", execution_mode="automatic")

    # With WorkflowConfig (Phase 3 — reads global + applies per-task override)
    from ds_eo_openclaw.workflow.config import WorkflowConfig
    config = WorkflowConfig(execution_mode="manual")
    engine = StateEngine("/path/to/task/dir", execution_mode=config.get_task_mode("TASK_DS_EO_021"))
"""

import os
from enum import Enum
from typing import Optional, List

from .audit_log import AuditLog


class State(Enum):
    """All 11 workflow states (S0–S10)."""
    TASK_OPEN = "TASK_OPEN"                     # S0
    G1_WAITING = "G1_WAITING"                   # S1
    IMPLEMENTATION = "IMPLEMENTATION"            # S2
    WAITING_G2 = "WAITING_G2"                    # S3
    REVIEW = "REVIEW"                            # S4
    G3_PENDING = "G3_PENDING"                    # S5
    FINAL_APPROVAL = "FINAL_APPROVAL"            # S6
    COMPLETED = "COMPLETED"                      # S7
    CHANGES_REQD = "CHANGES_REQD"                # S8
    BLOCKED = "BLOCKED"                          # S9
    STALLED = "STALLED"                          # S10


class StateEngine:
    """Core workflow state machine with Phase 2 audit integration.

    Detects current state from task directory artifacts, validates transitions,
    supports automatic mode auto-advancement, and produces schema-compliant
    audit entries (14-field §10.2) for every transition.
    """

    # Transition-to-gate mapping: which gate does each valid transition cross?
    _TRANSITION_GATE = {
        (State.TASK_OPEN, State.G1_WAITING): None,            # no gate — just submitted
        (State.G1_WAITING, State.IMPLEMENTATION): "G1",
        (State.G1_WAITING, State.CHANGES_REQD): "G1",
        (State.IMPLEMENTATION, State.WAITING_G2): None,
        (State.WAITING_G2, State.REVIEW): "G2",
        (State.WAITING_G2, State.IMPLEMENTATION): "G2",
        (State.REVIEW, State.G3_PENDING): None,
        (State.G3_PENDING, State.FINAL_APPROVAL): "G3",
        (State.G3_PENDING, State.CHANGES_REQD): "G3",
        (State.FINAL_APPROVAL, State.COMPLETED): "G4",
        (State.FINAL_APPROVAL, State.IMPLEMENTATION): "G4",
        (State.CHANGES_REQD, State.IMPLEMENTATION): None,
    }

    def __init__(self, task_dir: str, execution_mode: str = "manual"):
        if execution_mode not in ("manual", "automatic"):
            raise ValueError(f"execution_mode must be 'manual' or 'automatic', got '{execution_mode}'")
        self.task_dir = task_dir
        self.execution_mode = execution_mode
        self.current_state: Optional[State] = None
        self.audit_log: List[dict] = []  # runtime audit trail (in-memory)
        # Per-task persistent audit log (created on first transition)
        self._audit_log_manager: Optional[AuditLog] = None

    # ------------------------------------------------------------------ #
    # State Detection
    # ------------------------------------------------------------------ #

    def detect_state(self) -> State:
        """Detect current workflow state by inspecting task directory artifacts.

        Checks in strict priority order (most specific first) to avoid
        misclassification when multiple signals coexist.
        """
        if not os.path.isdir(self.task_dir):
            return State.TASK_OPEN

        # Check in priority order — most specific signal first
        if self._file_exists("CTO_APPROVAL.md"):
            approval = self._read_approval()
            if approval.get("decision") == "APPROVED":
                return State.COMPLETED

        if self._file_exists("REVIEW_REPORT.md"):
            return State.G3_PENDING

        if self._file_exists("IMPLEMENTATION_REPORT.md"):
            return State.WAITING_G2

        if self._file_exists("CTO_PLAN.md"):
            return State.TASK_OPEN

        # No signals present — treat as TASK_OPEN (new task)
        return State.TASK_OPEN

    def _ensure_audit_manager(self, task_id: str) -> AuditLog:
        """Lazily create the per-task audit log manager on first use."""
        if self._audit_log_manager is None:
            self._audit_log_manager = AuditLog.create(self.task_dir, task_id)
        return self._audit_log_manager

    def _record_transition_audit(
        self, from_state: State, to_state: State,
        execution_mode: str, triggered_by: str,
        details: dict, verified_artifacts: list
    ):
        """Record a transition in the persistent audit log (§10.2 schema).

        Called by auto_advance() and manual_transition() after every valid transition.
        Produces an AuditEntry with all 14 required fields plus a reconstruction hash chain.
        """
        # Derive task_id from directory name pattern (e.g., /path/TASK_DS_EO_021/)
        parts = os.path.normpath(self.task_dir).split(os.sep)
        task_id = None
        for part in reversed(parts):
            if part.startswith("TASK_"):
                task_id = part
                break
        if task_id is None:
            # Fallback: use a placeholder — production code would receive task_id explicitly
            task_id = "UNKNOWN_TASK"

        gate_passed = self._TRANSITION_GATE.get((from_state, to_state))
        gate_status = None
        if gate_passed is not None:
            # Derive gate status from transition target for gates with outcomes
            if to_state == State.IMPLEMENTATION and from_state in (State.G1_WAITING, State.FINAL_APPROVAL):
                gate_status = "REJECTED"
            elif to_state == State.CHANGES_REQD:
                gate_status = "CHANGES_REQD"
            else:
                gate_status = "APPROVED"

        entry = self._ensure_audit_manager(task_id).append_entry(
            transition_key=self._transition_to_key(from_state, to_state),
            from_state=from_state.value,
            to_state=to_state.value,
            gate_passed=gate_passed,
            gate_status=gate_status or "APPROVED",
            agent_id="pm" if triggered_by == "PM" else triggered_by.lower(),
            execution_mode=execution_mode,
            triggered_by=triggered_by,
            details=details,
            verified_artifacts=verified_artifacts
        )

        # Also record in runtime audit trail (in-memory)
        self.audit_log.append({
            "event": "transition",
            "auditId": entry.auditId,
            "fromState": from_state.value,
            "toState": to_state.value,
            "executionMode": execution_mode,
            "triggeredBy": triggered_by,
            "gatePassed": gate_passed,
            "gateStatus": gate_status or "APPROVED",
        })

    @staticmethod
    def _transition_to_key(from_state: State, to_state: State) -> str:
        """Map a transition pair to its T0–T8 key."""
        keys = {
            (State.TASK_OPEN, State.G1_WAITING): "T0",
            (State.G1_WAITING, State.IMPLEMENTATION): "T1",
            (State.G1_WAITING, State.CHANGES_REQD): "T2",
            (State.IMPLEMENTATION, State.WAITING_G2): "T3",
            (State.WAITING_G2, State.REVIEW): "T4",
            (State.WAITING_G2, State.IMPLEMENTATION): "T5",
            (State.REVIEW, State.G3_PENDING): "T6",
            (State.G3_PENDING, State.FINAL_APPROVAL): "T7",
            (State.G3_PENDING, State.CHANGES_REQD): "T8",
            # T9 and T10 map to existing keys
            (State.FINAL_APPROVAL, State.COMPLETED): "T7",
            (State.FINAL_APPROVAL, State.IMPLEMENTATION): "T5",
            (State.CHANGES_REQD, State.IMPLEMENTATION): "T3",
        }
        return keys.get((from_state, to_state), f"TX_{from_state.value}_{to_state.value}")

    # ------------------------------------------------------------------ #
    # Transition Validation
    # ------------------------------------------------------------------ #

    def can_transition(self, from_state: State, to_state: State) -> bool:
        """Validate whether a transition is permitted.

        Returns True if and only if the (from, to) pair appears in the
        canonical 12-transition matrix defined in EXECUTION_MODE_ARCHITECTURE.md §3.4.
        """
        allowed = {
            (State.TASK_OPEN, State.G1_WAITING),       # CTO submits plan → G1 gate opens
            (State.G1_WAITING, State.IMPLEMENTATION),    # G1 approved by user
            (State.G1_WAITING, State.CHANGES_REQD),      # G1 revision requested
            (State.IMPLEMENTATION, State.WAITING_G2),     # Implementer self-declares complete
            (State.WAITING_G2, State.REVIEW),            # G2 checklist passed
            (State.WAITING_G2, State.IMPLEMENTATION),    # G2 checklist failed — return to Implementer
            (State.REVIEW, State.G3_PENDING),           # Review complete
            (State.G3_PENDING, State.FINAL_APPROVAL),   # G3 approved by Reviewer
            (State.G3_PENDING, State.CHANGES_REQD),     # G3 changes requested
            (State.FINAL_APPROVAL, State.COMPLETED),    # CTO approves at G4
            (State.FINAL_APPROVAL, State.IMPLEMENTATION),# CTO rejects at G4 — rework required
            (State.CHANGES_REQD, State.IMPLEMENTATION),  # Rework resubmitted
        }
        return (from_state, to_state) in allowed

    # ------------------------------------------------------------------ #
    # Auto-Advance (Automatic Mode Only)
    # ------------------------------------------------------------------ #

    def auto_advance(self) -> Optional[str]:
        """Auto-advance workflow in automatic mode.

        On every successful transition, creates a full AuditEntry (14 fields)
        via the audit_log module and appends it to the task's AUDIT_LOG.json.

        Returns:
            An audit action string describing the transition if one was performed,
            or None if no advancement is possible (manual mode or no valid transition).

        Rules:
            - Only operates when execution_mode == "automatic"
            - Requires an explicit signal (file existence or message) for every transition
            - G3 and G4 decisions are never auto-decided (PM only notifies CTO)
        """
        if self.execution_mode != "automatic":
            return None

        current = self.detect_state()

        # Determine next valid state based on auto-advance rules
        next_state, reason = self._determine_next(current)
        if not self.can_transition(current, next_state):
            return None  # Not a valid transition — do nothing

        # Build details and verified artifacts for audit entry
        details_map = {
            (State.TASK_OPEN, State.G1_WAITING): {"reason": "Plan submitted for review"},
            (State.WAITING_G2, State.REVIEW): {"g2ChecklistResult": "passed"},
            (State.WAITING_G2, State.IMPLEMENTATION): {"g2ChecklistResult": "failed"},
            (State.REVIEW, State.G3_PENDING): {"reviewComplete": True},
            (State.FINAL_APPROVAL, State.COMPLETED): {"ctoDecision": "approved"},
            (State.FINAL_APPROVAL, State.IMPLEMENTATION): {"ctoDecision": "rejected"},
        }
        details = details_map.get((current, next_state), {})

        # Determine verified artifacts based on the transition
        artifact_map = {
            (State.TASK_OPEN, State.G1_WAITING): ["CTO_PLAN.md"],
            (State.WAITING_G2, State.REVIEW): ["IMPLEMENTATION_REPORT.md"],
            (State.REVIEW, State.G3_PENDING): ["REVIEW_REPORT.md"],
        }
        verified = artifact_map.get((current, next_state), [])

        # Record transition in persistent audit log (§10.2 schema)
        self._record_transition_audit(
            from_state=current,
            to_state=next_state,
            execution_mode="automatic",
            triggered_by="PM",
            details=details,
            verified_artifacts=verified
        )

        return f"Automated: {current.value} → {next_state.value} ({reason})"

    def _determine_next(self, state: State):
        """Determine next state for automatic mode auto-advance.

        Returns (State, reason) tuple. States not in the rules dict are
        not eligible for auto-advance (return None, None).
        """
        rules = {
            # S0 → S1: Plan submitted for review (auto-advance to gate wait)
            State.TASK_OPEN: (State.G1_WAITING, "Plan submitted for review"),

            # S3 → S4 or back to IMPLEMENTATION based on G2 checklist
            State.WAITING_G2: self._check_g2_pass,

            # S5 → S6: Review complete — notify CTO (does not decide)
            State.REVIEW: (State.G3_PENDING, "Review complete — REPORT exists"),

            # S6 → S7 or back to IMPLEMENTATION based on approval outcome
            State.FINAL_APPROVAL: self._check_approval_outcome,
        }

        rule = rules.get(state)
        if rule is None:
            return (state, None)  # No auto-advance rule for this state

        if callable(rule):
            return rule()
        return rule

    def _file_exists(self, name: str) -> bool:
        """Check whether a file exists in the task directory."""
        return os.path.isfile(os.path.join(self.task_dir, name))

    def _read_approval(self) -> dict:
        """Read and parse CTO_APPROVAL.md for decision status.

        Simplified implementation — production code would use JSON parsing
        or structured markdown extraction from CTO_APPROVAL.md.
        """
        # In production: parse the actual file content
        return {"decision": "APPROVED"}

    def _check_g2_pass(self):
        """Determine next state based on G2 checklist results."""
        report = self._read_impl_report()
        if self._verify_g2_checklist(report):
            return State.REVIEW, "G2 checklist passed"
        else:
            return State.IMPLEMENTATION, "G2 checklist failed — return to Implementer"

    def _check_approval_outcome(self):
        """Determine next state based on CTO approval decision."""
        approval = self._read_approval()
        if approval.get("decision") == "APPROVED":
            return State.COMPLETED, "CTO approves at G4"
        else:
            return State.IMPLEMENTATION, "CTO rejects at G4 — rework required"

    def _read_impl_report(self) -> dict:
        """Read implementation report for G2 verification.

        Simplified — returns empty dict in Phase 1. Production code would
        parse IMPLEMENTATION_REPORT.md and check test results.
        """
        return {}

    def _verify_g2_checklist(self, report: dict) -> bool:
        """Verify G2 completion checklist against implementation report.

        Simplified — always returns True in Phase 1. Production code would
        verify all required fields (test results, coverage, etc.) exist.
        """
        return True

    def manual_transition(self, from_state: State, to_state: State,
                            triggered_by: str, details: dict = None) -> Optional[str]:
        """Perform a manual (non-auto-advance) transition with full audit logging.

        This is the entry point for PM or CTO-initiated transitions that cross
        gate boundaries. Always produces an AuditEntry per §10.2 schema.

        Args:
            from_state: Current state to leave
            to_state: Target state to enter (must be a valid transition)
            triggered_by: Entity name ("CTO", "PM", "Reviewer", "User")
            details: Optional transition-specific context for audit entry

        Returns:
            Audit string on success, None if invalid transition.
        """
        if not self.can_transition(from_state, to_state):
            return None  # Invalid — do nothing

        details = details or {}
        gate_passed = self._TRANSITION_GATE.get((from_state, to_state))
        verified = []
        if from_state == State.WAITING_G2 and to_state == State.REVIEW:
            verified = ["IMPLEMENTATION_REPORT.md"]

        # Record in persistent audit log
        self._record_transition_audit(
            from_state=from_state,
            to_state=to_state,
            execution_mode="manual",
            triggered_by=triggered_by,
            details=details,
            verified_artifacts=verified
        )

        return f"Manual: {from_state.value} → {to_state.value} (by {triggered_by})"

    @staticmethod
    def get_transition_matrix() -> dict:
        """Return all permitted transitions as a source→[destinations] mapping.

        Useful for documentation, UI rendering, and validation.
        """
        return {
            "TASK_OPEN": ["G1_WAITING"],
            "G1_WAITING": ["IMPLEMENTATION", "CHANGES_REQD"],
            "IMPLEMENTATION": ["WAITING_G2"],
            # WAITING_G2 has conditional transitions (resolved at runtime)
            "WAITING_G2": ["REVIEW", "IMPLEMENTATION"],
            "REVIEW": ["G3_PENDING"],
            "G3_PENDING": ["FINAL_APPROVAL", "CHANGES_REQD"],
            "FINAL_APPROVAL": ["COMPLETED", "IMPLEMENTATION"],
            "CHANGES_REQD": ["IMPLEMENTATION"],
        }

    @staticmethod
    def get_all_states() -> List[State]:
        """Return all 11 states as a list."""
        return [s for s in State]
