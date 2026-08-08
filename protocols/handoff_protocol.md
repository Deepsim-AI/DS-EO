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


---

## Implementer Report Enforcement — Strengthened (Updated §9.0)

**Recurring violation**: Across TASK_DS_EO_020 and TASK_DS_EO_022, the Implementer completed code changes and tests but did NOT produce IMPLEMENTATION_REPORT.md at completion time. In both cases, user intervention was required to request the report. This is no longer tolerated.

### Rule 1: Report as part of the completion action — not a separate step
When the Implementer finishes code changes and tests, **IMPLEMENTATION_REPORT.md must be written before any other action**. It is not optional. The implementer may not claim "implementation complete" until the report exists on disk.

### Rule 2: Automated pre-review gate
Before any Reviewer begins work on a task, the IMPLEMENTATION_REPORT.md MUST exist AND its timestamp must be earlier than the REVIEW_REPORT.md timestamp (or review start time). If the file does not exist when the Reviewer first accesses the task directory, the Reviewer MUST:
1. Send `PM_STATUS_UPDATE` with status="BLOCKED" and message "IMPLEMENTATION_REPORT.md missing — Implementer has not completed reporting step"
2. Return the task to the Implementer without reviewing code
3. Log in BOUNDARY_VIOLATION.md that the implementation report was deferred past completion time

### Rule 3: Process violation classification
- **Severity**: High — delays review by definition, wastes Reviewer effort if they start before the report exists
- **Tracking**: Count of Implementer-report-deferrals across tasks becomes a measurable process metric
- **Escalation**: If two or more Implementers in the same session defer reports, escalate to CTO for protocol enforcement

### Rule 4: No retroactive production accepted as valid
A report produced after user request — even if it predates review — is flagged with a note in BOUNDARY_VIOLATION.md documenting "IMPLEMENTATION_REPORT.md produced via user request, not at completion time." This flags the Implementer's behavior for CTO evaluation.

## Related Protocols

- `communication_protocol.md` — Message format standards
- `delegation_protocol.md` — Task creation and assignment
- `completion_protocol.md` — Per-role completion checklists

---

## Anti-Hallucination Requirement (NEW §8.0)

**Problem**: Agents may reference artifacts, tasks, or state from previous sessions that no longer exist in the current workspace.

**Rule**: Before claiming any task artifact exists (CTO_PLAN.md, IMPLEMENTATION_REPORT.md, CTO_APPROVAL.md, etc.) or before stating a task is pending/approved/completed, the agent **MUST verify file existence on disk AND confirm git state** (git log shows the artifact was committed).

**Violation response**:
- If any claimed artifact cannot be verified via filesystem check → do not proceed; report to user that the claim cannot be substantiated
- If PM proposes work based on stale/phantom state → this is a process violation requiring immediate correction
- PM must never reference a TASK directory or plan it did not just create or can confirm exists on disk

**Verification checklist for any agent claiming task state**:
1. `ls <task_directory>` — does the directory exist?
2. `ls <task_directory>/<artifact_name>` — does the claimed file exist?
3. `git log --oneline` — was the artifact committed to a known remote SHA?

All three checks must pass before any claim about task state is made.

---

## Implementer Report Enforcement (NEW §9.0)

**Problem**: The implementation report must be produced simultaneously with work completion — not retroactively after user intervention or review start. This is a recurring failure mode across tasks.

**Rule 1: Immeate report on completion.** When the Implementer finishes code changes and tests, the IMPLEMENTATION_REPORT.md must be written **before any other action**. It is not a separate phase — it is part of the completion step itself. The Implementer may not claim "implementation complete" until the report exists.

**Rule 2: Reviewer timestamp gate.** The Reviewer MUST verify that IMPLEMENTATION_REPORT.md predates the reviewer's first access to the task directory by at least the time needed for the implementer to produce the report (minimum: the time between the delegate message and the report). If the report was created more than X minutes after the delegate message, or if there is no evidence of simultaneous production, flag it.

**Rule 3: No review without report.** The Reviewer must refuse to begin review if IMPLEMENTATION_REPORT.md does not exist at the time of their first access to the task directory. If accessed later and then found, the gap must be documented in BOUNDARY_VIOLATION.md and the user notified.

