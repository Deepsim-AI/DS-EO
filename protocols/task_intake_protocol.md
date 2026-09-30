# DS-EO Task Intake Protocol (G0)

**Version**: 1.0  
**Status**: Active  
**Scope**: All OpenClaw workspaces using DS-EO  

---

## Purpose

Defines the G0 intake phase — how new tasks enter the engineering workflow, who owns G0, what artifacts are produced at intake, and which agent session holds exclusive write access to a task directory once it exists. This protocol replaces the ambiguous "PM-only intake" model with a request-path-based ownership model and adds folder-level locking to prevent contention.

---

## 1. Intake Model — Request-Path-Based Ownership

### Rule 1: The Agent That Receives the Initial Customer Request Owns G0

| Entry path | G0 owner | Artifacts produced |
|------------|----------|-------------------|
| User → PM (secretary/intake) | **PM** creates folder + `TASK_REQUEST.md` | Task directory scaffold, `TASK_REQUEST.md`, user notification about adding supporting materials |
| User → CTO directly | **CTO** creates folder + `TASK_REQUEST.md` | Task directory scaffold, `TASK_REQUEST.md`, then proceeds to independent planning (CTO_PLAN.md) |

**`TASK_REQUEST.md` is an intake artifact, not a PM-exclusive artifact.** It records the user's requirements verbatim regardless of which agent captured them.

### Rule 2: CTO Can Legitimately Create Task Folders Without PM

This directly explains why TASK_DS_EO_043 was legitimately created by CTO without PM involvement — if the user directed their request to the CTO, the CTO owns G0. Conversely, **if the user went through PM, then PM's failure to create `TASK_REQUEST.md` is a genuine workflow violation** and must be documented in `BOUNDARY_VIOLATION.md`.

### Rule 3: Intake Is Administrative Only

Whoever handles G0 creates workspace scaffolding (directories, file structure, verbatim request preservation). They do **not** produce technical plans. Stop at workspace creation and hand off to CTO for planning.

The following are **NOT violations** when done during G0 by PM:
- Creating `TASK_REQUEST.md` with the user's stated requirements (verbatim or summarized)
- Organizing the task directory structure
- Notifying the user about adding supporting materials
- Stopping at G0 and handing off to CTO

The following **ARE violations** during G0:
- Any agent writing `CTO_PLAN.md` during G0 intake
- PM performing architectural analysis, selecting components, or designing solutions
- Any agent producing another role's artifacts

---

## 2. TASK_REQUEST.md — Intake Artifact

### Format

```markdown
# TASK_REQUEST — <TASK_ID>

**Submitted by**: <user name or "Anonymous">  
**Submitted at**: <ISO-8601>  
**Priority**: P0 | P1 | P2  
**Intake agent**: PM or CTO  

## Verbatim User Request
<The user's original request, word for word, preserved exactly as submitted.>

## Captured Requirements
<List of requirements gathered during the intake conversation. Each should be a discrete, testable item.>

## Supporting Materials
- <List any specs, docs, examples, datasets, or references the user provided or may add later>

## Notes
<Any additional context gathered during intake — non-technical: timeline constraints, stakeholder concerns, known dependencies.>
```

### Rules for TASK_REQUEST.md

1. **Must contain the verbatim user request** as the first substantive section. No summarization of the original request — only captured requirements and supporting materials may be paraphrased.
2. **Must be produced at intake time**, not retroactively. An agent that completes G0 without this artifact has violated workflow protocol.
3. **May be updated by the user** with additional materials after intake (specs, docs, examples). The updating agent records updates but does not alter the verbatim original request section.
4. **Must exist on disk before any phase beyond G0 begins.** The CTO verifies this before writing `CTO_PLAN.md`; if it's missing, the agent must halt and produce it (or request it from whoever should have).

---

## 3. Task Folder Locking — Session-Level Ownership

### Purpose

Prevent multiple agent sessions from simultaneously working on or modifying the same task directory. This solves the contention problem where one session is writing artifacts while another reads/injects context.

### LOCK.md — The Folder Lock File

Every task directory that has been created (G0 complete) MUST contain a `LOCK.md` file:

```markdown
# Task Folder Lock — <TASK_ID>

**Locked by**: <agent_id> — e.g., "CTO", "PM", "Implementer"  
**Session ID**: <current session ID>  
**Locked at**: <ISO-8601>  
**Status**: active | released  

## Reason
<Why the lock was acquired. Examples: "G0 intake in progress", "Implementation phase G2", "Post-G4 closure in progress">

## Scope
<Which files/directories this agent may write during its session>
```

### Lock Acquisition Rules

1. **Acquire before writing**: The owning agent MUST write `LOCK.md` with `status: active` before producing any artifact in the task directory (except another lock).
2. **One active lock per folder**: Only one `LOCK.md` may have `status: active` per task directory at a time. A second agent detecting an active lock on a different session must STOP and not proceed.
3. **Release after session completes**: When the owning agent's session ends (gracefully or via compaction/interruption), the agent MUST set `LOCK.md status: released` with the session end timestamp before producing any final output. If the session dies mid-write, the lock is considered stale (see staleness below).
4. **Transferring ownership**: When one agent hands off to another (e.g., G0 → G1), the releasing agent sets `status: released`, then the acquiring agent writes a new `LOCK.md` with its own session ID and `status: active` before proceeding.

### Staleness Rules

A lock is considered **stale** if:
- The lock has `status: active` AND the session recorded in the lock is no longer responsive (detected via `openclaw status` or session check) AND the lock was last updated more than 1 hour ago.
- The agent finds no matching active session for the claimed `session_id`.

**On detecting a stale lock**:
1. Record the detection in the task directory as `LOCK_EXPIRY.md`:
   ```markdown
   # Lock Expiry — <TASK_ID>

   **Expired at**: <ISO-8601>  
   **Original holder**: <agent_id> / session_id  
   **Detected by**: <current agent_id>  
   **Action taken**: Lock cleared and re-acquired  

   **Reason**: No active session found for <session_id>; lock age > 1hr.
   ```
2. Write a new `LOCK.md` with the current agent's details and `status: active`.
3. Proceed — stale locks do not block work.

### Lock Enforcement at Each Gate Entry

Every Pre-Phase Entry Gate check (§10 of handoff_protocol) MUST also verify the lock:

| Gate | Check |
|------|-------|
| Any gate entry | `ls <task_dir>/LOCK.md` exists AND either (a) status is `active` and holder matches expected agent, OR (b) no active lock exists (task is idle), OR (c) any existing lock is stale per staleness rules |

If an active lock exists held by a different, responsive session, the receiving agent MUST halt and notify via `PM_STATUS_UPDATE` with status="BLOCKED" and reason="Folder locked by <agent> on session <id>".

---

## 4. G0 Workflow — Complete Sequence

### Flow A: User → PM (Secretary Path)

1. **PM receives user request** — Capture the verbatim request, any initial requirements, priority.
2. **PM creates task folder** — `docs/development/reports/TASK_<NNN>/` (ID assigned by CTO if available, otherwise PM uses a placeholder and notifies CTO to assign a proper ID).
3. **PM writes `TASK_REQUEST.md`** — Captures verbatim request, requirements, priority.
4. **PM acquires folder lock** — Writes `LOCK.md` with status "active", agent "PM".
5. **PM notifies user** — Tells them they may add specifications, documents, examples, datasets, references, or other supporting materials to the task folder.
6. **PM releases lock** — Sets `status: released`.
7. **PM produces READY_FOR_CTO handoff** — Sends the standardized JSON message (see below).
8. **PM stops at G0** — No further work on this task.

### Flow B: User → CTO Directly

1. **CTO receives user request** — Capture the verbatim request, clarify requirements with the user if needed.
2. **CTO creates task folder** — `docs/development/reports/TASK_<YYYYMMDD>_<NNN>/` (assigns ID).
3. **CTO writes `TASK_REQUEST.md`** — Captures verbatim request and confirmed requirements.
4. **CTO acquires folder lock** — Writes `LOCK.md` with status "active", agent "CTO".
5. **CTO performs independent architectural analysis** — This is G1 planning, not a G0 activity. The CTO inspects the repository independently (does not rely on PM-authored context as authoritative).
6. **CTO writes `CTO_PLAN.md`** — Full architecture analysis, acceptance criteria, implementation instructions.
7. **CTO releases lock** — Sets `status: released`.
8. **CTO sends user for G1 approval** — User approves or requests changes.

