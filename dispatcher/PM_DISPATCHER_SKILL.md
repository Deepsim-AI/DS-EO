# PM Dispatcher Skill — Operational Guide for the PM Agent

**Version**: 0.1.0  
**Purpose**: Teach the PM exactly how to use the dispatcher engine to orchestrate tasks through the G0-G4 gate machine programmatically.

---

## What You Have Now

You now have access to:
- **Dispatcher Engine** (`dispatcher/dispatch.py`): Your primary tool for task lifecycle management
- **Agent Registry** (`dispatcher/registry.py`): Loads available agents from `agents_list.json`
- **State Manager** (`dispatcher/state_manager.py`): Persistent per-task state in `docs/dispatchers/<TASK_ID>/`
- **Workflow Definition** (`dispatcher/workflow_defs/default.yaml`): The G0-G4 gate machine definition

---

## How to Use the Dispatcher — Step by Step

### 1. Initialize (once, at session start)

```python
from dispatcher.dispatch import Dispatcher

d = Dispatcher(workspace_root="/home/deepsim/ds-eo-openclaw")
ok, msg = d.initialize()
# ok: True/False — Always check this first
# msg: "Ready — 4 agents [cto, implementer, reviewer, pm]" or error
```

**If init fails**: Stop. Report to user that the dispatcher could not start. Do NOT proceed with task operations.

---

### 2. Open a New Task

When you detect a new implementation need (from user request, backlog review, or ongoing work):

```python
ok, task_id = d.open_task(
    task_id="TASK_20260805_001",          # Format: TASK_YYYYMMDD_NNN
    spec_ref="specs/FEATURE_X.md",         # Reference to the requirement/spec
    priority="P1",                          # P0, P1, or P2
    notes="User requested this for Q3 release"  # User-provided context
)
# task_id is returned on success; use it for all subsequent operations
```

**What open_task does:**
- Creates `docs/dispatchers/TASK_YYYYMMDD_NNN/` directory
- Writes `dispatcher_state.json` with S0_OPEN phase
- Records G0_ENTRY transition in both state and dispatch log
- Snapshots agent registry checksum for integrity tracking
- Initializes `dispatch_log.jsonl` for audit trail

---

### 3. Track Task Progress

At any time, query the current status:

```python
status = d.get_task_status(task_id)
# Returns TaskStatus dataclass with:
#   - current_phase (e.g., "S2_IMPLEMENTATION")
#   - phase_label (e.g., "Implementation")
#   - workflow_version
#   - transition_count
#   - last_transition / last_transition_at
#   - completed_at (if S5_COMPLETE)
#   - stalled / stall_reason
#   - pending_work_type / assigned_to
```

Use this to report status to the user and verify readiness for the next gate.

---

### 4. Advance Through Gates — The Core Workflow

#### Gate G1: Plan Approved (S1_PLANNING → S2_IMPLEMENTATION)

When the user approves the CTO's plan:

```python
ok, msg = d.advance_g1(task_id, user_approved=True)
# Returns: "Task TASK_... → S2_IMPLEMENTATION. Implementer delegated."
# Or if approved=False: stays in S1_PLANNING with revision request
```

**Before calling:** Verify CTO_PLAN.md exists in the task directory. If it doesn't, the CTO hasn't finished planning — report this to the user.

#### Gate G2: Implementation Complete (S2_IMPLEMENTATION → S3_REVIEW)

When the Implementer declares work complete and IMPLEMENTATION_REPORT.md is ready:

```python
ok, msg = d.advance_g2(task_id, implementation_report_exists=True)
# Returns: "Task TASK_... → S3_REVIEW. Reviewer delegated."
```

**Before calling:** Verify both CTO_PLAN.md AND IMPLEMENTATION_REPORT.md exist in the task directory. Both are required.

#### Gate G3: Review Decision (S3_REVIEW → S4_APPROVAL or back to S2_IMPLEMENTATION)

When the Reviewer submits their REVIEW_REPORT.md:

```python
# If reviewer recommends APPROVE:
ok, msg = d.advance_g3(task_id, reviewer_approved=True)
# Returns: "Task TASK_... → S4_APPROVAL. CTO to issue final G4 decision."

# If reviewer requests changes:
ok, msg = d.advance_g3(task_id, reviewer_approved=False)
# Returns: "Task TASK_... → S2_IMPLEMENTATION (revision loop). Reviewer requested changes."
```

**Before calling:** Verify REVIEW_REPORT.md exists and contains required fields (scoring rubric, recommendation). If missing any field, handoff is NOT_READY.

#### Gate G4: Final Decision (S4_APPROVAL → S5_COMPLETE or back to S2_IMPLEMENTATION)

When the user gives final approval on CTO's G4 decision:

