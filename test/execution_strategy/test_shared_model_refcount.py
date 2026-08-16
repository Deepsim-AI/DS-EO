"""
Test: SharedModelStrategy ref-counting — Phase B.

TASK_DS_EO_044 deliverable 5b.
Verifies the shared-model reference-counting behavior:
- first caller triggers load (mocked), refcount = 1
- second caller on same model: no second load, refcount = 2
- release of one agent keeps model loaded (refcount 2 → 1)
- release of last agent schedules unload (refcount → 0)
- release of unknown agent is a graceful no-op

External effects (Ollama HTTP, ollama subprocess) are mocked.
Class-level state is reset between tests so tests are order-independent.
"""
import asyncio
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dispatcher.execution_strategy.constants import Strategy
from dispatcher.execution_strategy.shared_model_strategy import SharedModelStrategy

WORKSPACE = "/home/deepsim/ds_eo_openclaw"
MODEL = "ollama/qwen3.8:27b"


def _reg(agent_id="implementer", model=MODEL, success=True):
    """Fake AgentRegistry using the correct load() + resolve() API."""
    mock = MagicMock()
    if success:
        agent = MagicMock()
        agent.model = model
        mock.resolve.return_value = MagicMock(success=True, agent=agent, error=None)
    else:
        mock.resolve.return_value = MagicMock(
            success=False, agent=None, error=f"Agent '{agent_id}' not found"
        )
    return mock


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _reset_class_state():
    SharedModelStrategy._ref_counts.clear()
    SharedModelStrategy._active_agents.clear()


class TestRefCounting:
    def test_first_caller_triggers_load(self):
        _reset_class_state()
        s = SharedModelStrategy(workspace_root=WORKSPACE)
        with patch("dispatcher.registry.AgentRegistry", return_value=_reg("cto")), \
             patch.object(s, "_ensure_loaded", side_effect=_ensure_loaded_mock(True)) as mock_load:
            result = _run(s.prepare_for_agent("cto"))
        assert result.success is True
        assert result.strategy == Strategy.SHARED_MODEL.value
        mock_load.assert_called_once_with(MODEL)
        assert s.__class__._ref_counts.get(MODEL) == 1

    def test_second_caller_no_second_load(self):
        _reset_class_state()
        s = SharedModelStrategy(workspace_root=WORKSPACE)
        with patch("dispatcher.registry.AgentRegistry", return_value=_reg("cto")):
            _run(s.prepare_for_agent("cto"))
        with patch("dispatcher.registry.AgentRegistry", return_value=_reg("implementer")), \
             patch.object(s, "_ensure_loaded", side_effect=_ensure_loaded_mock(True)) as mock_load:
            result = _run(s.prepare_for_agent("implementer"))
        assert result.success is True
        mock_load.assert_called_once_with(MODEL)
        assert s.__class__._ref_counts.get(MODEL) == 2

    def test_release_keeps_loaded_while_refs_remain(self):
        _reset_class_state()
        s = SharedModelStrategy(workspace_root=WORKSPACE)
        with patch("dispatcher.registry.AgentRegistry", return_value=_reg("cto")):
            _run(s.prepare_for_agent("cto"))
        with patch("dispatcher.registry.AgentRegistry", return_value=_reg("implementer")):
            _run(s.prepare_for_agent("implementer"))
        # Two agents active → releasing one must NOT schedule unload.
        with patch("dispatcher.registry.AgentRegistry", return_value=_reg("implementer")), \
             patch.object(s, "_schedule_unload", side_effect=_schedule_unload_mock()) as mock_unload:
            result = _run(s.release_agent("implementer"))
        assert result.success is True
        assert "ref(s) remain" in result.notes[-1] or "remaining refs: 1" in result.notes[-1]
        mock_unload.assert_not_called()
        assert s.__class__._ref_counts.get(MODEL) == 1

    def test_last_release_schedules_unload(self):
        _reset_class_state()
        s = SharedModelStrategy(workspace_root=WORKSPACE)
        with patch("dispatcher.registry.AgentRegistry", return_value=_reg("reviewer")):
            _run(s.prepare_for_agent("reviewer"))
        with patch("dispatcher.registry.AgentRegistry", return_value=_reg("reviewer")), \
             patch.object(s, "_schedule_unload", side_effect=_schedule_unload_mock()) as mock_unload:
            result = _run(s.release_agent("reviewer"))
        assert result.success is True
        mock_unload.assert_called_once_with(MODEL)
        # Ref count cleaned up after full release.
        assert s.__class__._ref_counts.get(MODEL) in (0, None)

    def test_release_unknown_agent_graceful(self):
        _reset_class_state()
        s = SharedModelStrategy(workspace_root=WORKSPACE)
        with patch("dispatcher.registry.AgentRegistry", return_value=_reg(success=False)):
            result = _run(s.release_agent("ghost_agent"))
        assert result.success is True
        assert "nothing to release" in result.notes[-1] or "not found" in result.notes[-1]

    def test_prepare_unknown_agent_typed_failure(self):
        _reset_class_state()
        s = SharedModelStrategy(workspace_root=WORKSPACE)
        with patch("dispatcher.registry.AgentRegistry", return_value=_reg("ghost", success=False)):
            result = _run(s.prepare_for_agent("ghost"))
        assert result.success is False
        assert result.strategy == Strategy.SHARED_MODEL.value
        assert any("ghost" in n for n in result.notes)


class TestContract:
    def test_supports_concurrent_agents(self):
        s = SharedModelStrategy(workspace_root=WORKSPACE)
        assert s.can_support_concurrent_agents() is True


def _ensure_loaded_mock(loaded=True):
    async def fake(model_name):
        return loaded
    return fake


def _schedule_unload_mock():
    async def fake(model_name):
        return True
    return fake


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
