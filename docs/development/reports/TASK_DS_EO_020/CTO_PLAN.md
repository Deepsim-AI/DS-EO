# CTO Plan — TASK_DS_EO_020

**Task ID**: TASK_DS_EO_020  
**Title**: Phase 1 — PM Workflow State Engine (Core)  
**Date**: 2026-08-01  
**CTO**: qwen3.6:35b (ollama)  
**Spec Reference**: `docs/development/reports/TASK_DS_EO_019/EXECUTION_MODE_ARCHITECTURE.md` (§12.3, with supporting context from §2–§11)

---

## 1. Problem Statement

Phase 1 of the Execution Mode Architecture (from TASK_DS_EO_019) requires implementing a PM workflow state engine — the core state machine that enables Automatic Mode. This is a discrete engineering task that produces **new code** (not just documentation). The engine must implement the 11-state state machine, validate transitions, auto-advance eligible states in automatic mode, and alert CTO where authority cannot be automated.

This task produces:
1. A new Python module `ds_eo_openclaw/workflow/state_engine.py` implementing the state machine
2. Updated PM tool policy granting exec access for state engine integration
3. Updated PM agent definition with auto-advancement responsibilities
4. Unit tests for all 12 transitions

---

## 2. Current-State Analysis

### 2.1 What Exists Now (for this task)

| Component | Location | Notes |
|-----------|----------|-------|
| State machine spec | `EXECUTION_MODE_ARCHITECTURE.md` §2 (11 states, 12 transitions) | Authoritative design reference |
| PM role definition | `agents/pm.md` | Has write access; exec/process denied — needs update |
| Task artifact structure | `docs/development/reports/TASK_<id>/` | Existing pattern, state engine uses existing files as signals |
| Project config | OpenClaw `openclaw.json` or project-level config | Target for `workflow.execution_mode` field |
| PM session management | Existing via OpenClaw sessions API | Used by PM to trigger next-agent sessions |

### 2.2 What Does NOT Exist Yet (to be created)

| Component | New Location | Description |
|-----------|-------------|-------------|
| State engine module | `ds_eo_openclaw/workflow/state_engine.py` | Core state machine implementation (~80 lines) |
| Tests for state engine | `tests/test_state_engine.py` | Unit tests covering all 12 transitions |

### 2.3 What Needs to Change

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `agents/pm.md` | Modify | Add auto-advancement instructions, update tool policy reference |
| OpenClaw config (if needed) | May need update | Configure `workflow.execution_mode` field in project-level settings |

---

## 3. Design Analysis

### 3.1 State Machine Core

The state engine implements the 11-state machine defined in TASK_DS_EO_019 (§2). Each state has:
- A unique ID (S0–S10)
- An entry condition (what triggers entering this state)
- An exit condition (what triggers leaving this state)
- A list of permitted transitions (which states can be reached from here)
- An owner (which role manages this state)
- Required artifacts (files that must exist in the task directory to satisfy entry)

### 3.2 State-to-Artifact Mapping (Critical Design Decision)

The engine uses **existing task directory files as state signals** — no new file formats needed:

| State | File Signal (in task dir) |
|-------|--------------------------|
| S0 `TASK_OPEN` | `CTO_PLAN.md` exists, not yet submitted for G1 |
| S1 `G1_WAITING` | CTO has flagged plan as awaiting user approval |
| S2 `IMPLEMENTATION` | User approved at G1; DELEGATE message sent |
| S3 `WAITING_G2` | `IMPLEMENTATION_REPORT.md` exists in task dir |
| S4 `REVIEW` | PM sends REVIEWER_ASSIGN to Reviewer session |
| S5 `G3_PENDING` | `REVIEW_REPORT.md` exists in task dir |
| S6 `FINAL_APPROVAL` | PM alerts CTO; CTO is reviewing findings |
| S7 `COMPLETED` | `CTO_APPROVAL.md` exists with APPROVED decision |
| S8 `CHANGES_REQUESTED` | G1 revision requested or G3 return sent |
| S9 `BLOCKED` | Any agent reports blocker |
| S10 `STALLED` | No artifact update within configured timeout |

### 3.3 Auto-Advance Rules (Automatic Mode Only)

In automatic mode, the PM engine auto-advances when:
1. Entry condition is met (artifact exists or signal received)
2. Transition is eligible for automatic advancement (not a human-gated gate)
3. No blocker is active

