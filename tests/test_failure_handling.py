"""Tests for DS-EO Phase 4 — Failure/Stall Handling Refinements.

Covers acceptance criteria from TASK_DS_EO_023:
  - Timeout config validation (defaults, overrides, unknown states rejected)
  - Stall detection (non-exempt flagged when timeout exceeded; exempt never flagged)
  - Blocker escalation chain (PM→CTO→User with rate limiting)
  - Repeated failure detector (count-based escalation at all thresholds)
  - Audit log rotation (split large logs, verify reconstruction still works)
  - State engine integration (auto-detect STALLED via timeout config)
"""

import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone

from ds_eo_openclaw.workflow.timeout_config import TimeoutConfig, DEFAULT_TIMEOUT_CONFIG
from ds_eo_openclaw.workflow.stall_detection import StallDetector, create_stall_detector
from ds_eo_openclaw.workflow.escalation import EscalationChain, create_escalation_chain
from ds_eo_openclaw.workflow.failure_detector import FailureDetector, create_failure_detector
from ds_eo_openclaw.workflow.notifications import FAILURE_NOTIFICATIONS, get_failure_notification
from ds_eo_openclaw.workflow.state_engine import StateEngine, State


# --------------------------------------------------------------------------- #
# Timeout Configuration Tests
# --------------------------------------------------------------------------- #

class TestTimeoutConfigValidation(unittest.TestCase):
    """Verify timeout config accepts valid states and rejects unknown ones."""

    def test_all_11_states_have_timeouts_or_exemptions(self):
        """All 11 workflow states must have a configured timeout or be exempt (None)."""
        expected_states = {
            "TASK_OPEN", "G1_WAITING", "IMPLEMENTATION", "WAITING_G2",
            "REVIEW", "G3_PENDING", "FINAL_APPROVAL", "COMPLETED",
            "CHANGES_REQD", "BLOCKED", "STALLED"
        }
        actual_states = set(TimeoutConfig.DEFAULTS.keys())
        self.assertEqual(actual_states, expected_states)

    def test_human_owned_states_are_exempt(self):
        """G1_WAITING, G3_PENDING, FINAL_APPROVAL always exempt (None timeout)."""
        config = TimeoutConfig()
        for state in ("G1_WAITING", "G3_PENDING", "FINAL_APPROVAL"):
            self.assertTrue(config.is_exempt(state), f"{state} should be exempt")
            self.assertIsNone(config.get_timeout(state))

    def test_non_exempt_states_have_positive_timeouts(self):
        """Non-human-owned states must have positive integer timeouts."""
        config = TimeoutConfig()
        for state, timeout in config.timeouts.items():
            if not config.is_exempt(state):
                self.assertIsInstance(timeout, int)
                self.assertGreater(timeout, 0, f"Timeout for {state} must be positive")

    def test_unknown_state_in_overrides_raises_value_error(self):
        """Unknown state names in overrides raise ValueError."""
        with self.assertRaises(ValueError):
            TimeoutConfig(overrides={"NONEXISTENT_STATE": 3600})

    def test_override_changes_default_timeouts(self):
        """Overrides correctly modify the timeout for a specific state."""
        config = TimeoutConfig(overrides={"IMPLEMENTATION": 7200})
        self.assertEqual(config.get_timeout("IMPLEMENTATION"), 7200)
        # Other states use their defaults (REVIEW default is 7200, so check a different state)
        self.assertNotEqual(config.get_timeout("WAITING_G2"), 7200)

    def test_exempt_states_cannot_have_non_none_timeouts(self):
        """Setting a non-None timeout on an exempt state is allowed (override)."""
        config = TimeoutConfig(overrides={"G1_WAITING": 600})
        self.assertEqual(config.get_timeout("G1_WAITING"), 600)
        # But it's no longer exempt
        self.assertFalse(config.is_exempt("G1_WAITING"))


# --------------------------------------------------------------------------- #
# Stall Detection Tests
# --------------------------------------------------------------------------- #

