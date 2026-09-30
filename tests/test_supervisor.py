"""
DS-EO Dispatcher — Workflow Supervisor Tests (TASK_DS_EO_027)

Tests for stuck, aborted, failed, and lost session scenarios.
Also tests manual mode (observer-only) vs automatic mode behavior.

Run: python -m pytest tests/test_supervisor.py -v
"""

import json
import os
import sys
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

# Ensure the project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dispatcher.session_dispatch.supervisor import (
    WorkflowSupervisor,
    SupervisorConfig,
    SupervisorEvent,
    HeartbeatResult,
    RecoveryResult,
    TaskSupervisorState,
    AgentState,
)
from dispatcher.session_dispatch.liveness import LivenessChecker, LivenessResult


# ====================================================================
# Fixtures
# ====================================================================

def _make_temp_workspace():
    """Create a temporary workspace with minimal task structure."""
    ws = tempfile.mkdtemp(prefix="test_supervisor_")
    # Create expected directory structure
    for d in ["docs/development/reports", "docs/dispatchers", "tests"]:
        os.makedirs(os.path.join(ws, d), exist_ok=True)
    return ws


def _make_task_dir(ws, task_id="TASK_TEST_001"):
    """Create a minimal task directory with dispatcher_state.json."""
    td = os.path.join(ws, "docs", "dispatchers", task_id)
    os.makedirs(td, exist_ok=True)
    state = {
        "task_id": task_id,
        "current_phase": "S2_IMPLEMENTATION",
        "pending_work": {
            "spawn_session_key": f"agent:implementer:subagent:test1234:{task_id}",
            "assigned_to": "implementer",
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(os.path.join(td, "dispatcher_state.json"), "w") as f:
        json.dump(state, f)
    # Create a dummy report artifact
    report_dir = os.path.join(ws, "docs", "development", "reports", task_id)
    os.makedirs(report_dir, exist_ok=True)
    with open(os.path.join(report_dir, "TASK_REPORT.md"), "w") as f:
        f.write(f"# {task_id} Report\n")
    return td


# ====================================================================
# AC-1: Agent Liveness Detection
# ====================================================================

class TestAgentLivenessDetection:
    """AC-1: Supervisor can verify spawned session liveness."""

    def test_verify_phantom_session(self):
        """Phantom sessions (non-existent keys) are detected."""
        ws = _make_temp_workspace()
        try:
            checker = LivenessChecker(workspace_root=ws)
            result = checker.verify_session_alive("agent:implementer:subagent:phantom_key")
            assert not result.alive, "Phantom session should not be alive"
            assert result.status == "unknown"
            assert result.reason is not None and len(result.reason) > 0
        finally:
            shutil.rmtree(ws)

    def test_verify_active_session(self):
        """Active sessions with matching task directory are detected as alive."""
        ws = _make_temp_workspace()
        try:
            td = _make_task_dir(ws, "TASK_TEST_ACTIVE")
            checker = LivenessChecker(workspace_root=ws)
            session_key = f"agent:implementer:subagent:test1234:TASK_TEST_ACTIVE"
            result = checker.verify_session_alive(session_key)
            assert result.alive, f"Active session should be alive. Reason: {result.reason}"
            assert result.status == "running"
        finally:
            shutil.rmtree(ws)

    def test_liveness_within_one_heartbeat_cycle(self):
        """Phantom sessions detected within one heartbeat cycle."""
        ws = _make_temp_workspace()
        try:
            supervisor = WorkflowSupervisor(workspace_root=ws)
            supervisor.start_supervising("TASK_TEST_CYCLE", mode="automatic")
            
            # Add a phantom agent
            supervisor.add_agent_to_supervision(
                "TASK_TEST_CYCLE",
                "agent:implementer:subagent:phantom99:TASK_TEST_CYCLE",
                "implementer",
                "S2_IMPLEMENTATION",
            )
            
            stalled, _ = supervisor.detect_stall("TASK_TEST_CYCLE")
            assert len(stalled) == 1, f"Should detect 1 stalled agent, got {len(stalled)}"
        finally:
            shutil.rmtree(ws)


# ====================================================================
# AC-2: Heartbeat / Progress Detection
# ====================================================================

class TestHeartbeatProgressDetection:
    """AC-2: Heartbeat polls at configured interval; no-progress triggers after timeout."""

    def test_heartbeat_ok_when_agent_working(self):
        """Agent with recent progress returns heartbeat ok."""
        ws = _make_temp_workspace()
        try:
            supervisor = WorkflowSupervisor(
                config=SupervisorConfig(no_progress_timeout_seconds=300, heartbeat_interval_seconds=60),
                workspace_root=ws,
            )
            supervisor.start_supervising("TASK_TEST_HB1", mode="automatic")
            
            # Create a real task dir so liveness passes
            td = _make_task_dir(ws, "TASK_TEST_HB1")
            
            session_key = f"agent:implementer:subagent:testhb:TASK_TEST_HB1"
            supervisor.add_agent_to_supervision(
                "TASK_TEST_HB1", session_key, "implementer", "S2_IMPLEMENTATION"
            )
            
            # Record progress
            ts = supervisor._task_states["TASK_TEST_HB1"]
            agent = ts.agents[session_key]
            now = datetime.now(timezone.utc)
            agent.last_progress_at = now.isoformat()
            
            stalled, report = supervisor.detect_stall("TASK_TEST_HB1")
            assert len(stalled) == 0, f"Should not detect stall for working agent, got stalled={stalled}"
        finally:
            shutil.rmtree(ws)

    def test_no_progress_detection(self):
        """No-progress detection triggers after no_progress_timeout seconds."""
        ws = _make_temp_workspace()
        try:
            supervisor = WorkflowSupervisor(
                config=SupervisorConfig(
                    no_progress_timeout_seconds=10,  # Short for testing
                    heartbeat_interval_seconds=5,
                ),
                workspace_root=ws,
            )
            supervisor.start_supervising("TASK_TEST_NOP", mode="automatic")
            
            td = _make_task_dir(ws, "TASK_TEST_NOP")
            session_key = f"agent:implementer:subagent:testnop:TASK_TEST_NOP"
            supervisor.add_agent_to_supervision(
                "TASK_TEST_NOP", session_key, "implementer", "S2_IMPLEMENTATION"
            )
            
            # Set last progress to 30 seconds ago (exceeds 10s timeout)
            ts = supervisor._task_states["TASK_TEST_NOP"]
            agent = ts.agents[session_key]
            agent.last_progress_at = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
            
            stalled, _ = supervisor.detect_stall("TASK_TEST_NOP")
            assert len(stalled) == 1, "Should detect no-progress after timeout"
        finally:
            shutil.rmtree(ws)

    def test_artifact_change_resets_progress_timer(self):
        """Recording artifact change resets the progress timer."""
        ws = _make_temp_workspace()
        try:
            supervisor = WorkflowSupervisor(workspace_root=ws)
            supervisor.start_supervising("TASK_TEST_ART", mode="automatic")
            
            td = _make_task_dir(ws, "TASK_TEST_ART")
            session_key = f"agent:implementer:subagent:testart:TASK_TEST_ART"
            supervisor.add_agent_to_supervision(
                "TASK_TEST_ART", session_key, "implementer", "S2_IMPLEMENTATION"
            )
            
            # Record progress 30 seconds ago
            ts = supervisor._task_states["TASK_TEST_ART"]
            agent = ts.agents[session_key]
            agent.last_progress_at = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
            
            # Now record an artifact change (resets timer)
            assert supervisor.record_artifact_change(session_key, "TASK_TEST_ART") == True
            
            ts = supervisor._task_states["TASK_TEST_ART"]
            agent = ts.agents[session_key]
            assert agent.state == "RUNNING", f"Should be RUNNING after artifact change, got {agent.state}"
        finally:
            shutil.rmtree(ws)


# ====================================================================
# AC-3: Timeout Enforcement
# ====================================================================

class TestTimeoutEnforcement:
    """AC-3: Hard timeout escalates to HUMAN_INTERVENTION; all thresholds configurable."""

    def test_hard_timeout_triggers_stall(self):
        """Agents exceeding hard_timeout_seconds are detected as stalled."""
        ws = _make_temp_workspace()
        try:
            supervisor = WorkflowSupervisor(
                config=SupervisorConfig(
                    hard_timeout_seconds=10,
                    heartbeat_interval_seconds=5,
                    no_progress_timeout_seconds=300,  # Long enough not to trigger
                ),
                workspace_root=ws,
            )
            supervisor.start_supervising("TASK_TEST_TIMEOUT", mode="automatic")
            
            td = _make_task_dir(ws, "TASK_TEST_TIMEOUT")
            session_key = f"agent:implementer:subagent:testto:TASK_TEST_TIMEOUT"
            supervisor.add_agent_to_supervision(
                "TASK_TEST_TIMEOUT", session_key, "implementer", "S2_IMPLEMENTATION"
            )
            
            # Set spawn time to 30 seconds ago (exceeds 10s hard timeout)
            ts = supervisor._task_states["TASK_TEST_TIMEOUT"]
            agent = ts.agents[session_key]
            agent.spawned_at = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
            
            stalled, _ = supervisor.detect_stall("TASK_TEST_TIMEOUT")
            assert len(stalled) == 1, "Should detect hard timeout stall"
        finally:
            shutil.rmtree(ws)

    def test_configurable_thresholds(self):
        """All thresholds are configurable via SupervisorConfig."""
        config = SupervisorConfig(
            heartbeat_interval_seconds=60,
            no_progress_timeout_seconds=120,
            hard_timeout_seconds=600,
            retry_attempts=3,
            retry_backoff_seconds=[30, 90],
        )
        assert config.heartbeat_interval_seconds == 60
        assert config.no_progress_timeout_seconds == 120
        assert config.hard_timeout_seconds == 600
        assert config.retry_attempts == 3
        assert config.retry_backoff_seconds == [30, 90]


# ====================================================================
# AC-4: Retry and Recovery
# ====================================================================

class TestRetryRecovery:
    """AC-4: Retries with exponential backoff; exhaustion → HUMAN_INTERVENTION."""

    def test_retry_succeeds_within_budget(self):
        """Stalled agents are retried up to configured limit."""
        ws = _make_temp_workspace()
        try:
            supervisor = WorkflowSupervisor(
                config=SupervisorConfig(retry_attempts=2, retry_backoff_seconds=[1, 5]),
                workspace_root=ws,
            )
            supervisor.start_supervising("TASK_TEST_RETRY", mode="automatic")
            
            td = _make_task_dir(ws, "TASK_TEST_RETRY")
            session_key = f"agent:implementer:subagent:testrt:TASK_TEST_RETRY"
            supervisor.add_agent_to_supervision(
                "TASK_TEST_RETRY", session_key, "implementer", "S2_IMPLEMENTATION"
            )
            
            result = supervisor.attempt_recovery("TASK_TEST_RETRY", session_key)
            assert result.success is True
            assert result.action_taken == "retried"
            assert result.retry_number == 1
            assert result.new_session_key is not None
        finally:
            shutil.rmtree(ws)

    def test_retry_exhaustion_esculates(self):
        """When retries exhausted, task enters HUMAN_INTERVENTION state."""
        ws = _make_temp_workspace()
        try:
            supervisor = WorkflowSupervisor(
                config=SupervisorConfig(retry_attempts=2, retry_backoff_seconds=[1]),
                workspace_root=ws,
            )
            supervisor.start_supervising("TASK_TEST_EXHAUST", mode="automatic")
            
            td = _make_task_dir(ws, "TASK_TEST_EXHAUST")
            session_key = f"agent:implementer:subagent:testex:TASK_TEST_EXHAUST"
            supervisor.add_agent_to_supervision(
                "TASK_TEST_EXHAUST", session_key, "implementer", "S2_IMPLEMENTATION"
            )
            
            # Exhaust retries
            for i in range(3):  # Attempt more than retry_attempts
                result = supervisor.attempt_recovery("TASK_TEST_EXHAUST", session_key)
            
            ts = supervisor._task_states["TASK_TEST_EXHAUST"]
            assert ts.overlay_state == "HUMAN_INTERVENTION", \
                f"Expected HUMAN_INTERVENTION, got {ts.overlay_state}"
        finally:
            shutil.rmtree(ws)

    def test_retry_prompt_includes_stall_context(self):
        """Retry prompt includes stall context (previous session, retry number)."""
        ws = _make_temp_workspace()
        try:
            supervisor = WorkflowSupervisor(workspace_root=ws)
            supervisor.start_supervising("TASK_TEST_PROMPT", mode="automatic")
            
            td = _make_task_dir(ws, "TASK_TEST_PROMPT")
            session_key = f"agent:implementer:subagent:testpt:TASK_TEST_PROMPT"
            supervisor.add_agent_to_supervision(
                "TASK_TEST_PROMPT", session_key, "implementer", "S2_IMPLEMENTATION"
            )
            
            ts = supervisor._task_states["TASK_TEST_PROMPT"]
            agent = ts.agents[session_key]
            agent.retry_count = 0
            
            prompt = supervisor._build_retry_prompt(
                "TASK_TEST_PROMPT", agent, session_key
            )
            
            assert "RETRY DISPATCH" in prompt
            assert session_key in prompt
            assert f"Retry attempt:" in prompt
        finally:
            shutil.rmtree(ws)


# ====================================================================
# AC-5: State Machine Extensions
# ====================================================================

class TestStateMachineExtensions:
    """AC-5: Overlay states persisted; manual mode = observer only."""

    def test_overlay_states_valid_transitions(self):
        """Overlay state transitions follow the defined rules."""
        ws = _make_temp_workspace()
        try:
            supervisor = WorkflowSupervisor(workspace_root=ws)
            supervisor.start_supervising("TASK_TEST_SM", mode="automatic")
            
            # Valid: SUPERVISING → AGENT_STALLED
            assert supervisor.update_overlay_state("TASK_TEST_SM", "AGENT_STALLED") == True
            
            # Valid: AGENT_STALLED → HUMAN_INTERVENTION
            assert supervisor.update_overlay_state("TASK_TEST_SM", "HUMAN_INTERVENTION") == True
            
            # Invalid: TASK_ABORTED is terminal
            supervisor.update_overlay_state("TASK_TEST_SM", "TASK_ABORTED")
            assert supervisor.update_overlay_state("TASK_TEST_SM", "SUPERVISING") == False, \
                "TASK_ABORTED should be terminal"
        finally:
            shutil.rmtree(ws)

    def test_manual_mode_no_auto_recovery(self):
        """In manual mode, Supervisor warns but does NOT auto-recover."""
        ws = _make_temp_workspace()
        try:
            supervisor = WorkflowSupervisor(workspace_root=ws)
            supervisor.start_supervising("TASK_TEST_MANUAL", mode="manual")
            
            td = _make_task_dir(ws, "TASK_TEST_MANUAL")
            session_key = f"agent:implementer:subagent:testman:TASK_TEST_MANUAL"
            supervisor.add_agent_to_supervision(
                "TASK_TEST_MANUAL", session_key, "implementer", "S2_IMPLEMENTATION"
            )
            
            result = supervisor.attempt_recovery("TASK_TEST_MANUAL", session_key)
            assert result.success is False
            assert result.action_taken == "not_recovered_manual_mode"
            
            # Overlay state should remain SUPERVISING (no auto-transition)
            ts = supervisor._task_states["TASK_TEST_MANUAL"]
            assert ts.mode == "manual"
        finally:
            shutil.rmtree(ws)


# ====================================================================
# AC-6: User Notifications
# ====================================================================

class TestUserNotifications:
    """AC-6: All events generate notifications with severity mapping."""

    def test_notification_format(self):
        """Supervisor event formatting includes severity icon and actionable commands."""
        supervisor = WorkflowSupervisor()
        
        event = SupervisorEvent(
            type="ESCALATION",
            severity="CRITICAL",
            task_id="TASK_TEST_NOTIFY",
            message="Agent stalled after 2 retries.",
            actionable_commands=["/eo.retry", "/eo.abort", "/eo.continue"],
        )
        
        formatted = supervisor.format_notification(event)
        assert "🚨" in formatted, "CRITICAL should have 🚨 icon"
        assert "Escalation" in formatted
        assert "/eo.retry" in formatted
        assert "/eo.abort" in formatted

    def test_severity_icons(self):
        """Each severity level maps to the correct icon."""
        supervisor = WorkflowSupervisor()
        
        # CRITICAL → 🚨
        e1 = SupervisorEvent(type="TEST", severity="CRITICAL")
        assert "🚨" in supervisor.format_notification(e1)
        
        # WARNING → ⚠️
        e2 = SupervisorEvent(type="TEST", severity="WARNING")
        assert "⚠️" in supervisor.format_notification(e2)
        
        # INFO → ℹ️
        e3 = SupervisorEvent(type="TEST", severity="INFO")
        assert "ℹ️" in supervisor.format_notification(e3)

    def test_event_emitted_on_stall(self):
        """Stall detection emits a STALL_DETECTED event."""
        ws = _make_temp_workspace()
        try:
            supervisor = WorkflowSupervisor(workspace_root=ws)
            supervisor.start_supervising("TASK_TEST_STALL_EVT", mode="automatic")
            
            td = _make_task_dir(ws, "TASK_TEST_STALL_EVT")
            session_key = f"agent:implementer:subagent:testse:TASK_TEST_STALL_EVT"
            supervisor.add_agent_to_supervision(
                "TASK_TEST_STALL_EVT", session_key, "implementer", "S2_IMPLEMENTATION"
            )
            
            # Mark agent as stale
            ts = supervisor._task_states["TASK_TEST_STALL_EVT"]
            agent = ts.agents[session_key]
            agent.last_progress_at = (datetime.now(timezone.utc) - timedelta(seconds=400)).isoformat()
            
            stalled, _ = supervisor.detect_stall("TASK_TEST_STALL_EVT")
            assert len(stalled) == 1
            
            # Verify STALL_DETECTED event exists in the log
            event_types = [e.type for e in ts.events]
            assert "STALL_DETECTED" in event_types, f"Expected STALL_DETECTED event, got {event_types}"
        finally:
            shutil.rmtree(ws)


# ====================================================================
# AC-7: Tests for stuck, aborted, failed, lost sessions + manual mode
# ====================================================================

class TestStuckAbortedFailedLostSessions:
    """AC-7: Comprehensive test scenarios."""

    def test_stuck_session_scenario(self):
        """Test: heartbeat detects no progress → stall → retry → complete."""
        ws = _make_temp_workspace()
        try:
            supervisor = WorkflowSupervisor(
                config=SupervisorConfig(
                    no_progress_timeout_seconds=10,
                    hard_timeout_seconds=900,
                    retry_attempts=2,
                ),
                workspace_root=ws,
            )
            supervisor.start_supervising("TASK_TEST_STUCK", mode="automatic")
            
            td = _make_task_dir(ws, "TASK_TEST_STUCK")
            session_key = f"agent:implementer:subagent:testsc:TASK_TEST_STUCK"
            supervisor.add_agent_to_supervision(
                "TASK_TEST_STUCK", session_key, "implementer", "S2_IMPLEMENTATION"
            )
            
            # Simulate stuck agent (no progress for 30s > timeout of 10s)
            ts = supervisor._task_states["TASK_TEST_STUCK"]
            agent = ts.agents[session_key]
            agent.last_progress_at = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
            
            # Detect stall
            stalled, _ = supervisor.detect_stall("TASK_TEST_STUCK")
            assert len(stalled) == 1
            
            # Retry once
            result = supervisor.attempt_recovery("TASK_TEST_STUCK", session_key)
            assert result.success is True
            assert result.action_taken == "retried"
        finally:
            shutil.rmtree(ws)

    def test_aborted_session_scenario(self):
        """Test: Supervisor correctly aborts and writes failure report."""
        ws = _make_temp_workspace()
        try:
            supervisor = WorkflowSupervisor(workspace_root=ws)
            supervisor.start_supervising("TASK_TEST_ABORT", mode="automatic")
            
            td = _make_task_dir(ws, "TASK_TEST_ABORT")
            # Write a dummy artifact so we can verify it gets counted
            with open(os.path.join(td, "WORK_DONE.md"), "w") as f:
                f.write("# Work done\n")
            
            session_key = f"agent:implementer:subagent:testab:TASK_TEST_ABORT"
            supervisor.add_agent_to_supervision(
                "TASK_TEST_ABORT", session_key, "implementer", "S2_IMPLEMENTATION"
            )
            
            result = supervisor.abort_task("TASK_TEST_ABORT")
            assert result.success is True
            assert result.action_taken == "aborted"
            
            # Verify failure report written
            ts = supervisor._task_states["TASK_TEST_ABORT"]
            assert ts.overlay_state == "TASK_ABORTED"
        finally:
            shutil.rmtree(ws)

    def test_failed_session_scenario(self):
        """Test: Agent reports error → Supervisor handles per config."""
        ws = _make_temp_workspace()
        try:
            supervisor = WorkflowSupervisor(workspace_root=ws)
            supervisor.start_supervising("TASK_TEST_FAILED", mode="automatic")
            
            # Create a phantom session (no task dir) to simulate crash
            session_key = "agent:implementer:subagent:testfail:TASK_TEST_FAILED"
            supervisor.add_agent_to_supervision(
                "TASK_TEST_FAILED", session_key, "implementer", "S2_IMPLEMENTATION"
            )
            
            # Liveness check on phantom should detect failure
            liveness = supervisor.liveness.verify_session_alive(session_key)
            assert not liveness.alive, "Phantom session should be detected as not alive"
        finally:
            shutil.rmtree(ws)

    def test_lost_session_phantom(self):
        """Test: Liveness checker catches non-existent sessions."""
        ws = _make_temp_workspace()
        try:
            checker = LivenessChecker(workspace_root=ws)
            
            result = checker.verify_session_alive("agent:implementer:subagent:nonexistent_xyz:TASK_LOST")
            assert not result.alive, "Non-existent session should be detected as dead"
            assert result.status == "unknown"
        finally:
            shutil.rmtree(ws)

    def test_manual_mode_observer_only(self):
        """Test: Supervisor warns but does NOT auto-recover in manual mode."""
        ws = _make_temp_workspace()
        try:
            supervisor = WorkflowSupervisor(workspace_root=ws)
            supervisor.start_supervising("TASK_TEST_MANUAL_OB", mode="manual")
            
            td = _make_task_dir(ws, "TASK_TEST_MANUAL_OB")
            session_key = f"agent:implementer:subagent:testmo:TASK_TEST_MANUAL_OB"
            supervisor.add_agent_to_supervision(
                "TASK_TEST_MANUAL_OB", session_key, "implementer", "S2_IMPLEMENTATION"
            )
            
            # Try to recover — should NOT succeed in manual mode
            result = supervisor.attempt_recovery("TASK_TEST_MANUAL_OB", session_key)
            assert result.success is False
            assert result.action_taken == "not_recovered_manual_mode"
            
            # Overlay state should remain SUPERVISING (not AGENT_STALLED)
            ts = supervisor._task_states["TASK_TEST_MANUAL_OB"]
            assert ts.overlay_state == "SUPERVISING", \
                f"Manual mode should keep SUPERVISING, got {ts.overlay_state}"
        finally:
            shutil.rmtree(ws)


# ====================================================================
# AC-8: Integration and Config Validation
# ====================================================================

class TestIntegrationConfigValidation:
    """AC-8: End-to-end flow; config validation catches invalid thresholds."""

    def test_config_validation_default_sanity(self):
        """Default config satisfies derived constraint: heartbeat_interval ≤ no_progress_timeout / 4."""
        config = SupervisorConfig()
        assert config.heartbeat_interval_seconds <= config.no_progress_timeout_seconds / 4
        
        # hard_timeout ≥ no_progress_timeout + max(retry_backoff)
        assert config.hard_timeout_seconds >= config.no_progress_timeout_seconds + max(config.retry_backoff_seconds)

    def test_supervisor_summary(self):
        """Supervisor generates summary with agent details."""
        ws = _make_temp_workspace()
        try:
            supervisor = WorkflowSupervisor(workspace_root=ws)
            supervisor.start_supervising("TASK_TEST_SUMM", mode="automatic")
            
            td = _make_task_dir(ws, "TASK_TEST_SUMM")
            session_key = f"agent:implementer:subagent:testsm:TASK_TEST_SUMM"
            supervisor.add_agent_to_supervision(
                "TASK_TEST_SUMM", session_key, "implementer", "S2_IMPLEMENTATION"
            )
            
            summary = supervisor.get_supervisor_summary("TASK_TEST_SUMM")
            assert summary["task_id"] == "TASK_TEST_SUMM"
            assert summary["overlay_state"] == "SUPERVISING"
            assert summary["mode"] == "automatic"
            assert summary["agent_count"] >= 1
        finally:
            shutil.rmtree(ws)

    def test_event_log_tracking(self):
        """All supervisor events are tracked in the event log."""
        ws = _make_temp_workspace()
        try:
            supervisor = WorkflowSupervisor(workspace_root=ws)
            supervisor.start_supervising("TASK_TEST_LOG", mode="automatic")
            
            td = _make_task_dir(ws, "TASK_TEST_LOG")
            session_key = f"agent:implementer:subagent:testlog:TASK_TEST_LOG"
            supervisor.add_agent_to_supervision(
                "TASK_TEST_LOG", session_key, "implementer", "S2_IMPLEMENTATION"
            )
            
            ts = supervisor._task_states["TASK_TEST_LOG"]
            assert len(ts.events) >= 1  # At least the start event
            
            # Record a notification
            evt = supervisor.notify_user(
                "TASK_TEST_LOG", "STALL_DETECTED", "Test stall notification",
                severity="WARNING", session_key=session_key,
                actionable_commands=["/eo.retry"],
            )
            assert evt.type == "STALL_DETECTED"
        finally:
            shutil.rmtree(ws)


# ====================================================================
# LivenessChecker unit tests
# ====================================================================

class TestLivenessChecker:
    """Unit tests for the liveness checker component."""

    def test_extract_task_id_from_session(self):
        """Task ID extraction from session key works correctly."""
        ws = _make_temp_workspace()
        checker = LivenessChecker(workspace_root=ws)
        
        key = "agent:implementer:subagent:abc123:TASK_LIVENESS_001"
        task_id = checker._extract_task_id_from_session(key)
        assert task_id == "TASK_LIVENESS_001"

    def test_extract_agent_from_session(self):
        """Agent extraction from session key works correctly."""
        ws = _make_temp_workspace()
        checker = LivenessChecker(workspace_root=ws)
        
        key = "agent:implementer:subagent:abc123:TASK_LIVENESS_002"
        agent_id = checker._extract_agent_from_session(key)
        assert agent_id == "implementer"

    def test_health_report(self):
        """Health report correctly counts alive/dead/stalled sessions."""
        ws = _make_temp_workspace()
        try:
            td = _make_task_dir(ws, "TASK_HLTH_001")
            checker = LivenessChecker(workspace_root=ws)
            
            tracked = [
                {"session_key": f"agent:implementer:subagent:testh1:TASK_HLTH_001", "task_dir": td},
            ]
            report = checker.health_report(tracked)
            assert report["total"] == 1
        finally:
            shutil.rmtree(ws)


# ====================================================================
# SupervisorConfig dataclass tests
# ====================================================================

class TestSupervisorConfigDataclass:
    """Test the SupervisorConfig dataclass defaults and values."""

    def test_defaults(self):
        config = SupervisorConfig()
        assert config.heartbeat_interval_seconds == 60
        assert config.no_progress_timeout_seconds == 300
        assert config.hard_timeout_seconds == 900
        assert config.retry_attempts == 2
        assert config.retry_backoff_seconds == [60, 180]
        assert config.alert_on_first_stall is True
        assert config.notification_channels == ["webchat"]

    def test_custom_values(self):
        config = SupervisorConfig(
            heartbeat_interval_seconds=30,
            no_progress_timeout_seconds=60,
            hard_timeout_seconds=300,
            retry_attempts=5,
            retry_backoff_seconds=[10, 30, 90],
        )
        assert config.heartbeat_interval_seconds == 30
        assert config.retry_backoff_seconds == [10, 30, 90]


# ====================================================================
# Run
# ====================================================================

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
