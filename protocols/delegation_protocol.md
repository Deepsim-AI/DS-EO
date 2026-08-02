# DS-EO Delegation Protocol (Global Standard)

**Version**: 1.0  
**Status**: Active  
**Scope**: All OpenClaw workspaces using DS-EO  

---

## Purpose

Defines the standard process for creating and assigning implementation tasks in development workflows. This protocol ensures every task has a clear scope, acceptance criteria, and handoff contract.

---

## Delegation Flow

```
PM detects need for new task → PM requests CTO to create → CTO creates TASK directory + assigns ID → CTO writes CTO_PLAN.md → User approves (G1) → CTO delegates to Implementer
```

### Step 1: Task Creation and Initiation

**CTO Role — Sole Authority for Task Creation**: The CTO is the sole authority for creating task directories and assigning IDs:
- Creates `docs/development/reports/TASK_<YYYYMMDD>_<NNN>/` directory
- Assigns ID following naming convention in `communication_protocol.md`
- **Writes CTO_PLAN.md directly** — this is a technical document containing architectural analysis, problem statement, acceptance criteria, risks, constraints, and implementation instructions. No other agent may produce CTO_PLAN.md.
- Owns all technical content in `CTO_PLAN.md`.

**PM Role — Task Detection, Requesting, and Orchestration**: The Project Manager initiates task creation by:
1. Detecting that a new implementation task is needed (based on user requests, backlog review, or ongoing work).
2. **Requesting** the CTO to create the task: alerting the CTO with requirement reference, priority, and any user-provided context. The PM may *propose* what the task should cover, but must not write the plan itself.
3. The PM does NOT create directories, assign IDs, or write `CTO_PLAN.md` — those are exclusively CTO responsibilities.
4. After CTO creates the task and writes the plan, PM triggers the skeleton by sending a `TASK_OPEN` message.

**PM → CTO Handoff**: PM transitions the task to CTO by sending a `TASK_OPEN` message with:
- Task ID and directory path (assigned by CTO)
- Reference to the originating spec or requirement
- Any user-provided context or priority notes
- Note: "CTO has created the task — please populate CTO_PLAN.md with technical plan"

**PM → Reviewer Handoff**: After Gate G4, PM transitions a completed task to the Reviewer for final verification by sending a `TASK_STATUS_UPDATE` message.

**PM → Close Handoff**: Post-G4 cleanup. PM archives the task directory, updates project status, and sends `TASK_STALLED` notification.

---

## Spec Lifecycle Management

Specs (requirements derived from user input) follow this lifecycle:

1. **Creation**: CTO creates specs during the planning phase, derived from user requirements.
2. **Tracking**: PM tracks spec status (`active`, `in_progress`, `completed`, `archived`) in `PROJECT_STATUS.md`.
3. **Reference**: Implementer references specs but never modifies them — all changes go through a new CTO plan.
4. **Completion**: At G4 approval, the CTO moves the spec to "completed" status; PM records this update in `PROJECT_STATUS.md`.
5. **Archival**: Specs for closed/completed tasks may be archived per project policy.

### Rules

- Only the CTO creates or modifies specs.
- PM tracks but does not create or modify spec content.
- Implementer never writes to spec files — only reads them as reference.

---

## Role Boundary Enforcement (NEW §4.0)

**No agent may perform work that belongs to another role.** This is a fundamental boundary, not a suggestion.

### Violation Detection and Response

When any agent detects it is about to cross into another role's territory:

1. **Stop immediately** — Do not continue the action
2. **Document** — Write `BOUNDARY_VIOLATION.md` in the task directory describing what was attempted and which role owns that work
3. **Return** — Notify the appropriate agent that this work belongs to them
4. **User notification** (if timeline-impacting) — PM sends PM_STATUS_UPDATE

### Concrete Examples

| Wrong Action | Owner | Correct Agent |
|-------------|-------|---------------|
| PM writes CTO_PLAN.md | ❌ PM | ✅ CTO only |
| PM creates task directory | ❌ PM | ✅ CTO only |
| PM assigns TASK ID | ❌ PM | ✅ CTO only |
| Implementer decides architecture not in plan | ❌ Implementer | ✅ CTO only |
| Reviewer modifies code | ❌ Reviewer | ✅ N/A (only reports) |
| Reviewer writes anything except REVIEW_REPORT.md | ❌ Reviewer | ✅ (prohibited) |
| CTO does Post-G4 cleanup | ❌ CTO | ✅ PM only |
| Any agent defers multi-step sequence to next session | ❌ All | ✅ Must complete in same session or document interruption |

---

### Step 2: Task Delegation Message

After user approval at Gate G1, the CTO delegates to the Implementer using the `DELEGATE` message format defined in `communication_protocol.md`. The delegation must include:

- **Task description** — What needs to be done
- **Spec reference** — Path to the relevant specification
- **Acceptance criteria** — Testable conditions for completion
- **Artifacts expected** — Required deliverables (file names and locations)
- **Constraints** — Boundaries the Implementer must respect

### Step 3: Implementation Contract

The delegation creates an implicit contract. The Implementer must:

1. Acknowledge receipt of the task assignment.
2. Confirm understanding of acceptance criteria before starting work.
3. Work within the stated constraints (no scope expansion without CTO approval).
4. Report completion via `IMPL_COMPLETE` message with all required fields.

---

## Scope Containment Rules

1. **No feature creep**: Implementer must not add capabilities beyond what's in the approved plan.
2. **No architectural changes beyond plan**: Any deviation requires a formal CTO proposal and user approval.
3. **Single-task focus**: Each TASK directory contains work for exactly one task. Do not merge multiple tasks into one.
4. **Continuation only when pending**: Only the CTO may declare work as continuation of an existing TASK, and only when all acceptance criteria from the original plan are still pending.

---

## Delegation Message Template

```markdown
**DELEGATE** — Task: <taskId>

**Title**: <brief title>

**Spec Reference**: <path to spec file>

**Acceptance Criteria**:
1. <criterion 1>
2. <criterion 2>
3. ...

**Artifacts Expected**:
- `<artifact_name>` at `<expected_path>`

**Constraints**:
- <constraint 1>
- <constraint 2>

**Notes**: <optional context, rationale, or implementation hints>
```

---

## Rules

1. Only the CTO may delegate tasks to the Implementer.
2. The user must approve (Gate G1) before delegation occurs.
3. Every delegation must reference an existing spec or architecture document.
4. Acceptance criteria must be testable — vague criteria are grounds for returning to the CTO.
5. **PM does not write technical content** — it creates task requests and orchestrates process; all technical artifacts (directories, IDs, plans) are exclusively CTO responsibilities.
6. **No agent may perform another agent's core duties**, regardless of convenience or urgency. Boundary violations are process violations requiring documentation and user notification.

---

## Related Protocols

- `communication_protocol.md` — Message format standards
- `completion_protocol.md` — What Implementer must deliver at completion
- `handoff_protocol.md` — Phase transition requirements
