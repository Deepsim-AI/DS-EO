# G1 → G2 Handoff — TASK_DS_EO_044

**Handoff Date:** 2026-08-15 10:55 PDT  
**CTO:** 🏗️ approved Phase B scope  
**Implementer:** 💻  

---

## Approved Scope (Per CTO_PLAN.md §9 Phase B)

Build the two missing strategy implementations and integrate them into the engine. **No changes to existing Phase A code.**

### Deliverables

| # | Deliverable | Type | File Path |
|---|------------|------|-----------|
| 1 | SequentialStrategy (with internal ModelLifecycleManager) | NEW | `dispatcher/execution_strategy/sequential_strategy.py` |
| 2 | SharedModelStrategy (ref-counted shared model) | NEW | `dispatcher/execution_strategy/shared_model_strategy.py` |
| 3 | Engine integration hooks (real prepare/release) | MODIFIED | `dispatcher/engine.py:269-285` + completion path |
| 4 | Update package exports | MODIFIED | `dispatcher/execution_strategy/__init__.py` |
| 5 | Unit tests (~18 tests) | NEW | `test/execution_strategy/` (3 files) |
| 6 | Migration guide | NEW | `MIGRATION_GUIDE.md` in task dir |

---

## Existing Architecture (DO NOT MODIFY)

### Base Classes & Types (READ-ONLY reference)
```
dispatcher/execution_strategy/strategy_base.py    — ExecutionStrategy ABC, StrategyResult, CapabilityReport
dispatcher/execution_strategy/constants.py         — Strategy enum, ModelState enum, ModelStateError
```

### Phase A Implementations (READ-ONLY reference for patterns)
```
dispatcher/execution_strategy/concurrent_strategy.py   — Pattern for strategy implementation
dispatcher/execution_strategy/capability_assessor.py   — /api/ps polling pattern (500ms intervals)
dispatcher/execution_strategy/selector.py              — get_or_resolve(), set_manual_override()
dispatcher/execution_strategy/__init__.py              — ExecutionStrategyManager facade, singleton
```

### Engine Integration Point (to MODIFY)
```
dispatcher/engine.py lines 269-285: Replace stub with real hook calls
```

---

## Implementation Rules

1. **New files only** — no editing existing Phase A files except `__init__.py` and `engine.py` as noted
2. **Follow ConcurrentStrategy patterns** — use the same imports, logging style, error patterns
3. **Thread safety** — all lifecycle methods must acquire `asyncio.Lock` before mutating state
4. **Error handling** — ModelStateError from constants.py for typed failures; StrategyResult with success=False for non-fatal issues
5. **Tests must be importable** — `python -m pytest test/execution_strategy/ -v` must pass

---

## SequentialStrategy Implementation Notes (from CTO_PLAN.md §2)

### _ModelLifecycleManager states
```
idle → loading → ready → executing → unloading → idle
```

### Key methods to implement:
- `ensure_ready(model_name)` — main entry, handles full lifecycle
- `_load_model(model_name)` — verify installed via ollama show, then load
- `_verify_loaded(model_name, timeout_s=30)` — poll /api/ps with 500ms intervals
- `release_model(model_name)` → unloading → verify unloaded

### Engine integration (dispatcher/engine.py):
```python
# Before transition validation:
strategy_mgr = ExecutionStrategyManager(workspace_root=ws)
prep = await strategy_mgr.prepare_phase(target_agent)
if not prep.success:
    return TransitionResult(success=False, error=f"Strategy prepare failed...", ...)

# After phase completion (in completion handler):
release = await strategy_mgr.release_phase(target_agent)
```

---

## SharedModelStrategy Notes (CTO_PLAN.md §3)

- `_ref_counts: dict[str, int]` — model name → active agent count
- `_active_agents: set` — track which agents currently hold refs
- On prepare: load once if refcount==0, increment refcount, add to _active_agents
- On release: decrement refcount, remove from _active_agents; unload only when both are empty

---

**End of handoff.** Implementer should work SequentialStrategy first, then SharedModelStrategy, then engine integration. Return to CTO for review after all deliverables are complete.
