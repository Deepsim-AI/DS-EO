# Migration Guide — Execution Strategy Manager (Phase B)

**Task:** TASK_DS_EO_044  
**Date:** 2026-08-16  
**Author:** CTO 🏗️  
**Applies to:** Users upgrading from TASK_DS_EO_043 Phase A or running concurrent mode today

---

## What Changed in Phase B

Phase A (TASK_DS_EO_043) delivered the **foundation**: `ExecutionStrategy` base class, `ConcurrentStrategy`, `CapabilityAssessor`, and selector singleton. It auto-detected system capabilities and defaulted to concurrent mode when possible.

**Phase B (TASK_DS_EO_044) adds two new strategy implementations:**

| Strategy | What It Does | When to Use |
|----------|-------------|-------------|
| `concurrent` (existing) | All agent models loaded simultaneously | Systems with 96GB+ unified memory or discrete GPU |
| **`sequential`** (new) | One model at a time — loads before use, unloads after each phase | Jetson AGX Orin (64GB), single-GPU desktops, edge deployments |
| **`shared_model`** (new) | All roles share the SAME model — no unloading, ref-counted | Users who intentionally use one model across all agents |

**No behavioral change if you stay on `concurrent` mode.** This is an additive release.

---

## Adoption Paths

### Path 1: Sequential Mode (Constrained Hardware)

**Recommended for:** Systems with < 96GB unified memory, or systems where loading two large models simultaneously causes OOM/swapping.

**Before Phase B:** Your system would either run concurrent and risk memory pressure, or crash with `MODEL_LOAD_TIMEOUT`.

**After Phase B:** The `SequentialStrategy` manages a strict lifecycle:
1. Before each agent phase → loads the target model (if not already resident)
2. After each phase → unloads it (polling `/api/ps` every 500ms, timeout 30s)
3. Only one large model is ever resident at a time

**How to adopt:**

#### Option A: Config override (recommended for persistent change)
Create or edit `STRATEGY_OVERRIDE.json` in your task directory:

```json
{
  "strategy": "sequential",
  "source": "user_override",
  "persisted_at": "2026-08-16T07:30:00Z"
}
```

Or set the environment variable before starting DS-EO:
```bash
export DS_EO_EXECUTION_STRATEGY=sequential
```

#### Option B: Manual override after startup
Once DS-EO is running, use the selector API (from any agent session):
```python
from dispatcher.execution_strategy import ExecutionStrategyManager
mgr = ExecutionStrategyManager()
await mgr.switch_strategy("sequential")
```

**What to expect:** Each phase transition will add ~2–5s latency for model load/unload. Phase G1 planning through G4 approval may take 15–25s longer total, but memory pressure is eliminated.

---

### Path 2: Shared Model Mode (Single Model for All Roles)

**Recommended for:** Users who intentionally configure the same model (e.g., `qwen3.6:35b`) for CTO/Implementer/Reviewer/PM agents — or who want to benchmark a single model across different prompts.

**How it works:**
- First agent to `prepare_for_agent()` loads the model
- Subsequent agents increment a ref-count; no redundant loads
- When all agents have released, the model unloads
- If agents overlap (concurrent session phases), they share one resident copy

**How to adopt:**

```json
{
  "strategy": "shared_model",
  "source": "user_override"
}
```

**Prerequisite:** All four agents must have `model` set to the same value in your agent config (`openclaw.json`). If agents reference different models, only the first-encountered model will be loaded and shared.

**What to expect:** Memory usage is minimal (one model in RAM). However, all agents share the same "mental state" — context from one agent's session can bleed into another's if phases overlap.

---

### Path 3: Stay on Concurrent (No Action Required)

If you're running concurrent mode today and your system handles it well:
- **No changes needed.** Phase B does not alter `ConcurrentStrategy` behavior.
- The selector still checks for Phase A capabilities — if they exist, concurrent remains the default.
- Auto-detection thresholds are unchanged.

