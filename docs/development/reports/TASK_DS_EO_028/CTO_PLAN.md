---
produced_by: ollama/qwen3.6:35b
role: CTO
task_id: TASK_DS_EO_028
gate: G1 (planning)
task_name: Failure Detection and Recovery for Automatic Workflow Execution
---

# CTO Plan — TASK_DS_EO_028

## 1. Architecture Analysis

### 1.1 Current State of the Automatic Workflow

The automatic workflow infrastructure was completed across TASK_DS_EO_020 through TASK_DS_EO_023:

| Module | File | Lines | Status |
|--------|------|-------|--------|
| State Engine | `workflow/state_engine.py` | 473 | Complete — 11 states (S0–S10), auto-advance, manual transitions |
| Audit Trail | `workflow/audit_log.py` | 298 | Complete — persistent per-task audit log with reconstruction hash chain |
| Mode Selector | `workflow/selector.py` + `workflow/config.py` | 107+167 | Complete — global mode + per-task override |
| Failure Detector | `workflow/failure_detector.py` | 191 | Complete — rework loop count with configurable thresholds (REWORK→WARNING→ESCALATE) |
| Stall Detection | `workflow/stall_detection.py` | 135 | Complete — per-state timeout comparison, human-ownership exemptions |
| Timeout Config | `workflow/timeout_config.py` | 142 | Complete — 11 states with per-state timeouts, None=exempt |
| Escalation Chain | `workflow/escalation.py` | 166 | Complete — PM→CTO→User chain with rate limiting |
| Notifications | `workflow/notifications.py` | 84 | Complete — mode switch + failure notification types |
| Supervisor (dispatcher) | `dispatcher/session_dispatch/supervisor.py` | ~560 | Complete — agent liveness heartbeat, retry/recovery for stalled agents, abort workflow |
| Liveness Checker | `dispatcher/session_dispatch/liveness.py` | ~140 | Complete — session-level liveness detection |
| Workflow Engine (dispatcher) | `dispatcher/engine.py` | ~620 | Complete — gate state machine, transition validation |

### 1.2 What the Spec Requires vs. What Exists

The spec (TASK_DS_EO_028.md) has 16 sections. Here is the gap analysis:

| Spec Section | Requirement | Current Status | Gap |
|---|---|---|---|
| §3 Desired Workflow | Failed stage recovery path with RETRY / HUMAN_REQUIRED branches | Partial | No explicit `RETRYING` or `WAITING_FOR_HUMAN` states in State enum; no branch logic for failures |
| §4 Failure States | Distinguish PENDING, RUNNING, STALLED, FAILED, RETRYING, WAITING_FOR_HUMAN, RECOVERED, COMPLETED, ABORTED | Partial | Current `State` enum has 11 states (TASK_OPEN through STALLED). Missing: RETRYING, WAITING_FOR_HUMAN, RECOVERED, ABORTED. PENDING and RUNNING are not in the enum. |
| §5 Failure Detection | Agent execution failure, missing artifacts, invalid result, verification failure, stall/timeout, unexpected interruption | Partial | `FailureDetector` only tracks rework loops per gate. No detection of agent exit codes, artifact validation, or process interruption state |
| §6 Recovery Policy | Deterministic recovery actions: RETRY_STAGE, RESUME_STAGE, WAIT_FOR_HUMAN, ABORT_WORKFLOW | **Not implemented** | `supervisor.py` has `attempt_recovery()` for stalled agents only. No workflow-level recovery policy engine |
| §7 Retry Policy | Configurable retry limit (e.g., max_retries: 2) | Partial | Supervisor has `config.retry_attempts = 2`, but it is agent-liveness specific, not workflow-gate specific |
| §8 Persistent Recovery State | Persist task_id, mode, current_gate, status, failure info, recovery info | **Not implemented** | No dedicated persistence layer for recovery state. Existing `dispatcher_state.json` tracks phase only, not failure/recovery specifics |
| §9 Resume Behavior | After restart: load persisted state, confirm prior gates completed, resume or recover | **Not implemented** | No resume/restore logic in StateEngine or WorkflowEngine |
| §10 Human Intervention | Enter WAITING_FOR_HUMAN with diagnostic (task ID, gate, failure reason, retry count, artifacts, recommended action) | Partial | Escalation chain produces notifications but no structured diagnostic report; no dedicated `WAITING_FOR_HUMAN` state |
| §11 Logging/Audit Trail | Recovery events recorded; human-readable history showing what failed, when, why, what DS-EO did | Partial | Audit log records transitions but not failure/recovery-specific events |
| §12 Safety Requirements | Never overwrite artifacts, never mark failed as complete, no silent discard, no endless retry, no gate bypass | Partial | Can verify via testing — safety constraints need explicit enforcement |
| §13 Testing | 12 specific test requirements for failure + recovery paths | **Not implemented** | Existing tests cover Phase 4 failure/stall in isolation, not the integrated recovery workflow |
| §15 Non-Goals | No redesign, no AI diagnosis, no distributed scheduling, no notifications implementation, no web dashboard, no major refactoring | Clear | These are explicitly excluded — must keep scope tight |

