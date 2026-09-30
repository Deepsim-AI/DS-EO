# CTO_PLAN.md — TASK_DS_EO_DSH_008

**Task:** Phase 5: Smoke Tests + Reliability Comparison + Go-Live  
**Author:** CTO (qwen3.6:35b)  
**Date:** 2026-09-29  
**Gate:** G1 — Plan for User Review  

---

## 1. Task Objective

Phase 5 is the **final migration verification gate**. It does NOT implement new features — it verifies that all prior phases are correct and produces the comparison matrix that proves the DSH Edition is production-ready.

### Three Deliverables
| D | Deliverable | Location | Format |
|---|------------|----------|--------|
| D1 | Smoke test execution report | `reports/TASK_DS_EO_DSH_008_PHASE5/SMOKE_TEST_REPORT.md` | Markdown with test results |
| D2 | Deliverable E comparison matrix | `reports/TASK_DS_EO_DSH_008_PHASE5/DELIVERABLE_E_COMPARISON.md` | Markdown table (DSH vs OpenClaw behavior) |
| D3 | Default runtime flip + go-live readiness checklist | `reports/TASK_DS_EO_DSH_008_PHASE5/GOLIVE_CHECKLIST.md` | Checklist |

---

## 2. Scope: Verification, Not Implementation

### What Phase 5 DOES
- Execute existing test suite (pytest) against current codebase
- Compare DSH adapter behavior vs OpenClaw adapter behavior for all RuntimeAPI methods
- Produce Deliverable E comparison matrix showing parity status per method
- Verify no regressions from Phases 1–4
- Check that `RuntimeAdapterFactory.create(runtime="auto")` resolves to DSH when manifest has DSH defaults

### What Phase 5 Does NOT Do
- **Implement DSH adapter stubs** — that's TASK_DS_EO_DSH_009+ (real DSH integration)
- **Change OpenClaw adapter** — the backward-compatible backend remains unchanged
- **Fix pre-existing test failures** — the baseline report already documents 2 known failing tests (`test_warn_delivers_notification`, `test_protected_session_warn_only`) due to read-only volume, not product bugs

---

## 3. Deliverable E Comparison Matrix

### Current DSH Adapter Status Per RuntimeAPI Method

| Method | OpenClaw Impl | DSH Stub Status | Parity | Notes |
|--------|---------------|-----------------|--------|-------|
| `compact_session()` | ✅ Real impl (via sessions_list + CLI) | ❌ Stub → returns error | ❌ Not ready | A1 |
| `archive_session()` | ✅ Real impl (session export) | ❌ Stub → returns error | ❌ Not ready | A3 |
| `close_session()` | ✅ Real impl (sessions_close) | ❌ Stub → returns error | ❌ Not ready | A1 |
| `get_session_info()` | ✅ Real impl (sessions_list filter) | ❌ Stub → returns None | ❌ Not ready | A3 |
| `spawn_session()` | ✅ Real impl (sessions_spawn integration) | ❌ Stub → returns error | ❌ Not ready | A6 |
| `submit_task()` | ✅ Via dispatcher | ❌ Stub → returns error | ❌ Not ready | D2 |
| `run_tools()` | ✅ Via gateway tools.invoke | ❌ Stub → returns error | ❌ Not ready | A2, A8 |
| `model_info()` | ✅ Via ollama list_models | ⚠️ Partial (placeholder fields) | ⚠️ Partial | A5 — ID and provider correct, metadata placeholders |
| `available_models()` | ✅ Via ollama list_models | ❌ Stub → returns [] | ❌ Not ready | A5 |
| `run_task()` | ✅ Via subprocess.run (release_manager.py) | ❌ Stub → returns error | ❌ Not ready | D2 — but release_manager still uses subprocess directly, not via adapter |

### Summary
- **0 of 10 methods have parity** between OpenClaw and DSH adapters
- **1 of 10 partially works** (model_info returns valid struct with correct ID/provider, but metadata is placeholder)
- **All session lifecycle operations** are stubbed in DSH adapter — cannot test functional parity yet

---

## 4. Smoke Test Plan

### Phase 5 Test Scope

| Test Suite | Target | Pass Criteria | Notes |
|-----------|--------|--------------|-------|
| `tests/test_adapter/test_phase0.py` | Adapter package contract | 11/11 pass | Existing test suite for Phase 0 adapter interface compliance |
| `test/execution_strategy/` | Execution strategy module | 53/53 pass | Self-contained, no runtime dependency |
| `tests/` (main) | Full DS-EO test suite | ≥ 568/570 pass | Baseline: 568 passed at inspection; 2 known failures due to read-only volume |
| `test_installation_flow.sh` | Installer validation | 10/10 pass | Shell smoke test |

