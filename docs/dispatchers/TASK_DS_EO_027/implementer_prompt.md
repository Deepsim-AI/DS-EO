You are the **Implementer**.


## DISPATCH: G1_APPROVE — TASK_DS_EO_027

### Assignment: DS-EO Workflow Execution Reliability & Watchdog

Execute the CTO Plan below.

---

## CTO Plan (Full Content)

# CTO Plan — TASK_DS_EO_027

**Task ID**: TASK_DS_EO_027  
**Phase**: 6b (DS-EO Workflow Supervisor / Watchdog)  
**Title**: DS-EO Workflow Execution Reliability & Watchdog  
**Date**: 2026-08-05  
**Project**: DS-EO OpenClaw Edition  
**CTO**: qwen3.6:35b (ollama)

---

## 1. Problem Statement

DS-EO's automatic mode relies on the Dispatcher to orchestrate agent handoffs across gates G0–G4, but has **no reliability layer**. Three defects were discovered during TASK_DAL_002:

1. **Phantom sessions**: `spawn_agent()` returned mock success without creating real OpenClaw sessions (fixed in TASK_DS_EO_026)
2. **No liveness detection**: No mechanism to verify spawned agents are actually working or alive
3. **No timeout/progress monitoring**: Stalled, aborted, lost, or failed sessions run indefinitely with no detection

These defects mean the automatic mode can silently fail at any point in the pipeline — the dispatcher assumes success without verification, and there is no watchdog to detect stalls, force recovery, or notify humans.

This task creates a **Workflow Supervisor / Watchdog** component that adds reliability across the entire automatic mode lifecycle.

---

## 2. Scope

The Supervisor must cover all eight areas below. Each area has specific requirements defined in sections 3–10.

### In Scope
- Agent lifecycle management (creation, tracking, liveness states)
- Heartbeat / progress detection per agent per phase
- Configurable timeout thresholds and no-progress detection
- Retry with configurable limits and backoff
- Recovery: re-dispatch, escalate to human, abort task
- Stalled / failed / human-intervention state machine extensions
- User notifications (webchat, email, or configurable channels)
- State-machine changes for new Supervisor-owned states
- Manual mode awareness (Supervisor only affects automatic mode)
- Tests for stuck, aborted, failed, and lost session scenarios

### Out of Scope (for this task)
- Cross-platform compatibility (Claude/Codex/Gemini) — handled in ds-eo-core / v1.0
- Channel integrations beyond OpenClaw webchat — can be extensible but minimal viable implementation is webchat
- User-facing slash commands for Supervisor controls — that's a future PM task

---

## 3. Agent Lifecycle and Liveness States

### 3.1 Agent Lifecycle Model

The Supervisor manages every agent session from creation to completion:

```
NOT_CREATED → CREATED → RUNNING → [COMPLETED | FAILED | STALLED | ABORTED | HUMAN_INTERVENTION]
                                          ↓           ↓         ↓          ↓
                                       (report)    (retry/abort) (recover/notify)
```

### 3.2 Liveness States (per agent per session)

| State | Trigger | Supervisor Action |
|-------|---------|-------------------|
| `CREATED` | Dispatcher calls `spawn_agent()` | Begin heartbeat monitoring |
| `RUNNING` | Session exists and responds to health checks | Monitor progress; check no-progress threshold |
| `HEARTBEAT_ACTIVE` | Agent sends periodic heartbeat during work | Clear last-activity timer |
| `NO_PROGRESS` | No new artifacts/tokens for configurable period | Warn user; begin countdown to timeout |
| `STALLED` | Progress timeout reached | Attempt recovery (retry or escalate) |
| `FAILED` | Max retries exceeded, agent crashed, or error detected | Notify user; abort task with failure report |
| `ABORTED` | User explicitly aborts via `/eo.abort` or Supervisor auto-abort | Clear session; write failure report |
| `HUMAN_INTERVENTION` | Stalled + retry exhausted OR Supervisor deems manual review needed | Notify user with summary; wait for human direction |
| `COMPLETED` | Agent reports G2_COMPLETE / G3_APPROVE etc. per protocol | Advance state machine; notify completion |

### 3.3 Session Existence Verification

Every spawned session must be verified against OpenClaw's session store:

```python
def verify_session_alive(session_key):
    """Check if the reported session exists in OpenClaw's session store."""
    # Query gateway session store → return existence + status
```

This must run **before** and **after** every phase transition to catch phantom sessions.

---

## 4. Heartbeat / Progress Detection

### 4.1 Heartbeat Mechanism