### 1.3 Key Architectural Insight

**The existing code is modular but not unified.** Each failure-handling module (FailureDetector, StallDetector, EscalationChain) was built as a standalone component during Phase 4 of TASK_DS_EO_023. The supervisor layer in `dispatcher/session_dispatch/` handles agent-level liveness and retry, but there is **no single entry point** that:

1. Observes failure across the workflow state machine
2. Applies a recovery policy
3. Persists the recovery state
4. Resumes on restart
5. Escalates when appropriate

TASK_DS_EO_028 bridges this gap by creating a minimal **`RecoveryEngine`** that sits between the StateEngine and the Supervisor, unifying detection → decision → persistence → resume without refactoring any existing module.

---

## 2. Required Changes (Minimal Scope)

### Change Set Overview

| # | File | Action | Description |
|---|------|--------|-------------|
| C1 | `ds_eo_openclaw/workflow/state_engine.py` | MODIFY | Add 4 new states to State enum: RECOVERING, WAITING_FOR_HUMAN, RESUMED, ABORTED. Add `can_transition()` rules for failure/recovery paths. |
| C2 | `ds_eo_openclaw/workflow/recovery_engine.py` | CREATE | New module — unified recovery policy engine (detection → decision → persistence → resume) |
| C3 | `ds_eo_openclaw/workflow/recovery_state.py` | CREATE | Persistent recovery state persistence/resume layer (§8, §9 of spec) |
| C4 | `ds_eo_openclaw/workflow/notifications.py` | MODIFY | Add notification types for recovery events (retry_initiated, retry_exhausted, workflow_escalated) |
| C5 | `ds_eo_openclaw/workflow/__init__.py` | MODIFY | Export new classes and constants |
| C6 | `tests/test_recovery_engine.py` | CREATE | Tests per spec §13 (12 test requirements) |
| C7 | Existing test suite | VERIFY | Ensure no regression (run full pytest suite) |

### Detailed Change Descriptions

#### C1 — Extend State Enum (state_engine.py, ~25 lines added)

Add 4 new states to the existing `State` enum:
```python
RECOVERING = "RECOVERING"           # S11 — workflow is being recovered
WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"  # S12 — human intervention required
RESUMED = "RESUMED"                 # S13 — recovery resumed from persisted state
ABORTED = "ABORTED"                 # S14 — workflow explicitly aborted
```

Add transition rules to `can_transition()` and `_TRANSITION_GATE`:
- From FAILED-like conditions: → WAITING_FOR_HUMAN, → ABORTED
- From RECOVERING: → RETRY_STAGE (resumes to previous phase)
- From WAITING_FOR_HUMAN: → RESUMED (user resumes manually)

**Important**: The existing 11-state state machine is NOT modified. These 4 new states are append-only additions that only activate when recovery is in effect.

#### C2 — RecoveryEngine (NEW, ~200 lines)

