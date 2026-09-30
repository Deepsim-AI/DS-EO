# CTO_PLAN.md — TASK_DS_EO_DSH_010

**Task:** Phase 7: DSH Adapter Implementation — P2+ Methods (Configurable)  
**Author:** CTO (qwen3.6:35b)  
**Date:** 2026-09-29  
**Gate:** G1 — Plan for User Review  

---

## 1. Scope and Approach

Phase 7 continues the pattern established in Phase 6: configurable DSH adapter methods that attempt real API calls when a base_url is configured, and fall back gracefully otherwise. **No live DSH API is assumed.**

### P2 Methods (Medium-High complexity)
| Method | TODO Target Endpoint | Approach |
|--------|---------------------|----------|
| `archive_session()` | POST /sessions/{key}/export-trajectory | Configurable HTTP call → clear error when unavailable |
| `spawn_session()` | POST /sessions/spawn | Configurable HTTP call with config mapping → clear error when unavailable |
| `submit_task()` | POST /tasks/submit (DSH task queue) | Configurable HTTP call → clear error when unavailable |

### P3 Methods (Medium complexity)
| Method | TODO Target Endpoint | Approach |
|--------|---------------------|----------|
| `run_tools()` | Tool execution gateway with policy gate | Policy gate + configurable call → deny/forward to DSH |
| `available_models()` | GET /models (list all) | Configurable HTTP call → populate RuntimeModel list |

### P4 Methods (Low complexity)
| Method | TODO Target Endpoint | Approach |
|--------|---------------------|----------|
| `run_task()` | Hook/tool execution system | Simple configurable wrapper → clear error when unavailable |

### Not Changed in Phase 7
- `register_binding()` — already returns True, no functional change needed (P4, trivial)
- P1 methods (get_session_info, compact_session, close_session, model_info) — already done in Phase 6

---

## 2. Method-by-Method Implementation Scope

### archive_session() [P2]

**Current:** Stub returns `success=False` with "not implemented" message.  
**Phase 7 implementation:**
- Attempt DSH API POST `/sessions/{key}/export-trajectory` with body `{session_key, agent_id, output_path}`
- Parse response: extract `output_path` from DSH response → return `ActionResult(success=True, details={"output_path": path})`
- When unavailable: return `success=False` with clear error message
- Error mapping: HTTP 4xx/5xx → mapped to readable error string

**Complexity:** Medium — straightforward HTTP call + response parsing  
**Risk:** Low — follows existing dsh_http_client.py pattern

### spawn_session() [P2]

**Current:** Stub returns `success=False` with "not implemented" message.  
**Phase 7 implementation:**
- Validate config dict keys (model, workspace_root, etc.) against expected schema
- Attempt DSH API POST `/sessions/spawn` with mapped body `{agent_id, model, workspace_root, ...}`
- Parse response: extract `session_key` or `run_id` → return `ActionResult(success=True, details={"session_key": key})`
- When unavailable: return `success=False` with clear error message

**Complexity:** Medium — requires config validation + mapping from DS-EO config schema to DSH session creation schema  
**Risk:** Low — follows existing pattern; the real complexity is in DSH session creation API which will exist later

### submit_task() [P2]

