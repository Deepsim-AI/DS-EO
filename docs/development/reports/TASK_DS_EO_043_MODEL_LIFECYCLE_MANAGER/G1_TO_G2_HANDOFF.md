# G1 → G2 Handoff — TASK_DS_EO_043 Phase A

**To:** Implementer 💻 (ollama/ornith:35b)  
**From:** CTO 🏗️ (ollama/qwen3.6:35b)  
**Date:** 2026-08-14 07:40 PDT  
**Scope:** Phase A only (Foundation)  

## Authority

CTO_APPROVAL.md in this task directory grants Phase A approval. Do NOT proceed to Phase B/C without explicit CTO instruction.

## Read This First

1. **Read the full plan:** `CTO_PLAN.md` — 888 lines. You MUST read every section.
2. **This handoff** provides the deliverable checklist and constraints.
3. **Source of truth for DS-EO governance:** AGENTS.md (workspace root). Read it in full before touching any code.

## Phase A Deliverables

### Deliverable 1: `dispatcher/execution_strategy/__init__.py`

```python
"""Execution Strategy Manager — Phase A."""
from .constants import Strategy, ModelState, ModelStateError
from .strategy_base import ExecutionStrategy, StrategyResult, CapabilityReport
from .concurrent_strategy import ConcurrentStrategy
from .capability_assessor import CapabilityAssessor
from .selector import ExecutionStrategySelector

__all__ = [
    "ExecutionStrategy",
    "StrategyResult",
    "CapabilityReport",
    "ConcurrentStrategy",
    "CapabilityAssessor",
    "ExecutionStrategySelector",
    "Strategy",
    "ModelState",
]
```

### Deliverable 2: `dispatcher/execution_strategy/constants.py`

- `class Strategy(str, Enum): CONCURRENT = "concurrent"; SEQUENTIAL = "sequential"; SHARED_MODEL = "shared_model"`
- `class ModelState(str, Enum): UNLOADED | LOAD_REQUIRED | LOADING | READY | BUSY | UNLOADING | ERROR`
- `MODEL_LOAD_TIMEOUT_SECONDS = 60`
- `UNLOAD_POLL_INTERVAL_MS = 500`
- `MIN_FREE_RAM_GB = 8`
- `AUTO_DETECTION_SIGNALS:` list of named tuples for each signal (memory, VRAM, unified vs discrete, model sizes, active models count)

### Deliverable 3: `dispatcher/execution_strategy/strategy_base.py`

Pure abstract base class. Exact contract from CTO_PLAN.md §5.1 — do NOT modify the interface. Copy the ABC definition verbatim from the plan. This is the non-negotiable contract.

### Deliverable 4: `dispatcher/execution_strategy/concurrent_strategy.py`

- Copy `ConcurrentStrategy` class from CTO_PLAN.md §5.2
- Must import and wrap existing `SessionSpawnManager` (find its location via `grep` in current codebase — do NOT modify it)
- The `prepare_for_agent` method resolves agent → model from registry, calls existing spawn, returns StrategyResult
- **Zero behavioral change.** If someone runs concurrent mode today, nothing changes except the result has an extra `strategy: "concurrent"` field

### Deliverable 5: `dispatcher/execution_strategy/capability_assessor.py`

Implement auto-detection logic from CTO_PLAN.md §4.1. This is pure detection — no lifecycle management here.

Required detection signals (implement each as a method):
1. `detect_total_memory()` → read `/proc/meminfo` or use `psutil`
2. `detect_gpu_vram()` → `nvidia-smi` for discrete GPU, None for CPU/unified
3. `detect_memory_type()` → check `/dev/dri`, `lspci`, or Python's `platform` module for unified memory
4. `get_configured_model_sizes()` → resolve agent models via existing registry, get file sizes via `ollama show --format json`
5. `count_active_loaded_models()` → GET `/api/ps` from Ollama
6. `count_distinct_agent_models()` → iterate agents_list.json

Decision logic: exactly the decision matrix from CTO_PLAN.md §4.1, implemented as a classmethod returning `CapabilityReport`.

### Deliverable 6: `dispatcher/execution_strategy/selector.py`

