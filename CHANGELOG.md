# Changelog

All notable changes to DS-EO OpenClaw Edition will be documented in this file.

## [0.1.0] — 2026-07-28

### Added
- Initial package structure with all core components
- Three engineering roles: CTO, Implementer, Reviewer (portable prompts)
- Six engineering protocols extracted from DS-AIOS development environment
- Five document templates covering the full task lifecycle
- Installation script suite with backup and rollback support
- Configuration merge safety with atomic writes
- Verification test suite (schema, completeness, config safety, smoke test)
- Package manifest (`ds_eo_manifest.yaml`) as single source of truth
- Full documentation: README, ARCHITECTURE, INSTALLATION, MIGRATION_GUIDE, CONTRIBUTING


## [Phase 1 — Canonical Repository Establishment] — 2026-07-28

### Migration

Established `ds-eo-openclaw/` as the canonical long-term repository for DS-EO OpenClaw Edition. Migrated all task artifacts from temporary workspace (`/home/deepsim/DS-EO/`) into canonical repo's `docs/reports/` directory. Deprecated the temporary workspace.

**Resolved**: Missing `CTO_APPROVAL.md` for TASK_DS_EO_002 — final approval decision documented and included in task history.


## [Phase 2 — Self-Hosting] — 2026-07-28

### Self-Hosting Achievements

- DS-EO agents redirected to canonical workspace (`ds-eo-openclaw/`)
- Workspace-level AGENTS.md created establishing build-time governance within the package
- Dev infrastructure mirror (`docs/development/protocols/`) deployed via symlinks
- First real task cycle executed end-to-end within the canonical repo: TASK_DS_EO_003 (Roadmap creation)
- All four gates (G1–G4) validated working with agents operating in self-hosted mode

### Tasks Completed This Phase

| Task | Title | Decision |
|------|-------|----------|
| TASK_20260729_001 | Self-hosting (DS-EO develops DS-EO) | ✅ APPROVED |
| TASK_DS_EO_003 | Add DS-EO v0.2 Roadmap to Package | ✅ APPROVED |


## [Phase 3 — Protocol & Governance Consistency Migration] — 2026-07-30

### Tasks Completed This Phase

| Task | Title | Decision |
|------|-------|----------|
| TASK_DS_EO_015+017 | Protocol & Governance Consistency Migration | ✅ APPROVED |

### Summary

Protocol authority, artifact ownership, and capability alignment were audited against the actual workflow. Seven protocol inconsistencies were resolved (P1–P7 from WORKFLOW_AUDIT), five ownership gaps were filled, and eight recommendations were implemented.

**Key changes**:
- Renamed `PM_STALLED` → `TASK_STALLED` across all protocols
- Created unified G2 Gate Checklist as authoritative single source
- Reassigned REVIEW_REPORT.md production to Reviewer with write capability
- Corrected delegation_protocol.md: task creation ownership returned to CTO
- Added metadata enforcement at G3/G4 gates and post-rejection handling procedure
- Created `GATE_AUTHORITY_MATRIX.md` as authoritative gate governance reference
- All agent role definitions now match actual tool capabilities


## [Post-G4 Cleanup] — 2026-07-31

### Tasks Completed This Phase

| Task | Title | Decision |
|------|-------|----------|
| TASK_DS_EO_018 | Document Consistency Sweep | ✅ APPROVED |

### Summary

Post-TASK_DS_EO_015+017 documentation audit identified stale references to the pre-migration state (3 roles vs 4, 6 protocols vs 7, Reviewer as read-only). A sweep across 10+ files corrected all discrepancies against authoritative sources. The final gap — `GATE_AUTHORITY_MATRIX.md` missing from `ds_eo_manifest.yaml` — was closed with proper manifest registration and test count updates. All 53 tests pass.


## [Post-G4 Cleanup] — 2026-08-01

### Tasks Completed This Phase

| Task | Title | Decision |
|------|-------|----------|
| TASK_DS_EO_019 | Configurable Manual and Automatic Workflow Execution Modes (Design) | ✅ APPROVED |

### Summary

TASK_DS_EO_019 delivered architecture design for configurable workflow execution modes — one engineering workflow with Manual or Automatic orchestration. No code changes; all deliverables are architectural documents and a 5-phase implementation roadmap. Design reviewed by Reviewer at 5/5 spec compliance and 5/5 architecture adherence (APPROVE_WITH_COMMENTS). CTO final approval issued. Phase 1 implementation (PM workflow state engine) recommended as next task.


## [0.3.0 — Automatic Mode Implementation] — 2026-08-02

### Phase 1: PM Workflow State Engine (TASK_DS_EO_020)

**Added:**
- `ds_eo_openclaw/workflow/state_engine.py` — State enum (S0–S10), StateEngine class (detect_state, can_transition, auto_advance)
- `tests/test_state_engine.py` — 14 unit tests covering all acceptance criteria
- Package scaffolding: `__init__.py` files for `ds_eo_openclaw/` and `workflow/`
- Updated `agents/pm.md` with Workflow State Engine Integration section and tool policy update

**Test Results**: 14/14 tests pass


### Phase 2: Audit Trail Integration (TASK_DS_EO_021)

