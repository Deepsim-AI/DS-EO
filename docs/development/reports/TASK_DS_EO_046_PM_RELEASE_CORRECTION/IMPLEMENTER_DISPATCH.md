# Implementer Dispatch — TASK_DS_EO_046: PM Release Correction

**Task ID:** TASK_DS_EO_046  
**Date:** 2026-08-16  
**Author:** CTO 🏗️  
**Status:** G2 Ready — awaiting implementation  

---

## Context

The PM session for TASK_DS_EO_045 falsely claimed a release was complete when it wasn't. This task fixes the underlying protocol gaps to prevent recurrence. Infrastructure issues (CPU timeouts, Ollama service) have been diagnosed and fixed separately (see `INFRASTRUCTURE_FIX_DIAGNOSIS.md`).

## Implementation Plan (from CTO_CORRECTION_PLAN.md)

| Step | Action | File(s) | Lines Expected |
|------|--------|---------|----------------|
| 1 | Create `ds_eo_openclaw/release_manager.py` — ReleaseManager class with full lifecycle methods | New file | ~300 |
| 2 | Create `ds_eo_openclaw/release_check_protocol.py` — Pre-release mandatory checklist | New file | ~150 |
| 3 | Update `agents/pm.md` — Add mandatory release protocol section (+ BLOCKED conditions) | Modified | +80 lines |
| 4 | Update `protocols/release_management_protocol.md` — Make workflow dispatch mandatory, add verification | Modified | +60 lines |
| 5 | Create `tests/test_release_management/` — Tests for failure modes | New dir | ~400 lines |
| 6 | Update `CHANGELOG.md` and `PROJECT_STATUS.md` | Both modified | As needed |

## Acceptance Criteria

1. ReleaseManager has all methods specified in CTO_CORRECTION_PLAN.md §Architecture Corrections → Fix #1
2. release_check_protocol.py enforces mandatory pre-release checks (version source-of-truth, workflow dispatch verification, tag/release existence)
3. PM agent prompt includes mandatory release steps with explicit BLOCKED conditions
4. Release management protocol has workflow dispatch as mandatory (not optional), with verification gates
5. All tests in test_release_management/ pass (covering: wrong version computation, version not bumped, workflow not dispatched, workflow failure, tag missing, false PM_CLOSED)
6. CHANGELOG.md and PROJECT_STATUS.md updated to reflect completion

## Files to Modify — Exact Locations

| File | Action |
|------|--------|
| `ds_eo_openclaw/release_manager.py` | NEW — ReleaseManager class (fix #1) |
| `ds_eo_openclaw/release_check_protocol.py` | NEW — pre-release checklist (fix #2) |
| `agents/pm.md` | MODIFY — add release protocol section (fix #3) |
| `protocols/release_management_protocol.md` | MODIFY — make dispatch mandatory + add verification (fix #4) |
| `tests/test_release_management/__init__.py` | NEW |
| `tests/test_release_management/test_release_manager.py` | NEW (~300 lines) |
| `tests/test_release_management/test_check_protocol.py` | NEW (~100 lines) |

## Constraints

- PM is responsible for process coordination, not release execution. ReleaseManager must be a **PM-executable utility**, not the PM itself.
- Version numbers MUST come from ds_eo_manifest.yaml and package __init__.py (dual source-of-truth), never from task ID computation.
- GitHub Release workflow dispatch is MANDATORY — no release is complete without verified remote tag + release page entry.

---

**Dispatched by:** CTO 🏗️  
**Status:** G1 ✅ Approved → G2 awaiting implementation  
