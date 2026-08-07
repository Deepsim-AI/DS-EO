# DS-EO Workflow Comparison — Manual vs Automatic Mode

**Version**: 0.1.0  
**Created**: 2026-08-06  
**Scope**: All OpenClaw workspaces using DS-EO  

---

## Overview

DS-EO supports two execution modes for the engineering workflow: **Manual** and **Automatic**. Both use the same underlying 11-state machine, protocol requirements, gate enforcement, and artifact structure. The difference is entirely in **who drives each phase transition**: the user (manual) or the StateEngine's auto-advance logic (automatic).

> **Key principle**: In both modes, gates G1 (plan approval) and G4 (final approval) require explicit user input. No gate decision is ever made automatically.

---

## The 11-State Machine (Shared by Both Modes)

All transitions, artifacts, agents, and authority rules are identical regardless of mode. Only the *trigger mechanism* differs.

| State ID | Name | Gate Responsible Agent |
|----------|------|------------------------|
| S0 | TASK_OPEN | PM |
| S1 | G1_WAITING | CTO (plan) → User (approval) |
| S2 | IMPLEMENTATION | Implementer |
| S3 | WAITING_G2 | Implementer → Reviewer |
| S4 | REVIEW | Reviewer |
| S5 | G3_PENDING | CTO (final decision) |
| S6 | FINAL_APPROVAL | CTO (G4 approve/reject) |
| S7 | COMPLETED | PM (Post-G4 cleanup) |
| S8 | CHANGES_REQD | Implementer (revision loop) |
| S9 | BLOCKED | Any agent → User |
| S10 | STALLED | PM escalation |

### Transition Matrix

| From | To | Gate | Trigger Mechanism |
|------|-----|------|-------------------|
| TASK_OPEN | G1_WAITING | — | Plan submitted for review |
| G1_WAITING | IMPLEMENTATION | G1 APPROVED | User approves plan |
| G1_WAITING | CHANGES_REQD | G1 REJECTED | User requests revision |
| IMPLEMENTATION | WAITING_G2 | — | Implementer self-declares complete |
| WAITING_G2 | REVIEW | G2 PASSED | G2 checklist passes |
| WAITING_G2 | IMPLEMENTATION | G2 FAILED | G2 checklist fails → rework |
| REVIEW | G3_PENDING | — | Review report exists |
| G3_PENDING | FINAL_APPROVAL | G3 APPROVED | Reviewer recommends APPROVE |
| G3_PENDING | CHANGES_REQD | G3 REJECTED | Reviewer recommends REQUEST_CHANGES or REJECT |
| FINAL_APPROVAL | COMPLETED | G4 APPROVED | CTO approves; user confirms |
| FINAL_APPROVAL | IMPLEMENTATION | G4 REJECTED | CTO rejects → rework |
| CHANGES_REQD | IMPLEMENTATION | — | Rework resubmitted |

---

## Complete Workflow: Manual Mode

The user drives every phase transition. Nothing advances without an explicit human signal.

### Full Flow (10 Steps)