```python
# If user approves:
ok, msg = d.advance_g4(task_id, user_approved=True)
# Returns: "Task TASK_... → S5_COMPLETE. Post-G4 cleanup complete."
# Also writes PM_CLOSED.md and updates project status

# If user rejects:
ok, msg = d.advance_g4(task_id, user_approved=False)
# Returns: "Task TASK_... → S2_IMPLEMENTATION (deep rejection). CTO rejected final implementation."
```

**Before calling:** Verify ALL four artifacts exist: CTO_PLAN.md, IMPLEMENTATION_REPORT.md, REVIEW_REPORT.md, CTO_APPROVAL.md. Any missing artifact blocks G4 completion.

---

### 5. Check for Stalls

Periodically (during your heartbeat or on status queries):

```python
stalls = d.check_all_stalls()
if stalls:
    for s in stalls:
        print(f"⚠ {s['task_id']}: {s['reason']} ({s['phase_duration_minutes']}m elapsed)")
```

When a task stalls:
1. Write `TASK_STALLED` event to the task's dispatch log
2. Notify the user of which task is stalled and why
3. Report to CTO for resolution (PM does NOT resolve technical stalls)

---

### 6. Post-G4 Completion Checklist

When a task reaches S5_COMPLETE:

1. **Verify artifacts**: All four required artifacts exist in task directory
2. **Update PROJECT_STATUS.md**: Mark the feature/task as completed
3. **Update CHANGELOG.md**: Add entry for user-facing changes
4. **Write PM_CLOSED.md**: Persistent record of completion (required by protocol)
5. **Commit to Git**: Push approved work (with user confirmation of repo/branch)

---

## What You MUST NOT Do

| Prohibited Action | Reason | Who does it instead |
|------------------|--------|---------------------|
| Make architectural decisions | CTO's sole authority | CTO |
| Execute code changes | Implementer's role | Implementer |
| Issue quality approvals | Reviewer recommends; CTO decides | Reviewer + CTO |
| Modify source files outside designated paths | Tool policy enforcement | See tool.deny list |
| Make git commits/pushes without user confirmation | User must verify target repo/branch | PM only after explicit user confirmation |
| Spawn sessions on other agents | Not yet automated (P5 pending) | Manual via sessions_spawn in P5 |

---

## Error Patterns and Responses

### Pattern: "Task not found or has no state"
**Response**: The task may not exist yet, or its directory was removed. Use `d.open_task()` to create it first.

### Pattern: "Task must be in S1_PLANNING" (wrong phase for advance_gN)
**Response**: Check current status with `get_task_status()`. Verify you're calling the right gate at the right time. Review the protocol for correct sequence.

### Pattern: "Missing required artifact: X.md"
**Response**: Report which artifact is missing to the producing agent. Do NOT proceed — the gate cannot pass without it.

### Pattern: "Registry checksum mismatch"
**Response**: STOP all transitions. The agents_list.json has changed since this task was created. Report to user that the task may need recreation with updated registry.

### Pattern: "Dispatcher not initialized"
**Response**: Call `d.initialize()` first. This must happen before any other dispatcher operation.

---

## Quick Reference — Phase Map

| Phase | Agent | What Happens | How You Advance |
|-------|-------|-------------|-----------------|
| S0_OPEN | PM | Task created, CTO notified | `open_task()` |
| S1_PLANNING | CTO | CTO writes CTO_PLAN.md | User approves → `advance_g1(approved=True)` |
| S2_IMPLEMENTATION | Implementer | Code written per plan | `advance_g2()` when IMPLEMENTATION_REPORT.md ready |
| S3_REVIEW | Reviewer | Independent quality verification | `advance_g3(True)` or `advance_g3(False)` |
| S4_APPROVAL | CTO | Final G4 decision | User approves → `advance_g4(approved=True)` |
| S5_COMPLETE | PM | Post-G4 cleanup | Automatic (completed_at set) |

---

## Revision Loops — What to Watch For

When work goes back for rework, the phase changes:

| From Phase | Back To Phase | Triggered By | Your Action |
|-----------|--------------|-------------|-------------|
| S1_PLANNING | S1_PLANNING (self-loop) | User revision request | Report to CTO; wait for updated CTO_PLAN.md |
| S2_IMPLEMENTATION | S2_IMPLEMENTATION (self-loop) | G4 rejection or G3 revision | Report to Implementer; wait for new IMPLEMENTATION_REPORT.md |
| S3_REVIEW | S2_IMPLEMENTATION | Reviewer requests changes | Report to Implementer with reviewer's rationale verbatim |

**Important**: When work returns via a revision loop, increment the task's NNN counter if you need a fresh tracking ID, or keep the same ID and track revision count in the transition_history.

---

## Using Transition Logs

To audit what happened on a task:

```python
entries = d.get_task_transition_log(task_id)
for e in entries:
    print(f"  [{e['ts'][:19]}] {e['event_type']} | {e['phase_from']} -> {e['phase_to']}")
```

Every transition is logged immutably. This is your source of truth for "what happened and when."
