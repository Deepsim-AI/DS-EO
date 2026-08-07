---
produced_by: ollama/qwen3.6:35b
role: CTO
task_id: TASK_DS_EO_029
gate: G1 (planning)
---

# CTO Plan — TASK_DS_EO_029

## 1. Architecture Analysis

### 1.1 Current PM Capabilities

The PM agent currently has these capabilities for task lifecycle management:

| Capability | Status | Location | Description |
|-----------|--------|----------|-------------|
| PM Agent Definition | ✅ Complete | `agents/pm.md` | Full role definition, tool policies, write paths, anti-role-collapse rules |
| Dispatcher Engine | ✅ Complete | `dispatcher/dispatch.py` | `open_task()`, gate advances (G1-G4), status queries, stall detection |
| State Manager | ✅ Complete | `dispatcher/state_manager.py` | Per-task persistent state, atomic writes, dispatch logs |
| Workflow Definitions | ✅ Complete | `dispatcher/workflow_defs/default.yaml` | Agent config, phase definitions, transition matrices |
| PM Dispatcher Skill | ✅ Complete | `dispatcher/PM_DISPATCHER_SKILL.md` | Operational guide for PM to use dispatcher |
| State Engine (v2) | ✅ Complete | `ds_eo_openclaw/workflow/state_engine.py` | 15-state state machine with auto-advance, audit trail |
| Agent Registry | ✅ Complete | `dispatcher/registry.py` | Agent validation, registry checksums |

### 1.2 Gap Analysis: What Exists vs. What Spec Requires

The spec (TASK_DS_EO_029.md §1-§22) requires **task intake and workspace initialization** — the PM must receive user demands and automatically create organized task workspaces. Here is what exists vs. what's missing:

| Spec Requirement (§) | Current Status | Gap |
|---|---|---|
| **§3 PM Role (Secretary)** | PM definition exists but no intake method | **NEW**: Need `pm_intake()` method on the Dispatcher or a new `TaskIntakeManager` module |
| **§5 Task Workspace Creation** | `dispatcher.open_task()` creates S0 state + basic dir | **PARTIAL**: Creates directory + dispatcher_state.json, but does NOT create task report artifacts (CTO_PLAN.md skeleton, TASK_REQUEST.md) in `docs/development/reports/` |
| **§6 Task Intake Record (TASK_REQUEST.md)** | Not implemented | **NEW**: PM needs to create `TASK_REQUEST.md` artifact preserving user's original request verbatim |
| **§7 Original vs Analysis** | No separation mechanism | **NEW**: Need INPUTS/ directory + TASK_REQUEST.md (verbatim) + PM_ANALYSIS.md (PM interpretation) distinction |
| **§8 User-Provided Files** | Not implemented | **NEW**: PM needs capability to accept and organize user files into task workspace's INPUTS/ subdirectory |
| **§9 User Follow-Up Message** | Not implemented (user-facing behavior) | **EXTENSION**: PM session logic needs to produce structured follow-up message telling user workspace location |
| **§10 Task Package for CTO** | Partially exists via `open_task()` | **EXTENSION**: Must ensure full task report directory structure in `docs/development/reports/` follows DS-EO conventions (CTO_PLAN.md, PM analysis, metadata) |
| **§11 CTO Handoff** | No automated handoff mechanism | **NEW**: PM needs READY_FOR_CTO signal state and CTO-readable task manifest |
| **§13 Task Metadata** | Partial: dispatcher_state.json has basic fields | **EXTENSION**: Need additional fields — `intake_status`, `workspace_path` (reports dir) alongside existing `task_id`, `mode`, `created_at` |
| **§14 Task Intake States** | Existing states: S0-S10 + recovery | **NEW**: Extend with intake-specific states: `INTAKE`, `AWAITING_USER_INPUT`, `READY_FOR_CTO` (maps to TASK_OPEN in workflow) |
| **§15 Additional Materials** | No add-to-existing-task capability | **NEW**: PM needs method to detect context-identified task and append materials to existing workspace |
| **§16 Duplicate Detection** | Not implemented | **NEW**: Critical — must check existing tasks for semantic similarity before creating new one |
| **§17 Manual/Auto Modes** | Both modes fully functional | **NO CHANGE**: Intake works identically in both; post-intake behavior already differs by mode (manual=user-controlled, auto=auto-advance) |
| **§18 Permissions** | PM tool policy restricts to designated paths | **NO CHANGE**: PM writes go to reports dir + designated metadata paths only. No source code access needed. |