```
Step  ── Agent ─── ───────────── Action Required by User ─────────────
───────────────────────────────────────────────────────────────────────────
1     PM       Send `/eo task` → PM creates S0_OPEN + dispatcher_state.json
              PM initializes the dispatcher and opens a new task skeleton

2     CTO      PM spawns CTO (or user triggers). CTO writes CTO_PLAN.md
              with problem statement, proposed changes, acceptance criteria,
              and implementation instructions.

3     User     ⚠️ G1 GATE — User MUST approve CTO_PLAN.md
              Review the plan and say "APPROVE" or request revision.
              PM advances via advance_g1(approved=True/False)
───────────────────────────────────────────────────────────────────────────
4     Implem.  After G1 approval, PM spawns Implementer via sessions_spawn()
              Implementer writes code per the CTO's plan + produces
              IMPLEMENTATION_REPORT.md with test results.

5     User/PM  ⚠️ Manual signal required to advance G2
              User says "implementation is done" or PM detects artifact.
              PM verifies artifacts exist (CTO_PLAN.md + IMPLEMENTATION_REPORT.md)
              then calls advance_g2().

6     Reviewer PM spawns Reviewer via sessions_spawn(agent="reviewer")
              Reviewer writes REVIEW_REPORT.md with: spec compliance matrix,
              regression analysis, code quality assessment, architecture check,
              scoring rubric (4 dimensions), and recommendation.
───────────────────────────────────────────────────────────────────────────
7     User/CTO ⚠️ User reviews reviewer findings; CTO evaluates G3
              PM reports findings to user. If recommended APPROVE,
              PM advances via advance_g3(True). Otherwise → CHANGES_REQD loop.

8     CTO      PM spawns CTO for final G4 evaluation. CTO writes
              CTO_APPROVAL.md with approve/reject decision + rationale
              referencing the Reviewer's report and spec compliance.
───────────────────────────────────────────────────────────────────────────
9     User     ⚠️ G4 GATE — User MUST give final sign-off
              Review CTO_APPROVAL.md and approve or reject the implementation.

10    PM       On user approval, PM runs Post-G4 cleanup:
               1. Verify all four artifacts in task directory
               2. Update PROJECT_STATUS.md
               3. Update CHANGELOG.md
               4. Write PM_CLOSED.md
               5. Commit to Git (with user confirmation)
               6. Push to remote (user confirms repo + branch)
───────────────────────────────────────────────────────────────────────────
```

### User Actions Required in Manual Mode

| Decision Point | User Action | Gate |
|---------------|-------------|------|
| Start a new task | `/eo task` → provide spec/priority | G0 (entry) |
| Approve CTO plan | Say "APPROVE" on CTO_PLAN.md | **G1** |
| Signal implementation complete | Say "implementation done" or PM detects artifact | — |
| Accept/reject review findings | Review REVIEW_REPORT.md; PM advances accordingly | G3 context |
| Final approve/reject | Say "APPROVE" on CTO_APPROVAL.md | **G4** |
| Git push confirmation | Confirm target repo URL + branch | Post-G4 |

### Manual Mode Characteristics

| Aspect | Behavior |
|--------|----------|
| Phase transitions | User commands every step explicitly |
| PM role | Reactive — waits for user to say "advance" |
| Auto-advance (StateEngine) | Disabled: `auto_advance()` returns `None` in manual mode |
| Stall detection | Available but passive; user must notice and act |
| Supervisor behavior | Observer-only (warns but does not auto-retry or escalate) |
| Artifact verification | Identical to automatic mode (AGENTS.md §10 enforcement) |
| Audit trail | Identical: 14-field entries for every transition |
| Revision loops | User manually routes work back; PM does not auto-route |

---

## Complete Workflow: Automatic Mode

The StateEngine and PM's Workflow State Engine auto-advance eligible transitions based on artifact detection. User still owns gates G1 and G4 only.

### Full Flow (12 Steps)

```
Step  ── Agent ─── ──────────── Behavior (Auto-Advance in Bold) ────────────
──────────────────────────────────────────────────────────────────────────────────────
1     PM       Send `/eo task` → PM creates S0_OPEN + dispatcher_state.json

2     CTO      PM spawns CTO. CTO writes CTO_PLAN.md

3     PM auto  **detect_state()** sees CTO_PLAN.md exists on disk
               → **auto_advance()**: S0 → G1_WAITING
               Notification: "Plan submitted for review"
               ⚠️ User must STILL approve at G1 — not auto-decided
──────────────────────────────────────────────────────────────────────────────────────
4     User     User approves CTO_PLAN.md (required in both modes)

5     PM auto  On user_approved=True → **advance_g1()**: S1 → S2_IMPLEMENTATION
               PM spawns Implementer via sessions_spawn(agent="implementer")
──────────────────────────────────────────────────────────────────────────────────────
6     Implem.  Implementer writes code + IMPLEMENTATION_REPORT.md

7     PM auto  **detect_state()** sees IMPLEMENTATION_REPORT.md exists on disk
               → **_check_g2_pass()**: runs G2 checklist verification
               → **auto_advance()**: S3 → S4_REVIEW (if passed) or S2 (if failed)
               Notification: "G2 passed automatically — Reviewer assigned"
               PM spawns Reviewer via sessions_spawn(agent="reviewer")
──────────────────────────────────────────────────────────────────────────────────────
8     Reviewer Reviewer writes REVIEW_REPORT.md with scoring + recommendation

9     PM auto  **detect_state()** sees REVIEW_REPORT.md exists on disk
               → **auto_advance()**: S4 → G3_PENDING (always, per §10.2)
               Notification: "Review complete. Awaiting CTO G3 evaluation."
               PM spawns CTO for G4 decision via sessions_spawn(agent="cto")
──────────────────────────────────────────────────────────────────────────────────────
10    CTO      CTO evaluates review, writes CTO_APPROVAL.md (approve or reject)
              Notification: "Completion Summary sent — see COMPLETION_SUMMARY below"

11    User     ⚠️ G4 GATE — User MUST approve final implementation (required in both modes)
──────────────────────────────────────────────────────────────────────────────────────
12    PM auto  On user_approved=True → **advance_g4()**: S6 → S5_COMPLETE
               Post-G4 cleanup runs automatically: status update, changelog,
               PM_CLOSED.md, commit (with user confirmation for remote push)
──────────────────────────────────────────────────────────────────────────────────────
```

