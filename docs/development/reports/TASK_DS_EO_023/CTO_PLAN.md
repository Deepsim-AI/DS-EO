# CTO Plan — TASK_DS_EO_023

**Task ID**: TASK_DS_EO_023  
**Title**: Phase 4 — Failure/Stall Handling Refinements  
**Date**: 2026-08-02  
**CTO**: qwen3.6:35b (ollama)  
**Spec Reference**: `docs/development/reports/TASK_DS_EO_019/EXECUTION_MODE_ARCHITECTURE.md` §§9.2–9.6

---

## 1. Problem Statement

Phase 1 gave us the state machine engine. Phase 2 gave us audit trail logging. Phase 3 gave us the mode selector. But in automatic mode, when things go wrong there is no enforcement mechanism for stall detection timeouts, blocker escalation chains, or repeated failure patterns. These are all designed in §9.2–§9.6 but never implemented.

Phase 4 produces the operational resilience layer — configurable timeouts per state, PM monitoring cycle for timestamp comparison, escalation chains for blockers, and detection of repeated review failures with automatic CTO escalation. Without this, automatic mode cannot reliably self-manage tasks that encounter problems.

---

## 2. Current-State Analysis

### 2.1 What Exists Now

| Component | Location | Notes |
|-----------|----------|-------|
| State engine module | `ds_eo_openclaw/workflow/state_engine.py` | Detects states from files but no activity timestamp tracking |
| Audit log module | `ds_eo_openclaw/workflow/audit_log.py` | Full schema, but no rotation/archival for long tasks |
| Mode config + selector | `ds_eo_openclaw/workflow/config.py`, `selector.py` | Can switch modes but no monitoring integration |
| Notification system | `ds_eo_openclaw/workflow/notifications.py` | 7 auto-mode notifications defined, none wired to failure paths |

### 2.2 What Does NOT Exist Yet (to be created)

| Component | New Location | Description |
|-----------|-------------|-------------|
| Timeout configuration | `ds_eo_openclaw/workflow/timeout_config.py` (~50 lines) | Per-state configurable timeouts, default values, validation |
| Stall detection engine | `ds_eo_openclaw/workflow/stall_detection.py` (~80 lines) | PM monitoring cycle, timestamp comparison, configurable exemptions |
| Blocker escalation chain | `ds_eo_openclaw/workflow/escalation.py` (~60 lines) | Escalation path from PM → CTO → User with rate limiting |
| Repeated failure detector | `ds_eo_openclaw/workflow/failure_detector.py` (~50 lines) | Tracks rework loop count, triggers escalation after threshold |
| Audit log rotation | `ds_eo_openclaw/workflow/audit_log.py` (modify) | Rotation/archival for long-lived task audit logs |

### 2.3 What Needs to Change

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `state_engine.py` | Modify | Integrate timeout config + stall detection; auto-detect STALLED state on each cycle |
| `notifications.py` | Modify | Wire failure notifications (§9.2–§9.6) to the notification dispatch system |

---

## 3. Design Analysis

### 3.1 Timeout Configuration (§9.3)

Configurable timeout per state, with human-ownership exemptions:

```python
class TimeoutConfig:
    DEFAULTS = {
        "TASK_OPEN":      86400,   # 24h — user takes time to review plans
        "G1_WAITING":     None,    # Human-owned, exempt from stall detection
        "IMPLEMENTATION": 36000,   # 10h — reasonable coding window
        "WAITING_G2":      3600,   # 1h — implementer writes report
        "REVIEW":         7200,    # 2h — review window
        "G3_PENDING":     None,    # Human-owned (CTO evaluation), exempt
        "FINAL_APPROVAL": None,    # Human-owned (CTO decision), exempt
        "COMPLETED":      None,    # Terminal state
        "CHANGES_REQD":   7200,    # 2h — rework submission window
        "BLOCKED":        1800,    # 30min — blockers should be resolved fast
        "STALLED":        None,    # Already stalled
    }
    
    def __init__(self, overrides: dict | None = None):
        self.timeouts = dict(self.DEFAULTS)
        if overrides:
            for k, v in overrides.items():
                if k not in self.DEFAULTS and k != "enabled":
                    raise ValueError(f"Unknown state: {k}")
                self.timeouts[k] = v
    
    def is_exempt(self, state: str) -> bool:
        """Human-ownership states are exempt from stall detection."""
        return self.timeouts.get(state) is None
```

