# CTO_PLAN.md — TASK_DS_EO_DSH_013

**Task:** Phase 9: Production Readiness & OpenClaw Bridge Consolidation  
**Author:** CTO (qwen3.6:35b)  
**Date:** 2026-09-30  
**Gate:** G1 — Plan for User Review  

---

## 1. Objective

Bridge the gap between "DSH adapter is fully implemented" and "ready for production deployment." Phase 9 consolidates what's done, removes legacy artifacts, and prepares for the release model.

---

## 2. Current State Assessment

### What's Complete (from Phases 0-8)

| Phase | Status | Result |
|-------|--------|--------|
| 0 | ✅ Done | RuntimeAPI interface (11 methods + create factory) |
| 1 | ✅ Done | DshRuntimeAdapter — all 11 methods with real DSH API calls |
| 2 | ✅ Done | DSH HTTP client, model registry with SHA256 checksums |
| 3 | ✅ Done | RuntimeAdapterFactory.create(runtime="dsh") wiring |
| 4 | ✅ Done | Tool bindings (run_tools method) |
| 5 | ✅ Done | Smoke tests — comparison matrix against OpenClaw adapter |
| 6 | ✅ Done | P1 implementation: model_registry, run_task, error handling |
| 7 | ✅ Done | P2+ methods: compact_session, archive_session, close_session, get_session_info, spawn_session, submit_task, run_tools, available_models, model_info, register_binding |
| 8A | ✅ Done | Package renamed ds_eo_openclaw → ds_eo_dsh (107 files) |
| 8B | ✅ Done | Deployment docs, .env.example, config templates |

### What's Missing / Not Production-Ready

#### Gap 1: OpenClaw Adapter is Still Named `openclaw_adapter.py`

The Phase 9A plan mentioned renaming `openclaw_adapter.py` → `openclaw_bridge.py` but **this was never done**. The file still exists as `openclaw_adapter.py` in `ds_eo_dsh/adapter/`.

**Why it matters:** After DSH is confirmed to fully replace OpenClaw, keeping `openclaw_adapter.py` creates ambiguity. Is it a bridge? A legacy adapter? The name should reflect its actual role.

#### Gap 2: RuntimeAdapterFactory.create(runtime="auto") Default Behavior

When `runtime="auto"` and no DSH_API_BASE is set, the factory should detect this clearly and fail fast rather than silently defaulting to OpenClaw. This affects production readiness because:
- Dev users without DSH configured get confusing fallback behavior
- Production deployments need explicit runtime choice

**Current state:** RuntimeAdapterFactory.create() imports `OpenClawRuntimeAdapter` when `runtime="openclaw"` or `"auto"`. Without DSH_API_BASE, `DshRuntimeAdapter` still constructs but returns error results for all methods.

#### Gap 3: No `__init__.py` Version / Package Metadata

The old package had `ds_eo_openclaw/__init__.py` with version extraction used by release management. The renamed `ds_eo_dsh/__init__.py` needs proper metadata.

#### Gap 4: No Release Management Infrastructure

- No `setup.py` or `pyproject.toml` for packaging
- No CHANGELOG version tracking
- No version export (`__version__`) in package
- No test coverage analysis

#### Gap 5: OpenClaw Bridge Path A/B Not Cleanly Separated

`session_spawn.py` still has Path A ("preferred") = run inside OpenClaw agent session, and Path B (fallback) = standalone REST. The preference labeling is misleading post-DSH — when DSH_API_BASE is configured, session creation should default to DSH endpoints, not OpenClaw sessions.

---

## 3. Scope: Three Sub-Tasks

### Sub-Task A: OpenClaw Adapter Consolidation (Renaming)

**Action:** Rename `ds_eo_dsh/adapter/openclaw_adapter.py` → `openclaw_bridge.py`

| Step | Command | Notes |
|------|---------|-------|
| 1. File rename | `mv ds_eo_dsh/adapter/openclaw_adapter.py ds_eo_dsh/adapter/openclaw_bridge.py` | |
| 2. Update __init__.py import | `sed -i 's/from \.openclaw_adapter/import .openclaw_bridge/g' ds_eo_dsh/adapter/__init__.py` | One line change |
| 3. Update any callers in codebase | grep + sed across entire project | Check all imports |
| 4. Update docstrings/comments | Clarify this is the OpenClaw bridge, not core adapter | Low-effort text changes |