### User Actions Required in Automatic Mode

| Decision Point | User Action | Gate |
|---------------|-------------|------|
| Start a new task | `/eo task` → provide spec/priority | G0 (entry) |
| Approve CTO plan | Say "APPROVE" on CTO_PLAN.md | **G1** |
| Final approve/reject | Say "APPROVE" on CTO_APPROVAL.md | **G4** |
| Git push confirmation | Confirm target repo URL + branch | Post-G4 |

### Auto-Mode User Notifications

Per `notifications.py`, each auto-transition produces a user-facing message:

| Transition | Notification Message |
|-----------|---------------------|
| S0 → G1_WAITING | "Plan submitted for review" |
| S3 → S4 (REVIEW, G2 passed) | "G2 passed automatically — Reviewer assigned" |
| S4 → G3_PENDING | "Review complete. Awaiting CTO G3 evaluation." |
| S7 (COMPLETED) | "Task completed, cleanup in progress" |
| CHANGES_REQD | "Changes requested: [reason] — rework required" |
| BLOCKER | "BLOCKER: [details]" (urgent priority) |
| STALLED | "STALLED: last activity [timestamp], exceeded timeout" (warning priority) |

### Automatic Mode Characteristics

| Aspect | Behavior |
|--------|----------|
| Phase transitions | StateEngine auto-advances on artifact detection + explicit gate approvals |
| PM role | Proactive — detects artifacts, pushes workflow forward via `auto_advance()` |
| Auto-advance (StateEngine) | Enabled: `auto_advance()` runs each cycle, pushes through eligible states |
| Stall detection | Active; PM monitors last_artifact_update vs timeout_config; auto-detects STALLED |
| Supervisor behavior | **Active**: heartbeat polling, auto-retry with exponential backoff, escalation to user if retries exhausted |
| Artifact verification | Identical to manual mode (AGENTS.md §10 enforcement) |
| Audit trail | Identical: 14-field entries for every transition |
| Revision loops | PM auto-routes on G2 failure; CTO G4 rejection also auto-routes back to S2 |

---

## Side-by-Side Comparison

### What's the Same in Both Modes

| Element | Manual Mode | Automatic Mode | Notes |
|---------|-------------|----------------|-------|
| 11-state machine | ✅ Identical | ✅ Identical | Same states, same transitions |
| Artifact requirements | ✅ Identical | ✅ Identically enforced | AGENTS.md §10 hard gates |
| Gate G1 (plan approval) | User decides | User decides | No difference |
| Gate G4 (final approval) | User decides | User decides | No difference |
| Four formal gates | ✅ G1–G4 | ✅ G1–G4 | Same authority matrix |
| Artifact files | Same names/formats | Same names/formats | CTO_PLAN.md, IMPLEMENTATION_REPORT.md, REVIEW_REPORT.md, CTO_APPROVAL.md |
| Audit trail | 14-field entries | 14-field entries | Identical schema |
| Role boundaries | ✅ Enforced | ✅ Enforced | Rule 9 (no cross-agent substitution) |
| Pre-phase entry gates | ✅ AGENTS.md §10.1–10.3 | ✅ AGENTS.md §10.1–10.3 | Same artifact checks |
| Revision loop mechanics | Manual routing | Auto-routing | Only trigger mechanism differs |
| Two-layer model | ✅ Preserved | ✅ Preserved | Development vs runtime separation |

