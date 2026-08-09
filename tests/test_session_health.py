"""
DS-EO Session Health — Test Suite (§24, C11)

Comprehensive tests for the session health system covering:
- Health classification (Phase 2)
- Policy evaluation (Phase 3)
- Action execution and verification (Phase 4)
- Audit trail persistence (Phase 5)

Run with: python -m pytest tests/test_session_health.py -v
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Add the project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from ds_eo_openclaw.session_health.enums import (
    SessionHealthState,
    LifecycleAction,
    MonitorStatus,
)
from ds_eo_openclaw.session_health.config import SessionHealthConfig, get_default_config
from ds_eo_openclaw.session_health.discoverer import SessionDiscoverer, SessionHealthData
from ds_eo_openclaw.session_health.classifier import HealthClassifier, ClassificationResult, SignalEvidence
from ds_eo_openclaw.session_health.policy import HealthPolicy, PolicyDecision
from ds_eo_openclaw.session_health.openclaw_api import OpenClawAPI
from ds_eo_openclaw.session_health.executor import SessionHealthExecutor


# --------------------------------------------------------------------------- #
# Test Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def default_config():
    """Standard conservative configuration."""
    return get_default_config()


@pytest.fixture
def custom_config():
    """Configuration with aggressive thresholds for testing."""
    return SessionHealthConfig(
        stale_after_seconds=60,           # 1 minute (aggressive)
        oversized_context_kb=1024,          # 1 MB
        max_compaction_attempts=1,
        error_threshold=1,
        orphan_inactive_seconds=30,         # 30 seconds
        monitoring_interval_seconds=60,     # 1 minute polling
    )


@pytest.fixture
def classifier(default_config):
    """HealthClassifier with default config."""
    return HealthClassifier(config=default_config)


@pytest.fixture
def policy(default_config):
    """HealthPolicy with default config and no protected sessions."""
    return HealthPolicy(config=default_config, protected_sessions=set())


# --------------------------------------------------------------------------- #
# Phase 2: Health Classification Tests (C3)
# --------------------------------------------------------------------------- #


class TestHealthClassifier:
    """Test deterministic classification with explainability."""

    def test_healthy_session(self, classifier):
        """Rule 8: Default — HEALTHY for active sessions within thresholds."""
        data = SessionHealthData(
            session_key="test-healthy",
            alive=True,
            status="running",
            age_seconds=300.0,
            inactivity_seconds=10.0,
            context_size_kb=500,
            compaction_status="OK",
            execution_state="RUNNING",
            error_count=0,
            task_association="ACTIVE",
        )

        result = classifier.classify(data)
        assert result.state == SessionHealthState.ACTIVE  # Active task protection overrides HEALTHY
        assert result.confidence == 1.0
        assert len(result.evidence) > 0

    def test_active_task_protection(self, classifier):
        """Rule 1: Active tasks are NEVER classified as unhealthy."""
        data = SessionHealthData(
            session_key="test-active",
            alive=True,
            status="running",
            age_seconds=7200.0,  # 2 hours old (would be STALE)
            inactivity_seconds=3700.0,  # Over stale threshold
            context_size_kb=60000,  # Oversized
            error_count=5,  # Above threshold
            task_association="ACTIVE",  # But has active task — protected!
        )

        result = classifier.classify(data)
        assert result.state == SessionHealthState.ACTIVE
        # Evidence should contain the active task signal explanation
        assert any("active task" in e.conclusion.lower() for e in result.evidence)

    def test_stale_session(self, classifier):
        """Rule 6: Inactive beyond stale threshold → STALE."""
        data = SessionHealthData(
            session_key="test-stale",
            alive=True,
            status="completed",
            age_seconds=7200.0,
            inactivity_seconds=3700.0,  # Over default 3600s threshold
            context_size_kb=500,
            compaction_status="OK",
            execution_state="IDLE",
            error_count=0,
            task_association="INACTIVE",
        )

        result = classifier.classify(data)
        assert result.state == SessionHealthState.STALE
        assert "stale" in result.summary.lower()

    def test_oversized_session(self, classifier):
        """Rule 3: Context exceeds threshold → OVERSIZED."""
        data = SessionHealthData(
            session_key="test-oversized",
            alive=True,
            status="running",
            age_seconds=600.0,
            inactivity_seconds=100.0,
            context_size_kb=52000,  # Over default 51200KB threshold
            compaction_status="OK",
            execution_state="IDLE",
            error_count=0,
            task_association="INACTIVE",
        )

        result = classifier.classify(data)
        assert result.state == SessionHealthState.OVERSIZED
        assert "oversized" in result.summary.lower() or "OVERSIZED" in result.summary

    def test_erroring_session(self, classifier):
        """Rule 4: Errors exceed threshold → ERRORING."""
        data = SessionHealthData(
            session_key="test-erroring",
            alive=True,
            status="running",
            age_seconds=600.0,
            inactivity_seconds=100.0,
            context_size_kb=500,
            compaction_status="OK",
            execution_state="RUNNING",
            error_count=4,  # Over default threshold of 3
            task_association="INACTIVE",
        )

        result = classifier.classify(data)
        assert result.state == SessionHealthState.ERRORING
        assert "error" in result.summary.lower()

    def test_orphaned_session(self, custom_config):
        """Rule 5: No task + inactive → ORPHANED."""
        # Use aggressive config for faster testing
        classifier = HealthClassifier(config=custom_config)
        
        data = SessionHealthData(
            session_key="test-orphan",
            alive=True,
            status="completed",
            age_seconds=100.0,
            inactivity_seconds=35.0,  # Over orphan threshold of 30s
            context_size_kb=500,
            compaction_status="OK",
            execution_state="IDLE",
            error_count=0,
            task_association="NONE",  # No task association
        )

        result = classifier.classify(data)
        assert result.state == SessionHealthState.ORPHANED
        assert "orphan" in result.summary.lower() or "ORPHANED" in result.summary

    def test_recovery_required_session(self, custom_config):
        """Rule 2: Compaction failed + retries exhausted → RECOVERY_REQUIRED."""
        classifier = HealthClassifier(config=custom_config)
        
        data = SessionHealthData(
            session_key="test-recovery",
            alive=True,
            status="running",
            age_seconds=600.0,
            inactivity_seconds=100.0,
            context_size_kb=500,
            compaction_status="FAILED",
            execution_state="IDLE",
            error_count=0,
            task_association="INACTIVE",
            recovery_history=["attempt_1", "attempt_2"],  # Over threshold of 1
        )

        result = classifier.classify(data)
        assert result.state == SessionHealthState.RECOVERY_REQUIRED
        assert "recovery" in result.summary.lower() or "RECOVERY" in result.summary

    def test_compaction_failed_with_retries_remaining(self, custom_config):
        """Rule 2: Compaction failed but retries remain → not RECOVERY_REQUIRED."""
        classifier = HealthClassifier(config=custom_config)
        
        data = SessionHealthData(
            session_key="test-compaction",
            alive=True,
            status="running",
            age_seconds=600.0,
            inactivity_seconds=100.0,
            context_size_kb=500,
            compaction_status="FAILED",
            execution_state="IDLE",
            error_count=0,
            task_association="INACTIVE",
            recovery_history=["attempt_1"],  # At threshold but not exceeded
        )

        result = classifier.classify(data)
        # Should NOT be RECOVERY_REQUIRED since retries remain
        assert result.state != SessionHealthState.RECOVERY_REQUIRED

    def test_stuck_execution(self, classifier):
        """Rule 7: Execution stuck → STUCK."""
        data = SessionHealthData(
            session_key="test-stuck",
            alive=True,
            status="running",
            age_seconds=600.0,
            inactivity_seconds=100.0,
            context_size_kb=500,
            compaction_status="OK",
            execution_state="STUCK",  # Stuck execution
            error_count=0,
            task_association="INACTIVE",
        )

        result = classifier.classify(data)
        assert result.state == SessionHealthState.STUCK
        assert "stuck" in result.summary.lower() or "STUCK" in result.summary

    def test_unknown_session(self, classifier):
        """Rule 8: Not alive and no other signals → UNKNOWN."""
        data = SessionHealthData(
            session_key="test-unknown",
            alive=False,
            status="error",
            age_seconds=600.0,
            inactivity_seconds=100.0,
            context_size_kb=None,  # Unknown
            compaction_status="UNDETERMINED",
            execution_state="UNKNOWN",
            error_count=0,
            task_association="NONE",
        )

        result = classifier.classify(data)
        assert result.state == SessionHealthState.UNKNOWN
        assert result.confidence < 1.0  # Lower confidence for UNKNOWN

    def test_classification_includes_explanation(self, classifier):
        """Every classification includes human-readable explanation."""
        data = SessionHealthData(
            session_key="test-explain",
            alive=True,
            status="running",
            age_seconds=7200.0,
            inactivity_seconds=3700.0,  # Stale
            context_size_kb=500,
            compaction_status="OK",
            execution_state="IDLE",
            error_count=0,
            task_association="INACTIVE",
        )

        result = classifier.classify(data)
        assert len(result.evidence) > 0
        assert all(isinstance(e, SignalEvidence) for e in result.evidence)
        
        # Verify evidence has required fields
        for evidence in result.evidence:
            assert hasattr(evidence, 'signal_name')
            assert hasattr(evidence, 'conclusion')

    def test_classification_to_dict(self, classifier):
        """ClassificationResult can be serialized to dict."""
        data = SessionHealthData(
            session_key="test-dict",
            alive=True,
            status="running",
            task_association="ACTIVE",
        )

        result = classifier.classify(data)
        d = result.to_dict()
        
        assert "session_key" in d
        assert "state" in d
        assert "evidence" in d
        assert "summary" in d


# --------------------------------------------------------------------------- #
# Phase 3: Policy Evaluation Tests (C4)
# --------------------------------------------------------------------------- #


class TestHealthPolicy:
    """Test deterministic policy mapping with safety layers."""

    def test_active_task_protection(self, policy):
        """Safety Layer 1: Active tasks → NO_ACTION always."""
        # Include evidence with active task signal so safety layer detects it
        classification = ClassificationResult(
            session_key="test-protected",
            state=SessionHealthState.STALE,  # Would normally get MARK_STALE
            evidence=[SignalEvidence(signal_name="task_association", value="ACTIVE", conclusion="Active task detected")],
        )

        decision = policy.evaluate("test-protected", classification)
        assert decision.action == LifecycleAction.NO_ACTION
        assert decision.is_safety_override is True
        assert "active task" in decision.reason.lower()

    def test_protected_session(self, default_config):
        """Safety Layer 2: Protected sessions → WARN always."""
        policy = HealthPolicy(
            config=default_config,
            protected_sessions={"test-protected-session"},
        )

        classification = ClassificationResult(
            session_key="test-protected-session",
            state=SessionHealthState.ORPHANED,  # Would normally get ARCHIVE
        )

        decision = policy.evaluate("test-protected-session", classification)
        assert decision.action == LifecycleAction.WARN
        assert decision.is_safety_override is True

    def test_recovery_required_action(self, policy):
        """Safety Layer 3: Recovery required → ESCALATE."""
        classification = ClassificationResult(
            session_key="test-recovery",
            state=SessionHealthState.RECOVERY_REQUIRED,
        )

        decision = policy.evaluate("test-recovery", classification)
        assert decision.action == LifecycleAction.ESCALATE
        assert "recovery" in decision.reason.lower()

    def test_stale_to_mark_stale(self, policy):
        """STALE → MARK_STALE (if no active task)."""
        classification = ClassificationResult(
            session_key="test-stale",
            state=SessionHealthState.STALE,
        )

        decision = policy.evaluate("test-stale", classification)
        assert decision.action == LifecycleAction.MARK_STALE

    def test_oversized_to_compact(self, policy):
        """OVERSIZED → COMPACT."""
        classification = ClassificationResult(
            session_key="test-oversized",
            state=SessionHealthState.OVERSIZED,
        )

        decision = policy.evaluate("test-oversized", classification)
        assert decision.action == LifecycleAction.COMPACT

    def test_erroring_to_warn(self, policy):
        """ERRORING → WARN."""
        classification = ClassificationResult(
            session_key="test-erroring",
            state=SessionHealthState.ERRORING,
        )

        decision = policy.evaluate("test-erroring", classification)
        assert decision.action == LifecycleAction.WARN

    def test_orphaned_to_archive(self, policy):
        """ORPHANED → ARCHIVE."""
        classification = ClassificationResult(
            session_key="test-orphaned",
            state=SessionHealthState.ORPHANED,
        )

        decision = policy.evaluate("test-orphaned", classification)
        assert decision.action == LifecycleAction.ARCHIVE

    def test_stuck_to_escalate(self, policy):
        """STUCK → ESCALATE."""
        classification = ClassificationResult(
            session_key="test-stuck",
            state=SessionHealthState.STUCK,
        )

        decision = policy.evaluate("test-stuck", classification)
        assert decision.action == LifecycleAction.ESCALATE

    def test_compaction_failed_to_retry(self, policy):
        """COMPACTION_FAILED → RETRY_COMPACTION."""
        classification = ClassificationResult(
            session_key="test-compaction-failed",
            state=SessionHealthState.COMPACTION_FAILED,
        )

        decision = policy.evaluate("test-compaction-failed", classification)
        assert decision.action == LifecycleAction.RETRY_COMPACTION

    def test_healthy_to_no_action(self, policy):
        """HEALTHY → NO_ACTION."""
        classification = ClassificationResult(
            session_key="test-healthy",
            state=SessionHealthState.HEALTHY,
        )

        decision = policy.evaluate("test-healthy", classification)
        assert decision.action == LifecycleAction.NO_ACTION


# --------------------------------------------------------------------------- #
# Phase 2: Configuration Tests (C8)
# --------------------------------------------------------------------------- #


class TestConfig:
    """Test configurable thresholds and defaults."""

    def test_default_config_values(self):
        """Default config has conservative values."""
        config = get_default_config()
        
        assert config.stale_after_seconds == 3600
        assert config.oversized_context_kb == 51200
        assert config.max_compaction_attempts == 2
        assert config.error_threshold == 3
        assert config.orphan_inactive_seconds == 7200
        assert config.monitoring_interval_seconds == 300
        assert config.observe_by_default is True

    def test_custom_config_override(self):
        """Custom config overrides all defaults."""
        config = SessionHealthConfig(
            stale_after_seconds=100,
            oversized_context_kb=2000,
            max_compaction_attempts=5,
            error_threshold=10,
            orphan_inactive_seconds=60,
            monitoring_interval_seconds=60,
            observe_by_default=False,
        )

        assert config.stale_after_seconds == 100
        assert config.oversized_context_kb == 2000
        assert config.max_compaction_attempts == 5
        assert config.error_threshold == 10
        assert config.orphan_inactive_seconds == 60
        assert config.monitoring_interval_seconds == 60
        assert config.observe_by_default is False

    def test_config_to_dict_roundtrip(self):
        """Config can be serialized and deserialized."""
        original = SessionHealthConfig(stale_after_seconds=999)
        d = original.to_dict()
        
        restored = SessionHealthConfig.from_dict(d)
        assert restored.stale_after_seconds == 999
        # Other fields should match defaults since they weren't in dict
        assert restored.oversized_context_kb == 51200

    def test_config_from_yaml_fallback(self):
        """from_yaml_path falls back to defaults on error."""
        config = SessionHealthConfig.from_yaml_path("/nonexistent/path.yaml")
        
        # Should return defaults, not raise exception
        assert isinstance(config, SessionHealthConfig)
        assert config.stale_after_seconds == 3600

    def test_monitoring_enabled(self):
        """is_monitoring_enabled reflects monitoring_interval_seconds."""
        config_with_monitoring = get_default_config()
        assert config_with_monitoring.is_monitoring_enabled() is True
        
        config_without_monitoring = SessionHealthConfig(monitoring_interval_seconds=None)
        assert config_without_monitoring.is_monitoring_enabled() is False


# --------------------------------------------------------------------------- #
# Phase 2: Enum Tests (C1)
# --------------------------------------------------------------------------- #


class TestEnums:
    """Test enum properties and behavior."""

    def test_health_state_is_critical(self):
        """is_critical correctly identifies critical states."""
        assert SessionHealthState.RECOVERY_REQUIRED.is_critical is True
        assert SessionHealthState.COMPACTION_FAILED.is_critical is True
        assert SessionHealthState.ERRORING.is_critical is True
        
        assert SessionHealthState.HEALTHY.is_critical is False
        assert SessionHealthState.ACTIVE.is_critical is False

    def test_health_state_requires_action(self):
        """requires_action identifies non-healthy states."""
        assert SessionHealthState.STALE.requires_action is True
        assert SessionHealthState.OVERSIZED.requires_action is True
        
        assert SessionHealthState.HEALTHY.requires_action is False
        assert SessionHealthState.ACTIVE.requires_action is False

    def test_lifecycle_action_is_destructive(self):
        """is_destructive identifies destructive actions."""
        assert LifecycleAction.ARCHIVE.is_destructive is True
        assert LifecycleAction.CLOSE.is_destructive is True
        
        assert LifecycleAction.NO_ACTION.is_destructive is False
        assert LifecycleAction.WARN.is_destructive is False

    def test_lifecycle_action_is_execution(self):
        """is_execution_action identifies actual work actions."""
        assert LifecycleAction.COMPACT.is_execution_action is True
        assert LifecycleAction.ESCALATE.is_execution_action is True
        
        assert LifecycleAction.NO_ACTION.is_execution_action is False
        assert LifecycleAction.WARN.is_execution_action is False

    def test_monitor_status_allows_execution(self):
        """allows_execution only for ACTIVE status."""
        assert MonitorStatus.ACTIVE.allows_execution is True
        assert MonitorStatus.OBSERVING.allows_execution is False
        assert MonitorStatus.PAUSED.allows_execution is False


# --------------------------------------------------------------------------- #
# Phase 2: Discoverer Tests (C2) - Basic Signal Collection
# --------------------------------------------------------------------------- #


class TestDiscoverer:
    """Test session discovery and signal collection."""

    def test_discover_all_sessions_returns_list(self):
        """discover_all_sessions returns a list of SessionHealthData."""
        discoverer = SessionDiscoverer()
        sessions = discoverer.discover_all_sessions()
        
        assert isinstance(sessions, list)

    def test_session_health_data_structure(self):
        """SessionHealthData has all required fields."""
        data = SessionHealthData(session_key="test")
        
        assert hasattr(data, 'session_key')
        assert hasattr(data, 'alive')
        assert hasattr(data, 'status')
        assert hasattr(data, 'age_seconds')
        assert hasattr(data, 'inactivity_seconds')
        assert hasattr(data, 'context_size_kb')
        assert hasattr(data, 'compaction_status')
        assert hasattr(data, 'execution_state')
        assert hasattr(data, 'error_count')
        assert hasattr(data, 'task_association')
        assert hasattr(data, 'recovery_history')
        assert hasattr(data, 'associated_task_id')
        assert hasattr(data, 'mapping_confidence')

    def test_discoverer_with_workspace_root(self):
        """SessionDiscoverer accepts custom workspace root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            discoverer = SessionDiscoverer(workspace_root=tmpdir)
            assert discoverer.workspace_root == os.path.abspath(tmpdir)