---

## Switching Between Modes at Runtime

You can switch modes without restarting DS-EO using the `/eo execution strategy` skill command:

| Command | Effect |
|---------|--------|
| `/eo execution strategy auto` | Clear manual override, re-run capability assessment |
| `/eo execution strategy concurrent` | Force concurrent mode |
| `/eo execution strategy sequential` | Force sequential mode (warns if on constrained hardware) |
| `/eo execution strategy shared_model` | Force shared model mode |

The override persists to `STRATEGY_OVERRIDE.json` and survives DS-EO restarts.

---

## Configuration Reference

### STRATEGY_OVERRIDE.json

Located in: `docs/development/reports/TASK_DS_EO_043_MODEL_LIFECYCLE_MANAGER/STRATEGY_OVERRIDE.json` (default, relative to workspace root).

```json
{
  "strategy": "<concurrent | sequential | shared_model>",
  "source": "user_override",
  "persisted_at": "<ISO-8601 timestamp>",
  "workspace_root": "<absolute path to workspace>"
}
```

### Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `DS_EO_EXECUTION_STRATEGY` | Force strategy on startup | `sequential` |
| `DS_EO_STRATEGY_OVERRIDE_PATH` | Custom override file location | `/tmp/strategy_override.json` |

### Agent Config (openclaw.json)

No changes needed to `openclaw.json`. The execution strategy manager is independent of the agent model config. However, your agent's `model` field should be set correctly for proper lifecycle management:

```json
{
  "agents": [
    {
      "id": "cto",
      "model": "ollama/qwen3.6:35b"
    },
    {
      "id": "implementer",
      "model": "ollama/qwen3.8:27b"
    }
  ]
}
```

The strategy manager reads model names from `dispatcher/registry` (which sources from agent config). If a model name is unresolved, the lifecycle operations fall back gracefully.

---

## Troubleshooting

### Sequential Mode Issues

**Problem:** Model load takes >30s or times out  
**Check:**
- Is the model installed? Run `ollama list` to verify
- Does the model name exactly match your agent config? Check for typos (e.g., `qwen3.6:35b` vs `qwen3.6`)
- Is `/api/ps` reachable? Test: `curl http://127.0.0.1:11434/api/ps`

**Problem:** Model not unloading after phase  
**Check:**
- Check DS-EO logs for `unload delayed (warning logged)` messages
- On next phase, the stale model is automatically evicted before loading the new one
- If this keeps happening, verify your Ollama version supports `keep_alive=0`

**Problem:** `INSUFFICIENT_MEMORY` error  
**Cause:** Free RAM < 8GB (`MIN_FREE_RAM_GB` threshold in constants)  
**Fix:** Close other memory-heavy processes, or switch to `shared_model` mode

### Shared Model Mode Issues

**Problem:** Agents using different models but shared mode is active  
**Effect:** Only the first-encountered model is loaded; others resolve at runtime and may fail  
**Fix:** Align all agent `model` fields in your config to the same value before switching to `shared_model`

**Problem:** Model stays resident after all agents released  
**Cause:** Active session still holds a reference (e.g., PM dashboard query)  
**Fix:** Wait for all sessions to complete, or restart DS-EO

### Concurrent Mode Issues

**Problem:** OOM killing during concurrent phase  
**Cause:** Your system does not actually support concurrent model residency despite Phase A detection  
**Fix:** Switch to `sequential` mode (see Path 1 above) — this is a known limitation of CPU-only systems with <96GB memory

---

## Test Suite

Phase B adds 23 new tests (total: 53 passing):

| Test Module | Tests | Covers |
|-------------|-------|--------|
| `test_sequential_lifecycle.py` | 14 | Full lifecycle, short-circuit when resident, unload verification, state transitions |
| `test_shared_model_refcount.py` | 7 | Ref-counting, lazy unload, concurrent access |
| `test_engine_strategy_integration.py` | 3+2 | Engine hook ordering, sync-to-async bridge, failure fallback |