### What's Different

| Element | Manual Mode | Automatic Mode | Impact |
|---------|-------------|----------------|--------|
| **Phase transition trigger** | User commands every step | StateEngine auto-advances on artifact detection | Auto mode is hands-off between gates |
| **PM role** | Reactive — waits for user input | Proactive — detects artifacts and pushes forward | PM behavior differs significantly |
| **Auto-advance (StateEngine)** | `auto_advance()` always returns `None` | Runs each cycle; advances eligible states automatically | Core behavioral difference |
| **Reviewer completion visibility** | User checks disk or asks PM | Auto-notification: "Review complete. Awaiting CTO" | Auto mode has user-facing signals during workflow |
| **Implementer completion detection** | User says "done" or PM manual check | detect_state() sees IMPLEMENTATION_REPORT.md, runs G2 checklist | Same end state; different detection mechanism |
| **Stall handling** | User must notice and act manually | Auto-detect via timeout config; Supervisor auto-retries | Auto mode catches stalls faster |
| **Supervisor monitoring** | Observer-only (warns but does nothing) | Active: heartbeat, auto-retry with backoff, escalation to user | Major operational difference |
| **User notifications during workflow** | None until G4/Cleanup | Auto-mode sends state entry messages at each transition | Auto mode keeps user informed mid-workflow |
| **Revision loop routing** | User manually routes work back via commands | PM auto-routes on G2 failure / CTO rejection; updates phase automatically | Less friction for iteration cycles |
| **User actions required** | 6 decision points (start, G1, signal impl done, review accept/reject, G4, push) | 3 decision points (start, G1, G4, plus push confirmation) | Fewer user interactions in auto mode |

### User Action Count Summary

| Metric | Manual Mode | Automatic Mode |
|--------|-------------|----------------|
| Explicit user decisions required | 4–6 | 3 (G1 + G4 + push) |
| Intermediate status visibility | None until PM reports | Auto notifications at each transition |
| Stall detection | User-observed | PM auto-detects within timeout window |
| Artifact checking | PM or user verifies manually | StateEngine `detect_state()` checks on every cycle |

---

## Decision Matrix: When to Use Each Mode

| Scenario | Recommended Mode | Rationale |
|----------|-----------------|-----------|
| First-time DS-EO usage; learning the workflow | **Manual** | User needs full control and visibility of each decision point |
| Experienced user with clear spec; trusted plan | **Automatic** | Fewer interactions needed; auto mode accelerates delivery |
| High-stakes architectural changes | **Manual** | Every transition requires deliberate user confirmation |
| Routine bug fixes / small features | **Automatic** | Artifact detection handles most of the workflow automatically |
| Complex multi-phase projects | **Mixed** — manual for planning, automatic for implementation/review | Use mode-specific task overrides: `selector.switch_task_mode("TASK_XXX", "automatic")` |
| Training / teaching the protocol | **Manual** | Shows every gate and artifact explicitly |
| Production pipeline (CI/CD style) | **Automatic** | Full automation; user only approves at gates |

### Mode Switching

Both modes can be switched at any state boundary:

```python
from ds_eo_openclaw.workflow.selector import ModeSelector

selector = ModeSelector(config)

# Global switch
old_mode, new_mode, notification = selector.switch_mode("automatic")
# → ("manual", "automatic", "Auto mode enabled — PM will auto-advance eligible transitions")

# Per-task override (task-specific mode without affecting others)
selector.switch_task_mode("TASK_20260806_001", "manual")
```

