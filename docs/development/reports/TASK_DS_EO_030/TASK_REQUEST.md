# TASK_DS_EO_030 — OpenClaw Agent Session Health and Lifecycle Management

**Project:** DS-EO (OpenClaw Engineering Organization)
**Task ID:** TASK_DS_EO_030
**Priority:** High
**Status:** Proposed
**Depends on:** TASK_DS_EO_028 — Failure Detection and Recovery; existing OpenClaw session management and DS-EO workflow state

---

## 1. Objective

Implement an **OpenClaw Agent Session Health and Lifecycle Management** capability within DS-EO.

The purpose is to continuously monitor agent sessions and identify sessions that are:

* stale;
* excessively large;
* stuck;
* repeatedly failing;
* unable to compact;
* orphaned;
* otherwise unhealthy.

The system should provide safe, policy-driven actions to keep OpenClaw agent sessions operational and prevent session-related problems from degrading DS-EO workflows.

The primary goal is:

> **Prevent unhealthy OpenClaw sessions from becoming a recurring source of run errors, failed compaction, excessive context growth, and stalled engineering workflows.**

This task should integrate with existing DS-EO recovery and workflow-state mechanisms rather than creating a competing recovery architecture.

---

# 2. Problem

During real DS-EO development, OpenClaw can accumulate large or stale sessions across agents.

Observed problems include:

* very large session histories;
* stale sessions remaining active for long periods;
* run errors;
* inability to compact;
* sessions becoming difficult or impossible to continue;
* excessive context growth;
* agents appearing stuck;
* abandoned sessions remaining in the environment.

These problems can eventually interfere with otherwise healthy engineering workflows.

The current system requires manual observation and cleanup.

DS-EO should instead be able to monitor session health and perform safe lifecycle management.

---

# 3. Scope

This task covers:

```text
Session discovery
       ↓
Health inspection
       ↓
Classification
       ↓
Policy evaluation
       ↓
Safe action
       ↓
Verification
       ↓
Audit / reporting
```

The first implementation should focus on **reliable operational management**, not sophisticated AI-based diagnosis.

---

# 4. Design Principle

The system must follow this principle:

> **Observe first, classify second, act conservatively, verify afterward.**

Session cleanup must never be based solely on age or context size.

Before taking destructive or disruptive action, DS-EO must determine whether the session is associated with active work.

---

# 5. Session Health Model

Define a session health model capable of distinguishing at least:

```text
HEALTHY
ACTIVE
STALE
OVERSIZED
STUCK
COMPACTION_REQUIRED
COMPACTION_FAILED
ERRORING
ORPHANED
RECOVERY_REQUIRED
UNKNOWN
```

The exact internal representation may use existing OpenClaw/DS-EO terminology where appropriate.

The important requirement is that DS-EO can distinguish a normal active session from a session requiring intervention.

---

# 6. Session Discovery

Implement a mechanism to discover relevant OpenClaw agent sessions.

The system should be able to determine, where the underlying OpenClaw interface permits:

* session ID;
* agent identity;
* task ID, if associated;
* session creation time;
* last activity time;
* current execution state;
* context/session size;
* compaction status;
* recent errors;
* current workflow state;
* whether the session is actively executing;
* whether the session is associated with unfinished work.

The implementation should use supported OpenClaw interfaces or existing DS-EO integration points.

Do not depend on fragile parsing of human-readable CLI output if a structured interface is available.

---

# 7. Session-to-Task Association

Where possible, DS-EO should associate an OpenClaw session with:

```text
Agent
   ↓
Task
   ↓
Workflow
```

For example:

```text
Session
  ↓
Implementer
  ↓
TASK_DS_EO_028
  ↓
G3 Implementation
```

This association is essential for safe cleanup.

A session associated with an active task must be treated differently from an abandoned session.

---

# 8. Health Indicators

The health evaluator should consider multiple signals.

At minimum:

### 8.1 Age

How long the session has existed.

### 8.2 Inactivity

How long since the session last made meaningful progress.

### 8.3 Context size

Whether the session has grown beyond configured thresholds.

### 8.4 Compaction state

Whether:

* compaction is unnecessary;
* compaction is required;
* compaction succeeded;
* compaction failed;
* compaction repeatedly failed.