The Supervisor polls each active agent at a configurable interval (default: 2 minutes):

```python
class AgentHeartbeat:
    def __init__(self, session_key, poll_interval_seconds=120):
        self.session_key = session_key
        self.poll_interval = poll_interval_seconds
        self.last_progress = now()
        self.last_artifact_update = None
        self.artifact_baseline = {}  # snapshot at task start
    
    def check_progress(self):
        """Verify agent is making progress toward its deliverables."""
        current_state = verify_session_alive(self.session_key)
        new_artifacts = scan_deliverables_directory()
        new_tokens = check_agent_token_progress()
        
        if current_state.status != "running":
            return HeartbeatResult(dead=True, reason=f"Session {self.session_key} is {current_state.status}")
        
        time_since_last = now() - self.last_progress
        time_since_artifact = (now() - self.last_artifact_update) if self.last_artifact_update else float('inf')
        
        if time_since_artifact > no_progress_timeout:
            return HeartbeatResult(no_progress=True, artifact_age_seconds=time_since_artifact)
        
        # Compare artifacts to baseline — any new ones?
        changes = detect_new_artifacts(self.artifact_baseline, new_artifacts)
        if not changes and no_tokens_since_progress():
            return HeartbeatResult(stalled=True)
        
        return HeartbeatResult(ok=True)
```

### 4.2 Artifact Change Detection

- On task start: capture baseline of all deliverable files (hash + mtime)
- On each heartbeat: re-scan and compare
- A heartbeat with zero artifact changes for the full no-progress period = stalled

---

## 5. Configurable Timeouts and Thresholds

### 5.1 Configuration Schema

```yaml
supervisor:
  heartbeat_interval_seconds: 120    # How often to poll each active agent
  no_progress_timeout_seconds: 300   # Time with zero artifact changes before warning
  hard_timeout_seconds: 900          # Max time in any phase before forced escalation
  retry_attempts: 2                  # Max times to re-dispatch a stalled agent
  retry_backoff_seconds: [60, 180]   # Delay between retries (exponential)
  user_notification_channels:        # Where to send alerts
    - webchat
    - email                          # optional, configurable
  alert_on_first_stall: true         # Notify immediately on first stall
```

### 5.2 Threshold Derivation Logic

- `heartbeat_interval` ≤ `no_progress_timeout / 4` — must poll frequently enough to catch no-progress before timeout
- `hard_timeout` ≥ `no_progress_timeout + max(retry_backoff)` — must leave time for retries within the hard limit
- Defaults chosen based on typical implementer work rate: ~50KB/min artifact creation

---

## 6. Retry Limits and Recovery

### 6.1 Retry Rules

| Condition | Action |
|-----------|--------|
| First stall detected | Log warning; send notification to user |
| No progress after `no_progress_timeout` | Attempt retry #1 (re-dispatch same agent with same prompt) |
| Retry exhausted or second stall | Escalate: notify user with full session summary and request decision |
| User says "retry" | Attempt next retry if attempts remaining, else proceed to G4 rejection |
| User says "abort" | Clear all sessions; write failure report; advance task to FAILED |
| User says "continue" | Allow current agent to finish (no more retries) |

### 6.2 Recovery Behavior

```
Stalled Agent → notify user with summary
    ├── If retry_attempts > 0: re-dispatch with original prompt + stall context
    │       → New session created; verified alive; heartbeat monitoring restarted
    └── If retry_attempts == 0: escalate to HUMAN_INTERVENTION state
            → Send full report to user (artifacts so far, what's missing, root cause analysis)
            → Wait for user direction: retry / abort / proceed to G4 partial approval
```

---

## 7. Stalled / Failed / Human-Intervention States

### 7.1 State Machine Extensions

The existing 6-phase state machine (S0_OPEN through S5_COMPLETE) needs Supervisor-owned overlay states:

**New global overlay states:**

| State | Description | Transitions From |
|-------|-------------|------------------|
| `SUPERVISING` | Default auto-mode operational state | Entered when automatic mode is active |
| `AGENT_STALLED` | Agent detected as stalled (no progress) | SUPERVISING |
| `AGENT_FAILED` | Agent failed / max retries exhausted | AGENT_STALLED, SUPERVISING |
| `HUMAN_INTERVENTION` | Supervisor waiting for human direction | AGENT_STALLED, AGENT_FAILED |
| `TASK_ABORTED` | Task explicitly aborted | Any non-terminal state |

**Transitions within the overlay:**

