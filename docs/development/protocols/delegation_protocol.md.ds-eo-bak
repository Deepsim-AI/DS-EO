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
PM creates TASK skeleton → PM assigns to CTO for plan → User approves (G1) → CTO delegates to Implementer
```

### Step 1: Task Creation and Initiation

**CTO Role — Technical Planning**: The CTO is the sole authority for writing `CTO_PLAN.md` containing technical content:
- Problem statement
- Current-state analysis
- Proposed changes with affected files
- Acceptance criteria (derived from spec)
- Risks and constraints
- Implementation instructions

**PM Role — Task Initiation and Orchestration**: The Project Manager initiates task creation by:
1. Determining if it's a continuation of an existing TASK or a new one.
2. Creating directory: `docs/development/reports/TASK_<YYYYMMDD>_<NNN>/`
3. Assigning ID following naming convention in `communication_protocol.md`.
4. Writing `CTO_PLAN.md` **placeholder** (not technical content) — a structured skeleton with section headers and instructions for the CTO to fill:
   ```
   # CTO Plan Placeholder
   ## Instructions
   The CTO shall populate this file with the architectural plan including:
   - Problem statement
   - Current-state analysis
   - Proposed changes with affected files
   - Acceptance criteria (derived from spec)
   - Risks and constraints
   - Implementation instructions
   ```
5. Handing off to CTO for technical planning work.

**PM → CTO Handoff**: PM transitions the task to CTO by sending a `TASK_OPEN` message with:
- Task ID and directory path
- Reference to the originating spec or requirement
- Any user-provided context or priority notes
- Note: "CTO_PLAN.md placeholder ready — please populate with technical plan"

**PM → Reviewer Handoff**: After Gate G4, PM transitions a completed task to the Reviewer for final verification by sending a `TASK_STATUS_UPDATE` message.

**PM → Close Handoff**: Post-G4 cleanup. PM archives the task directory, updates project status, and sends `TASK_CLOSED` notification.

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
5. **PM does not write technical content** — it creates task skeletons and plan placeholders only; all architectural decisions remain with the CTO.

---

## Related Protocols

- `communication_protocol.md` — Message format standards
- `completion_protocol.md` — What Implementer must deliver at completion
- `handoff_protocol.md` — Phase transition requirements