### 1.3 Key Architectural Decision: Extend vs. New

Per the spec's design principle (§22) — "smallest reliable implementation" — and our stabilization mandate (TASK_DS_EO_028 completed, TASK_DS_EO_027 completed), the decision is clear:

**Extends existing Dispatcher + Task Intake Manager module.** We extend `Dispatcher.open_task()` to also create task report directory structure, and add a new `TaskIntakeManager` class that handles:
- User request intake (verbatim preservation)
- Duplicate detection against existing tasks
- Task workspace initialization (both dispatcher state dir AND reports dir)
- Input file organization
- Post-intake follow-up messaging

**Rationale:**
1. `Dispatcher.open_task()` already creates `docs/dispatchers/TASK_ID/dispatcher_state.json` — we extend it to also create the corresponding `docs/development/reports/TASK_ID/` skeleton
2. A separate `TaskIntakeManager` cleanly separates intake logic (user interaction, file handling, duplicate detection) from lifecycle management (existing Dispatcher responsibility)
3. No changes to existing state machine, agent registry, or gate mechanics

### 1.4 Existing Task ID Numbering Mechanism

Current convention: `TASK_<YYYYMMDD>_<NNN>` where NNN increments per day. This is enforced by PM in `agents/pm.md` and documented in protocol. The PM determines the next ID by scanning existing task directories.

**Duplicate detection (§16)** must check:
1. Exact task ID collision (same YYYYMMDD_NNN) — already guaranteed by incrementing convention
2. Semantic duplicate (user requesting same thing as an existing TASK) — new requirement requiring semantic comparison against existing TASK_REQUEST.md / spec content

### 1.5 Directory Structure Convention

Existing DS-EO tasks live in:
```
docs/development/reports/TASK_<ID>/    ← Task report artifacts
  ├── CTO_PLAN.md (CTO produces)
  ├── IMPLEMENTATION_REPORT.md (Implementer produces)
  ├── REVIEW_REPORT.md (Reviewer produces)
  ├── CTO_APPROVAL.md (CTO produces)
  └── TASK_COMPLETION_AUDIT.md (when complete)

docs/dispatchers/TASK_<ID>/            ← Dispatcher state
  ├── dispatcher_state.json
  ├── dispatch_log.jsonl
  └── ...
```

New intake must create BOTH locations simultaneously.

---

## 2. Required Changes

### 2.1 New Module: `ds_eo_openclaw/intake/task_intake.py`

**Single new module.** This is the core implementation — handles all task intake logic without touching existing workflow/ dispatcher code.

```
ds_eo_openclaw/intake/
├── __init__.py              # Public API exports
└── task_intake.py           # TaskIntakeManager class (~300-400 lines)
```

#### `TaskIntakeManager` class:

| Method | Purpose | Returns |
|--------|---------|---------|
| `__init__(workspace_root)` | Initialize with workspace path | — |
| `create_task_intake(request_text, user_files=None, mode='manual')` | Create complete task workspace from user input | `(task_id, workspace_path, success: bool, error_msg?)` |
| `add_materials_to_existing(task_id, materials)` | Add files/content to existing task workspace | `(success: bool, updated_task_id)` |
| `find_semantic_matches(request_text, max_results=3)` | Check for potential duplicates against existing tasks | `[existing_task_info]` |
| `prepare_cto_handoff(task_id)` | Ensure task is ready for CTO reading | `handoff_artifacts_path` |
| `_next_task_id(date_override=None)` | Get next available task ID per convention | `str` (e.g., "TASK_20260807_001") |
| `_deduplicate(request_text)` | Check if request matches existing task | `(is_duplicate, matching_task_info or None)` |
| `_create_report_dir(task_id)` | Create skeleton in docs/development/reports/ | success bool |
| `_create_intake_artifacts(task_id, request_text, user_files)` | Write TASK_REQUEST.md, PM_ANALYSIS.md, INPUTS/ | success bool |

