# Execution Strategy Manager

Manages how LLM models are loaded and released across DS-EO agent phases (G1→G2→G3→G4). Three strategies optimize for different hardware profiles.

## Strategies

| Strategy | Loading Behavior | Hardware Profile | Latency Overhead |
|----------|-----------------|------------------|------------------|
| **concurrent** (default) | All agent models loaded simultaneously | 96GB+ unified memory or discrete GPU | ~0s |
| **sequential** | One model at a time — loads before use, unloads after each phase | Jetson AGX Orin (64GB), single-GPU desktop, edge deployments | +2–5s per phase |
| **shared_model** | Single model shared across all agents via ref-counting | Users configuring identical models for CTO/Implementer/Reviewer/PM | ~0s after first agent |

## Quick Start

Switch modes:
```
/eo execution strategy sequential   # For constrained hardware
/eo execution strategy shared_model # For single-model multi-role setups
/eo execution strategy auto         # Revert to auto-detection
```

Or set a persistent override in `STRATEGY_OVERRIDE.json` (see Migration Guide for details).

## Architecture

```
ExecutionStrategyManager  ← Public facade (singleton)
    │
    ├── ExecutionStrategySelector  ← Resolution logic (auto vs. manual)
    │     ├── CapabilityAssessor   ← Hardware detection signals
    │     └── STRATEGY_OVERRIDE.json  ← Persistent user override
    │
    ├── ConcurrentStrategy         ← Phase A: foundation + default strategy
    ├── SequentialStrategy         ← Phase B: model lifecycle manager
    └── SharedModelStrategy        ← Phase B: ref-counted model sharing
```

## Public API

### ExecutionStrategyManager (import: `dispatcher.execution_strategy`)

| Method | Description | Called By |
|--------|-------------|-----------|
| `prepare_phase(agent_id)` | Prepare model for agent phase (async) | `engine.py` before transition |
| `release_phase(agent_id)` | Release model resources after phase | `engine.py` after completion |
| `switch_strategy(name)` | User-initiated mode change | Skill command |
| `status_report()` → dict | Current strategy state for monitoring | PM dashboard / skill status |

### ExecutionStrategySelector (import: `dispatcher.execution_strategy`)

| Method | Description |
|--------|-------------|
| `get_or_resolve()` → `(name, impl, CapabilityReport)` | Resolve active strategy (caches result) |
| `set_manual_override(name)` | Persist + apply manual override |
| `clear_override()` | Revert to auto-detection |

## Configuration

Three mechanisms (in priority order):

1. **Skill command:** `/eo execution strategy <mode>` — runtime, persists across restarts
2. **Override file:** `STRATEGY_OVERRIDE.json` — persistent across DS-EO restarts
3. **Auto-detection:** Runs at startup; selects based on system capability assessment

## Monitoring

Watch these INFO-level log messages:
- `"Strategy auto-detected at startup:"` — initial selection
- `"Manual override set to"` — user mode change
- `"/api/ps verified"` — model lifecycle events (sequential mode)
## Phase C — Polish (TASK_DS_EO_045, 2026-08-16)

Phase C delivered the user-facing `/eo execution strategy` skill commands:
- Runtime mode switching without restart (`auto`, `concurrent`, `sequential`, `shared_model`)
- Status reporting with capability assessment details and lifecycle state
- Startup eager auto-detection (strategy resolved at ExecutionStrategyManager init time)
- Migration guide, benchmarking guidance, and monitoring patterns

Phase C is documentation + skill polish — no new strategy implementations.

## Tests

53 tests total across Phases A + B. All passing.
Phase C added skill commands (no new strategy tests needed).
See `test/execution_strategy/` for the full test suite.

## Migration

For adoption paths, benchmarks, and troubleshooting:
[Migration Guide](../../docs/development/reports/TASK_DS_EO_044_MODEL_LIFECYCLE_IMPLEMENTER/MIGRATION_GUIDE.md)