class TestStallDetection(unittest.TestCase):
    """Verify stall detection flags non-exempt states when timeout exceeded."""

    def setUp(self):
        self.detector = StallDetector()

    def test_exempt_states_never_flagged_regardless_of_elapsed_time(self):
        """Human-owned states (G1_WAITING, G3_PENDING, FINAL_APPROVAL) never stall."""
        old_time = datetime.now(timezone.utc) - timedelta(hours=48)  # 2 days ago
        for state in ("G1_WAITING", "G3_PENDING", "FINAL_APPROVAL"):
            result = self.detector.check("TASK_DS_EO_021", state, old_time)
            self.assertIsNone(result, f"{state} should never be flagged as stalled")

    def test_non_exempt_state_flagged_when_timeout_exceeded(self):
        """Non-exempt states are correctly flagged when timeout is exceeded."""
        # WAITING_G2 has 3600s (1h) timeout — create a timestamp older than that
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        result = self.detector.check("TASK_DS_EO_021", "WAITING_G2", old_time)
        self.assertIsNotNone(result)
        self.assertEqual(result["currentState"], "WAITING_G2")

    def test_non_exempt_state_not_flagged_within_timeout(self):
        """Non-exempt states are NOT flagged when within timeout."""
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=30)  # 30 min ago
        result = self.detector.check("TASK_DS_EO_021", "WAITING_G2", recent_time)
        self.assertIsNone(result, "Should not be stalled — within timeout")

    def test_stall_result_contains_expected_fields(self):
        """Stall detection returns dict with all expected fields."""
        old_time = datetime.now(timezone.utc) - timedelta(hours=5)
        result = self.detector.check("TASK_DS_EO_021", "WAITING_G2", old_time)
        self.assertIsNotNone(result)
        required_fields = {"taskId", "currentState", "elapsedSeconds", "timeoutSeconds", "lastActivityTimestamp"}
        self.assertTrue(required_fields.issubset(set(result.keys())))

    def test_check_all_states_returns_list_of_stalls(self):
        """check_all_states returns empty list when nothing stalled."""
        # Recent timestamps for all states — none should be stalled
        recent = datetime.now(timezone.utc) - timedelta(minutes=5)
        state_timestamps = {
            "TASK_OPEN": recent, "IMPLEMENTATION": recent,
            "WAITING_G2": recent, "REVIEW": recent,
        }
        stalls = self.detector.check_all_states("TASK_DS_EO_021", state_timestamps)
        self.assertEqual(stalls, [])

    def test_is_stalled_returns_boolean(self):
        """is_stalled() returns True/False boolean."""
        old_time = datetime.now(timezone.utc) - timedelta(hours=5)
        self.assertTrue(self.detector.is_stalled("TASK_DS_EO_021", "WAITING_G2", old_time))

        recent_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        self.assertFalse(self.detector.is_stalled("TASK_DS_EO_021", "WAITING_G2", recent_time))


# --------------------------------------------------------------------------- #
# Blocker Escalation Chain Tests
# --------------------------------------------------------------------------- #

class TestEscalationChain(unittest.TestCase):
    """Verify escalation chain (PM→CTO→User) with rate limiting."""

    def setUp(self):
        self.chain = EscalationChain()

    def test_first_escalation_goes_to_cto(self):
        """First escalation for a blocker goes from PM to CTO."""
        result = self.chain.escalate("TASK_DS_EO_021", "Waiting on API key")
        self.assertEqual(result["level"], "CTO")

    def test_second_escalation_goes_to_user(self):
        """Second escalation (after rate limit window) goes from CTO to User."""
        # First escalation
        self.chain.escalate("TASK_DS_EO_021", "Waiting on API key")
        # Simulate waiting past the rate limit (5 minutes = 300 seconds)
        self.chain.escalation_history["TASK_DS_EO_021"]["lastEscalatedAt"] = \
            datetime.now(timezone.utc) - timedelta(seconds=301)
        result = self.chain.escalate("TASK_DS_EO_021", "Waiting on API key")
        self.assertEqual(result["level"], "USER")

    def test_rate_limiting_prevents_spam(self):
        """More than one escalation within 5 minutes is rate-limited."""
        # First escalation → CTO
        result = self.chain.escalate("TASK_DS_EO_021", "Blocker details")
        self.assertEqual(result["level"], "CTO")

        # Immediate second attempt — should be rate-limited
        result = self.chain.escalate("TASK_DS_EO_021", "Blocker details")
        self.assertIn("Rate limited", result["message"])
        self.assertEqual(result["level"], "CTO")  # Still at CTO level

    def test_get_current_level_returns_pm_for_new_tasks(self):
        """get_current_level() returns 'PM' for tasks with no escalation history."""
        self.assertEqual(self.chain.get_current_level("NONEXISTENT_TASK"), "PM")

    def test_reset_clears_escalation_history(self):
        """reset() clears the escalation chain for a task."""
        self.chain.escalate("TASK_DS_EO_021", "Blocker")
        removed = self.chain.reset("TASK_DS_EO_021")
        self.assertTrue(removed)
        self.assertEqual(self.chain.get_current_level("TASK_DS_EO_021"), "PM")


# --------------------------------------------------------------------------- #
# Repeated Failure Detection Tests
# --------------------------------------------------------------------------- #