A single class that provides:
- `detect_failure(state_engine)` → FailureInfo dict
- `determine_recovery(failure_info, config)` → RecoveryAction enum
- `execute_recovery(action, state_engine)` → transition result
- `is_safe_to_resume()` → bool (verifies prior gates completed)

Recovery policy table (deterministic):

| Failure Type | Current Phase | Retry Count | Action |
|---|---|---|---|
| Missing artifact | Any pre-G4 | < max_retries | RETRY_STAGE |
| Missing artifact | Any pre-G4 | ≥ max_retries | WAIT_FOR_HUMAN |
| Verification failure | Pre-G2 | < max_retries | RETRY_STAGE |
| Verification failure | Pre-G2 | ≥ max_retries | WAIT_FOR_HUMAN |
| Agent execution error | Any pre-G4 | < max_retries | RESUME_STAGE (retry agent session) |
| Agent execution error | Any pre-G4 | ≥ max_retries | WAIT_FOR_HUMAN |
| Stall/timeout | Any active phase | < max_retries | RETRY_STAGE (resend to same agent or new) |
| Stall/timeout | Any active phase | ≥ max_retries | WAIT_FOR_HUMAN |
| Unexpected interruption | Any active phase | — | RESUME_STATE (inspect persisted state) |

Retry budget is per-task, not per-retry-attempt. Once exhausted, the engine transitions to WAITING_FOR_HUMAN permanently for that task.

#### C3 — RecoveryState Persistence (NEW, ~150 lines)

Manages persistence of recovery state:
- `save(state, task_id)` → writes recovery_state.json alongside dispatcher_state.json
- `load(task_id)` → dict with all required fields from spec §8
- `can_resume()` → validates persisted state integrity before resume

Format matches spec §8 YAML structure (stored as JSON for Python interoperability):
```json
{
  "task_id": "TASK_DS_EO_028",
  "mode": "automatic",
  "current_gate": "G3",
  "status": "RUNNING",
  "failure": { "type": "verification_failed", "message": "...", "timestamp": "..." },
  "recovery": { "attempts": 1, "last_action": "RETRY_STAGE", "next_action": "RESUME" }
}
```

#### C4 — Notification Types (notifications.py, ~30 lines added)

Add to FAILURE_NOTIFICATIONS:
- `retry_initiated` — retry count and backoff info
- `retry_exhausted` — escalation to human
- `workflow_escalated` — full diagnostic summary
- `recovery_resumed` — resume confirmation

#### C5, C6, C7 — Exports, Tests, Regression

Standard integration steps.

---

## 3. Acceptance Criteria (derived from spec §14)

| # | Criterion | Verification Method |
|---|---|---|
| A1 | Existing automatic mode executes normally | Run existing auto-advance tests; verify no new transitions in normal path |
| A2 | Defined failure conditions can be detected | Unit test `RecoveryEngine.detect_failure()` with each failure type (§5) |
| A3 | Workflow state distinguishes execution, failure, and recovery states | Verify State enum has all required states; test transition matrix |
| A4 | Recovery actions are deterministic and policy-driven | Table-driven tests mapping (failure_type, phase, retry_count) → action |
| A5 | Retry limits configurable and enforced | Test with max_retries=0, 1, 2, 3; verify behavior at boundary |
| A6 | Workflow state survives process interruption/restart | Write recovery_state.json, load in new engine instance, verify resume path |
| A7 | Previously completed gates preserved | Resume after G1+G2 → verify they are not repeated (audit log check) |
| A8 | DS-EO enters WAITING_FOR_HUMAN when automatic recovery inappropriate | Test: verification failure at G4 + max_retries reached → state = WAITING_FOR_HUMAN |
| A9 | Recovery events auditable | Verify each recovery action writes to audit log with required fields |
| A10 | Required gates cannot be silently bypassed | Integration test: attempt direct transition from RECOVERING to COMPLETED → reject |
| A11 | Existing manual mode remains functional | Run manual mode tests; verify no auto-advance occurs |
| A12 | Automated tests cover failure and recovery paths | pytest passes with ≥ 90% coverage on new modules |
| A13 | Full regression test suite passes | `python -m pytest` — zero failures across all existing tests |
| A14 | Relevant documentation updated | Update `ds_eo_openclaw/workflow/README.md` (or docstring) with new module docs |

