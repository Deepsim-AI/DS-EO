---
produced_by: ollama/qwen3.6:35b
role: CTO
task_id: TASK_DS_EO_030
gate: G1 (planning)
---

# CTO Plan — TASK_DS_EO_030

## OpenClaw Agent Session Health and Lifecycle Management

---

## 1. Architecture Analysis

### 1.1 Current State of the System

**Existing modules relevant to this task:**

| Module | File | Lines | Relevance to TASK_DS_EO_030 |
|--------|------|-------|---------------------------|
| LivenessChecker | `dispatcher/session_dispatch/liveness.py` | ~290 | **DIRECT REUSE** — already discovers sessions, checks alive/completed/error, scans artifact dirs, produces health snapshots. This is the foundation we build on. |
| RecoveryEngine | `ds_eo_openclaw/workflow/recovery_engine.py` | TASK_DS_EO_028 implementation | **INTEGRATION POINT** — recovery policies (RETRY/ESCALATE) should flow through this, not duplicate its logic. |
| RecoveryState | `ds_eo_openclaw/workflow/recovery_state.py` | TASK_DS_EO_028 implementation | **DIRECT REUSE** — persistence layer for recovery state can be extended with session health metadata. |
| TaskIntakeManager | `ds_eo_openclaw/intake/task_intake.py` | TASK_DS_EO_029 implementation | Not directly relevant to monitoring, but provides the task→session association infrastructure via `MANIFEST.md`. |
| StateEngine | `ds_eo_openclaw/workflow/state_engine.py` | ~500 lines | **CONTEXT** — workflow states inform whether a session's associated task is ACTIVE, COMPLETED, etc. This is one input to health classification. |
| Supervisor | `dispatcher/session_dispatch/supervisor.py` | ~560 lines | **INTEGRATION POINT** — currently handles agent liveness heartbeat; session health should feed into its recovery decisions rather than competing with them. |
| StallDetector | `ds_eo_openclaw/workflow/stall_detection.py` | ~135 lines | **CONTEXT** — already tracks phase durations and inactivity; some thresholds overlap with what TASK_DS_EO_030 needs (stale detection). |

### 1.2 Gap Analysis: Spec Requirements vs. What Exists

The spec (§§1-28) requires a comprehensive session health system. Here is the gap analysis mapped to existing code:

| Spec Section | Requirement | Current Status | Gap / New Work |
|---|---|---|---|
| **§3 Scope** | Session discovery → health inspection → classification → policy → action → verification → audit | Partial | LivenessChecker does discovery + basic health. Missing: classification model, configurable thresholds, lifecycle actions (COMPACT/ARCHIVE/CLOSE), verify-then-persist, unified monitoring loop. |
| **§5 Health Model** | 12+ health classifications (HEALTHY through RECOVERY_REQUIRED) | **Not implemented** | Need a `SessionHealthState` enum and classifier that maps multi-signal inputs to deterministic classification. LivenessChecker's `alive/completed/error/unknown` is too coarse. |
| **§6 Session Discovery** | session ID, agent identity, task association, creation time, last activity, context size, compaction status, errors, workflow state | Partial | LivenessChecker discovers sessions and maps to task dirs. Missing: context size, compaction status, error history, workflow state integration. |
| **§7 Session-to-Task Association** | Map session → agent → task → workflow state | **Partial** | LivenessChecker has `_extract_task_id_from_session()` but it's heuristic-based (scans strings for "TASK_"). Need authoritative mapping from dispatcher state + OpenClaw API. |
| **§8 Health Indicators** | Age, inactivity, context size, compaction state, execution state, error history, task state, recovery history | **Not implemented** | LivenessChecker has phase_duration and artifact_count. Need all 8 indicators as configurable inputs to the classifier. |
| **§9 Health Classification** | Deterministic classification with explainability | **Not implemented** | Need `HealthClassifier` class: multi-signal → single classification + explanation (which signals triggered what). |
| **§10 Configurable Thresholds** | YAML config for stale_after, oversized_context, max_compaction_attempts, error_threshold, monitoring_interval | **Not implemented** | New configuration module. Should follow existing DS-EO config convention (`workflow/config.py` pattern). |
| **§11 Lifecycle Actions** | NO_ACTION through ESCALATE | Partial | RecoveryEngine has RETRY/ESCALATE concepts but scoped to workflow stages, not sessions. Need session-level action enum and executor. |
| **§12 Action Policy** | Deterministic conservative policy map (e.g., HEALTHY→NO_ACTION, OVERSIZED→COMPACT) | **Not implemented** | Need `HealthPolicy` class: classification → recommended action, with explainability for every decision. |
| **§13 Protection of Active Work** | Never destroy sessions with active tasks without verifying | **Not implemented** | Critical safety layer. The policy executor must check task state before ANY destructive action. |
| **§14 Integration with TASK_DS_EO_028** | Reuse RecoveryEngine/state mechanism | N/A — we can design this in | **ARCHITECTURAL DECISION**: Session Health Manager sits *before* RecoveryEngine. Unhealthy session → detection → policy decides COMPACT/RETRY/MONITOR → if RETRY needed, delegates to RecoveryEngine. No duplication of recovery logic. |
| **§15 Monitoring Loop** | Periodic health evaluation with configurable interval | **Not implemented** | New `SessionHealthMonitor` that orchestrates discovery → classify → policy → action → verify → audit on a configurable schedule. |
| **§16 Action Verification** | Verify result before recording success | **Not implemented** | Policy executor must poll/confirm each action's effect, record actual outcome. |
| **§17 Failed Compaction Recovery** | Retry with limit → preserve state → escalate | Partial | RecoveryEngine has retry logic for workflow stages; need session-specific compaction retry path. |
| **§18 Stale Session Handling** | Distinguish stale+active vs stale+abandoned | **Not implemented** | HealthClassifier needs to incorporate task state (ACTIVE/COMPLETED/ABORTED) into stale classification output. |
| **§19 Orphan Detection** | Identify sessions without active task/workflow association | Partial | LivenessChecker's "no task directory" check is a primitive orphan signal. Need explicit orphan classifier with configurable policy. |
| **§20 Agent-Level Summary** | Per-agent health aggregation (like current liveness.py report) | Partial | LivenessChecker's `health_report()` already does this pattern. Extend to include new health classifications. |
| **§21 Audit Trail** | Every lifecycle action recorded with session, agent, task, detected state, action, result | **Not implemented** | New `SessionHealthAuditLog` — extend existing `audit_log.py` patterns or create separate session-specific log. |
| **§22 Manual Override** | PROTECTED flag on sessions | **Not implemented** | New metadata field in session health state; policy must check this before any action. |
| **§23 Dry-Run Mode** | Observe-only: report what would happen without executing | **Not implemented** | Policy executor mode flag; all classification still runs, actions are logged as "WOULD_PERFORM" instead of executed. |
| **§24 Testing** | 18 test requirements + existing tests pass | **Not implemented** | Comprehensive test suite required. See Acceptance Criteria below. |

### 1.3 Key Architectural Decisions

#### Decision A: Build on LivenessChecker, Don't Replace It

The spec explicitly says "small, reliable operational layer around OpenClaw's existing session capabilities." The LivenessChecker already has the core discovery mechanism (cross-referencing tracked sessions against gateway state). We **extend** it rather than replacing it.

**New module sits above:**
```
SessionHealthManager (new)
  ├── SessionDiscoverer    → extends/wraps LivenessChecker for broader signal collection
  ├── HealthClassifier     → maps multi-signal inputs to classifications
  ├── HealthPolicy         → classification → action mapping
  ├── PolicyExecutor       → executes actions with verification
  └── SessionHealthMonitor → scheduling loop tying it all together
```

#### Decision B: Separate Compaction from RecoveryEngine

TASK_DS_EO_028's RecoveryEngine handles *workflow stage* recovery (retry stages, escalate workflows). TASK_DS_EO_030 handles *session-level* lifecycle (compact sessions, archive, close). These are different abstraction layers. Integration point is: if the policy decides RETRY and a workflow stage needs resumption, delegate to RecoveryEngine. If the session just needs COMPACT/ARCHIVE/CLOSE, that's session-level only.

#### Decision C: Thresholds in Configuration, Not Code

Per spec §10, all thresholds are configurable via YAML. This follows the existing `workflow/config.py` pattern. Default values must be conservative (favor NO_ACTION over aggressive cleanup).

