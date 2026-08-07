# Changelog

All notable changes to DS-EO OpenClaw Edition will be documented in this file.

## [0.1.0] — 2026-07-28

## [v0.5 — Task Intake Manager Layer] — 2026-08-07

### TASK_DS_EO_029: PM Task Intake for User-Directed Workspace Creation

#### Added

**Task Intake Module (`ds_eo_openclaw/intake/`) [NEW]**
- `__init__.py` — Public API exports (`TaskIntakeManager`, `create_task_intake`)
- `task_intake.py` (~808 lines) — `TaskIntakeManager` class with:
  - `_next_task_id()` — Sequential task ID per day (TASK_YYYYMMDD_NNN)
  - `create_task_intake()` — End-to-end workspace creation (dispatcher state + reports dir)
  - `_deduplicate()` / `find_semantic_matches()` — Jaccard similarity dedup (threshold 0.7)
  - `_create_report_dir()` — Skeleton with TASK_REQUEST.md, PM_ANALYSIS.md, INPUTS/, MANIFEST.md
  - `add_materials_to_existing()` — Post-intake file/content addition
  - `prepare_cto_handoff()` — Ensures all artifacts present for CTO reading
  - Verbatim user request preservation in TASK_REQUEST.md
  - User-provided file organization into INPUTS/ subdirectory
- `tests/test_task_intake.py` [NEW] — 25 tests (all passing)

**Agent Documentation Updates**
- `agents/pm.md` — Task Intake section with usage examples (lines 212-316)
- `ds_eo_manifest.yaml` — Added intake module entry under `modules.intake`

#### Integration Notes
- Zero changes to state machine, gate mechanics, or existing workflow modules
- All writes scoped to docs/ and reports/ directories only
- Mode-agnostic: works identically in both manual and automatic execution modes
- Intentionally independent of dispatcher's gate machinery — creates artifacts; Dispatcher handles lifecycle transitions

## [v0.4 — Dispatcher/Workflow Engine Layer] — 2026-08-05

### Added

#### Dispatcher Core (`dispatcher/`)
- **registry.py** — Agent registry loader with SHA256 integrity checksum validation
  - Loads agents_list.json, resolves agent targets (model, workspace, tool policy)
  - Detects registry drift and blocks operations on mismatch
- **engine.py** — G0-G4 gate machine state machine (data-driven from YAML workflow definitions)
  - 6 phases (S0-S5), 9 transitions with authority/artifact requirements
  - Prompt template resolution and rendering per transition type
  - Stall detection (phase duration + idle threshold)
- **state_manager.py** — Persistent per-task state with atomic writes
  - Create/read/validate/update lifecycle
  - Immutable transition history + dispatch_log.jsonl append-only audit trail
  - Registry integrity verification on every read
- **dispatch.py** — Unified dispatcher API for PM-driven task orchestration
  - `initialize()`, `open_task()`, `advance_g1/g2/g3/g4()` lifecycle methods
  - `get_task_status()`, `check_all_stalls()`, `get_task_transition_log()`
  - Full G0→G4 verified end-to-end; rejection loops (G3_CHANGES, G4_REJECT) confirmed
- **session_dispatch/engine.py** — sessions_spawn wrapper for agent-to-agent handoffs
  - Prompt composition: role identity + transition context + workflow template + task artifacts
  - Parallel dispatch with yield-wait for completions
  - All handoffs use `context="isolated"` per protocol mandate

#### Gateway Bindings (`binding_defs/`)
- **entry_points.yaml** — Minimal gateway entry-point bindings (PM only)
  - /eo.task → PM, /eo.approve → CTO, /eo.review → Reviewer
  - No workflow logic in gateway config (design constraint met)

#### Documentation
- **ARCHITECTURE.md** — Architecture overview with dispatcher layer diagram
- **IMPLEMENTATION_PLAN.md** — 5-phase build plan with priorities and risks
- **PROTOCOL.md** — Runtime contract between dispatcher components
- **STATE_SCHEMA.md** — Per-task state file formats (dispatcher_state.json, dispatch_log.jsonl)
- **SKILL.md** — PM-facing dispatcher skill overview
- **PM_DISPATCHER_SKILL.md** — Operational guide for PM agent to use dispatcher

### Tool Policy Changes
- **PM**: Added exec, write, sessions_list, session_status, memory_search, memory_get
- **CTO**: Added sessions_spawn, sessions_send (for delegation to Implementer)
- All changes committed and verified

