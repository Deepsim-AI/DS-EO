# Deliverable E — DSH Edition vs OpenClaw Edition Comparison Matrix

**TASK_ID:** `TASK_DS_EO_DSH_008`  
**Date:** 2026-09-29  

---

## Purpose

This matrix compares the behavior of DS-EO DSH Edition against the original DS-EO OpenClaw Edition across all RuntimeAPI methods, demonstrating what has been migrated and what remains pending.

---

## Method-by-Method Parity Analysis

### Session Lifecycle (A1, A3)

| Method | OpenClaw Behavior | DSH Adapter Current | Parity Status |
|--------|-------------------|---------------------|---------------|
| `compact_session(session_key)` | Queries session store via sessions_list CLI → compacted if found. Returns ActionResult(success=True/False, context_size_kb, tokens_compacted) | Stub: returns ActionResult(success=False, error="DSH adapter not yet implemented") | ❌ **NOT IMPLEMENTED** |
| `archive_session(session_key, dest_dir)` | Archives session trajectory via sessions_list → export-trajectory flow. Returns ActionResult with output_path | Stub: returns ActionResult(success=False, error) | ❌ **NOT IMPLEMENTED** |
| `close_session(session_key)` | Closes session via sessions_close. Returns ActionResult(success=True/False) | Stub: returns ActionResult(success=False, error) | ❌ **NOT IMPLEMENTED** |
| `get_session_info(session_key)` | Queries session metadata (context_size_bytes, turn_count, last_turn_time). Returns RuntimeSession or None | Stub: returns None (placeholder) | ❌ **NOT IMPLEMENTED** |

### Session Spawning & Dispatch (A6, D2)

| Method | OpenClaw Behavior | DSH Adapter Current | Parity Status |
|--------|-------------------|---------------------|---------------|
| `spawn_session(config)` | Invokes sessions_spawn via Path A (gateway tool_call) or Path B (REST API). Returns SpawnOutcome with session_key, run_id | Stub: returns ActionResult(success=False, error) | ❌ **NOT IMPLEMENTED** |
| `submit_task(task, role, plan)` | Routes through dispatcher engine. Creates S0_OPEN state → delegates to CTO (S1) via sessions_spawn | Stub: returns ActionResult(success=False, error) | ❌ **NOT IMPLEMENTED** |

### Tool Execution (A2, A8)

| Method | OpenClaw Behavior | DSH Adapter Current | Parity Status |
|--------|-------------------|---------------------|---------------|
| `run_tools(session_key, tool_name, tool_args, policy)` | Checks gateway.tools.allow/deny policy → invokes tool via /tools/invoke endpoint | Stub: returns ActionResult(success=False, error) | ❌ **NOT IMPLEMENTED** |
| `run_task(tool, args)` | Replaces subprocess.run in release_manager.py. Maps to DSH hook/tool execution system | Stub: returns ActionResult(success=False, error) | ❌ **NOT IMPLEMENTED** |

### Model Registry (A5, A9)

| Method | OpenClaw Behavior | DSH Adapter Current | Parity Status |
|--------|-------------------|---------------------|---------------|
| `model_info(model_id)` | Queries ollama list_models → returns RuntimeModel with context_window, max_tokens, gpu_layers, ram_bytes, provider="ollama" | Returns RuntimeModel(id=model_id, context_window=0 placeholder, provider="dsh") | ⚠️ **PARTIAL** — ID and provider correct; metadata fields are placeholders awaiting DSH model catalog |
| `available_models()` | Queries ollama list_models → returns list[RuntimeModel] with real metadata for each model | Returns [] (empty) | ❌ **NOT IMPLEMENTED** |

### Hooks & Bindings (A7)

| Method | OpenClaw Behavior | DSH Adapter Current | Parity Status |
|--------|-------------------|---------------------|---------------|
| `register_binding(command, handler_fn)` | Registers gateway entry-point binding. Returns True on success | Returns True (always — stub). Does nothing | ⚠️ **PARTIAL** — returns correct boolean but registration has no effect |

---

## Summary Statistics

| Metric | Count | Percentage |
|--------|-------|------------|
| Methods with full parity | 0 / 10 | 0% |
| Methods with partial parity | 2 / 10 (model_info, register_binding) | 20% |
| Methods fully stubbed | 8 / 10 | 80% |

---

## Runtime Architecture Comparison

```
OpenClaw Edition:                    DSH Edition:
┌─────────────────────┐             ┌─────────────────────┐
│ DS-EO Core         │             │ DS-EO Core          │
│ (unchanged)        │             │ (unchanged)         │
└────────┬───────────┘             └────────┬───────────┘
         │                                  │
         ▼                                  ▼
┌─────────────────────┐     Migrated      ┌─────────────────────┐
│ RuntimeAPI          │──────────────────▶│ RuntimeAPI          │
│ (Protocol)          │                   │ (Protocol — same)   │
└────────┬───────────┘                   └────────┬───────────┘
         │                                        │
    ┌────┴────┐                              ┌───┴───┐
    │         │                              │       │
    ▼         ▼                              ▼       ▼
┌────────┐ ┌──────────────┐        ┌──────────┐ ┌────────┐
│ DSH    │ │ OpenClaw     │        │ Runtime  │ │ Run-   │
│ Adapter│ │ Legacy       │        │ Factory  │ │ Time   │
│(stubs) │ │ Adapter      │        │          │ │ Adapter│
└────────┘ └──────────────┘        └──────────┘ └────────┘
```

**Key architectural differences:**

1. **DSH Edition adds a RuntimeAdapterFactory** as the single entry point for creating adapters — the OpenClaw Edition had direct instantiation
2. **OpenClaw adapter is retained** in DSH Edition as backward-compatible backend (not removed, not deprecated)
3. **Model resolution** moved from hardcoded `ollama/*` to manifest-driven registry with DSH URI transformation (`dsh://model/...`)
4. **Discovery runtime target** switched from `"openclaw"` to `"dsh"` in discoverer.py (Phase 4)

---

## Parity Achievement Plan

### Immediate (TASK_DS_EO_DSH_009+) — DSH Adapter Implementation
| Priority | Method | Effort | Risk |
|----------|--------|--------|------|
| P1 (critical) | `get_session_info()` | Medium | Low — map DSH session metadata to RuntimeSession |
| P1 (critical) | `compact_session()` | Medium | Low — implement per method stub TODO comment |
| P1 (critical) | `close_session()` | Low | Low — straightforward DELETE mapping |
| P2 | `archive_session()` | Medium | Medium — file export requires DSH filesystem API |
| P2 | `spawn_session()` | High | Medium — requires DSH session creation API |
| P3 | `model_info()`, `available_models()` | Medium | Low — query DSH /models catalog |
| P3 | `submit_task()` | High | High — requires DSH task queue integration |
| P3 | `run_tools()` | High | High — tool execution with policy gate is complex |
| P4 | `run_task()` | Low | Low — maps to DSH hook execution |
| P4 | `register_binding()` | Low | Low — already returns True, needs no functional change |

### Post-Parity (Future)
- When all 10 methods achieve parity → remove `"auto"` fallback, make DSH the only default
- Optional: Phase 7+ — Remove `openclaw_adapter.py` if no longer needed in production

---

<!-- project: github.com/Deepsim-AI/DS-EO -->
