---
produced_by: pm
role: PM
task_id: TASK_20260808_001
gate: G0 (intake)
created_at: 2026-08-08T14:07:12.575624+00:00
---

# Task Manifest ←  TASK_20260808_001

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | `TASK_20260808_001` |
| **Created** | 2026-08-08T14:07:12.575624+00:00 |
| **Intake Status** | INTAKE |
| **Mode** | manual (default) |
| **Dispatcher State Path** | `docs/dispatchers/TASK_20260808_001/` |
| **Reports Directory** | `docs/development/reports/TASK_20260808_001/` |

## Available Artifacts

```
TASK_20260808_001/
├── TASK_REQUEST.md          ← User's verbatim request (preserved)
├── PM_ANALYSIS.md           ← PM interpretation/summary
├── INPUTS/                  ← User-provided files
│   ├── TASK_REQUEST.md
└── MANIFEST.md              ← This file (task metadata)
```

## Request Summary

Implement an OpenClaw Agent Session Health and Lifecycle Management capability within DS-EO.

The purpose is to continuously monitor agent sessions and identify sessions that are:

stale;
excessively large;
stuck;
repeatedly failing;
unable to compact;
orphaned;
otherwise unhealthy.

The system should provide safe, policy-driven actions to keep OpenClaw agent sessions operational and prevent session-related problems from degrading DS-EO workflows.

The primary goal is:

Prevent unhealthy OpenCla...
