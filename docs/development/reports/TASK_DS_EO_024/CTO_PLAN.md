# CTO Plan — TASK_DS_EO_024

**Task ID**: TASK_DS_EO_024  
**Title**: Phase 5 — Testing and Validation Suite  
**Date**: 2026-08-02  
**CTO**: qwen3.6:35b (ollama)  
**Spec Reference**: `docs/development/reports/TASK_DS_EO_019/EXECUTION_MODE_ARCHITECTURE.md` §12.7

---

## 1. Problem Statement

Phases 1–4 have built the complete Automatic Mode infrastructure:
- Phase 1: State machine engine (11 states, 12 transitions)
- Phase 2: Audit trail logging (14-field schema, integrity chain)
- Phase 3: Mode selector (manual/automatic switching + per-task overrides)
- Phase 4: Failure/stall handling (timeouts, escalation chains, repeated failure detection)

But there is no unified test suite that validates the system works correctly as a whole. Each phase has its own unit tests, but we need comprehensive integration testing across all phases, covering every combination of mode × state × edge case. Phase 5 produces this validation layer.

---

## 2. Current-State Analysis

### 2.1 What Exists Now (for testing)

| Component | Location | Notes |
|-----------|----------|-------|
| State engine tests | `tests/test_state_engine.py` | 14 tests — individual state detection/transition/auto-advance |
| Audit log tests | `tests/test_audit_log.py` | 20 tests — schema, persistence, reconstruction for single task |
| Mode selector tests | `tests/test_mode_selector.py` | 31 tests — config validation, switching, notifications, integration |
| Failure handling tests | `tests/test_failure_handling.py` | 33 tests — timeouts, stall detection, escalation chains, failure detection |

**Total existing tests: 98** (all passing)

### 2.2 What Does NOT Exist Yet (to be created)

| Component | New Location | Description |
|-----------|-------------|-------------|
| Manual mode regression suite | `tests/test_manual_mode_regression.py` (~100 lines) | Every gate, state transition, and handoff in manual mode — verify zero behavioral change |
| Auto-mode transition matrix | `tests/test_auto_mode_transitions.py` (~80 lines) | All 12 transitions × auto-advance = full coverage |
| Mode switching tests | `tests/test_mode_switching.py` (~80 lines) | 12 states × 2 switch directions = 24 scenarios (per §12.7 architecture spec) |
| Blocker/stall edge case tests | `tests/test_edge_cases.py` (~60 lines) | Timeout thresholds, escalation timing, race conditions |
| Audit reconstruction integration | `tests/test_audit_integration.py` (~40 lines) | Cross-task reconstruction using AUDIT_INDEX.json |
| Platform portability verification | `tests/test_platform_portability.py` (~30 lines) | Architecture doc cross-reference check (all §11 decisions verified) |
| Test runner / conftest | `tests/conftest.py` or `tests/__init__.py` | Fixtures for fake task directories, config factories |

### 2.3 What Needs to Change

All new code — Phase 5 is a **testing phase**. No production code changes needed, only test infrastructure and test cases.

---

## 3. Design Analysis

### 3.1 Test Categories (per architecture §12.7)

#### Category A: Manual Mode Regression Tests
Every transition, gate check, state detection, notification, and handoff in manual mode — verified against current production behavior. Zero behavioral changes allowed.

| Test Group | Count | Scope |
|-----------|-------|-------|
| State transitions (manual) | 12 | Every `can_transition()` pair produces same result as auto-advance logic |
| Gate enforcement (G1/G2/G3/G4) | 8 | All gates reject in manual mode; no gate is bypassable |
| Audit trail (manual) | 5 | Manual transitions produce identical audit entries to auto mode |
| Mode selector (manual default) | 3 | Config defaults to manual; switch to automatic works; back works |
| Notification (manual) | 2 | No auto-mode notifications fired in manual mode |

#### Category B: Auto-Mode Transition Tests
Every state → next valid state transition verified with audit entry, correct gateStatus, and notification dispatch.

| Test Group | Count | Scope |
|-----------|-------|-------|
| All 12 transitions (auto) | 12 | S0→S1, G1_WAITING→IMPLEMENTATION, etc. — each produces AuditEntry + correct state |
| Auto-advance vs manual transition parity | 12 | Both paths produce identical audit entries and state results |

