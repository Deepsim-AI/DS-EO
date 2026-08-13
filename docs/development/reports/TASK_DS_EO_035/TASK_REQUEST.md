---
produced_by: user
session_id: b98d4488-5428-4eba-99c8-ecce7da4f2a2
produced_at: 2026-08-08T23:14:00-07:00
role: User
task_id: TASK_DS_EO_035
---

# User Request — TASK_DS_EO_035

**Original user request:** "Let us do the Phase 7 compaction integration with real OpenClaw API first"

**Context:** CTO plan for TASK_DS_EO_035 has been approved at G1. User requested to use EO automatic mode for execution.

## Requirements
- Implement real OpenClaw API integrations for all 5 lifecycle actions (COMPACT, ARCHIVE, CLOSE, MONITOR, WARN)
- Create new `openclaw_api.py` module with thin CLI wrappers
- Update `executor.py`, `discoverer.py`, and tests
- Zero breaking changes to existing API surface
- All 38 existing tests pass + new integration tests