### Expected Result After Phase 1–4 Changes

- **Phase 1 changes** (session_health → RuntimeAdapterFactory): No behavioral impact — adapter delegates identically
- **Phase 2 changes** (model_registry.py + model placeholder): No behavioral impact on existing tests — fallback defaults ensure same behavior
- **Phase 3 changes** (config naming/comments): Zero source code changes, no test impact
- **Phase 4 change** (discoverer.py runtime="dsh"): No functional impact — DSH get_session_info() stub returns None, which triggers the existing file-system estimation fallback in `_get_real_context_size()`

**Expected outcome:** Same test results as baseline — 568/570 pass, 2 known failures (pre-existing, not regressions).

---

## 5. Go-Live Readiness Checklist

### Pre-Go-Live Conditions
| Condition | Status | Notes |
|-----------|--------|-------|
| All adapters pass contract tests (Phase 0 suite) | ✅ PASS | 11/11 already verified |
| No new test failures introduced by Phases 1–4 | ⏳ TO VERIFY | Expected: same as baseline |
| Model registry resolves correctly for all roles | ✅ PASS | Verified in Phase 2 testing |
| RuntimeAdapterFactory("auto") defaults to DSH | ⏳ TO VERIFY | Depends on manifest `default_runtime` field |
| OpenClaw adapter retained as backward compat | ✅ PASS | Still importable, still works |
| Deliverable E matrix documented | ⏳ PRODUCED in Phase 5 | Shows current parity status |

### Post-Go-Live Actions (Future: TASK_DS_EO_DSH_009+)
1. Implement real DSH adapter stubs one by one
2. Verify each method achieves parity with OpenClaw adapter
3. When all methods achieve parity, remove `"auto"` fallback and make DSH the only default
4. Phase 7+: Remove remaining `openclaw_adapter.py` if no longer needed

---

## 6. Acceptance Criteria for G2/G3/G4

### G2 (Implementation Ready)
- [x] CTO_PLAN.md complete with exact deliverable definitions
- [x] Current test baseline documented (INSPECTION_REPORT.md: 570 collected, 568 passed)
- [x] DSH adapter stub status analyzed per method
- [x] Smoke test plan scoped to existing suites only

### G3 (Review Complete)
- [ ] SMOKE_TEST_REPORT.md produced with actual test results
- [ ] DELIVERABLE_E_COMPARISON.md shows parity status for all 10 RuntimeAPI methods
- [ ] GOLIVE_CHECKLIST.md shows pre-go-live conditions met or pending

### G4 (CTO Approval Ready)
- [ ] No regressions from Phases 1–4 confirmed by smoke tests
- [ ] Deliverable E matrix clearly shows current state vs target state
- [ ] `TASK_COMPLETION_AUDIT.md` gate status reflects results

---

## 7. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| New test failures from Phase 1–4 changes | Medium (low likelihood) | All changes were adapter delegation passthroughs or config-only; verify with smoke tests |
| DSH default_runtime not set in manifest, so `RuntimeAdapterFactory.create(runtime="auto")` still defaults to OpenClaw | Low | Add check in plan for manifest inspection |
| Comparison matrix shows all methods failing parity → no actionable next steps | Medium | Matrix documents current state; TASK_DS_EO_DSH_009+ handles implementation |

---

## 8. Deliverables Summary

| # | Deliverable | Location | Status |
|---|------------|----------|--------|
| D1 | CTO_PLAN.md (this document) | `reports/TASK_DS_EO_DSH_008_PHASE5/` | ✅ PRODUCED |
| D2 | TASK_COMPLETION_AUDIT.md | `reports/TASK_DS_EO_DSH_008_PHASE5/` | ⏳ TO BE WRITTEN |
| D3 | SMOKE_TEST_REPORT.md | Same dir | ⏳ TO BE PRODUCED (executes tests) |
| D4 | DELIVERABLE_E_COMPARISON.md | Same dir | ⏳ TO BE PRODUCED (analysis output) |
| D5 | GOLIVE_CHECKLIST.md | Same dir | ⏳ TO BE PRODUCED |
| D6 | Phase 0 adapter contract test results | §3 above | ✅ INCLUDED (baseline known: 11/11 pass) |
| D7 | Deliverable E parity analysis | §4 above | ✅ INCLUDED (all methods documented) |

---

## 9. Pending Decisions

1. **Should Phase 5 actually execute the test suite?** Yes — I will run pytest and capture results for the report.
2. **Do you want me to check if `ds_eo_manifest.yaml` has `default_runtime` set?** If not, I'll add that to the golive checklist as a manual action.
3. **Ready for Phase 5 execution?** Signal when approved.
