# CTO Plan — TASK_DS_EO_044: ModelLifecycleManager & Strategy Implementations

**Created:** 2026-08-15 10:46 PDT  
**Status:** PLANNED (awaiting user approval for Gate G1)  
**Author:** CTO 🏗️  
**Predecessor:** TASK_DS_EO_043 Phase A — Execution Strategy Manager foundation  

---

## 1. Context & Scope

TASK_DS_EO_043 delivered the **foundation**: `execution_strategy/` package with base class, ConcurrentStrategy (identity wrap), CapabilityAssessor, and selector singleton. All 30 unit tests pass.

**TASK_DS_EO_044 delivers Phase B:** the two missing strategy implementations, engine integration hooks, skill command, and migration documentation. This is NOT a redesign — it extends existing architecture.

### What's Already In Place (No Re-Work)

| Component | File | Status |
|-----------|------|--------|
| ExecutionStrategy ABC + StrategyResult / CapabilityReport | `dispatcher/execution_strategy/strategy_base.py` | ✅ Complete |
| Strategy enum, ModelState enum, ModelStateError | `dispatcher/execution_strategy/constants.py` | ✅ Complete |
| ConcurrentStrategy (identity wrap) | `dispatcher/execution_strategy/concurrent_strategy.py` | ✅ Complete |
| CapabilityAssessor (6 detection signals) | `dispatcher/execution_strategy/capability_assessor.py` | ✅ Complete |
| ExecutionStrategySelector singleton + override persistence | `dispatcher/execution_strategy/selector.py` | ✅ Complete |
| ExecutionStrategyManager facade (singleton, prepare_phase/release_phase) | `dispatcher/execution_strategy/__init__.py` | ✅ Complete |
| Engine hooks stub | `dispatcher/engine.py:269-282` | ✅ Non-fatal skeleton ready |

### What TASK_DS_EO_044 Adds

| # | Component | New File? |
|---|-----------|-----------|
| 1 | SequentialStrategy (ModelLifecycleManager integrated) | `sequential_strategy.py` — NEW |
| 2 | SharedModelStrategy (single model, multiple roles) | `shared_model_strategy.py` — NEW |
| 3 | Engine integration hooks (real prepare_phase/release_phase calls) | `dispatcher/engine.py` — MODIFIED |
| 4 | Skill command `/eo execution strategy <mode>` | skill definition — NEW |
| 5 | Integration tests | test files — NEW |
| 6 | Migration guide + README update | docs — NEW |

---

## 2. SequentialStrategy — Design

### 2.1 Architecture

SequentialStrategy **contains** ModelLifecycleManager internally. The key behaviors:

1. **State Machine** tracks model state per agent phase: `idle → loading → ready → executing → unloading → idle`
2. **Prepare flow:** Check if target model already loaded → if not, verify installed → unload current model (if any) → load new model → verify via `/api/ps` → return StrategyResult
3. **Release flow:** Mark model as not executing → schedule async unload → verify unloaded via `/api/ps` polling with 500ms intervals, timeout 30s
4. **Thread safety:** Internal asyncio.Lock protects the state machine

### 2.2 ModelLifecycleManager — Internal Details

```python
class _ModelLifecycleManager:
    """Core state machine with mutex for sequential strategy.
    
    State transitions:
        idle → loading → ready → executing → unloading → idle
        Any state --(error)--> error
    
    Model states tracked independently:
        installed (ollama show succeeds)
        loaded/resident (/api/ps shows model)
        executing (active session using this model)
    
    Thread safety: all methods acquire self._lock.
    """
    
    async def ensure_ready(self, model_name: str) -> StrategyResult
    async def release_model(self, model_name: str) -> StrategyResult  
    async def _unload_current_model(self) -> bool  # returns success/fail
    async def _load_model(self, model_name: str) -> StrategyResult
    async def _verify_loaded(self, model_name: str, timeout_s=30) -> bool
    
    @property
    def current_model(self) -> Optional[str]
    @property
    def state(self) -> str  # idle/loading/ready/executing/unloading/error
```

### 2.3 Implementation Strategy (NOT a full rewrite)

**ModelLifecycleManager currently exists as conceptual design only in CTO_PLAN.md §5.3.** We need to actually implement it inside `SequentialStrategy`. The implementation draws from:

- The state machine design documented in TASK_DS_EO_043's CTO_PLAN.md
- `/api/ps` API patterns (already used by CapabilityAssessor for detection)
- Existing error handling via `ModelStateError` from Phase A

**Key design decisions:**

1. **Poll-based verification, not event-driven.** Ollama doesn't emit load/unload completion events. We poll `/api/ps` with 500ms intervals (configurable), timeout at 30s. This is conservative and safe on CPU-only hardware.

2. **Unloading waits for model eviction from memory.** After calling Ollama's unload endpoint, we poll until `/api/ps` no longer lists the model. If it remains after 30s, we log a warning and proceed (the next `ensure_ready` will handle cleanup).