#### Decision D: Phase-Ordered Implementation

Per spec §27, implement in phases to minimize risk:
1. Discovery + Observation (no actions)
2. Health Classification (deterministic model)
3. Policy Integration (connect to RecoveryEngine)
4. Safe Lifecycle Actions (with protections)
5. Persistence + Audit
6. Real-World Validation

---

## 2. Required Changes (Minimal Scope)

### Change Set Overview

| # | File | Action | Description | Phase |
|---|------|--------|-------------|-------|
| **C1** | `ds_eo_openclaw/session_health/enums.py` | CREATE | Health state, action, and monitoring status enums (§5, §11) | Phase 2 |
| **C2** | `ds_eo_openclaw/session_health/discoverer.py` | CREATE | Session discovery extending LivenessChecker — broader signal collection (§6, §7) | Phase 1 |
| **C3** | `ds_eo_openclaw/session_health/classifier.py` | CREATE | Health classifier with configurable thresholds → deterministic classification (§8, §9, §18, §19) | Phase 2 |
| **C4** | `ds_eo_openclaw/session_health/policy.py` | CREATE | Health-to-action policy engine with protection rules (§10, §12, §13, §17, §22, §23) | Phase 3-4 |
| **C5** | `ds_eo_openclaw/session_health/executor.py` | CREATE | Policy executor with action verification and dry-run mode (§11, §16, §17) | Phase 4 |
| **C6** | `ds_eo_openclaw/session_health/monitor.py` | CREATE | Scheduled monitoring loop orchestrating the pipeline (§15) | Phase 3 |
| **C7** | `ds_eo_openclaw/session_health/audit.py` | CREATE | Session health audit trail logging (§21) | Phase 5 |
| **C8** | `ds_eo_openclaw/session_health/config.py` | CREATE | Configurable thresholds + default conservative values (§10, §23) | Phase 2-3 |
| **C9** | `ds_eo_openclaw/session_health/__init__.py` | CREATE | Public API exports | All phases |
| **C10** | `ds_eo_openclaw/intake/manifest.py` | MODIFY (minor) | Add session health metadata field to task manifest for protection tracking | Phase 2 |
| **C11** | `tests/test_session_health.py` | CREATE | Comprehensive test suite per spec §24 (18 tests) | Phase 2-5 |
| **C12** | `agents/pm.md` | MODIFY (minor) | Document session health monitoring capability for PM awareness | Post-phase |
| **C13** | Existing test suite | VERIFY | Ensure no regression (run full pytest suite) | All phases |

### Detailed Change Descriptions

#### C1 — Enums (`session_health/enums.py`, ~80 lines)

```python
class SessionHealthState(str, Enum):
    HEALTHY = "HEALTHY"
    ACTIVE = "ACTIVE"
    STALE = "STALE"
    OVERSIZED = "OVERSIZED"
    STUCK = "STUCK"
    COMPACTION_REQUIRED = "COMPACTION_REQUIRED"
    COMPACTION_FAILED = "COMPACTION_FAILED"
    ERRORING = "ERRORING"
    ORPHANED = "ORPHANED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    UNKNOWN = "UNKNOWN"

class LifecycleAction(str, Enum):
    NO_ACTION = "NO_ACTION"
    WARN = "WARN"
    MONITOR = "MONITOR"
    COMPACT = "COMPACT"
    RETRY_COMPACTION = "RETRY_COMPACTION"
    MARK_STALE = "MARK_STALE"
    ARCHIVE = "ARCHIVE"
    CLOSE = "CLOSE"
    ESCALATE = "ESCALATE"

class MonitorStatus(str, Enum):
    OBSERVING = "OBSERVING"         # dry-run mode
    ACTIVE = "ACTIVE"                # normal operation
    PAUSED = "PAUSED"               # manual override active
```

#### C2 — Discoverer (`session_health/discoverer.py`, ~250 lines)

Extends LivenessChecker's `verify_session_alive()` with broader signal collection:

- Reuses LivenessChecker for alive status and artifact scanning (existing code)
- Adds: context size estimation (from session file sizes or OpenClaw API if available)
- Adds: compaction status detection (check for compacted vs. un-compacted session state)
- Adds: error history collection (scan recent log entries / task directory error markers)
- Adds: workflow state lookup via dispatcher's `state_manager.py` — get current phase/task state for each discovered session
- Returns structured `SessionHealthData` dataclass with all health indicators (§8)

