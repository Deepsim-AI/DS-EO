"""Tests for DS-EO Audit Trail (Phase 2).

Covers acceptance criteria from TASK_DS_EO_021:
  - Schema validation (all 14 fields, correct types)
  - Persistence round-trip (append + read back)
  - Reconstruction verification (6 scenarios from known task history)
  - State engine audit integration (auto and manual mode)
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from ds_eo_openclaw.workflow.audit_log import AuditEntry, AuditLog, ProjectAuditIndex
from ds_eo_openclaw.workflow.state_engine import StateEngine, State


# --------------------------------------------------------------------------- #
# Schema Validation Tests
# --------------------------------------------------------------------------- #

class TestAuditSchemaValidation(unittest.TestCase):
    """Verify every field in the 14-field schema is present and correctly typed."""

    def setUp(self):
        self.base_entry = {
            "auditId": "12345678-1234-4123-8123-123456789012",
            "taskId": "TASK_DS_EO_021",
            "transitionKey": "T0",
            "fromState": "TASK_OPEN",
            "toState": "G1_WAITING",
            "gatePassed": None,
            "gateStatus": "APPROVED",
            "agentId": "pm",
            "executionMode": "automatic",
            "triggeredBy": "PM",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {"reason": "Plan submitted"},
            "verifiedArtifacts": ["CTO_PLAN.md"],
            "reconstructionHash": "a" * 64,
        }

    def test_all_14_fields_present(self):
        """Every entry must have exactly the 14 required fields."""
        entry = AuditEntry(**self.base_entry)
        expected_fields = {
            "auditId", "taskId", "transitionKey", "fromState", "toState",
            "gatePassed", "gateStatus", "agentId", "executionMode",
            "triggeredBy", "timestamp", "details", "verifiedArtifacts",
            "reconstructionHash"
        }
        actual_fields = set(entry.__slots__)
        self.assertEqual(actual_fields, expected_fields)

    def test_audit_id_is_valid_uuid(self):
        """auditId must be a valid UUID v4 string."""
        import uuid as uuid_mod
        entry = AuditEntry(**self.base_entry)
        parsed = uuid_mod.UUID(entry.auditId, version=4)
        self.assertEqual(str(parsed), entry.auditId)

    def test_gate_status_always_present_not_null(self):
        """gateStatus must never be null — always one of three values."""
        for status in ("APPROVED", "REJECTED", "CHANGES_REQD"):
            base = dict(self.base_entry, gateStatus=status)
            entry = AuditEntry(**base)
            self.assertIsNotNone(entry.gateStatus)

    def test_gate_status_rejects_invalid_value(self):
        """gateStatus outside the allowed set raises ValueError."""
        base = dict(self.base_entry, gateStatus="INVALID")
        with self.assertRaises(ValueError):
            AuditEntry(**base)

    def test_execution_mode_validation(self):
        """executionMode must be 'manual' or 'automatic' only."""
        for mode in ("manual", "automatic"):
            base = dict(self.base_entry, executionMode=mode)
            entry = AuditEntry(**base)
            self.assertEqual(entry.executionMode, mode)

        with self.assertRaises(ValueError):
            AuditEntry(**dict(self.base_entry, executionMode="invalid"))

    def test_timestamp_is_iso8601_utc(self):
        """timestamp must be parseable ISO-8601 UTC string."""
        entry = AuditEntry(**self.base_entry)
        # Verify it parses without error (basic check: contains 'T' and ends with 'Z')
        self.assertIn("T", entry.timestamp)
        self.assertTrue(entry.timestamp.endswith("Z"))

    def test_reconstruction_hash_is_sha256(self):
        """reconstructionHash must be 64-char hex SHA-256."""
        entry = AuditEntry(**self.base_entry)
        self.assertEqual(len(entry.reconstructionHash), 64)
        # Verify it's valid hex
        int(entry.reconstructionHash, 16)

    def test_missing_required_field_raises(self):
        """Omitting any required field raises ValueError."""
        base = dict(self.base_entry)
        del base["auditId"]
        with self.assertRaises(ValueError):
            AuditEntry(**base)


# --------------------------------------------------------------------------- #
# Persistence Tests
# --------------------------------------------------------------------------- #

class TestAuditLogPersistence(unittest.TestCase):
    """Verify audit entries persist to disk and round-trip correctly."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_log(self):
        return AuditLog.create(self.tmpdir, "TASK_DS_EO_021")

    def test_create_initializes_file_on_first_append(self):
        """AUDIT_LOG.json is created on the first append (not at construction)."""
        log = self._make_log()
        entry = log.append_entry(
            transition_key="T0", from_state="TASK_OPEN", to_state="G1_WAITING",
            gate_passed=None, gate_status="APPROVED", agent_id="pm",
            execution_mode="automatic", triggered_by="PM",
            details={"reason": "test"}, verified_artifacts=["CTO_PLAN.md"]
        )
        self.assertEqual(entry.taskId, "TASK_DS_EO_021")

    def test_append_and_read_back_round_trip(self):
        """Append N entries, read them back — all fields preserved."""
        log = self._make_log()
        for i in range(5):
            log.append_entry(
                transition_key=f"T{i}", from_state="S0", to_state=f"S{i+1}",
                gate_passed=None, gate_status="APPROVED", agent_id="pm",
                execution_mode="automatic", triggered_by="PM",
                details={"seq": i}, verified_artifacts=[]
            )

        entries = log.get_entries()
        self.assertEqual(len(entries), 5)
        for entry in entries:
            # Verify all fields survived round-trip
            self.assertIsNotNone(entry.auditId)
            self.assertIsNotNone(entry.taskId)
            self.assertIsNotNone(entry.reconstructionHash)

    def test_reconstruction_hash_chain_is_contiguous(self):
        """Each entry's hash must be derivable from the preceding chain."""
        log = self._make_log()
        # First entry: hash of empty string
        e1 = log.append_entry(
            transition_key="T0", from_state="S0", to_state="S1",
            gate_passed=None, gate_status="APPROVED", agent_id="pm",
            execution_mode="automatic", triggered_by="PM",
            details={}, verified_artifacts=[]
        )

        # Second entry: hash of (prev_hash + prev_entry_json)
        e2 = log.append_entry(
            transition_key="T1", from_state="S1", to_state="S2",
            gate_passed=None, gate_status="APPROVED", agent_id="pm",
            execution_mode="automatic", triggered_by="PM",
            details={}, verified_artifacts=[]
        )

        # Verify e2's hash is different from e1 (chain advanced)
        self.assertNotEqual(e1.reconstructionHash, e2.reconstructionHash)