### 8.5 Execution state

Whether the agent is:

```text
RUNNING
IDLE
WAITING
STUCK
FAILED
UNKNOWN
```

### 8.6 Error history

Repeated run errors or other execution failures should contribute to session health classification.

### 8.7 Task state

Whether the associated task is:

```text
ACTIVE
WAITING
COMPLETED
FAILED
ABORTED
UNKNOWN
```

### 8.8 Recovery history

Consider whether previous recovery attempts have already failed.

---

# 9. Health Classification

The system should produce a deterministic health assessment.

For example:

```text
Session S123

Agent: Implementer
Task: TASK_DS_EO_028
Last activity: 3 minutes ago
Context: normal
Errors: 0
Task state: RUNNING

→ HEALTHY
→ No action
```

Another example:

```text
Session S456

Agent: Reviewer
Task: TASK_DS_EO_017
Last activity: 4 hours ago
Context: large
Compaction: failed twice
Task state: no longer active

→ COMPACTION_FAILED / STALE
→ Recovery candidate
```

The classification should be explainable.

---

# 10. Configurable Thresholds

Thresholds must be configurable rather than hard-coded.

Examples:

```yaml
session_health:
  stale_after: ...
  oversized_context: ...
  max_compaction_attempts: ...
  error_threshold: ...
  monitoring_interval: ...
```

The exact schema should follow existing DS-EO configuration conventions.

Do not invent arbitrary values without documenting their rationale.

---

# 11. Safe Lifecycle Actions

The system should support a controlled set of actions.

At minimum:

```text
NO_ACTION
WARN
MONITOR
COMPACT
RETRY_COMPACTION
MARK_STALE
ARCHIVE
CLOSE
ESCALATE
```

The exact available actions depend on the capabilities exposed by OpenClaw.

DS-EO must not implement an action merely because it is conceptually desirable if OpenClaw does not provide a safe mechanism for it.

---

# 12. Action Policy

Actions should be deterministic and conservative.

Example:

```text
HEALTHY
    ↓
NO_ACTION

OVERSIZED
    ↓
COMPACTION_REQUIRED
    ↓
COMPACT

COMPACTION_FAILED
    ↓
RETRY_COMPACTION
    ↓
if still failing
    ↓
ESCALATE / ARCHIVE according to policy

STALE + NO ACTIVE TASK
    ↓
MARK_STALE
    ↓
ARCHIVE / CLOSE

STALE + ACTIVE TASK
    ↓
DO NOT DESTROY
    ↓
ESCALATE / MONITOR
```

The policy must not blindly terminate sessions.

---

# 13. Protection of Active Work

This is a critical safety requirement.

A session must not be automatically closed, archived, or destroyed merely because it is old or large.

Before destructive or disruptive action, DS-EO should check:

```text
Is an agent actively executing?
Is there an active task?
Is there unfinished work?
Is there unpersisted state?
Are there uncommitted source changes?
Is the workflow waiting for this session?
Has the task been completed or abandoned?
```

If these conditions cannot be reliably determined, the safe default is:

```text
NO DESTRUCTIVE ACTION
        ↓
ESCALATE / WARN
```

---

# 14. Integration with TASK_DS_EO_028

TASK_DS_EO_030 should reuse the failure/recovery concepts introduced by TASK_DS_EO_028.

For example:

```text
Session Health Manager
        ↓
detect unhealthy session
        ↓
Recovery Engine
        ↓
determine action
        ↓
COMPACT / RETRY / ESCALATE / ARCHIVE
```

Do not implement a second independent recovery policy engine.

Where appropriate, use the recovery state representation and persistence mechanisms established by TASK_DS_EO_028.

---

# 15. Monitoring Loop

Implement a monitoring mechanism capable of periodically evaluating session health.

Conceptually:

```text
Monitor
   ↓
Discover sessions
   ↓
Collect health data
   ↓
Evaluate state
   ↓
Apply policy
   ↓
Perform safe action
   ↓
Verify result
   ↓
Persist event
   ↓
Next monitoring cycle
```

The monitoring mechanism should not interfere with active agent execution.

The interval should be configurable.

---