**Rule 4: Implementer may not defer reporting.** The Implementer has no authority to defer report production to a later session. This is a process violation equivalent to "report retroactively produced" but more severe because it delays review by definition.


---

## Pre-Phase Entry Gate Enforcement (NEW §10.0)

**Problem**: Agents routinely proceed to the next phase even when prerequisite artifacts from prior phases are missing. Rules in text ("must") provide no mechanical barrier. TASK_DS_EO_024 demonstrated two violations: Reviewer skipped G3 and jumped to Post-G4 without REVIEW_REPORT.md; no CTO_APPROVAL.md existed before PM_CLOSED.md was written.

**Principle**: Each phase gate is a *mechanical checkpoint*, not an advisory step. The receiving agent has **zero authority** to start until ALL prerequisite artifacts exist on disk and are verified. If any artifact is missing, the agent MUST halt, log the block, and notify the user — never infer, proceed, or perform another agent's duties.

### §10.1 Pre-G3 Enforcement (Reviewer Entry Gate)

Before the Reviewer begins ANY review activity for a task, the following files must exist in the task directory:

- [ ] `CTO_PLAN.md` — verified present and non-empty
- [ ] `IMPLEMENTATION_REPORT.md` — verified present AND timestamp predates reviewer access time

**If either file is missing:**
1. Agent MUST halt immediately — do not read code, do not run git diff, do not begin assessment
2. Write `BLOCKED_BY_MISSING_ARTIFACTS.md` to the task directory:
   ```markdown
   # BLOCKED BY MISSING ARTIFACTS

   **Task**: <TASK_ID>
   **Blocked By**: <agent_name/model>
   **Timestamp**: <ISO-8601>

   ## Missing Artifacts
   - <artifact 1> — status: absent/created-after-review-start
   - ...

   ## Required Next Step
   The Implementer must produce all missing artifacts. The user must be notified of this blockage.
   ```
3. Send `PM_STATUS_UPDATE` with status="BLOCKED", reason="G3 entry gate failed — missing artifacts"
4. Do not proceed until the missing artifacts appear and are verified

**This rule overrides all other review duties.** No review report, no scoring rubric, no recommendation — nothing happens without the prerequisite files. This prevents TASK_DS_EO_024-style gaps where review never occurred but Post-G4 proceeded anyway.

### §10.2 Pre-G4 Enforcement (CTO Entry Gate)

Before the CTO issues a final G4 decision, the following must exist:

- [ ] `REVIEW_REPORT.md` — verified present with a valid recommendation field
- [ ] `IMPLEMENTATION_REPORT.md` — verified present

**If REVIEW_REPORT.md is missing:**
1. CTO MUST NOT issue an approval or rejection at G4
2. Document in `BLOCKED_BY_MISSING_ARTIFACTS.md` that G3 was never executed
3. Send `PM_STATUS_UPDATE` with status="BLOCKED", reason="G4 cannot execute — no review report (G3 was skipped)"

**This rule prevents the TASK_DS_EO_024 violation where Post-G4 was performed without any prior review.**

### §10.3 Pre-Post-G4 Enforcement (PM Entry Gate)

Before the PM begins ANY Post-G4 work, the following files must ALL exist in the task directory with valid content:

- [ ] `CTO_PLAN.md` — present and non-empty
- [ ] `IMPLEMENTATION_REPORT.md` — present and non-empty
- [ ] `REVIEW_REPORT.md` — present with a valid recommendation (APPROVE, APPROVE_WITH_COMMENTS, REQUEST_CHANGES, or REJECT)
- [ ] `CTO_APPROVAL.md` — present with an **APPROVE** decision

**If ANY file is missing:**
1. PM MUST halt immediately — do not update status, do not write CHANGELOG, do not commit, do not push
2. Write `BLOCKED_BY_MISSING_ARTIFACTS.md` to the task directory documenting which artifacts are absent and why Post-G4 cannot proceed
3. Send `PM_STATUS_UPDATE` with status="BLOCKED", reason="<specific missing artifact(s)>"
4. Notify user: "Post-G4 blocked for <TASK_ID> — missing: <list>. Review (G3) and/or CTO approval (G4) were not executed."

