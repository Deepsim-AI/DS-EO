# CTO_PLAN.md — TASK_DS_EO_DSH_009

**Task:** Phase 6: DSH Adapter Implementation — P1 Methods (Session Lifecycle)  
**Author:** CTO (qwen3.6:35b)  
**Date:** 2026-09-29  
**Gate:** G1 — Plan for User Review  

---

## 1. Critical Constraint: No Live DSH API Available

The TODO comments in `dsh_adapter.py` reference *target* endpoints (e.g., `POST /sessions/{key}/compact`, `GET /sessions/{key}`) that are **not yet confirmed or available**. These are design-time placeholders.

**This means Phase 6 cannot implement real DSH integration.** Instead, it implements a **production-ready adapter skeleton** with:
1. HTTP client infrastructure for future DSH API calls
2. Configuration-driven endpoint URLs (so they flip to real endpoints when DSH API ships)
3. Full method-level test coverage that validates the adapter contract and wiring
4. Parity progress measured against Deliverable E

### What Phase 6 DOES
- Create `dsh_http_client.py` — shared HTTP client with configurable base URL, auth, timeouts, error mapping
- Replace stub returns in **P1 methods** (`get_session_info`, `compact_session`, `close_session`) with *configurable* implementations that:
  - First try the configured DSH endpoint (will fail gracefully against unknown URLs)
  - Fall back to file-system discovery when DSH is unavailable (backward compat path)
- Add unit tests that validate the adapter wiring, HTTP client behavior, and fallback paths
- Update model_info to read from a configurable DSH model catalog URL

### What Phase 6 Does NOT Do
- Implement real network calls (no live endpoint to call)
- Require any external DSH installation or configuration
- Modify OpenClaw adapter in any way
- Change DS-EO governance, workflow engine, or dispatcher logic

---

## 2. Target: P1 Methods Only

Per Deliverable E priority plan:

| Priority | Method | What Phase 6 Implements |
|----------|--------|------------------------|
| P1 | `get_session_info()` | Configurable HTTP client call → fallback to file-system discovery when endpoint unreachable |
| P1 | `compact_session()` | Configurable HTTP client call → returns success=False with clear error if DSH unavailable |
| P1 | `close_session()` | Configurable HTTP client call → returns success=False with clear error if DSH unavailable |
| Partial | `model_info()` | Same treatment: configurable catalog URL → fallback to ollama list when unreachable |

### Not In Scope (Deferred to TASK_DS_EO_DSH_010+)
| Method | Reason Deferred |
|--------|----------------|
| `archive_session()` | Requires DSH file export API — more complex, P2 priority |
| `spawn_session()` | Requires session creation endpoint + config mapping — P2, high effort |
| `submit_task()` | Requires task queue integration — P3, highest complexity |
| `run_tools()` | Requires tool execution gateway — P3, highest risk |
| `available_models()` | Can share with `model_info` catalog approach; separate test needed — defer to 010 |
| `run_task()` | Generic hook mapping — P4, low priority |

---

## 3. Architecture: Configurable HTTP Client

```
dsh_http_client.py (NEW)
├── DshHttpClient class
│   ├── base_url: str           ← configurable via ds_eo_manifest.yaml "dsh.api_base"
│   ├── auth_token: str         ← configurable or from env
│   ├── timeout: int            ← default 30s
│   ├── post(endpoint, body) → dict  ← with error mapping
│   ├── get(endpoint) → dict
│   └── delete(endpoint) → bool
├── HTTP_ERROR_MAP              ← DSH-specific errors → ActionResult.success=False
└── HEALTH_CHECK_ENABLED        ← runtime flag for graceful degradation

ds_eo_openclaw/adapter/dsh_adapter.py (MODIFIED)
├── get_session_info()          ← try DSH API → fallback file-system discovery
├── compact_session()           ← try DSH API → return clear error
├── close_session()             ← try DSH API → return clear error
└── model_info()               ← try DSH catalog → fallback placeholder

ds_eo_openclaw/adapter/dsh_http_client_test.py (NEW)
├── test_dsh_http_client_post_success
├── test_dsh_http_client_timeout
├── test_dsh_http_client_error_mapping
└── test_fallback_paths
```

---

## 4. Deliverable Definitions