```
SUPERVISING → AGENT_STALLED (via heartbeat detection)
AGENT_STALLED → HUMAN_INTERVENTION (retry exhausted or no retries configured)
HUMAN_INTERVENTION → SUPERVISING (user: "retry")
HUMAN_INTERVENTION → TASK_ABORTED (user: "abort")
HUMAN_INTERVENTION → SUPERVISING (user: "continue" — let existing agent finish)
```

### 7.2 Agent-Level Failure States

Each spawned agent session also tracks its own failure state:

| State | Condition |
|-------|-----------|
| `RUNNING` | Session exists and responds to health checks |
| `NO_PROGRESS` | No new artifacts for no_progress_timeout period |
| `STALLED` | Hard timeout reached or persistent NO_PROGRESS across retries |
| `FAILED` | Agent reports error, crashes, or explicit failure |
| `COMPLETED` | Agent successfully advances through its gate |

---

## 8. User Notifications

### 8.1 Notification Events

| Event | Severity | Content |
|-------|----------|---------|
| First stall detected | WARNING | Session key, phase, time since last progress, current artifact count |
| Retry initiated | INFO | Which retry (#), backoff period |
| Escalation to human | CRITICAL | Full summary: deliverables produced so far, what's missing, root cause analysis (if available) |
| Task completion | INFO | Standard G5 closure notification |
| Task abort | WARNING | Summary of work completed vs. required |

### 8.2 Delivery Mechanism

- Primary: webchat message to the user who initiated the task
- Extensible: email, Slack, Telegram (via configurable channels)
- Include actionable buttons or slash commands: `/eo.retry`, `/eo.abort`, `/eo.continue`

---

## 9. Interaction with Manual and Automatic Modes

### 9.1 Automatic Mode

Supervisor is fully active: monitors all sessions, enforces timeouts, triggers recovery, notifies user.

### 9.2 Manual Mode

Supervisor runs in **observer-only** mode:
- No automated retries or escalations
- Still generates warnings for stalled agents (for user awareness)
- Does NOT modify state machine transitions (those are human-controlled in manual mode)

### 9.3 Per-Task Overrides

A task can override Supervisor settings via the task spec:

```yaml
task_spec:
  supervisor:
    heartbeat_interval_seconds: 60      # More aggressive for time-critical work
    no_progress_timeout_seconds: 120    # Tighter threshold
    retry_attempts: 3                    # More retries for complex work
    auto_escalate: false                # Never escalate without user approval
```

---

## 10. Required State Machine Changes

### 10.1 Workflow Engine Extensions

Add Supervisor overlay to `dispatcher/engine.py`:

```python
class SupervisorStateOverlay:
    """Overlay states for lifecycle monitoring outside the core workflow state machine."""
    
    # New overlay states (not part of core S0-S5)
    OVERLAY_STATES = ["SUPERVISING", "AGENT_STALLED", "AGENT_FAILED", 
                      "HUMAN_INTERVENTION", "TASK_ABORTED"]
    
    # Methods
    def start_supervising(self, task_id):
        """Begin Supervisor monitoring for a task."""
        
    def check_agent_liveness(self, agent_session_key):
        """Verify agent session exists and is healthy. Returns liveness state."""
        
    def detect_stall(self, task_id):
        """Run heartbeat check against all active agents. Returns (stalled_agents, progress_report)."""
        
    def attempt_recovery(self, task_id, stalled_agent):
        """Attempt to recover a stalled agent. Returns RecoveryResult with action taken."""
```

### 10.2 Integration Points

| Component | Change Required |
|-----------|-----------------|
| `dispatcher/engine.py` | Add SupervisorStateOverlay class; integrate into WorkflowEngine transitions |
| `dispatcher/state_manager.py` | Add overlay state tracking; persist supervisor metadata to dispatcher_state.json |
| `dispatcher/session_dispatch/engine.py` | Enhance spawn_agent() with built-in liveness verification; add verify_session_alive() |
| `dispatcher/registry.py` | No changes needed |
| Protocols (completion_protocol.md, delegation_protocol.md) | Add Supervisor event types and notification requirements |
| SKILL.md (for PM) | Add Supervisor awareness to PM dispatcher skill instructions |

---

## 11. Deliverables

| # | Deliverable | File Path | Description |
|---|-------------|-----------|-------------|
| 1 | Supervisor module | `dispatcher/session_dispatch/supervisor.py` (~300 lines) | Core Supervisor: heartbeat, progress, timeout, retry, escalation, notification |
| 2 | Agent liveness checker | `dispatcher/session_dispatch/liveness.py` (~100 lines) | Session existence + health verification against OpenClaw gateway |
| 3 | State overlay integration | Modified `dispatcher/engine.py` | SupervisorStateOverlay integrated into WorkflowEngine |
| 4 | Protocol updates | `docs/development/protocols/supervisor_protocol.md` (new) | Supervisor event types, notification requirements, manual vs auto mode rules |
| 5 | Config template | `config-templates/supervisor_config.example.json` | Supervisor settings schema with defaults and validation |
| 6 | PM skill update | `dispatcher/SKILL.md` | Add Supervisor awareness to PM dispatcher instructions |
| 7 | Tests | `tests/test_supervisor.py` (~250 lines) | Stuck, aborted, failed, lost session tests + integration scenarios |
| 8 | Task artifacts | `docs/development/reports/TASK_DS_EO_027/*` | Full DS-EO artifact set per protocol |

---

## 12. Acceptance Criteria

### AC-1: Agent Liveness Detection
- [ ] Supervisor can verify that any spawned session key corresponds to a real, running OpenClaw session
- [ ] Phantom sessions (non-existent keys) are detected and reported within one heartbeat cycle
- [ ] Agent lifecycle states correctly map to actual session status

### AC-2: Heartbeat / Progress Detection
- [ ] Supervisor polls active agents at the configured interval
- [ ] No-progress detection triggers after `no_progress_timeout` seconds of zero artifact changes
- [ ] Artifact change detection compares against task-start baseline using hash + mtime

### AC-3: Timeout Enforcement
- [ ] Agents that exceed `hard_timeout_seconds` are automatically escalated to HUMAN_INTERVENTION
- [ ] No-progress timeout triggers a warning notification before escalation
- [ ] All thresholds are configurable per-task via spec override

### AC-4: Retry and Recovery
- [ ] Stalled agents are retried up to configured limit with exponential backoff
- [ ] Each retry creates a verified live session (not phantom)
- [ ] When retries exhausted, task enters HUMAN_INTERVENTION state
- [ ] User receives actionable notification with summary

### AC-5: State Machine Extensions
- [ ] New overlay states (SUPERVISING, AGENT_STALLED, AGENT_FAILED, HUMAN_INTERVENTION, TASK_ABORTED) are persistent in dispatcher_state.json
- [ ] Manual mode does NOT trigger automated recovery — only observer mode
- [ ] Automatic mode triggers full supervisor lifecycle

### AC-6: User Notifications
- [ ] All supervisor events (stall, retry, escalation, completion, abort) generate notifications
- [ ] Escalation notifications include actionable slash commands or clear instructions
- [ ] Notification severity maps to event type (CRITICAL/WARNING/INFO)

### AC-7: Tests
- [ ] Test for stuck session: heartbeat detects no progress → stall → retry → complete
- [ ] Test for aborted session: Supervisor correctly aborts and writes failure report
- [ ] Test for failed session: Agent reports error → Supervisor handles per config
- [ ] Test for lost session (phantom): Verify liveness catches non-existent sessions
- [ ] Test manual mode: Supervisor warns but does NOT auto-recover
- [ ] All tests pass with zero failures

### AC-8: Integration
- [ ] Full end-to-end: open task → dispatcher spawns agent → supervisor monitors → detects stall → recovers → completes G2
- [ ] Config validation: invalid thresholds produce clear error at startup
- [ ] No regression on manual mode tasks (they continue working unchanged)

---

## 13. Gate Status

| Gate | Status | Notes |
|------|--------|-------|
| G0 (Task Creation) | ⬜ Pending | Awaiting CTO creation |
| G1 (User Approval of Plan) | ⬜ Pending | Awaiting user approval |
| G2 (Implementation Complete) | ⬜ Pending | — |
| G3 (Review Passes) | ⬜ Pending | — |
| G4 (Final Approval) | ⬜ Pending | — |

---

**CTO Plan produced by**: CTO (qwen3.6:35b)  
**Date**: 2026-08-05T19:00Z  
**Project**: DS-EO OpenClaw Edition  
**Repository**: ds-eo-openclaw / Deepsim-AI/DS-EO


---

## Delegate Message

# DELEGATE MESSAGE — TASK_DS_EO_027

**From**: CTO (G1 Approved)  
**To**: Implementer  
**Phase**: S1_PLANNING → S2_IMPLEMENTATION  
**Date**: 2026-08-05  
**Priority**: P1  

## Plan Reference
- CTO_PLAN.md: `/home/deepsim/ds_eo_openclaw/docs/development/reports/TASK_DS_EO_027/CTO_PLAN.md`

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

