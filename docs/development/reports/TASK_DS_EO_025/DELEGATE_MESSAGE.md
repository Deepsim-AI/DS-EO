# DELEGATE — TASK_DS_EO_025

**Task ID**: TASK_DS_EO_025  
**From**: CTO (qwen3.6:35b)  
**To**: Implementer (ornith:35b)  
**Gate**: G1 approved  
**Date**: 2026-08-03  

---

## Task Scope

Create user-facing `/eo mode` slash commands for switching and displaying execution mode. This is a **greenfield skill** — only new files, zero changes to existing production code.

## Files to Create (4 files)

### 1. `skills/eo/SKILL.md` — Skill Definition
- SKILL.md with frontmatter declaring name="eo", description, user-invocable=true
- Agent instructions for handling `/eo mode <subcommand> [args]` invocations
- Subcommands: `manual`, `automatic`, `status`, `override <task_id> <mode|off>`

### 2. `skills/eo/commands.py` — Utility Functions
```python
# ds_eo_openclaw/skills/eo/commands.py
from ds_eo_openclaw.workflow.selector import ModeSelector, create_selector
from ds_eo_openclaw.workflow.config import WorkflowConfig

def get_current_mode() -> dict
    # Returns {execution_mode: str, task_overrides: dict}

def switch_to(mode: str) -> tuple[bool, str]
    # Calls selector.switch_mode(); returns (success, message)

def set_override(task_id: str, mode_or_off: str) -> tuple[bool, str]
    # Sets or removes per-task override; returns (success, message)

def format_status() -> str
    # Returns formatted status string for display to user
```

### 3. `tests/test_eo_commands.py` — Test Suite (~30 tests)
- Tests for all four utility functions
- Invalid mode rejection
- Override set/remove paths
- Status display with and without overrides

### 4. `skills/eo/__init__.py` — Package init (empty, for imports)

## Acceptance Criteria (must ALL be met)

1. `/eo mode manual` switches to manual and returns confirmation
2. `/eo mode automatic` switches to automatic and returns confirmation  
3. `/eo mode status` displays current mode + overrides + G1/G4 note
4. `/eo mode override TASK_<id> <mode>` sets override correctly
5. `/eo mode override TASK_<id> off` removes override
6. Invalid modes rejected with clear error message, no side effects
7. All Phase 5 tests still pass (no regressions) — the existing test suite must not break
8. `commands.py` imports from existing modules — no new business logic

## Constraints

- **Zero changes** to `ds_eo_openclaw/workflow/` package
- **Zero changes** to gate rules, state machine, or any existing behavior
- `commands.py` must use only the existing public API: `ModeSelector`, `WorkflowConfig`
- Tests must run with `pytest` and pass in the existing test infrastructure

## Implementation Instructions

1. Create directory `skills/eo/` under workspace root (`/home/deepsim/ds-eo-openclaw/skills/eo/`)
2. Write SKILL.md following AgentSkills spec format
3. Write commands.py with the four functions described above
4. Write tests in `tests/test_eo_commands.py`
5. Run full test suite: `python -m pytest` — must pass including existing Phase 5 tests
6. Verify no production code changes (git diff should show only new files)

## Architecture Notes

- The existing ModeSelector already produces audit trail entries and notifications on mode switch — reuse these hooks automatically
- Per-task overrides use the same mechanism as `switch_task_mode()` in the existing selector
- Default config is manual (`WorkflowConfig.DEFAULT_CONFIG`) — confirm this remains unchanged
- G1/G4 are never automated (per D4) — ensure status display notes this

---

*Implementation instructions produced by: CTO (qwen3.6:35b)*  
*Date: 2026-08-03*