### 3.2 Stall Detection Engine (§9.3 + §10.4 in architecture risk register)

The PM monitoring cycle compares activity timestamps against configured timeouts:

```python
class StallDetector:
    def check(self, task_id: str, current_state: str, last_activity_time: datetime):
        """Check if task is stalled based on timeout config."""
        config = TimeoutConfig()
        
        # Human-ownership states are exempt
        if config.is_exempt(current_state):
            return None  # No stall possible in human-owned state
        
        timeout = config.timeouts.get(current_state)
        elapsed = (datetime.now(timezone.utc) - last_activity_time).total_seconds()
        
        if elapsed >= timeout:
            return {
                "taskId": task_id,
                "currentState": current_state,
                "elapsedSeconds": elapsed,
                "timeoutSeconds": timeout,
                "lastActivityTimestamp": last_activity_time.isoformat(),
            }
        return None  # Not stalled
```

### 3.3 Blocker Escalation Chain (§9.2)

When a blocker is detected:
1. PM creates BLOCKED audit entry (T9 in architecture)
2. PM alerts CTO immediately with blocker details
3. If no resolution within timeout → escalate to user
4. Rate limiting: max one escalation per 5 minutes to prevent spam

### 3.4 Repeated Failure Detection (§9.6)

When the same task enters rework more than 3 times total:
1. First rejection (G3 or G4): Standard rework loop — documented
2. Second rejection: Warning notification to user with pattern details
3. Third+ rejection: Automatic escalation to CTO with failure pattern report
4. CTO decides whether to revise scope, replace implementer, or accept

### 3.5 Audit Log Rotation (per architecture risk register §14)

For long-lived tasks with many rework iterations:
- Audit logs > 500 entries or > 1MB get rotated to `AUDIT_LOG_ROTATED_YYYYMMDD.json`
- Latest log file always contains recent entries for reconstruction
- Index entry tracks rotation history

---

## 4. Implementation Plan

### 4.1 Files to Create/Modify

#### New: `ds_eo_openclaw/workflow/timeout_config.py` (~50 lines)
TimeoutConfig class with per-state defaults and configurable overrides. Validation: unknown state names rejected, None = exempt (human-owned).

#### New: `ds_eo_openclaw/workflow/stall_detection.py` (~80 lines)
StallDetector class — monitors activity timestamps against timeout config. PM monitoring cycle integration point (called per-state on each cycle). State exemption logic for human-ownership states (§6.1 of architecture).

#### New: `ds_eo_openclaw/workflow/escalation.py` (~60 lines)
EscalationChain class — blocker escalation path (PM → CTO → User). Rate limiting to prevent spam (5-minute window). Repeated failure detection integration.

#### New: `ds_eo_openclaw/workflow/failure_detector.py` (~50 lines)
FailureDetector class — tracks rework count per task. Threshold-based escalation at 1st, 2nd, and 3rd+ rejections. Pattern report generation for CTO evaluation.

#### New: `tests/test_failure_handling.py` (~120 lines)
Timeout config validation (defaults, overrides, unknown states rejected). Stall detection for all 5 non-exempt states with configurable thresholds. Blocker escalation chain (CTO alert → user escalation with rate limiting). Repeated failure detector (count-based escalation at thresholds). Audit log rotation (split large logs, verify reconstruction still works).