Run tests:
```bash
cd /home/deepsim/ds_eo_openclaw
python -m pytest test/execution_strategy/ -v
```

---

## Migration Checklist

Use this checklist when upgrading to Phase B:

- [ ] Run Phase A test suite (30 tests) — verify no regressions
- [ ] Run full test suite (53 tests) — all should pass
- [ ] Choose strategy mode appropriate for your hardware
- [ ] Set override via config file, env var, or skill command
- [ ] Test one phase transition end-to-end (e.g., G1 → G2 with new mode)
- [ ] Monitor logs for lifecycle messages (`loaded and verified`, `released`, etc.)
- [ ] Adjust expectations: sequential mode adds ~2–5s per phase transition

---

## FAQ

**Q: Do I need to re-install anything?**  
A: No. Phase B is additive — new files in `dispatcher/execution_strategy/`. No existing files are modified.

**Q: Can I switch modes during a task?**  
A: Yes, but not mid-phase. Switch between tasks or after all agents have released. The selector's `switch_strategy()` method handles this safely.

**Q: What happens if Ollama is not running?**  
A: Both new strategies gracefully fall back: `_trigger_load` assumes the model will load on first inference (same as concurrent mode), and `_verify_loaded` logs a debug message but doesn't fail the phase.

**Q: Is shared_model safe for production use?**  
A: It's designed for intentional single-model setups. For most multi-agent workflows, `sequential` mode provides better isolation with acceptable latency tradeoff. Use `shared_model` when you specifically want shared state between roles.

---

*End of Migration Guide — TASK_DS_EO_044 Phase B*

---

## Monitoring & Troubleshooting

### Log Messages to Watch For

All execution strategy operations log at INFO level. In production, grep logs for:

| Pattern | Meaning | Action if Unexpected |
|---------|---------|---------------------|
| `"Strategy auto-detected at startup:"` | Initial selection | Verify it picked the right mode for your hardware |
| `"Manual override set to"` | User mode change | Confirm this was intentional |
| `"/api/ps verified"` | Model loaded successfully (sequential) | Normal — no action needed |
| `"Model ... unloaded"` / `"unload delayed"` | Lifecycle completion | "delayed" means model may still be resident; next phase will clean up |
| `"Failed to unload previous model"` | Unload didn't complete in time | Non-fatal — proceed; cleanup handled on next cycle |
| `"Execution mode: ... (source: auto)"` | Auto-selected at prepare_phase | Verify strategy is correct for your setup |

### Where Logs Appear

Logs flow through Python's standard `logging` module, level INFO. Check:
- Gateway logs (if running in webchat/TUI)
- DS-EO supervisor logs if run as daemon service
- File output configured via gateway log settings

### Benchmarking Guide

To measure per-mode overhead on your system:

1. **Set a mode override** using `/eo execution strategy <mode>` or `STRATEGY_OVERRIDE.json`
2. **Run a G1→G2 transition cycle** and note the phase transition time in logs
3. **Compare across modes** (run each mode at least 3 times, take average)

#### Expected Baselines (CPU-only, ~8GB model):

| Mode | Prepare Time | Release Time | Total Phase Overhead |
|------|-------------|--------------|---------------------|
| concurrent | ~0s (no-op) | ~0s (no-op) | ~0s |
| sequential | 2–5s (load + verify) | 1–3s (unload + verify) | 3–8s per phase |
| shared_model | 2–5s (first agent only) | ~0s (ref > 0) | ~0s after first |

#### Tools:
- **Ollama memory:** `curl http://127.0.0.1:11434/api/ps` — shows loaded models and their resident size
- **System RAM:** `free -h` or `/proc/meminfo` — track free RAM before/after transitions
- **DS-EO log timestamps:** compare `prepare_phase()` call time vs. completion timestamp

