# CTO Plan — TASK_DS_EO_043: Execution Strategy Manager

**Created:** 2026-08-14 07:00 PDT  
**Revised:** (incorporates user feedback — three strategy modes + auto-selection)  
**Status:** PLANNED (awaiting user approval for Gate G1)  
**Author:** CTO 🏗️  

---

## 1. Problem Statement

TASK_DS_EO_042 proved that on the Jetson AGX Orin 64GB unified-memory CPU-only hardware, **concurrent multi-model inference is not viable**. However, building a system that *assumes* sequential residency as the universal default would:

- Break existing workflows for users with powerful GPU/server hardware where concurrent spawn already works.
- Remove user agency in choosing which strategy fits their use case (testing, debugging, benchmarking).
- Make DS-EO less portable — it should work equally well on a data center GPU cluster and a $499 Jetson board.

**The fix:** An **Execution Strategy Manager** that provides three strategies as configurable modes, with automatic selection as the default. The `ModelLifecycleManager` is one strategy implementation (sequential), not the universal behavior.

---

## 2. Three Execution Modes

### Mode 1: `concurrent` — Preserve Existing Behavior

- Multiple agent sessions run concurrently using existing OpenClaw `sessions_spawn`.
- Each role uses its own model; models stay loaded via OpenClaw's `keep_alive` config.
- **No model management overhead.** This is the current behavior, preserved exactly as-is.
- Appropriate for: systems with sufficient GPU memory (e.g., RTX 4090+ per GPU, data center servers) or where performance is prioritized over hardware safety.
- The existing `SessionSpawnManager` remains unchanged. No lifecycle management happens in this mode.

### Mode 2: `sequential` — ModelLifecycleManager

- Only one large model resident at a time per agent phase.
- Uses `ModelLifecycleManager` with explicit state machine, readiness verification, and typed errors.
- Unloads previous model before loading the next; verifies via `/api/ps`.
- Appropriate for: constrained unified-memory systems (Jetson AGX Orin 64GB), edge deployments, or any system where concurrent model residency causes degradation.

### Mode 3: `shared_model` — Single Model, Multiple Roles

- Multiple logical roles resolve to the same physical model.
- No unnecessary unload/reload when the model is already resident.
- Roles remain logically independent (separate sessions, separate prompts) but share model weights.
- Appropriate for: users who intentionally configure the same model for CTO/Implementer/Reviewer/PM (e.g., to reduce memory pressure without managing lifecycles, or for benchmarking model quality across roles).

---

## 3. Model State Taxonomy (Critical Distinction)

We must distinguish four independent concepts — **none implies any other**:

| State | Definition | How to Verify |
|-------|-----------|---------------|
| **Installed** | Model exists on disk as a GGUF file, ready to load | `ollama show <model>` succeeds (no download needed) |
| **Loaded/Resident** | Model weights are mapped into GPU/CPU memory and available for inference | `/api/ps` lists the model in its active models array |
| **Actively Executing** | An agent session is currently generating tokens using this model | OpenClaw reports an active chat completion; `/api/ps` shows context usage |
| **Available for Another Role** | The model is resident AND no other role has it actively executing (or the system can safely handle multiple consumers) | Depends on strategy: in `concurrent` mode, any loaded model is available; in `sequential`, only the one designated as current is available |

**Key insight:** A model can be "installed" and "loaded/resident" but **not** "available for another role" if it's already executing. Conversely, a model can be "installed" but not "loaded/resident" — requiring a load operation. The strategy manager operates on the *resident/executing* states, not the installed state.

---

## 4. Strategy Selection: Auto vs Manual

### 4.1 `auto` — Default Strategy

Auto-selection performs a **capability assessment** at DS-EO startup (or when the first task is opened). It evaluates all of these signals and chooses the most appropriate strategy:

| Signal | Source | Threshold / Logic |
|--------|--------|-------------------|
| Total system memory | `/proc/meminfo` (Linux) or `psutil` | < 32GB total → disqualify concurrent |
| Available GPU VRAM | `nvidia-smi` (discrete GPU) or unified memory API | If discrete GPU exists AND per-model size fits coherently → concurrent possible |
| Unified vs discrete memory | OS-level detection (`/dev/dri`, `lspci`) | Unified (Tegra, Apple Silicon) → favor sequential if total RAM < 64GB; two models at ~24GB each on unified memory cause bandwidth saturation (per TASK_DS_EO_042) |
| Configured model sizes | Sum of unique `AgentInfo.model` values resolved via `registry.py`, look up file size via `ollama show` or local manifest | If sum of top-2 model sizes > 60% of available GPU/RAM → sequential needed |
| Number of active models in config | Count of distinct models across all agent entries in `agents_list.json` | > 3 distinct models with concurrent loading expected on unified memory → flag risk |
| Existing loaded models | `/api/ps` at assessment time | If ≥ 2 large models already resident + any new load needed → sequential recommended |