#### Key behaviors:

1. **`_next_task_id()`**: Scans `docs/dispatchers/` for all TASK_* dirs, extracts YYYYMMDD_NNN, finds max NNN for today's date. If no tasks today, starts at 001. Uses today's date (not the date of the latest task) to allow same-day sequential intake.

2. **`_deduplicate()`**: For each existing task with status S0_OPEN through G3_PENDING (i.e., not yet fully completed), reads its TASK_REQUEST.md (or spec content in TASK_xxx.md) and compares using simple text similarity (e.g., Jaccard similarity on token sets, or keyword overlap). If similarity > threshold (default 0.7), returns the matching task with recommendation to append instead of create-new.

3. **`create_task_intake()`**: The primary entry point. Orchestrates:
   - Deduplication check
   - Next task ID assignment
   - Create `docs/dispatchers/TASK_ID/` via existing `Dispatcher.open_task()`
   - Create `docs/development/reports/TASK_ID/` with skeleton:
     ```
     TASK_ID/
     ├── TASK_REQUEST.md        ← User's verbatim request preserved
     ├── PM_ANALYSIS.md         ← PM interpretation/summary (optional)
     ├── INPUTS/                ← User-provided files organized here
     │   └── user_files_as_is
     └── MANIFEST.md            ← Task metadata (id, mode, status, intake_status)
     ```
   - Returns task_id and workspace_path for PM to report to user

4. **`add_materials_to_existing()`**: Given a task_id (from context or explicit reference), writes new materials into that task's INPUTS/ directory and appends to the manifest. Supports both file addition and text notes.

5. **`prepare_cto_handoff()`**: Ensures all required artifacts exist in reports dir, returns path for CTO to read. Does NOT advance workflow state — that remains PM's gate transition responsibility via existing `Dispatcher.advance_g1()` etc.

### 2.2 Extended Module: `ds_eo_openclaw/intake/__init__.py`

```python
from .task_intake import TaskIntakeManager

__all__ = ["TaskIntakeManager", "create_task_intake"]
```

Simple public API — one function, one class.

### 2.3 Extension: PM Agent Definition Update (§6)

Update `agents/pm.md` to reference the new intake module and include usage examples in the operational instructions section. No role changes — just add the new capability to the "What You Have" list.

**Existing PM write paths are sufficient:**
- `docs/development/reports/**` ✅ (already designated)
- `docs/dispatchers/**` ✅ (implied via dispatcher integration)

No new path permissions needed. The PM's existing tool policy (`tools.allow: ["write", "apply_patch", "web_search", "web_fetch", "exec"]`) is sufficient because intake writes go to already-designated paths.

### 2.4 Tests: `tests/test_task_intake.py`

Tests organized per spec §19 requirements (numbered 1-17):

```
test_task_intake/
├── test_create_workspace()           # Req 2, 3
├── test_assigns_valid_task_id()      # Req 3
├── test_preserves_user_request()     # Req 4, 5
├── test_separates_analysis_from_original()  # Req 6
├── test_organizes_user_files()       # Req 7
├── test_no_unnecessary_duplication()  # Req 8
├── test_reports_workspace_location()  # Req 9
├── test_accepts_additional_materials()  # Req 10
├── test_prepares_cto_handoff()       # Req 11, 12
├── test_manual_mode_still_works()    # Req 13
├── test_auto_mode_still_works()      # Req 14
├── test_prevents_duplicates()        # Req 15
├── test_no_source_code_access_needed()  # Req 16
└── test_existing_tests_pass()        # Req 17 (run suite)
```

Each test is a standalone unit test using `tmp_path` fixtures from conftest.py. No integration with live gateway — purely filesystem simulation.

### 2.5 Documentation Updates

