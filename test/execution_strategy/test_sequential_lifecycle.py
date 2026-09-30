"""
Test: SequentialStrategy (ModelLifecycleManager) — Phase B.

TASK_DS_EO_044 deliverable 5a.
Verifies the sequential model lifecycle state machine:
- prepare/release happy path
- already-resident optimization (no redundant load)
- registry resolution failure (typed failure, no exception)
- strategy contract (can_support_concurrent_agents == False)
- get_current_strategy_report shape

External effects (ollama subprocess, /api/ps) are mocked.
"""
import asyncio
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dispatcher.execution_strategy.strategy_base import StrategyResult, CapabilityReport
from dispatcher.execution_strategy.constants import Strategy
from dispatcher.execution_strategy.sequential_strategy import (
    SequentialStrategy, _ModelLifecycleManager,
)

WORKSPACE = "/home/deepsim/ds_eo_openclaw"


def _reg(agent_id="implementer", model="ollama/qwen3.8:27b", success=True):
    """Build a fake AgentRegistry with load() + resolve() (the correct API)."""
    mock = MagicMock()
    if success:
        agent = MagicMock()
        agent.model = model
        mock.resolve.return_value = MagicMock(
            success=True, agent=agent, error=None
        )
    else:
        mock.resolve.return_value = MagicMock(
            success=False, agent=None, error=f"Agent '{agent_id}' not found"
        )
    return mock


_test_loop = None

def _run(coro):
    global _test_loop
    if _test_loop is None or _test_loop.is_closed():
        _test_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_test_loop)
    return _test_loop.run_until_complete(coro)


class TestRegistryResolution:
    """_resolve_model must use load() then resolve() (Phase B bugfix)."""

    def test_resolves_model_via_registry(self):
        s = SequentialStrategy(workspace_root=WORKSPACE)
        fake_reg = _reg()
        with patch("dispatcher.registry.AgentRegistry", return_value=fake_reg):
            assert s._resolve_model("implementer") == "ollama/qwen3.8:27b"
        fake_reg.resolve.assert_called_once_with("implementer")

    def test_unknown_agent_returns_none_not_exception(self):
        s = SequentialStrategy(workspace_root=WORKSPACE)
        fake_reg = _reg(success=False)
        with patch("dispatcher.registry.AgentRegistry", return_value=fake_reg):
            assert s._resolve_model("nonexistent") is None

    def test_registry_import_failure_returns_none(self):
        s = SequentialStrategy(workspace_root=WORKSPACE)
        with patch("dispatcher.registry.AgentRegistry",
                   side_effect=ImportError("no module")):
            assert s._resolve_model("implementer") is None


class TestPrepareRelease:
    def test_prepare_unknown_agent_fails_typed(self):
        s = SequentialStrategy(workspace_root=WORKSPACE)
        fake_reg = _reg(success=False)
        with patch("dispatcher.registry.AgentRegistry", return_value=fake_reg):
            result = _run(s.prepare_for_agent("ghost_agent"))
        assert isinstance(result, StrategyResult)
        assert result.success is False
        assert result.strategy == Strategy.SEQUENTIAL.value
        assert any("ghost_agent" in n for n in result.notes)

    def test_release_unknown_agent_is_graceful(self):
        s = SequentialStrategy(workspace_root=WORKSPACE)
        fake_reg = _reg(success=False)
        with patch("dispatcher.registry.AgentRegistry", return_value=fake_reg):
            result = _run(s.release_agent("ghost_agent"))
        # Nothing loaded → graceful no-op success (no exception)
        assert isinstance(result, StrategyResult)
        assert result.success is True

    def test_full_lifecycle_with_mocked_lifecycle_ops(self):
        """prepare → release happy path; verify state transitions through 'executing'."""
        s = SequentialStrategy(workspace_root=WORKSPACE)
        fake_reg = _reg()

        lifecycle = s._lifecycle

        async def fake_ensure_ready(model_name):
            # Mirror real _do_load state bookkeeping so strategy-level
            # assertions (state, model_status) exercise real code paths.
            async with lifecycle._lock:
                lifecycle._state = "ready"
                lifecycle._current_model = model_name
                if model_name not in lifecycle._model_status:
                    lifecycle._model_status[model_name] = {
                        "installed": True, "loaded": True, "executing": False,
                    }
            return StrategyResult(
                success=True, strategy="sequential", model_status={
                    model_name: {"installed": True, "loaded": True, "executing": False}
                }, notes=["mock load ok"],
            )

        async def fake_release(model_name):
            async with lifecycle._lock:
                lifecycle._state = "idle"
                lifecycle._current_model = None
                if model_name in lifecycle._model_status:
                    lifecycle._model_status[model_name]["loaded"] = False
                    lifecycle._model_status[model_name]["executing"] = False
            return StrategyResult(
                success=True, strategy="sequential", model_status={
                    model_name: {"installed": True, "loaded": False, "executing": False}
                }, notes=["mock unload ok"],
            )

        with patch("dispatcher.registry.AgentRegistry", return_value=fake_reg), \
             patch.object(lifecycle, "ensure_ready", side_effect=fake_ensure_ready), \
             patch.object(lifecycle, "release_model", side_effect=fake_release):
            prep = _run(s.prepare_for_agent("implementer"))
            assert prep.success is True
            assert lifecycle.state == "executing"
            assert lifecycle.model_status["ollama/qwen3.8:27b"]["executing"] is True

            rel = _run(s.release_agent("implementer"))
            assert rel.success is True
            assert lifecycle.state == "idle"