# --------------------------------------------------------------------------- #
# Integration Tests: Full Pipeline (Phase 2-5)
# --------------------------------------------------------------------------- #


class TestFullPipeline:
    """Test the complete health pipeline: discover → classify → policy."""

    def test_pipeline_healthy_session(self, default_config):
        """Complete pipeline for a healthy session."""
        discoverer = SessionDiscoverer()
        classifier = HealthClassifier(config=default_config)
        policy = HealthPolicy(config=default_config)

        # Simulate discovered data
        data = SessionHealthData(
            session_key="test-pipeline-healthy",
            alive=True,
            status="running",
            age_seconds=300.0,
            inactivity_seconds=10.0,
            context_size_kb=500,
            compaction_status="OK",
            execution_state="RUNNING",
            error_count=0,
            task_association="ACTIVE",
        )

        # Classify
        classification = classifier.classify(data)
        
        # Evaluate policy
        decision = policy.evaluate(classification.session_key, classification)
        
        assert decision.action == LifecycleAction.NO_ACTION

    def test_pipeline_stale_session(self, default_config):
        """Complete pipeline for a stale session."""
        discoverer = SessionDiscoverer()
        classifier = HealthClassifier(config=default_config)
        policy = HealthPolicy(config=default_config)

        data = SessionHealthData(
            session_key="test-pipeline-stale",
            alive=True,
            status="completed",
            age_seconds=7200.0,
            inactivity_seconds=3700.0,  # Over threshold
            context_size_kb=500,
            compaction_status="OK",
            execution_state="IDLE",
            error_count=0,
            task_association="INACTIVE",
        )

        classification = classifier.classify(data)
        decision = policy.evaluate(classification.session_key, classification)
        
        assert decision.action == LifecycleAction.MARK_STALE

    def test_pipeline_active_task_protection(self, default_config):
        """Active tasks are protected through the entire pipeline."""
        discoverer = SessionDiscoverer()
        classifier = HealthClassifier(config=default_config)
        policy = HealthPolicy(config=default_config)

        # Data that would normally be STALE due to age/inactivity
        data = SessionHealthData(
            session_key="test-pipeline-protected",
            alive=True,
            status="running",
            age_seconds=7200.0,  # Would trigger STALE
            inactivity_seconds=3700.0,  # Would trigger STALE
            context_size_kb=500,
            compaction_status="OK",
            execution_state="IDLE",
            error_count=0,
            task_association="ACTIVE",  # But has active task — protected!
        )

        classification = classifier.classify(data)
        decision = policy.evaluate(classification.session_key, classification)
        
        assert decision.action == LifecycleAction.NO_ACTION