**Auto-selection decision matrix:**

```
if discrete_GPU_and_sufficient_VRAM():
    strategy = "concurrent"
elif unified_memory and total_RAM >= 64GB:
    # 64GB can typically handle two ~20GB models without catastrophic bandwidth contention
    if configured_unique_models <= 2:
        strategy = "concurrent"  # borderline but likely safe
    else:
        strategy = "sequential"  # safer default
elif unified_memory and total_RAM < 64GB:
    strategy = "sequential"    # Jetson AGX Orin 64GB case
else:
    strategy = "shared_model"  # fallback when hardware detection unclear
```

The auto-selection log is written to `docs/development/reports/TASK_DS_EO_043_MODEL_LIFECYCLE_MANAGER/AUTO_SELECTION_LOG.md` for auditability.

### 4.2 Manual Override

Any user can override auto-selection:

- **Via config:** `execution.strategy` field in workspace config (or DS-EO config)
- **Via skill command:** `/eo execution strategy <concurrent|sequential|shared_model>` — stored as a persistent override, not ephemeral
- **Via task-level override:** Per-task override in dispatcher state for targeted testing/debugging

```json
{
  "execution": {
    "strategy": "auto"   // or "concurrent", "sequential", "shared_model"
  }
}
```

When auto is overridden, the override is **persisted** (not lost on restart) and logged in `docs/development/reports/TASK_DS_EO_043_MODEL_LIFECYCLE_MANAGER/OVERRIDE_LOG.md`.

### 4.3 Detection of Override vs Auto

The ExecutionStrategyManager always records the **source** of the selected strategy:
- `"auto"` → capability assessment result
- `"user_override"` → persisted manual config or skill command

This distinction matters for debugging and benchmarking — users need to know whether a mode is running because of auto-detection or because they set it.

---

## 5. Architecture: ExecutionStrategyManager

```
dispatcher/
├── engine.py                 # Workflow state machine (unchanged)
├── registry.py               # Agent → model mapping (reuse as-is)
├── state_manager.py          # Persistent task state (unchanged)
├── session_dispatch/         # Session handoff layer (unchanged)
│   └── engine.py
├── session_spawn.py           # OpenClaw spawn integration (strategy-aware)
├── execution_strategy/       # ← NEW sub-package
│   ├── __init__.py           # exports ExecutionStrategyManager, ExecutionStrategy
│   ├── constants.py          # Strategy enum, state taxonomy, capability thresholds
│   ├── strategy_base.py      # Abstract base class + common interface
│   ├── concurrent_strategy.py # Preserves existing spawn behavior exactly
│   ├── sequential_strategy.py # Contains ModelLifecycleManager
│   │   └── model_lifecycle/  # Internal to this file: OllamaClient, state machine
│   ├── shared_model_strategy.py
│   ├── capability_assessor.py # Auto-detection logic
│   └── selector.py           # Resolves auto vs manual; singleton manager
├── workflow_defs/
├── binding_defs/
└── project_resolver/
```

### 5.1 Strategy Interface (Base Class)

All strategies implement a common contract:

```python
class ExecutionStrategy(ABC):
    """Common interface for all execution strategies."""
    
    @abstractmethod
    async def prepare_for_agent(self, agent_id: str) -> StrategyResult:
        """
        Ensure the target model/environment is ready for an agent.
        
        Returns StrategyResult with:
            - success: bool
            - strategy: str (strategy name)
            - model_status: dict describing current model state
            - notes: list of human-readable status messages
        
        Raises StrategyError with typed codes.
        """
    
    @abstractmethod
    async def release_agent(self, agent_id: str) -> StrategyResult:
        """Clean up after an agent phase completes."""
    
    @abstractmethod
    def can_support_concurrent_agents(self) -> bool:
        """Return True if this strategy supports concurrent spawning."""
    
    @abstractmethod
    def assess_capability(self) -> CapabilityReport:
        """For auto-selection: return hardware capability report."""


@dataclass
class StrategyResult:
    success: bool
    strategy: str  # "concurrent" | "sequential" | "shared_model"
    model_status: dict  # {model_name: {"installed": bool, "loaded": bool, "executing": bool}}
    notes: list[str] = field(default_factory=list)


@dataclass
class CapabilityReport:
    strategy: str  # recommended strategy name
    confidence: float  # 0.0 - 1.0
    signals: dict  # raw signal values used for decision
    reason: str  # human-readable explanation
```

### 5.2 ConcurrentStrategy — Preserves Existing Behavior