**Key integration:** Creates authoritative session-to-task mapping by cross-referencing:
1. LivenessChecker's task_id extraction (session key heuristic)
2. Dispatcher state files (`dispatcher_state.json`) for confirmed mappings
3. OpenClaw API session metadata if available

#### C3 — Classifier (`session_health/classifier.py`, ~200 lines)

Maps multi-signal inputs to deterministic classification:

```python
class HealthClassifier:
    def __init__(self, config: HealthConfig):
        self.config = config

    def classify(self, data: SessionHealthData) -> ClassificationResult:
        """Deterministic health assessment with explainability."""
        signals = self._collect_signals(data)
        score = self._evaluate(signals)
        classification = self._map_to_state(score, signals)
        return ClassificationResult(
            health_state=classification,
            explanation=self._explain(signals),  # human-readable rationale
            signals={k: v for k, v in signals.items()},
        )
```

Classification rules (deterministic, non-sequential):
1. If `has_active_task == True` AND `last_activity < stale_threshold`: → ACTIVE (not STALE) — protection from premature stale classification
2. If `compaction_status == COMPACTION_FAILED` AND `retry_count >= max_retries`: → RECOVERY_REQUIRED
3. If `context_size > oversized_threshold`: → OVERSIZED
4. If `last_activity < stale_threshold` AND `has_active_task == False`: → STALE
5. If `error_history.count > error_threshold`: → ERRORING
6. If `no_associated_task` AND `last_activity < orphan_threshold`: → ORPHANED
7. If `execution_state == STUCK`: → STUCK
8. Default: HEALTHY

**Explainability:** Every result includes the specific signals that led to each classification and why (e.g., "NOT_STALE because has_active_task=true overrides age heuristic").

#### C4 — Policy (`session_health/policy.py`, ~200 lines)

Maps health classifications to lifecycle actions with all safety layers:

```python
class HealthPolicy:
    def evaluate(self, result: ClassificationResult) -> ActionDecision:
        """Return recommended action + explanation + safety checks."""
        
        # Safety 1: Protection check (spec §13)
        if result.signals.get("has_active_task", False):
            return ActionDecision(
                action=LifecycleAction.NO_ACTION,
                reason="Active task protects session from destructive actions",
                safety_override=True,
            )
        
        # Safety 2: Protected sessions (spec §22)
        if result.signals.get("is_protected", False):
            return ActionDecision(
                action=LifecycleAction.WARN,
                reason="Session is PROTECTED — manual override active",
                safety_override=True,
            )
        
        # Safety 3: Recovering sessions (spec §17)
        if result.health_state == SessionHealthState.RECOVERY_REQUIRED:
            return self._handle_recovery(result)
        
        # Policy map (§12)
        policy_map = {
            SessionHealthState.HEALTHY: LifecycleAction.NO_ACTION,
            SessionHealthState.ACTIVE: LifecycleAction.MONITOR,
            SessionHealthState.STALE: LifecycleAction.MARK_STALE,
            SessionHealthState.OVERSIZED: LifecycleAction.COMPACT,
            SessionHealthState.STUCK: LifecycleAction.ESCALATE,
            SessionHealthState.COMPACTION_FAILED: LifecycleAction.RETRY_COMPACTION,
            SessionHealthState.ERRORING: LifecycleAction.ESCALATE,
            SessionHealthState.ORPHANED: LifecycleAction.ARCHIVE,
        }
        
        action = policy_map.get(result.health_state, LifecycleAction.MONITOR)
        return ActionDecision(action=action, reason=f"Policy map for {result.health_state}")
```

#### C5 — Executor (`session_health/executor.py`, ~200 lines)

Executes actions with verification:

- Each action has a `perform(session_data)` → `ActionResult` (success/failure + actual outcome)
- COMPACT: Triggers compaction, then polls to verify context was reduced
- ARCHIVE/CLOSE: Validates the lifecycle transition actually occurred
- ESCALATE: Routes to RecoveryEngine or user notification per recovery protocol
- Verify-then-persist pattern from spec §16

#### C6 — Monitor (`session_health/monitor.py`, ~150 lines)

