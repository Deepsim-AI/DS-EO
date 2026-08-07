# DS-EO Supervisor Protocol — Watchdog Runtime Contract

**Version**: 0.1.0  
**Status**: Design  
**Scope**: Workflow Supervisor / Watchdog component (TASK_DS_EO_027)  
**Related**: `dispatcher/session_dispatch/supervisor.py`, `dispatcher/session_dispatch/liveness.py`

---

## Overview

The Supervisor is a reliability layer that monitors spawned agent sessions during automatic mode. It detects stalled, failed, or lost sessions and triggers recovery (retry) or escalation to the user. The supervisor does NOT modify the core workflow state machine — it runs as an overlay on top of S0-S5 phase tracking.

**Key constraint**: Supervisor auto-recovery only activates in **automatic mode**. In manual mode it operates in observer-only mode (warns but never auto-recovers).

---

## 1. Agent Lifecycle States

Every agent session managed by the supervisor follows this lifecycle:

```
NOT_CREATED → CREATED → RUNNING → [COMPLETED | FAILED | STALLED | ABORTED | HUMAN_INTERVENTION]
                                          ↓           ↓         ↓          ↓
                                       (report)    (retry/abort) (recover/notify)
```

### Per-Agent States

| State | Trigger | Supervisor Action |
|-------|---------|-------------------|
| `CREATED` | Dispatcher calls spawn_agent() | Begin heartbeat monitoring |
| `RUNNING` | Session exists and responds to health checks | Monitor progress; check no-progress threshold |
| `HEARTBEAT_ACTIVE` | Agent sends periodic heartbeat during work | Clear last-activity timer |
| `NO_PROGRESS` | No new artifacts/tokens for configurable period | Warn user; begin countdown to timeout |
| `STALLED` | Progress timeout reached | Attempt recovery (retry or escalate) |
| `FAILED` | Max retries exceeded, agent crashed, or error detected | Notify user; abort task with failure report |
| `ABORTED` | User explicitly aborts via /eo.abort or Supervisor auto-abort | Clear session; write failure report |
| `HUMAN_INTERVENTION` | Stalled + retry exhausted OR Supervisor deems manual review needed | Notify user with summary; wait for human direction |
| `COMPLETED` | Agent reports G2_COMPLETE / G3_APPROVE etc. per protocol | Advance state machine; notify completion |

---

## 2. Global Overlay States

The supervisor maintains an overlay on the core workflow state machine:

```
SUPERVISING → AGENT_STALLED → HUMAN_INTERVENTION → SUPERVISING (retry)
                                        ↓                → TASK_ABORTED (abort)
                                        ↓                → SUPERVISING (continue)
AGENT_FAILED  → HUMAN_INTERVENTION
```

### Overlay State Definitions

| State | Description | Transitions From |
|-------|-------------|------------------|
| `SUPERVISING` | Default auto-mode operational state — all agents monitored | Entered when automatic mode is active; from AGENT_STALLED (retry); from HUMAN_INTERVENTION (continue) |
| `AGENT_STALLED` | Agent detected as stalled (no progress) | SUPERVISING |
| `AGENT_FAILED` | Agent failed / max retries exhausted | AGENT_STALLED, SUPERVISING |
| `HUMAN_INTERVENTION` | Supervisor waiting for human direction | AGENT_STALLED, AGENT_FAILED |
| `TASK_ABORTED` | Task explicitly aborted | Any non-terminal state |

### Transition Rules

- **SUPERVISING → AGENT_STALLED**: Triggered by heartbeat detection (no progress within no_progress_timeout)
- **AGENT_STALLED → HUMAN_INTERVENTION**: When retry_attempts exhausted or zero retries configured
- **HUMAN_INTERVENTION → SUPERVISING**: User says "retry" and retries remaining, or user says "continue"
- **HUMAN_INTERVENTION → TASK_ABORTED**: User says "abort"
- **TASK_ABORTED**: Terminal — no outgoing transitions

---

## 3. Heartbeat / Progress Detection Protocol

### 3.1 Polling Schedule