#### Category C: Mode Switching Tests (§12.7 requirement)
Per the architecture spec: **12 states × 2 switch directions = 24 test scenarios.**

| Test Group | Count | Scope |
|-----------|-------|-------|
| Switch manual → automatic at each state | 8 | Valid switch from non-terminal states (not BLOCKED/STALLED) |
| Switch automatic → manual at each state | 8 | Same — preserves current workflow state without corruption |
| Switch at terminal states (COMPLETED, TASK_OPEN) | 2 | Edge cases for mode switches at state boundaries |
| Rapid successive switch testing | 4 | Two consecutive switches, verify final state is consistent |

#### Category D: Blocker/Stall Edge Cases
Per architecture §§9.2–9.6 and risk register.

| Test Group | Count | Scope |
|-----------|-------|-------|
| Timeout threshold boundary conditions | 5 | Exactly at timeout (should flag), just under (should not) |
| Escalation timing / rate limiting | 3 | Multiple blockers within 5-minute window → only one escalates |
| Repeated failure counting edge cases | 4 | Reset on completion, cross-task counter isolation |
| Concurrent stall detection | 2 | Two tasks stalled simultaneously, both reported independently |

#### Category E: Audit Trail Reconstruction Verification
Cross-task reconstruction using AUDIT_INDEX.json as the entry point.

| Test Group | Count | Scope |
|-----------|-------|-------|
| Reconstruct TASK_DS_EO_020 (clean path) | 1 | Verify full state history from audit data alone |
| Reconstruct TASK_DS_EO_023 (with rework loop) | 1 | Verify rework loops are correctly identified |
| Cross-task index navigation | 1 | AUDIT_INDEX.json contains all expected tasks with latestState |

#### Category F: Platform Portability Verification
Cross-reference every architecture design decision (§13) against the implementation.

| Test Group | Count | Scope |
|-----------|-------|-------|
| All 8 design decisions verified | 8 | D1–D8 each verified in code (mode is config not protocol, default=manual, PM no authority, G1/G4 never automated, per-task audit, platform-neutral, G2 auto-safe, boundary-only switches) |

### 3.2 Test Infrastructure

```python
# tests/conftest.py — shared fixtures
from ds_eo_openclaw.workflow.state_engine import StateEngine, State
from ds_eo_openclaw.workflow.audit_log import AuditLog, AuditEntry
from ds_eo_openclaw.workflow.config import WorkflowConfig
from ds_eo_openclaw.workflow.selector import ModeSelector

@pytest.fixture
def fake_task_dir(tmp_path):
    """Create a temporary task directory with simulated artifacts."""
    d = tmp_path / "TASK_FAKE"
    d.mkdir()
    return str(d)

@pytest.fixture
def manual_config():
    """Default WorkflowConfig in manual mode."""
    return WorkflowConfig(execution_mode="manual")

@pytest.fixture
def automatic_config():
    """WorkflowConfig in automatic mode."""
    return WorkflowConfig(execution_mode="automatic")

@pytest.fixture
def selector(manual_config):
    """ModeSelector with manual config."""
    return ModeSelector(manual_config)
```

---

## 4. Implementation Plan

### 4.1 Files to Create

#### New: `tests/test_manual_mode_regression.py` (~100 lines, ~25 tests)
All manual mode paths verified against production behavior:
- All state transitions produce same result whether triggered by auto_advance() or manual_transition()
- Every gate (G1/G2/G3/G4) rejects in manual mode
- Audit entries for manual transitions identical to auto mode entries
- Mode defaults to manual, switch to automatic works
- No auto-mode notifications fired

#### New: `tests/test_auto_mode_transitions.py` (~80 lines, ~20 tests)
All 12 transitions verified in automatic mode with audit trail and state results:
- Each transition produces AuditEntry with correct gateStatus
- Auto-advance parity test: same (from_state, to_state) produces identical result whether triggered by auto or manual

#### New: `tests/test_mode_switching.py` (~80 lines, ~24+ tests)
Architecture-mandated 12 states × 2 directions = 24 scenarios:
- Manual→automatic switch at each of 8 non-terminal states
- Automatic→manual switch at each of 8 non-terminal states  
- Switches at terminal states (COMPLETED, TASK_OPEN)
- Rapid successive switches verify consistency