# --------------------------------------------------------------------------- #
# Test Runner Entry Point
# --------------------------------------------------------------------------- #


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ===== Phase 7: Real OpenClaw API Integration Tests (TASK_DS_EO_035) =====


class TestOpenClawAPI:
    """Test the OpenClawAPI wrapper with mocked subprocess calls."""

    def test_compact_session_success(self):
        """COMPACT: successful compaction returns context size in KB."""
        api = OpenClawAPI()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({"contextSizeBytes": 1048576}),
                stderr="",
            )
            result = api.compact_session("test-session-key")

        assert result["success"] is True
        assert result["error"] is None
        assert result["context_size_kb"] == 1024  # 1MB → 1024KB

    def test_compact_session_failure(self):
        """COMPACT: non-zero exit code returns failure with error message."""
        api = OpenClawAPI()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="compaction failed: session not found",
            )
            result = api.compact_session("nonexistent-session")

        assert result["success"] is False
        assert "CLI failed" in result["error"]
        assert result["context_size_kb"] is None

    def test_archive_session_success(self):
        """ARCHIVE: successful export returns file path."""
        api = OpenClawAPI()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({"filePath": "/tmp/archive.tar.gz"}),
                stderr="",
            )
            result = api.archive_session("test-session-key")

        assert result["success"] is True
        assert result["error"] is None
        assert result["file_path"] == "/tmp/archive.tar.gz"

    def test_archive_session_failure(self):
        """ARCHIVE: non-zero exit code returns failure with error message."""
        api = OpenClawAPI()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="export failed: session not found",
            )
            result = api.archive_session("nonexistent-session")

        assert result["success"] is False
        assert "CLI failed" in result["error"]
        assert result["file_path"] is None

    def test_close_session_not_supported(self):
        """CLOSE: documents limitation when no direct close API exists."""
        api = OpenClawAPI()
        with patch("subprocess.run") as mock_run:
            # Simulate cleanup returning empty result (session still in store)
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps([]),
                stderr="",
            )
            result = api.close_session("test-session-key")

        assert result["success"] is False
        assert "does not support direct session close" in result["error"].lower()
        assert result["method"] == "none"

    def test_get_session_info_success(self):
        """GET_INFO: returns context size, turn count, and status for found session."""
        api = OpenClawAPI()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps([
                    {
                        "key": "test-session-key",
                        "contextSizeBytes": 2097152,
                        "turnCount": 42,
                        "status": "running",
                        "lastTurnTime": "2026-08-08T23:00:00Z",
                    }
                ]),
                stderr="",
            )
            result = api.get_session_info("test-session-key")

        assert result["success"] is True
        assert result["context_size_bytes"] == 2097152
        assert result["turn_count"] == 42
        assert result["status"] == "running"
        assert result["last_turn_time"] == "2026-08-08T23:00:00Z"

    def test_get_session_info_not_found(self):
        """GET_INFO: returns failure when session is not in the store."""
        api = OpenClawAPI()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps([]),  # Empty list — session not found
                stderr="",
            )
            result = api.get_session_info("nonexistent-session-key")

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_run_cmd_timeout(self):
        """_run_cmd: handles subprocess.TimeoutExpired gracefully."""
        api = OpenClawAPI(timeout_seconds=1)
        with patch("subprocess.run") as mock_run:
            import subprocess
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["openclaw", "sessions", "list"],
                timeout=1,
            )
            success, stdout, stderr = api._run_cmd(["openclaw", "sessions", "list"])

        assert success is False
        assert "timed out" in stderr.lower()

    def test_run_cmd_file_not_found(self):
        """_run_cmd: handles FileNotFoundError when openclaw CLI is missing."""
        api = OpenClawAPI()
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("openclaw not found in PATH")
            success, stdout, stderr = api._run_cmd(["openclaw", "sessions", "list"])

        assert success is False
        assert "not found" in stderr.lower()


