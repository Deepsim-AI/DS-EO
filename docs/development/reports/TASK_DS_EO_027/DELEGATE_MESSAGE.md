# DELEGATE MESSAGE — TASK_DS_EO_027

**From**: CTO (G1 Approved)  
**To**: Implementer  
**Phase**: S1_PLANNING → S2_IMPLEMENTATION  
**Date**: 2026-08-05  
**Priority**: P1  

## Plan Reference
- CTO_PLAN.md: `/home/deepsim/ds-eo-openclaw/docs/development/reports/TASK_DS_EO_027/CTO_PLAN.md`

## Assignment

Implement the DS-EO Workflow Supervisor / Watchdog — a reliability layer for automatic mode that detects stalled/failed/lost agent sessions and auto-recovers or escalates to user.

### Deliverables
1. `dispatcher/session_dispatch/supervisor.py` — Core Supervisor: heartbeat monitoring, progress detection, timeout enforcement, retry/recovery, escalation, notifications
2. `dispatcher/session_dispatch/liveness.py` — Session existence + health verification against OpenClaw gateway
3. Updated `dispatcher/engine.py` — SupervisorStateOverlay integrated into WorkflowEngine
4. `docs/development/protocols/supervisor_protocol.md` — New protocol defining Supervisor events and requirements
5. `config-templates/supervisor_config.example.json` — Config schema with defaults
6. Updated `dispatcher/SKILL.md` — PM awareness of Supervisor
7. `tests/test_supervisor.py` (~250 lines) — Tests for stuck, aborted, failed, lost sessions + integration

### Requirements
- Per AC-1 through AC-8 defined in CTO_PLAN.md §12 (Acceptance Criteria)
- Supervisor only auto-recovers in automatic mode; observer-only in manual mode
- All timeouts/thresholds configurable per-task via spec override
- Notification system extensible (webchat primary, others via config)

### Notes
- Prior DS-EO infra work (TASK_DS_EO_026) fixed phantom sessions — this task prevents them by adding liveness verification into spawn + continuous monitoring