- Singleton `ExecutionStrategySelector` per CTO_PLAN.md §5.5
- Config path for persistence: look up existing DS-EO config file pattern (check `ds_eo_config.yaml`, `config-templates/`, and any existing config in workspace root)
- Override stores to a field in the config under `execution.overrides.persistent`
- Manual override via `set_manual_override(strategy_name)` that persists + updates `_selected_strategy_name` + logs
- Clear override via `clear_override()` that removes persisted + re-runs auto-detection

### Deliverable 7: Update `dispatcher/engine.py`

Find the existing phase transition method (likely named `transition_to_agent` or similar — grep for it in the current codebase). Add two hooks:

```python
# BEFORE the spawn call:
strategy_mgr = ExecutionStrategyManager()  # singleton, lazy-init
prep = await strategy_mgr.prepare_phase(agent_id)
if not prep.success:
    logger.error(f"Strategy prepare failed for {agent_id}: {prep.notes}")
    raise PhaseError(f"Model lifecycle error: {prep.notes[0]}")

# AFTER the session completion (in the completion handler/callback):
release = await strategy_mgr.release_phase(agent_id)
```

**Do NOT modify anything else in engine.py.** The existing spawn logic stays exactly as-is.

### Deliverable 8: Unit Tests (`test/execution_strategy/`)

```
test/execution_strategy/
├── __init__.py
├── test_concurrent_identity.py   # Verify no behavioral change
├── test_capability_assess.py     # Mock hardware signals → assert correct strategy
├── test_selector_override.py     # Override persists to config, clears correctly
└── test_strategy_interface.py    # All strategies implement ABC contract
```

Each test must:
- Use `pytest` + `unittest.mock` (no real Ollama calls during unit tests)
- Assert on StrategyResult fields (success, strategy, model_status)
- Cover both happy path and at least one failure case per test

### Deliverable 9: Log Templates

```
docs/development/reports/TASK_DS_EO_043_MODEL_LIFECYCLE_MANAGER/AUTO_SELECTION_LOG.md
docs/development/reports/TASK_DS_EO_043_MODEL_LIFECYCLE_MANAGER/OVERRIDE_LOG.md
```

Both are templates — the Selector will populate them at runtime. The template documents the format.

### Deliverable 10: Config Example Update

Add execution strategy config to the existing DS-EO config example (find it in `config-templates/` or workspace root):

```yaml
execution:
  strategy: auto
  auto_assessment:
    enabled: true
    fallback_on_failure: sequential
  memory_safety:
    min_free_ram_gb: 8
    unloading_aggressive: false
  logging:
    level: INFO
    log_dir: docs/development/reports/TASK_DS_EO_043_MODEL_LIFECYCLE_MANAGER/
```

## Constraints (from AGENTS.md)

- **Model pressure:** Unload laguna-xs-2.1 + gpt-oss:20b before starting; keep nomic-embed-text loaded
- **No wholesale file reads:** Files over 50KB → use grep, targeted line reads only
- **Exact paths matter:** Every file path is specified above — no guessing locations
- **Registry location:** Find existing `AgentRegistry` via `grep -r "class AgentRegistry" dispatcher/` before writing any code that uses it
- **SessionSpawnManager location:** Find via `grep -r "class SessionSpawnManager" dispatcher/` — use as-is, never modify

## Implementation Order (sequential — do not parallelize)

1. constants.py (types only — no logic)
2. strategy_base.py (ABC contract)
3. concurrent_strategy.py (reads existing codebase to find references)
4. capability_assessor.py (pure detection — no lifecycle state)
5. selector.py (singleton + persistence)
6. __init__.py (exports)
7. Update engine.py (find hooks, add prepare/release calls)
8. All tests (parallel writing OK; sequential running to verify pass)
9. Log templates
10. Config example update

## Completion Criteria

Every item on the G2 Gate Checklist in `GATE_AUTHORITY_MATRIX.md` must be satisfied:
- [ ] Code changes applied per CTO_PLAN.md scope (all 10 deliverables)
- [ ] All existing tests still passing
- [ ] IMPLEMENTATION_REPORT.md filled with files changed, design decisions, test results, known limitations
- [ ] No unresolved TODOs/FIXMEs that block verification
- [ ] Artifacts carry required metadata (`agent_id: "implementer"`, `produced_at: timestamp`)

When all deliverables are complete and tests pass, produce IMPLEMENTATION_REPORT.md in the task directory and return to CTO.
