# CTO Plan — TASK_DS_EO_025

**Task ID**: TASK_DS_EO_025  
**Title**: User-Facing /eo Mode Commands (manual, automatic, status)  
**Date**: 2026-08-03  
**CTO**: qwen3.6:35b (ollama)  
**Spec Reference**: EXECUTION_MODE_ARCHITECTURE.md (§4–7), Phase 5 test suite (TASK_DS_EO_024)

---

## 1. Problem Statement

The Automatic Mode infrastructure is fully implemented (Phases 1–5) but users have no convenient way to interact with it. There are no slash commands for:

- `/eo mode manual` — switch execution mode to manual
- `/eo mode automatic` — switch execution mode to automatic  
- `/eo mode status` — show current mode and per-task overrides

This is a usability gap that should be resolved as soon as possible. The Phase 5 test suite validates all underlying ModeSelector/WorkflowConfig behavior (97/100 review score, all acceptance criteria met). This task adds the user-facing surface only — zero changes to execution semantics or gate rules.

---

## 2. Current-State Analysis

### 2.1 What Already Exists

| Component | Location | Role |
|-----------|----------|------|
| `ModeSelector.switch_mode()` | `ds_eo_openclaw/workflow/selector.py` | Core mode switch logic — returns (old, new, notification) |
| `ModeSelector.switch_task_mode()` | `ds_eo_openclaw/workflow/selector.py` | Per-task override management |
| `ModeSelector.is_safe_to_switch()` | `ds_eo_openclaw/workflow/selector.py` | Safety gate (always True per §4.5) |
| `WorkflowConfig.execution_mode` | `ds_eo_openclaw/workflow/config.py` | Global mode storage |
| `WorkflowConfig.task_overrides` | `ds_eo_openclaw/workflow/config.py` | Per-task override map |
| `ModeSelector.get_task_effective_mode()` | `ds_eo_openclaw/workflow/selector.py` | Resolve effective mode for a task |
| Phase 5 test suite (92 tests) | `tests/test_mode_switching.py`, etc. | Validates all switch scenarios |

### 2.2 What Does NOT Exist

| Component | Needed For |
|-----------|-----------|
| Slash command `/eo` | User-facing entry point |
| `/eo mode manual` handler | Switch to manual mode |
| `/eo mode automatic` handler | Switch to automatic mode |
| `/eo mode status` handler | Display current state |
| Notification integration | Inform user of mode change |

### 2.3 No Changes to Execution Semantics

This task does **not** modify any gate rules, transition logic, or automation behavior. The slash commands are a thin presentation layer over the existing ModeSelector API:

- `/eo mode manual` calls `selector.switch_mode("manual")` → same result as Phase 1–4
- `/eo mode automatic` calls `selector.switch_mode("automatic")` → same result as Phase 1–4
- `/eo mode status` reads config and displays it → no side effects

All gate rules (G1–G4), state machine transitions, audit logging, and escalation behavior remain identical. The architecture spec (§13 D1–D8) is fully preserved.

---

## 3. Design Analysis

### 3.1 Integration Point: OpenClaw Skill

OpenClaw's skill system is the appropriate integration point for user-invocable commands:

- Skills register as slash commands via `user-invocable: true` in SKILL.md frontmatter
- The `/eo` command routes to the agent (model-based dispatch, not tool-dispatch) — this ensures the agent can handle context, provide explanations, and produce audit entries
- Skill is placed in `<workspace>/skills/eo/` for workspace-level visibility

**Why a skill, not a plugin:** This is a workflow feature specific to DS-EO, not a general-purpose capability. A skill keeps it scoped, portable, and installable without requiring a full plugin.

### 3.2 Command Syntax

```
/eo mode manual       — Switch global mode to manual
/eo mode automatic    — Switch global mode to automatic
/eo mode status       — Show current mode + per-task overrides
/eo mode override TASK_<id> manual   — Set per-task override (optional)
/eo mode override TASK_<id> off      — Remove per-task override
```

Arguments are parsed by the agent's skill instructions (model-based routing). The underlying implementation uses `ModeSelector.switch_mode()` and `ModeSelector.switch_task_mode()`.

### 3.3 Output Format

Each command returns a structured response:

**On success (mode switch):**
```
✅ Execution mode changed: manual → automatic

PM will auto-advance eligible transitions through gates G1–G4.
Note: G1 and G4 still require human/CTO approval in both modes.

Current task overrides: (none)
```

**On /eo mode status:**
```
Execution Mode: automatic

Per-task overrides:
  TASK_DS_EO_021 → manual
  (no overrides for other tasks → use global default)

Gates G1/G4: Always require human/CTO approval (never automated)
```

**On error (invalid mode):**
```
❌ Invalid execution mode 'xyz'. Must be one of: manual, automatic
```

### 3.4 Audit Trail