**Added:**
- `ds_eo_openclaw/workflow/audit_log.py` (298 lines) — AuditEntry class with __slots__, AuditLog manager, ProjectAuditIndex
- `tests/test_audit_log.py` (448 lines) — 20 tests: schema validation, persistence round-trip, 6 reconstruction scenarios
- Updated `ds_eo_openclaw/workflow/state_engine.py` (~160 lines added) — integrated audit logging into auto_advance() and manual_transition()
- Updated `ds_eo_openclaw/workflow/__init__.py` — exported AuditLog from workflow package
- `docs/reports/AUDIT_INDEX.json` — project-level cross-task audit index

**Key capabilities:**
- Immutable 14-field AuditEntry with UUID v4, ISO-8601 UTC timestamps, SHA-256 integrity hashes
- Per-task AUDIT_LOG.json (lazy initialization on first append)
- Project-level AUDIT_INDEX.json with atomic writes
- Reconstruction hash chain — modifying any prior entry invalidates all subsequent hashes
- Full workflow history reconstructable from a single task's AUDIT_LOG.json

**Test Results**: 34/34 tests passing; **Reviewer Score**: 4.875/5


### Phase 3: User-Facing Mode Selector (TASK_DS_EO_022)

**Added:**
- `ds_eo_openclaw/workflow/config.py` (107 lines) — Mode config with validation + per-task override support
- `ds_eo_openclaw/workflow/selector.py` (167 lines) — Atomic mode switching with audit trail integration
- `ds_eo_openclaw/workflow/notifications.py` (51 lines) — §6.3 notification maps: 7 auto-mode + 2 switch messages

**Key capabilities:**
- Default mode is "manual" when config unset or invalid
- Atomic mode switching with previous-mode return for audit trail
- Per-task overrides with override > global precedence
- No gate-bypass possible in any mode
- Mode switch always logged as audit entry

**Test Results**: 31/31 tests passing; **Reviewer Score**: 9.5/10


### Phase 4: Failure/Stall Handling Refinements (TASK_DS_EO_023)

**Added:**
- `ds_eo_openclaw/workflow/timeout_config.py` (50 lines) — Per-state timeouts with human-ownership exemptions
- `ds_eo_openclaw/workflow/stall_detection.py` (80 lines) — PM monitoring cycle integration
- `ds_eo_openclaw/workflow/escalation.py` (60 lines) — Blocker escalation chain (PM → CTO → User) with 5-minute rate limiting
- `ds_eo_openclaw/workflow/failure_detector.py` (50 lines) — Repeated failure detection

**Test Results**: 151/151 tests passing (33 new + 118 existing); zero regression; **Reviewer Score**: 5/5


### Phase 5: Testing and Validation Suite (TASK_DS_EO_024)

**Added:**
- `tests/test_manual_mode_regression.py` (285 lines) — Manual mode regression (~25 tests)
- `tests/test_auto_mode_transitions.py` (224 lines) — Auto-mode transitions (~20 tests)
- `tests/test_mode_switching.py` (188 lines) — Mode switching scenarios (~24+ tests)
- `tests/test_edge_cases.py` (196 lines) — Timeout, stall, escalation edge cases (~14 tests)
- `tests/test_audit_integration.py` (228 lines) — Cross-task audit reconstruction (~7 tests)
- `tests/test_platform_portability.py` (260 lines) — Design decision verification (~8+ tests)

**Test Results**: 92/92 tests passing in 0.37s; zero production code changes required


### Phase 6: User-Facing /eo Mode Commands (TASK_DS_EO_025)

**Added:**
- `skills/eo/SKILL.md` (180 lines) — Slash command definition with OpenClaw integration frontmatter
- `skills/eo/commands.py` (135 lines, 4 functions) — get_current_mode(), switch_to(), set_override(), format_status()
- `tests/test_eo_commands.py` (280 lines, 34 tests)

**Key capabilities:**
- `/eo mode manual` — Switch to manual execution mode with confirmation
- `/eo mode automatic` — Switch to automatic execution mode with confirmation
- `/eo mode status` — Display current mode + per-task overrides + G1/G4 gate note
- `/eo mode override TASK_<id> <mode|off>` — Set or remove per-task execution mode

**Test Results**: 34/34 tests passing; total suite: 277 tests passing (no regressions)

---

## [Post-G4 Completion] — 2026-08-03

### PM Actions — Documentation Update

| Action | Status |
|--------|--------|
| Manifest version bumped to 0.3.0 + workflow package entries added | ✅ Done |
| CHANGELOG.md deduplicated and restructured | ✅ Done |
| README.md duplicates removed, v0.3 entry added, directory tree updated | ✅ Done |
| ARCHITECTURE.md roadmap updated | ✅ Done |
| AGENTS.md protocol table corrected (7 protocols) | ✅ Done |
| INSTALLATION.md duplicate method removed | ✅ Done |
| protocols/README.md categories corrected | ✅ Done |
| COMPATIBILITY.md versions aligned to 0.3.x | ✅ Done |
| examples/minimal-workflow.md updated with /eo skill and auto-mode refs | ✅ Done |
| Git commit | ✅ Committed |
| Remote push to origin/main | ✅ Pushed |