# 16. Action Verification

After taking an action, DS-EO should verify the result.

For example:

```text
COMPACT requested
       ↓
wait / poll
       ↓
inspect session
       ↓
compaction successful?
       ├── yes → HEALTHY / continue
       └── no  → COMPACTION_FAILED
```

Similarly, if a session is archived or closed, DS-EO should verify that the intended lifecycle transition actually occurred.

Never assume an action succeeded merely because the command/request returned.

---

# 17. Recovery From Failed Compaction

Because failed compaction is a known operational problem, it must receive explicit handling.

A possible policy:

```text
Context oversized
      ↓
Attempt compaction
      ↓
Success?
 ┌────┴────┐
YES        NO
 │          │
continue   retry
            ↓
       retry limit
            ↓
      preserve state
            ↓
       escalate /
       safe archive
```

Before any session is archived or closed following failed compaction, DS-EO must ensure that relevant task/workflow state has been persisted.

---

# 18. Stale Session Handling

A stale session is not automatically a disposable session.

Distinguish:

### Stale but active task

```text
STALE
+
ACTIVE TASK
```

Action:

```text
WARN / MONITOR / ESCALATE
```

Do not automatically destroy.

### Stale and abandoned task

```text
STALE
+
TASK COMPLETED / ABORTED
```

Action may be:

```text
ARCHIVE
CLOSE
```

subject to configured policy.

---

# 19. Orphan Detection

Identify sessions that cannot be associated with a currently active task or workflow.

Potential orphan:

```text
OpenClaw session
     ↓
No active task
     ↓
No active workflow
     ↓
No recent meaningful activity
```

Such sessions may be candidates for cleanup.

However, orphan detection should be conservative and configurable.

---

# 20. Agent-Level Health Summary

Provide a useful summary by agent.

For example:

```text
OpenClaw Session Health
────────────────────────────
CTO
  Healthy: 1
  Stale: 0
  Oversized: 0
  Errors: 0

Implementer
  Healthy: 1
  Stale: 1
  Oversized: 0
  Errors: 0

Reviewer
  Healthy: 0
  Stale: 2
  Compaction Failed: 1
```

This should initially be available through the existing DS-EO CLI/logging mechanisms.

A web dashboard is **not required** for this task.

---

# 21. Audit Trail

Every automatic lifecycle action must be recorded.

Example:

```text
SESSION HEALTH EVENT

Session: <session-id>
Agent: Implementer
Task: TASK_DS_EO_028

Detected:
  status: OVERSIZED
  context: above configured threshold

Action:
  COMPACT

Result:
  SUCCESS

Timestamp:
  ...
```

For failures:

```text
Action:
  COMPACT

Result:
  FAILED

Attempts:
  2

Next action:
  ESCALATE
```

The audit trail should allow an operator to understand what DS-EO did and why.

---

# 22. Manual Override

The system must provide a mechanism for the operator to prevent automatic lifecycle actions when necessary.

At minimum, the architecture should support a policy such as:

```text
PROTECTED
```

for a session.

A protected session must not be automatically archived, closed, or otherwise destroyed.

If a full CLI command is not appropriate for this task, implement the underlying state/policy mechanism and document the intended operator interface.

---

# 23. Dry-Run / Observe-Only Mode

Before enabling automatic cleanup, support an **observe-only / dry-run mode** where possible.

Example:

```text
Session S123 is classified as:

OVERSIZED
COMPACTION_REQUIRED

Would perform:
COMPACT

Action not executed because:
observe_only=true
```

This allows the operator to validate health policies against real OpenClaw sessions before enabling automatic actions.

---

# 24. Testing Requirements

Add automated tests covering at least:

1. healthy session is detected correctly;
2. active session is not incorrectly classified as stale;
3. stale inactive session is detected;
4. oversized session is detected;
5. compaction-required state is detected;
6. compaction success is handled;
7. compaction failure is handled;
8. retry limit is enforced;
9. repeated errors are detected;
10. orphan session is identified according to policy;
11. active task protects its associated session from destructive cleanup;
12. persisted task state is checked before destructive recovery;
13. lifecycle action result is verified;
14. audit events are recorded;
15. observe-only mode performs no destructive action;
16. manual/protected sessions are not automatically destroyed;
17. TASK_DS_EO_028 recovery mechanisms are reused where appropriate;
18. existing DS-EO tests continue to pass.

