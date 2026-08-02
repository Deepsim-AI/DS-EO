"""Tests for DS-EO Workflow State Engine (Phase 1).

Covers all acceptance criteria from TASK_DS_EO_020:
  - State detection for all signal-based states
  - Transition validation (all valid accepted, invalid rejected)
  - Auto-advance behavior (manual vs automatic mode)
  - No self-loops in transition matrix
"""

import os
import tempfile
import unittest

from ds_eo_openclaw.workflow.state_engine import State, StateEngine


class TestStateDetection(unittest.TestCase):
    """Verify state detection uses existing task directory files as signals."""

    def setUp(self):
        # Create a temp directory with controlled file presence
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_file(self, name):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write("signal")

    # -- Signal-based state detection ---------------------------------- #

    def test_task_open_with_cto_plan_only(self):
        """CTO_PLAN.md exists → TASK_OPEN (S0)."""
        self._write_file("CTO_PLAN.md")
        eng = StateEngine(self.tmpdir)
        self.assertEqual(eng.detect_state(), State.TASK_OPEN)

    def test_waiting_g2_with_impl_report(self):
        """IMPLEMENTATION_REPORT.md exists → WAITING_G2 (S3)."""
        self._write_file("CTO_PLAN.md")       # lower priority
        self._write_file("IMPLEMENTATION_REPORT.md")  # higher priority
        eng = StateEngine(self.tmpdir)
        self.assertEqual(eng.detect_state(), State.WAITING_G2)

    def test_g3_pending_with_review_report(self):
        """REVIEW_REPORT.md exists → G3_PENDING (S5)."""
        for f in ("CTO_PLAN.md", "IMPLEMENTATION_REPORT.md"):
            self._write_file(f)
        self._write_file("REVIEW_REPORT.md")
        eng = StateEngine(self.tmpdir)
        self.assertEqual(eng.detect_state(), State.G3_PENDING)

    def test_completed_with_approved_approval(self):
        """CTO_APPROVAL.md with APPROVED decision → COMPLETED (S7)."""
        for f in ("CTO_PLAN.md", "IMPLEMENTATION_REPORT.md", "REVIEW_REPORT.md"):
            self._write_file(f)
        self._write_file("CTO_APPROVAL.md")  # highest priority signal
        eng = StateEngine(self.tmpdir)
        self.assertEqual(eng.detect_state(), State.COMPLETED)

    def test_empty_dir_returns_task_open(self):
        """No files present → TASK_OPEN (S0)."""
        eng = StateEngine(self.tmpdir)
        self.assertEqual(eng.detect_state(), State.TASK_OPEN)


class TestTransitionValidation(unittest.TestCase):
    """Verify all 12 permitted transitions are accepted and invalid ones rejected."""

    def setUp(self):
        self.engine = StateEngine("/fake")

    def test_all_specified_transitions_allowed(self):
        """Every transition in the static matrix must pass can_transition()."""
        engine = StateEngine.get_transition_matrix()
        for src, dests in engine.items():
            for dst in dests:
                self.assertTrue(
                    self.engine.can_transition(State(src), State(dst)),
                    f"Transition {src}→{dst} not validated"
                )

    def test_invalid_transition_rejected(self):
        """Direct skip from TASK_OPEN to REVIEW is not permitted."""
        self.assertFalse(
            self.engine.can_transition(State.TASK_OPEN, State.REVIEW)
        )

    def test_no_self_loops(self):
        """No state can transition to itself."""
        for state in State:
            self.assertFalse(
                self.engine.can_transition(state, state),
                f"Self-loop detected on {state}"
            )

    def test_count_of_permitted_transitions(self):
        """Exactly 12 transitions must be permitted (per spec)."""
        count = sum(len(dests) for dests in StateEngine.get_transition_matrix().values())
        self.assertEqual(count, 12, f"Expected 12 transitions, got {count}")


class TestAutoAdvance(unittest.TestCase):
    """Verify auto-advance behavior respects execution mode and transition rules."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_manual_mode_no_auto_advance(self):
        """Manual mode: auto_advance() returns None for all states."""
        eng = StateEngine(self.tmpdir, execution_mode="manual")
        # Force various states by writing files
        for state in (State.TASK_OPEN, State.WAITING_G2, State.REVIEW, State.FINAL_APPROVAL):
            eng.current_state = state  # bypass detection for this test
            self.assertIsNone(eng.auto_advance(), f"Manual mode advanced from {state}")

    def test_auto_advance_uses_detect_state(self):
        """auto_advance() always uses detect_state(), not current_state."""
        eng = StateEngine(self.tmpdir, execution_mode="automatic")
        # Even if we set current_state manually, auto_advance calls detect_state()
        eng.current_state = State.STALLED  # should be ignored
        result = eng.auto_advance()  # detects TASK_OPEN → advances S0→S1
        self.assertIsNotNone(result)
        self.assertIn("G1_WAITING", result)

    def test_auto_advance_produces_audit_entry(self):
        """Auto-advancing from TASK_OPEN should produce an audit log entry."""
        eng = StateEngine(self.tmpdir, execution_mode="automatic")
        result = eng.auto_advance()
        # Should transition S0→S1 (TASK_OPEN → G1_WAITING)
        self.assertIsNotNone(result)
        self.assertIn("G1_WAITING", result)
        self.assertEqual(len(eng.audit_log), 1, "Expected exactly one audit entry")

    def test_auto_advance_invalid_mode_raises(self):
        """Invalid execution_mode raises ValueError."""
        with self.assertRaises(ValueError):
            StateEngine(self.tmpdir, execution_mode="invalid")


class TestStateEnum(unittest.TestCase):
    """Verify the State enum has all 11 states defined."""

    def test_all_states_present(self):
        expected_names = [
            "TASK_OPEN", "G1_WAITING", "IMPLEMENTATION", "WAITING_G2",
            "REVIEW", "G3_PENDING", "FINAL_APPROVAL", "COMPLETED",
            "CHANGES_REQD", "BLOCKED", "STALLED"
        ]
        actual_names = [s.name for s in State]
        self.assertEqual(len(actual_names), 11, f"Expected 11 states, got {len(actual_names)}")
        for name in expected_names:
            self.assertIn(name, actual_names, f"Missing state: {name}")


if __name__ == "__main__":
    unittest.main()