### Verified Test Suite
- Full G0→G1→G2→G3→G4 lifecycle end-to-end: ✓
- G3 rejection loop → S2_IMPLEMENTATION: ✓
- G4 deep rejection → S2_IMPLEMENTATION: ✓
- Registry checksum drift detection: ✓
- Atomic state writes + audit log integrity: ✓
- 13 files, ~4,402 lines total across dispatcher package

### Design Decisions
- **PM-driven programmatic orchestration**: PM is the canonical routing mechanism
- **Gateway bindings expose entry points only**: No workflow logic in openclaw.json
- **All internal routing lives in dispatcher**: Reads workflow_defs/default.yaml at runtime
- **context="isolated" mandate**: Every cross-phase handoff gets no session history bleed


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

---

## [v0.4.1 — Failure Detection and Recovery Layer] — 2026-08-07

### TASK_DS_EO_028: Failure Detection and Recovery for Auto Mode

#### Added

**Recovery Engine (`workflow/recovery_engine.py`) [NEW]**
- `FailureInfo` class — serializable failure metadata (type, message, timestamp)
- `RecoveryAction` enum: RETRY_STAGE, RESUME_STAGE, WAIT_FOR_HUMAN, ABORT_WORKFLOW
- `RecoveryEngine` class with data-driven `_POLICY_TABLE` mapping
  - Failure type × retries_exhausted × is_post_g4 → RecoveryAction lookup
  - `detect_failure()` — checks FAILED/STALLED states, missing artifacts, verification failures, interruptions (all 6 types from spec §5)
  - `determine_recovery()` — policy table lookup with unknown-failure fallback to WAIT_FOR_HUMAN
  - `execute_recovery()` — state transition with safety validation
  - `is_safe_to_resume()` — validates G1/G2/G3 artifacts before resuming
  - `_history_log` — in-memory audit trail of all recovery actions

**Recovery State Persistence (`workflow/recovery_state.py`) [NEW]**
- `RecoveryStateManager` class with save/load/can_resume/clear/delete lifecycle
- Persists to `recovery_state.json` alongside dispatcher state
- Validates required fields (task_id, mode, current_gate, status) on resume
- Blocks resume from COMPLETED or manual mode states

**State Engine Extensions (`workflow/state_engine.py`)**
- 4 new states: FAILED, RETRYING, WAITING_FOR_HUMAN, RESUMED
- 7 new transition rules for failure/recovery paths (total: 19 transitions)

**Notifications (`workflow/notifications.py`)**
- 4 recovery notification types added: retry_initiated, retry_exhausted, workflow_escalated, recovery_resumed
- `get_recovery_notification()` lookup function

#### Tests
- `tests/test_recovery_engine.py` [NEW] — 42 tests across policy table validation, failure info serialization, engine initialization, recovery execution paths, persistence round-trip, resume safety, retry limits, timeout handling, history log integrity, state machine integration, gate bypass prevention
- 4 existing test expectations updated for new state values
- **348 total tests passing, 0 failures**

#### Test Results
| Category | Tests | Coverage |
|----------|-------|----------|
| Policy table validation | 4 | All failure types, determinism, exhaustion |
| FailureInfo serialization | 2 | to_dict round-trip |
| Engine initialization | 3 | Default, custom, negative max_retries |
| Recovery execution paths | 10 | All policy actions verified |
| Persistence round-trip | 6 | save/load/can_resume/clear/delete |
| Resume safety checks | 4 | Artifact validation, blocked transitions |
| Retry limit enforcement | 6 | max_retries=0,1,2 boundary conditions |
| History log integrity | 3 | Recording, ordering, filtering |
| State machine integration | 8 | Transitions within state engine context |
| Gate bypass prevention | 2 | Direct recovery→completed blocked |
| Manual mode regression | 2 | Manual mode still functional |

**Reviewer Score**: 5/5

#### Key Capabilities
- **Deterministic recovery**: Data-driven policy table, no if/else chains
- **Configurable retry limits**: `max_retries` parameter tested at boundaries
- **Persistent state**: Full save/load round-trip survives process interruption
- **Resume preserves work**: Validates G1/G2/G3 artifacts before resuming
- **Human escalation**: Retry exhaustion transitions to WAITING_FOR_HUMAN state
- **Safety**: Direct RECOVERING→COMPLETED transition blocked and tested
- **Minimal change**: All modifications are additive — 4 new states, 7 transitions, 2 new modules (~460 lines), 1 test file (~490 lines)

#### Non-Goals Confirmed Not Implemented
- ❌ No AI-based failure diagnosis (rule-based policy only)
- ❌ No distributed scheduling
- ❌ No web dashboard
- ❌ No notification delivery (types defined, not dispatched)
- ❌ No architectural refactoring of existing modules

