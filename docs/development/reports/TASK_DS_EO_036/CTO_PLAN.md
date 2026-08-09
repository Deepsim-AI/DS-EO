---
produced_by: ollama/qwen3.6:35b
session_id: cto-tui-7011d3b2-10e1-4bac-bf99-a3b620a153ec
produced_at: 2026-08-09T11:20:00-07:00
role: CTO
task_id: TASK_DS_EO_036
gate: G1
---

# CTO Plan — TASK_DS_EO_036: DS-EO v0.8 Consolidation & Release

## Problem Statement

DS-EO has completed Phases 1–7 (state engine, audit trail, mode selector, failure handling, testing, session commands, session health with real CLI integration). The codebase is functional but:

1. **Changelog structure** — Inconsistent format with mixed heading styles (`## [v0.8` vs `## [0.1.0]`). Needs a clean, structured release note for v0.8.
2. **Version bump** — CHANGELOG.md still references `[0.1.0]` and `[Phase 1—Canonical Repository Establishment]`. The product is ready for a proper semantic version tag.
3. **README roadmap** — References `v0.7` as the latest release; needs update to v0.8.
4. **Project status** — PROJECT_STATUS.md has stale entries (TASK_DS_EO_030 revoked placeholder, TASK_DAL_002 referencing old state).
5. **Manifest alignment** — ds_eo_manifest.yaml was out of sync with the current module structure (fixed today; needs release note in changelog).
6. **No formal v0.8 release artifacts** — No RELEASE_NOTES, no version metadata bump anywhere.

## Scope

Documentation and configuration consolidation only. No code changes, no new features, no test modifications.

### Deliverables (in order):

1. **Update CHANGELOG.md** — Restructure to add a clean `[v0.8.0]` section summarizing all Phases 1–7 as one release.
2. **Bump version everywhere** — ds_eo_manifest.yaml (`package.version`), CHANGELOG.md section header, README.md version reference.
3. **Update README.md** — Update the roadmap to show v0.8 shipped, list completed phases, set next milestone (v0.9).
4. **Update PROJECT_STATUS.md** — Clean up stale entries, ensure all closed tasks are marked closed.
5. **Update ds_eo_manifest.yaml** — Bump `package.version` to 0.8.0, ensure all modules listed match the current codebase.

### Acceptance Criteria

1. All 433 tests still pass (unchanged by consolidation)
2. CHANGELOG.md has a clear `[v0.8.0]` section with phase summaries and no orphaned "Phase" headings at the same level as version sections
3. README.md references `v0.8.0` as latest, roadmap shows v0.8 shipped
4. PROJECT_STATUS.md has clean task table with only valid active/closed entries
5. ds_eo_manifest.yaml `package.version = 0.8.0` and all modules present
6. No code files modified (only CHANGELOG.md, README.md, PROJECT_STATUS.md, ds_eo_manifest.yaml)

### Files to Modify (exact list)

- `CHANGELOG.md` — Add v0.8 section, restructure
- `README.md` — Update version refs and roadmap
- `PROJECT_STATUS.md` — Clean task table
- `ds_eo_manifest.yaml` — Version bump + module verification

### Risk Assessment: LOW

- All changes are documentation/config only
- No behavioral changes to any system
- Zero test risk (tests unchanged)
- Easy to rollback if something looks wrong