**Current:** Stub returns `success=False` with "not implemented" message.  
**Phase 7 implementation:**
- Accept task dict, role, optional plan (DSH's task queue schema)
- Map DS-EO task structure → DSH task submission format
- Attempt DSH API POST `/tasks/submit` (or equivalent DSH task queue endpoint)
- Return `ActionResult(success=True, details={"task_id": <dsh_task_id>})` on success
- When unavailable: return `success=False` with clear error message

**Complexity:** High — requires mapping DS-EO task/plan structure to DSH task queue format  
**Risk:** Medium — DSH task queue API shape is unknown; this method is most likely to need redesign when DSH ships

### run_tools() [P3]

**Current:** Stub returns `success=False` with "not implemented" message.  
**Phase 7 implementation:**
- Policy gate check: if policy has "allow" list and tool not in it → deny immediately
- If policy has "deny" list and tool is in it → deny immediately
- Otherwise: attempt DSH tool execution API (POST `/tools/{name}/execute` with body `{tool_args}`)
- Return `ActionResult(success=True/False, error=...)` based on response

**Complexity:** High — requires implementing full OpenClaw gateway.tools.allow/deny policy semantics in Python  
**Risk:** Medium — DSH tool execution endpoint is unknown; needs careful design when API becomes available

### available_models() [P3]

**Current:** Stub returns `[]` (empty list).  
**Phase 7 implementation:**
- If `dsh_http_client` is available: GET `/models` → parse response list
- Map each DSH model entry → `RuntimeModel(id, context_window=0, max_tokens=0, gpu_layers=-1, provider="dsh")`
- When unavailable: return `[]` (same as current stub)

**Complexity:** Medium — follows same catalog query pattern as model_info  
**Risk:** Low — straightforward; DSH /models endpoint will list available models per OAI-compatible spec

### run_task() [P4]

**Current:** Stub returns `success=False` with "not implemented" message.  
**Phase 7 implementation:**
- Simple configurable wrapper: POST `/hooks/{tool}` with body `{args}`
- Return `ActionResult(success=True/False, error=...)` based on response
- When unavailable: return `success=False` with clear error

**Complexity:** Low — follows existing dsh_http_client pattern  
**Risk:** Low — straightforward implementation once DSH hook API is known

---

## 3. Deliverable Definitions

| # | Deliverable | Location | Format |
|---|------------|----------|--------|
| D1 | CTO_PLAN.md (this doc) | `reports/TASK_DS_EO_DSH_010_PHASE7/` | Markdown |
| D2 | TASK_COMPLETION_AUDIT.md | Same dir | Gate checklist |
| D3 | Updated dsh_adapter.py (P2+ methods) | `ds_eo_openclaw/adapter/` | Python (~40 method additions) |
| D4 | run_tools() policy gate implementation | In dsh_adapter.py | ~30 lines of policy logic |
| D5 | Phase 7 test suite updates | `tests/test_adapter/` | pytest additions (~8-10 tests) |
| D6 | TEST_REPORT.md | Same dir as task docs | Markdown with results |
| D7 | DELIVERABLE_E_DELTA.md (Phase 7) | Same dir as task docs | Parity delta + comparison |

---

## 4. Acceptance Criteria by Gate

### G2 (Execution Ready)
- [x] CTO_PLAN.md complete with scoped deliverables
- [x] P2+ methods identified: archive_session, spawn_session, submit_task, run_tools, available_models, run_task
- [x] Deliverable E parity analysis from Phase 5 provides target specifications

### G3 (Review Complete)
- [ ] All Phase 7 deliverables produced
- [ ] New/delta tests pass (≥ 8/8 for new P2+ methods)
- [ ] No regressions in existing adapter contract tests (11/11 from Phase 0 must still pass)

### G4 (CTO Approval Ready)
- [ ] P2 methods implement configurable HTTP calls with graceful fallback
- [ ] run_tools() implements full policy gate (allow/deny semantics)
- [ ] available_models() follows same catalog query pattern as model_info
- [ ] Parity status updated: configurable impls 4→10 (all 10 methods have configurable implementation)

---

## 5. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| DSH task queue API shape unknown → submit_task() may need redesign later | **Medium** | Implement clean abstraction layer; document TODO endpoint clearly |
| DSH tool execution endpoint unknown → run_tools() may need redesign | **Medium** | Same: configurable base_url means zero breakage when redesigned |
| run_tools policy gate complexity > expected | **Low-Medium** | Implement exactly what OpenClaw's tools.allow/deny does; defer to real test |
| available_models response format differs from assumption | **Low** | Configurable fallback returns [] — same as current stub behavior |
| Parity still shows 0/10 full after Phase 7 | Expected | Phase 7 delivers *configurable* implementations. Real parity requires live DSH API. |

---

## 6. Testing Strategy

### New/Delta Tests (dsh_adapter_p2_test.py)
| Test | What It Verifies | Mock/Real |
|------|-----------------|-----------|
| `test_archive_session_dsh_path` | Archive via configurable DSH call | Mocked dsh_http_client |
| `test_spawn_session_valid_config` | Spawn with valid config → success response mapping | Mocked dsh_http_client |
| `test_spawn_session_invalid_config` | Spawn with missing required keys → early error | Direct (no mock needed) |
| `test_submit_task_dsh_path` | Submit via DSH task queue API | Mocked dsh_http_client |
| `test_run_tools_policy_allow` | Tool in allow list → executed via DSH | Mocked |
| `test_run_tools_policy_deny` | Tool in deny list → denied without calling DSH | Direct (no mock needed) |
| `test_run_tools_policy_missing_deny` | No deny list → default allow → called DSH | Mocked |
| `test_available_models_dsh_path` | Available models from DSH catalog | Mocked dsh_http_client |
| `test_run_task_dsh_path` | Generic tool execution via DSH hook | Mocked dsh_http_client |

### Regression Tests
- `tests/test_adapter/test_phase0.py`: 11/11 must still pass
- `tests/test_adapter/dsh_http_client_test.py`: 11/11 from Phase 6 must still pass

---

## 7. File Change Summary

| Action | File | Lines Added/Removed |
|--------|------|---------------------|
| MODIFIED | `ds_eo_openclaw/adapter/dsh_adapter.py` (P2+ methods) | +120 / -30 |
| NEW | `tests/test_adapter/dsh_adapter_p2_test.py` | ~200 |
| NEW | `reports/TASK_DS_EO_DSH_010_PHASE7/TEST_REPORT.md` | ~50 |
| NEW | `reports/TASK_DS_EO_DSH_010_PHASE7/DELIVERABLE_E_DELTA.md` | ~30 |

---

## 8. Parity Progress Projection

| Metric | Before Phase 7 | After Phase 7 (expected) |
|--------|---------------|-------------------------|
| Full parity (live DSH API) | 0 / 10 | 0 / 10 (no live endpoint yet) |
| Partial/configurable impl | 4 / 10 | **10 / 10** ✅ All methods have configurable implementation + fallback |
| Stub only (returns error/None) | 6 / 10 | **0 / 10** |

**This is a milestone:** After Phase 7, ALL 10 RuntimeAPI methods will have configurable DSH implementations with graceful fallback. When the real DSH API ships and `base_url` is configured, all methods will activate automatically without further code changes (except endpoint URL updates if needed).

---

## 9. Pending Decisions

1. **Phase 7 scope:** P2+ methods only (archive_session, spawn_session, submit_task, run_tools, available_models, run_task). register_binding stays unchanged (trivial stub).
2. **run_tools policy gate:** Full implementation of OpenClaw's tools.allow/deny semantics. Is this acceptable complexity for Phase 7? Yes — the policy gate is pure Python logic, no external dependency needed.
3. **Ready for Phase 7 execution?** Signal when approved.