#### New: `tests/test_edge_cases.py` (~60 lines, ~14 tests)
Timeout/stress edge cases:
- Exactly-at-timeout boundary condition
- Escalation rate limiting under load
- Repeated failure counter isolation across tasks
- Concurrent stall detection

#### New: `tests/test_audit_integration.py` (~40 lines, ~3 tests)
Cross-task reconstruction from AUDIT_INDEX.json:
- Reconstruct TASK_DS_EO_020 clean path
- Reconstruct TASK_DS_EO_023 with rework loops
- Verify AUDIT_INDEX.json contains all tasks

#### New: `tests/test_platform_portability.py` (~30 lines, ~8 tests)
Each design decision (§13 D1–D8) verified against implementation code.

### 4.2 No Changes to Production Code
Phase 5 is pure testing — no production code modifications needed.

---

## 5. Acceptance Criteria

### Regression Testing (Category A)
- [ ] All manual mode transitions produce identical results whether via auto_advance() or manual_transition()
- [ ] All 4 gates reject in manual mode with no bypass possible
- [ ] Manual audit entries are functionally identical to auto-mode entries
- [ ] Mode defaults to "manual" if not configured
- [ ] No automatic-mode notifications fire in manual mode

### Transition Testing (Category B)
- [ ] All 12 state transitions verified in automatic mode with AuditEntry
- [ ] Every transition's gateStatus is correct per architecture §3.4

### Mode Switching (Category C — Architecture Requirement)
- [ ] 24 mode-switch scenarios covered (12 states × 2 directions)
- [ ] No workflow corruption after any switch
- [ ] State preserved through all switches
- [ ] Rapid successive switches produce consistent final state

### Edge Cases (Category D)
- [ ] Timeout boundary conditions tested (at, just under, just over)
- [ ] Escalation rate limiting works correctly (max 1 per 5 minutes)
- [ ] Repeated failure counters isolated per task
- [ ] Concurrent stall detection reports each task independently

### Audit Integration (Category E)
- [ ] Full history reconstructable from AUDIT_INDEX.json for TASK_DS_EO_020
- [ ] Full history reconstructable from AUDIT_INDEX.json for TASK_DS_EO_023 (with rework loop)
- [ ] Cross-task index contains all 4 phases' tasks

### Platform Portability (Category F)
- [ ] D1: Mode is config field, not protocol modification — verified in code
- [ ] D2: Default mode is "manual" — verified by default behavior
- [ ] D3: PM orchestrates but never decides — verified no PM decision paths exist
- [ ] D4: G1/G4 never automated — verified both gates require human/CTO
- [ ] D5: Per-task audit, not global-only — verified AUDIT_LOG.json per task
- [ ] D6: State machine platform-neutral — verified no OpenClaw-specific internals
- [ ] D7: G2 auto-safe because verification is rule-based — verified in code
- [ ] D8: Mode switches only at state boundaries — verified in selector code

### Test Infrastructure
- [ ] All 100+ tests pass with `python -m pytest` (no failures, no warnings)
- [ ] Zero production code changes required for Phase 5
- [ ] Each test is deterministic and isolated (fixtures ensure this)
- [ ] Test categories A–F are clearly separable in file structure

---

## 6. Risks and Constraints

### Risks
1. **No real runtime to test against**: This is unit-level testing; we can't test actual PM session orchestration in automated tests. Mitigation: the integration tests verify all production code paths, not just abstract state machines.

2. **Audit log cross-task dependency**: test_audit_integration.py depends on actual TASK_DS_EO_020 and TASK_DS_EO_023 audit logs existing. Mitigation: tests read from `docs/reports/` directory; if those files don't exist yet, the test is skipped (pytest.skip).

### Constraints
1. No production code changes — testing phase only
2. Tests must pass on both Linux and Windows (if platform portability is a real concern)
3. No external testing frameworks beyond pytest (standard library + pytest already in use)

---

## Gate Status

| Gate | Status | Notes |
|------|--------|-------|
| G0 (Task Creation) | ✅ Done | TASK_DS_EO_024 created by CTO |
| G1 (User Approval of Plan) | ⏳ Awaiting | User must approve before testing begins |
| G2–G4 | N/A | To be executed after implementation |

---

*CTO Plan produced by: CTO (qwen3.6:35b)*  
*Date: 2026-08-02*