---

## 4. Risk Assessment

### High Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| New states break existing transition logic | Medium | High | All new transitions are additive; no existing rules modified. Transition matrix tested exhaustively. |
| Persistence format divergence from dispatcher_state.json | Medium | Medium | Recovery state stored as parallel JSON file (recovery_state.json) — never modifies existing dispatcher_state.json |
| Resume logic incorrectly resuming across gate boundaries | High | Critical | `is_safe_to_resume()` explicitly checks each required gate artifact exists before resuming |

### Medium Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Notification types collide with existing FAILURE_NOTIFICATIONS | Low | Low | New keys use "recovery_" prefix, distinct from existing blocker/stalled/repeated_failure keys |
| Test coverage gaps on edge cases | Medium | Medium | Spec §13 defines 12 specific test requirements — each maps to a dedicated test method |

### Low Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Code complexity in RecoveryEngine | Low | Medium | Enforce ≤ 200 lines; keep policy table as data-driven lookups, not if/else chains |
| Non-goals creep (AI diagnosis, distributed scheduling) | Low | Critical | Explicitly document non-goals in plan; reviewer checks against spec §15 list |

### Mitigation Strategy

- **Principle of minimal change**: RecoveryEngine reads existing state artifacts; it never writes them. It only writes recovery_state.json and audit entries.
- **No refactoring**: All existing files receive additive changes only (enum extensions, dict merges). No class redesigns, no method signature changes.
- **Data-driven policy**: The recovery action table is a plain Python dict — easily audited, tested, and replaced if needed later.

---

## 5. Implementation Phases (for Implementer)

### Phase 1 — State Enum Extension + RecoveryEngine skeleton (EST: 45 min)
- Extend State enum in state_engine.py
- Create recovery_engine.py with empty methods
- Add placeholder notification types
- Unit tests for new states and transition rules

### Phase 2 — Recovery Policy Implementation (EST: 60 min)
- Implement `detect_failure()` for all 6 failure types (§5)
- Implement `determine_recovery()` with policy table
- Implement `execute_recovery()` with correct transitions
- Unit tests for each failure→action mapping

### Phase 3 — Persistence + Resume (EST: 45 min)
- Create recovery_state.py with save/load/can_resume
- Wire RecoveryEngine to persistence layer
- Test interrupted-state round-trip

### Phase 4 — Integration + Regression (EST: 60 min)
- Export new classes from `__init__.py`
- Write integration tests per spec §13
- Run full regression suite
- Update documentation

**Total EST: ~3.5 hours**

---

## 6. Non-Goals (per spec §15 — verified throughout implementation)

The following are **explicitly out of scope** and must NOT be implemented:
- ❌ Redesigning automatic workflow execution (existing state engine stays as-is)
- ❌ AI-based failure diagnosis (rule-based policy only)
- ❌ Distributed task scheduling
- ❌ Notification delivery (just define types; existing channel routing is separate)
- ❌ Web dashboard
- ❌ Major protocol redesign
- ❌ Unrelated architectural refactoring

---

## 7. Files Produced by This Plan

| File | Purpose | Author |
|------|---------|--------|
| `CTO_PLAN.md` | This document (plan + acceptance criteria) | CTO |
| Modified: `workflow/state_engine.py` | Add 4 new states + transition rules | Implementer |
| Created: `workflow/recovery_engine.py` | Unified recovery policy engine | Implementer |
| Created: `workflow/recovery_state.py` | Persistent recovery state management | Implementer |
| Modified: `workflow/notifications.py` | Add recovery notification types | Implementer |
| Modified: `workflow/__init__.py` | Export new classes | Implementer |
| Created: `tests/test_recovery_engine.py` | Tests per spec §13 | Implementer |
| CTO_APPROVAL.md | Final approve/reject (after review) | CTO |

---

*Submitted for G1 user approval.*
