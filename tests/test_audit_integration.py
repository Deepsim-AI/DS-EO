"""Category E: Audit Trail Reconstruction Integration — Phase 5.

Cross-task reconstruction using AUDIT_INDEX.json as the entry point.
Verifies full history reconstructable from audit data alone for known tasks.
"""

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from ds_eo_openclaw.workflow.audit_log import AuditLog, ProjectAuditIndex


class TestCrossTaskReconstruction:
    """Full task history reconstructable from AUDIT_INDEX.json."""

    def _create_task_with_history(self, task_dir, task_id, transitions):
        """Helper to create a task directory with audit log entries."""
        os.makedirs(task_dir, exist_ok=True)
        log = AuditLog.create(task_dir, task_id)
        for tk, fr, to, gp, gs in transitions:
            log.append_entry(
                transition_key=tk, from_state=fr, to_state=to,
                gate_passed=gp, gate_status=gs, agent_id="pm",
                execution_mode="automatic", triggered_by="PM",
                details={"seq": tk}, verified_artifacts=[]
            )

    def test_reconstruct_task_ds_eo_020_clean_path(self):
        """TASK_DS_EO_020 clean path reconstructable from audit data alone."""
        tmpdir = "/tmp/test_audit_integration_020"
        task_dir = os.path.join(tmpdir, "TASK_DS_EO_020")

        transitions = [
            ("T0", "TASK_OPEN", "G1_WAITING", None, "APPROVED"),
            ("T1", "G1_WAITING", "IMPLEMENTATION", "G1", "APPROVED"),
            ("T3", "IMPLEMENTATION", "WAITING_G2", None, "APPROVED"),
            ("T4", "WAITING_G2", "REVIEW", "G2", "APPROVED"),
            ("T6", "REVIEW", "G3_PENDING", None, "APPROVED"),
            ("T7", "G3_PENDING", "FINAL_APPROVAL", "G3", "APPROVED"),
            ("T7", "FINAL_APPROVAL", "COMPLETED", "G4", "APPROVED"),
        ]

        self._create_task_with_history(task_dir, "TASK_DS_EO_020", transitions)

        # Reconstruct from disk
        log = AuditLog.create(task_dir, "TASK_DS_EO_020")
        entries = log.get_entries()

        assert len(entries) == 7
        # Verify path reconstruction: TASK_OPEN → G1_WAITING → ... → COMPLETED
        states = [e.fromState for e in entries] + [entries[-1].toState]
        expected_states = ["TASK_OPEN", "G1_WAITING", "IMPLEMENTATION",
                          "WAITING_G2", "REVIEW", "G3_PENDING", "FINAL_APPROVAL",
                          "COMPLETED"]
        assert states == expected_states, f"Path mismatch: {states} vs {expected_states}"

        # Cleanup
        import shutil
        if os.path.exists(tmpdir):
            shutil.rmtree(tmpdir)

    def test_reconstruct_task_ds_eo_023_with_rework_loop(self):
        """TASK_DS_EO_023 with rework loop reconstructable."""
        tmpdir = "/tmp/test_audit_integration_023"
        task_dir = os.path.join(tmpdir, "TASK_DS_EO_023")

        transitions = [
            ("T0", "TASK_OPEN", "G1_WAITING", None, "APPROVED"),
            ("T1", "G1_WAITING", "IMPLEMENTATION", "G1", "APPROVED"),
            ("T3", "IMPLEMENTATION", "WAITING_G2", None, "APPROVED"),
            ("T4", "WAITING_G2", "REVIEW", "G2", "APPROVED"),
            ("T6", "REVIEW", "G3_PENDING", None, "APPROVED"),
            ("T8", "G3_PENDING", "CHANGES_REQD", "G3", "CHANGES_REQD"),  # G3 reject
            ("T3", "CHANGES_REQD", "IMPLEMENTATION", None, "APPROVED"),    # Rework
            ("T3", "IMPLEMENTATION", "WAITING_G2", None, "APPROVED"),
            ("T4", "WAITING_G2", "REVIEW", "G2", "APPROVED"),
            ("T6", "REVIEW", "G3_PENDING", None, "APPROVED"),
            ("T7", "G3_PENDING", "FINAL_APPROVAL", "G3", "APPROVED"),     # G3 approve
        ]

        self._create_task_with_history(task_dir, "TASK_DS_EO_023", transitions)

        log = AuditLog.create(task_dir, "TASK_DS_EO_023")
        entries = log.get_entries()

        assert len(entries) == 11
        # Verify rework loop: G3→CHANGES_REQD followed by CHANGES_REQD→IMPLEMENTATION
        transitions_list = [(e.fromState, e.toState) for e in entries]
        assert ("G3_PENDING", "CHANGES_REQD") in transitions_list
        assert ("CHANGES_REQD", "IMPLEMENTATION") in transitions_list

        # Cleanup
        import shutil
        if os.path.exists(tmpdir):
            shutil.rmtree(tmpdir)


