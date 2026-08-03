# DELEGATE — TASK_DS_EO_022

**Task ID**: TASK_DS_EO_022  
**Title**: Phase 3 — User-Facing Mode Selector  
**From**: CTO (qwen3.6:35b)  
**To**: Implementer (ollama/ornith:35b)  
**Gate**: G1 approved by user on 2026-08-02  
**Spec Reference**: docs/development/reports/TASK_DS_EO_019/EXECUTION_MODE_ARCHITECTURE.md §7 + §6.3

---

## What to Implement

### Deliverable 1: `ds_eo_openclaw/workflow/config.py` (~60 lines)
- **WorkflowConfig class**: Default mode "manual", validates values (only "manual"/"automatic"), switch() method returns previous mode, get_task_mode() applies per-task override precedence

### Deliverable 2: `ds_eo_openclaw/workflow/selector.py` (~80 lines)
- **ModeSelector class**: switch_mode() (atomic mode change with audit trail log), switch_task_mode() (per-task override), is_safe_to_switch() (always true per architecture §4.5 — no silent gate bypass possible in any mode)

### Deliverable 3: `ds_eo_openclaw/workflow/notifications.py` (~50 lines)
- **AUTO_MODE_NOTIFICATIONS dict**: All 7 state notifications per §6.3 exactly
- **MODE_NOTIFICATIONS dict**: Both direction switch messages

### Deliverable 4: Update `ds_eo_openclaw/workflow/state_engine.py`
- Wire config reader on init — auto-read execution_mode from WorkflowConfig
- Apply per-task override if task_id in overrides dict

### Deliverable 5: Update `ds_eo_openclaw/workflow/__init__.py`
- Export: WorkflowConfig, ModeSelector, AUTO_MODE_NOTIFICATIONS

---

## Acceptance Criteria (from CTO plan)

1. Default mode is "manual" when config unset or invalid
2. Config validates — only "manual"/"automatic" accepted, invalid raises ValueError
3. switch_mode() returns previous mode for audit trail
4. No gate-bypass possible in any mode
5. Mode switch always logged as audit entry
6. Per-task overrides work (override takes precedence over global)
7. is_safe_to_switch() confirms safety per architecture rules
8. All 7 auto-mode state notifications defined per §6.3 exactly
9. Both mode switch notifications defined
10. State engine reads execution_mode from config on init
11. Per-task override applied if task_id in overrides dict
12. No regression in manual mode behavior

---

## Constraints
- No external dependencies — standard library only
- Manual mode behavior unchanged — zero regression required
- All notifications must match §6.3 exactly (word-for-word)
- Produce IMPLEMENTATION_REPORT.md simultaneously with completion claim

---

*Delegated by: CTO (qwen3.6:35b)*
