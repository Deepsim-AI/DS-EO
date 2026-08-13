# DS-EO Dispatcher Protocol — Runtime Contract

**Version**: 0.1.0  
**Status**: Design  
**Scope**: All components within the dispatcher package

---

## Overview

This protocol defines how the Dispatcher component communicates with:
1. The **agent registry** (source of truth for available agents)
2. **OpenClaw gateway** (for session spawning and cross-agent messaging)
3. **Other DS-EO components** (protocols, templates, etc.)

---

## 1. Agent Registry Contract

### Loading
- Read from `agents_list.json` at workspace root
- On first load, cross-validate against gateway config (`openclaw config get agents`)
- If an agent in `agents_list.json` is not registered with the gateway → **block** with error
- If a gateway-registered agent is NOT in `agents_list.json` → log warning but allow (may be external)

### Resolution
```python
# Registry.resolve(target_agent_id, current_task_id) -> DispatchTarget
# Returns:
#   {
#     "agent_id": "implementer",
#     "workspace": "/home/deepsim/ds_eo_openclaw",
#     "spawn_command": "sessions_spawn(agent='implementer', context='isolated')",
#     "model": "ollama/ornith:35b",
#     "tool_policy": {...}
#   }
```

---

## 2. Workflow Engine Contract

### State Machine Rules
1. **Sequential gate order enforced**: Cannot transition from G0 directly to G3 — must pass through each intermediate gate
2. **Self-loops are valid**: Rejection transitions (G1_REJECT, G2_INCOMPLETE, G3_CHANGES, G4_REJECT) return work to the producing agent for rework
3. **Terminal state**: S5_COMPLETE is the only terminal phase; no outgoing transitions
4. **Stall detection runs automatically** on each phase entry

### Event Schema (all events use communication_protocol.md message format)
```json
{
  "type": "<EVENT_TYPE>",
  "taskId": "TASK_YYYYMMDD_NNN",
  "phase_from": "S1_PLANNING",
  "phase_to": "S2_IMPLEMENTATION",
  "transition": "G1_APPROVE",
  "source_agent": "cto",
  "target_agent": "implementer",
  "payload": {},
  "timestamp": "ISO8601"
}
```

### Validation Rules (enforced before each transition)
1. Current phase exists in workflow definition
2. Target phase is in `transitions_to` list for the given transition
3. All `requires_artifacts` for the transition exist in task directory
4. Authority check: the transitioning agent matches the authorized agent role
5. No gate can be bypassed — G1 must complete before any G2 action

---

## 3. Session Dispatch Contract

### How Dispatcher Spawns Agents

The Dispatcher uses OpenClaw's `sessions_spawn` tool exclusively for agent-to-agent handoffs:

| Transition | sessions_spawn parameters |
|-----------|--------------------------|
| TASK_OPEN (PM → CTO) | `agent='cto', context='isolated'`, prompt includes TASK_OPEN payload |
| DELEGATE (CTO → Implementer) | `agent='implementer', context='isolated'`, prompt includes DELEGATE payload |
| IMPL_COMPLETE (Implementer → Reviewer) | `agent='reviewer', context='isolated'`, prompt includes review_request template |
| REVIEW_COMPLETE (Reviewer → CTO) | `agent='cto', context='isolated'`, prompt includes approval_request template |
| TASK_STALLED (PM → CTO escalation) | `agent='cto', context='isolated'`, prompt includes stall details |

### Context Isolation Mandate

Per protocol requirement (from TASK_DS_EO_005/006):
- **Every cross-phase handoff MUST use `context="isolated"`**
- The receiving agent gets no session history from the producing agent
- All context is provided explicitly through the prompt payload
- This prevents context contamination and enforces clean role boundaries

### Session Key Convention

Spawned sessions use: `agent:<target_agent_id>:subagent:<task_uuid>`

The dispatcher does NOT manage these directly; OpenClaw handles session routing.

---

## 4. State Persistence Contract

### Location
```
docs/dispatcher/<TASK_ID>/dispatcher_state.json
```

### Schema
```json
{
  "version": "0.1.0",
  "taskId": "TASK_YYYYMMDD_NNN",
  "current_phase": "S2_IMPLEMENTATION",
  "workflow_version": "1.0",
  "agent_registry_checksum": "<sha256 of agents_list.json>",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "transition_history": [
    {
      "transition": "G0_ENTRY",
      "from_phase": null,
      "to_phase": "S0_OPEN",
      "timestamp": "ISO8601",
      "triggered_by": "pm"
    }
  ],
  "stall_checks": {
    "last_check": "ISO8601",
    "last_artifact_update": "ISO8601",
    "stalled": false
  }
}
```

### Persistence Rules
- Write after every transition (atomic write to temp file, then rename)
- Read on every engine operation (no stale state caching)
- Validate `agent_registry_checksum` matches current agents_list.json — if mismatched, block and alert
- PM is the only agent that writes state outside its own task directory

---

## 5. Gateway Bindings Contract (Entry Points Only)

Gateway-level bindings are **minimal** — they only route incoming external requests to the correct initial agent. All internal workflow routing lives in the dispatcher.

```json
// openclaw.json bindings (entry points only)
{
  "bindings": [
    {
      "agentId": "pm",
      "match": { "channel": "webchat", "peer": { "kind": "command", "id": "/eo.task" } }
    },
    {
      "agentId": "cto",
      "match": { "channel": "webchat", "peer": { "kind": "command", "id": "/eo.approve" } }
    },
    {
      "agentId": "reviewer",
      "match": { "channel": "webchat", "peer": { "kind": "command", "id": "/eo.review" } }
    }
  ]
}
```

The dispatcher **never writes or modifies these bindings**. They are managed externally.

---

## 6. Error Handling Contract

### Invalid Transition Attempt
1. Log error: `Cannot transition from {current_phase} via {transition} — not in workflow definition`
2. Write `TRANSITION_ERROR.md` in task directory
3. Notify PM of the invalid state
4. Do NOT execute the transition

### Missing Artifact (requires_artifacts check fails)
1. Log error: `Missing required artifact: {missing_file}`
2. Return specific guidance to requesting agent
3. Do NOT block — just report what's missing

### Agent Not Found in Registry
1. Error: `Target agent '{agent_id}' not found in agent registry`
2. Notify PM immediately
3. Block the transition until agent is registered

### Gateway Session Spawn Failure
1. Retry once with exponential backoff (2s)
2. If still failing, write error to task directory
3. Notify PM of dispatch failure
4. Do NOT silently drop the handoff
