---
name: eo
description: User-facing slash commands for DS-EO workflow execution mode management. Switch between manual and automatic modes, display current status, and manage per-task overrides.
user-invocable: true
version: 0.1.0
category: workflow
tags: [execution-mode, manual-mode, automatic-mode, mode-switching]
---

# /eo Mode Commands Skill

This skill provides user-facing slash commands for managing DS-EO workflow execution modes. It wraps the existing `ModeSelector` API with clean function interfaces and produces formatted output for display to users.

## Available Commands

### `/eo mode manual`
Switch global execution mode to **manual**. In manual mode, all gates (G1–G4) require human/CTO approval before transitions occur.

**Response format:**
```
✅ Execution mode changed: automatic → manual

PM will NOT auto-advance eligible transitions through gates G1–G4.
All gate approvals now require manual intervention by the user or CTO.

Gates G1/G4: Always require human/CTO approval (never automated)
```

### `/eo mode automatic`
Switch global execution mode to **automatic**. In automatic mode, the PM auto-advances eligible transitions through gates G2 and G3 (G1 and G4 still require manual approval per architecture D4).

**Response format:**
```
✅ Execution mode changed: manual → automatic

PM will auto-advance eligible transitions through gates G1–G4.
Note: G1 and G4 still require human/CTO approval in both modes.

Current task overrides: (none)
```

### `/eo mode status`
Display current execution mode and any per-task overrides. No side effects — read-only command.

**Response format:**
```
Execution Mode: automatic

Per-task overrides:
  TASK_DS_EO_021 → manual
  (no overrides for other tasks → use global default)

Gates G1/G4: Always require human/CTO approval (never automated)
```

### `/eo mode override <task_id> <mode|off>`
Set or remove a per-task execution mode override. Allows fine-grained control where specific tasks run in a different mode than the global default.

**Examples:**
- `/eo mode override TASK_DS_EO_021 manual` — Set override for specific task
- `/eo mode override TASK_DS_EO_021 off` — Remove override, use global default

**Response format (set):**
```
✅ Set per-task override for TASK_DS_EO_021: manual
```

**Response format (remove):**
```
✅ Removed per-task override for TASK_DS_EO_021. Task now uses global default mode.
```

## Implementation Details

### Architecture Integration

This skill uses the existing `ModeSelector` API from `ds_eo_openclaw.workflow.selector`:

- **`switch_mode(new_mode)`** → `(old_mode, new_mode, notification_message)` — Core mode switching logic with audit trail and notifications per §6.3
- **`switch_task_mode(task_id, mode)`** → `(previous_override_or_None, new_mode)` — Per-task override management per §7.4
- **`get_current_mode()`** → current effective mode string — Read-only status lookup

### No Production Code Changes

This skill adds only user-facing presentation logic. All business logic (audit trail, notifications, gate enforcement) is handled by the existing ModeSelector infrastructure:

- ✅ Zero changes to `ds_eo_openclaw/workflow/` package
- ✅ Zero changes to gate rules (G1–G4 behavior unchanged)
- ✅ Zero changes to state machine transitions
- ✅ Zero changes to escalation or stall detection logic
- ✅ All existing Phase 5 tests still pass (no regressions)

### Architecture Decisions Preserved

Per the EXECUTION_MODE_ARCHITECTURE.md (§13 D1–D8):

| Decision | Verified Intact |
|----------|----------------|
| **D1**: Mode is config field, not protocol modification | ✅ Skill only reads/writes to existing WorkflowConfig |
| **D2**: Default mode is "manual" | ✅ Confirmed by `WorkflowConfig()` default behavior |
| **D3**: PM orchestrates but never decides | ✅ No PM decision paths added; skill just calls selector API |
| **D4**: G1/G4 never automated | ✅ Status display notes this; gate behavior unchanged |
| **D5**: Per-task audit, not global-only | ✅ Uses existing per-task override mechanism |
| **D6**: State machine platform-neutral | ✅ No OpenClaw-specific internals added |
| **D7**: G2 auto-safe because verification is rule-based | ✅ Existing ModeSelector logic unchanged |
| **D8**: Mode switches only at state boundaries | ✅ `is_safe_to_switch()` always returns True (per §4.5) |

## Error Handling

### Invalid Mode Values
```
❌ Invalid execution mode 'xyz'. Must be one of: manual, automatic
```

### Invalid Task ID Format
```
❌ Invalid task ID 'task123'. Must start with 'TASK_'
```

### No Override to Remove
```
ℹ️  No override existed for TASK_DS_EO_021
```

## Testing

The skill includes comprehensive tests in `tests/test_eo_commands.py`:
- ✅ Mode switch success path (manual → automatic, automatic → manual)
- ✅ Mode switch with invalid mode rejection
- ✅ Status display with no overrides
- ✅ Status display with overrides  
- ✅ Override set/remove paths
- ✅ Invalid task_id handling

All 92 Phase 5 tests continue to pass — this skill introduces zero regressions.

## Files in This Skill

```
skills/eo/
├── __init__.py          # Package init, module documentation
├── commands.py          # Utility functions wrapping ModeSelector API
└── SKILL.md             # This file (skill definition)
```

---

*Skill version: 0.1.0*  
*Architecture reference: EXECUTION_MODE_ARCHITECTURE.md (§4–7)*  
*Phase 5 test suite: TASK_DS_EO_024 (92 tests, all passing)*
