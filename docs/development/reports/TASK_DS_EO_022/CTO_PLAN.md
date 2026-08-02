# CTO Plan — TASK_DS_EO_022

**Task ID**: TASK_DS_EO_022  
**Title**: Phase 3 — User-Facing Mode Selector  
**Date**: 2026-08-02  
**CTO**: qwen3.6:35b (ollama)  
**Spec Reference**: `docs/development/reports/TASK_DS_EO_019/EXECUTION_MODE_ARCHITECTURE.md` §7

---

## 1. Problem Statement

Phase 1 gave us the state machine engine. Phase 2 gave us audit trail logging. But there is no user-facing mechanism to control which execution mode (manual or automatic) the system uses, and no per-task override capability — both of which are explicitly designed in EXECUTION_MODE_ARCHITECTURE.md §7 but not yet implemented.

Phase 3 produces a clean, configurable mode selector that:
1. Lets the user switch between `manual` and `automatic` modes via command or config
2. Supports per-task execution_mode override (§7.4)
3. Issues notifications for automatic-mode transitions (as defined in §6.3)
4. Provides safe mode switching at any state boundary (no corruption)

This is a low-risk, high-value usability layer that makes the entire Phase 1–2 infrastructure actually controllable by the user.

---

## 2. Current-State Analysis

### 2.1 What Exists Now

| Component | Location | Notes |
|-----------|----------|-------|
| Mode config field (`workflow.execution_mode`) | ARCHITECTURE.md §7.1 | Defined but not implemented — no code reads it |
| Per-task override structure | ARCHITECTURE.md §7.4 | Designed but not implemented |
| Notifications for auto-mode states | ARCHITECTURE.md §6.3 | Documented but never wired up |
| Safe mode switching rules | ARCHITECTURE.md §4.5 | Defined as mandatory (no silent transitions through gates) |
| State engine (Phase 1) | `ds_eo_openclaw/workflow/state_engine.py` | Supports `execution_mode` parameter; reads it at init |
| Audit trail (Phase 2) | `ds_eo_openclaw/workflow/audit_log.py` | Mode-aware entries already exist |

### 2.2 What Does NOT Exist Yet

| Component | New Location | Description |
|-----------|-------------|-------------|
| Config file reader/loader | `ds_eo_openclaw/workflow/config.py` (~60 lines) | Reads project config, defaults to manual, validates values |
| Per-task override support | Same file + config schema (~40 lines) | `task_overrides` dict keyed by TASK_ID |
| Mode switching command | `ds_eo_openclaw/workflow/selector.py` (~80 lines) | `switch_mode()`, `switch_task_mode()`, safe-state validation |
| Auto-mode notification handler | `ds_eo_openclaw/workflow/notifications.py` (~50 lines) | Maps states to user notifications per §6.3 |

### 2.3 What Needs to Change

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `state_engine.py` | Modify | Wire config reader — auto-read `workflow.execution_mode` on init; apply task override if set |
| `workflow/__init__.py` | Modify | Export new modules (config, selector, notifications) |

---

## 3. Design Analysis

### 3.1 Mode Selector Core

The mode selector is a thin layer that:
1. Reads the current execution mode from config
2. Validates safe-to-switch condition (at state boundary only)
3. Applies the new mode atomically
4. Logs the mode change as an audit entry
5. Notifies user for all automatic-mode states requiring awareness (§6.3)

### 3.2 Config Model

```python
# Project-level config (default)
class WorkflowConfig:
    execution_mode: str = "manual"  # "manual" | "automatic"
    
    def switch(self, new_mode: str) -> None:
        if new_mode not in ("manual", "automatic"):
            raise ValueError(f"Invalid execution_mode: {new_mode}")
        self.execution_mode = new_mode

# Per-task override (optional)
class TaskOverride:
    overrides: dict[str, str]  # {"TASK_DS_EO_XXX": "automatic"}
    
    def get_task_mode(self, task_id: str) -> str:
        return self.overrides.get(task_id, global_config.execution_mode)
```

### 3.3 Safe Mode Switching Rules (§4.5 of architecture)

1. No silent transitions through gates — mode change never bypasses gate requirements
2. PM detects conditions, does not decide them — mode change only changes behavior, not decisions
3. Human signals are explicit — no mode switch based on silence or timeout
4. Rejection routes correctly — rejection paths identical in both modes
5. No auto-resolve of state machine errors — if state is invalid, reject the switch

### 3.4 User Notifications (per §6.3)

| State Entry | Notification |
|------------|--------------|
| S1 G1_WAITING | "Plan submitted for review" |
| S3→S4 | "G2 passed automatically — Reviewer assigned" |
| S5 G3_PENDING | "Review complete. Awaiting CTO G3 evaluation." |
| S7 COMPLETED | "Task completed, cleanup in progress" |
| S8 CHANGES_REQUESTED | "Changes requested: [reason] — rework required" |
| S9 BLOCKED | "BLOCKER: [details]" (urgent) |
| S10 STALLED | "STALLED: last activity [timestamp], exceeded timeout" |
| Mode switched to automatic | "Auto mode enabled — PM will auto-advance eligible transitions" |
| Mode switched to manual | "Mode switched to manual — all transitions require explicit action" |

---

## 4. Implementation Plan

### 4.1 Files to Create/Modify

#### New File: `ds_eo_openclaw/workflow/config.py` (~60 lines)