Scheduling layer that ties discovery → classify → policy → execute → audit:

```python
class SessionHealthMonitor:
    def __init__(self, config: HealthConfig):
        self.config = config
        self.status = MonitorStatus.OBSERVING  # dry-run by default (spec §23)
        
    def run_once(self):
        """Single monitoring cycle."""
        sessions = discoverer.discover_all_sessions()
        for session in sessions:
            data = discoverer.collect_health_data(session)
            result = classifier.classify(data)
            decision = policy.evaluate(result)
            
            if self.status == MonitorStatus.OBSERVING:
                audit.log_observed(session, decision)  # log but don't execute
            else:
                action_result = executor.execute(decision)
                audit.log_action(session, decision, action_result)
```

**Defaults:** `status=OBSERVING` (dry-run) — must be explicitly set to ACTIVE by operator.

#### C7 — Audit (`session_health/audit.py`, ~120 lines)

Persistent per-cycle audit log following spec §21 format. Reuses existing `audit_log.py` patterns where possible but creates session-specific log since the event types differ from workflow events.

#### C8 — Config (`session_health/config.py`, ~100 lines)

YAML configuration with conservative defaults:

```yaml
session_health:
  stale_after_seconds: 3600          # 1 hour default (conservative)
  oversized_context_kb: 51200        # 50 MB
  max_compaction_attempts: 2
  error_threshold: 3                 # errors before ERRORING classification
  orphan_inactive_seconds: 7200      # 2 hours for orphan detection
  monitoring_interval_seconds: 300   # 5 minute polling (configurable, None=disabled)
  observe_by_default: true           # dry-run default
```

---

## 3. Implementation Phases (per spec §27)

### Phase 1 — Discovery and Observation

**Files:** C9 (`__init__.py`), C2 (`discoverer.py`), C8 (`config.py`)
- Create `ds_eo_openclaw/session_health/` package
- Implement config with conservative defaults
- Extend LivenessChecker as Discoverer — collect all 8 health indicators (§8) from existing session infrastructure
- No actions, no classification yet — just reliable signal collection

**Acceptance:** Discovery returns complete `SessionHealthData` for every tracked session.

### Phase 2 — Health Classification

**Files:** C1 (`enums.py`), C3 (`classifier.py`) + tests
- Define all health states and classifications
- Implement deterministic classifier with explainability
- Configurable thresholds via config module
- Orphan detection logic (spec §19)
- Stale handling distinction: stale+active vs stale+abandoned (spec §18)

**Acceptance:** All 12 health states achievable through signal combinations. Every classification includes human-readable explanation.

### Phase 3 — Policy Integration

**Files:** C4 (`policy.py`), C6 (`monitor.py`)
- Implement policy map from classification → action (spec §12)
- Integrate with RecoveryEngine for workflow-level actions (spec §14)
- Build monitoring loop with configurable interval
- **Status defaults to OBSERVING** (dry-run — spec §23)

**Acceptance:** Monitoring loop runs in dry-run, reports what it WOULD do without executing. Recovery integration verified.

### Phase 4 — Safe Lifecycle Actions

**Files:** C5 (`executor.py`) + policy safety layers
- Implement all lifecycle actions with verification (spec §16)
- Active task protection layer (spec §13)
- Protected session override (spec §22)
- Failed compaction retry path (spec §17)
- Action result verification before persisting success

**Acceptance:** All actions verified post-execution. Protection rules enforced on every destructive action. No session destroyed without explicit verification.

### Phase 5 — Persistence and Audit

**Files:** C7 (`audit.py`), C10 (manifest update)
- Persistent audit trail with full event records (spec §21)
- Task manifest integration for protection flags (spec §22)
- Health state persistence across monitoring cycles

**Acceptance:** Every lifecycle action produces an auditable event. Protection state persists through restarts.

### Phase 6 — Real-World Validation

- Deploy to operational use during normal DS-EO development
- Use observed data to refine thresholds (do not hard-code arbitrary values)
- Update documentation

---

## 4. Acceptance Criteria

Derived from spec §25 and verified at G2:

