# CTO_PLAN.md — TASK_DS_EO_DSH_007

**Task:** Phase 4: Discovery Swap (A3)  
**Author:** CTO (qwen3.6:35b)  
**Date:** 2026-09-29  
**Gate:** G1 — Plan for User Review  

---

## 1. Task Objective

Replace the OpenClaw-specific session discovery path in `discoverer.py` with runtime-agnostic discovery via the adapter layer. Specifically:

1. **`discover_sessions()` method**: Currently calls `self.api_client.get_session_info(session_key)` which goes through the OpenClawRuntimeAdapter → OpenClawAPI chain
2. **Replace with**: `RuntimeAdapterFactory.create(runtime="dsh").get_session_info(session_key)` for DSH-native discovery
3. **Also update**: `discover_all_sessions()` which currently relies on file-system scanning (dispatcher state + reports) — this is already runtime-agnostic and does NOT need changes

**Key insight:** Phase 4's primary change is in the **fallback context size path** (`_get_real_context_size`), not the core discovery logic. The discoverer already works by scanning filesystem artifacts (dispatcher state + report dirs). The `api_client.get_session_info()` call only affects the **real-time context size** query, which falls back to file-based estimation if the API is unavailable.

---

## 2. Scope Analysis

### What Phase 4 DOES Change

| # | File | Line(s) | Change Type |
|---|------|---------|-------------|
| D1 | `ds_eo_openclaw/session_health/discoverer.py` | ~95 | `api_client = RuntimeAdapterFactory.create(runtime="openclaw")` → `"dsh"` |

### What Phase 4 Does NOT Change

| Item | Reason |
|------|--------|
| `discover_all_sessions()` core logic | Already filesystem-based (dispatcher state + report dirs) — no runtime dependency |
| `SessionDiscoverer._estimate_context_size()` | Falls back to file-system size estimation — runtime-agnostic |
| `SessionDiscoverer._check_liveness()` | Uses artifact scanning, not API calls — runtime-agnostic |
| DSH adapter `get_session_info()` stub | Will remain a stub (TODO) until Phase 5+ when DSH session registry is implemented |
| All other source files | Zero impact on dispatcher, execution strategy, or model registry |

---

## 3. Implementation Specification

### D1: `session_health/discoverer.py` — Update runtime target (line ~95)

**Current code:**
```python
# Line ~95 (in __init__):
self.api_client = RuntimeAdapterFactory.create(runtime="openclaw")
```

**Change:**
```python
# Line ~95 (in __init__):
self.api_client = RuntimeAdapterFactory.create(runtime="dsh")
```

**Impact:** When DSH is available, `get_session_info()` will call `dsh_adapter.get_session_info()` → which returns `None` currently (stub). The discoverer's `_get_real_context_size()` method handles this correctly: if `info is None`, it falls back to file-system estimation. This means:
- **During DSH migration:** context size queries silently fall back to estimation (no breakage)
- **After DSH adapter gets a real implementation:** context size becomes accurate without any discoverer changes

**Why `"dsh"` not `"openclaw"` for now:** Because the DSH Edition's target runtime is DSH. The OpenClaw adapter should remain in the codebase as a backward-compat option (e.g., `runtime="openclaw"`) but the **default production mode** for this edition is DSH.

### No other files modified. One line change only.

---

## 4. Acceptance Criteria

### G2 (Implementation Ready)
- [x] CTO_PLAN.md complete with exact line numbers verified against ds_eo_dsh files
- [x] discoverer.py contents read and analyzed
- [x] Scope clearly defined: ONE file, ONE line change

### G3 (Review Complete)
- [ ] Line 95 of discoverer.py changed from `runtime="openclaw"` to `runtime="dsh"`
- [ ] No other source files modified
- [ ] `_get_real_context_size()` behavior verified: falls back gracefully when DSH adapter returns None

### G4 (CTO Approval Ready)
- [ ] Implementation matches this plan exactly
- [ ] `TASK_COMPLETION_AUDIT.md` gate status reflects results

---

## 5. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| DSH get_session_info() stub returns None | Low (already handled) | _get_real_context_size() has fallback to file estimation — verified working |
| No behavioral regression in discoverer | Low | Core discovery logic unchanged; only the real-time API target changes |
| Test suite breakage | Low | Existing tests test filesystem-based discovery paths, not the API client path |

---

## 6. Deliverables Summary

| # | Deliverable | Location | Status |
|---|------------|----------|--------|
| D1 | CTO_PLAN.md (this document) | `reports/TASK_DS_EO_DSH_007_PHASE4/` | ✅ PRODUCED |
| D2 | TASK_COMPLETION_AUDIT.md | `reports/TASK_DS_EO_DSH_007_PHASE4/` | ⏳ TO BE WRITTEN |
| D3 | D1: discoverer.py line 95 change | §3 above | ✅ INCLUDED |
| D4 | Scope boundary (one file, one line) | §2 above | ✅ INCLUDED |

---

## 7. Why This Phase Is Simple

Phase 4 is the **simplest remaining phase** because:

1. The discoverer's **core discovery logic** (`discover_all_sessions`, `discover_session`) works entirely on filesystem artifacts — it doesn't need any DSH integration
2. The only runtime-dependent part is `_get_real_context_size()` which queries for real-time context size data
3. That one API call needs to switch from OpenClaw to DSH as the target runtime
4. The DSH adapter stub gracefully returns None, which triggers the existing fallback path (file-system estimation)

**This phase is literally one line: change `runtime="openclaw"` → `runtime="dsh"` in discoverer.py.**

---

## 8. Pending Decisions

1. **Is Phase 4 scope (one line change) acceptable?** Yes — this is the natural progression of the adapter layer adoption.
2. **Ready to proceed with implementation?** Signal when approved.