The supervisor polls each active agent at `heartbeat_interval_seconds` (default: 120s). This must satisfy:

```
heartbeat_interval ≤ no_progress_timeout / 4
```

This ensures we catch no-progress before the timeout fires.

### 3.2 Progress Detection Algorithm

On each heartbeat for an agent session:

1. **Verify session existence** — cross-reference against OpenClaw gateway session store (anti-phantom check)
2. **Scan artifact directory** — compare files against baseline captured at task start
3. **Detect changes** — any new/modified files since last scan = progress
4. **Evaluate timeout** — if zero artifact changes for `no_progress_timeout` seconds → NO_PROGRESS state

### 3.3 Artifact Change Detection

- At task start: capture hash + mtime of all deliverable files
- On each heartbeat: re-scan and compare against baseline
- Zero changes across the full no-progress period = stalled
- Any change resets the progress timer

---

## 4. Timeout and Threshold Configuration

### 4.1 Default Values

```json
{
  "heartbeat_interval_seconds": 120,
  "no_progress_timeout_seconds": 300,
  "hard_timeout_seconds": 900,
  "retry_attempts": 2,
  "retry_backoff_seconds": [60, 180],
  "alert_on_first_stall": true,
  "notification_channels": ["webchat"]
}
```

### 4.2 Threshold Derivation Logic

- `heartbeat_interval` ≤ `no_progress_timeout / 4`: must poll frequently enough to catch no-progress before timeout
- `hard_timeout` ≥ `no_progress_timeout + max(retry_backoff)`: must leave time for retries within the hard limit
- Defaults based on typical implementer work rate: ~50KB/min artifact creation

### 4.3 Per-Task Overrides

A task can override supervisor settings via the task spec:

```yaml
task_spec:
  supervisor:
    heartbeat_interval_seconds: 60      # More aggressive for time-critical work
    no_progress_timeout_seconds: 120    # Tighter threshold
    retry_attempts: 3                    # More retries for complex work
    auto_escalate: false                # Never escalate without user approval
```

---

## 5. Retry and Recovery Protocol

### 5.1 Retry Rules

| Condition | Action |
|-----------|--------|
| First stall detected | Log warning; send notification to user |
| No progress after `no_progress_timeout` | Attempt retry #1 (re-dispatch same agent with same prompt) |
| Retry exhausted or second stall | Escalate: notify user with full session summary and request decision |
| User says "retry" | Attempt next retry if attempts remaining, else proceed to G4 rejection |
| User says "abort" | Clear all sessions; write failure report; advance task to FAILED |
| User says "continue" | Allow current agent to finish (no more retries) |

### 5.2 Recovery Behavior

```
Stalled Agent → notify user with summary
    ├── If retry_attempts > 0: re-dispatch with original prompt + stall context
    │       → New session created; verified alive; heartbeat monitoring restarted
    └── If retry_attempts == 0: escalate to HUMAN_INTERVENTION state
            → Send full report to user (artifacts so far, what's missing, root cause analysis)
            → Wait for user direction: retry / abort / proceed to G4 partial approval
```

### 5.3 Retry Prompt Construction

Each retry includes stall context in the prompt:

1. Previous session key reference
2. Agent role and phase
3. Current retry attempt number
4. Instructions to check existing artifacts before continuing
5. Explicit "do not duplicate work" directive

---

## 6. User Notification Protocol

### 6.1 Event Types and Severity