**This rule is absolute.** PM has no authority to proceed with Post-G4 work without all four artifacts. This directly prevents TASK_DS_EO_024 where PM_CLOSED.md was written before G3 and G4 ever occurred.

### §10.4 Enforcement Rule: No Inferred Completion

No agent may infer that a prior phase completed based on:
- Chat messages or verbal claims
- Code changes that appear to match the spec
- Test results that pass
- Any other indirect evidence

**The only valid evidence of phase completion is the existence of the required artifact files on disk.** If a file doesn't exist, the phase never completed — period.

### §10.5 Enforcement Rule: No Cross-Agent Duty Substitution

If an agent encounters missing artifacts that it could theoretically produce itself, it MUST NOT fill them in. Each agent's output is its designated role artifact only:
- Reviewer writes REVIEW_REPORT.md only
- CTO writes CTO_APPROVAL.md only
- PM writes post-G4 deliverables only
- No agent may write another agent's artifacts under any circumstance

This rule prevents TASK_DS_EO_024 where the Reviewer wrote PM_CLOSED.md (a Post-G4 artifact) instead of REVIEW_REPORT.md (a G3 artifact).

---

## Phase Gate Compliance Verification File (NEW §11.0)

**Requirement:** Every task directory MUST contain a `TASK_COMPLETION_AUDIT.md` file that tracks which gates were executed and in what order. This file is the authoritative source for whether a task has properly completed all gates.

### TASK_COMPLETION_AUDIT.md Format

```markdown
# Task Completion Audit — <TASK_ID>

## Gate Execution Log
| Gate | Status | Artifact Produced | Produced By | Timestamp | Verified |
|------|--------|-------------------|-------------|-----------|----------|
| G1 | ✅ Executed | CTO_PLAN.md | CTO + User | YYYY-MM-DDTHH:MM:SS | YYYY-MM-DDTHH:MM:SS |
| G2 | ⏳ Pending | — | — | — | — |
| G3 | ❌ NOT EXECUTED | — | — | — | — |
| G4 | ❌ NOT EXECUTED | — | — | — | — |
| Post-G4 | ❌ BLOCKED (G3, G4 missing) | — | — | — | — |

## Blockers
- <list any blockers here>

## Gate Compliance Checklist
| Requirement | Met? | Evidence |
|-------------|------|----------|
| G3 review occurred | [ ] | REVIEW_REPORT.md present with recommendation |
| G4 CTO approval issued | [ ] | CTO_APPROVAL.md present with APPROVE decision |
| All 4 artifacts exist on disk | [ ] | ls confirms all files |
| Post-G4 atomic (completed in one session) | [ ] | PM_CLOSED timestamp check |

## Final Status: <PENDING_BLOCKED | ACTIVE | COMPLETE>
```

### Rules for TASK_COMPLETION_AUDIT.md

1. **Must be created at task open time** with all gates initialized to pending
2. **Updated after each gate execution** — status, artifact name, producer, timestamps
3. **Must exist before any phase transition** — the receiving agent reads this file as part of its prerequisite check
4. **Final Status must match reality** — if Post-G4 was written but G3/G4 are "NOT EXECUTED", mark as BLOCKED and flag violation
5. **If a gate is "NOT EXECUTED" but later gates claim completion, this is a process violation** — write `BOUNDARY_VIOLATION.md` and notify user

---

## Process Violation Documentation (NEW §12.0)

### When to Write BOUNDARY_VIOLATION.md

Write this file whenever:
- An agent proceeded past a gate without required artifacts
- A phase was skipped entirely (e.g., G3 never executed but Post-G4 ran)
- An agent produced another agent's artifact
- An implementation report was retroactively produced after review started
- Any gate sequence is out of order

### BOUNDARY_VIOLATION.md Format