**Safe-switching guarantees** (§4.5 of architecture):
1. No silent transitions through gates — mode change never bypasses gate requirements
2. PM detects conditions, does not decide them — mode change only changes behavior, not decisions
3. Human signals are explicit — no mode switch based on silence or timeout
4. Rejection routes correctly — rejection paths identical in both modes
5. No auto-resolve of state machine errors — if state is invalid, reject the switch

---

## Artifact Structure (Identical in Both Modes)

Every task directory contains:

```
docs/development/reports/TASK_<YYYYMMDD>_<NNN>/
├── CTO_PLAN.md               ← Planning artifact (CTO produces)
├── IMPLEMENTATION_REPORT.md  ← Implementation artifact (Implementer produces)
├── REVIEW_REPORT.md          ← Review artifact (Reviewer produces)
├── CTO_APPROVAL.md           ← Final decision artifact (CTO produces)
├── TASK_COMPLETION_AUDIT.md  ← Gate execution log (created at task open)
├── PM_CLOSED.md              ← Post-G4 closure record (PM produces)
├── BLOCKED_BY_MISSING_ARTIFACTS.md   ← Only if gate block detected
└── BOUNDARY_VIOLATION.md           ← Only if role boundary violated
```

Each artifact includes metadata per AGENTS.md §11e:
```yaml
---
produced_by: <agent_model_identity>
session_id: <openclaw_session_id>
produced_at: <ISO timestamp>
role: CTO | Implementer | Reviewer | PM
task_id: TASK_<YYYYMMDD>_<NNN>
gate: G1 | G2 | G3 | G4 | G5
---
```

---

## Rejection / Revision Flow (Identical in Both Modes)

The revision loop mechanics are the same regardless of mode. Only the trigger mechanism differs.

| Gate | Rejection | From Phase | To Phase | Trigger |
|------|-----------|------------|----------|---------|
| G1 | Plan revision requested | S1_PLANNING | S1_PLANNING (self-loop) | User requests changes |
| G2 | Checklist fails | S3_WAITING_G2 | S2_IMPLEMENTATION | _check_g2_pass() returns False |
| G3 | Request changes / Reject | S5_G3_PENDING | S8_CHANGES_REQD → S2_IMPLEMENTATION | Reviewer recommends REQUEST_CHANGES or REJECT |
| G4 | CTO rejects final implementation | S6_FINAL_APPROVAL | S8_CHANGES_REQD → S2_IMPLEMENTATION | CTO writes REJECT in CTO_APPROVAL.md |

In **manual mode**: the user (or PM on user instruction) calls `advance_gN(False)` to route work back.
In **automatic mode**: `_check_g2_pass()` or `_check_approval_outcome()` auto-detects the rejection and advances to CHANGES_REQD.

---

## Source References

| Document | Relevant Section |
|----------|-----------------|
| `ds_eo_openclaw/README.md` | Overview, role definitions, canonical flow description |
| `ds_eo_openclaw/AGENTS.md` §10–§11 | Pre-phase entry gates, artifact enforcement, session boundary rules |
| `ds_eo_openclaw/dispatcher/PM_DISPATCHER_SKILL.md` | Manual mode step-by-step (Steps 1–10) |
| `ds_eo_openclaw/dispatcher/SKILL.md` | Phase map; Supervisor vs Manual Mode table |
| `ds_eo_openclaw/agents/pm.md` | PM Workflow State Engine auto-advance transitions |
| `ds_eo_openclaw/ds_eo_openclaw/workflow/state_engine.py` | 11-state enum, transition matrix, `auto_advance()` logic |
| `ds_eo_openclaw/ds_eo_openclaw/workflow/notifications.py` | Auto-mode notification message map (§6.3) |
| `ds_eo_openclaw/ds_eo_openclaw/workflow/selector.py` | Mode switch mechanics, safe-switching guarantees (§4.5) |
| `ds_eo_openclaw/dispatcher/ARCHITECTURE.md` | Architecture diagram; state machine; workflow definitions |
| `ds_eo_openclaw/dispatcher/workflow_defs/default.yaml` | YAML gate machine: phases, transitions, stall detection config |
| `ds_eo_openclaw/protocols/approval_protocol.md` | Gate authority matrix and decision rules |
| `ds_eo_openclaw/protocols/handoff_protocol.md` | Phase transition requirements, artifact checklists |

