# DS-EO Communication Protocol (Global Standard)

**Version**: 1.0  
**Status**: Active  
**Scope**: All OpenClaw workspaces using DS-EO  

---

## Purpose

Defines the standard message format and naming conventions for agent-to-agent communication during development workflows. This protocol covers **development-layer** communication only — it does not modify or replace runtime agent schemas.

---

## Message Types

### 1. Task Open (`TASK_OPEN`)

Sent by: PM → CTO (task initiation)  
Required fields:

```json
{
  "type": "TASK_OPEN",
  "taskId": "TASK_<YYYYMMDD>_<NNN>",
  "specRef": "<path to relevant spec or requirement>",
  "priority": "P0 | P1 | P2",
  "notes": "<user-provided context, priority rationale>"
}
```

### 2. Task Status Update (`PM_STATUS_UPDATE`)

Sent by: PM → User / relevant parties (informational)  
Required fields:

```json
{
  "type": "PM_STATUS_UPDATE",
  "taskId": "<optional TASK id if applicable>",
  "status": "IN_PROGRESS | BLOCKED | AWAITING_REVIEW | IN_REVIEW | APPROVED | COMPLETE | AWAITING_USER",
  "milestoneProgress": "<cumulative progress toward next milestone, if applicable>",
  "message": "<brief status description>"
}
```

### 3. Task Stalled (`TASK_STALLED`)

Sent by: PM → CTO / relevant parties (escalation)  
Required fields:

```json
{
  "type": "TASK_STALLED",
  "taskId": "TASK_<YYYYMMDD>_<NNN>",
  "currentPhase": "<phase name where stall occurred>",
  "lastActivity": "<timestamp of last artifact update>",
  "reason": "<description of stall condition>"
}
```

### 4. Task Closed (`PM_CLOSED`)

Sent by: PM → User / relevant parties (completion notification)  
Required fields:

```json
{
  "type": "PM_CLOSED",
  "taskId": "TASK_<YYYYMMDD>_<NNN>",
  "artifactsVerified": ["CTO_PLAN.md", "IMPLEMENTATION_REPORT.md", "REVIEW_REPORT.md", "CTO_APPROVAL.md"],
  "statusUpdatesWritten": true,
  "changelogUpdated": true
}
```

---

### 5. Task Delegation (`DELEGATE`)

Sent by: CTO → Implementer  
Required fields:

```json
{
  "type": "DELEGATE",
  "taskId": "TASK_<YYYYMMDD>_<NNN>",
  "title": "<brief title>",
  "specRef": "<path to relevant spec, e.g. specs/active/SPEC-XXXX.md>",
  "acceptanceCriteria": ["<criterion 1>", "<criterion 2>"],
  "artifactsExpected": ["<artifact name>"],
  "constraints": ["<constraint 1>"],
  "notes": "<optional context or rationale>"
}
```

### 6. Implementation Complete (`IMPL_COMPLETE`)

Sent by: Implementer → Reviewer (via CTO)  
Required fields:

```json
{
  "type": "IMPL_COMPLETE",
  "taskId": "TASK_<YYYYMMDD>_<NNN>",
  "reportPath": "<full path to IMPLEMENTATION_REPORT.md>",
  "testResults": {
    "passed": ["<test name>"],
    "failed": ["<test name with reason>"]
  },
  "changesSummary": "<brief summary of files modified>",
  "notes": "<any blockers or known issues>"
}
```

### 7. Review Complete (`REVIEW_COMPLETE`)

Sent by: Reviewer → CTO (chat artifact, then copied to file)  
Required fields:

```json
{
  "type": "REVIEW_COMPLETE",
  "taskId": "TASK_<YYYYMMDD>_<NNN>",
  "reportPath": "<full path to REVIEW_REPORT.md if written>",
  "findingsSummary": "<brief summary of key findings>",
  "recommendation": "APPROVE | APPROVE_WITH_COMMENTS | REQUEST_CHANGES | REJECT",
  "specComplianceScore": "<1-5 or pass/fail>",
  "regressionStatus": "NONE | DETECTED (describe)",
  "notes": "<detailed findings>"
}
```

