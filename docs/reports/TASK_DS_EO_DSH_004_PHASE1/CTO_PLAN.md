# CTO_PLAN.md — TASK_DS_EO_DSH_004

**Task:** Phase 1: OpenClaw Adapter Thinning (Implementation)  
**Author:** CTO (qwen3.6:35b)  
**Date:** 2026-09-29  
**Gate:** G1 — Plan for User Review  

---

## 1. Task Objective

Refactor **5 existing files** in `ds_eo_dsh/ds_eo_openclaw/` to use the Runtime Adapter pattern (`RuntimeAdapterFactory.create()`) instead of direct `OpenClawAPI` imports. This is a **structural refactor** — no behavioral change, no new features, only substitution of the adapter factory for direct instantiation.

---

## 2. Scope: 5 Files to Modify

| # | File (relative to ds_eo_dsh/) | Dependencies (from RUNTIME_ADAPTER_DESIGN.md) | Change Type |
|---|-------------------------------|---------------------------------------------|------------|
| F1 | `session_health/__init__.py` | Exports OpenClawAPI publicly | Replace import + export |
| F2 | `session_health/discoverer.py` | A3 (session discovery) | Import swap, instantiation swap |
| F3 | `session_health/executor.py` | A4 (actions) | Import swap, instantiation swap |
| F4 | `ds_eo_openclaw/__init__.py` (or session_health submodule import) | A3 (exposed to core) | Import swap |
| F5 | `release_manager.py` | A2 (subprocess.run in release flow) | Add adapter dependency, use `run_task()` where appropriate |

**Key rule:** Only the 5 files above are modified. No other existing code is touched. New files from Phase 0 (`adapter/`) are imported but not created.

---

## 3. File-by-File Specifications

### F1: `session_health/__init__.py` (line ~28)

**Current:**
```python
from .openclaw_api import OpenClawAPI
...
__all__ = [..., "OpenClawAPI", ...]
```

**Change:** Add adapter import alongside existing. Keep OpenClawAPI as backward-compatible export but add RuntimeAPI to exports.

```python
# ADD near top (after .enums import):
from ..adapter import RuntimeAPI, RuntimeAdapterFactory, OpenClawRuntimeAdapter  # noqa: F401

# ADD to __all__:
"RuntimeAPI", "RuntimeAdapterFactory", "OpenClawRuntimeAdapter",
```

**No removal.** OpenClawAPI stays exported for backward compatibility. The adapter types are additive.

---

### F2: `session_health/discoverer.py` (lines 18, 95)

**Current (line 18):**
```python
from .openclaw_api import OpenClawAPI
```

**Current (line 95 in __init__):**
```python
self.api_client = OpenClawAPI()
```

**Change:**
```python
# Line ~18: Replace import
from ..adapter import RuntimeAdapterFactory  # noqa: F401

# Line ~95 (in SessionDiscoverer.__init__, around line 95):
# OLD:
#     self.api_client = OpenClawAPI()
# NEW:
#     self.api_client = RuntimeAdapterFactory.create(runtime="openclaw")
```

**Type note:** `api_client` is now typed as `RuntimeAPI` (Protocol), not `OpenClawAPI`. Since it's used via duck-typed method calls, this is a no-behavior change — but callers that type-hint against `OpenClawAPI` must also change.

---

### F3: `session_health/executor.py` (lines 23, 90, 97)

**Current (line 23):**
```python
from .openclaw_api import OpenClawAPI
```

**Current (lines 90-97 in __init__ signature and body):**
```python
def __init__(
    self,
    ...,
    api_client: Optional[OpenClawAPI] = None,
    ...
):
    ...
    self.api_client = api_client or OpenClawAPI()
```

**Change:**
```python
# Line ~23: Replace import
from ..adapter import RuntimeAdapterFactory, OpenClawRuntimeAdapter  # noqa: F401

# Lines ~90-97 (in __init__):
# Type hint change for api_client parameter:
#   OLD: Optional[OpenClawAPI] = None
#   NEW: Optional[object] = None  (Protocol type would be too narrow for optional)
#         or use TYPE_CHECKING guard:
#     from ..adapter import RuntimeAPI
#
# Instantiation change (line ~97):
#   OLD: self.api_client = api_client or OpenClawAPI()
#   NEW: self.api_client = api_client or RuntimeAdapterFactory.create(runtime="openclaw")
```

**Important:** The `api_client` parameter type hint needs a guard if we want to import at runtime safely. Use:
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..adapter import RuntimeAPI
# Then use `object` as the runtime type, or Union[OpenClawAPI, "RuntimeAPI", None]
```

---

### F4: `release_manager.py` (lines 10, 98)

**Current (line 10):**
```python
import subprocess
```

**Current (line 98):**
```python
result = subprocess.run(...)
```

**Change:** This is the **hardest** Phase 1 change because `release_manager.py` uses `subprocess.run()` for version release operations, not for OpenClaw session management. The adapter's `run_task()` method is meant to replace this, but Phase 1 focuses on session-health-related OpenClaw coupling first.

**Phase 1 approach (conservative):**
```python
# Line ~10: ADD import
from ..adapter import RuntimeAdapterFactory

