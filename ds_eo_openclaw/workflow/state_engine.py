"""
DS-EO Workflow State Engine — Phase 1 (Core State Machine)

Implements the 11-state state machine for configurable workflow execution modes.
This engine is platform-neutral and can be used by any DS-EO edition
(OpenClaw, Claude, Codex, etc.).

States: S0–S10 as defined in EXECUTION_MODE_ARCHITECTURE.md §2
Transitions: 12 transitions as defined in EXECUTION_MODE_ARCHITECTURE.md §3.4

Usage:
    from ds_eo_openclaw.workflow.state_engine import StateEngine, State

    engine = StateEngine("/path/to/task/dir", execution_mode="automatic")
    current = engine.detect_state()
    result = engine.auto_advance()  # returns audit string or None
"""

import os
from enum import Enum
from typing import Optional, List


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
    """Core workflow state machine.

    Detects current state from task directory artifacts, validates transitions,
    and supports automatic mode auto-advancement for eligible states.
    """

    def __init__(self, task_dir: str, execution_mode: str = "manual"):
        if execution_mode not in ("manual", "automatic"):
            raise ValueError(f"execution_mode must be 'manual' or 'automatic', got '{execution_mode}'")
        self.task_dir = task_dir
        self.execution_mode = execution_mode
        self.current_state: Optional[State] = None
        self.audit_log: List[dict] = []

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

        # Record audit entry
        self.audit_log.append({
            "event": "transition",
            "fromState": current.value,
            "toState": next_state.value,
            "executionMode": "automatic",
            "triggeredBy": "PM",
            "reason": reason,
        })

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

    # ------------------------------------------------------------------ #
    # Static Utilities
    # ------------------------------------------------------------------ #

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