```python
class ConcurrentStrategy(ExecutionStrategy):
    """
    Strategy: concurrent
    
    No model lifecycle management. Spawns sessions via OpenClaw exactly as before.
    Models remain loaded per their keep_alive configuration.
    
    This is the identity path — no behavioral change from current DS-EO.
    """
    
    def __init__(self):
        self._spawn_manager = SessionSpawnManager()  # existing, unchanged
    
    async def prepare_for_agent(self, agent_id: str) -> StrategyResult:
        # Resolve model from registry (unchanged)
        agent_info = AgentRegistry(workspace_root).resolve(agent_id)
        
        # No model management needed — spawn directly
        outcome = self._spawn_manager.spawn_agent(...)
        
        return StrategyResult(
            success=outcome.success,
            strategy="concurrent",
            model_status={agent_info.model: {"installed": True, "loaded": True, "executing": False}},
            notes=[],
        )
    
    async def release_agent(self, agent_id: str) -> StrategyResult:
        # No cleanup needed in concurrent mode
        return StrategyResult(success=True, strategy="concurrent", model_status={}, notes=[])
    
    def can_support_concurrent_agents(self) -> bool:
        return True
    
    def assess_capability(self) -> CapabilityReport:
        return CapabilityReport(
            strategy="concurrent", confidence=1.0,
            signals={"type": "strategy"}, reason="Manual override to concurrent mode"
        )
```

**Key point:** `ConcurrentStrategy` does NOT modify `session_spawn.py`. It wraps the existing behavior. If the user selects `concurrent`, DS-EO behaves exactly as it did before this work.

### 5.3 SequentialStrategy — Contains ModelLifecycleManager

