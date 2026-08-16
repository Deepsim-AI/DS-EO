"""
Test: ExecutionStrategySelector override persistence and resolution.

Phase A deliverable 8 of TASK_DS_EO_043.
"""
import pytest
import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dispatcher.execution_strategy.selector import ExecutionStrategySelector
from dispatcher.execution_strategy.constants import Strategy, SELECTION_SOURCE_AUTO, SELECTION_SOURCE_USER_OVERRIDE


@pytest.fixture
def override_path(tmp_path):
    """Create a temporary override file path."""
    p = str(tmp_path / "test_override.json")
    return p


@pytest.fixture
def selector(override_path):
    """Fresh selector with isolated override path."""
    # Clear singleton state
    ExecutionStrategySelector._instance = None
    s = ExecutionStrategySelector(workspace_root="/home/deepsim/ds_eo_openclaw")
    s._override_path = override_path
    return s


class TestSelectorOverridePersistence:
    """Test that manual overrides persist to disk and clear correctly."""

    def test_set_override_persists_to_file(self, selector, override_path):
        selector.set_manual_override("sequential")
        
        assert os.path.exists(override_path)
        with open(override_path) as f:
            data = json.load(f)
        assert data["strategy"] == "sequential"
        assert data["source"] == SELECTION_SOURCE_USER_OVERRIDE

    def test_get_or_resolve_uses_override(self, selector):
        selector.set_manual_override("sequential")
        name, impl, report = selector.get_or_resolve()
        
        assert name == "sequential"
        # The reason should indicate user override
        assert "override" in report.reason.lower() or "user" in report.reason.lower()

    def test_clear_override_removes_file(self, selector, override_path):
        selector.set_manual_override("sequential")
        assert os.path.exists(override_path)
        
        selector.clear_override()
        assert not os.path.exists(override_path)
        # After clear, it should resolve to auto-detection.
        # TASK_DS_EO_044 (Phase B) ships sequential + shared_model, so the
        # Phase A assumption ("sequential unavailable -> concurrent fallback")
        # no longer holds. Verify auto-resolution lands on a real strategy.
        name, impl, report = selector.get_or_resolve()
        assert name in ["concurrent", "sequential", "shared_model"]
        assert report.strategy == name

    def test_set_manual_override_rejects_invalid(self, selector):
        with pytest.raises(ValueError):
            selector.set_manual_override("nonexistent_strategy")

    def test_override_survives_getter_calls(self, selector):
        """Multiple get_or_resolve calls should not change override."""
        selector.set_manual_override("sequential")
        
        name1, _, _ = selector.get_or_resolve()
        selector.set_manual_override("concurrent")  # change it
        name2, _, _ = selector.get_or_resolve()
        
        assert name1 == "sequential"
        assert name2 == "concurrent"

    def test_clear_and_revert(self, selector):
        """Clear override should re-run auto-detection."""
        with patch.object(ExecutionStrategySelector, '_resolve') as mock_resolve:
            mock_resolve.side_effect = [None, None]  # called once on set, once on clear
            selector.set_manual_override("sequential")
            mock_resolve.reset_mock()
            
            selector.clear_override()
            
            # Should call _resolve (auto-detection) to pick a new strategy
            assert mock_resolve.call_count >= 1

    def test_property_access_resolves(self, selector):
        """current_strategy_name and selection_source should auto-resolve if needed."""
        name = selector.current_strategy_name
        source = selector.selection_source
        
        # Should have resolved (either to override or auto)
        assert name in ["concurrent", "sequential"]
        assert source in [SELECTION_SOURCE_AUTO, SELECTION_SOURCE_USER_OVERRIDE]


class TestSelectorSingleton:
    """Test that ExecutionStrategySelector behaves as a singleton."""

    def test_singleton_across_instances(self):
        # Clear previous singleton
        ExecutionStrategySelector._instance = None
        
        s1 = ExecutionStrategySelector(workspace_root="/tmp/test")
        s2 = ExecutionStrategySelector(workspace_root="/tmp/other")
        
        assert s1 is s2  # Same instance

    def test_strategy_available_classmethod(self):
        concurrent_exists = ExecutionStrategySelector.strategy_available("ConcurrentStrategy")
        # TASK_DS_EO_044 (Phase B) shipped sequential + shared_model strategies,
        # so both must report available now (Phase A test predates that).
        sequential_exists = ExecutionStrategySelector.strategy_available("SequentialStrategy")
        
        assert concurrent_exists is True
        assert sequential_exists is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