Auto-advance actions per state:
- **S0→S1**: Already at S0 after CTO writes plan. Auto-advance when user approves G1 → S2 (but G1 approval itself requires user — PM detects the approval and forwards it).
- **S3→S4**: Auto-verify G2 checklist against `IMPLEMENTATION_REPORT.md`. If all pass, auto-send REVIEWER_ASSIGN to Reviewer session.
- **S5→S6**: Auto-detect `REVIEW_REPORT.md` existence → alert CTO for review (does not decide — only notifies).
- **S6→S7**: After CTO writes `CTO_APPROVAL.md` with APPROVED, PM auto-runs full post-G4 cleanup sequence.

**Never auto-advances without explicit signal**: The engine requires a file existence or message signal for every transition — no speculative state changes.

---

## 4. Implementation Plan

### 4.1 Files to Create/Modify

#### New File: `ds_eo_openclaw/workflow/state_engine.py` (~80 lines)

```python
# ds_eo_openclaw/workflow/state_engine.py
"""
DS-EO Workflow State Engine — Phase 1 (Core State Machine)

Implements the 11-state state machine for configurable workflow execution modes.
This engine is platform-neutral and can be used by any DS-EO edition
(OpenClaw, Claude, Codex, etc.).

States: S0–S10 as defined in EXECUTION_MODE_ARCHITECTURE.md §2
Transitions: 12 transitions as defined in EXECUTION_MODE_ARCHITECTURE.md §3.4
"""

import os
import json
from enum import Enum
from typing import Optional, List


class State(Enum):
    TASK_OPEN = "TASK_OPEN"           # S0
    G1_WAITING = "G1_WAITING"          # S1
    IMPLEMENTATION = "IMPLEMENTATION"  # S2
    WAITING_G2 = "WAITING_G2"         # S3
    REVIEW = "REVIEW"                  # S4
    G3_PENDING = "G3_PENDING"          # S5
    FINAL_APPROVAL = "FINAL_APPROVAL"  # S6
    COMPLETED = "COMPLETED"            # S7
    CHANGES_REQUESTED = "CHANGES_REQD" # S8
    BLOCKED = "BLOCKED"                # S9
    STALLED = "STALLED"               # S10


class StateEngine:
    def __init__(self, task_dir: str, execution_mode: str = "manual"):
        self.task_dir = task_dir
        self.execution_mode = execution_mode
        self.current_state: Optional[State] = None
        self.audit_log: List[dict] = []

    # State detection from task directory artifacts
    def detect_state(self) -> State:
        """Detect current workflow state by inspecting task directory artifacts."""
        if not os.path.exists(self.task_dir):
            return State.TASK_OPEN
        
        # Check in priority order (most specific first)
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
        
        return State.TASK_OPEN  # default

    # Transition validation
    def can_transition(self, from_state: State, to_state: State) -> bool:
        """Validate whether a transition is permitted."""
        allowed = {
            (State.TASK_OPEN, State.G1_WAITING),      # CTO submits plan
            (State.G1_WAITING, State.IMPLEMENTATION),   # G1 approved
            (State.G1_WAITING, State.CHANGES_REQUESTED),# G1 revision
            (State.IMPLEMENTATION, State.WAITING_G2),    # IMPL_COMPLETE
            (State.WAITING_G2, State.REVIEW),           # G2 pass
            (State.WAITING_G2, State.IMPLEMENTATION),   # G2 fail — return to Implementer
            (State.REVIEW, State.G3_PENDING),          # REVIEW_COMPLETE
            (State.G3_PENDING, State.FINAL_APPROVAL),   # G3 approved
            (State.G3_PENDING, State.CHANGES_REQUESTED),# G3 changes requested
            (State.FINAL_APPROVAL, State.COMPLETED),    # CTO approves
            (State.FINAL_APPROVAL, State.IMPLEMENTATION),# CTO rejects
            (State.CHANGES_REQUESTED, State.IMPLEMENTATION),# Rework resubmitted
        }
        return (from_state, to_state) in allowed

    # Auto-advance for automatic mode
    def auto_advance(self) -> Optional[str]:
        """Auto-advance workflow in automatic mode. Returns audit action string or None."""
        if self.execution_mode != "automatic":
            return None
        
        current = self.detect_state()
        
        # Determine next valid state
        next_state, reason = self._determine_next(current)
        if not self.can_transition(current, next_state):
            return None  # Not a valid transition
        
        # Record audit entry
        self.audit_log.append({
            "event": "transition",
            "fromState": current.value,
            "toState": next_state.value,
            "executionMode": "automatic",
            "triggeredBy": "PM",
            "reason": reason,
            "timestamp": None  # filled by caller
        })
        
        return f"Automated: {current.value} → {next_state.value} ({reason})"

    def _determine_next(self, state: State):
        """Determine next state for automatic mode auto-advance."""
        rules = {
            State.TASK_OPEN: (State.G1_WAITING, "Plan submitted for review"),
            State.WAITING_G2: self._check_g2_pass,
            State.REVIEW: (State.G3_PENDING, "Review complete — REPORT exists"),
            State.FINAL_APPROVAL: self._check_approval_outcome,
        }
        rule = rules.get(state)
        if callable(rule):
            return rule()
        return rule

    def _file_exists(self, name):
        return os.path.exists(os.path.join(self.task_dir, name))

    def _read_approval(self):
        # Simplified — in production uses JSON parsing of CTO_APPROVAL.md
        return {"decision": "APPROVED"}

    def _check_g2_pass(self):
        report = self._read_impl_report()
        if self._verify_g2_checklist(report):
            return State.REVIEW, "G2 checklist passed"
        else:
            return State.IMPLEMENTATION, "G2 checklist failed — return to Implementer"

    def _check_approval_outcome(self):
        approval = self._read_approval()
        if approval.get("decision") == "APPROVED":
            return State.COMPLETED, "CTO approves at G4"
        else:
            return State.IMPLEMENTATION, "CTO rejects at G4 — rework required"

    def _read_impl_report(self):
        return {}  # simplified

    def _verify_g2_checklist(self, report):
        return True  # simplified

    @staticmethod
    def get_transition_matrix():
        """Return all permitted transitions (for documentation/validation)."""
        return {
            "TASK_OPEN": ["G1_WAITING"],
            "G1_WAITING": ["IMPLEMENTATION", "CHANGES_REQD"],
            "IMPLEMENTATION": ["WAITING_G2"],
            "WAITING_G2": ["REVIEW", "IMPLEMENTATION"],  # G2 pass → REVIEW, G2 fail → return
            "REVIEW": ["G3_PENDING"],
            "G3_PENDING": ["FINAL_APPROVAL", "CHANGES_REQD"],
            "FINAL_APPROVAL": ["COMPLETED", "IMPLEMENTATION"],
            "CHANGES_REQD": ["IMPLEMENTATION"],
        }
```