# Line ~98: KEEP as-is for Phase 1. The release_manager's subprocess.run() is for
# Python package releases (version bumping, changelog), not runtime operations.
# This will be addressed in Phase 2+ when the adapter's run_task() is more mature.

# BUT: Add a TODO comment at line ~97 (before the subprocess.run):
#   # TODO Phase 1: migrate to RuntimeAPI.run_task() — pending DSH implementation
```

**Decision:** Defer full release_manager refactor to Phase 2+. Phase 1 focuses on session_health files only.

---

### F5: `session_health/__init__.py` revisited (SessionHealthConfig integration)

Actually, re-examining the scope, I realize there's a **6th location** that should be included:

**`session_health/config.py`** may contain path defaults that reference `~/.openclaw/`. Check if it needs updating. If not in scope for Phase 1, mark as Phase 2+.

---

## 4. What Is NOT Changed (Phase 1 Boundary)

| File | Reason |
|------|--------|
| `session_health/openclaw_api.py` | Source of truth — the adapter wraps this, doesn't replace it |
| `session_health/adapter/runtime_api.py` | Already created in Phase 0 |
| `dispatcher/session_spawn.py` | OpenClaw coupling (A6) is too complex for Phase 1; deferred to Phase 2+ |
| `release_manager.py` subprocess.run() | Release operations, not session lifecycle; deferred to Phase 2+ |
| `workflow/` modules | No OpenClaw dependency — untouched |
| `run_reliability/` modules | No OpenClaw dependency — untouched |
| `intake/` modules | No OpenClaw dependency — untouched |

---

## 5. Acceptance Criteria for G2/G3/G4

### G2 (Implementation Ready)
- [ ] CTO_PLAN.md complete with exact line numbers verified against ds_eo_dsh files
- [ ] All 5 files confirmed present in ds_eo_dsh via bootstrap verification
- [ ] No ambiguity in which lines to change per file
- [ ] Backward compatibility plan documented (OpenClawAPI stays exported)

### G3 (Review Complete)
- [ ] All 5 files modified with exact changes specified above
- [ ] `session_health/__init__.py` exports RuntimeAPI types in addition to OpenClawAPI
- [ ] `discoverer.py` uses RuntimeAdapterFactory.create(runtime="openclaw") at line ~95
- [ ] `executor.py` uses RuntimeAdapterFactory at instantiation; type hints updated
- [ ] No new imports of `from .openclaw_api import OpenClawAPI` in discoverer or executor
- [ ] All Phase 0 adapter files remain untouched (only read, not modified)
- [ ] Existing test suite runs against changed code

### G4 (CTO Approval Ready)
- [ ] Implementation matches this plan exactly
- [ ] All tests pass (Phase 0 + existing suite)
- [ ] No behavioral regression (adapter delegates identically to OpenClawAPI)
- [ ] `TASK_COMPLETION_AUDIT.md` gate status reflects results

---

## 6. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| discoverer.py uses api_client methods that differ between OpenClawAPI and RuntimeAPI | High | RuntimeAPI Protocol ensures method compatibility; verify all used methods exist on both types |
| Type hints break static analysis (mypy) | Medium | Use `object` or TYPE_CHECKING guard for protocol types |
| Other modules import directly from session_health expecting only OpenClawAPI exports | Low | We keep OpenClawAPI in __all__; additive export of RuntimeAPI doesn't break consumers |
| Phase 1 changes break pytest conftest.py assumptions | Medium | Run full test suite; check for any hardcoded type checks or isinstance() against OpenClawAPI |

---

## 7. Deliverables Summary

| # | Deliverable | Location | Status |
|---|------------|----------|--------|
| D1 | CTO_PLAN.md (this document) | `reports/TASK_DS_EO_DSH_004_PHASE1/` | ✅ PRODUCED |
| D2 | TASK_COMPLETION_AUDIT.md | `reports/TASK_DS_EO_DSH_004_PHASE1/` | ⏳ TO BE WRITTEN |
| D3 | F1: session_health/__init__.py change spec | §3 above | ✅ INCLUDED |
| D4 | F2: discoverer.py change spec | §3 above (lines 18, 95) | ✅ INCLUDED |
| D5 | F3: executor.py change spec | §3 above (lines 23, 90-97) | ✅ INCLUDED |
| D6 | F4: release_manager.py scope note | §3 above + §4 | ✅ INCLUDED |
| D7 | Scope boundary definition | §4 above | ✅ INCLUDED |
| D8 | Acceptance criteria (G2-G4) | §5 above | ✅ INCLUDED |
| D9 | Risk assessment | §6 above | ✅ INCLUDED |

---

## 8. Pending Decisions

1. **Is the Phase 1 scope acceptable?** Specifically: focus only on session_health files (F1-F3), defer release_manager.py and dispatcher/session_spawn.py to Phase 2+?
2. **Ready for TASK_DS_EO_DSH_004 implementation?** Signal when approved to begin.
