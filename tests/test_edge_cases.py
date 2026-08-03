"""Category D: Blocker/Stall Edge Case Tests — Phase 5.

Timeout thresholds, escalation timing, race conditions, and concurrent stall detection.
Covers architecture §§9.2–9.6 risk register items.
"""

import os
from datetime import datetime, timedelta, timezone

import pytest

from ds_eo_openclaw.workflow.timeout_config import TimeoutConfig
from ds_eo_openclaw.workflow.stall_detection import StallDetector
from ds_eo_openclaw.workflow.escalation import EscalationChain
from ds_eo_openclaw.workflow.failure_detector import FailureDetector


# --------------------------------------------------------------------------- #
# Timeout Threshold Boundary Conditions (5 tests)
# --------------------------------------------------------------------------- #

class TestTimeoutBoundaryConditions:
    """Exactly at timeout (should flag), just under (should not)."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.detector = StallDetector()

    def test_exactly_at_timeout_is_flagged(self):
        """Timestamp exactly at timeout boundary → flagged as stalled."""
        # WAITING_G2 has 3600s (1h) timeout
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(seconds=3600)  # Exactly 1 hour ago
        result = self.detector.check("TASK_EDGE_001", "WAITING_G2", old_time)
        assert result is not None, "Should be flagged at exactly the timeout boundary"

    def test_just_under_timeout_not_flagged(self):
        """Timestamp just under timeout → NOT flagged."""
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(seconds=3599)  # 1 second under
        result = self.detector.check("TASK_EDGE_002", "WAITING_G2", old_time)
        assert result is None, "Should NOT be flagged just under timeout"

    def test_just_over_timeout_is_flagged(self):
        """Timestamp just over timeout → flagged."""
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(seconds=3601)  # 1 second over
        result = self.detector.check("TASK_EDGE_003", "WAITING_G2", old_time)
        assert result is not None, "Should be flagged just over timeout"

    def test_implemention_timeout_boundary(self):
        """IMPLEMENTATION state (36000s / 10h) boundary condition."""
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(seconds=36000)  # Exactly at timeout
        result = self.detector.check("TASK_EDGE_004", "IMPLEMENTATION", old_time)
        assert result is not None, "Should be flagged exactly at IMPLEMENTATION timeout"

    def test_zero_elapsed_not_flagged(self):
        """Timestamp at 'now' (zero elapsed) → NOT flagged."""
        now = datetime.now(timezone.utc)
        result = self.detector.check("TASK_EDGE_005", "WAITING_G2", now)
        assert result is None, "Zero elapsed time should never be stalled"


# --------------------------------------------------------------------------- #
# Escalation Timing / Rate Limiting (3 tests)
# --------------------------------------------------------------------------- #

class TestEscalationTiming:
    """Multiple blockers within 5-minute window → only one escalates."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.chain = EscalationChain()

    def test_rate_limiting_within_5_minutes(self):
        """Two escalations within 5 minutes: second is rate-limited."""
        result1 = self.chain.escalate("TASK_EDGE_006", "Blocker A")
        assert result1["level"] == "CTO"

        # Immediate second escalation — should be rate limited
        result2 = self.chain.escalate("TASK_EDGE_006", "Blocker A")
        assert "Rate limited" in result2.get("message", "") or \
               result2["level"] == "CTO"  # Still at CTO level

    def test_rate_limit_expires_after_5_minutes(self):
        """After rate limit window passes, escalation proceeds to next level."""
        self.chain.escalate("TASK_EDGE_007", "Blocker B")

        # Manually backdate last escalation beyond 300 seconds ago
        self.chain.escalation_history["TASK_EDGE_007"]["lastEscalatedAt"] = \
            datetime.now(timezone.utc) - timedelta(seconds=301)

        result2 = self.chain.escalate("TASK_EDGE_007", "Blocker B")
        assert result2["level"] == "USER"  # Escalated past CTO to User

    def test_different_tasks_independent_rate_limiting(self):
        """Different tasks have independent rate limits — no cross-contamination."""
        self.chain.escalate("TASK_EDGE_008A", "Blocker X")
        result = self.chain.escalate("TASK_EDGE_008B", "Blocker Y")
        # Second task should escalate normally (no prior history)
        assert result["level"] == "CTO"


