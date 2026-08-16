# G1 → G2 Handoff — TASK_DS_EO_045: Execution Strategy Polish

**Approved by:** User 2026-08-16 07:56 PDT  
**Handoff to:** Implementer 💻  
**Scope per CTO_PLAN.md §9:** Low-risk polish on existing foundation  

---

## Deliverables to Implement

### 1. Skill Commands (`skills/eo/SKILL.md` — add ~30 lines)

Add new section "## Execution Strategy Commands" after existing commands:

```markdown
### `/eo execution strategy <mode>`

Switch the execution strategy mode (model loading behavior). This is separate from `/eo mode`, which controls workflow gate automation.

| Command | Effect |
|---------|--------|
| `/eo execution strategy auto` | Clear manual override, re-run capability assessment at next phase |
| `/eo execution strategy concurrent` | Force all agents to load models simultaneously |
| `/eo execution strategy sequential` | One model at a time — safer on constrained hardware (~2–5s per phase transition) |
| `/eo execution strategy shared_model` | All roles share one model instance (requires all agents configured with same model) |

**Response format:**
```
✅ Execution strategy changed: concurrent → sequential
Source: user_override
Active strategies: 3 available (concurrent, sequential, shared_model)
Note: Sequential mode adds ~2–5s per phase for model lifecycle management.
```

### `/eo execution strategy status`

Display current strategy configuration and model state. No side effects — read-only.

**Response format:**
```
Active Strategy: concurrent (auto-selected)
Capability Confidence: 1.0
Lifecycle State: {state, current_model, ...}
```
```

Implementation approach for the skill:
- The skill wraps `ExecutionStrategyManager.switch_strategy()` and `status_report()`
- On `auto`: call `selector.clear_override()`, log INFO confirmation
- On `concurrent/sequential/shared_model`: call `selector.set_manual_override(mode)`, log with appropriate warnings (sequential warns about latency, shared_model confirms model alignment)
- Status command reads from `ExecutionStrategyManager.status_report()` and formats the dict

### 2. Startup Eager Detection (`dispatcher/execution_strategy/__init__.py` — add ~5 lines)

In `ExecutionStrategyManager.__init__()`, after existing initialization:

```python
# Phase C: eager auto-detection at startup (not lazy)
if not self._initialized:
    name, impl, report = self.selector.get_or_resolve()
    logger.info(f"Strategy auto-detected at startup: {name} (source: {report.source})")
```

**Note:** `get_or_resolve()` is called once during init — the result is cached in the selector's `_selected_strategy_name`, so subsequent `prepare_phase` calls don't re-detect.

### 3. Package README (`dispatcher/execution_strategy/README.md` — new file, ~80 lines)

Structure:
```markdown
# Execution Strategy Manager

Three strategies for managing model loading across DS-EO agent phases:

1. **concurrent** (default on capable hardware) — All models loaded simultaneously
2. **sequential** (Jetson/constrained systems) — One model at a time, explicit lifecycle via `/api/ps`
3. **shared_model** (single-model multi-role) — Ref-counted single model shared across all agents

## Quick Start

Switch modes with `/eo execution strategy <mode>` or set `STRATEGY_OVERRIDE.json`.
See [Migration Guide](../../development/reports/TASK_DS_EO_044_MODEL_LIFECYCLE_IMPLEMENTER/MIGRATION_GUIDE.md) for adoption paths.

## Architecture

```
ExecutionStrategyManager (facade)
  └── ExecutionStrategySelector (auto/multi-strategy resolution)
        ├── ConcurrentStrategy (identity wrap, Phase A)
        ├── SequentialStrategy (ModelLifecycleManager, Phase B)
        └── SharedModelStrategy (ref-counted sharing, Phase B)
```

## Public API

- `ExecutionStrategyManager(workspace_root)` — Singleton facade
  - `prepare_phase(agent_id)` → StrategyResult — called before agent phase
  - `release_phase(agent_id)` → StrategyResult — called after agent phase  
  - `switch_strategy(name)` → None — user-initiated mode change
  - `status_report()` → dict — current state for monitoring

- `ExecutionStrategySelector(workspace_root)` — Resolution logic
  - `get_or_resolve()` → (name, impl, CapabilityReport)
  - `set_manual_override(name)` → persist + apply
  - `clear_override()` → revert to auto-detection
```

### 4. Migration Guide Updates (`TASK_DS_EO_044/MIGRATION_GUIDE.md` — add ~25 lines)

Add two new sections:

#### Monitoring & Troubleshooting
- Log messages to watch for at INFO level: `"Strategy auto-detected at startup:"`, `"Manual override set to"`, `"/api/ps verified"`
- If auto-detection picks wrong mode, use `/eo execution strategy` command or clear `STRATEGY_OVERRIDE.json`

#### Benchmarking
- How to measure phase transition overhead per mode (set override, time G1→G2 transitions via logs)
- Expected baselines: concurrent (~0s), sequential (+2–5s/phase), shared_model (~0s after first agent)

---

## Constraints

- Follow the exact line guidance in CTO_PLAN.md §6
- No behavioral changes to existing strategies (Phase A/B code untouched)
- Zero test changes needed — all additions are doc/command/logging only
- Non-fatal: if `dispatcher/execution_strategy` import fails, behavior is unchanged

## Implementation Order

1. Package README (doc-only, no risk)
2. Migration guide updates (doc-only, no risk)  
3. Startup eager detection (5 lines in __init__)
4. Skill commands (new section in SKILL.md)

**End of G1→G2 handoff.**
