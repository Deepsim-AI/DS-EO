# CTO Plan — TASK_DS_EO_046: PM Release Closure Failure Prevention

**Created:** 2026-08-16 10:50 PDT  
**Author:** CTO 🏗️ (ollama/qwen3.6:35b)  
**Status:** APPROVED — Implementation phase  

---

## Task Objective

Fix the PM release closure failure where versions were computed from task ID context instead of reading the manifest source of truth. Implement mandatory release workflow verification to prevent false PM_CLOSED claims.

---

## Root Cause (VERIFIED)

The PM session for TASK_DS_EO_045 falsely claimed a release was complete when it wasn't:
- Version "v0.1.4" was computed from task ID context, not from `ds_eo_manifest.yaml`
- No verification that the version bump was actually applied
- No verification that the GitHub release workflow was dispatched
- No verification that the release page entry exists on GitHub

---

## Implementation Plan

| Step | File | Action | Lines |
|------|------|--------|-------|
| 1 | `ds_eo_openclaw/release_manager.py` | CREATE — ReleaseManager class | ~470 |
| 2 | `ds_eo_openclaw/release_check_protocol.py` | CREATE — Pre-release checklist | ~277 |
| 3 | `agents/pm.md` | MODIFY — Add R-REL protocol section | +122 |
| 4 | `protocols/release_management_protocol.md` | MODIFY — Add mandatory dispatch section | +55 |
| 5 | `tests/test_release_management/test_release_management.py` | CREATE — 60 tests | ~595 |

---

## Acceptance Criteria

1. ✅ ReleaseManager reads version from `ds_eo_manifest.yaml` as source of truth (R-REL-1)
2. ✅ ReleaseManager has all methods specified in CTO_CORRECTION_PLAN.md
3. ✅ release_check_protocol.py enforces mandatory pre-release checks
4. ✅ PM agent prompt includes mandatory release steps with BLOCKED conditions
5. ✅ Release management protocol has workflow dispatch as mandatory
6. ✅ All 60 tests pass
7. ✅ Bugs fixed: verify_all_task_artifacts, all_passed semantics, format_report

---

## Files to Modify (Exact Locations)

| File | Path | Action |
|------|------|--------|
| release_manager.py | `ds_eo_openclaw/release_manager.py` | NEW |
| release_check_protocol.py | `ds_eo_openclaw/release_check_protocol.py` | NEW |
| pm.md | `agents/pm.md` | MODIFY |
| release_management_protocol.md | `protocols/release_management_protocol.md` | MODIFY |
| test_release_management.py | `tests/test_release_management/test_release_management.py` | NEW |

---

## Constraints

- PM is responsible for process coordination, not release execution
- Version numbers MUST come from `ds_eo_manifest.yaml` and `__init__.py`, never from task ID
- GitHub Release workflow dispatch is MANDATORY per R-REL-2
- All changes are read-only from CTO perspective (no code modification)

---

## Verification

After implementation, the following must pass:
- `python -m pytest tests/test_release_management/test_release_management.py -v` (60 tests)
- `python -c "from ds_eo_openclaw.release_manager import ReleaseManager; print('Import OK')"`
- All release checks in protocol must pass

---

**Status:** READY FOR IMPLEMENTATION