### Functional Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|-------------------|
| 1 | DS-EO can discover relevant OpenClaw sessions via `Discoverer.discover_all_sessions()` | Unit test on all existing task sessions |
| 2 | Session-to-task-agent association is authoritative (not heuristic) | Cross-reference with dispatcher state files |
| 3 | All 12 health states deterministically achievable through signal combinations | Classification unit tests for each state |
| 4 | Stale sessions identified per configurable threshold (`stale_after_seconds`) | Config override + test |
| 5 | Oversized sessions identified per configurable threshold (`oversized_context_kb`) | Test with oversized context data |
| 6 | Compaction failures identified and classified as `COMPACTION_FAILED` / `RECOVERY_REQUIRED` | Mock compaction failure signals |
| 7 | Repeated execution errors detected per configurable `error_threshold` | Inject error history into test data |
| 8 | Orphan sessions identified per policy (configurable timeout) | Create session with no task association |
| 9 | All thresholds configurable via YAML config (no arbitrary hard-coded values) | Verify all defaults in `config.py`, confirm external override works |
| 10 | Lifecycle actions determined by deterministic policy map, not heuristics | Policy unit tests for each classification→action mapping |
| 11 | Active task sessions protected from destructive cleanup on every action evaluation | Test: active task + STALE → NO_ACTION (not ARCHIVE/CLOSE) |
| 12 | Failed compaction follows controlled retry policy with configurable limit | Mock compaction failure + verify retry limit enforced |
| 13 | Recovery delegates to TASK_DS_EO_028 RecoveryEngine — no duplicate logic | Code review for import/reuse of `recovery_engine.py` |
| 14 | Lifecycle actions verified after execution (never assume success) | Each executor action returns verified result |
| 15 | Every automatic lifecycle action recorded in auditable trail | Audit log verification with sample events |
| 16 | Observe-only/dry-run mode reports actions without executing | Monitor status=OBSERVING, verify no actions executed |
| 17 | Protected sessions never automatically destroyed regardless of health state | Test: PROTECTED + STALE → WARN (not ARCHIVE/CLOSE) |
| 18 | All 18 test requirements from spec §24 pass + existing tests continue to pass | Full pytest suite execution |

### Quality Gates

- **G1:** This plan with acceptance criteria approved by user ✅ (pending)
- **G2:** Implementer delivers all phases in order with test results
- **G3:** Independent reviewer verifies against spec §25 criteria
- **G4:** CTO final approval based on G3 report and full test suite pass

---

## 5. Risk Assessment and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| OpenClaw API doesn't expose enough session metadata for all health indicators | Medium | Graceful degradation: missing signals default to conservative classification (e.g., unknown context size → assume healthy until other signals trigger) |
| Monitoring loop could interfere with active agent execution | High | Monitor runs on configurable interval; defaults to OBSERVING (dry-run); no concurrent session modifications during active workflow phases |
| Compaction actions could lose data if verification fails | Critical | Verify-then-persist pattern: COMPACT action MUST verify context reduction before marking success. Failed compaction enters recovery pipeline per spec §17 |
| Integration with RecoveryEngine creates coupling | Medium | Clear interface boundary: SessionHealthManager calls RecoveryEngine via explicit `recover_session()` method; no shared mutable state |
| Threshold tuning could cause false positives initially | Medium | Default to OBSERVING mode; use real session data from Phase 6 to calibrate before enabling ACTIVE mode |

---

## 6. Files Produced vs. Consumed

### New files (all under `ds_eo_openclaw/session_health/`):
```
session_health/
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
- `ds_eo_openclaw/intake/manifest.py` — add session health metadata field (C10)
- `tests/test_session_health.py` — new test file (C11)
- `agents/pm.md` — document capability for PM awareness (C12, minor)

### Reused (NOT modified):
- `dispatcher/session_dispatch/liveness.py` — Discovery layer foundation
- `ds_eo_openclaw/workflow/recovery_engine.py` — Recovery delegation
- `ds_eo_openclaw/workflow/audit_log.py` — Logging patterns
- All existing test suites

---

## 7. Implementation Order

Follow spec §27 strictly: **Phase 1 through Phase 6 in order.** Do not implement Phase N+1 before Phase N is complete and tested. Each phase's deliverables feed the next phase's inputs.

The Implementer should report completion of each phase before proceeding to the next. The CTO will verify artifacts at each phase gate (G2 confirmation).
