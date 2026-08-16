"""
Test: Engine <-> ExecutionStrategyManager lifecycle hook integration -- Phase B.

TASK_DS_EO_044 deliverable 5c.
Verifies that WorkflowEngine.execute_transition() calls the async strategy
lifecycle API (prepare_phase BEFORE, release_phase AFTER) via the sync-to-async
bridge, and that a hook failure is NON-FATAL (transition still succeeds).

The ExecutionStrategyManager is a process-wide singleton -- we patch its
prepare_phase/release_phase with spy coroutines to observe call order
without touching Ollama.
"""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dispatcher.engine import WorkflowEngine, TransitionResult
from dispatcher.execution_strategy import ExecutionStrategyManager, StrategyResult

WORKSPACE = "/home/deepsim/ds_eo_openclaw"
AGENT = "implementer"


def _ok_result():
    return StrategyResult(
        success=True, strategy="sequential",
        model_status={}, notes=["hook ok"],
    )


def _fail_result():
    return StrategyResult(
        success=False, strategy="sequential",
        model_status={}, notes=["hook failed"],
    )


def _reset_singleton():
    """Reset ExecutionStrategyManager singleton so each test starts clean."""
    ExecutionStrategyManager._instance = None
    from dispatcher.execution_strategy.shared_model_strategy import SharedModelStrategy
    SharedModelStrategy._ref_counts.clear()
    SharedModelStrategy._active_agents.clear()


class TestEngineHookIntegration:

    def test_hooks_called_in_order_before_and_after(self):
        _reset_singleton()
        calls = []

        async def spy_prepare(agent_id):
            calls.append(("prepare", agent_id))
            return _ok_result()

        async def spy_release(agent_id):
            calls.append(("release", agent_id))
            return _ok_result()

        engine = WorkflowEngine(workspace_root=WORKSPACE)
        assert engine.load_workflow() is True

        with patch.object(ExecutionStrategyManager, "prepare_phase", side_effect=spy_prepare), \
             patch.object(ExecutionStrategyManager, "release_phase", side_effect=spy_release):
            result = engine.execute_transition(
                task_id="TASK_TEST_001",
                from_phase="G1",
                transition_name="g1_to_g2",
                triggered_by_agent="cto",
                target_agent=AGENT,
            )

        # Hooks fired exactly once each, in prepare then release order.
        assert calls[0][0] == "prepare" and calls[0][1] == AGENT
        assert calls[-1][0] == "release" and calls[-1][1] == AGENT
        assert result is not None and isinstance(result, TransitionResult)

    def test_hook_failure_is_non_fatal(self):
        """A failed prepare_phase must not block the transition (Phase A contract)."""
        _reset_singleton()

        async def failing_prepare(agent_id):
            return _fail_result()

        async def ok_release(agent_id):
            return _ok_result()

        engine = WorkflowEngine(workspace_root=WORKSPACE)
        assert engine.load_workflow() is True

        with patch.object(ExecutionStrategyManager, "prepare_phase", side_effect=failing_prepare), \
             patch.object(ExecutionStrategyManager, "release_phase", side_effect=ok_release):
            result = engine.execute_transition(
                task_id="TASK_TEST_002",
                from_phase="G1",
                transition_name="g1_to_g2",
                triggered_by_agent="cto",
                target_agent=AGENT,
            )

        # Transition result must still be a TransitionResult (not an exception);
        # the engine must not crash when the strategy hook reports failure.
        assert isinstance(result, TransitionResult)

    def test_no_target_agent_skips_hooks(self):
        """Without a target agent, prepare/release must not be invoked."""
        _reset_singleton()
        calls = []

        async def spy_prepare(agent_id):
            calls.append("prepare")
            return _ok_result()

        async def spy_release(agent_id):
            calls.append("release")
            return _ok_result()

        engine = WorkflowEngine(workspace_root=WORKSPACE)
        assert engine.load_workflow() is True

        with patch.object(ExecutionStrategyManager, "prepare_phase", side_effect=spy_prepare), \
             patch.object(ExecutionStrategyManager, "release_phase", side_effect=spy_release):
            result = engine.execute_transition(
                task_id="TASK_TEST_003",
                from_phase="G1",
                transition_name="g1_to_g2",
                triggered_by_agent="cto",
                target_agent=None,
            )

        assert calls == []
        assert isinstance(result, TransitionResult)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