#### Modify: `ds_eo_openclaw/workflow/state_engine.py` (~30 lines)
Integrate TimeoutConfig into state detection — auto-detect STALLED on detect_state(). Wire stall detection result to trigger S9/S10 transitions.

#### Modify: `ds_eo_openclaw/workflow/notifications.py` (~20 lines)
Add failure notification types (blocker, stalled, repeated failure).

### 4.2 File Structure Summary

| Action | File | Lines |
|--------|------|-------|
| CREATE | `timeout_config.py` | ~50 |
| CREATE | `stall_detection.py` | ~80 |
| CREATE | `escalation.py` | ~60 |
| CREATE | `failure_detector.py` | ~50 |
| CREATE | `test_failure_handling.py` | ~120 |
| MODIFY | `state_engine.py` | ~30 |
| MODIFY | `notifications.py` | ~20 |
| MODIFY | `__init__.py` | +4 exports |

---

## 5. Acceptance Criteria

### Timeout Configuration
- [ ] All 11 states have configured timeouts or are explicitly exempt (human-owned)
- [ ] Unknown state names in overrides raise ValueError
- [ ] Human-owned states (G1_WAITING, G3_PENDING, FINAL_APPROVAL) always exempt

### Stall Detection
- [ ] Non-exempt states correctly flag as stalled when timeout exceeded
- [ ] Exempt states never flagged regardless of elapsed time
- [ ] Stalled task triggers STALLED state transition with audit entry and notification

### Blocker Escalation
- [ ] Blocker creates T9 audit entry with escalation chain
- [ ] CTO alerted first, then user if no resolution in timeout
- [ ] Rate limiting prevents >1 escalation per 5 minutes for same blocker

### Repeated Failure Detection
- [ ] First rejection → standard rework (no special handling)
- [ ] Second rejection → warning notification to user with pattern details
- [ ] Third+ rejection → automatic escalation to CTO with failure report
- [ ] Rework count resets on successful completion

### Audit Log Rotation
- [ ] Logs > 500 entries or > 1MB trigger rotation
- [ ] Rotated files named AUDIT_LOG_ROTATED_YYYYMMDD.json
- [ ] Latest log file contains recent entries; reconstruction still works post-rotation

### Integration
- [ ] State engine auto-detects STALLED state via timeout config on detect_state()
- [ ] Failure notifications wired to notification dispatch system
- [ ] All modules exported via workflow.__init__.py
- [ ] No regression in manual or automatic mode behavior

### Testing
- [ ] All tests pass (`python -m pytest tests/test_failure_handling.py`)
- [ ] Timeout config: defaults, overrides, invalid input testing
- [ ] Stall detection: all 5 non-exempt states tested with configurable thresholds
- [ ] Blocker escalation: full chain + rate limiting tested
- [ ] Repeated failure: count-based escalation at all thresholds
- [ ] Audit rotation: split + reconstruction verification

---

## 6. Risks and Constraints

### Risks
1. **Stall false positives (per architecture risk register)**: Long-running legitimate reviews/implementation trigger stall alerts. Mitigation: configurable timeouts per state + human-owned exemptions. The architecture already addresses this in §9.3.
2. **Audit log rotation complexity**: Splitting large audit logs for reconstruction verification adds code paths. Mitigation: rotation only triggers at high thresholds (500 entries / 1MB).

### Constraints
1. No external dependencies — standard library only (`datetime`, `json`)
2. Timeout defaults match architecture §9.3 recommendations where specified
3. Human-owned states (§6.1) always exempt from stall detection in both modes

---

## Gate Status

| Gate | Status | Notes |
|------|--------|-------|
| G0 (Task Creation) | ✅ Done | TASK_DS_EO_023 created by CTO |
| G1 (User Approval of Plan) | ⏳ Awaiting | User must approve before Implementer begins |
| G2–G4 | N/A | To be executed after implementation |

---

*CTO Plan produced by: CTO (qwen3.6:35b)*  
*Date: 2026-08-02*