3. **Lazy initialization.** `_ModelLifecycleManager` is created inside SequentialStrategy, not as a separate module, to keep imports minimal and avoid circular dependencies.

### 2.4 Engine Integration Details

**Current engine.py hook (Phase A stub):**
```python
# Lines 269-282: reads selector.current_strategy_name but does NOT call prepare_phase/release_phase
```

**After TASK_DS_EO_044:**
```python
# In execute_transition (before phase transition):
strategy_mgr = ExecutionStrategyManager(workspace_root=ws)
prep = await strategy_mgr.prepare_phase(target_agent)
if not prep.success:
    return TransitionResult(
        success=False,
        error=f"Strategy prepare failed for {target_agent}: {'; '.join(prep.notes)}",
        validation_messages=[f"Strategy: {prep.strategy}, Model status: {prep.model_status}"],
    )

# In transition completion handler (after phase completes):
release = await strategy_mgr.release_phase(target_agent)
```

**Non-breaking change:** If execution strategy import fails, hooks fall through silently (existing behavior). Only when the package is present and a specific strategy is selected do lifecycle operations occur.

---

## 3. SharedModelStrategy — Design

### 3.1 Architecture

SharedModelStrategy **does not unload models**. Instead:

1. On `prepare_for_agent`: Check if target model is already resident → if yes, increment refcount and return; if no, load it once
2. On `release_agent`: Decrement refcount → if zero, schedule async unload (but wait for all active agents to finish first)
3. The "all roles share same model" case: when CTO/Implementer/Reviewer all have the same `model` field, only one load happens

### 3.2 Implementation Notes

```python
class SharedModelStrategy(ExecutionStrategy):
    """Single model loaded once, shared across agents.
    
    Ref-counting ensures we don't unload while any agent is active.
    State: {model_name: refcount} + current_model tracker.
    """
    
    _ref_counts: dict = {}  # model → count
    _lock = asyncio.Lock()
```

This is simpler than SequentialStrategy because there's no state machine — just ref counting. The complexity is in the release path: we need to detect when ALL agents have released so unloading can proceed safely.

---

## 4. Skill Command — `/eo execution strategy <mode>`

### 4.1 Behavior

```
/eo execution strategy auto       → clear manual override, re-run capability assessment
/eo execution strategy concurrent → persist override to STRATEGY_OVERRIDE.json
/eo execution strategy sequential → persist override, warn if on constrained hardware  
/eo execution strategy shared_model → persist override, confirm model alignment
```

### 4.2 Implementation

This is a new skill definition that calls `ExecutionStrategySelector.set_manual_override()` and then `strategy_mgr.switch_strategy()`. The override persists across DS-EO restarts (written to workspace config).

---

## 5. Acceptance Criteria

### 5.1 Functional

- [ ] SequentialStrategy: full lifecycle works — ensure_ready → /api/ps verify → release_model → unloading confirmed
- [ ] SequentialStrategy: if model is already loaded, prepare returns success with "already resident" note (no redundant load)
- [ ] SequentialStrategy: unload verification polls /api/ps with 500ms intervals, 30s timeout; warning logged if eviction delayed
- [ ] SharedModelStrategy: ref-counting works — two agents share one model, both released → model stays loaded until all release
- [ ] ConcurrentMode: zero behavioral change (same as Phase A)
- [ ] Auto-detection still works (CapabilityAssessor unchanged)
- [ ] Manual override via selector persists across ExecutionStrategyManager re-instantiation

### 5.2 Integration

- [ ] engine.py calls prepare_phase before transition, release after completion
- [ ] Strategy failures in engine produce TransitionResult with error + model_status details
- [ ] Non-fatal fallback still works (if package import fails)
- [ ] Skill command /eo execution strategy sets override + logs change

### 5.3 Quality

- [ ] All new unit tests pass: SequentialStrategy lifecycle (≥6 tests), SharedModelStrategy refcount (≥4 tests), engine integration (≥3 tests)
- [ ] Full test suite (Phase A + Phase B): ≥ 40 tests total, all passing
- [ ] No regressions in existing Phase A tests

### 5.4 Documentation

- [ ] Migration guide for existing users (sequential/shared_model adoption paths)
- [ ] README update for execution_strategy/ package
- [ ] Config schema documented with strategy field examples

---

## 6. File-by-File Plan (Exact Guidance)

### 6.1 NEW: `dispatcher/execution_strategy/sequential_strategy.py` (~400 lines)

**Lines 1-50:** Module docstring, imports (asyncio, logging, os, time, typing)

**Lines 51-200:** `_ModelLifecycleManager` internal class
- Line 55: `__init__`: `_state="idle", _current_model=None, _lock=Lock()`
- Lines 60-90: `ensure_ready(model_name)` — state machine entry point
  - idle → verify installed → check loaded via `/api/ps` → if not loaded, load it
  - loading → ready with StrategyResult
