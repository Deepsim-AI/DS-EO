# DS-EO Handoff Protocol (Global Standard)

**Version**: 1.0  
**Status**: Active  
**Scope**: All OpenClaw workspaces using DS-EO  

---

## Purpose

Defines the explicit transition requirements between workflow phases, including artifact checklists for receiving agents and error handling for incomplete handoffs. Extends the core development workflow with actionable verification steps.

---

## Phase Transitions

### Transition 0: PM → Open TASK (New Task Skeleton Creation)

**Trigger**: New implementation request identified.

**Prerequisites**:
- [ ] Requirement or spec reference identified
- [ ] Priority determined by user/PM

**Actions**:
1. **PM requests CTO to create the task** — PM alerts the CTO with requirement, priority, and context. The CTO creates the directory and assigns the ID (see `delegation_protocol.md` §Step 1).
2. After CTO creates the task, PM triggers the skeleton by sending a `TASK_OPEN` message.

**Handoff Message**: PM sends a `TASK_OPEN` message:
```json
{
  "type": "TASK_OPEN",
  "taskId": "TASK_<YYYYMMDD>_<NNN>",
  "specRef": "<path to relevant spec or requirement>",
  "priority": "P0 | P1 | P2",
  "notes": "<user-provided context, priority rationale>"
}
```

**Receiving Agent Verification** (CTO checks before starting):
1. Confirm task directory exists at expected path.
2. Read `CTO_PLAN.md` placeholder — verify it contains section headers for CTO to fill.
3. Identify the relevant spec or requirement referenced.
4. Begin architectural planning work.

---

### Transition 0a: PM → Monitor (Stall Detection During Any Phase)

**Trigger**: Task has not progressed within expected timeframe, or any agent reports a blocker.

**Actions**:
1. Check task directory for recent artifact updates.
2. If no progress detected → send `TASK_STALLED` message to relevant parties.
3. Document stall reason and escalate per project policy.

**Handoff Message**: PM sends a `TASK_STALLED` message:
```json
{
  "type": "TASK_STALLED",
  "taskId": "TASK_<YYYYMMDD>_<NNN>",
  "currentPhase": "<phase name where stall occurred>",
  "lastActivity": "<timestamp of last artifact update>",
  "reason": "<description of stall condition>"
}
```

**Note**: PM does not resolve technical stalls — it escalates to the CTO for resolution.

---

### Transition 0b: PM → Close (Post-G4 Cleanup)

**Trigger**: Gate G4 approval issued by CTO.

**Actions**:
1. Verify all task artifacts are present in the task directory.
2. Update `PROJECT_STATUS.md` to reflect completed work.
3. Add entries to `CHANGELOG.md` for user-facing changes.
4. Flag milestone completion if applicable.
5. Commit approved work to the local Git repository (see commit message format below).
6. Send `PM_CLOSED` message to relevant parties.
7. Push approved work to GitHub (if user has confirmed target repository and branch).

**Git Commit Format**: After actions 1–4, PM runs:
```bash
git add <changed-files>
git commit -m "TASK_<YYYYMMDD>_<NNN>: [Post-G4] Complete approved work — <brief description>"
```

The commit message must reference the TASK_ID and include a brief description of the task scope. Committed files include status/changelog updates and any new protocol or artifact files from this task. **Constraint**: Only committed after G4 approval; never during active implementation or review phases.

**Handoff Message**: PM sends a `TASK_CLOSED` message:
```json
{
  "type": "PM_CLOSED",
  "taskId": "TASK_<YYYYMMDD>_<NNN>",
  "closedBy": "PM",
  "artifactsVerified": ["CTO_PLAN.md", "IMPLEMENTATION_REPORT.md", "REVIEW_REPORT.md", "CTO_APPROVAL.md"],
  "statusUpdatesWritten": true,
  "changelogUpdated": true
}
```

**Post-G4 Atomic Completion (NEW)** — Effective immediately: The entire Post-G4 sequence (actions 1–7) must be completed **within the same session** that receives G4 approval. If the PM session ends before push completes:

- A `TASK_STALLED` message must be sent with phase="POST_G4_PUSH_INCOMPLETE" and lastActivity set to the time of session end
- On next available cycle, a PM session MUST resume the Post-G4 sequence from where it left off — not restart from scratch
- This is a **process violation** if the gap persists for more than one session boundary

