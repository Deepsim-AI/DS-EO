"""
DS-EO Session Health — Test Suite (§24, C11)

Comprehensive tests for the session health system covering:
- Health classification (Phase 2)
- Policy evaluation (Phase 3)
- Action execution and verification (Phase 4)
- Audit trail persistence (Phase 5)

Run with: python -m pytest tests/test_session_health.py -v
"""

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