```python
class SequentialStrategy(ExecutionStrategy):
    """
    Strategy: sequential
    
    Uses ModelLifecycleManager to enforce one-model-at-a-time residency.
    All model lifecycle operations (load, unload, verify readiness) go through MLM.
    """
    
    def __init__(self):
        self._mlm = ModelLifecycleManager()  # internal, not shared with other strategies
    
    async def prepare_for_agent(self, agent_id: str) -> StrategyResult:
        agent_info = AgentRegistry(workspace_root).resolve(agent_id)
        model_name = agent_info.model
        
        # Ensure model is loaded and ready (unloads previous if needed)
        try:
            ok = self._mlm.ensure_ready(model_name)
        except ModelStateError as e:
            return StrategyResult(
                success=False, strategy="sequential",
                model_status={}, notes=[f"Model lifecycle error: {e.code}"],
            )
        
        # Verify current state for reporting
        loaded = self._mlm.ollama_client.get_loaded_models()
        model_status = {}
        for name, info in loaded.items():
            model_status[name] = {"installed": True, "loaded": True, "executing": False}
        
        return StrategyResult(
            success=ok, strategy="sequential",
            model_status=model_status,
            notes=[f"Loaded {model_name} for agent {agent_id}"],
        )
    
    async def release_agent(self, agent_id: str) -> StrategyResult:
        agent_info = AgentRegistry(workspace_root).resolve(agent_id)
        self._mlm.release_model(agent_info.model)
        return StrategyResult(success=True, strategy="sequential", model_status={}, notes=[])
    
    def can_support_concurrent_agents(self) -> bool:
        return False
    
    def assess_capability(self) -> CapabilityReport:
        # For auto-selection, report that sequential works on this hardware
        return CapabilityReport(
            strategy="sequential", confidence=1.0,
            signals={"hardware": "constrained"}, reason="Auto-selected for hardware constraints"
        )


# === ModelLifecycleManager (internal to SequentialStrategy) ===

class ModelState(str, Enum):
    UNLOADED = "UNLOADED"
    LOAD_REQUIRED = "LOAD_REQUIRED"
    LOADING = "LOADING"
    READY = "READY"
    BUSY = "BUSY"
    UNLOADING = "UNLOADING"
    ERROR = "ERROR"


class ModelStateError(Exception):
    MODEL_LOAD_TIMEOUT = "MODEL_LOAD_TIMEOUT"
    INSUFFICIENT_MEMORY = "INSUFFICIENT_MEMORY"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    UNLOAD_FAILURE = "UNLOAD_FAILURE"
    CONCURRENT_TRANSITION = "CONCURRENT_TRANSITION"
    API_ERROR = "API_ERROR"
    READY_CHECK_FAILURE = "READY_CHECK_FAILURE"


class OllamaClient:
    """Thin HTTP wrapper over ollama REST API."""
    
    def list_models(self) -> dict:        # GET /api/tags
    def is_model_installed(self, name) -> bool:  # check /api/tags result
    def pull_model(self, name) -> bool:   # POST /api/pull
    def get_loaded_models(self) -> dict:  # GET /api/ps → {name: info}
    def load_model(self, name) -> bool:   # via ollama CLI or HTTP keep_alive trick
    def unload_model(self, name) -> None: # via keep_alive="-1s" on next load or subprocess
    def get_memory_info(self) -> dict:    # /proc/meminfo or psutil


class ModelLifecycleManager:
    """Core state machine with mutex for sequential strategy."""
    
    def __init__(self, workspace_root=None):
        self._state_lock = threading.Lock()
        self._model_states: dict[str, ModelState] = {}
        self._current_model: Optional[str] = None  # the one currently loaded
        self.ollama_client = OllamaClient()
    
    def ensure_ready(self, model_name: str, timeout_seconds=60) -> bool:
        """Ensure a model is loaded and ready. Unloads other large models first."""
        with self._state_lock:
            # 1. Already in desired state?
            current = self._get_internal_state(model_name)
            if current in (ModelState.READY, ModelState.BUSY):
                return True
            
            # 2. Identify and unload previous large model(s)
            loaded_models = self.ollama_client.get_loaded_models()
            for loaded_name in loaded_models:
                if loaded_name != model_name and loaded_name not in ("nomic-embed-text",):
                    self._unload_model(loaded_name)
            
            # 3. Verify unloading succeeded
            post_unload = self.ollama_client.get_loaded_models()
            for prev in loaded_models:
                if prev != model_name and prev not in ("nomic-embed-text",) and prev in post_unload:
                    raise ModelStateError(ModelStateError.UNLOAD_FAILURE, f"{prev} did not unload")
            
            # 4. Check available memory before loading
            mem_ok, free_gb = self._check_memory_available(model_name)
            if not mem_ok:
                raise ModelStateError(ModelStateError.INSUFFICIENT_MEMORY,
                                      f"Only {free_gb:.1f}GB free; model needs ~{self._estimate_size(model_name)}GB")
            
            # 5. Load the model
            self._set_internal_state(model_name, ModelState.LOADING)
            loaded = self.ollama_client.load_model(model_name)
            if not loaded:
                self._set_internal_state(model_name, ModelState.ERROR)
                raise ModelStateError(ModelStateError.MODEL_LOAD_TIMEOUT, f"{model_name} load timeout")
            
            # 6. Verify readiness via /api/ps (mandatory)
            ps = self.ollama_client.get_loaded_models()
            if model_name not in ps:
                self._set_internal_state(model_name, ModelState.ERROR)
                raise ModelStateError(ModelStateError.READY_CHECK_FAILURE,
                                      f"{model_name} loaded but not confirmed by /api/ps")
            
            self._set_internal_state(model_name, ModelState.READY)
            self._current_model = model_name
            return True
    
    def release_model(self, model_name: str):
        with self._state_lock:
            if self._get_internal_state(model_name) == ModelState.BUSY:
                self.ollama_client.unload_model(model_name)
                self._set_internal_state(model_name, ModelState.UNLOADED)
                if self._current_model == model_name:
                    self._current_model = None
    
    def get_current_strategy_report(self) -> dict:
        """Return current strategy state for logging/status."""
        return {
            "strategy": "sequential",
            "current_model": self._current_model,
            "model_states": dict(self._model_states),
            "loaded_via_api_ps": self.ollama_client.get_loaded_models(),
        }


# State machine transitions:
#   UNLOADED ──load_required──▶ LOAD_REQUIRED ──start_load──▶ LOADING
#   LOADING ──timeout/failure──▶ ERROR     LOADING ──/api/ps ok──▶ READY
#   READY ──agent_spawn──▶ BUSY     BUSY ──session_complete──▶ release_model()
#   UNLOADED ◄──release_model()── BUSY     (all states) ──error──▶ ERROR

### 5.4 SharedModelStrategy — Same Model, Multiple Roles

```python
class SharedModelStrategy(ExecutionStrategy):
    """
    Strategy: shared_model
    
    Multiple logical roles resolve to the same physical model.
    No unnecessary unload/reload cycles when the model is already resident.
    Roles remain logically separate (separate sessions, separate prompts).
    
    Example config:
      agents_list.json: all 4 agents use "ollama/qwen3.6:27b"
      
    Behavior:
      - CTO phase: ensure qwen3.6:27b is loaded → spawn CTO session
      - Implementer phase: resolve to same model → already loaded, skip reload → spawn Implementer
      - Reviewer phase: resolve to same model → already loaded, skip reload → spawn Reviewer
      
    Key distinction from concurrent mode:
      In concurrent mode, different roles use DIFFERENT models (all loaded).
      In shared_model, different roles use the SAME model (loaded once, used by all).
    """
    
    def __init__(self):
        self._spawn_manager = SessionSpawnManager()
        self._model_load_status: dict[str, str] = {}  # model → "loading"|"ready"|"error"
        self._model_lock = threading.Lock()
    
    async def prepare_for_agent(self, agent_id: str) -> StrategyResult:
        agent_info = AgentRegistry(workspace_root).resolve(agent_id)
        model_name = agent_info.model
        
        with self._model_lock:
            # Check if this model is already resident and ready
            if self._model_load_status.get(model_name) == "ready":
                loaded = self._mlm_client_if_exists or self.ollama_client.get_loaded_models()
                status_entry = {model_name: {"installed": True, "loaded": True, 
                      "executing": model_name in loaded, "shared_by": [aid for aid, m in agents if m == model_name]}}
                return StrategyResult(
                    success=True, strategy="shared_model",
                    model_status=status_entry,
                    notes=[f"Model {model_name} already loaded — reused for agent {agent_id}"],
                )
            
            # Model not yet loaded — load it (only once)
            self._model_load_status[model_name] = "loading"
            installed = self.ollama_client.is_model_installed(model_name)
            if not installed:
                self._model_load_status[model_name] = "error"
                return StrategyResult(
                    success=False, strategy="shared_model",
                    model_status={}, notes=[f"Model {model_name} not installed"],
                )
            
            loaded_ok = self.ollama_client.load_model(model_name)
            if not loaded_ok:
                self._model_load_status[model_name] = "error"
                return StrategyResult(
                    success=False, strategy="shared_model",
                    model_status={}, notes=[f"Failed to load {model_name}"],
                )
            
            # Verify via /api/ps
            ps = self.ollama_client.get_loaded_models()
            if model_name not in ps:
                self._model_load_status[model_name] = "error"
                return StrategyResult(
                    success=False, strategy="shared_model",
                    model_status={}, notes=[f"{model_name} not confirmed by /api/ps"],
                )
            
            self._model_load_status[model_name] = "ready"
            status_entry = {model_name: {"installed": True, "loaded": True, 
                  "executing": True, "shared_by": [agent_id]}}
            return StrategyResult(
                success=True, strategy="shared_model",
                model_status=status_entry,
                notes=[f"Loaded {model_name} for agent {agent_id} (first consumer)"],
            )
    
    async def release_agent(self, agent_id: str) -> StrategyResult:
        # Do NOT unload the model — other roles may still need it
        agent_info = AgentRegistry(workspace_root).resolve(agent_id)
        model_name = agent_info.model
        
        # Track which role last used; don't unload until all are done
        # (simplified: in production, use reference counting)
        return StrategyResult(success=True, strategy="shared_model", 
                              model_status={}, notes=[f"Released {agent_id}, model {model_name} remains loaded"])
    
    def can_support_concurrent_agents(self) -> bool:
        return True  # multiple sessions can share one model
    
    def assess_capability(self) -> CapabilityReport:
        return CapabilityReport(
            strategy="shared_model", confidence=1.0,
            signals={"type": "strategy"}, reason="Manual override to shared_model mode"
        )