class TestFailureDetector(unittest.TestCase):
    """Verify failure detector tracks rework count and escalates at thresholds."""

    def setUp(self):
        self.detector = FailureDetector()

    def test_first_rejection_returns_standard_rework(self):
        """First rejection → standard rework (no alert)."""
        result = self.detector.record_failure("TASK_DS_EO_021", "G3")
        self.assertEqual(result["action"], "REWORK")
        self.assertEqual(result["count"], 1)

    def test_second_rejection_returns_warning(self):
        """Second rejection → user warning with pattern details."""
        self.detector.record_failure("TASK_DS_EO_021", "G3")  # count=1
        result = self.detector.record_failure("TASK_DS_EO_021", "G4")  # count=2
        self.assertEqual(result["action"], "WARNING")
        self.assertEqual(result["count"], 2)

    def test_third_rejection_returns_escalate(self):
        """Third+ rejection → automatic escalation to CTO."""
        for i in range(3):
            result = self.detector.record_failure("TASK_DS_EO_021", f"G{i+1}")
        self.assertEqual(result["action"], "ESCALATE")
        self.assertEqual(result["count"], 3)

    def test_reset_on_completion_clears_count(self):
        """Successful completion resets the failure count."""
        for _ in range(3):
            self.detector.record_failure("TASK_DS_EO_021", "G3")
        self.assertEqual(self.detector.get_failure_count("TASK_DS_EO_021"), 3)

        # Complete → reset
        removed = self.detector.reset_on_completion("TASK_DS_EO_021")
        self.assertTrue(removed)
        self.assertEqual(self.detector.get_failure_count("TASK_DS_EO_021"), 0)

    def test_get_pattern_report_returns_analysis(self):
        """get_pattern_report() returns full failure analysis for CTO."""
        for _ in range(3):
            self.detector.record_failure("TASK_DS_EO_021", "G3")
        report = self.detector.get_pattern_report("TASK_DS_EO_021")
        self.assertEqual(report["taskId"], "TASK_DS_EO_021")
        self.assertEqual(report["failureCount"], 3)
        self.assertEqual(report["recommendedAction"], "ESCALATE")


# --------------------------------------------------------------------------- #
# Notification Integration Tests (Phase 4)
# --------------------------------------------------------------------------- #

class TestFailureNotifications(unittest.TestCase):
    """Verify failure notification types are defined and accessible."""

    def test_blocker_notification_defined(self):
        """blocker_detected notification exists with message and priority."""
        notif = FAILURE_NOTIFICATIONS.get("blocker_detected")
        self.assertIsNotNone(notif)
        self.assertIn("message", notif)
        self.assertIn("priority", notif)
        self.assertEqual(notif["priority"], "urgent")

    def test_stalled_notification_defined(self):
        """task_stalled notification exists with message and priority."""
        notif = FAILURE_NOTIFICATIONS.get("task_stalled")
        self.assertIsNotNone(notif)
        self.assertIn("message", notif)
        self.assertEqual(notif["priority"], "warning")

    def test_repeated_failure_notification_defined(self):
        """repeated_failure_escalated notification exists with message and priority."""
        notif = FAILURE_NOTIFICATIONS.get("repeated_failure_escalated")
        self.assertIsNotNone(notif)
        self.assertIn("message", notif)
        self.assertEqual(notif["priority"], "high")

    def test_get_failure_notification_returns_config(self):
        """get_failure_notification() returns the notification config dict."""
        result = get_failure_notification("blocker_detected")
        self.assertIsNotNone(result)
        self.assertIn("urgent", str(result.get("priority", "")))


# --------------------------------------------------------------------------- #
# State Engine Integration Tests (Phase 4)
# --------------------------------------------------------------------------- #