**Risk:** Low — single file rename + import updates.

---

### Sub-Task B: Production Config Defaults

**Action:** Improve RuntimeAdapterFactory behavior and session_spawn defaults.

| Change | File | Details |
|--------|------|---------|
| Factory default when DSH_API_BASE unset → explicit error, not silent OpenClaw fallback | `runtime_api.py` | Add clear detection + ValueError |
| Clarify session_spawn Path A/B semantics | `session_spawn.py` | Rename paths to "OpenClaw mode" / "DSH API mode" |
| Add `__version__` to `ds_eo_dsh/__init__.py` | `__init__.py` | Set to 0.1.0-pre |

---

### Sub-Task C: Release Infrastructure Skeleton

**Action:** Create release management foundation.

| Deliverable | File | Content |
|-------------|------|---------|
| VERSION file | `ds_eo_dsh/VERSION` | `0.1.0-pre` |
| __init__.py version export | `ds_eo_dsh/__init__.py` | `__version__ = "0.1.0-pre"` + exports |
| pyproject.toml (skeleton) | `pyproject.toml` | Package metadata, dependencies, build system |
| README.md migration section | `README.md` | Add "Migrating from DS-EO OpenClaw Edition" section |

---

## 4. Deliverables

| # | Deliverable | Location | Format |
|---|------------|----------|--------|
| D1 | CTO_PLAN.md (this doc) | reports/TASK_DS_EO_DSH_013_PHASE9/ | Markdown |
| D2 | TASK_COMPLETION_AUDIT.md | Same dir | Gate checklist |
| D3 | `openclaw_bridge.py` (renamed file) | ds_eo_dsh/adapter/ | Python file |
| D4 | Updated `ds_eo_dsh/VERSION` + `__init__.py` | ds_eo_dsh/ | Metadata |
| D5 | Updated `runtime_api.py` factory defaults | ds_eo_dsh/adapter/ | Production safety fix |
| D6 | Updated `session_spawn.py` path naming | ds_eo_dsh/dispatcher/ | Semantic improvement |
| D7 | TEST_REPORT.md | Same dir as task docs | Markdown |
| D8 | DELIVERABLE_E_DELTA.md (Phase 9) | Same dir as task docs | Summary delta |

---

## 5. Implementation Order

1. **3A** — Rename openclaw_adapter.py → openclaw_bridge.py (lowest risk)
2. **3B** — Update runtime defaults + add __version__ (medium risk, need testing)
3. **3C** — Release infrastructure skeleton (low-risk, documentation-heavy)

---

## 6. Acceptance Criteria by Gate

### G2 (Execution Ready)
- [x] CTO_PLAN.md complete with all gaps identified and scope defined

### G3 (Review Complete)
- [ ] openclaw_bridge.py exists, all imports updated
- [ ] Runtime factory fails explicitly when no DSH_API_BASE set
- [ ] `ds_eo_dsh` has `__version__` export
- [ ] pyproject.toml skeleton in place

### G4 (CTO Approval Ready)
- [ ] All tests pass after rename + runtime defaults changes
- [ ] No import errors across any module
- [ ] Version info accessible via `import ds_eo_dsh; print(ds_eo_dsh.__version__)`

---

## 7. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| openclaw_bridge.py rename breaks imports in tests | Medium | Update all references + run full test suite |
| Runtime factory change breaks existing configs that rely on silent fallback | **High** | Only change behavior when DSH_API_BASE is unset — existing configs with DSH_API_BASE still work |
| pyproject.toml incompatibility with current build tools | Low | Minimal skeleton — just metadata, no complex configuration |

---

## 8. Pending Decisions

1. **Should the factory default be changed to fail fast when no DSH_API_BASE?** This is a breaking change for dev setups. Alternative: keep silent fallback but add explicit warning logs.
2. **Ready for Phase 9 execution?** Signal when approved.

