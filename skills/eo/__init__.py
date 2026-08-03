"""DS-EO OpenClaw Edition - /eo Mode Commands Skill.

This skill provides user-facing slash commands for switching and displaying execution mode.

Available Commands:
* /eo mode manual - Switch to manual execution mode
* /eo mode automatic - Switch to automatic execution mode  
* /eo mode status - Show current mode and per-task overrides
* /eo mode override TASK_<id> <mode|off> - Set or remove per-task override

Implementation Notes:
All commands use the existing ModeSelector API from ds_eo_openclaw.workflow.selector.
No production code changes were made for this skill. It only adds user-facing presentation logic.
"""
