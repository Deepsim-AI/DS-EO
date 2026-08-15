"""
Execution Strategy — ConcurrentStrategy (Identity Wrap).

Phase A deliverable 4 of TASK_DS_EO_043.
Source of truth: CTO_PLAN.md §5.2.

Preserves existing spawn behavior exactly as-is. No behavioral change from
current DS-EO except the result has an extra `strategy: "concurrent"` field.
"""

import asyncio
import logging
from typing import Optional

from .constants import (
    Strategy,
    ModelState,
)
from .strategy_base import ExecutionStrategy, StrategyResult, CapabilityReport

logger = logging.getLogger(__name__)


class ConcurrentStrategy(ExecutionStrategy):
    """
    Strategy: concurrent
    
    No model lifecycle management. Spawns sessions via existing SessionSpawnManager
    exactly as before. Models remain loaded per their keep_alive configuration.
    
    This is the identity path — no behavioral change from current DS-EO.
    """

    def __init__(self, workspace_root: str = None):
        self.workspace_root = workspace_root
        # Lazy import to avoid circular dependency at module load time
        self._spawn_manager = None
    
    @property
    def spawn_manager(self):
        if self._spawn_manager is None and self.workspace_root:
            from dispatcher.session_spawn import SessionSpawnManager
            self._spawn_manager = SessionSpawnManager(
                workspace_root=self.workspace_root
            )
        return self._spawn_manager

    async def prepare_for_agent(self, agent_id: str) -> StrategyResult:
        """
        Prepare for an agent in concurrent mode.
        
        Resolves model from registry, calls existing spawn manager, returns StrategyResult.
        Zero behavioral change — just wraps the call with metadata tracking.
        """
        # Resolve agent → model from the AgentRegistry
        try:
            from dispatcher.registry import AgentRegistry
            registry = AgentRegistry(workspace_root=self.workspace_root)
            result = registry.load()
            if not result.success or not result.agent:
                return StrategyResult(
                    success=False,
                    strategy=Strategy.CONCURRENT.value,
                    model_status={},
                    notes=[f"Agent registry lookup failed for {agent_id}: {result.error}"],
                )
            agent_info = result.agent
            model_name = agent_info.model
        except Exception as e:
            logger.warning(f"Registry resolution for {agent_id} failed (non-fatal): {e}")
            model_name = "unknown"

        # No model lifecycle management needed — spawn directly via existing manager
        if self.spawn_manager:
            try:
                outcome = self.spawn_manager.spawn_agent(
                    task_id="",  # Phase-level, not task-level
                    agent_role=agent_id,
                    prompt_content=f"ConcurrentStrategy: prepare_phase for {agent_id}",
                    model_override=None,
                )
                return StrategyResult(
                    success=outcome.success,
                    strategy=Strategy.CONCURRENT.value,
                    model_status={model_name: {"installed": True, "loaded": True, "executing": False}},
                    notes=[f"Concurrent spawn prepared for {agent_id} (model: {model_name})"],
                )
            except Exception as e:
                logger.error(f"Spawn failed for agent {agent_id}: {e}")
                return StrategyResult(
                    success=False,
                    strategy=Strategy.CONCURRENT.value,
                    model_status={},
                    notes=[f"Spawn failed for agent {agent_id}: {e}"],
                )

        # Fallback if no spawn manager — report the model would be used
        logger.info(f"ConcurrentStrategy: prepare_for_agent({agent_id}) — model={model_name}, no spawn mgr")
        return StrategyResult(
            success=True,
            strategy=Strategy.CONCURRENT.value,
            model_status={model_name: {"installed": True, "loaded": False, "executing": False}},
            notes=[f"Model {model_name} would be used for agent {agent_id} (no spawn in this context)"],
        )

    async def release_agent(self, agent_id: str) -> StrategyResult:
        """No cleanup needed in concurrent mode — models stay loaded."""
        return StrategyResult(
            success=True,
            strategy=Strategy.CONCURRENT.value,
            model_status={},
            notes=[f"Released {agent_id} (concurrent mode — no unloading)"],
        )

    def can_support_concurrent_agents(self) -> bool:
        """Concurrent strategy supports concurrent spawning by definition."""
        return True

    def assess_capability(self) -> CapabilityReport:
        """Manual override to concurrent mode always reports full capability."""
        return CapabilityReport(
            strategy=Strategy.CONCURRENT.value,
            confidence=1.0,
            signals={"type": "strategy"},
            reason="Manual override to concurrent mode",
        )
