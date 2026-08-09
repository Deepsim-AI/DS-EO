---
produced_by: ollama/qwen3.6:35b
role: CTO
task_id: TASK_20260808_001
gate: G2 (handoff to Implementer)
produced_at: 2026-08-08T14:14:00Z
session_id: cto-webchat-session
---

# G2 Handoff — TASK_20260808_001

## To the Implementer

You are receiving this handoff from the CTO after G1 (plan) was approved by the user.

### Your Task ID
**TASK_20260808_001** — Verify against directory name: `docs/development/reports/TASK_20260808_001/`

### Deliverable Location
Write all deliverables to: `/home/deepsim/ds_eo_openclaw/docs/development/reports/TASK_20260808_001/`

### Approved Plan
Full plan is in `CTO_PLAN.md`. Implement **exactly as specified** — no independent architectural decisions.

### Files to Create (9 new files):

```
ds_eo_openclaw/session_health/__init__.py       # C9
ds_eo_openclaw/session_health/enums.py           # C1 (~80 lines)
ds_eo_openclaw/session_health/config.py          # C8 (~100 lines)
ds_eo_openclaw/session_health/discoverer.py      # C2 (~250 lines) — extends LivenessChecker
ds_eo_openclaw/session_health/classifier.py      # C3 (~200 lines)
ds_eo_openclaw/session_health/policy.py          # C4 (~200 lines)
ds_eo_openclaw/session_health/executor.py        # C5 (~200 lines)
ds_eo_openclaw/session_health/monitor.py         # C6 (~150 lines)
ds_eo_openclaw/session_health/audit.py           # C7 (~120 lines)
tests/test_session_health.py                     # C11 (18 tests)
```

### Files to Modify (3 minor):

```
ds_eo_openclaw/intake/manifest.py      # Add session health metadata field
agents/pm.md                           # Document capability for PM awareness  
CHANGELOG.md + PROJECT_STATUS.md       # Update per Post-G4 requirements
```

### Key Constraints
- **Phase order is mandatory**: Phase 1→2→3→4→5→6. No skipping.
- All thresholds in config.py — no arbitrary values in code.
- Integrate with RecoveryEngine (ds_eo_openclaw/workflow/recovery_engine.py) — do not duplicate recovery logic.
- All monitoring defaults to OBSERVING (dry-run).
- Every lifecycle action verified post-execution.
- Active task sessions protected from all destructive actions.

### Test Requirements
Run `python -m pytest tests/test_session_health.py -v` and `python -m pytest tests/ -v --ignore=tests/test_session_health.py` to confirm no regressions.

### Report Format
Upon completion, produce:
1. `IMPLEMENTATION_REPORT.md` with all changes, test results, any deviations from plan
2. Include phase-by-phase confirmation in the report

---

**CTO confirms: Phase 1 artifact (discoverer.py + config.py) is now your deliverable. Produce the complete implementation.**