---

# 25. Acceptance Criteria

TASK_DS_EO_030 is complete when:

* [ ] DS-EO can discover relevant OpenClaw sessions.
* [ ] DS-EO can associate sessions with agents and tasks where possible.
* [ ] Session health can be classified deterministically.
* [ ] Stale sessions can be identified.
* [ ] Oversized sessions can be identified.
* [ ] Compaction failures can be identified.
* [ ] Repeated execution errors can be identified.
* [ ] Orphan sessions can be identified according to configurable policy.
* [ ] Health thresholds are configurable.
* [ ] Lifecycle actions are policy-driven.
* [ ] Active task sessions are protected from unsafe cleanup.
* [ ] Failed compaction follows a controlled recovery policy.
* [ ] Recovery integrates with TASK_DS_EO_028 rather than duplicating its policy engine.
* [ ] Lifecycle actions are verified after execution.
* [ ] Every automatic lifecycle action is recorded in an audit trail.
* [ ] Observe-only/dry-run behavior is available.
* [ ] Manual/protected sessions are respected.
* [ ] Automated tests cover the major health and lifecycle states.
* [ ] Existing DS-EO functionality continues to work.
* [ ] Relevant DS-EO documentation is updated.

---

# 26. Non-Goals

This task does **not** include:

* replacing OpenClaw's native session management;
* modifying OpenClaw core unless absolutely necessary;
* building a new session storage system;
* building a web dashboard;
* implementing sophisticated AI-based session diagnosis;
* automatically deleting arbitrary session data;
* automatically killing active agents without state protection;
* redesigning TASK_DS_EO_028;
* redesigning DS-EO workflow execution;
* implementing distributed orchestration.

The first implementation should be a **small, reliable operational layer around OpenClaw's existing session capabilities**.

---

# 27. Implementation Order

The Implementer should preferably proceed in phases.

### Phase 1 — Discovery and Observation

Implement:

```text
session discovery
health metrics
session/task association
observe-only reporting
```

Do not perform destructive cleanup yet.

### Phase 2 — Health Classification

Implement:

```text
healthy
stale
oversized
stuck
compaction-required
compaction-failed
erroring
orphaned
```

with configurable thresholds.

### Phase 3 — Policy Integration

Integrate with the existing recovery engine/state mechanism from TASK_DS_EO_028.

Implement deterministic action selection.

### Phase 4 — Safe Lifecycle Actions

Implement supported actions such as:

```text
WARN
COMPACT
RETRY
ARCHIVE
CLOSE
ESCALATE
```

with appropriate safeguards.

### Phase 5 — Persistence and Audit

Persist:

```text
health state
recovery state
action history
```

and produce an auditable lifecycle history.

### Phase 6 — Real-World Validation

Run the capability during actual DS-EO development.

Use observed OpenClaw session behavior to refine thresholds and recovery policies.

Do not over-engineer rules before real usage provides evidence.

---

# 28. Final Design Principle

The goal is **not** to make DS-EO aggressively clean up OpenClaw.

The goal is:

> **Keep OpenClaw's agent environment healthy while protecting active engineering work.**

The desired operational behavior is:

```text
                    OpenClaw
                       │
                Session Monitor
                       │
                       ▼
                Health Assessment
                       │
          ┌────────────┼────────────┐
          ↓            ↓            ↓
       HEALTHY       STALE       OVERSIZED
          │            │            │
      NO ACTION     inspect      compact
                                    │
                              ┌─────┴─────┐
                              ↓           ↓
                           success      failure
                              │           │
                           continue    recovery
                                          │
                              ┌───────────┼───────────┐
                              ↓           ↓           ↓
                           retry      preserve     escalate
                                      state
```

**DS-EO should manage sessions as operational resources, not treat them as disposable conversations.**

A healthy session continues uninterrupted. A stale session is investigated. An oversized session is compacted when safe. A failed compaction enters recovery. An active task is protected. An abandoned session can eventually be archived or closed. Every automatic action is explainable and auditable.