class TestAlreadyResident:
    def test_ensure_ready_short_circuits_when_resident(self):
        m = _ModelLifecycleManager(workspace_root=WORKSPACE)
        m._state = "ready"
        m._current_model = "ollama/qwen3.8:27b"
        m._model_status["ollama/qwen3.8:27b"] = {
            "installed": True, "loaded": True, "executing": False,
        }

        result = _run(m.ensure_ready("ollama/qwen3.8:27b"))
        assert result.success is True
        assert any("already resident" in n for n in result.notes)
        # State unchanged — no load attempt triggered.
        assert m.state == "ready"

    def test_ensure_ready_refuses_while_unloading(self):
        m = _ModelLifecycleManager(workspace_root=WORKSPACE)
        m._state = "unloading"
        m._current_model = "ollama/qwen3.8:27b"

        result = _run(m.ensure_ready("ollama/laguna-xs-2.1:q4_K_M"))
        assert result.success is False
        assert any("unloading" in n.lower() for n in result.notes)

    def test_release_noop_when_not_executing(self):
        m = _ModelLifecycleManager(workspace_root=WORKSPACE)
        m._state = "idle"
        m._current_model = None

        result = _run(m.release_model("ollama/qwen3.8:27b"))
        assert result.success is True
        assert m.state == "idle"


class TestContractAndReport:
    def test_no_concurrent_agents(self):
        s = SequentialStrategy(workspace_root=WORKSPACE)
        assert s.can_support_concurrent_agents() is False

    def test_assess_capability_always_available(self):
        s = SequentialStrategy(workspace_root=WORKSPACE)
        report = s.assess_capability()
        assert isinstance(report, CapabilityReport)
        assert report.strategy == Strategy.SEQUENTIAL.value
        assert report.confidence == 1.0

    def test_get_current_strategy_report_shape(self):
        s = SequentialStrategy(workspace_root=WORKSPACE)
        report = s.get_current_strategy_report()
        assert report["state"] == "idle"
        assert report["current_model"] is None
        assert report["model_status"] == {}


class TestUnloadFailureRecovery:
    def test_failed_release_enters_error_state(self):
        m = _ModelLifecycleManager(workspace_root=WORKSPACE)
        m._state = "executing"
        m._current_model = "ollama/qwen3.8:27b"
        m._model_status["ollama/qwen3.8:27b"] = {
            "installed": True, "loaded": True, "executing": True,
        }

        async def failing_unload(name):
            return False  # eviction timeout

        with patch.object(m, "_unload_model_by_name", side_effect=failing_unload):
            result = _run(m.release_model("ollama/qwen3.8:27b"))

        assert result.success is False
        assert m.state == "error"

        # Error recovery: reset_state returns to idle.
        m.reset_state()
        assert m.state == "idle"
        assert m.current_model is None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