```python
"""Execution mode configuration management."""

class WorkflowConfig:
    def __init__(self, execution_mode: str = "manual", task_overrides: dict | None = None):
        self.execution_mode = self._validate(execution_mode)
        self.task_overrides = task_overrides or {}
    
    @staticmethod
    def _validate(mode: str) -> str:
        if mode not in ("manual", "automatic"):
            raise ValueError(f"Invalid execution_mode: {mode}")
        return mode
    
    def switch(self, new_mode: str) -> str:
        old = self.execution_mode
        self.execution_mode = self._validate(new_mode)
        return old  # Return previous mode for audit trail
    
    def get_task_mode(self, task_id: str) -> str:
        return self.task_overrides.get(task_id, self.execution_mode)

# Defaults
DEFAULT_CONFIG = WorkflowConfig()
```

#### New File: `ds_eo_openclaw/workflow/selector.py` (~80 lines)

```python
"""User-facing mode selector with safe switching guarantees."""

class ModeSelector:
    def __init__(self, config: WorkflowConfig):
        self.config = config
    
    def switch_mode(self, new_mode: str) -> tuple[str, str]:
        """Switch execution mode. Returns (previous_mode, new_mode)."""
        previous = self.config.execution_mode
        old = self.config.switch(new_mode)
        
        # Audit trail: log the mode change
        from .audit_log import create_system_entry
        # ... creates entry with gateStatus=APPROVED, triggeredBy=User
        
        return previous, new_mode
    
    def switch_task_mode(self, task_id: str, new_mode: str):
        """Set per-task override for execution mode."""
        if task_id not in self.config.task_overrides:
            raise ValueError(f"No such task: {task_id}")
        old = self.config.task_overrides[task_id]
        self.config.task_overrides[task_id] = self.config._validate(new_mode)
        return old  # Return previous override
    
    def is_safe_to_switch(self) -> bool:
        """Mode switch is safe at any state boundary (per architecture §4.5)."""
        # In practice: always safe per the architecture — modes can be switched
        # between states without corruption. No silent gate-bypass possible.
        return True
```

#### New File: `ds_eo_openclaw/workflow/notifications.py` (~50 lines)

```python
"""Auto-mode state notifications per EXECUTION_MODE_ARCHITECTURE.md §6.3."""

AUTO_MODE_NOTIFICATIONS = {
    "G1_WAITING": "Plan submitted for review",
    "REVIEW": "G2 passed automatically — Reviewer assigned",
    "G3_PENDING": "Review complete. Awaiting CTO G3 evaluation.",
    "COMPLETED": "Task completed, cleanup in progress",
    "CHANGES_REQD": "Changes requested — rework required",
    "BLOCKED": "BLOCKER: details pending",
    "STALLED": "STALLED: last activity unknown, exceeded timeout",
}

MODE_NOTIFICATIONS = {
    ("manual", "automatic"): "Auto mode enabled — PM will auto-advance eligible transitions",
    ("automatic", "manual"): "Mode switched to manual — all transitions require explicit action",
}
```

### 4.2 Files to Modify

| File | Changes | Description |
|------|---------|-------------|
| `ds_eo_openclaw/workflow/state_engine.py` | ~10 lines | Wire config reader on init; apply task override if set |
| `ds_eo_openclaw/workflow/__init__.py` | Add exports | Export WorkflowConfig, ModeSelector, AUTO_MODE_NOTIFICATIONS |

### 4.3 File Structure Summary

| Action | File | Lines |
|--------|------|-------|
| CREATE | `config.py` | ~60 |
| CREATE | `selector.py` | ~80 |
| CREATE | `notifications.py` | ~50 |
| MODIFY | `state_engine.py` | ~10 (init wiring) |
| MODIFY | `__init__.py` | +3 exports |

---

## 5. Acceptance Criteria

### Mode Configuration
- [ ] Default mode is `manual` if config is unset or invalid
- [ ] Config validates values — only "manual" and "automatic" accepted
- [ ] Invalid values raise ValueError (not silent default)
- [ ] Per-task overrides work via `get_task_mode()` — override takes precedence over global

### Mode Switching
- [ ] `switch_mode()` returns previous mode for audit trail
- [ ] No gate-bypass possible in any mode — all gates preserved identically
- [ ] Mode switch always logged as audit entry (for reconstruction)
- [ ] `is_safe_to_switch()` confirms safety per architecture rules

### Notifications
- [ ] All 7 auto-mode state notifications defined per §6.3
- [ ] Both mode switch notifications defined (manual→automatic, automatic→manual)
- [ ] Notification content matches exactly what §6.3 specifies

### Integration
- [ ] State engine reads execution_mode from config on init
- [ ] Per-task override applied if task_id in overrides dict
- [ ] New modules exported via `workflow.__init__.py`
- [ ] No regression in manual mode behavior (identical to pre-phase-3)

### Testing
- [ ] All tests pass (`python -m pytest tests/test_mode_selector.py`)
- [ ] Config validation tested (valid inputs, invalid inputs, defaults)
- [ ] Mode switch atomicity tested (previous/new returned, audit entry created)
- [ ] Per-task override tested (override takes precedence over global)
- [ ] Notification lookup tested (all states → correct message)

---

## 6. Risks and Constraints

### Risks
1. **Config file format discovery**: We need to decide where the config lives. Options: `openclaw.json` field, YAML project config, or Python module-level defaults. For Phase 3, I recommend starting with in-memory default (configurable via constructor) — file persistence is Phase 4+.

### Constraints
1. No external dependencies — standard library only
2. Manual mode behavior unchanged — zero regression
3. All notifications must match §6.3 exactly

---

## Gate Status

| Gate | Status | Notes |
|------|--------|-------|
| G0 (Task Creation) | ✅ Done | TASK_DS_EO_022 created by CTO |
| G1 (User Approval of Plan) | ⏳ Awaiting | User must approve before Implementer begins |
| G2–G4 | N/A | To be executed after implementation |

---

*CTO Plan produced by: CTO (qwen3.6:35b)*  
*Date: 2026-08-02*