### 8. Approval Decision (`APPROVAL_DECISION`)

Sent by: CTO → User / Implementer  
Required fields:

```json
{
  "type": "APPROVAL_DECISION",
  "taskId": "TASK_<YYYYMMDD>_<NNN>",
  "decision": "APPROVE | REJECT",
  "rationale": "<reasoning referencing Reviewer report and spec compliance>",
  "nextSteps": "<if rejected: what to fix or revise>"
}
```

### 9. Status Update (`STATUS_UPDATE`)

Sent by: Any agent → relevant parties (informational)  
Required fields:

```json
{
  "type": "STATUS_UPDATE",
  "taskId": "<optional TASK id if applicable>",
  "status": "IN_PROGRESS | BLOCKED | AWAITING_REVIEW | IN_REVIEW | COMPLETE",
  "message": "<brief status description>"
}
```

### 10. Completion Summary (NEW) — CTO → User (Post-G4)

Sent by: CTO → User **immediately after** writing `CTO_APPROVAL.md` at Gate G4 approval. This is a mandatory handoff from the technical authority to the user, summarizing what was approved and proposing next steps.

**Required fields**:
```json
{
  "type": "COMPLETION_SUMMARY",
  "taskId": "TASK_<YYYYMMDD>_<NNN>",
  "decision": "APPROVE | REJECT",
  "deliverablesCompleted": ["<list of deliverable names and file paths>"],
  "reviewScore": "<overall review score or N/A if rejected>",
  "nextAvailableTasks": [
    {
      "title": "<proposed task title>",
      "priority": "P0 | P1 | P2",
      "briefScope": "<one-line summary>"
    }
  ],
  "pmActionRequired": true,
  "notes": "<optional context>"
}
```

**Timing**: This message is sent *before* the PM begins Post-G4 cleanup — it is a CTO deliverable that triggers the user's awareness and enables informed prioritization of Phase N+1.

---

## PM Communication Patterns

### Pattern 1: Periodic Status Reports
- **When**: At regular intervals or upon notable progress during any TASK lifecycle phase.
- **To**: User / organization stakeholders.
- **Content**: Process state only — task status, milestone progress, blockers (non-technical).
- **Format**: `PM_STATUS_UPDATE` message type.

### Pattern 2: Milestone Summaries
- **When**: After Gate G4 approval and post-G4 PM checklist completion.
- **To**: User / organization stakeholders.
- **Content**: Summary of completed work, cumulative progress toward next milestone, changelog entries made.
- **Format**: `PM_STATUS_UPDATE` message with milestone context.

### Pattern 3: Release Announcements
- **When**: After a set of TASKs is closed and project status reflects the release.
- **To**: User / organization stakeholders.
- **Content**: What shipped, which TASKs contributed, link to CHANGELOG entries.
- **Format**: `PM_STATUS_UPDATE` message with release context.

### Pattern 4: Stall Escalation
- **When**: Task has not progressed within expected timeframe.
- **To**: CTO (for technical resolution).
- **Content**: Current phase, last activity timestamp, stall reason.
- **Format**: `TASK_STALLED` message type.

### Pattern 5: Proactive Next-Task Proposal (NEW)

- **When**: Immediately after Post-G4 cleanup is complete AND the user has not already initiated a new task request.
- **To**: User.
- **Content**: "Here's what just shipped. Here are the next tasks available per the roadmap — which do you want to prioritize?"
- **Format**: `PM_STATUS_UPDATE` message containing:
  - Completed deliverables summary (1 sentence)
  - Ranked list of next-available tasks with priority and one-line scope
  - Explicit question asking for prioritization direction

**This pattern ensures the PM proactively drives the workflow forward instead of waiting passively for user input.** A task's completion is not considered "complete" from a process standpoint until the next-task proposal has been sent to the user.

---

## Communication Boundaries

1. **PM communicates process state** — task status, milestone progress, administrative updates.
2. **PM does NOT communicate technical content** — all technical discussion flows through Implementer → CTO channels (`DELEGATE`, `IMPL_COMPLETE`, `REVIEW_COMPLETE`).
3. The Reviewer never sends an IMPL_COMPLETE or DELEGATE message.
4. Chat artifacts must include the full path to any file-based deliverable.