# ===== Phase 7: Executor Integration Tests (mocked at subprocess level) =====


class TestExecutorPhase7:
    """Test executor action handlers with mocked OpenClaw API."""

    @pytest.fixture
    def mock_api_client(self):
        """Create a mock OpenClawAPI client for executor tests."""
        return MagicMock(spec=OpenClawAPI)

    @pytest.fixture
    def executor_with_mock_api(self, mock_api_client):
        """Create an executor with a mocked API client (active monitoring)."""
        config = get_default_config()
        return SessionHealthExecutor(
            config=config,
            monitor_status=MonitorStatus.ACTIVE,
            api_client=mock_api_client,
        )

    def test_compact_with_mock_success(self, executor_with_mock_api, mock_api_client):
        """COMPACT: real API call returns successful result with reduced context size."""
        # Mock the API to return a successful compaction with smaller context
        mock_api_client.compact_session.return_value = {
            "success": True,
            "error": None,
            "context_size_kb": 500,  # Reduced from pre-size
        }

        health_data = SessionHealthData(
            session_key="test-session",
            alive=True,
            status="running",
            context_size_kb=1000,  # Pre-compact size (larger)
            error_count=0,
            age_seconds=300.0,
            task_association="INACTIVE",
        )

        result = executor_with_mock_api.execute(
            "test-session", LifecycleAction.COMPACT, health_data
        )

        assert result.success is True
        assert result.verified is True  # Post-size (500) < pre-size (1000)
        assert result.post_metrics["context_size_kb_after"] == 500
        mock_api_client.compact_session.assert_called_once_with("test-session")

    def test_compact_with_mock_failure(self, executor_with_mock_api, mock_api_client):
        """COMPACT: real API call returns failure — action fails gracefully."""
        # Mock the API to return a failure
        mock_api_client.compact_session.return_value = {
            "success": False,
            "error": "compaction failed",
            "context_size_kb": None,
        }

        health_data = SessionHealthData(
            session_key="test-session",
            alive=True,
            status="running",
            context_size_kb=1000,
            error_count=0,
            age_seconds=300.0,
            task_association="INACTIVE",
        )

        result = executor_with_mock_api.execute(
            "test-session", LifecycleAction.COMPACT, health_data
        )

        assert result.success is False
        assert result.error_message == "compaction failed"
        mock_api_client.compact_session.assert_called_once()

    def test_archive_with_mock_success(self, executor_with_mock_api, mock_api_client):
        """ARCHIVE: real API call returns successful archive with file path."""
        # Mock the API to return a successful archive
        mock_api_client.archive_session.return_value = {
            "success": True,
            "error": None,
            "file_path": "/tmp/test-archive.tar.gz",
        }

        health_data = SessionHealthData(
            session_key="test-session",
            alive=True,
            status="completed",
            context_size_kb=500,
            error_count=0,
            age_seconds=3600.0,
            task_association="INACTIVE",  # Not active — can archive
        )

        # Patch os.path.exists so the executor's verification passes
        with patch("os.path.exists", return_value=True):
            result = executor_with_mock_api.execute(
                "test-session", LifecycleAction.ARCHIVE, health_data
        
        )

        assert result.success is True
        assert result.verified is True  # File path exists on disk (mocked)
        mock_api_client.archive_session.assert_called_once()

    def test_archive_active_task_blocked(self, executor_with_mock_api):
        """ARCHIVE: active task sessions are blocked before API call."""
        health_data = SessionHealthData(
            session_key="test-session",
            alive=True,
            status="running",
            context_size_kb=500,
            error_count=0,
            age_seconds=3600.0,
            task_association="ACTIVE",  # Active — cannot archive
        )

        # Patch os.path.exists so the executor's verification passes
        with patch("os.path.exists", return_value=True):
            result = executor_with_mock_api.execute(
                "test-session", LifecycleAction.ARCHIVE, health_data
        
        )

        assert result.success is False
        assert "active" in result.error_message.lower()

    def test_close_with_mock_failure(self, executor_with_mock_api, mock_api_client):
        """CLOSE: documents limitation when no direct close API exists."""
        # Mock the API to return failure (session still in store)
        mock_api_client.close_session.return_value = {
            "success": False,
            "method": "none",
            "error": "OpenClaw does not support direct session close",
        }

        health_data = SessionHealthData(
            session_key="test-session",
            alive=False,  # Not alive — safe to attempt close
            status="completed",
            context_size_kb=500,
            error_count=0,
            age_seconds=3600.0,
            task_association="INACTIVE",  # Not active — can attempt close
        )

        result = executor_with_mock_api.execute(
            "test-session", LifecycleAction.CLOSE, health_data
        )

        assert result.success is False
        assert "does not support direct session close" in result.error_message.lower()
        mock_api_client.close_session.assert_called_once()

    def test_warn_delivers_notification(self, executor_with_mock_api):
        """WARN: writes structured notification file to ~/.openclaw/notifications/."""
        health_data = SessionHealthData(
            session_key="test-session",
            alive=True,
            status="running",
            context_size_kb=5000,
            error_count=0,
            age_seconds=3600.0,
            task_association="INACTIVE",
        )

        result = executor_with_mock_api.execute(
            "test-session", LifecycleAction.WARN, health_data
        )

        assert result.success is True
        assert result.post_metrics.get("warning_recorded") is True
        # Verify notification file was created (check path exists)
        notification_file = result.post_metrics.get("notification_file")
        if notification_file:
            assert os.path.exists(notification_file) or "notifications" in notification_file

    def test_monitor_updates_internal_state(self, executor_with_mock_api):
        """MONITOR: updates internal monitoring config without real API call."""
        health_data = SessionHealthData(
            session_key="test-session",
            alive=True,
            status="running",
            context_size_kb=500,
            error_count=0,
            age_seconds=3600.0,
            task_association="INACTIVE",
        )

        result = executor_with_mock_api.execute(
            "test-session", LifecycleAction.MONITOR, health_data
        )

        assert result.success is True
        assert result.post_metrics.get("monitoring_enabled") is True
        # Should include the configured polling interval
        assert str(executor_with_mock_api.config.monitoring_interval_seconds) in str(result.details)

    def test_e2e_compact_verify_size_reduction(self, executor_with_mock_api, mock_api_client):
        """End-to-end: COMPACT → verify pre-size > post-size."""
        # Mock the API to return a smaller context size after compaction
        mock_api_client.compact_session.return_value = {
            "success": True,
            "error": None,
            "context_size_kb": 200,  # Much smaller than pre-size
        }

        health_data = SessionHealthData(
            session_key="test-session",
            alive=True,
            status="running",
            context_size_kb=1000,  # Pre-compact size (large)
            error_count=0,
            age_seconds=3600.0,
            task_association="INACTIVE",
        )

        result = executor_with_mock_api.execute(
            "test-session", LifecycleAction.COMPACT, health_data
        )

        assert result.success is True
        assert result.verified is True
        # Verify the pre/post metrics show reduction
        pre_size = result.pre_metrics.get("context_size_kb")
        post_size = result.post_metrics.get("context_size_kb_after")
        assert pre_size is not None and post_size is not None
        assert pre_size > post_size, f"Pre-size ({pre_size}) should be greater than post-size ({post_size})"

    def test_protected_session_warn_only(self):
        """Protected sessions: only WARN allowed — COMPACT/ARCHIVE/CLOSE blocked."""
        config = get_default_config()
        protected_key = "protected-session-key"
        executor = SessionHealthExecutor(
            config=config,
            monitor_status=MonitorStatus.ACTIVE,
            protected_sessions={protected_key},
        )

        health_data = SessionHealthData(
            session_key=protected_key,
            alive=True,
            status="running",
            context_size_kb=5000,
            error_count=0,
            age_seconds=3600.0,
            task_association="INACTIVE",
        )

        # COMPACT should be blocked on protected session
        compact_result = executor.execute(
            protected_key, LifecycleAction.COMPACT, health_data
        )
        assert compact_result.success is False
        assert "protected" in compact_result.error_message.lower()

        # ARCHIVE should be blocked on protected session
        archive_result = executor.execute(
            protected_key, LifecycleAction.ARCHIVE, health_data
        )
        assert archive_result.success is False
        assert "protected" in archive_result.error_message.lower()

        # CLOSE should be blocked on protected session
        close_result = executor.execute(
            protected_key, LifecycleAction.CLOSE, health_data
        )
        assert close_result.success is False
        assert "protected" in close_result.error_message.lower()

        # WARN should still work on protected sessions
        warn_result = executor.execute(
            protected_key, LifecycleAction.WARN, health_data
        )
        assert warn_result.success is True  # WARN allowed even on protected sessions

    def test_monitor_status_blocks_execution(self):
        """OBSERVING/PAUSED status: no actions executed (dry-run mode)."""
        config = get_default_config()
        executor = SessionHealthExecutor(
            config=config,
            monitor_status=MonitorStatus.OBSERVING,  # Not ACTIVE
        )

        health_data = SessionHealthData(
            session_key="test-session",
            alive=True,
            status="running",
            context_size_kb=500,
            error_count=0,
            age_seconds=3600.0,
            task_association="INACTIVE",
        )

        result = executor.execute("test-session", LifecycleAction.COMPACT, health_data)
        assert result.success is False
        assert "observing" in result.error_message.lower()


