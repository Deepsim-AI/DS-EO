# DS-EO Dispatcher — State Schema Reference

**Version**: 0.1.0  
**Scope**: All persistent state files produced/consumed by the dispatcher

---

## 1. Task Directory Structure (with dispatcher)

```
docs/dispatcher/
├── TASK_YYYYMMDD_NNN/
│   ├── dispatcher_state.json          ← Phase + transition history
│   ├── agent_registry_snapshot.json   ← Snapshot of agents at task creation
│   ├── workflow_ref.yaml              ← Copy of workflow definition version used
│   └── dispatch_log.jsonl             ← Append-only event log (JSON Lines)
├── TASK_YYYYMMDD_NNN_2/
│   └── ...
└── INDEX.md                            ← Maps task IDs → paths
```

## 2. dispatcher_state.json Schema

```jsonc
{
  "version": "0.1.0",
  "taskId": "TASK_YYYYMMDD_NNN",
  
  // Current workflow state
  "current_phase": "S2_IMPLEMENTATION",          // One of S0-S5
  "workflow_version": "1.0",                     // Which workflow_def is active
  
  // Agent registry validation
  "agent_registry_checksum": "sha256hex...",     // Validate agents_list.json hasn't changed
  "registry_agents": ["cto", "implementer", "reviewer", "pm"],
  
  // Lifecycle timestamps
  "created_at": "2026-08-05T10:00:00Z",
  "updated_at": "2026-08-05T14:30:00Z",
  "completed_at": null,                          // Set when S5_COMPLETE is reached
  
  // Phase tracking
  "phase_history": [
    {
      "phase": "S0_OPEN",
      "entered_at": "2026-08-05T10:00:00Z",
      "left_at": "2026-08-05T10:05:00Z",
      "agent": "pm"
    },
    {
      "phase": "S1_PLANNING",
      "entered_at": "2026-08-05T10:05:00Z",
      "left_at": null,                          // Currently active = null
      "agent": "cto"
    }
  ],
  
  // All transitions (immutable history)
  "transition_history": [
    {
      "id": "txn_001",
      "transition": "G0_ENTRY",
      "from_phase": null,
      "to_phase": "S0_OPEN",
      "timestamp": "2026-08-05T10:00:00Z",
      "triggered_by_agent": "pm",
      "event_type": "TASK_OPEN",
      "payload_summary": "New feature request for EO system",
      "artifacts_verified": [],
      "result": "success"
    }
  ],
  
  // Stall detection state
  "stall_checks": {
    "last_check": "2026-08-05T14:00:00Z",
    "last_artifact_update": "2026-08-05T12:00:00Z",  // Last file write in task dir
    "stalled": false,
    "stall_alert_sent_at": null,
    "current_phase_entered": "2026-08-05T10:05:00Z"
  },
  
  // Current pending work (what the active agent is doing)
  "pending_work": {
    "task_id": "TASK_YYYYMMDD_NNN",
    "assigned_to": "cto",
    "work_type": "CTO_PLAN.md creation",
    "spawn_session_key": "agent:cto:subagent:abc123",
    "spawned_at": "2026-08-05T10:05:00Z"
  }
}
```

## 3. dispatch_log.jsonl Schema (one JSON object per line)

Each line is a complete event record:

```json
{
  "seq": 4,
  "ts": "2026-08-05T11:30:00Z",
  "event_type": "G2_COMPLETE",
  "phase_from": "S2_IMPLEMENTATION",
  "phase_to": "S3_REVIEW",
  "source_agent": "implementer",
  "target_agent": "reviewer",
  "artifacts_verified": ["IMPLEMENTATION_REPORT.md"],
  "spawned_session_key": "agent:reviewer:subagent:def456",
  "success": true,
  "notes": "All G2 checklist items verified"
}
```

## 4. agent_registry_snapshot.json Schema (task creation snapshot)

Captures the agent registry at the time a task was created for audit purposes:

```json
{
  "checksum": "sha256hex...",
  "snapshot_at": "2026-08-05T10:00:00Z",
  "source_file": "agents_list.json",
  "agents": [
    {
      "id": "cto",
      "model": "ollama/qwen3.6:35b",
      "workspace": "/home/deepsim/ds_eo_openclaw"
    }
  ]
}
```

## 5. INDEX.md Schema (task directory index)

Simple TSV for fast lookups:

```
taskId   path                                      status      last_transition
TASK_20260805_001  docs/dispatcher/TASK_20260805_001   COMPLETE    G4_APPROVE
TASK_20260805_002  docs/dispatcher/TASK_20260805_002   IN_PROGRESS G3_CHANGES
```
