"""
Execution Strategy — SequentialStrategy (ModelLifecycleManager).

Phase B deliverable 1 of TASK_DS_EO_044.
Source of truth: CTO_PLAN.md §2.

Only one model loaded at a time per agent phase. Uses explicit state machine
with readiness verification via Ollama /api/ps.
"""

import asyncio
import logging
import os
import subprocess
from typing import Optional

from .constants import Strategy, ModelState, ModelStateError
from .strategy_base import ExecutionStrategy, StrategyResult, CapabilityReport

logger = logging.getLogger(__name__)


# ============================================================================
# _ModelLifecycleManager — Internal state machine
# ============================================================================

class _ModelLifecycleManager:
    """Core state machine with mutex for sequential strategy.

    State transitions:
        idle → loading → ready → executing → unloading → idle
        Any state --(error)--> error (requires reset via ensure_ready)

    Model states tracked independently:
        installed — ollama show <model> succeeds
        loaded/resident — /api/ps lists model in active_models
        executing — an agent session is actively using this model

    Thread safety: all public methods acquire self._lock before mutating state.
    """

    def __init__(self, workspace_root: str = None):
        self.workspace_root = workspace_root or os.getcwd()
        self._state: str = "idle"          # idle/loading/ready/executing/unloading/error
        self._current_model: Optional[str] = None
        self._model_status: dict[str, dict] = {}  # model_name -> {installed, loaded, executing}
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        return self._state

    @property
    def current_model(self) -> Optional[str]:
        return self._current_model

    @property
    def model_status(self) -> dict[str, dict]:
        """Snapshot of all tracked model states."""
        return dict(self._model_status)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ensure_ready(self, model_name: str) -> StrategyResult:
        """Ensure target model is loaded and ready for use.

        If the requested model is already resident, returns success with
        'already resident' note (no redundant load).
        """
        async with self._lock:
            # Fast path: same model already loaded and ready
            if self._current_model == model_name and self._state in ("ready", "executing"):
                return StrategyResult(
                    success=True,
                    strategy=Strategy.SEQUENTIAL.value,
                    model_status=self.model_status,
                    notes=[f"Model '{model_name}' already resident (state: {self._state})"],
                )

            # Already unloading? Wait for completion.
            if self._state == "unloading":
                logger.warning(
                    f"ensure_ready({model_name}): unloading in progress, "
                    f"will be available after current phase completes."
                )
                return StrategyResult(
                    success=False,
                    strategy=Strategy.SEQUENTIAL.value,
                    model_status={},
                    notes=["Currently unloading previous model — retry after release_phase"],
                )

            # If a different model is loaded, unload it first.
            if self._current_model and self._current_model != model_name:
                unloaded = await self._unload_current_model()
                if not unloaded:
                    logger.warning(f"Failed to unload previous model '{self._current_model}'; proceeding anyway")

        # Now acquire lock again for the load phase.
        async with self._lock:
            return await self._do_load(model_name)

    async def release_model(self, model_name: str) -> StrategyResult:
        """Mark model as not executing and schedule async unload."""
        async with self._lock:
            if self._state != "executing" or self._current_model != model_name:
                # Model not currently executing — nothing to do.
                return StrategyResult(
                    success=True,
                    strategy=Strategy.SEQUENTIAL.value,
                    model_status=self.model_status,
                    notes=[f"Model '{model_name}' not in executing state (state: {self._state})"],
                )

            self._state = "unloading"
            logger.info(f"SequentialStrategy: unloading model '{model_name}'")

        # Release lock during unload (it's a blocking operation).
        unloaded = await self._unload_model_by_name(model_name)

        async with self._lock:
            if unloaded:
                self._state = "idle"
                was_current = self._current_model
                self._current_model = None
                # Update status tracking
                if model_name in self._model_status:
                    self._model_status[model_name]["loaded"] = False
                    self._model_status[model_name]["executing"] = False
            else:
                logger.warning(
                    f"release_model({model_name}): unload timed out, "
                    f"model may still be resident. Will clean up on next ensure_ready."
                )
                # Leave in error state so next ensure_ready handles cleanup
                self._state = "error"

        return StrategyResult(
            success=unloaded,
            strategy=Strategy.SEQUENTIAL.value,
            model_status=self.model_status if unloaded else {model_name: {"loaded": False}},
            notes=[f"Model '{model_name}' {'unloaded' if unloaded else 'unload delayed (warning logged)'}"]
            + ([f"Previous state: executing, current state: {self._state}"] if not unloaded else []),
        )

    # ------------------------------------------------------------------
    # Internal operations (must hold _lock for mutators)
    # ------------------------------------------------------------------

    async def _do_load(self, model_name: str) -> StrategyResult:
        """Load the model after ensuring it's installed."""
        self._state = "loading"
        self._current_model = model_name

        # Check if already in model_status tracking
        if model_name not in self._model_status:
            self._model_status[model_name] = {"installed": False, "loaded": False, "executing": False}

        # Verify installed (ollama show)
        installed = await self._check_installed(model_name)
        self._model_status[model_name]["installed"] = installed

        if not installed:
            self._state = "error"
            self._current_model = None
            return StrategyResult(
                success=False,
                strategy=Strategy.SEQUENTIAL.value,
                model_status={},
                notes=[f"Model '{model_name}' is not installed (ollama show failed)"],
            )

        # Trigger load via Ollama API.
        loaded = await self._trigger_load(model_name)
        if not loaded:
            self._state = "error"
            self._current_model = None
            return StrategyResult(
                success=False,
                strategy=Strategy.SEQUENTIAL.value,
                model_status={},
                notes=[f"Failed to load model '{model_name}' via Ollama API"],
            )

        # Wait for /api/ps to confirm.
        verified = await self._verify_loaded(model_name)
        if not verified:
            self._state = "error"
            logger.error(f"_do_load({model_name}): model loaded but /api/ps verification failed (timeout)")
            return StrategyResult(
                success=False,
                strategy=Strategy.SEQUENTIAL.value,
                model_status={},
                notes=[f"Model '{model_name}' loaded per API but not visible in /api/ps within 30s"],
            )

        self._state = "ready"
        self._model_status[model_name]["loaded"] = True
        logger.info(f"_do_load: model '{model_name}' ready (state={self._state})")
        return StrategyResult(
            success=True,
            strategy=Strategy.SEQUENTIAL.value,
            model_status=self.model_status,
            notes=[f"Model '{model_name}' loaded and verified via /api/ps"],
        )

    async def _check_installed(self, model_name: str) -> bool:
        """Verify model exists on disk via 'ollama show'."""
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(subprocess.run, ["ollama", "show", model_name],
                                  capture_output=True, text=True, timeout=10),
                timeout=15,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, Exception) as e:
            logger.debug(f"_check_installed({model_name}): {e}")
            return False

    async def _trigger_load(self, model_name: str) -> bool:
        """Trigger Ollama to load the model (pull+load if needed)."""
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(subprocess.run, ["ollama", "run", model_name, ""],
                                  capture_output=True, text=True, timeout=10),
                timeout=60,
            )
            # ollama run exits immediately with empty stdin; return code 0 means success
            return result.returncode == 0
        except (subprocess.TimeoutExpired, Exception) as e:
            logger.debug(f"_trigger_load({model_name}): {e}")
            # Fallback: just assume loaded — Ollama auto-pulls on first inference
            logger.info(f"_trigger_load: fallback assuming '{model_name}' will load on use")
            return True

    async def _verify_loaded(self, model_name: str, timeout_s: int = 30) -> bool:
        """Poll /api/ps until model appears in active_models or timeout."""
        deadline = asyncio.get_event_loop().time() + timeout_s
        while asyncio.get_event_loop().time() < deadline:
            try:
                import urllib.request
                req = urllib.request.Request("http://127.0.0.1:11434/api/ps")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = resp.read().decode()
                    if not data.strip():
                        pass  # empty response means no active models
                    else:
                        import json
                        info = json.loads(data)
                        active_models = info.get("models", []) if isinstance(info, dict) else []
                        for m in active_models:
                            model_field = m.get("model", m.get("name", ""))
                            if model_name in model_field:
                                return True
            except Exception as e:
                logger.debug(f"_verify_loaded poll error: {e}")

            await asyncio.sleep(0.5)  # 500ms polling interval
        return False

    async def _unload_current_model(self) -> bool:
        """Unload the currently loaded model."""
        if not self._current_model:
            return True
        return await self._unload_model_by_name(self._current_model)

    async def _unload_model_by_name(self, model_name: str) -> bool:
        """Send unload request and verify via /api/ps polling."""
        # Send unload signal to Ollama.
        # Ollama has no dedicated unload endpoint — the standard mechanism is the
        # keep_alive=0 API (POST /api/chat|/api/generate with keep_alive: 0).
        # Best-effort: some versions accept DELETE; fall back to polling /api/ps
        # until the model is evicted (or times out).
        try:
            import json as _json
            import urllib.request
            body = _json.dumps({"model": model_name, "keep_alive": 0}).encode()
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/generate",
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info(f"keep_alive=0 unload request accepted for '{model_name}': {resp.status}")
        except Exception as e:
            logger.debug(f"_unload_model_by_name: keep_alive=0 request failed ({e}); will poll for eviction")

        # Poll until model disappears.
        deadline = asyncio.get_event_loop().time() + 30
        while asyncio.get_event_loop().time() < deadline:
            try:
                req = urllib.request.Request("http://127.0.0.1:11434/api/ps")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = resp.read().decode()
                    if not data.strip():
                        return True  # no active models → unloaded
                    import json
                    info = json.loads(data)
                    active_models = info.get("models", []) if isinstance(info, dict) else []
                    for m in active_models:
                        model_field = m.get("model", m.get("name", ""))
                        if model_name in model_field:
                            break
                    else:
                        # Not found in active models → unloaded
                        return True
            except Exception as e:
                logger.debug(f"Unload poll error for '{model_name}': {e}")
            await asyncio.sleep(0.5)

        logger.warning(f"_unload_model_by_name({model_name}): eviction timeout — model may still be resident")
        return False

    def reset_state(self):
        """Reset state machine to idle (for error recovery)."""
        self._state = "idle"
        self._current_model = None