| Document | Change | Scope |
|----------|--------|-------|
| `agents/pm.md` | Add "Task Intake" section with usage examples | Minor (additive) |
| `dispatcher/PM_DISPATCHER_SKILL.md` | Cross-reference intake module | Minor (additive) |
| `ds_eo_manifest.yaml` | Add `intake/` to package manifest | Required per convention |
| `CHANGELOG.md` | Add entry for TASK_DS_EO_029 | Standard post-G4 (PM duty) |

### 2.6 No Changes To

| Component | Reason |
|-----------|--------|
| `workflow/state_engine.py` | Intake states are PM-level; workflow states (S0-S14) unchanged |
| `dispatcher/dispatch.py` | `open_task()` signature unchanged; intake layer calls it internally |
| `dispatcher/engine.py` | Workflow engine is gate logic only; no changes |
| `dispatcher/registry.py` | Agent registry unchanged |
| `agents/cto.md`, `implementer.md`, `reviewer.md` | Other agents' definitions unchanged |
| Existing test suite | Only additive tests added |
| Gate mechanics (G1-G4) | Intake ends at TASK_OPEN; gates work as before |
| Manual/auto mode switching | Both modes already functional; intake produces same output regardless of mode |

---

## 3. Acceptance Criteria Mapping

Direct mapping from spec §20 to implementation deliverables:

| # | Spec Criterion | Implementation Deliverable | Test Coverage |
|---|----------------|--------------------------|---------------|
| 1 | PM can receive user demand directly | `TaskIntakeManager.create_task_intake()` accepts request_text parameter | test_create_workspace() |
| 2 | PM automatically creates task workspace | `_create_report_dir()` + existing `open_task()` | test_create_workspace() |
| 3 | PM assigns/records task ID via convention | `_next_task_id()` scans existing dirs per TASK_YYYYMMDD_NNN | test_assigns_valid_task_id() |
| 4 | PM records user's request | TASK_REQUEST.md written verbatim in INPUTS/ or root | test_preserves_user_request() |
| 5 | Original specifications preserved | Written files are never overwritten; original content stored as-is | test_preserves_user_request() |
| 6 | PM organizes user files/references | `INPUTS/` subdirectory structure with file organization logic | test_organizes_user_files() |
| 7 | PM initializes task metadata/state | MANIFEST.md created + dispatcher_state.json via existing open_task() | test_prepares_cto_handoff() |
| 8 | PM tells user workspace location | Return value of create_task_intake includes path; PM reports it | test_reports_workspace_location() |
| 9 | User can add additional specs/materials | `add_materials_to_existing()` supports post-intake additions | test_accepts_additional_materials() |
| 10 | PM incorporates additional materials | INPUTS/ grows organically; manifest updated with new entries | test_accepts_additional_materials() |
| 11 | PM can prepare task for CTO | `prepare_cto_handoff()` ensures all artifacts present | test_prepares_cto_handoff() |
| 12 | CTO reads workspace without user intervention | reports dir follows DS-EO conventions; CTO reads TASK_REQUEST.md directly | test_prepares_cto_handoff() |
| 13 | PM does not need source-code permissions | All writes to docs/ + reports/ dirs only; verified in test_no_source_code_access_needed() | test_no_source_code_access_needed() |
| 14 | Manual workflow functional | Existing mode tests pass; intake doesn't affect mode selection | test_manual_mode_still_works() |
| 15 | Automatic workflow functional | Existing mode tests pass; intake doesn't affect mode selection | test_auto_mode_still_works() |
| 16 | Duplicate task creation handled | `_deduplicate()` with similarity threshold; test_prevents_duplicates() | test_prevents_duplicates() |
| 17 | Automated tests cover new functionality | `tests/test_task_intake.py` with 14+ test cases | All tests above |
| 18 | Existing regression tests pass | Run full pytest suite after implementation | test_existing_tests_pass() (integration) |
| 19 | Documentation updated | agents/pm.md, manifest, etc. per §2.5 | Verified at G4 review |

---