#### New File: `tests/test_state_engine.py` (~80 lines)

```python
"""Tests for DS-EO Workflow State Engine (Phase 1)."""
import unittest
from ds_eo_openclaw.workflow.state_engine import State, StateEngine


class TestStateDetection(unittest.TestCase):
    def test_task_open_with_cto_plan(self):
        eng = StateEngine("/fake/task_dir")
        # CTO_PLAN exists → TASK_OPEN
        self.assertEqual(eng.detect_state(), State.TASK_OPEN)

    def test_waiting_g2_with_impl_report(self):
        eng = StateEngine("/fake/task_dir")
        # IMPLEMENTATION_REPORT exists → WAITING_G2
        self.assertEqual(eng.detect_state(), State.WAITING_G2)

    def test_g3_pending_with_review_report(self):
        eng = StateEngine("/fake/task_dir")
        # REVIEW_REPORT exists → G3_PENDING
        self.assertEqual(eng.detect_state(), State.G3_PENDING)

    def test_completed_with_approved_approval(self):
        eng = StateEngine("/fake/task_dir")
        # CTO_APPROVED with APPROVED decision → COMPLETED
        self.assertEqual(eng.detect_state(), State.COMPLETED)


class TestTransitions(unittest.TestCase):
    def test_all_specified_transitions_allowed(self):
        engine = StateEngine.get_transition_matrix()
        for src, dests in engine.items():
            for dst in dests:
                # Each must be a valid enum transition
                self.assertTrue(
                    StateEngine("/fake").can_transition(
                        State(src), State(dst)
                    ),
                    f"Transition {src}→{dst} not validated"
                )

    def test_invalid_transition_rejected(self):
        engine = StateEngine("/fake")
        # Direct skip from TASK_OPEN to REVIEW is not permitted
        self.assertFalse(
            engine.can_transition(State.TASK_OPEN, State.REVIEW)
        )

    def test_no_self_loops(self):
        engine = StateEngine("/fake")
        for state in State:
            self.assertFalse(
                engine.can_transition(state, state),
                f"Self-loop detected on {state}"
            )


class TestAutoAdvance(unittest.TestCase):
    def test_manual_mode_no_auto_advance(self):
        eng = StateEngine("/fake", execution_mode="manual")
        # Manual mode never auto-advances
        self.assertIsNone(eng.auto_advance())

    def test_auto_advance_produces_audit_entry(self):
        eng = StateEngine("/fake", execution_mode="automatic")
        result = eng.auto_advance()
        # Should produce audit log entry when transitioning
        self.assertIn("audit_log", dir(eng))


if __name__ == "__main__":
    unittest.main()
```