| # | Deliverable | Location | Format |
|---|------------|----------|--------|
| D1 | CTO_PLAN.md (this doc) | `reports/TASK_DS_EO_DSH_009_PHASE6/` | Markdown |
| D2 | TASK_COMPLETION_AUDIT.md | Same dir | Gate checklist |
| D3 | dsh_http_client.py (NEW) | `ds_eo_openclaw/adapter/` | Python module (~150 lines) |
| D4 | Updated dsh_adapter.py | Same dir | P1 methods implemented |
| D5 | dsh_http_client_test.py (NEW) | `tests/test_adapter/` | pytest suite (~8 tests) |
| D6 | Phase 6 test report | `reports/TASK_DS_EO_DSH_009_PHASE6/TEST_REPORT.md` | Markdown with results |
| D7 | Deliverable E parity update | Same dir | Parity delta (3→4 methods with configurable implementation) |

---

## 5. Acceptance Criteria by Gate

### G2 (Implementation Ready)
- [x] CTO_PLAN.md complete with scoped deliverables
- [x] Current stub status documented per method in Deliverable E
- [x] P1 target methods identified: get_session_info, compact_session, close_session, model_info

### G3 (Review Complete)
- [ ] All Phase 6 deliverables produced
- [ ] New test suite passes (dsh_http_client_test.py ≥ 8/8 tests)
- [ ] No regressions in existing adapter contract tests (11/11 must still pass)

### G4 (CTO Approval Ready)
- [ ] P1 methods implement HTTP client with graceful fallback
- [ ] Parity status updated: 3→4 methods from "stub only" to "configurable implementation"
- [ ] No behavioral regressions in Phase 0 test suite

---

## 6. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| DSH API base URL not configured → all P1 methods always fail gracefully | **Expected behavior, not a bug** | Fallback paths ensure backward compatibility; clear logging on each attempt |
| New HTTP client introduces dependencies (urllib/requests) | Low | Uses `urllib.request` (stdlib only), no new pip deps |
| Test coverage gap for fallback paths | Medium | Explicit test cases for both DSH and fallback paths |
| Parity still shows 0/10 full after Phase 6 | Expected | Phase 6 delivers *configurable* implementations, not full parity. Real parity requires live DSH API. |

---

## 7. Testing Strategy

### New Tests (dsh_http_client_test.py)
| Test | What It Verifies | Mock/Real |
|------|-----------------|-----------|
| `test_post_success` | HTTP POST → parsed response dict | Mocked |
| `test_post_timeout` | Timeout → mapped to ActionResult(success=False, error="Timeout") | Mocked |
| `test_post_http_error` | 4xx/5xx → proper error mapping | Mocked |
| `test_get_success` | HTTP GET → parsed response dict | Mocked |
| `test_get_session_info_dsh_path` | DSH endpoint returns valid session data | Mocked |
| `test_get_session_info_fallback` | Unreachable DSH → file-system discovery fallback | Testable |
| `test_compact_session_dsh_path` | Compact via DSH API | Mocked |
| `test_close_session_dsh_path` | Close via DSH API | Mocked |

### Regression Tests (existing)
- `tests/test_adapter/test_phase0.py`: 11/11 must still pass (no behavioral changes to contract)
- Any existing tests that instantiate DshRuntimeAdapter directly

---

## 8. File Change Summary

| Action | File | Lines Added/Removed |
|--------|------|---------------------|
| NEW | `ds_eo_openclaw/adapter/dsh_http_client.py` | ~150 |
| MODIFIED | `ds_eo_openclaw/adapter/dsh_adapter.py` (P1 methods) | +80 / -30 |
| NEW | `tests/test_adapter/dsh_http_client_test.py` | ~200 |
| NEW | `reports/TASK_DS_EO_DSH_009_PHASE6/TEST_REPORT.md` | ~50 |
| NEW | `reports/TASK_DS_EO_DSH_009_PHASE6/DELIVERABLE_E_DELTA.md` | ~30 |

---

## 9. Parity Progress Projection

| Metric | Before Phase 6 | After Phase 6 (expected) |
|--------|---------------|-------------------------|
| Full parity | 0 / 10 | 0 / 10 (real DSH API not available) |
| Partial / configurable impl | 2 / 10 | **4 / 10** (+get_session_info, +compact_session, +close_session, +model_info) |
| Stub only (returns error/None) | 8 / 10 | **6 / 10** (-archive, -spawn, -submit_task, -run_tools, -available_models, -run_task) |

**Note:** "Partial/configurable" means the adapter attempts a real DSH call first, falls back to backward-compat path if unreachable. This is *functionally stub-level* until a live endpoint is configured, but structurally correct for production deployment.

---

## 10. Pending Decisions

1. **Should Phase 6 actually write the HTTP client code?** Yes — it's infrastructure that every future method will reuse.
2. **Do you want the fallback to file-system discovery (backward compat) or just return clear error?** I recommend backward-compat: if DSH endpoint is unreachable, fall back to what works now. This ensures zero breakage.
3. **Ready for Phase 6 execution?** Signal when approved.