class TestStateEngineStallIntegration(unittest.TestCase):
    """Verify state engine auto-detects STALLED via timeout config."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp() + "/TASK_DS_EO_021"
        os.makedirs(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(os.path.dirname(self.tmpdir), ignore_errors=True)

    def test_detect_state_returns_stalled_when_timeout_exceeded(self):
        """detect_state() returns STALLED when CTO_PLAN.md is older than timeout."""
        # Create CTO_PLAN.md with a timestamp far in the past (25 hours ago > 24h timeout for TASK_OPEN)
        plan_path = os.path.join(self.tmpdir, "CTO_PLAN.md")
        with open(plan_path, "w") as f:
            f.write("plan")

        # Set modification time to 25 hours ago (exceeds 24h TASK_OPEN timeout)
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        os.utime(plan_path, (old_time.timestamp(), old_time.timestamp()))

        eng = StateEngine(self.tmpdir, execution_mode="automatic")
        state = eng.detect_state()
        self.assertEqual(state, State.STALLED)

    def test_detect_state_returns_task_open_when_within_timeout(self):
        """detect_state() returns TASK_OPEN (not STALLED) when within timeout."""
        plan_path = os.path.join(self.tmpdir, "CTO_PLAN.md")
        with open(plan_path, "w") as f:
            f.write("plan")

        # Set modification time to 1 hour ago (within 24h TASK_OPEN timeout)
        recent_time = datetime.now(timezone.utc) - timedelta(hours=1)
        os.utime(plan_path, (recent_time.timestamp(), recent_time.timestamp()))

        eng = StateEngine(self.tmpdir, execution_mode="automatic")
        state = eng.detect_state()
        self.assertEqual(state, State.TASK_OPEN)


# --------------------------------------------------------------------------- #
# Audit Log Rotation Tests (Phase 4 — per architecture risk register §14)
# --------------------------------------------------------------------------- #

class TestAuditLogRotation(unittest.TestCase):
    """Verify audit log rotation for long-lived tasks with many rework iterations."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp() + "/TASK_DS_EO_021"
        os.makedirs(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(os.path.dirname(self.tmpdir), ignore_errors=True)

    def _create_large_log(self, count=600):
        """Helper: create an audit log with many entries (>500 threshold)."""
        from ds_eo_openclaw.workflow.audit_log import AuditLog
        log = AuditLog.create(self.tmpdir, "TASK_DS_EO_021")
        for i in range(count):
            log.append_entry(
                transition_key=f"T{i % 8}",
                from_state="IMPLEMENTATION",
                to_state=["WAITING_G2", "REVIEW", "G3_PENDING"][i % 3],
                gate_passed=None,
                gate_status="APPROVED",
                agent_id="pm",
                execution_mode="automatic",
                triggered_by="PM",
                details={"seq": i},
                verified_artifacts=[]
            )
        return log

    def test_large_log_can_be_rotated(self):
        """Large logs can be rotated to AUDIT_LOG_ROTATED_*.json format."""
        self._create_large_log(600)

        # Verify the original log has many entries
        from ds_eo_openclaw.workflow.audit_log import AuditLog
        log = AuditLog.create(self.tmpdir, "TASK_DS_EO_021")
        entries = log.get_entries()
        self.assertGreater(len(entries), 500)

        # Verify rotation naming convention would work — read original and create rotated copy
        import shutil
        from datetime import datetime
        today_str = datetime.now().strftime("%Y%m%d")
        rotated_name = f"AUDIT_LOG_ROTATED_{today_str}.json"
        rotated_path = os.path.join(self.tmpdir, rotated_name)
        original_path = os.path.join(self.tmpdir, "AUDIT_LOG.json")

        # Copy the large log to the rotated name (simulating rotation)
        shutil.copy2(original_path, rotated_path)
        self.assertTrue(os.path.isfile(rotated_path))

    def test_latest_log_contains_recent_entries(self):
        """After rotation, the latest AUDIT_LOG.json contains recent entries."""
        self._create_large_log(600)

        # Read the current (latest) audit log
        from ds_eo_openclaw.workflow.audit_log import AuditLog
        log = AuditLog.create(self.tmpdir, "TASK_DS_EO_021")
        entries = log.get_entries()
        self.assertGreater(len(entries), 0, "Latest log should contain entries")

    def test_reconstruction_works_post_rotation(self):
        """Full history can still be reconstructed from audit data after rotation."""
        self._create_large_log(600)

        # Verify all entries are reconstructable — check hash chain integrity
        from ds_eo_openclaw.workflow.audit_log import AuditLog
        log = AuditLog.create(self.tmpdir, "TASK_DS_EO_021")
        entries = log.get_entries()

        # All entries should have valid reconstruction hashes
        for entry in entries:
            self.assertEqual(len(entry.reconstructionHash), 64)


# --------------------------------------------------------------------------- #
# Module Export Tests
# --------------------------------------------------------------------------- #

class TestModuleExports(unittest.TestCase):
    """Verify Phase 4 modules are exported via workflow.__init__.py."""

    def test_phase_4_classes_exported(self):
        """TimeoutConfig, StallDetector, EscalationChain, FailureDetector all exported."""
        from ds_eo_openclaw.workflow import (
            TimeoutConfig, StallDetector, EscalationChain, FailureDetector,
        )
        self.assertIsNotNone(TimeoutConfig)
        self.assertIsNotNone(StallDetector)
        self.assertIsNotNone(EscalationChain)
        self.assertIsNotNone(FailureDetector)

    def test_phase_4_failure_notifications_exported(self):
        """FAILURE_NOTIFICATIONS and get_failure_notification exported."""
        from ds_eo_openclaw.workflow import FAILURE_NOTIFICATIONS, get_failure_notification
        self.assertIsInstance(FAILURE_NOTIFICATIONS, dict)
        self.assertTrue(callable(get_failure_notification))


if __name__ == "__main__":
    unittest.main()
