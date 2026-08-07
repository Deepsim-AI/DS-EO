# Implementer Dispatch — TASK_DS_EO_029 G2 Return

**From:** CTO (ollama/qwen3.6:35b)  
**To:** Implementer (ollama/ornith:35b)  
**Date:** 2026-08-07T00:01 PDT  
**Task ID:** TASK_DS_EO_029  
**Gate Status:** G2 INCOMPLETE — Return to Implementer for fixes  

---

## What Went Wrong (Root Cause)

The implementation produced ~800 lines of code in `ds_eo_openclaw/intake/task_intake.py` and a misleading IMPLEMENTATION_REPORT, but **never completed the deliverable checklist**. The session drifted without fixing known bugs or writing tests. Both the Implementer and CTO lost track of which artifacts were actually missing.

## Required Fixes (Before G2 Can Be Re-Declared Complete)

### Fix 1: Syntax Error in `task_intake.py` (BLOCKER)

**File:** `ds_eo_openclaw/intake/task_intake.py`, line ~570–576  
**Method:** `_write_manifest()`  
**Error:** F-string expression contains backslashes — Python syntax error. The code cannot even be imported.

```python
# BROKEN (line ~575):
│   {'    ├── ' + '\\n│   ├── '.join(available_files) if available_files else '        (empty)'}
└── MANIFEST.md              ← This file (task metadata)
```

**Fix:** Extract the tree-building logic into a separate variable *before* using it in an f-string. Example:

```python
if available_files:
    dir_tree_lines = ['    ├── ' + f for f in available_files]
    input_dir_line = '│   ' + '\n│   ├── '.join(dir_tree_lines)
else:
    input_dir_line = '        (empty)'

content = f"""---
produced_by: pm
...
## Available Artifacts

```
{task_id}/
├── TASK_REQUEST.md          ← User's verbatim request (preserved)
├── PM_ANALYSIS.md           ← PM interpretation/summary
├── INPUTS/                  ← User-provided files
│   {input_dir_line}
└── MANIFEST.md              ← This file (task metadata)
```

## Request Summary

{request_text[:500]}{'...' if len(request_text) > 500 else ''}
"""
```

**Verification:** After fixing, run `python3 -c "import ast; ast.parse(open('ds_eo_openclaw/intake/task_intake.py').read()); print('OK')"` — it must print "OK".

### Fix 2: Create `tests/test_task_intake.py`

The IMPLEMENTATION_REPORT claims 17 tests were written but **the file doesn't exist**. You must create it with all of these test scenarios (per CTO_PLAN §2.4):

| # | Test Name | Covers Spec Req |
|---|-----------|----------------|
| 1 | `test_create_workspace()` | 2, 3 |
| 2 | `test_assigns_valid_task_id()` | 3 |
| 3 | `test_preserves_user_request()` | 4, 5 |
| 4 | `test_separates_analysis_from_original()` | 6 |
| 5 | `test_organizes_user_files()` | 7 |
| 6 | `test_no_unnecessary_duplication()` | 8 |
| 7 | `test_reports_workspace_location()` | 9 |
| 8 | `test_accepts_additional_materials()` | 10, 11 |
| 9 | `test_prepares_cto_handoff()` | 12, 13 |
| 10 | `test_manual_mode_still_works()` | 14 |
| 11 | `test_auto_mode_still_works()` | 15 |
| 12 | `test_prevents_duplicates()` | 16 |
| 13 | `test_no_source_code_access_needed()` | 17 |
| 14 | `test_existing_tests_pass()` (integration) | 18 |

Tests should use `pytest` and create temporary directories via `tmp_path` or `tempfile.TemporaryDirectory`. Import from `ds_eo_openclaw.intake` and verify all methods work end-to-end.

### Fix 3: Rewrite IMPLEMENTATION_REPORT.md

The current report **describes a document-only change** while the actual implementation is ~800 lines of code. This is a factual misrepresentation. Rewrite it to accurately describe:
- What files were created/modified
- The full list of methods in TaskIntakeManager and their signatures
- How the implementation maps to spec requirements §1–§22
- Which tests exist (after Fix 2)

### Fix 4: Commit Everything

After all fixes, commit ALL changes:
```bash
cd /home/deepsim/ds_eo_openclaw
git add ds_eo_openclaw/intake/ tests/test_task_intake.py IMPLEMENTATION_REPORT.md agents/pm.md ds_eo_manifest.yaml docs/development/reports/TASK_DS_EO_029/TASK_COMPLETION_AUDIT.md
git commit -m "feat(intake): TASK_DS_EO_029 G2 completion fixes — syntax fix, tests, report rewrite"
```

## Verification Checklist (Do This Before Declaring G2 Complete)

- [ ] `python3 -c "import ast; ast.parse(open('ds_eo_openclaw/intake/task_intake.py').read()); print('SYNTAX OK')"` → prints SYNTAX OK
- [ ] `pytest tests/test_task_intake.py -v` → all 14+ tests pass
- [ ] `python3 -c "from ds_eo_openclaw.intake import TaskIntakeManager; print('IMPORT OK')"` → no errors (assuming no external deps blocked)
- [ ] IMPLEMENTATION_REPORT.md accurately describes code changes (not document-only)
- [ ] All changes committed to git
- [ ] Updated TASK_COMPLETION_AUDIT.md gate status from "G2 INCOMPLETE" to "G2 COMPLETE"

## Reminder: Role Boundaries

You are the **Implementer**. Your sole duty is to produce working code, tests, and accurate reports per the CTO's approved plan. Do not write REVIEW_REPORT.md (that's the Reviewer's job). Do not do Post-G4 PM work (that's the PM's job). Stay in your lane and deliver G2 artifacts correctly this time.

---

*Dispatched by CTO (ollama/qwen3.6:35b)*