- Lines 95-130: `_load_model(model_name)` — call `ollama show` to verify installed, then trigger load (via Ollama API or process spawn)
- Lines 135-165: `_verify_loaded(model_name, timeout_s=30)` — poll `/api/ps`, 500ms interval
- Lines 170-200: `release_model(model_name)` → state unloading → call unload endpoint → verify unloading

**Lines 201-400:** `SequentialStrategy` public class (implements ExecutionStrategy)
- Line 205: `__init__(workspace_root)` — instantiate `_ModelLifecycleManager`
- Lines 210-260: `prepare_for_agent(agent_id)` → resolve model via registry → call lifecycle.ensure_ready → return StrategyResult with strategy="sequential"
- Lines 265-300: `release_agent(agent_id)` → resolve model → call lifecycle.release_model → return StrategyResult  
- Lines 305-315: `can_support_concurrent_agents()` → return False
- Lines 320-350: `assess_capability()` → CapabilityReport with strategy="sequential", confidence=1.0 (always available, just slower)

### 6.2 NEW: `dispatcher/execution_strategy/shared_model_strategy.py` (~250 lines)

**Lines 1-40:** Module docstring, imports

**Lines 41-180:** `SharedModelStrategy` class
- Line 45: `_ref_counts: dict[str, int] = {}`, `_active_agents: set = set()`, `_lock = Lock()`
- Lines 50-100: `prepare_for_agent(agent_id)` → resolve model via registry → acquire lock → check ref_count → if 0, load model → increment ref_count → add agent_id to _active_agents → return StrategyResult with strategy="shared_model"
- Lines 105-150: `release_agent(agent_id)` → acquire lock → decrement ref_count → remove agent_id → if ref_count==0 and no active agents, schedule unload → return StrategyResult

### 6.3 MODIFIED: `dispatcher/engine.py` (lines ~269-282)

Replace Phase A stub with real hook calls:
- Lines 270-285: Replace current `_exec_strategy_name` read with actual async prepare_phase call before transition validation, and release_phase in the completion path
- Preserve non-fatal fallback (try/except around import + calls)

### 6.4 MODIFIED: `dispatcher/execution_strategy/__init__.py` (~50 lines added)

- Import SequentialStrategy and SharedModelStrategy
- Update `get_or_resolve()` in selector to register new strategies
- Update `__all__` exports

### 6.5 NEW: Test files (3 test modules, ~18 tests total)

| File | Tests | Location |
|------|-------|----------|
| `test/execution_strategy/test_sequential_lifecycle.py` | 6 | SequentialStrategy lifecycle scenarios |
| `test/execution_strategy/test_shared_model_refcount.py` | 4 | SharedModelStrategy ref-counting |
| `test/execution_strategy/test_engine_integration.py` | 3-5 | Engine hook integration |

### 6.6 NEW: Docs

| File | Location |
|------|----------|
| `MIGRATION_GUIDE.md` | task dir / migration guide |
| `README.md` (update) | `dispatcher/execution_strategy/` package README |

---

## 7. Risk Assessment

| Risk | Mitigation |
|------|-----------|
| SequentialStrategy OOM kills on load | Poll /proc/meminfo before loading; refuse if free RAM < min_free_ram_gb threshold |
| /api/ps unload lag causes stale state | 30s timeout with warning; next prepare cycle handles cleanup |
| SharedModel ref-count race condition | asyncio.Lock protects all ref_count mutations |
| Engine integration blocks on model load | Timeout at 60s for ensure_ready; return PhaseError if exceeded |

---

## 8. Timeline Estimate

| Phase | Tasks | Est. Hours |
|-------|-------|-----------|
| SequentialStrategy implementation | ModelLifecycleManager + SequentialStrategy | 6-10 |
| SharedModelStrategy implementation | Ref-counting + release logic | 3-5 |
| Engine integration hooks | Real prepare/release calls in engine.py | 2-3 |
| Skill command | /eo execution strategy handler | 2-3 |
| Tests (unit + integration) | Sequential lifecycle, refcount, engine hooks | 4-6 |
| Docs (migration guide + README update) | Migration paths, config schema, package docs | 2-3 |
| **Total** | | **19-30 hours** |

---

## Gate Status

| Gate | Prerequisite Met? | Notes |
|------|------------------|-------|
| G1 (Plan Review) | Awaiting user approval | Extends TASK_DS_EO_043 Phase A foundation |
| G2 (Implementation) | Pending G1 approval | — |
| G3 (Review) | Pending G2 completion | — |
| G4 (CTO Approval) | Pending G3 approval | — |
| G5 (PM Closure) | Pending G4 approval | — |

---

**End of CTO Plan for TASK_DS_EO_044.**  
Awaiting user approval to proceed to Gate G1 (plan review).