## 4. Risk Assessment and Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Duplicate detection false positives** (PM rejects legitimate new tasks) | Medium | High — blocks user workflow | Conservative threshold (0.7); always show matching task to PM for manual decision |
| **PM creates duplicate IDs** | Low | Critical | `_next_task_id()` scans existing directories; collision impossible by construction |
| **PM permission scope violation** | Low | Medium — security risk | All writes scoped to `docs/` and `docs/dispatchers/`; no source code paths touched |
| **Intake breaks manual/auto mode separation** | Low | High — architectural regression | Intake produces identical output regardless of mode; mode affects only post-intake auto-advance |
| **Extension of Dispatcher.open_task() signature** | Medium | Medium — API change risk | Don't modify open_task() at all. Intake layer calls it independently and creates reports dir separately |
| **Existing tests broken by new code** | Low | Medium | Additive only; run full suite before G2 |
| **User files (PDFs, images) not handled gracefully** | Medium | Low — non-goal | Store as-is in INPUTS/; no parsing required |

### Critical Risk: Semantic Duplicate Detection Accuracy

The `_deduplicate()` method uses text similarity against existing task requests. False negatives (missing duplicates) are less harmful than false positives (blocking legitimate new tasks). Strategy:
- Default threshold: 70% keyword overlap on normalized token sets
- On match: show PM the candidate task and ask whether to create-new or append-to-existing
- Never auto-create-or-append silently — always present option to user/PM

### Critical Risk: Two Parallel State Locations

Tasks now have state in BOTH `docs/dispatchers/TASK_ID/` (dispatcher) AND `docs/development/reports/TASK_ID/` (reports). The intake module MUST create both atomically. If one fails, the other must be rolled back. Implementation uses try/finally with temp directory creation followed by fsync.

---

## 5. Implementation Phases

Per spec §19 testing requirements and stabilization principle, implementation is a single cohesive unit (no multi-phase split needed):

### Phase A: Intake Module (~300-400 lines)
- `ds_eo_openclaw/intake/__init__.py`
- `ds_eo_openclaw/intake/task_intake.py`
  - `TaskIntakeManager` class with all methods from §2.1

### Phase B: Tests (~200 lines)
- `tests/test_task_intake.py`
- All 14+ test cases from spec §19 and §20 criteria

### Phase C: Documentation & Integration (~50 lines)
- Update `agents/pm.md` with intake usage examples
- Update `ds_eo_manifest.yaml`
- Update `CHANGELOG.md` (will be done by PM in Post-G4 per protocol)

**Total estimated size: ~550-650 lines of new code, ~100 lines of doc changes.**

No existing files are modified except for additive documentation updates.

---

## 6. Dependency Mapping

| Dependency | Status | Notes |
|-----------|--------|-------|
| Existing PM role definition | ✅ Available | `agents/pm.md` — no changes needed |
| Dispatcher engine (`dispatcher/dispatch.py`) | ✅ Stable | TASK_DS_EO_028 completed; not modified, called by intake layer |
| State manager (`dispatcher/state_manager.py`) | ✅ Stable | Called internally via dispatcher.open_task() |
| Workflow state engine (`workflow/state_engine.py`) | ✅ Stable | Not modified |
| PM Dispatcher Skill doc | ✅ Available | `dispatcher/PM_DISPATCHER_SKILL.md` — will be cross-referenced |
| Existing test infrastructure | ✅ Available | `conftest.py` fixtures, pytest 7.x |
| Task ID numbering convention | ✅ Established | TASK_YYYYMMDD_NNN pattern from AGENTS.md §3 |

---

## 7. G1 Gate Approval Request

This plan proposes:
1. **One new module** (`ds_eo_openclaw/intake/`) with `TaskIntakeManager` class
2. **One new test file** (`tests/test_task_intake.py`) with 14+ tests
3. **Minor doc updates** to `agents/pm.md`, `ds_eo_manifest.yaml`

**Zero changes to:** state machine, gate mechanics, agent definitions (beyond referencing the new module), or existing workflow.

**Total scope:** ~650 lines of code/docs. Smallest reliable implementation that makes the PM a practical front door.

Requesting user approval at G1 to proceed to Implementer handoff.