The CTO's final step (writing `CTO_APPROVAL.md`) does NOT include Post-G4 duties per AGENTS.md §6 Rule 6. Post-G4 is exclusively PM, and the PM must complete it atomically without deferring to a future session.

**Note**: PM does not decide gates — it only observes and records transitions. Gate decisions remain with the CTO.
---

### Transition 1: CTO → Implementer (Gate G1)

**Trigger**: User approves the CTO's task plan.

**Prerequisites** (must all exist before handoff):
- [ ] `docs/development/reports/TASK_<id>/` directory created
- [ ] `CTO_PLAN.md` written with problem statement, proposed changes, acceptance criteria, and implementation instructions
- [ ] User approval confirmed (Gate G1 cleared)

**Handoff Message**: CTO sends a `DELEGATE` message to the Implementer containing:
- Task ID and full directory path
- Spec reference
- Acceptance criteria
- Constraints and boundaries

**Receiving Agent Verification** (Implementer checks before starting):
1. Confirm task directory exists at expected path
2. Read `CTO_PLAN.md` — verify acceptance criteria are present and testable
3. Identify the relevant spec file referenced in the plan
4. Flag any ambiguity to CTO before beginning work

---

### Transition 2: Implementer → Reviewer (Gate G2)

**Trigger**: Implementer reports implementation complete with test results.

**Prerequisites** (must all exist before handoff):
- All items on the **G2 Gate Checklist** (see `approval_protocol.md`) verified complete
- **[NEW] IMPLEMENTATION_REPORT.md must exist at the time of self-declaration.** The report is not a retrospective artifact — it must be produced *simultaneously* with the implementer's completion claim. Retroactively filling in an implementation report after review has begun constitutes a process violation and requires user notification.

**Handoff Message**: Implementer sends an `IMPL_COMPLETE` message containing:
- Task ID
- Full path to `IMPLEMENTATION_REPORT.md`
- Test result summary (passed/failed)
- Changes summary

**Receiving Agent Verification** (Reviewer checks before starting):
1. Confirm task directory exists at expected path
2. Read `IMPLEMENTATION_REPORT.md` — verify it references the spec and acceptance criteria
3. Run `git diff` to see actual changes vs. what was reported
4. **Verify report timestamps**: if IMPLEMENTATION_REPORT.md was created or significantly modified *after* Reviewer's first access to the task directory, flag this as a process violation and notify the user before proceeding. The report must predate any review activity.
5. If report is missing, incomplete, or retroactively produced → return to Implementer with specific gap + process violation notice

---

### Transition 3: Reviewer → CTO (Gate G3)

**Trigger**: Reviewer submits review findings.

**Prerequisites** (must all exist before handoff):
- [ ] `git diff` reviewed against original spec
- [ ] Regression analysis completed
- [ ] Scoring rubric filled out (`review_protocol.md`)
- [ ] Recommendation issued: APPROVE / APPROVE_WITH_COMMENTS / REQUEST_CHANGES / REJECT
- [ ] All Phase 2 and Phase 3 artifacts carry required metadata fields (`agent_id`, `produced_at`)

**Handoff Method**: Reviewer writes `REVIEW_REPORT.md` directly to the task directory. CTO no longer copies the report — it is already in place.

**Receiving Agent Verification** (CTO checks before deciding):
1. Confirm review report exists (chat or file)
2. Verify Implementer's handoff path was provided and verified by Reviewer
3. Check that recommendation is clear and justified — if not, return to Reviewer

---

**Note — G3 iteration**: G3 may be entered multiple times for re-review. Each return from the Reviewer with REQUEST_CHANGES or REJECT sends the task back to Implementer for correction. The task **never re-enters G2** on a return — it loops G3 → Implementer → G3 until the Reviewer issues PASS, then proceeds to G4.

### Transition 4: CTO → Complete/Return (Gate G4)

**Trigger**: CTO issues final approval decision.

**Prerequisites** (must all exist before handoff):
- [ ] `CTO_APPROVAL.md` written with decision and rationale
- [ ] Spec status updated (active → completed or moved accordingly)
- [ ] Decision references Reviewer's report

**Handoff Message**: CTO communicates the decision to the user. If approved, work is done. If rejected, specify what needs fixing and return to Implementer or Reviewer as appropriate.

---

## Error Handling: Incomplete Handoffs