### Standardized Handoff Message (PM → CTO after G0)

```json
{
  "type": "READY_FOR_CTO",
  "taskId": "TASK_<YYYYMMDD>_<NNN>",
  "taskPath": "<full path to task directory>",
  "intakeAgent": "PM",
  "artifactsAvailable": ["TASK_REQUEST.md", "LOCK.md"],
  "lockStatus": "released",
  "status": "INTAKE_COMPLETE",
  "stopReason": "Intake boundary reached. CTO must independently perform technical analysis.",
  "pmDidNotPerformArchitecturalAnalysis": true
}
```

---

## 5. Transition Table Update (for handoff_protocol.md)

The following updates the existing Transition 0 definition in `handoff_protocol.md`:

### Transition 0: Intake — NEW

**Trigger**: User submits a new task request to PM or CTO.

**Predecessor replaces**: "PM requests CTO to create the task" (old model where CTO always created folders).

**New model**: The agent receiving the user request performs G0 intake directly, creating the folder + `TASK_REQUEST.md` per this protocol. No separate "CTO creates folder" step is needed.

### Transition 0b: PM → Close — Updated

Updated to reference that TASK_REQUEST.md must exist before any G1+ work:
- Before Post-G4 work begins, verify `TASK_REQUEST.md` exists in the task directory (proof that intake was completed). If missing, write `BLOCKED_BY_MISSING_ARTIFACTS.md` referencing this protocol.

### Transition 1: CTO → Implementer — Updated

Now includes an additional prerequisite:
- [ ] `LOCK.md` exists with status "active" held by Implementer OR no active lock exists (CTO released before handoff)

---

## 6. Process Violations

### When to Write BOUNDARY_VIOLATION.md for G0 Issues

Write this file whenever:
- An agent performs G0 intake but fails to create `TASK_REQUEST.md` (e.g., user went through PM and no TASK_REQUEST.md exists)
- A task folder is created without a corresponding lock or with an active lock held by a different responsive session (contention violation)
- The CTO creates `CTO_PLAN.md` during G0 intake instead of `TASK_REQUEST.md` first

### Severity Definitions for G0 Violations

| Severity | When to Use | Required Response |
|----------|-------------|-------------------|
| **Critical** | Post-G4 performed without G0 artifact (TASK_REQUEST.md) existing — task has no recorded user request | Immediate user notification; halt all work until intake is properly documented |
| **High** | G0 completed by one agent but another agent's active lock exists on the folder (contention) | Block phase; notify user in session; clear stale lock per staleness rules |
| **Medium** | TASK_REQUEST.md created retroactively (after user requested it, not at intake time) | Flag in BOUNDARY_VIOLATION.md; note for CTO evaluation of agent behavior |
| **Low** | LOCK.md missing but no contention detected | Fix lock on next access; log as process improvement item |

---

## 7. Related Protocols

- `delegation_protocol.md` — Task creation and assignment (references this protocol for G0)
- `handoff_protocol.md` — Phase transition requirements (updated to reflect new G0 model)
- `communication_protocol.md` — Message formats including READY_FOR_CTO and lock-related messages
- `GATE_AUTHORITY_MATRIX.md` — Gate ownership, including G0 ownership model

---

## 8. Integration with TASK_DS_EO_043 Audit

This protocol directly addresses the root cause identified in TASK_DS_EO_043:
- The CTO legitimately created the task folder and wrote `TASK_REQUEST.md` because the user directed their request to the CTO (not through PM).
- Had the user gone through PM, PM's failure to create `TASK_REQUEST.md` would be a **genuine workflow violation** documented under this protocol.
- The LOCK mechanism would have prevented session contention issues that contributed to BUG2 (test failures) and the Implementer hang incident.

---

*Protocol authored: 2026-08-15*  
*Approved by: CTO 🏗️ (pending formal sign-off via new task)*  
*Next action: Formalize in TASK_DS_EO_044 after CTO review and user approval.*
