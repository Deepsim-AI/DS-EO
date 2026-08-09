---
produced_by: ollama/qwen3.6:35b
role: CTO
task_id: TASK_20260808_001
gate: G1 (planning)
produced_at: 2026-08-08T14:07:00Z
session_id: cto-webchat-session
---

# CTO Plan — TASK_20260808_001

## OpenClaw Agent Session Health and Lifecycle Management

> **Note**: This task replaces the revoked TASK_DS_EO_030. The analysis below is a fresh CTO deliverable produced by this agent session, properly isolated from PM intake per Section 11 enforcement rules.

---

## 1. Architecture Analysis

### 1.1 Current State of the System

| Module | File | Lines | Relevance to This Task |
|--------|------|-------|------------------------|
| LivenessChecker | `dispatcher/session_dispatch/liveness.py` | ~290 | **DIRECT REUSE** — discovers sessions, checks alive/completed/error, scans artifact dirs, produces health snapshots. Foundation we build on. |
| RecoveryEngine | `ds_eo_openclaw/workflow/recovery_engine.py` | TASK_DS_EO_028 | **INTEGRATION POINT** — recovery policies (RETRY/ESCALATE) should flow through this, not duplicate its logic. |
| RecoveryState | `ds_eo_openclaw/workflow/recovery_state.py` | TASK_DS_EO_028 | **DIRECT REUSE** — persistence layer for recovery state can be extended with session health metadata. |
| StateEngine | `ds_eo_openclaw/workflow/state_engine.py` | ~500 lines | **CONTEXT** — workflow states inform whether a session's associated task is ACTIVE/COMPLETED/etc., one input to health classification. |
| Supervisor | `dispatcher/session_dispatch/supervisor.py` | ~560 lines | **INTEGRATION POINT** — handles agent liveness heartbeat; session health should feed into recovery decisions rather than competing. |
| StallDetector | `ds_eo_openclaw/workflow/stall_detection.py` | ~135 lines | **CONTEXT** — tracks phase durations and inactivity; some thresholds overlap with stale detection needs. |

### 1.2 Gap Analysis

The requirement calls for a comprehensive session health system covering discovery → classification → policy → action → verification → audit. Here is the gap analysis:

| Requirement | Current Status | New Work Needed |
|---|---|---|
| Health model (12+ states) | Not implemented | `SessionHealthState` enum + classifier mapping multi-signal inputs to deterministic classifications |
| Session discovery | Partial (LivenessChecker) | Broader signal collection: context size, compaction status, error history, workflow state |
| Authoritative session→task mapping | Heuristic-based | Cross-reference LivenessChecker with dispatcher state files + OpenClaw API metadata |
| 8 health indicators | Not implemented | Age, inactivity, context size, compaction state, execution state, error history, task state, recovery history |
| Deterministic classification | Not implemented | `HealthClassifier` — multi-signal → single classification + explainability |
| Configurable thresholds | Not implemented | YAML config module following `workflow/config.py` convention |
| Lifecycle actions (NO_ACTION→ESCALATE) | Partial | Session-level action enum and executor (different abstraction from RecoveryEngine's stage-level recovery) |
| Policy map (classification → action) | Not implemented | `HealthPolicy` class with explainability for every decision |
| Protection of active work | Not implemented | Safety layer: never destroy sessions with active tasks without verifying |
| Monitoring loop | Not implemented | `SessionHealthMonitor` — scheduling discovery→classify→policy→action→verify→audit |
| Action verification | Not implemented | Verify result before recording success (never assume) |
| Failed compaction recovery | Partial | Session-specific compaction retry path via RecoveryEngine integration |
| Orphan detection | Primitive signal | Explicit orphan classifier with configurable timeout and policy |
| Audit trail | Existing patterns in audit_log.py | Session health-specific log extending those patterns |

### 1.3 Key Architectural Decisions

**Decision A: Build on LivenessChecker, Don't Replace It.** The spec calls for a "small, reliable operational layer around OpenClaw's existing session capabilities." We extend the LivenessChecker rather than replacing it.

```
SessionHealthManager (new)
  ├── SessionDiscoverer    → extends/wraps LivenessChecker
  ├── HealthClassifier     → multi-signal → classification + explanation
  ├── HealthPolicy         → classification → action mapping
  ├── PolicyExecutor       → executes actions with verification
  └── SessionHealthMonitor → scheduling loop
```

**Decision B: Separate Compaction from RecoveryEngine.** TASK_DS_EO_028's RecoveryEngine handles *workflow stage* recovery. This task handles *session-level* lifecycle (compact/archive/close). Integration point: policy decides RETRY → delegates to RecoveryEngine; COMPACT/ARCHIVE/CLOSE is session-level only.

**Decision C: Thresholds in Configuration, Not Code.** All thresholds configurable via YAML per spec §10. Conservative defaults — favor NO_ACTION over aggressive cleanup.

**Decision D: Phase-Ordered Implementation.** Phases 1 through 6 in order. Each phase's deliverables feed the next. No skipping.

---

## 2. Required Changes

### Change Set Overview

| # | File | Action | Description | Phase |
|---|------|--------|-------------|-------|
| **C1** | `ds_eo_openclaw/session_health/enums.py` | CREATE | Health state, action, monitoring status enums (§5, §11) | 2 |
| **C2** | `ds_eo_openclaw/session_health/discoverer.py` | CREATE | Session discovery extending LivenessChecker (§6, §7) | 1 |
| **C3** | `ds_eo_openclaw/session_health/classifier.py` | CREATE | Health classifier with thresholds → classification (§8, §9) | 2 |
| **C4** | `ds_eo_openclaw/session_health/policy.py` | CREATE | Health→action policy with safety layers (§10, §12, §13) | 3-4 |
| **C5** | `ds_eo_openclaw/session_health/executor.py` | CREATE | Action execution + verification + dry-run (§11, §16) | 4 |
| **C6** | `ds_eo_openclaw/session_health/monitor.py` | CREATE | Scheduling loop orchestrating the pipeline (§15) | 3 |
| **C7** | `ds_eo_openclaw/session_health/audit.py` | CREATE | Session health audit trail (§21) | 5 |
| **C8** | `ds_eo_openclaw/session_health/config.py` | CREATE | Configurable thresholds + conservative defaults (§10) | 2-3 |
| **C9** | `ds_eo_openclaw/session_health/__init__.py` | CREATE | Public API exports | All |
| **C10** | `ds_eo_openclaw/intake/manifest.py` | MODIFY (minor) | Add session health metadata field for protection tracking | 2 |
| **C11** | `tests/test_session_health.py` | CREATE | Comprehensive test suite per spec §24 (18 tests) | 2-5 |
| **C12** | `agents/pm.md` | MODIFY (minor) | Document session health capability for PM awareness | Post-phase |

### Detailed Change Descriptions

#### C1 — Enums (~80 lines)
```python
class SessionHealthState(str, Enum):
    HEALTHY, ACTIVE, STALE, OVERSIZED, STUCK, COMPACTION_REQUIRED,
    COMPACTION_FAILED, ERRORING, ORPHANED, RECOVERY_REQUIRED, UNKNOWN

class LifecycleAction(str, Enum):
    NO_ACTION, WARN, MONITOR, COMPACT, RETRY_COMPACTION, MARK_STALE,
    ARCHIVE, CLOSE, ESCALATE

class MonitorStatus(str, Enum):
    OBSERVING, ACTIVE, PAUSED  # OBSERVING = dry-run by default (§23)
```

#### C2 — Discoverer (~250 lines)
Extends LivenessChecker's alive check with: context size estimation, compaction status detection, error history collection, workflow state lookup via dispatcher. Returns structured `SessionHealthData` dataclass with all 8 health indicators. Authoritative session→task mapping via cross-reference of LivenessChecker extraction + dispatcher state files + OpenClaw API metadata.

#### C3 — Classifier (~200 lines)
Deterministic classification with explainability. Classification rules:
1. Active task → ACTIVE (not STALE) — protection
2. Compaction failed + retry exhausted → RECOVERY_REQUIRED
3. Context > oversized_threshold → OVERSIZED
4. Inactive + no active task → STALE
5. Errors > threshold → ERRORING
6. No associated task + inactive → ORPHANED
7. Execution stuck → STUCK
8. Default: HEALTHY

Every result includes human-readable explanation of which signals triggered what.

#### C4 — Policy (~200 lines)
Maps classifications to actions with all safety layers:
- Active task protection (spec §13): ALWAYS NO_ACTION for active tasks
- Protected session override (spec §22): ALWAYS WARN
- Failed compaction retry path (spec §17)
- Deterministic policy map for remaining states

#### C5 — Executor (~200 lines)
Each action has `perform(session_data)` → `ActionResult`. COMPACT verifies context reduction post-execution. ARCHIVE/CLOSE validates lifecycle transition. ESCALATE routes to RecoveryEngine or user notification. Verify-then-persist pattern from spec §16.

#### C6 — Monitor (~150 lines)
Scheduling loop: discover_all_sessions() → classify → policy → execute → audit. Default status = OBSERVING (dry-run). Must be explicitly set to ACTIVE by operator.

#### C7 — Audit (~120 lines)
Persistent per-cycle audit log following spec §21 format, extending existing `audit_log.py` patterns.

#### C8 — Config (~100 lines)
YAML configuration with conservative defaults:
```yaml
session_health:
  stale_after_seconds: 3600          # 1 hour (conservative)
  oversized_context_kb: 51200        # 50 MB
  max_compaction_attempts: 2
  error_threshold: 3
  orphan_inactive_seconds: 7200      # 2 hours
  monitoring_interval_seconds: 300   # 5 minute polling (None=disabled)
  observe_by_default: true           # dry-run default (§23)
```

---

## 3. Implementation Phases

### Phase 1 — Discovery and Observation
**Files:** C9, C2, C8
- Create `ds_eo_openclaw/session_health/` package
- Config with conservative defaults
- Extend LivenessChecker as Discoverer
- **No actions, no classification** — just reliable signal collection

### Phase 2 — Health Classification
**Files:** C1, C3 + tests
- All health states and classifications defined
- Deterministic classifier with explainability
- Orphan detection (spec §19)
- Stale handling: stale+active vs stale+abandoned (spec §18)

### Phase 3 — Policy Integration
**Files:** C4, C6
- Policy map from classification → action
- RecoveryEngine integration (spec §14)
- Monitoring loop with configurable interval
- **Status defaults to OBSERVING** (dry-run)

### Phase 4 — Safe Lifecycle Actions
**Files:** C5 + policy safety layers
- All lifecycle actions with verification
- Active task protection (spec §13)
- Protected session override (spec §22)
- Failed compaction retry (spec §17)

### Phase 5 — Persistence and Audit
**Files:** C7, C10
- Persistent audit trail with full event records
- Task manifest integration for protection flags
- Health state persistence across cycles

### Phase 6 — Real-World Validation
- Deploy to operational use during normal DS-EO development
- Refine thresholds using observed data
- Update documentation

---

## 4. Acceptance Criteria

### Functional Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| 1 | Discover relevant OpenClaw sessions via `Discoverer.discover_all_sessions()` | Unit test on all existing task sessions |
| 2 | Session-to-task-agent association is authoritative (not heuristic) | Cross-reference with dispatcher state files |
| 3 | All 12 health states deterministically achievable | Classification unit tests for each state |
| 4 | Stale sessions identified per configurable threshold | Config override + test |
| 5 | Oversized sessions identified per configurable threshold | Test with oversized context data |
| 6 | Compaction failures classified as COMPACTION_FAILED / RECOVERY_REQUIRED | Mock compaction failure signals |
| 7 | Repeated execution errors detected per configured threshold | Inject error history into test data |
| 8 | Orphan sessions identified per policy (configurable timeout) | Create session with no task association |
| 9 | All thresholds configurable via YAML (no hardcoded values) | Verify defaults in config.py, confirm external override works |
| 10 | Actions determined by deterministic policy map | Policy unit tests for each classification→action mapping |
| 11 | Active task sessions protected from destructive cleanup | Test: active task + STALE → NO_ACTION |
| 12 | Failed compaction follows controlled retry policy | Mock failure + verify retry limit enforced |
| 13 | Recovery delegates to TASK_DS_EO_028 RecoveryEngine | Code review for import/reuse of recovery_engine.py |
| 14 | Lifecycle actions verified after execution | Each executor action returns verified result |
| 15 | Every automatic lifecycle action recorded in audit trail | Audit log verification with sample events |
| 16 | Dry-run mode reports without executing | Monitor status=OBSERVING, verify no actions executed |
| 17 | Protected sessions never automatically destroyed | Test: PROTECTED + STALE → WARN (not ARCHIVE/CLOSE) |
| 18 | All tests pass + existing tests continue to pass | Full pytest suite execution |

### Quality Gates
- **G1:** This plan with acceptance criteria approved by user
- **G2:** Implementer delivers all phases in order with test results
- **G3:** Independent reviewer verifies against spec criteria
- **G4:** CTO final approval based on G3 report and full test suite pass

---

## 5. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| OpenClaw API doesn't expose enough session metadata | Medium | Graceful degradation: missing signals default to conservative classification |
| Monitoring loop interferes with active agent execution | High | Configurable interval; defaults to OBSERVING; no concurrent modifications during active workflow phases |
| Compaction actions could lose data if verification fails | Critical | Verify-then-persist: COMPACT MUST verify context reduction before marking success. Failed → recovery pipeline per spec §17 |
| Integration with RecoveryEngine creates coupling | Medium | Clear interface boundary: explicit `recover_session()` method; no shared mutable state |
| Threshold tuning causes false positives initially | Medium | Default to OBSERVING; use real session data from Phase 6 to calibrate |

---

## 6. Deliverables Summary

### New files (~1,300 lines total):
```
ds_eo_openclaw/session_health/
├── __init__.py          # C9 — public API
├── enums.py             # C1 — state/action/status enums
├── discoverer.py        # C2 — session discovery (extends LivenessChecker)
├── classifier.py        # C3 — health classification
├── policy.py            # C4 — health→action policy with safety layers
├── executor.py          # C5 — action execution + verification
├── monitor.py           # C6 — scheduling loop
├── audit.py             # C7 — audit trail
└── config.py            # C8 — configurable thresholds
```

### Modified files:
- `ds_eo_openclaw/intake/manifest.py` — session health metadata field (minor)
- `tests/test_session_health.py` — new test file (18 tests)
- `agents/pm.md` — document capability for PM awareness (minor)

### Reused (NOT modified):
- `dispatcher/session_dispatch/liveness.py` — Discovery foundation
- `ds_eo_openclaw/workflow/recovery_engine.py` — Recovery delegation
- `ds_eo_openclaw/workflow/audit_log.py` — Logging patterns
- All existing test suites

---

## 7. Implementation Order

**Follow phases 1 through 6 strictly.** Do not implement Phase N+1 before Phase N is complete and tested. Each phase's deliverables feed the next phase's inputs. The Implementer should report completion of each phase before proceeding. The CTO will verify artifacts at each phase gate (G2 confirmation).

---

**Awaiting G1 user approval to proceed to Implementer.**