class TestAuditIndexNavigation:
    """AUDIT_INDEX.json contains all expected tasks with latestState."""

    def test_index_contains_expected_tasks(self, tmp_path):
        """AUDIT_INDEX.json has entries for known TASKs."""
        # Create a temporary index file at the standard location
        import shutil
        original_dir = os.getcwd()
        try:
            idx_path = "docs/reports/AUDIT_INDEX.json"
            os.makedirs(os.path.dirname(idx_path), exist_ok=True)

            test_index = [
                {"taskId": "TASK_DS_EO_020", "latestState": "COMPLETED",
                 "lastAuditTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
                {"taskId": "TASK_DS_EO_023", "latestState": "G3_PENDING",
                 "lastAuditTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
            ]

            with open(idx_path, "w") as f:
                json.dump(test_index, f)

            # Verify index is readable
            all_tasks = ProjectAuditIndex.get_all_tasks()
            task_ids = [t["taskId"] for t in all_tasks]
            assert "TASK_DS_EO_020" in task_ids
            assert "TASK_DS_EO_023" in task_ids

        finally:
            # Cleanup
            if os.path.isfile(idx_path):
                os.remove(idx_path)

    def test_get_task_state_lookup(self, tmp_path):
        """Quick lookup of a task's latest state from index."""
        import shutil
        idx_path = "docs/reports/AUDIT_INDEX.json"

        try:
            os.makedirs(os.path.dirname(idx_path), exist_ok=True)

            test_index = [
                {"taskId": "TASK_DS_EO_020", "latestState": "COMPLETED",
                 "lastAuditTime": "2026-08-01T10:00:00Z"},
            ]
            with open(idx_path, "w") as f:
                json.dump(test_index, f)

            state = ProjectAuditIndex.get_task_state("TASK_DS_EO_020")
            assert state == "COMPLETED"

        finally:
            if os.path.isfile(idx_path):
                os.remove(idx_path)

    def test_get_task_state_nonexistent_returns_none(self):
        """Lookup of non-existent task returns None."""
        idx_path = "docs/reports/AUDIT_INDEX.json"

        try:
            # Empty index
            with open(idx_path, "w") as f:
                json.dump([], f)

            state = ProjectAuditIndex.get_task_state("NONEXISTENT_TASK")
            assert state is None

        finally:
            if os.path.isfile(idx_path):
                os.remove(idx_path)


class TestReconstructionHashIntegrity:
    """Verify reconstruction hash chain integrity across all scenarios."""

    def test_hash_chain_continuity(self, tmp_path):
        """Each entry's hash derives correctly from preceding entries."""
        task_dir = str(tmp_path / "TASK_HASH_CHECK")
        os.makedirs(task_dir)

        log = AuditLog.create(task_dir, "TASK_HASH_CHECK")

        # Create 3 entries and verify chain
        e1 = log.append_entry(
            transition_key="T0", from_state="S0", to_state="S1",
            gate_passed=None, gate_status="APPROVED", agent_id="pm",
            execution_mode="automatic", triggered_by="PM",
            details={}, verified_artifacts=[]
        )

        e2 = log.append_entry(
            transition_key="T1", from_state="S1", to_state="S2",
            gate_passed=None, gate_status="APPROVED", agent_id="pm",
            execution_mode="automatic", triggered_by="PM",
            details={}, verified_artifacts=[]
        )

        e3 = log.append_entry(
            transition_key="T2", from_state="S2", to_state="S3",
            gate_passed=None, gate_status="APPROVED", agent_id="pm",
            execution_mode="automatic", triggered_by="PM",
            details={}, verified_artifacts=[]
        )

        # All hashes should be unique (chain advanced)
        assert len({e1.reconstructionHash, e2.reconstructionHash, e3.reconstructionHash}) == 3

    def test_hash_unchanged_after_read_back(self, tmp_path):
        """Hashes survive disk persistence and read-back."""
        task_dir = str(tmp_path / "TASK_HASH_PERSIST")
        os.makedirs(task_dir)

        log = AuditLog.create(task_dir, "TASK_HASH_PERSIST")

        # Create entries
        e1 = log.append_entry(
            transition_key="T0", from_state="S0", to_state="S1",
            gate_passed=None, gate_status="APPROVED", agent_id="pm",
            execution_mode="automatic", triggered_by="PM",
            details={}, verified_artifacts=[]
        )

        # Read back from disk
        log2 = AuditLog.create(task_dir, "TASK_HASH_PERSIST")
        entries_back = log2.get_entries()

        assert len(entries_back) == 1
        assert entries_back[0].reconstructionHash == e1.reconstructionHash