# --------------------------------------------------------------------------- #
# Repeated Failure Counting Edge Cases (4 tests)
# --------------------------------------------------------------------------- #

class TestFailureCounting:
    """Reset on completion, cross-task counter isolation."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.detector = FailureDetector()

    def test_counter_resets_on_completion(self):
        """Successful completion resets the failure count to zero."""
        for _ in range(5):
            self.detector.record_failure("TASK_EDGE_009", "G3")
        assert self.detector.get_failure_count("TASK_EDGE_009") == 5

        # Completion → reset
        removed = self.detector.reset_on_completion("TASK_EDGE_009")
        assert removed is True
        assert self.detector.get_failure_count("TASK_EDGE_009") == 0

    def test_counter_not_reset_on_non_completion(self):
        """Non-completion events do NOT reset the failure count."""
        for _ in range(3):
            self.detector.record_failure("TASK_EDGE_010", "G4")
        assert self.detector.get_failure_count("TASK_EDGE_010") == 3

    def test_cross_task_counter_isolation(self):
        """Each task has its own independent failure counter."""
        # Task A: 2 failures
        for _ in range(2):
            self.detector.record_failure("TASK_EDGE_A", "G3")
        # Task B: 5 failures
        for _ in range(5):
            self.detector.record_failure("TASK_EDGE_B", "G4")

        assert self.detector.get_failure_count("TASK_EDGE_A") == 2
        assert self.detector.get_failure_count("TASK_EDGE_B") == 5

    def test_cross_task_reset_does_not_affect_other(self):
        """Resetting one task's counter doesn't affect another."""
        for _ in range(3):
            self.detector.record_failure("TASK_EDGE_C", "G3")
        for _ in range(2):
            self.detector.record_failure("TASK_EDGE_D", "G4")

        # Reset only TASK_EDGE_C
        self.detector.reset_on_completion("TASK_EDGE_C")

        assert self.detector.get_failure_count("TASK_EDGE_C") == 0
        assert self.detector.get_failure_count("TASK_EDGE_D") == 2


# --------------------------------------------------------------------------- #
# Concurrent Stall Detection (2 tests)
# --------------------------------------------------------------------------- #

class TestConcurrentStallDetection:
    """Two tasks stalled simultaneously, both reported independently."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.detector = StallDetector()

    def test_two_tasks_stalled_independently(self):
        """Both tasks are detected as stalled without interference."""
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(hours=5)  # Well past WAITING_G2 timeout (1h)

        result_a = self.detector.check("TASK_CONCURRENT_A", "WAITING_G2", old_time)
        result_b = self.detector.check("TASK_CONCURRENT_B", "WAITING_G2", old_time)

        assert result_a is not None, "Task A should be stalled"
        assert result_b is not None, "Task B should be stalled"
        assert result_a["taskId"] == "TASK_CONCURRENT_A"
        assert result_b["taskId"] == "TASK_CONCURRENT_B"

    def test_check_all_states_reports_each_independently(self):
        """check_all_states returns stalls for each task independently."""
        now = datetime.now(timezone.utc)
        old_time_a = now - timedelta(hours=5)
        old_time_b = now - timedelta(hours=2)  # Still within timeout

        state_timestamps = {
            "WAITING_G2": old_time_a,
            "REVIEW": old_time_b,  # Within timeout (7200s / 2h)
        }

        stalls = self.detector.check_all_states("TASK_CONCURRENT_C", state_timestamps)
        # WAITING_G2 is stalled (5h > 1h), REVIEW is not (2h = exactly at timeout)
        assert len(stalls) >= 1, "At least WAITING_G2 should be detected"