```markdown
# Boundary Violation — <TASK_ID>

**Violation Type**: <type — e.g., "G3_SKIP_POST_G4", "REPORT_RETROACTIVE", "CROSS_AGENT_DUTY">
**Detected By**: <agent/model>
**Timestamp**: <ISO-8601>

## Description
<What happened, what should have happened, and the gap>

## Timeline
| Timestamp | Action | Agent | Issue |
|-----------|--------|-------|-------|
| ... | ... | ... | ... |

## Required Remediation
1. <specific action to fix>
2. <specific action to fix>

## Impact Assessment
- Severity: <Low | Medium | High | Critical>
- Work affected: <description>
- User notified: [ ] Yes / [ ] No
```

### Severity Definitions

| Severity | When to Use | Required Response |
|----------|-------------|-------------------|
| **Critical** | Post-G4 performed without G3/G4 approval; work committed/pushed without gates | Immediate user notification; halt all subsequent work on this task until remediated |
| **High** | Gate skipped but not yet committed; review started without implementation report | Block phase; notify user in session |
| **Medium** | Report produced after deadline but before review started | Flag in BOUNDARY_VIOLATION.md; note for CTO evaluation of Implementer |
| **Low** | Minor process deviations that don't affect task integrity | Log for process improvement review; no user notification required |

---

---

### Transition 0c: PM → CTO (Pre-Plan Handoff — TASK_DS_EO_030 fix)

**Trigger**: PM has completed task intake and workspace preparation.

**PM Output** (the ONLY thing the PM may produce during this transition):
```json
{
    "type": "READY_FOR_CTO",
    "taskId": "TASK_<YYYYMMDD>_<NNN>",
    "workspacePath": "<path to reports directory>",
    "artifactsAvailable": ["TASK_REQUEST.md", "MANIFEST.md", "PM_ANALYSIS.md"],
    "status": "INTAKE_COMPLETE",
    "pmStopReason": "Intake boundary reached. CTO must independently perform technical analysis.",
    "pmAnalysisIsUserRequestOnly": true,
    "pmDidNotPerformArchitecturalAnalysis": true
}
```

**CTO Verification Before Planning**:
1. Confirm `TASK_REQUEST.md` exists and contains the verbatim user request.
2. Read `PM_ANALYSIS.md` — but treat it as **user-submitted context**, not authoritative planning content.
3. Perform independent architectural analysis of the repository.
4. Produce `CTO_PLAN.md` independently, without copying or relying on any PM-authored planning artifacts.

**Boundary Enforcement**: If the CTO finds that `PM_ANALYSIS.md` contains architectural analysis (rather than request interpretation), the CTO must note this in `BOUNDARY_VIOLATION.md` but still proceed with independent analysis. The user should be notified of the boundary violation.

**Prohibited PM Actions During This Transition**:
- ❌ Writing `CTO_PLAN.md`
- ❌ Performing architectural analysis
- ❌ Designing technical solutions
- ❌ Selecting implementation components
- ❌ Submitting G1 or any gate approval

DELEGATION_FIX
echo "handoff_protocol.md updated with PM→CTO transition"

---

### Transition 0c: PM → CTO (Pre-Plan Handoff)

**Trigger**: PM has completed task intake and workspace preparation.

**PM Output** (the ONLY thing the PM may produce during this transition):
```json
{
    "type": "READY_FOR_CTO",
    "taskId": "TASK_<YYYYMMDD>_<NNN>",
    "workspacePath": "<path to reports directory>",
    "artifactsAvailable": ["TASK_REQUEST.md", "MANIFEST.md"],
    "status": "INTAKE_COMPLETE",
    "pmStopReason": "Intake boundary reached. CTO must independently perform technical analysis.",
    "pmDidNotPerformArchitecturalAnalysis": true
}
```

**CTO Verification Before Planning**:
1. Confirm `TASK_REQUEST.md` exists and contains the verbatim user request.
2. Read `PM_ANALYSIS.md` — but treat it as **user-submitted context**, not authoritative planning content.
3. Perform independent architectural analysis of the repository.
4. Produce `CTO_PLAN.md` independently.

**Prohibited PM Actions**:
- Writing `CTO_PLAN.md` or any planning artifact
- Architectural analysis, gap analysis, design decisions
- Selecting implementation components/files
- Submitting G1 or any gate approval