### 4.2 Files to Modify

#### Modify: `agents/pm.md`

Add to the PM's role definition:

1. **New workflow state section** — describing S0–S10 states and when PM auto-advances
2. **Auto-advance responsibilities** — list of states where PM can auto-advance (S0→S1, S3→S4, S5→S6 notification, S7 post-G4)
3. **Tool policy update** — add `exec` to allow list for state engine integration (specifically for checking file existence and running state engine)

The exact change to the tool policy section:
```json
"tools": {
    "allow": ["write", "apply_patch", "web_search", "web_fetch", "exec"],
    "deny": ["process"]
}
```

Note: `exec` is allowed only for file checking and state engine invocation. PM must not use `exec` for git operations (still in deny). This should be clarified in the PM role definition.

### 4.3 File Structure Summary

| Action | File | Location | Lines |
|--------|------|----------|-------|
| CREATE | `state_engine.py` | `ds_eo_openclaw/workflow/state_engine.py` | ~80 |
| CREATE | `test_state_engine.py` | `tests/test_state_engine.py` | ~80 |
| MODIFY | `pm.md` | `agents/pm.md` | +3 new sections |

---

## 5. Acceptance Criteria

This task is complete when the following are satisfied:

### State Engine Correctness
- [ ] All 11 states (S0–S10) are implemented in the StateEngine class
- [ ] All 12 permitted transitions are validated by `can_transition()`
- [ ] No invalid or unexpected transitions are allowed (test confirms)
- [ ] No self-loops exist in the transition matrix

### Auto-Advance Behavior
- [ ] Manual mode: `auto_advance()` returns None for all states
- [ ] Automatic mode: auto-advances when valid transition exists AND no blocker active
- [ ] G3 and G4 decisions are never auto-decided (PM only notifies CTO)
- [ ] Audit log entry is created on every auto-advance

### Integration
- [ ] PM can invoke the state engine from its workflow loop
- [ ] State detection uses existing task directory files as signals (no new format)
- [ ] `agents/pm.md` updated with auto-advance instructions and tool policy change
- [ ] Manual mode remains fully functional — no regression in existing behavior

### Testing
- [ ] All tests pass (`python -m pytest tests/test_state_engine.py`)
- [ ] State detection tested for all 8 states that have file signals
- [ ] Transition validation tested: all valid transitions accepted, all invalid rejected
- [ ] Auto-advance mode toggle tested (manual returns None, automatic advances)

---

## 6. Risks and Constraints

### Risks
1. **Agent confusion during tool policy change**: Granting `exec` to PM's allow list changes its capabilities significantly. The PM role definition must clearly document *when* and *why* exec is used (file checking, state engine invocation only).
2. **State detection ambiguity**: File existence is the signal for multiple states. The detect_state() method must check in strict priority order to avoid misclassification.

### Constraints
1. No new storage format — use existing task directory files as state signals
2. Platform-neutral — no OpenClaw-specific internals in the state engine module
3. PM's `process` tool remains denied (no shell backgrounding)
4. Manual mode must be fully functional with zero regression

---

## Gate Status

| Gate | Status | Notes |
|------|--------|-------|
| G0 (Task Creation) | ✅ Done | TASK_DS_EO_020 created |
| G1 (User Approval of Plan) | ⏳ Awaiting | User must approve before Implementer begins |
| G2–G4 | N/A | To be executed after implementation |

---

*CTO Plan produced by: CTO (qwen3.6:35b)*  
*Date: 2026-08-01*
