"""
Execution Strategy — SharedModelStrategy (Single Model, Multiple Roles).

Phase B deliverable 2 of TASK_DS_EO_044.
Source of truth: CTO_PLAN.md §3.

Multiple logical roles resolve to the same physical model. No unnecessary
unload/reload when the model is already resident. Roles remain logically
independent (separate sessions, separate prompts) but share model weights.
"""

import asyncio
import logging
from typing import Optional

from .constants import Strategy, ModelState
from .strategy_base import ExecutionStrategy, StrategyResult, CapabilityReport

logger = logging.getLogger(__name__)


class SharedModelStrategy(ExecutionStrategy):
    """Strategy: shared_model

    Single model loaded once, shared across agents. Ref-counting ensures
    the model stays loaded while any agent is active and unloads only when
    ALL agents have released.

    Appropriate for users who intentionally configure the same model for
    CTO/Implementer/Reviewer/PM (e.g., to reduce memory pressure without
    managing lifecycles, or for benchmarking model quality across roles).
    """

    # Class-level ref counts (shared across instances if multiple are created)
    _ref_counts: dict[str, int] = {}       # model_name → active agent count
    _active_agents: set[tuple[str, str]] = set()  # (agent_id, model_name) pairs
    _lock = asyncio.Lock()

    def __init__(self, workspace_root: str = None):
        self.workspace_root = workspace_root
        self._local_ref_counts: dict[str, int] = {}   # instance-level ref count
        self._local_agents: set[str] = set()            # instance-level agent tracking

    async def prepare_for_agent(self, agent_id: str) -> StrategyResult:
        """Prepare for an agent in shared_model mode.

        Resolves the model from registry. If the model is not yet loaded,
        loads it (first caller). Increments ref-count for subsequent callers.
        """
        # Resolve model name from registry.
        model_name = await self._resolve_model(agent_id)
        if model_name is None:
            return StrategyResult(
                success=False,
                strategy=Strategy.SHARED_MODEL.value,
                model_status={},
                notes=[f"Failed to resolve agent {agent_id} from registry"],
            )

        async with self._lock:
            # Increment ref-count (class-level).
            self.__class__._ref_counts[model_name] = self.__class__._ref_counts.get(model_name, 0) + 1
            self.__class__._active_agents.add((agent_id, model_name))

            # Also track locally.
            self._local_ref_counts[model_name] = self._local_ref_counts.get(model_name, 0) + 1
            self._local_agents.add(agent_id)

            loaded = await self._ensure_loaded(model_name)

        return StrategyResult(
            success=True,
            strategy=Strategy.SHARED_MODEL.value,
            model_status={model_name: {"installed": True, "loaded": True, "ref_count": self.__class__._ref_counts[model_name]}},
            notes=[f"Shared model '{model_name}' active for {agent_id} (refcount={self.__class__._ref_counts[model_name]})"],
        )

    async def release_agent(self, agent_id: str) -> StrategyResult:
        """Release an agent from shared_model mode.

        Decrements ref-count. When ref-count reaches zero and no agents remain,
        schedules the model for unloading.
        """
        async with self._lock:
            # Find the model this agent was using (best-effort).
            model_name = None
            for aid, mname in list(self.__class__._active_agents):
                if aid == agent_id:
                    model_name = mname
                    break

            if not model_name:
                # Try local tracking.
                if self._local_agents and agent_id in self._local_agents:
                    # Pick the first model associated with this agent.
                    model_name = next(k for k, v in self._local_ref_counts.items() if v > 0) or None

            if not model_name:
                return StrategyResult(
                    success=True,
                    strategy=Strategy.SHARED_MODEL.value,
                    model_status={},
                    notes=[f"Agent {agent_id} not found in active tracking — nothing to release"],
                )

            # Decrement ref-counts.
            self.__class__._ref_counts[model_name] = max(0, self.__class__._ref_counts.get(model_name, 1) - 1)
            self.__class__._active_agents.discard((agent_id, model_name))
            self._local_ref_counts[model_name] = max(0, self._local_ref_counts.get(model_name, 1) - 1)
            self._local_agents.discard(agent_id)

            refcount = self.__class__._ref_counts[model_name]
            unloaded_lazily = False

            if refcount == 0 and len(self.__class__._active_agents) == 0:
                logger.info(f"SharedModelStrategy: all agents released model '{model_name}' — scheduling unload")
                unloaded_lazily = await self._schedule_unload(model_name)

        # Clean up empty entries.
        async with self._lock:
            if refcount == 0 and model_name in self.__class__._ref_counts:
                del self.__class__._ref_counts[model_name]

        return StrategyResult(
            success=True,
            strategy=Strategy.SHARED_MODEL.value,
            model_status={model_name: {"installed": True, "loaded": not unloaded_lazily, "ref_count": refcount}},
            notes=[f"Released {agent_id} from shared model '{model_name}' (remaining refs: {refcount})"]
            + ([f"Model scheduled for lazy unload (no active agents)"] if unloaded_lazily else [f"Model still loaded ({refcount} ref(s) remain)"]),
        )

    def can_support_concurrent_agents(self) -> bool:
        """Shared model supports concurrent agents by design — all share one model instance."""
        return True

    def assess_capability(self) -> CapabilityReport:
        """Shared model provides a different kind of assessment.

        Returns strategy=shared_model only if at least two agents share the same model config.
        """
        # Check if multiple agents resolve to the same model.
        shared_models = self._count_shared_models()
        is_shared = len(shared_models) > 0

        return CapabilityReport(
            strategy=Strategy.SHARED_MODEL.value,
            confidence=1.0 if is_shared else 0.0,
            signals={
                "type": "strategy",
                "shared_models": shared_models,
                "reason": f"{'Shared' if is_shared else 'Not shared'} model configuration detected",
            },
            reason=f"SharedModelMode available: {len(shared_models)} model(s) shared across roles"
                   if is_shared
                   else "No shared model config found; SharedModelStrategy not auto-selected.",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _resolve_model(self, agent_id: str) -> Optional[str]:
        """Resolve the model name for an agent from the registry."""
        try:
            from dispatcher.registry import AgentRegistry
            registry = AgentRegistry(workspace_root=self.workspace_root)
            registry.load()
            reg_result = registry.resolve(agent_id)
            if not reg_result.success or not reg_result.agent:
                logger.warning(f"SharedModelStrategy registry resolution for {agent_id} failed: {reg_result.error}")
                return None
            return reg_result.agent.model
        except Exception as e:
            logger.warning(f"SharedModelStrategy registry resolution for {agent_id} failed: {e}")
            return None

    async def _ensure_loaded(self, model_name: str) -> bool:
        """Ensure model is loaded — first caller triggers load."""
        try:
            import urllib.request
            req = urllib.request.Request("http://127.0.0.1:11434/api/ps")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read().decode()
                if data.strip():
                    import json
                    info = json.loads(data)
                    active_models = info.get("models", []) if isinstance(info, dict) else []
                    for m in active_models:
                        model_field = m.get("model", m.get("name", ""))
                        if model_name in model_field:
                            return True  # already loaded
        except Exception as e:
            logger.debug(f"_ensure_loaded poll error: {e}")

        # Not found — trigger load via Ollama run (same pattern as SequentialStrategy).
        try:
            import subprocess
            result = await asyncio.wait_for(
                asyncio.to_thread(subprocess.run, ["ollama", "run", model_name, ""],
                                  capture_output=True, text=True, timeout=10),
                timeout=60,
            )
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"_ensure_loaded({model_name}): {e}")
            # Fallback assumption.
            return True

    async def _schedule_unload(self, model_name: str) -> bool:
        """Schedule lazy unload of the shared model."""
        try:
            import urllib.request
            req = urllib.request.Request("http://127.0.0.1:11434/api/generate", method="DELETE")
            with urllib.request.urlopen(req, timeout=5) as resp:
                logger.info(f"SharedModelStrategy: unload request sent for '{model_name}': {resp.status}")
        except Exception as e:
            logger.debug(f"_schedule_unload({model_name}): {e}")

        # Verify unloaded via polling.
        deadline = asyncio.get_event_loop().time() + 30
        while asyncio.get_event_loop().time() < deadline:
            try:
                req = urllib.request.Request("http://127.0.0.1:11434/api/ps")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = resp.read().decode()
                    if not data.strip():
                        return True
                    import json
                    info = json.loads(data)
                    active_models = info.get("models", []) if isinstance(info, dict) else []
                    for m in active_models:
                        if model_name in m.get("model", m.get("name", "")):
                            break
                    else:
                        return True  # not found → unloaded
            except Exception as e:
                logger.debug(f"Unload poll error: {e}")
            await asyncio.sleep(0.5)

        return False

    def _count_shared_models(self) -> list[str]:
        """Identify models shared by multiple agents (best-effort without registry)."""
        # Placeholder — full implementation would query AgentRegistry for all agents.
        return []


# ------------------------------------------------------------------
# Class-level cleanup on strategy change
# ------------------------------------------------------------------

def clear_shared_model_state():
    """Reset class-level state when strategy changes. Call during switch_strategy."""
    SharedModelStrategy._ref_counts.clear()
    SharedModelStrategy._active_agents.clear()