When a handoff fails verification (missing artifacts, incomplete reports, unclear acceptance criteria):

1. **Identify the gap** — Document exactly what's missing or incomplete
2. **Return with specifics** — Send feedback to the originating agent naming the specific issue(s)
3. **Do not proceed** — The next phase cannot start until the handoff is complete
4. **Log the return** — Note in the task directory if a return occurred (for process improvement)

### Common Return Reasons

| Returning Agent | To | Reason |
|----------------|-----|--------|
| CTO | Implementer | Ambiguous acceptance criteria; missing spec reference |
| Reviewer | Implementer | Implementation report incomplete; test results missing; **report retroactively produced** |
| CTO | Reviewer | No review report received; or report lacks recommendation |

---

## Handoff Artifact Checklist (Quick Reference)

| From → To | Required Artifacts | Verification Action |
|-----------|-------------------|---------------------|
| PM → Open TASK | `CTO_PLAN.md` placeholder, spec ref | Read placeholder, confirm structure |
| PM → Monitor | Stall detection report | Verify last activity timestamp |
| PM → Close | Artifact verification, status update + **push confirmation** | Confirm all artifacts present AND remote push verified |
| CTO → Implementer | `CTO_PLAN.md`, user approval | Read plan, confirm criteria present |
| Implementer → Reviewer | **`IMPLEMENTATION_REPORT.md` (pre-dating review)** | Run git diff, check test results, **verify report timestamps** |
| Reviewer → CTO | Review report (chat/file) | Confirm recommendation exists |
| CTO → User/Complete | `CTO_APPROVAL.md`, updated spec | Decision clear and referenced |

---

## Session-Continuity Guarantee (NEW §7.0)

**Problem**: Agent sessions may end mid-sequence, leaving processes partially completed. The last known state is not a valid completion — the work must be finished.

**Rule 1: Continuity is mandatory.** Every agent that begins a multi-step sequence must complete it in a single session. If interruption occurs, the incomplete state must be persisted in the task directory as `SESSION_INTERRUPT.md` before any new work starts on another task.

**Rule 2: Interrupted sessions are tracked artifacts.** `SESSION_INTERRUPT.md` format:
```json
{
  "interruptedBy": "<reason or auto-detected timeout>",
  "completedSteps": ["<step already completed>"],
  "pendingSteps": ["<step that was not completed>"],
  "sessionEndTimestamp": "<ISO-8601>",
  "nextAgent": "<which agent must resume>",
  "blockingOnUserConfirmation": false
}
```

**Rule 3: No task may begin until the previous session's interruption is resolved.** An agent receiving a new task request MUST check whether any unresolved `SESSION_INTERRUPT.md` exists in the workspace. If it does, that interrupted sequence takes priority — new work only starts after it completes.

**Rule 4: User notification on cross-session gaps.** If an interrupted sequence spans more than one session boundary and requires user intervention (e.g., a missing push confirmation), the PM MUST send a `PM_STATUS_UPDATE` with status="AWAITING_USER" describing what is blocked. This is a process violation if omitted.

**Rule 5: Session continuity applies to all agents, not just PM.** The CTO's G4 decision is complete only when it writes `CTO_APPROVAL.md`. The Implementer's work is complete only when tests are written and pass. The Reviewer's review is complete only when `REVIEW_REPORT.md` exists. None of these may be deferred to another session without documenting the interruption.

---

## Rules

1. No phase may begin until the receiving agent has verified all prerequisites.
2. Incomplete handoffs are returned — never silently accepted.
3. The receiving agent is responsible for verification, not the sending agent.
4. All return reasons must be specific and actionable.
5. **IMPLEMENTATION_REPORT.md must exist at the time of Implementer's self-declaration of completion.** Retroactively filling in an implementation report after review has begun is a process violation and requires user notification before proceeding.
6. **Post-G4 duties are atomic** — The entire Post-G4 sequence (status update, changelog, commit, PM_CLOSED message, push) must complete within one session. If the session ends mid-sequence, a TASK_STALLED message with phase="POST_G4_PUSH_INCOMPLETE" is required. The next available PM session MUST resume and complete the sequence — not defer it again. This is a process violation if the gap persists beyond one session boundary.

---

## Related Protocols

- `communication_protocol.md` — Message format standards
- `delegation_protocol.md` — Task creation and assignment
- `completion_protocol.md` — Per-role completion checklists