---

*This document provides a comprehensive side-by-side reference for DS-EO's two execution modes. It is intended as both user-facing documentation and agent operational reference.*

---

## Session Lifecycle — Where Messages Go (Automatic Mode)

This section clarifies the session routing that both modes use but was not documented before.

### The Isolated Session Model

Every cross-phase handoff uses `sessions_spawn(agent="...", context="isolated")`. This creates a new, isolated agent session with its own message history. **No phase shares a session with another.**

### Complete Session Map for Automatic Mode

```
User's Chat Session (webchat/Signal/etc.)
    │
    ├── /eo task ──► PM Agent (session 1)
    │                   │
    │                   ├── spawns CTO isolated (session 2) — user never sees session 2
    │                   │       CTO writes CTO_PLAN.md
    │                   │
    │                   ▼ notifies user: "Plan submitted for review"
    │
User's Chat Session ←─────── (user reads plan, says APPROVE)
    │
    ├── PM spawns Implementer isolated (session 3) — user never sees session 3
    │       Implementer writes code + IMPLEMENTATION_REPORT.md
    │
    │ StateEngine detects artifact → auto-advances → notifies user
    │ "G2 passed automatically — Reviewer assigned"
    │
    ├── PM spawns Reviewer isolated (session 4) — user never sees session 4
    │       Reviewer writes REVIEW_REPORT.md
    │
    │ StateEngine detects artifact → auto-advances → notifies user
    │ "Review complete. Awaiting CTO G3 evaluation."
    │
    ├── PM spawns CTO isolated (session 5) — user never sees session 5
    │       CTO writes CTO_APPROVAL.md
    │
    ▼ notifies user: "Final approval required" + CTO's recommendation
User's Chat Session ←─────── (user reads decision, says APPROVE at G4)
    │
    └── PM runs Post-G4 cleanup (session 6 — PM session)
            Updates status, changelog, writes PM_CLOSED.md
            Notifies user: "Task completed, cleanup in progress"
```

### What the User Actually Sees in Automatic Mode

| When | What Appears in User's Chat Session |
|------|-----------------------------------|
| Starts task | "Task TASK_XXX created. CTO is writing the plan." (from PM) |
| Plan ready | "Plan submitted for review — see CTO_PLAN.md" + request for APPROVE |
| Review starts | "G2 passed automatically — Reviewer assigned" (auto-notification) |
| Review done | "Review complete. Awaiting CTO G3 evaluation." (auto-notification) |
| Decision ready | "Final approval required — CTO recommends [APPROVE/REJECT]" + request for G4 action |
| Cleanup done | "Task completed, cleanup in progress" + git push confirmation request |

### What the User Does NOT See

| Session Type | Why Hidden | Reason |
|-------------|-----------|--------|
| CTO planning session | Context-isolated spawn | Per protocol: no cross-session context contamination |
| Implementer session | Context-isolated spawn | Same isolation principle — user doesn't need to see implementation details |
| Reviewer session | Context-isolated spawn | Independent verification requires separation from user/Implementer influence |
| CTO G4 decision session | Context-isolated spawn | Independent evaluation of review findings |

### Manual Mode Session Routing

In manual mode, the same isolated session model applies — but **the PM does not auto-advance**. Instead:

1. User sends `/eo task` → routes to PM (same gateway binding)
2. PM spawns CTO isolated → CTO writes plan
3. **User must explicitly say "APPROVE"** before PM proceeds
4. PM spawns Implementer isolated → Implementer works
5. **User must explicitly say "implementation done" or PM manually checks** → triggers G2 advance
6. PM spawns Reviewer isolated → Reviewer verifies
7. **User must advise PM to "advance to review" or check review findings** → triggers G3 advance
8. PM spawns CTO for G4 → CTO decides
9. **User must explicitly approve at G4** → triggers completion

The only difference from automatic mode: **steps 3, 5, and 7 require explicit user commands to the PM**, rather than the StateEngine auto-detecting artifacts and advancing on its own.

---

*This section clarifies the session routing that was previously undocumented across the codebase.*