| Event | Severity | Content | Actionable Commands |
|-------|----------|---------|---------------------|
| First stall detected | WARNING | Session key, phase, time since last progress, current artifact count | — |
| Retry initiated | INFO | Which retry (#), backoff period | /eo.retry (if more retries) |
| Escalation to human | CRITICAL | Full summary: deliverables produced so far, what's missing, root cause analysis | /eo.retry, /eo.abort, /eo.continue |
| Task completion | INFO | Standard G5 closure notification | — |
| Task abort | WARNING | Summary of work completed vs. required | — |

### 6.2 Delivery Mechanism

- **Primary**: webchat message to the user who initiated the task
- **Extensible**: email, Slack, Telegram (via configurable channels)
- Notifications include severity icon and actionable slash commands when applicable

---

## 7. Mode Awareness

### 7.1 Automatic Mode

Supervisor is fully active: monitors all sessions, enforces timeouts, triggers recovery, notifies user.

### 7.2 Manual Mode

Supervisor runs in **observer-only** mode:
- No automated retries or escalations triggered by the supervisor itself
- Still generates warnings for stalled agents (for user awareness)
- Does NOT modify state machine transitions (those are human-controlled in manual mode)
- User-initiated `/eo.retry` still works — it's a manual command, not auto-recovery

### 7.3 Per-Task Mode Override

A task can be explicitly set to manual or automatic via the dispatcher state:

```json
{
  "supervisor_mode": "automatic",
  "supervisor_config_override": { ... }
}
```

---

## 8. State Persistence

Supervisor overlay states are persisted in `dispatcher_state.json` under a new section:

```json
{
  "supervisor_metadata": {
    "overlay_state": "SUPERVISING",
    "mode": "automatic",
    "agents": {
      "agent:implementer:subagent:abc123": {
        "session_key": "agent:implementer:subagent:abc123",
        "agent_id": "implementer",
        "phase": "S2_IMPLEMENTATION",
        "state": "RUNNING",
        "spawned_at": "ISO8601",
        "last_progress_at": "ISO8601",
        "artifact_baseline": { ... },
        "retry_count": 0
      }
    },
    "events": [ ... ],
    "last_heartbeat_at": "ISO8601"
  }
}
```

---

## 9. Integration Points

| Component | Change Required |
|-----------|-----------------|
| `dispatcher/engine.py` | SupervisorStateOverlay methods integrated into WorkflowEngine |
| `dispatcher/state_manager.py` | Persist supervisor metadata to dispatcher_state.json |
| `dispatcher/session_dispatch/engine.py` | Enhanced spawn_agent() with built-in liveness verification; add verify_session_alive() |
| `dispatcher/registry.py` | No changes needed |
| Protocols (completion_protocol.md, delegation_protocol.md) | Add Supervisor event types and notification requirements |
| SKILL.md (for PM) | Add Supervisor awareness to PM dispatcher skill instructions |

---

## 10. Failure Modes and Recovery

### 10.1 Phantom Session (Session Key Not Found in Gateway)

1. Heartbeat detects session key has no evidence of existence
2. Mark agent state as FAILED
3. If retries remaining: attempt recovery with new session
4. If no retries: escalate to user with "phantom session detected" warning

### 10.2 Agent Crash (Session Key Found But No Artifacts)

1. Session exists but artifact count unchanged since spawn
2. Mark agent state as NO_PROGRESS
3. After `no_progress_timeout` without recovery: mark STALLED
4. Proceed with retry or escalation per protocol

### 10.3 Silent Stall (Agent Working but Not Writing Artifacts)

1. Session alive, no errors detected
2. But artifact baseline unchanged for `no_progress_timeout` seconds
3. Mark agent state as NO_PROGRESS → STALLED after threshold
4. Proceed with retry or escalation per protocol

---

## 11. Acceptance Criteria Summary

| AC | Requirement | Verified By |
|----|-------------|-------------|
| AC-1 | Liveness detection catches phantom sessions within one heartbeat cycle | Unit tests + integration |
| AC-2 | Heartbeat polls at configured interval; no-progress triggers after timeout | Unit tests |
| AC-3 | Hard timeout escalates to HUMAN_INTERVENTION; all thresholds configurable | Unit tests + config validation |
| AC-4 | Retries with exponential backoff; exhaustion → HUMAN_INTERVENTION | Integration tests |
| AC-5 | Overlay states persisted in dispatcher_state.json; manual mode = observer only | Integration tests |
| AC-6 | All events generate notifications with severity mapping | Unit tests |
| AC-7 | Tests for stuck, aborted, failed, lost sessions + manual mode | Test suite (AC-7) |
| AC-8 | End-to-end flow works; config validation catches invalid thresholds | Integration tests |