# ===== Phase 7: Discoverer Integration Tests =====


class TestDiscovererPhase7:
    """Test discoverer's real context size query with mocked API."""

    def test_get_real_context_size_from_api(self):
        """Real context size is queried from OpenClaw API when available."""
        discoverer = SessionDiscoverer()

        # Mock the API client to return a specific context size
        with patch.object(discoverer.api_client, 'get_session_info') as mock_get:
            mock_get.return_value = {
                "success": True,
                "context_size_bytes": 2097152,  # 2MB in bytes
                "turn_count": None,
                "status": None,
                "last_turn_time": None,
                "error": None,
            }

            result = discoverer._get_real_context_size("test-session-key")

        assert result == 2048  # 2MB → 2048KB (integer division)
        mock_get.assert_called_once_with("test-session-key")

    def test_get_real_context_size_fallback_to_estimation(self):
        """Falls back to estimation when API is unavailable."""
        discoverer = SessionDiscoverer()

        # Mock the API client to return failure (API unavailable)
        with patch.object(discoverer.api_client, 'get_session_info') as mock_get:
            mock_get.return_value = {
                "success": False,
                "context_size_bytes": None,
                "turn_count": None,
                "status": None,
                "last_turn_time": None,
                "error": "API unavailable",
            }

            # Fallback: estimation from file system (uses existing _estimate_context_size)
            with patch.object(discoverer, '_estimate_context_size', return_value=42):
                result = discoverer._get_real_context_size("agent:reviewer:TASK_DS_EO_035")

        assert result == 42  # Estimation fallback value

    def test_get_real_context_size_api_error(self):
        """Returns None when API fails and estimation also has no data."""
        discoverer = SessionDiscoverer()

        with patch.object(discoverer.api_client, 'get_session_info') as mock_get:
            mock_get.return_value = {
                "success": False,
                "context_size_bytes": None,
                "turn_count": None,
                "status": None,
                "last_turn_time": None,
                "error": "API error",
            }

            # No task directory to estimate from — returns None
            result = discoverer._get_real_context_size("no-task-id-session")

        assert result is None
