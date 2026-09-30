# CTO_PLAN.md — TASK_DS_EO_DSH_011

**Task:** Phase 8A: Package Renaming & Branding Cleanup  
**Author:** CTO (qwen3.6:35b)  
**Date:** 2026-09-30  
**Gate:** G1 — Plan for User Review  

---

## 1. Objective

Rename `ds_eo_openclaw/` package to `ds_eo_dsh/` and remove all OpenClaw-specific branding, producing a clean "DS-EO DSH Edition" codebase with no branding dependency on OpenClaw.

**This is Phase 8A (renaming). Phase 8B (deployment docs) follows immediately after.**

---

## 2. Full Scope Analysis

### Files Affected: 50 total

Based on grep of all `ds_eo_openclaw` references:
- **19 source files** inside `ds_eo_openclaw/` — internal imports + hardcoded paths
- **31 test/config files** across `test/`, `tests/`, `examples/`, `skills/` — external imports

### Types of Changes Needed

#### Type 1: Import Statements (majority of changes)
```python
# Before
from ds_eo_openclaw.adapter.dsh_adapter import DshRuntimeAdapter
import ds_eo_openclaw.dispatcher
sys.path.insert(0, "ds_eo_openclaw")

# After  
from ds_eo_dsh.adapter.dsh_adapter import DshRuntimeAdapter
import ds_eo_dsh.dispatcher
sys.path.insert(0, "ds_eo_dsh")
```

#### Type 2: Hardcoded Paths (inside `ds_eo_openclaw/`)
```python
# Before
workspace_root="/home/deepsim/ds_eo_openclaw"
pkg = ws / "ds_eo_openclaw"

# After
workspace_root=os.path.dirname(os.path.dirname(__file__))  # or configurable
pkg = ws / "ds_eo_dsh"
```

#### Type 3: OpenClaw Branding in Comments/Strings
- `DS-EO Dispatcher — Real Session Spawn via OpenClaw Gateway API` → remove
- Function/class docstrings mentioning OpenClaw as the primary product context
- Comments like `"openclaw config get agents"` → update to generic reference

#### Type 4: Filename Renames (no internal code change needed)
| Old filename | New filename | Reason |
|-------------|--------------|--------|
| `openclaw_adapter.py` | `openclaw_bridge.py` | Clarifies it's the bridge, not the core adapter |
| `ds_eo_openclaw/` dir | `ds_eo_dsh/` dir | Package rename |

### 3. Detailed File-by-File Change Plan

#### A. Source Files Inside `ds_eo_openclaw/` (19 files)

These are renamed to `ds_eo_dsh/`. Within each file:
- `import ds_eo_openclaw.*` → `import ds_eo_dsh.*`
- `"ds_eo_openclaw"` string literals → `"ds_eo_dsh"` 
- OpenClaw branding in comments/docstrings → generic

| File | Changes Needed | Priority |
|------|---------------|----------|
| `adapter/__init__.py` | Import paths, module name | **Critical** — gateway for all imports |
| `adapter/dsh_adapter.py` | Comments, docstring | Medium |
| `adapter/openclaw_adapter.py` | **RENAME to openclaw_bridge.py**, import paths | **Critical** |
| `adapter/dsh_http_client.py` | Comments | Low |
| `adapter/model_registry.py` | Import paths, comments | Medium |
| `dispatcher/dispatch.py` | Hardcoded paths (3), imports | **Critical** |
| `dispatcher/session_spawn.py` | Heavy OpenClaw branding in docstrings (~30 lines) | High |
| `dispatcher/state_manager.py` | Path references in comments | Low |
| `dispatcher/registry.py` | Comments | Low |
| `dispatcher/project_resolver/resolver.py` | `to_openclaw_entry()` → rename to `to_gateway_entry()` | **Critical** |
| `dispatcher/project_resolver/task_id_manager.py` | Path references | Medium |
| `dispatcher/execution_strategy/selector.py` | Comments | Low |
| `session_health/__init__.py` | Import paths | Medium |
| `session_health/*.py` (5 files) | Import paths, OpenClaw branding in comments | Medium |
| `workflow/*.py` (7 files) | Import paths | **Critical** — state engine depends on these |
| `release_check_protocol.py` | Internal imports, module name references | Medium |
| `release_manager.py` | References to package metadata | Medium |

#### B. Test Files (31 files)

All change `import ds_eo_openclaw.*` → `import ds_eo_dsh.*`.

High-priority tests that must pass after rename:
- `tests/test_adapter/` — 3 test files (22 Phase 0 + 14 Phase 7 = **36 tests**)
- `tests/conftest.py` — **Critical** — all tests load this fixture module
- `tests/test_session_health.py` — imports from session_health package
- `tests/test_state_engine.py`, `tests/test_eo_commands.py`, `tests/test_mode_switching.py`

#### C. Other Files
- `examples/run_reliability/usage.py` — update example code
- `skills/eo/*.py` — if they import from ds_eo_openclaw
- Root-level docs (README, PROJECT_STATUS.md) — update package name references

---

## 3. Deliverables

