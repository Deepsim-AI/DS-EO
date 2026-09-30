# DS-EO Delegation Protocol (Global Standard)

**Version**: 1.1  
**Status**: Active  
**Scope**: All OpenClaw workspaces using DS-EO  

---

## Purpose

Defines the standard process for creating and assigning implementation tasks in development workflows. This protocol ensures every task has a clear scope, acceptance criteria, and handoff contract.

---

## Delegation Flow — V1.1 Revised

```
User request arrives → G0 owner (PM or CTO, determined by path) → G0 intake (create folder + TASK_REQUEST.md) → CTO planning (CTO_PLAN.md) → User approves (G1) → Implementation → Review → Approval → Post-G4 closure
```

### Step 1: Task Creation and G0 Intake

**G0 ownership rule**: The agent that receives the initial customer request owns G0 intake. This produces two possible flows:

#### Flow A: User → PM (Secretary/Intake path)

When a user requests new work through the PM:

1. **PM creates the task folder:** Creates `docs/development/reports/TASK_<NNN>/` directory (ID assigned by CTO if available, otherwise PM assigns placeholder ID)
2. **PM writes `TASK_REQUEST.md`:** Captures verbatim user request, any requirements gathered during intake conversation, and priority
3. **PM notifies the user:** Tells them they may add specifications, documents, examples, datasets, references, or other supporting materials to the task folder
4. **PM stops at G0:** Outputs `READY_FOR_CTO` handoff message. PM does NOT write `CTO_PLAN.md`, perform architectural analysis, or select implementation approaches.

#### Flow B: User → CTO directly

When a user requests new work directly with the CTO:

1. **CTO creates the task folder:** Creates `docs/development/reports/TASK_<YYYYMMDD>_<NNN>/` directory and assigns ID
2. **CTO writes `TASK_REQUEST.md`:** Captures verbatim user request, clarifies requirements with the user if needed
3. **CTO stops at G0 intake:** After producing `TASK_REQUEST.md`, the CTO independently performs architectural analysis and produces `CTO_PLAN.md` (this is still G1 planning, not a G0 activity)

**In both flows, `TASK_REQUEST.md` exists before any technical planning begins.** The difference is only in *who* creates it.

### Step 2: Technical Planning (G1) — CTO Exclusive

After G0 intake completes (in either flow), the CTO owns all technical planning:

- **CTO Role — Sole Authority for Technical Planning:**
  - Writes `CTO_PLAN.md` containing architectural analysis, problem statement, acceptance criteria, risks, constraints, and implementation instructions
  - Owns all technical content in `CTO_PLAN.md`. No other agent may produce this artifact.
  - Performs independent analysis of the repository — does not rely on or copy PM-authored intake context as authoritative

### Step 3: Delegation to Implementer (Post-G1)

After user approval at Gate G1, the CTO delegates to the Implementer using the `DELEGATE` message format defined in `communication_protocol.md`. The delegation must include:
- **Task description** — What needs to be done
- **Spec reference** — Path to the relevant specification
- **Acceptance criteria** — Testable conditions for completion
- **Artifacts expected** — Required deliverables (file names and locations)
- **Constraints** — Boundaries the Implementer must respect

### Step 4: Implementation Contract

The delegation creates an implicit contract. The Implementer must:
1. Acknowledge receipt of the task assignment.
2. Confirm understanding of acceptance criteria before starting work.
3. Work within the stated constraints (no scope expansion without CTO approval).
4. Report completion via `IMPL_COMPLETE` message with all required fields.

---

## Task Folder Ownership — V1.1 Clarification

**G0 artifacts (folder + TASK_REQUEST.md) are created by whoever receives the request.** This is NOT a CTO-exclusive duty.

| What | Owner | Notes |
|------|-------|-------|
| Task folder creation | G0 owner (PM or CTO) | Whichever agent received the initial request |
| `TASK_REQUEST.md` | G0 owner (PM or CTO) | Intake artifact — records requirements, not plans |
| TASK ID assignment | G0 owner or CTO | If PM creates folder but doesn't have ID yet, uses placeholder; CTO can retroactively assign |
| `CTO_PLAN.md` | CTO exclusively | Technical planning — never produced during G0 intake |