Every mode switch produces an audit entry via the existing `ModeSelector.switch_mode()` flow:
- The ModeSelector already logs every switch to the audit trail
- Notification is dispatched per §6.3 of the architecture spec
- No additional audit infrastructure needed — we reuse existing hooks

---

## 4. Implementation Plan

### 4.1 Files to Create

#### New: `skills/eo/SKILL.md` (the skill definition)
SKILL.md with YAML frontmatter declaring the slash command and instructions for how the agent should handle `/eo mode <subcommand> [args]` invocations. Contains:
- Mode description in frontmatter (`name`, `description`, `user-invocable`)
- Implementation instructions (how to route each subcommand)
- Error handling rules

#### New: `skills/eo/commands.py` (utility functions for the skill)
Python helper that provides clean function wrappers around the ModeSelector API:
```python
def get_current_mode():
    """Returns dict: { 'execution_mode': str, 'task_overrides': dict }"""

def switch_to(mode: str):
    """Switches mode via ModeSelector. Returns (success: bool, message: str)"""

def set_override(task_id: str, mode: str | None):
    """Sets or removes per-task override. Returns success and message."""

def format_mode_status():
    """Formats a human-readable status string."""
```

These are lightweight wrappers — no business logic, just clean API access. The actual logic lives in `ds_eo_openclaw/workflow/selector.py` (existing) and `ds_eo_openclaw/workflow/config.py` (existing).

### 4.2 Files to Modify

**None.** Zero changes to production code or existing protocols. This task creates new files only.

---

## 5. Acceptance Criteria

### Command Availability
- [ ] `/eo mode manual` is available as a slash command
- [ ] `/eo mode automatic` is available as a slash command
- [ ] `/eo mode status` is available as a slash command
- [ ] `/eo mode override <task_id> <mode|off>` is available
- [ ] Skill registers correctly with OpenClaw (appears in skill list)

### Mode Switching (/eo mode manual / automatic)
- [ ] Calls `ModeSelector.switch_mode()` with correct argument
- [ ] Returns confirmation message showing old mode → new mode transition
- [ ] Dispatches mode switch notification per §6.3 architecture spec
- [ ] Produces audit trail entry (via existing selector infrastructure)
- [ ] Invalid modes produce clear error message without side effects

### Status (/eo mode status)
- [ ] Displays current global execution mode
- [ ] Displays per-task overrides if any exist
- [ ] Displays note about G1/G4 gate behavior (never automated)
- [ ] Handles clean output when no overrides exist

### Per-Task Override (/eo mode override)
- [ ] `/eo mode override TASK_<id> manual` sets override correctly
- [ ] `/eo mode override TASK_<id> off` removes override
- [ ] Invalid task_id format is rejected with helpful message
- [ ] Invalid mode for override is rejected

### Architecture Preservation
- [ ] No changes to gate rules (G1–G4 behavior unchanged)
- [ ] No changes to state machine transitions
- [ ] No changes to escalation or stall detection logic
- [ ] All existing Phase 5 tests still pass (no regressions)
- [ ] D1–D8 architecture decisions verified intact

### Test Coverage
- [ ] Tests for `commands.py` utility functions:
  - Mode switch success path
  - Mode switch with invalid mode
  - Status display with no overrides
  - Status display with overrides
  - Override set/remove paths
  - Invalid task_id handling
- [ ] Skill frontmatter valid (parseable YAML, correct name/description)

---

## 6. Risks and Constraints

### Risks
1. **Skill command registration**: The skill must be in the correct workspace directory for OpenClaw to discover it. Placement at `skills/eo/SKILL.md` under the workspace root is required.

2. **No existing ModeSelector instance**: The slash command needs a way to access the current WorkflowConfig/ModeSelector state. The implementation should use the module-level `DEFAULT_CONFIG` from `config.py` or accept config injection. For simplicity, we'll use direct imports from the existing modules — no new dependency injection needed.

3. **No production code changes**: Per architecture constraint §5 "No Changes to Production Code", we only add skill files and utility wrappers. The ModeSelector/WorkflowConfig classes are read-only for this task.

### Constraints
1. Zero changes to `ds_eo_openclaw/workflow/` package (existing infrastructure is sufficient)
2. Zero changes to gate rules, state machine, or any existing behavior
3. Tests must be compatible with pytest and run in the existing test suite
4. Skill frontmatter follows AgentSkills spec format

---

## Gate Status

| Gate | Status | Notes |
|------|--------|-------|
| G0 (Task Creation) | ✅ Done | TASK_DS_EO_025 created by CTO |
| G1 (User Approval of Plan) | ⏳ Awaiting | User must approve before implementation begins |
| G2–G4 | N/A | To be executed after implementation |

---

*CTO Plan produced by: CTO (qwen3.6:35b)*  
*Date: 2026-08-03*