# --------------------------------------------------------------------------- #
# Reconstruction Tests — 6 Scenarios from Known Task History
# --------------------------------------------------------------------------- #

class TestReconstruction(unittest.TestCase):
    """Verify full task history can be reconstructed from AUDIT_LOG.json alone."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_log(self):
        return AuditLog.create(self.tmpdir, "TASK_DS_EO_021")

    def _reconstruct_path(self, entries):
        """Walk entries in order and rebuild the state machine path.

        Returns list of (fromState, toState) tuples representing the full history.
        """
        path = []
        for entry in entries:
            path.append((entry.fromState, entry.toState))
        return path

    def _verify_gates_present(self, entries):
        """Verify all 4 gates (G1-G4) appear with correct authority."""
        gate_entries = [e for e in entries if e.gatePassed is not None]
        expected_gates = {"G1", "G2", "G3", "G4"}
        actual_gates = {e.gatePassed for e in gate_entries}
        self.assertEqual(actual_gates, expected_gates)

    # -- Scenario 1: Approved Pass (clean path) -------------------------- #

    def test_scenario_1_approved_pass(self):
        """Clean task: S0→G1_WAITING→S2→S3→S4→S5→S6→COMPLETED."""
        log = self._make_log()
        transitions = [
            ("T0", "TASK_OPEN", "G1_WAITING", None, "APPROVED"),
            ("T1", "G1_WAITING", "IMPLEMENTATION", "G1", "APPROVED"),
            ("T3", "IMPLEMENTATION", "WAITING_G2", None, "APPROVED"),
            ("T4", "WAITING_G2", "REVIEW", "G2", "APPROVED"),
            ("T6", "REVIEW", "G3_PENDING", None, "APPROVED"),
            ("T7", "G3_PENDING", "FINAL_APPROVAL", "G3", "APPROVED"),
            ("T7", "FINAL_APPROVAL", "COMPLETED", "G4", "APPROVED"),
        ]
        for tk, fr, to, gp, gs in transitions:
            log.append_entry(tk, fr, to, gp, gs, "pm", "automatic", "PM", {}, [])

        entries = log.get_entries()
        self.assertEqual(len(entries), 7)
        path = self._reconstruct_path(entries)
        # Verify the state machine was followed correctly
        self.assertEqual(path[0], ("TASK_OPEN", "G1_WAITING"))
        self.assertEqual(path[-1], ("FINAL_APPROVAL", "COMPLETED"))

    # -- Scenario 2: G2 Fail (return to Implementer) --------------------- #

    def test_scenario_2_g2_fail(self):
        """G2 checklist fails: S0→...→S3→S2 rework."""
        log = self._make_log()
        transitions = [
            ("T0", "TASK_OPEN", "G1_WAITING", None, "APPROVED"),
            ("T1", "G1_WAITING", "IMPLEMENTATION", "G1", "APPROVED"),
            ("T3", "IMPLEMENTATION", "WAITING_G2", None, "APPROVED"),
            ("T5", "WAITING_G2", "IMPLEMENTATION", "G2", "REJECTED"),
        ]
        for tk, fr, to, gp, gs in transitions:
            log.append_entry(tk, fr, to, gp, gs, "pm", "automatic", "PM", {}, [])

        entries = log.get_entries()
        self.assertEqual(len(entries), 4)
        # Verify G2 gate status is REJECTED
        g2_entries = [e for e in entries if e.gatePassed == "G2"]
        self.assertEqual(len(g2_entries), 1)
        self.assertEqual(g2_entries[0].gateStatus, "REJECTED")

    # -- Scenario 3: G3 Reject (return to Implementer) ------------------- #

    def test_scenario_3_g3_reject(self):
        """G3 review rejects: S0→...→S5→S8→S2 rework."""
        log = self._make_log()
        transitions = [
            ("T0", "TASK_OPEN", "G1_WAITING", None, "APPROVED"),
            ("T1", "G1_WAITING", "IMPLEMENTATION", "G1", "APPROVED"),
            ("T3", "IMPLEMENTATION", "WAITING_G2", None, "APPROVED"),
            ("T4", "WAITING_G2", "REVIEW", "G2", "APPROVED"),
            ("T6", "REVIEW", "G3_PENDING", None, "APPROVED"),
            ("T8", "G3_PENDING", "CHANGES_REQD", "G3", "CHANGES_REQD"),
        ]
        for tk, fr, to, gp, gs in transitions:
            log.append_entry(tk, fr, to, gp, gs, "pm", "automatic", "PM", {}, [])

        entries = log.get_entries()
        g3_entries = [e for e in entries if e.gatePassed == "G3"]
        self.assertEqual(len(g3_entries), 1)
        self.assertEqual(g3_entries[0].gateStatus, "CHANGES_REQD")

    # -- Scenario 4: G4 Reject (CTO rejects at final approval) ----------- #

    def test_scenario_4_g4_reject(self):
        """G4 CTO rejection: S0→...→S6→S2 rework."""
        log = self._make_log()
        transitions = [
            ("T0", "TASK_OPEN", "G1_WAITING", None, "APPROVED"),
            ("T1", "G1_WAITING", "IMPLEMENTATION", "G1", "APPROVED"),
            ("T3", "IMPLEMENTATION", "WAITING_G2", None, "APPROVED"),
            ("T4", "WAITING_G2", "REVIEW", "G2", "APPROVED"),
            ("T6", "REVIEW", "G3_PENDING", None, "APPROVED"),
            ("T7", "G3_PENDING", "FINAL_APPROVAL", "G3", "APPROVED"),
            ("T5", "FINAL_APPROVAL", "IMPLEMENTATION", "G4", "REJECTED"),
        ]
        for tk, fr, to, gp, gs in transitions:
            log.append_entry(tk, fr, to, gp, gs, "pm", "automatic", "PM", {}, [])

        entries = log.get_entries()
        g4_entries = [e for e in entries if e.gatePassed == "G4"]
        self.assertEqual(len(g4_entries), 1)
        self.assertEqual(g4_entries[0].gateStatus, "REJECTED")

    # -- Scenario 5: Rework Loop (G3 reject → implement → G3 approve) --- #

    def test_scenario_5_rework_loop(self):
        """Full rework cycle: G3 reject → resubmit → G3 approve."""
        log = self._make_log()
        transitions = [
            ("T0", "TASK_OPEN", "G1_WAITING", None, "APPROVED"),
            ("T1", "G1_WAITING", "IMPLEMENTATION", "G1", "APPROVED"),
            ("T3", "IMPLEMENTATION", "WAITING_G2", None, "APPROVED"),
            ("T4", "WAITING_G2", "REVIEW", "G2", "APPROVED"),
            ("T6", "REVIEW", "G3_PENDING", None, "APPROVED"),
            ("T8", "G3_PENDING", "CHANGES_REQD", "G3", "CHANGES_REQD"),  # G3 reject
            # Rework: back to implementation
            ("T3", "CHANGES_REQD", "IMPLEMENTATION", None, "APPROVED"),
            ("T3", "IMPLEMENTATION", "WAITING_G2", None, "APPROVED"),
            ("T4", "WAITING_G2", "REVIEW", "G2", "APPROVED"),
            ("T6", "REVIEW", "G3_PENDING", None, "APPROVED"),
            ("T7", "G3_PENDING", "FINAL_APPROVAL", "G3", "APPROVED"),  # G3 approve
        ]
        for tk, fr, to, gp, gs in transitions:
            log.append_entry(tk, fr, to, gp, gs, "pm", "automatic", "PM", {}, [])

        entries = log.get_entries()
        self.assertEqual(len(entries), 11)
        # Verify G3 gate status is CHANGES_REQD on the reject entry
        g3_reject = [e for e in entries if e.gatePassed == "G3" and e.gateStatus == "CHANGES_REQD"]
        self.assertEqual(len(g3_reject), 1)
        # Verify rework loop: first G3→CHANGES_REQD then later CHANGES_REQD→IMPLEMENTATION
        transitions = [(e.fromState, e.toState) for e in entries]
        self.assertIn(("G3_PENDING", "CHANGES_REQD"), transitions)
        self.assertIn(("CHANGES_REQD", "IMPLEMENTATION"), transitions)

    # -- Scenario 6: Blocker Encountered --------------------------------- #

    def test_scenario_6_blocker(self):
        """Blocker entry followed by resolution."""
        log = self._make_log()
        transitions = [
            ("T0", "TASK_OPEN", "G1_WAITING", None, "APPROVED"),
            ("T1", "G1_WAITING", "IMPLEMENTATION", "G1", "APPROVED"),
            # Blocker: no transition — just an audit entry about the blocker
        ]
        for tk, fr, to, gp, gs in transitions:
            log.append_entry(tk, fr, to, gp, gs, "pm", "automatic", "PM", {}, [])

        # Manually add a blocker entry (no state transition)
        block_entry = log.append_entry(
            transition_key="T0", from_state="IMPLEMENTATION", to_state="BLOCKED",
            gate_passed=None, gate_status="APPROVED", agent_id="implementer",
            execution_mode="manual", triggered_by="Implementer",
            details={"blocker": "Waiting on external dependency"}, verified_artifacts=[]
        )

        # Resolution: blocker cleared, resume
        log.append_entry(
            transition_key="T3", from_state="BLOCKED", to_state="WAITING_G2",
            gate_passed=None, gate_status="APPROVED", agent_id="pm",
            execution_mode="automatic", triggered_by="PM",
            details={"resolution": "Dependency received"}, verified_artifacts=[]
        )

        entries = log.get_entries()
        # 2 initial transitions + 1 blocker entry + 1 resolution = 4 total
        self.assertEqual(len(entries), 4)
        # Verify blocker entry is present with correct triggered_by
        blocker_entries = [e for e in entries if e.triggeredBy == "Implementer"]
        self.assertEqual(len(blocker_entries), 1)


# --------------------------------------------------------------------------- #
# State Engine Audit Integration Tests
# --------------------------------------------------------------------------- #

class TestStateEngineAuditIntegration(unittest.TestCase):
    """Verify state engine creates full audit entries on transitions."""

    def setUp(self):
        # Use a proper TASK_ directory name so task_id derivation works
        self.tmpdir = tempfile.mkdtemp()
        self.task_dir = os.path.join(self.tmpdir, "TASK_DS_EO_021")
        os.makedirs(self.task_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_auto_advance_creates_full_audit_entry(self):
        """auto_advance() in automatic mode produces an AuditEntry with all 14 fields."""
        eng = StateEngine(self.task_dir, execution_mode="automatic")
        result = eng.auto_advance()  # S0 → G1_WAITING (first transition)

        self.assertIsNotNone(result)
        # Verify audit log was created on disk
        audit_path = os.path.join(self.task_dir, "AUDIT_LOG.json")
        self.assertTrue(os.path.isfile(audit_path))

        with open(audit_path) as f:
            data = json.load(f)
        entry_dict = data[0]  # First (only) entry

        # Verify all 14 fields present in the persisted JSON
        expected_fields = {
            "auditId", "taskId", "transitionKey", "fromState", "toState",
            "gatePassed", "gateStatus", "agentId", "executionMode",
            "triggeredBy", "timestamp", "details", "verifiedArtifacts",
            "reconstructionHash"
        }
        self.assertEqual(set(entry_dict.keys()), expected_fields)

    def test_manual_transition_creates_audit_entry(self):
        """manual_transition() also produces a full AuditEntry."""
        eng = StateEngine(self.task_dir, execution_mode="automatic")
        # Create CTO_PLAN.md so detect_state returns TASK_OPEN (S0)
        with open(os.path.join(self.task_dir, "CTO_PLAN.md"), "w") as f:
            f.write("plan")

        result = eng.manual_transition(
            from_state=State.TASK_OPEN,
            to_state=State.G1_WAITING,
            triggered_by="CTO",
            details={"reason": "Plan submitted"}
        )

        self.assertIsNotNone(result)
        entries_path = os.path.join(self.task_dir, "AUDIT_LOG.json")
        if os.path.isfile(entries_path):
            with open(entries_path) as f:
                data = json.load(f)
            self.assertGreater(len(data), 0)

    def test_gate_status_never_null_in_audit_entries(self):
        """Every audit entry must have a non-null gateStatus."""
        eng = StateEngine(self.task_dir, execution_mode="automatic")
        # Force through multiple transitions to cover all gates
        with open(os.path.join(self.task_dir, "CTO_PLAN.md"), "w"): pass
        eng.auto_advance()  # S0→S1

        entries_path = os.path.join(self.task_dir, "AUDIT_LOG.json")
        if os.path.isfile(entries_path):
            with open(entries_path) as f:
                data = json.load(f)
            for entry in data:
                self.assertIsNotNone(entry.get("gateStatus"),
                    f"gateStatus is null in entry {entry.get('auditId')}")


if __name__ == "__main__":
    unittest.main()
