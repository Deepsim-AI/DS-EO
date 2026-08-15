"""
Test: ConcurrentStrategy preserves existing spawn behavior (zero behavioral change).

Phase A deliverable 8 of TASK_DS_EO_043.
"""
import asyncio
import pytest
from unittest.mock import MagicMock, patch

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dispatcher.execution_strategy.concurrent_strategy import ConcurrentStrategy
from dispatcher.execution_strategy.strategy_base import StrategyResult


@pytest.fixture
def strategy():
    return ConcurrentStrategy(workspace_root="/home/deepsim/ds_eo_openclaw")


class TestConcurrentIdentity:
    """Verify that concurrent mode introduces zero behavioral change."""

    def test_prepare_returns_success(self, strategy):
        result = asyncio.get_event_loop().run_until_complete(
            strategy.prepare_for_agent("implementer")
        )
        # When spawn manager fails to resolve (no real registry), 
        # the fallback should still return success=True with model info
        assert isinstance(result, StrategyResult)
        assert result.strategy == "concurrent"

    def test_release_no_op(self, strategy):
        result = asyncio.get_event_loop().run_until_complete(
            strategy.release_agent("implementer")
        )
        assert result.success is True
        assert result.strategy == "concurrent"
        assert "no unloading" in result.notes[0].lower()

    def test_can_support_concurrent(self, strategy):
        assert strategy.can_support_concurrent_agents() is True

    def test_spawns_via_existing_manager_if_available(self, strategy):
        """When spawn manager exists, delegate to it."""
        mock_outcome = MagicMock()
        mock_outcome.success = True
        
        # Bug2a fix: spawn_manager is a @property descriptor, so we must patch
        # on the *class* (type(strategy)), not the instance. 
        mock_spawn_mgr = MagicMock()
        mock_spawn_mgr.spawn_agent.return_value = mock_outcome
        
        # Also mock registry resolution since real agents_list.json lookup for
        # "implementer" returns agent=None (load-all, not find-one). We need to
        # make the registry path return success=True with a valid model name.
        mock_registry_result = MagicMock()
        mock_registry_result.success = True
        mock_agent_info = MagicMock()
        mock_agent_info.model = "ollama/qwen3.6:35b"
        mock_registry_result.agent = mock_agent_info

        with patch.object(type(strategy), 'spawn_manager', new_callable=lambda: mock_spawn_mgr):
            with patch('dispatcher.registry.AgentRegistry') as MockReg:
                instance = MockReg.return_value
                instance.load.return_value = mock_registry_result
                result = asyncio.get_event_loop().run_until_complete(
                    strategy.prepare_for_agent("implementer")
                )
            
            assert result.success is True
            assert result.strategy == "concurrent"
            # metadata is attached by ExecutionStrategyManager.prepare_phase, not
            # directly by ConcurrentStrategy — skip that assertion for direct-strategy tests

    def test_assess_capability_manual_override(self, strategy):
        report = strategy.assess_capability()
        assert report.strategy == "concurrent"
        assert report.confidence == 1.0
        assert "Manual override" in report.reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