### Role Boundaries (NEW §5.0)

| Agent | May Do | May NOT Do | Enforcement |
|-------|--------|------------|-------------|
| **PM** | Create task requests, orchestrate process, Post-G4 admin, user notifications | Write CTO plans, make technical decisions, delegate implementation | Cross-boundary action is a process violation; must be flagged and corrected |
| **CTO** | Architectural analysis, task plans, G1/G3/G4 decisions, Completion Summary to user | Implement code, write review reports, do Post-G4 cleanup | CTO's authority ends at CTO_APPROVAL.md |
| **Implementer** | Code per approved plan, tests, implementation report | Architect anything new, decide gates, communicate with Reviewer directly | All work must match the CTO plan exactly; deviations require CTO return |
| **Reviewer** | Independent verification, review report with scoring and recommendation | Approve or reject (only recommends to CTO), modify code or non-review files | Scoping is strictly one TASK directory; only REVIEW_REPORT.md may be written |

### Violation Response Protocol (NEW §5.1)

When any agent detects a role boundary violation by another agent:
1. **Stop** — Do not proceed with the violating work
2. **Flag** — Document the specific violation in the task directory as `BOUNDARY_VIOLATION.md`
3. **Return** — Send the work back to the originating agent with specifics
4. **User notification** — If the violation affects deliverable quality or timeline, notify the user via PM_STATUS_UPDATE

Examples of violations:
- PM writing a CTO_PLAN.md → boundary violation (PM cannot write technical plans)
- Implementer making architectural decisions not in the CTO plan → boundary violation
- Reviewer modifying code files outside REVIEW_REPORT.md → boundary violation
- CTO doing Post-G4 cleanup → boundary violation

---

## Naming Conventions

### Task IDs

- Format: `TASK_<YYYYMMDD>_<NNN>`
- YYYYMMDD = date the task is created
- NNN = sequential number, resets daily (start at `_001`)
- Assigned exclusively by CTO

### Artifact Names

| Phase | Artifact Name | Case Convention |
|-------|--------------|-----------------|
| Planning | `CTO_PLAN.md` | Title Case |
| Implementation | `IMPLEMENTATION_REPORT.md` | Pascal Case |
| Review | `REVIEW_REPORT.md` | Pascal Case |
| Approval | `CTO_APPROVAL.md` | Title Case |

### Directory Structure

```
docs/development/reports/TASK_<id>/
├── CTO_PLAN.md
├── IMPLEMENTATION_REPORT.md
├── REVIEW_REPORT.md          (written by Reviewer directly)
├── CTO_APPROVAL.md
└── SESSION_INTERRUPT.md      (if session ends mid-sequence)
└── BOUNDARY_VIOLATION.md     (if role boundary is crossed)
```

---

## Message Lifecycle

1. **Created** → Agent initiates a message (e.g., DELEGATE from CTO)
2. **Acknowledged** → Receiving agent confirms receipt
3. **Processed** → Work is performed based on the message
4. **Completed** → Result or next message is produced
5. **Archived** → Message is captured in task artifacts

---

## Rules

1. All task-related communication must reference a `taskId`.
2. Messages should be concise; detailed content goes into artifact files, not chat messages.
3. The Implementer never initiates a DELEGATE message — it only receives them from CTO.
4. Chat artifacts must include the full path to any file-based deliverable.
5. PM communicates process state only — technical content flows through Implementer → CTO channels.
6. **CTO must send COMPLETION_SUMMARY immediately after G4 approval** — user awareness and next-task prioritization cannot be deferred to PM.
7. **PM must proactively propose next tasks after Post-G4** — workflow ownership includes driving forward, not just recording.

---

## Related Protocols

- `delegation_protocol.md` — How tasks are created and assigned
- `completion_protocol.md` — What constitutes a complete deliverable per role
- `handoff_protocol.md` — Transition requirements between phases
- `review_protocol.md` — Review criteria and scoring
- `approval_protocol.md` — Approval gate rules