# For auto-selection, SharedModelStrategy provides a different kind of assessment:
class SharedModelCapabilityAssessment(CapabilityReport):
    """For auto when models are already configured to overlap."""
    
    def detect_shared_models(self) -> list[str]:
        """Detect which models multiple agents share in current config."""
        registry = AgentRegistry(workspace_root)
        registry.load()
        model_usage: dict[str, list[str]] = {}  # model → [agent_ids]
        for aid, agent in registry.agents.items():
            model_usage.setdefault(agent.model, []).append(aid)
        
        shared = {m: agents for m, agents in model_usage.items() if len(agents) > 1}
        return shared
```

### 5.5 Selector — Auto vs Manual Resolution

```python
class ExecutionStrategySelector:
    """
    Resolves which execution strategy to use.
    
    Priority order:
    1. User override (persisted config or skill command)
    2. Auto-detection via CapabilityAssessor
    
    Singleton per DS-EO process lifetime.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, workspace_root=None):
        if self._initialized:
            return
        self.workspace_root = workspace_root or os.environ.get("DS_EO_WORKSPACE")
        self.config_path = os.path.join(self.workspace_root, "ds_eo_config.yaml")  # or similar
        self._strategy_map = {
            "concurrent": ConcurrentStrategy(),
            "sequential": SequentialStrategy(),
            "shared_model": SharedModelStrategy(),
        }
        self._selected_strategy_name: Optional[str] = None  # None = not yet resolved
        self._selection_source: Optional[str] = None         # "auto" | "user_override"
        self._initialized = True
    
    def get_or_resolve(self) -> tuple[str, ExecutionStrategy, CapabilityReport]:
        """
        Get the current strategy. Resolve if not yet selected.
        
        Returns: (strategy_name, strategy_instance, capability_report)
        """
        if self._selected_strategy_name is None:
            self._resolve()
        
        return (self._selected_strategy_name, 
                self._strategy_map[self._selected_strategy_name],
                CapabilityReport(
                    strategy=self._selected_strategy_name,
                    confidence=0.9 if self._selection_source == "auto" else 1.0,
                    signals={}, reason=(
                        "User override: " + self._selected_strategy_name 
                        if self._selection_source == "user_override"
                        else "Auto-selected by capability assessment"
                    )
                ))
    
    def set_manual_override(self, strategy_name: str):
        """Persist a manual override."""
        if strategy_name not in self._strategy_map:
            raise ValueError(f"Unknown strategy: {strategy_name}. Valid: {list(self._strategy_map.keys())}")
        self._selected_strategy_name = strategy_name
        self._selection_source = "user_override"
        self._persist_override(strategy_name)
    
    def clear_override(self):
        """Remove manual override; revert to auto."""
        self._clear_persisted_override()
        self._resolve()  # re-run auto-detection
    
    def _resolve(self):
        """Run auto-detection and select strategy."""
        report = CapabilityAssessor.assess(self.workspace_root)
        self._selected_strategy_name = report.strategy
        self._selection_source = "auto"
    
    def _persist_override(self, strategy_name: str):
        """Write override to config file."""
        ...  # see §6 Config Schema
    
    def _clear_persisted_override(self):
        """Remove override from config file."""
        ...

### 5.6 ExecutionStrategyManager — Public Facade (Singleton)

This is the entry point used by `engine.py` during phase transitions:

```python
class ExecutionStrategyManager:
    """Public facade: wraps selector + strategy instance. Used by engine.py."""
    
    def __init__(self, workspace_root=None):
        self.selector = ExecutionStrategySelector(workspace_root)
    
    async def prepare_phase(self, agent_id: str) -> StrategyResult:
        strategy_name, strategy_impl, report = self.selector.get_or_resolve()
        
        # Log which mode is active
        logger.info(f"Execution mode: {strategy_name} (source: {self.selector._selection_source})")
        
        result = await strategy_impl.prepare_for_agent(agent_id)
        
        # Attach metadata for logging
        result.metadata = {"strategy": strategy_name, "source": self.selector._selection_source}
        return result
    
    async def release_phase(self, agent_id: str) -> StrategyResult:
        _, strategy_impl, _ = self.selector.get_or_resolve()
        return await strategy_impl.release_agent(agent_id)
    
    async def switch_strategy(self, strategy_name: str):
        """Allow user-initiated mode change at runtime."""
        self.selector.set_manual_override(strategy_name)
        logger.info(f"Strategy switched to {strategy_name} by user")
    
    def status_report(self) -> dict:
        name, impl, report = self.selector.get_or_resolve()
        if hasattr(impl, 'get_current_strategy_report'):
            lifecycle_status = impl.get_current_strategy_report()
        else:
            lifecycle_status = {"status": "N/A (strategy does not manage individual models)"}
        
        return {
            "active_strategy": name,
            "source": self.selector._selection_source,
            "capability_report": {
                "confidence": report.confidence,
                "reason": report.reason,
                "signals": report.signals,
            },
            "lifecycle_state": lifecycle_status,
        }
```

---

## 6. Config Schema

### 6.1 Workspace-level Config (ds_eo_config.yaml)

```yaml
execution:
  strategy: auto                    # auto | concurrent | sequential | shared_model
  auto_assessment:
    enabled: true                   # run detection at startup
    fallback_on_failure: sequential # default if detection fails
  memory_safety:
    min_free_ram_gb: 8              # never load below this threshold
    unloading_aggressive: false     # aggressive unload even if some RAM remains
  overrides:
    persistent: {}                  # persisted by selector when user runs /eo execution strategy
    per_task:                       # optional per-task overrides
      TASK_DS_EO_044: shared_model  # example
  
  logging:
    level: INFO                     # DEBUG for benchmarking, INFO for normal
    log_dir: docs/development/reports/TASK_DS_EO_043_MODEL_LIFECYCLE_MANAGER/
```

### 6.2 Agent-Level Config (agents_list.json / openclaw.json)

No changes required — each agent's `model` field remains the source of truth for *which* model it uses. The strategy layer operates *above* this mapping.

### 6.3 Auto-Detection State Files (generated)

```
docs/development/reports/TASK_DS_EO_043_MODEL_LIFECYCLE_MANAGER/
├── AUTO_SELECTION_LOG.md         # auto-detection result with signals
├── OVERRIDE_LOG.md               # manual overrides and timestamps
└── STRATEGY_STATUS.json          # current strategy state (written by ExecutionStrategyManager)
```

---

## 7. Integration Points

### 7.1 Where engine.py Changes

**Before:** `engine.py` called `SessionSpawnManager.spawn_agent()` directly, with no awareness of model lifecycle.

**After:** `engine.py` calls `ExecutionStrategyManager.prepare_phase(agent_id)` before spawning and `release_phase(agent_id)` after completion. The spawn call itself remains the same — only the pre/post hooks change.

```python
# Before (simplified):
async def transition_to_agent(self, agent_id):
    outcome = self.spawn_manager.spawn_agent(agent_id, ...)
    
# After:
async def transition_to_agent(self, agent_id):
    prep = await self.strategy_mgr.prepare_phase(agent_id)
    if not prep.success:
        # handle error — model load failed, log to strategy status file
        raise PhaseError(f"Strategy prepare failed: {prep.notes}")
    
    outcome = self.spawn_manager.spawn_agent(agent_id, ...)
    
    # After session completes (in the completion handler):
    release = await self.strategy_mgr.release_phase(agent_id)
```

### 7.2 Where registry.py Stays Unchanged

`registry.py` continues to provide `resolve(agent_id) -> AgentInfo`. The strategy layer consumes this but does not modify it.

### 7.3 Existing Files That Remain Untouched

- `session_spawn.py` — unchanged in all three strategies. ConcurrentStrategy wraps the existing behavior; SequentialStrategy and SharedModelStrategy each have their own spawn paths or use the existing one with different preconditions.
- `state_manager.py` — persistent task state is independent of execution strategy.
- `workflow_defs/` — workflow definitions are strategy-agnostic.
- `binding_defs/` — binding definitions unchanged.
- `project_resolver/` — project resolution unchanged.

### 7.4 Skill Command Integration

The `/eo execution strategy <mode>` skill command maps directly to `ExecutionStrategySelector.set_manual_override(mode)`. The command stores the override persistently and updates the config file, then calls `prepare_phase` for the currently active agent if any.

---

## 8. Testing Strategy

### 8.1 Unit Tests (pytest)

| Test | What it verifies | File |
|------|-----------------|------|
| ConcurrentStrategy identity | Verify concurrent mode produces same behavior as pre-change codebase | `test/concurrent_strategy/test_identity.py` |
| SequentialStrategy load/unload cycle | Full lifecycle: ensure_ready → verify /api/ps → release_model → verify unloaded | `test/sequential_strategy/test_lifecycle.py` |
| SharedModelStrategy reuse | Two agents resolve to same model → second call finds it already loaded, no re-load | `test/shared_model_strategy/test_reuse.py` |
| CapabilityAssessor auto-detection | Mock different hardware signals → assert correct strategy selection | `test/selector/test_capability_assess.py` |
| Selector override persistence | Set manual override → check config file updated → clear override → check reverted | `test/selector/test_override_persistence.py` |
| Strategy switching at runtime | Switch from concurrent → sequential mid-task → verify next agent uses new strategy | `test/engine/test_strategy_switch.py` |

### 8.2 Integration Tests

| Test | Setup | What it verifies |
|------|-------|-----------------|
| Full G1-G4 flow in sequential mode | Real Ollama instance, single large model + nomic-embed-text | Phase transitions complete without memory errors; model unloading between phases is verified |
| Full G1-G4 flow in concurrent mode | Multi-GPU setup or sufficient VRAM | All roles spawn and run concurrently as before |
| Strategy auto-detection on constrained hardware | Jetson AGX Orin 64GB (or simulated with cgroups) | Auto selects sequential, writes AUTO_SELECTION_LOG.md |
| Manual override vs auto | Set override to concurrent on constrained hardware → observe behavior | Override is respected; warning logged about risk |

### 8.3 Performance Benchmarks

For each strategy:
- Time-to-first-token (TTFT) per phase transition
- Peak RSS memory during model load/unload
- /api/ps round-trip latency for readiness verification
- Total task completion time (G1 through G4)

Baseline = current concurrent behavior on the same hardware. Sequential mode's TTFT penalty is expected (~2-5s per phase for model load), but the tradeoff is correctness and stability.

---

## 9. Migration Path

### Phase A: Foundation (TASK_DS_EO_043 itself)
1. Create `execution_strategy/` sub-package with base class, constants, selectors
2. Implement `ConcurrentStrategy` (identity wrap of existing code)
3. Implement `CapabilityAssessor` + auto-detection logic
4. Implement `ExecutionStrategySelector` (singleton with override persistence)
5. Write unit tests for the above

### Phase B: Sequential Mode (next task — TASK_DS_EO_044)
1. Move `ModelLifecycleManager` from CTO plan into `SequentialStrategy`
2. Implement `SharedModelStrategy`
3. Hook into `engine.py` with `prepare_phase` / `release_phase`
4. Integration tests on constrained hardware

### Phase C: Skill Command + Polish
1. `/eo execution strategy` skill command for manual override
2. Auto-detection runs at DS-EO startup, not lazily at first task
3. Status reporting via `ExecutionStrategyManager.status_report()` — visible in PM dashboard
4. Migration guide for existing DS-EO users

---

## 10. Acceptance Criteria

### 10.1 Functional

- [ ] Three strategies (concurrent, sequential, shared_model) all produce valid `StrategyResult` objects with correct metadata
- [ ] Auto-detection correctly identifies constrained hardware and selects sequential; overrides are respected
- [ ] Sequential mode: models unload between phases, /api/ps verification succeeds, no model remains resident after release
- [ ] Concurrent mode: zero behavioral change from current DS-EO (all roles spawn, run, complete as before)
- [ ] Shared_model mode: same model loaded once, reused across agents without reload; unloading waits until all roles release

### 10.2 Integration

- [ ] `engine.py` calls strategy manager hooks correctly at phase boundaries
- [ ] Strategy selection is logged to `AUTO_SELECTION_LOG.md` or `OVERRIDE_LOG.md`
- [ ] Skill command `/eo execution strategy` persists override and applies it immediately

### 10.3 Quality

- [ ] All unit tests pass (≥ 6 test cases as listed in §8)
- [ ] Integration test on Jetson AGX Orin 64GB: full G1-G4 flow completes without OOM or model conflict errors
- [ ] Performance benchmark data collected and documented (TTFT, memory peaks, total phase transition time)

### 10.4 Documentation

- [ ] README update describing the three strategies and how to switch between them
- [ ] Config schema documented in config reference
- [ ] Migration guide for existing users who want to test sequential or shared_model modes

---

## 11. Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Auto-detection picks wrong strategy | Low (heuristic is conservative) | Fallback to sequential on any detection failure; manual override always available |
| Model unload doesn't free memory immediately | Medium (Ollama GC timing) | Poll /api/ps in a loop with 500ms intervals, timeout after 30s; if still resident, log warning and proceed |
| Shared_model mode causes role confusion | Low (logical separation maintained) | Strategy report includes `shared_by` field so users can audit which roles share models |
| Concurrent override on constrained hardware breaks DS-EO | Medium (user error) | Log critical warning to AUTO_SELECTION_LOG.md when auto-detected capability < required; skill command also warns before applying |

---

## 12. Deliverables Summary

| Deliverable | Location | Status |
|------------|----------|--------|
| `execution_strategy/` sub-package (6 files) | `dispatcher/execution_strategy/` | Planned |
| Updated `engine.py` hooks | `dispatcher/engine.py` | Planned |
| Unit tests | `test/concurrent_strategy/`, `test/sequential_strategy/`, `test/shared_model_strategy/`, `test/selector/` | Planned |
| Auto-selection log template | `docs/development/reports/TASK_DS_EO_043_MODEL_LIFECYCLE_MANAGER/AUTO_SELECTION_LOG.md` | Planned |
| Override log template | `docs/development/reports/TASK_DS_EO_043_MODEL_LIFECYCLE_MANAGER/OVERRIDE_LOG.md` | Planned |
| Config schema reference update | `config-templates/ds_eo_config.yaml.example` | Planned |
| Migration guide | `docs/development/reports/TASK_DS_EO_043_MODEL_LIFECYCLE_MANAGER/MIGRATION_GUIDE.md` | Planned |

---

## 13. Timeline Estimate

| Phase | Tasks | Est. Hours |
|-------|-------|-----------|
| A: Foundation (this task) | Package scaffolding + ConcurrentStrategy + CapabilityAssessor + Selector + unit tests | 8-12 |
| B: Sequential + SharedModel | ModelLifecycleManager integration + SharedModelStrategy + engine hooks + integration tests | 10-16 |
| C: Skill command + polish | `/eo execution strategy` command + startup detection + status reporting + docs + migration guide | 6-8 |
| **Total** | | **24-36 hours** |

---

## Gate Status

| Gate | Prerequisite Met? | Notes |
|------|------------------|-------|
| G1 (Plan Review) | Awaiting user approval | Plan incorporates three strategies + auto-selection as requested |
| G2 (Implementation) | Pending G1 approval | — |
| G3 (Review) | Pending G2 completion | — |
| G4 (CTO Approval) | Pending G3 approval | — |
| G5 (PM Closure) | Pending G4 approval | — |

---

**End of CTO Plan for TASK_DS_EO_043.**  
Awaiting user approval to proceed to Gate G1 (plan review).