# ============================================================================
# SequentialStrategy — Public ExecutionStrategy implementation
# ============================================================================

class SequentialStrategy(ExecutionStrategy):
    """Strategy: sequential

    Only one large model resident at a time per agent phase. Uses
    ModelLifecycleManager with explicit state machine, readiness
    verification, and typed errors.

    Unloads previous model before loading the next; verifies via /api/ps.
    Appropriate for constrained unified-memory systems (Jetson AGX Orin 64GB),
    edge deployments, or any system where concurrent model residency causes degradation.
    """

    def __init__(self, workspace_root: str = None):
        self.workspace_root = workspace_root
        self._lifecycle = _ModelLifecycleManager(workspace_root)

    async def prepare_for_agent(self, agent_id: str) -> StrategyResult:
        """Ensure the target model is ready for an agent phase."""
        # Resolve model name from registry (same pattern as ConcurrentStrategy).
        model_name = self._resolve_model(agent_id)
        if model_name is None:
            return StrategyResult(
                success=False,
                strategy=Strategy.SEQUENTIAL.value,
                model_status={},
                notes=[f"Failed to resolve agent {agent_id} from registry"],
            )

        result = await self._lifecycle.ensure_ready(model_name)

        if result.success:
            # Mark as executing
            async with self._lifecycle._lock:
                if model_name in self._lifecycle._model_status:
                    self._lifecycle._model_status[model_name]["executing"] = True
                self._lifecycle._state = "executing"

        return result

    async def release_agent(self, agent_id: str) -> StrategyResult:
        """Release model resources after an agent phase completes."""
        # Resolve model name for cleanup.
        model_name = self._resolve_model(agent_id)
        if model_name is None:
            # Best-effort: try to unload whatever is current.
            model_name = self._lifecycle.current_model

        if not model_name:
            return StrategyResult(
                success=True,
                strategy=Strategy.SEQUENTIAL.value,
                model_status={},
                notes=[f"No model resolved for {agent_id} release — nothing to do"],
            )

        result = await self._lifecycle.release_model(model_name)

        if result.success:
            logger.info(f"SequentialStrategy: released agent {agent_id}, model '{model_name}' unloaded")

        return result

    def _resolve_model(self, agent_id: str) -> Optional[str]:
        """Resolve the model name for an agent from the registry."""
        try:
            from dispatcher.registry import AgentRegistry
            registry = AgentRegistry(workspace_root=self.workspace_root)
            registry.load()
            reg_result = registry.resolve(agent_id)
            if not reg_result.success or not reg_result.agent:
                logger.warning(f"Registry resolution for {agent_id} failed: {reg_result.error}")
                return None
            return reg_result.agent.model
        except Exception as e:
            logger.warning(f"Registry resolution for {agent_id} failed (non-fatal): {e}")
            return None

    def can_support_concurrent_agents(self) -> bool:
        """Sequential strategy does NOT support concurrent agents (one model at a time)."""
        return False

    def assess_capability(self) -> CapabilityReport:
        """Sequential mode is always available — tradeoff is latency, not capability."""
        return CapabilityReport(
            strategy=Strategy.SEQUENTIAL.value,
            confidence=1.0,
            signals={"type": "strategy", "reason": "sequential mode is universally available"},
            reason="Sequential mode works on all hardware; tradeoff is ~2-5s per phase for model load/unload latency.",
        )

    def get_current_strategy_report(self) -> dict:
        """Returns current lifecycle state (used by ExecutionStrategyManager.status_report)."""
        return {
            "state": self._lifecycle.state,
            "current_model": self._lifecycle.current_model,
            "model_status": self._lifecycle.model_status,
        }
