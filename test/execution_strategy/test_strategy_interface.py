"""
Test: Strategy ABC contract compliance.

Phase A deliverable 8 of TASK_DS_EO_043.
Verifies that all strategy implementations satisfy the ExecutionStrategy ABC contract.
"""
import asyncio
import pytest
import sys
import os
from abc import ABC
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dispatcher.execution_strategy.strategy_base import (
    ExecutionStrategy, StrategyResult, CapabilityReport
)
from dispatcher.execution_strategy.constants import Strategy
from dispatcher.execution_strategy.concurrent_strategy import ConcurrentStrategy


class TestABCContract:
    """Verify that all strategy classes properly implement the ABC contract."""

    def test_concurrent_inherits_from_ABC(self):
        assert issubclass(ConcurrentStrategy, ExecutionStrategy)

    def test_concurrent_implements_prepare_for_agent(self):
        """prepare_for_agent must be async and return StrategyResult."""
        s = ConcurrentStrategy(workspace_root="/home/deepsim/ds_eo_openclaw")
        result = asyncio.get_event_loop().run_until_complete(
            s.prepare_for_agent("test_agent")
        )
        assert isinstance(result, StrategyResult)

    def test_concurrent_implements_release_agent(self):
        """release_agent must be async and return StrategyResult."""
        s = ConcurrentStrategy(workspace_root="/home/deepsim/ds_eo_openclaw")
        result = asyncio.get_event_loop().run_until_complete(
            s.release_agent("test_agent")
        )
        assert isinstance(result, StrategyResult)

    def test_concurrent_implements_can_support_concurrent_agents(self):
        """can_support_concurrent_agents must return bool."""
        s = ConcurrentStrategy(workspace_root="/home/deepsim/ds_eo_openclaw")
        result = s.can_support_concurrent_agents()
        assert isinstance(result, bool)

    def test_concurrent_implements_assess_capability(self):
        """assess_capability must return CapabilityReport."""
        s = ConcurrentStrategy(workspace_root="/home/deepsim/ds_eo_openclaw")
        report = s.assess_capability()
        assert isinstance(report, CapabilityReport)


class TestDataClasses:
    """Verify StrategyResult and CapabilityReport fields match contract."""

    def test_strategy_result_required_fields(self):
        r = StrategyResult(
            success=True,
            strategy="concurrent",
            model_status={"model1": {"installed": True}},
        )
        assert hasattr(r, 'success')
        assert hasattr(r, 'strategy')
        assert hasattr(r, 'model_status')
        assert hasattr(r, 'notes')
        assert hasattr(r, 'metadata')

    def test_capability_report_required_fields(self):
        r = CapabilityReport(
            strategy="sequential",
            confidence=0.9,
            signals={"test": 1},
            reason="test reason",
        )
        assert hasattr(r, 'strategy')
        assert hasattr(r, 'confidence')
        assert hasattr(r, 'signals')
        assert hasattr(r, 'reason')

    def test_strategy_result_default_notes(self):
        r = StrategyResult(success=True, strategy="x", model_status={})
        assert r.notes == []  # default_factory creates empty list
        assert r.metadata is None


class TestStrategyResultMetadata:
    """Test that metadata field works correctly (attached by ExecutionStrategyManager)."""

    def test_metadata_none_by_default(self):
        r = StrategyResult(success=True, strategy="x", model_status={})
        assert r.metadata is None

    def test_metadata_can_be_assigned(self):
        r = StrategyResult(success=True, strategy="x", model_status={})
        r.metadata = {"key": "value"}
        assert r.metadata == {"key": "value"}


class TestConcurrentStrategyBehavior:
    """Additional behavioral tests for ConcurrentStrategy ABC compliance."""

    def test_prepare_returns_strategy_field(self):
        s = ConcurrentStrategy(workspace_root="/home/deepsim/ds_eo_openclaw")
        result = asyncio.get_event_loop().run_until_complete(
            s.prepare_for_agent("implementer")
        )
        assert result.strategy == Strategy.CONCURRENT.value

    def test_release_returns_strategy_field(self):
        s = ConcurrentStrategy(workspace_root="/home/deepsim/ds_eo_openclaw")
        result = asyncio.get_event_loop().run_until_complete(
            s.release_agent("implementer")
        )
        assert result.strategy == Strategy.CONCURRENT.value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