**Key boundary rule:** Creating a task folder and writing `TASK_REQUEST.md` is **intake work**, not planning work. It does not involve architectural analysis, design decisions, or component selection. This is fundamentally different from producing `CTO_PLAN.md`.

---

## Spec Lifecycle Management

Specs (requirements derived from user input) follow this lifecycle:

1. **Creation:** CTO creates specs during the planning phase, derived from user requirements.
2. **Tracking:** PM tracks spec status (`active`, `in_progress`, `completed`, `archived`) in `PROJECT_STATUS.md`.
3. **Reference:** Implementer references specs but never modifies them — all changes go through a new CTO plan.
4. **Completion:** At G4 approval, the CTO moves the spec to "completed" status; PM records this update in `PROJECT_STATUS.md`.
5. **Archival:** Specs for closed/completed tasks may be archived per project policy.

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
| Implementer decides architecture not in plan | ❌ Implementer | ✅ CTO only |
| Reviewer modifies code | ❌ Reviewer | ✅ (prohibited) |
| CTO does Post-G4 cleanup | ❌ CTO | ✅ PM only |
| Any agent defers multi-step sequence to next session | ❌ All | ✅ Must complete in same session or document interruption |

### Intake Boundary — What "Creating a folder + TASK_REQUEST.md" Is NOT

The following are **NOT** violations of the intake/planning boundary when done during G0 by PM:
- Creating `TASK_REQUEST.md` with the user's stated requirements (verbatim or summarized)
- Organizing the task directory structure
- Notifying the user about adding supporting materials
- Stopping at G0 and handing off to CTO

The following **ARE** violations during G0 by PM:
- Analyzing the architecture of how to solve the problem
- Selecting implementation components or file paths
- Designing solutions or writing `CTO_PLAN.md`
- Making technical decisions about scope or approach

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
5. **No agent may perform another agent's core duties**, regardless of convenience or urgency. Boundary violations are process violations requiring documentation and user notification.
6. **G0 intake is NOT CTO-exclusive.** The task folder + `TASK_REQUEST.md` is produced by whichever agent received the customer request (PM or CTO). Only `CTO_PLAN.md` remains CTO-exclusive.

---

## Related Protocols

- `task_intake_protocol.md` — G0 intake, TASK_REQUEST.md format, folder locking (LOCK.md)
- `communication_protocol.md` — Message format standards
- `completion_protocol.md` — What Implementer must deliver at completion
- `handoff_protocol.md` — Phase transition requirements

---

## Intake Boundary Enforcement (NEW §5.0)

### Rule 1: Intake is Administrative Only

Whoever handles G0 intake creates workspace scaffolding (directories, file structure, verbatim request preservation). They do **not** produce technical plans. Stop at workspace creation and hand off to CTO for planning.

### Rule 2: `CTO_PLAN.md` Remains CTO-Exclusive

| Actor | May write `CTO_PLAN.md`? |
|-------|--------------------------|
| CTO   | ✅ Yes — exclusively |
| PM    | ❌ No |
| Implementer | ❌ No |
| Reviewer | ❌ No |
| Any other agent | ❌ No |

Creating a task directory and writing `TASK_REQUEST.md` is **not** producing `CTO_PLAN.md`. These are distinct artifacts with different purposes. Confusing them was the root cause of TASK_DS_EO_043's workflow failure.

### Rule 3: Mechanical Enforcement of Intake Boundaries

When any agent completes task intake, they **must** perform a self-audit before producing any further output:

1. List every action taken during this session
2. For each action, check: "Is this creating/organizing G0 workspace artifacts? If YES → OK. If NO → boundary violation."
3. If any non-intake actions are found (architectural analysis, solution design, component selection), **halt and document** in `BOUNDARY_VIOLATION.md`
4. Output only the standardized READY_FOR_CTO status line

### Rule 4: Same-Model Role Separation

When PM and CTO use the same model, role separation depends **entirely on prompt boundaries**, not model identity. Agents must recognize this risk and be extra vigilant about self-monitoring for role conflation. A self-authored CTO artifact by a PM is an automatic process violation regardless of model identity.

### Rule 5: Independent CTO Planning Required

Even when the PM's task workspace contains preliminary analysis or suggested approaches, the CTO **must independently** inspect the repository, perform their own technical analysis, and produce an authoritative `CTO_PLAN.md`. The CTO must not rely on or reference PM-authored planning content as authoritative — only as user-submitted context.