| # | Deliverable | Location | Format |
|---|------------|----------|--------|
| D1 | CTO_PLAN.md (this doc) | `reports/TASK_DS_EO_DSH_011_PHASE8A/` | Markdown |
| D2 | TASK_COMPLETION_AUDIT.md | Same dir | Gate checklist |
| D3 | **ds_eo_dsh/** — renamed package directory | Project root | Directory + in-place refactoring |
| D4 | `openclaw_bridge.py` (was openclaw_adapter.py) | ds_eo_dsh/adapter/ | Renamed file |
| D5 | All test/config files updated imports | tests/, examples/, skills/ | In-place rename |
| D6 | TEST_REPORT.md | Same dir as task docs | Markdown with results |
| D7 | DELIVERABLE_E_DELTA.md (Phase 8A) | Same dir as task docs | Branding delta + summary |

---

## 4. Implementation Strategy

### Step 1: Create `ds_eo_dsh/` by copying and in-place renaming
```bash
# Copy the directory structure
cp -r ds_eo_openclaw ds_eo_dsh

# In-place rename of all imports (recursively)
find ds_eo_dsh -name "*.py" -exec sed -i 's/ds_eo_openclaw/ds_eo_dsh/g' {} +

# Fix path references inside source files  
sed -i 's|/ds_eo_openclaw/|/ds_eo_dsh/|g' ds_eo_dsh/**/*.py
```

### Step 2: Rename `openclaw_adapter.py` to `openclaw_bridge.py`
```bash
mv ds_eo_dsh/adapter/openclaw_adapter.py ds_eo_dsh/adapter/openclaw_bridge.py
# Update any imports referencing the old filename within the new directory
find ds_eo_dsh -name "*.py" -exec sed -i 's/openclaw_adapter/openclaw_bridge/g' {} +
```

### Step 3: Rename all test/config files
```bash
# Same pattern across all affected directories
for dir in tests examples skills test; do
  find "$dir" -name "*.py" -exec sed -i 's/ds_eo_openclaw/ds_eo_dsh/g' {} +
done
```

### Step 4: Rename `to_openclaw_entry` → `to_gateway_entry` (in resolver.py)
```bash
sed -i 's/to_openclaw_entry/to_gateway_entry/g' ds_eo_dsh/dispatcher/project_resolver/resolver.py
# Also update any callers of this method
find ds_eo_dsh -name "*.py" -exec sed -i 's/\.to_openclaw_entry(/\.to_gateway_entry(/g' {} +
```

### Step 5: Update OpenClaw branding in comments/docstrings (selective)
Only change where it improves clarity, not where "OpenClaw" is the correct technical reference:
- Comments like `DSH adapter for OpenClaw` → `DS-EO DSH Runtime Adapter`  
- Docstrings referencing OpenClaw as primary context → neutral language
- **Keep**: references to OpenClaw Gateway API, CLI tools, session lifecycle (these are still real dependencies)

### Step 6: Verify — test suite against new paths
```bash
cd /home/deepsim/ds_eo_dsh
python3 -m pytest tests/test_adapter/ --tb=line -q
# Expected: 36 passed
```

### Step 7: Commit + push (before deleting old directory)

---

## 5. Acceptance Criteria by Gate

### G2 (Execution Ready)
- [x] CTO_PLAN.md complete with 50 affected files cataloged
- [x] Rename strategy: copy → sed-in-place → rename file → verify
- [x] All critical import paths identified (adapter/__init__.py, conftest.py, workflow/*.py)

### G3 (Review Complete)
- [ ] `ds_eo_dsh/` created with all imports updated
- [ ] `openclaw_bridge.py` renamed
- [ ] `to_openclaw_entry` → `to_gateway_entry` renamed
- [ ] **All 36 adapter tests pass** on new paths

### G4 (CTO Approval Ready)
- [ ] No remaining `import ds_eo_openclaw` anywhere
- [ ] No hardcoded `/ds_eo_openclaw/` path strings in runtime code  
- [ ] All test imports updated
- [ ] **36/36 adapter tests pass**
- [ ] Branding consistent: "DS-EO DSH Edition" throughout

### G5 (PM Closure Ready)
- [ ] `ds_eo_openclaw/` deleted or archived as git tag
- [ ] Full test suite passes
- [ ] Commit pushed to remote

---

## 6. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Broken import after rename → runtime failure | **High** | Run full adapter test suite (36 tests) as verification gate before deletion |
| Missing sed replacement in edge cases | Medium | Post-sed grep: `grep -rn "ds_eo_openclaw" . --include="*.py"` — must return 0 matches (excluding git history) |
| Test fixtures reference old path names | Medium | All tests in conftest.py + individual test files covered by sed |
| Cross-references between ds_eo_dsh/ modules | Low | Internal imports use relative or `ds_eo_dsh.` prefix — both handled by sed |

---

## 7. What NOT to Change (Preserve as-is)

- **session_spawn.py Path A/B logic**: This IS the OpenClaw integration bridge. Keep working, just update branding.
- **project_resolver resolver.py `to_openclaw_entry()` logic**: Still needed for generating config entries. Just rename the method (`to_gateway_entry`).
- **OpenClaw CLI invocations**: Valid when DSH Edition runs within OpenClaw. Keep functionality, update comments.
- **`.openclaw/` directory references**: These are external to the package and still valid at runtime.

---

## 8. Phase 8B Preview (Deployment Docs)

After Phase 8A commits:
1. **DEPLOYMENT_GUIDE.md** — Environment setup, DSH_API_BASE config, Docker/K8s templates
2. **config-templates/dsh_edition/** — Production-ready agent configs for DSH Edition
3. **.env.example** — Minimal env file with required DSH variables

These are documentation-only (no code changes), proceed immediately after Phase 8A.

---

## 9. Pending Decisions

1. **Package name:** Confirmed `ds_eo_dsh/`. 
2. **openclaw_adapter.py → openclaw_bridge.py**: Renamed to clarify it's the bridge, not the core adapter.
3. **Ready for Phase 8A execution?** Signal when approved.

