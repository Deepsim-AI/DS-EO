# DELEGATE — TASK_DS_EO_023

**Task ID**: TASK_DS_EO_023  
**Title**: Phase 4 — Failure/Stall Handling Refinements  
**From**: CTO (qwen3.6:35b)  
**To**: Implementer (ollama/ornith:35b)  
**Gate**: G1 approved by user on 2026-08-02  
**Spec Reference**: docs/development/reports/TASK_DS_EO_019/EXECUTION_MODE_ARCHITECTURE.md §§9.2–9.6

---

## What to Implement

### Deliverable 1: `ds_eo_openclaw/workflow/timeout_config.py` (~50 lines)
- **TimeoutConfig class**: Default timeouts per state (G1_WAITING, G3_PENDING, FINAL_APPROVAL = None/exempt for human-owned states), configurable overrides dict, unknown state names raise ValueError

### Deliverable 2: `ds_eo_openclaw/workflow/stall_detection.py` (~80 lines)
- **StallDetector class**: check() method — compares elapsed time against timeout config, returns stall info dict or None; human-owned states always return None regardless of elapsed time

### Deliverable 3: `ds_eo_openclaw/workflow/escalation.py` (~60 lines)
- **EscalationChain class**: Blocker escalation path (PM → CTO via DELEGATE with blocker context, then User if no resolution in timeout)
- Rate limiting: max one escalation per 5 minutes for same blocker

### Deliverable 4: `ds_eo_openclaw/workflow/failure_detector.py` (~50 lines)
- **FailureDetector class**: Tracks rework count per task, threshold-based actions at each rejection (1st=standard rework, 2nd=user warning with pattern, 3rd+=CTO escalation with failure report), resets on completion

### Deliverable 5: Update `ds_eo_openclaw/workflow/state_engine.py`
- Integrate TimeoutConfig into detect_state() — auto-detect STALLED state
- Wire stall detection result to trigger S9/BLOCKED or S10/STALLED transitions
- Add _record_transition_audit for failure transitions (T9)

### Deliverable 6: Update `ds_eo_openclaw/workflow/notifications.py`
- Add failure notification types: blocker_detected, task_stalled, repeated_failure_escalated

### Deliverable 7: Update `ds_eo_openclaw/workflow/__init__.py`
- Export: TimeoutConfig, StallDetector, EscalationChain, FailureDetector

---

## Acceptance Criteria (from CTO plan)

1. All 11 states have configured timeouts or are explicitly exempt (human-owned)
2. Unknown state names in overrides raise ValueError
3. Human-owned states (G1_WAITING, G3_PENDING, FINAL_APPROVAL) always exempt from stall detection regardless of elapsed time
4. Non-exempt states correctly flag as stalled when timeout exceeded
5. Blocker creates T9 audit entry with escalation chain (PM → CTO → User)
6. Rate limiting prevents >1 escalation per 5 minutes for same blocker
7. First rejection → standard rework, second → user warning, third+ → CTO escalation
8. Rework count resets on successful completion
9. Audit log rotation at >500 entries or >1MB with reconstruction verification
10. State engine auto-detects STALLED via timeout config
11. Failure notifications wired to dispatch system
12. All modules exported via __init__.py
13. No regression in manual or automatic mode behavior

---

## Constraints
- No external dependencies — standard library only (datetime, json)
- Timeout defaults match architecture §9.3 recommendations
- Human-owned states always exempt from stall detection in both modes
- Produce IMPLEMENTATION_REPORT.md simultaneously with completion claim

---

*Delegated by: CTO (qwen3.6:35b)*
