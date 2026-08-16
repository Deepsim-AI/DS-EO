"""
Execution Strategy Manager — Package Entry Point.

Phase A deliverable 7 of TASK_DS_EO_043 + Phase B additions (TASK_DS_EO_044).

Exports the public API for the execution strategy subsystem:
- ExecutionStrategy (ABC base class)
- StrategyResult, CapabilityReport (data classes)
- ConcurrentStrategy, SequentialStrategy, SharedModelStrategy
- CapabilityAssessor, ExecutionStrategySelector
- ExecutionStrategyManager (public facade used by engine.py)
"""

import asyncio
import logging
import os

from .constants import Strategy, ModelState, ModelStateError
from .strategy_base import ExecutionStrategy, StrategyResult, CapabilityReport
from .concurrent_strategy import ConcurrentStrategy
from .sequential_strategy import SequentialStrategy
from .shared_model_strategy import SharedModelStrategy, clear_shared_model_state
from .capability_assessor import CapabilityAssessor
from .selector import ExecutionStrategySelector

logger = logging.getLogger(__name__)


class ExecutionStrategyManager:
    """
    Public facade: wraps selector + strategy instance. Used by engine.py.

    Singleton per DS-EO process lifetime. Provides prepare_phase / release_phase
    hooks that engine.py calls at phase boundaries.
    """

    _instance = None

    def __new__(cls, workspace_root=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._pending_workspace_root = workspace_root
        return cls._instance

    def __init__(self, workspace_root: str = None):
        """Initialize the manager. Safe to call multiple times — idempotent."""
        if self._initialized:
            return

        if workspace_root is None and hasattr(self, '_pending_workspace_root'):
            workspace_root = self._pending_workspace_root

        if workspace_root is None:
            workspace_root = os.environ.get("DS_EO_WORKSPACE", os.getcwd())

        self.workspace_root = os.path.abspath(workspace_root)
        self.selector = ExecutionStrategySelector(workspace_root=self.workspace_root)
        self._initialized = True

    async def prepare_phase(self, agent_id: str) -> StrategyResult:
        """
        Called BEFORE spawning an agent session.

        Resolves the active strategy, prepares the model/environment,
        and returns a StrategyResult with model status metadata.
        """
        strategy_name, strategy_impl, report = self.selector.get_or_resolve()

        logger.info(
            f"Execution mode: {strategy_name} (source: {self.selector.selection_source})"
        )

        result = await strategy_impl.prepare_for_agent(agent_id)

        # Attach metadata for logging
        result.metadata = {
            "strategy": strategy_name,
            "source": self.selector.selection_source,
            "confidence": report.confidence,
        }
        return result

    async def release_phase(self, agent_id: str) -> StrategyResult:
        """
        Called AFTER an agent session completes.

        Releases model resources as appropriate for the active strategy.
        """
        _, strategy_impl, _ = self.selector.get_or_resolve()
        return await strategy_impl.release_agent(agent_id)

    async def switch_strategy(self, strategy_name: str):
        """
        Allow user-initiated mode change at runtime.

        Persists the override and logs the change.
        """
        self.selector.set_manual_override(strategy_name)
        logger.info(f"Strategy switched to {strategy_name} by user")

        # Clear any shared model state when switching away.
        if strategy_name != Strategy.SHARED_MODEL.value:
            clear_shared_model_state()

    def status_report(self) -> dict:
        """
        Return current strategy state for logging/status.

        Used by PM dashboard and status reporting.
        """
        name, impl, report = self.selector.get_or_resolve()

        lifecycle_status = {"status": "N/A (strategy does not manage individual models)"}
        if hasattr(impl, 'get_current_strategy_report'):
            try:
                lifecycle_status = impl.get_current_strategy_report()
            except Exception as e:
                logger.debug(f"Could not get lifecycle report: {e}")

        return {
            "active_strategy": name,
            "source": self.selector.selection_source,
            "capability_report": {
                "confidence": report.confidence,
                "reason": report.reason,
                "signals": report.signals,
            },
            "lifecycle_state": lifecycle_status,
        }


__all__ = [
    "ExecutionStrategy",
    "StrategyResult",
    "CapabilityReport",
    "ConcurrentStrategy",
    "SequentialStrategy",
    "SharedModelStrategy",
    "clear_shared_model_state",
    "CapabilityAssessor",
    "ExecutionStrategySelector",
    "ExecutionStrategyManager",
    "Strategy",
    "ModelState",
    "ModelStateError",
]
