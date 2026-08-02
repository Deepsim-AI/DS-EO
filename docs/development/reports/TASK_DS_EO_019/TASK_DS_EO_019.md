# TASK_DS_EO_019

## Title

Design Configurable Manual and Automatic Workflow Execution Modes

---

## Background

DS-EO OpenClaw Edition has evolved from its original manually orchestrated workflow into a formal four-role engineering organization consisting of:

* **CTO / Architect** — architecture, planning, and final approval authority
* **Project Manager (PM)** — process coordination, task lifecycle tracking, and handoff verification
* **Implementer** — approved implementation and repository changes
* **Reviewer** — independent quality verification

The current DS-EO development lifecycle is governed by four formal gates:

```text
User Request
    │
    ▼
PM Lifecycle Coordination
    │
    ▼
CTO Planning
    │
   G1
    │
    ▼
Implementer
    │
   G2
    │
    ▼
Reviewer
    │
   G3
    │
    ▼
CTO Final Approval
    │
   G4
    │
    ▼
Completed
```

The current system primarily relies on **manual agent selection and transition by the user**. This mode provides high transparency and control and is valuable for development, debugging, experimentation, and critical work.

However, as DS-EO matures, the user should be able to choose whether workflow progression is:

1. **Manual** — the user explicitly controls agent activation and progression; or
2. **Automatic** — the PM coordinates eligible workflow transitions automatically while respecting all existing roles, protocols, artifacts, and approval gates.

The objective is therefore not to create a second engineering process.

The objective is to make **workflow execution strategy configurable while preserving one canonical DS-EO engineering lifecycle**.

---

# 1. Objective

Design the architecture required for DS-EO to support configurable workflow execution modes.

The design must establish:

* Manual execution
* Automatic execution
* The relationship between execution mode and PM orchestration
* A formal workflow state model
* State-transition rules
* Gate and approval behavior
* Configuration requirements
* Human-intervention points
* Failure, rejection, and stall handling
* A future implementation roadmap

The design must be based on the **current DS-EO architecture and protocols**, not on the original TASK_DS_EO_003 assumptions.

---

# 2. Core Architectural Principle

## One Engineering Workflow, Multiple Execution Strategies

Manual and Automatic modes must not create separate engineering processes.

Both modes MUST use the same:

* roles
* responsibilities
* task lifecycle
* protocols
* artifacts
* gate definitions
* acceptance criteria
* review requirements
* approval authority
* rejection handling
* completion requirements

Only the mechanism used to advance the workflow differs.

Conceptually:

```text
                    ┌──────────────────────┐
                    │ Canonical DS-EO      │
                    │ Engineering Workflow │
                    └──────────┬───────────┘
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
           Manual Mode                Automatic Mode
                 │                           │
          User controls               PM coordinates
          progression                 eligible transitions
                 │                           │
                 └─────────────┬─────────────┘
                               │
                    Same G1 → G2 → G3 → G4
                    Same protocols
                    Same artifacts
                    Same authority
```

Execution mode must therefore be treated as an **orchestration concern**, not as a modification of the engineering protocol.

---

# 3. Current Workflow Baseline

The design must treat the current DS-EO workflow as the baseline.

The current lifecycle is:

```text
User Request
    ↓
PM Lifecycle Coordination
    ↓
CTO Planning
    ↓
G1 — User Approval
    ↓
Implementer
    ↓
G2 — Implementation Completion / CTO Confirmation
    ↓
Reviewer
    ↓
G3 — Review / CTO Confirmation
    ↓
CTO Final Approval
    ↓
G4 — Complete
```

The current Gate Authority Matrix is authoritative for gate ownership, decision authority, required artifacts, and transition conditions.

The execution-mode design MUST NOT redefine these gates.

---

# 4. Manual Mode

Manual Mode is the current reference execution strategy.

## Characteristics

In Manual Mode:

* The user explicitly controls progression between agents.
* The user may select or activate the next agent.
* The user can inspect intermediate outputs before continuing.
* PM still performs its defined process-coordination responsibilities.
* PM still verifies handoff prerequisites.
* Agents remain bound by their existing roles and protocols.
* G1–G4 remain mandatory.
* Approval authority does not change.

Manual Mode must remain fully supported.

It must not be treated as a deprecated or fallback mode.

## Purpose

Manual Mode is particularly appropriate for:

* architecture development
* debugging
* protocol development
* learning and experimentation
* high-risk changes
* situations requiring close human supervision
* diagnosing workflow failures

---

# 5. Automatic Mode

Automatic Mode allows DS-EO to progress through eligible workflow stages without requiring the user to manually activate every agent.

The PM becomes the primary **workflow orchestration coordinator**.

However, Automatic Mode MUST NOT give the PM authority that it does not possess in Manual Mode.

The PM must continue to:

* monitor workflow state
* verify prerequisites
* verify artifact completeness
* verify required metadata
* coordinate handoffs
* identify blockers
* report stalled tasks
* route work to the appropriate next role

The PM must NOT:

* make architectural decisions
* approve CTO plans
* approve implementation quality
* replace the Reviewer
* issue CTO G4 approval
* change task scope
* bypass required gates
* modify source code
* perform Git operations
* convert a failed review into an approval

Automatic Mode therefore means:

> **Automatic transition orchestration, not automatic authority.**

---

# 6. Human Approval Gates

The design MUST distinguish between:

### Workflow automation

Actions that may be performed automatically when prerequisites are satisfied.

Examples:

* detecting that an agent has completed its phase
* checking required artifacts
* checking metadata
* updating workflow state
* notifying the next role
* requesting the next agent to act
* routing a rejected implementation back to the Implementer

### Engineering authority

Decisions that belong to a specific role and cannot be transferred merely because Automatic Mode is enabled.

The design must preserve the current gate authorities.

At minimum:

| Gate | Authority                                     |
| ---- | --------------------------------------------- |
| G1   | User                                          |
| G2   | Implementer declares completion; CTO confirms |
| G3   | Reviewer evaluates/recommends; CTO confirms   |
| G4   | CTO                                           |

Automatic execution MUST NOT silently convert these decisions into PM decisions.

---

# 7. Automatic Mode and User Intervention

The design must explicitly define when Automatic Mode:

1. proceeds without user intervention
2. pauses and waits for the user
3. requests CTO action
4. routes work back to the Implementer
5. waits for Reviewer action
6. reports a blocker
7. terminates or stalls the workflow

The design should distinguish at least:

```text
AUTOMATICALLY PROCEED
        │
        ├── prerequisites satisfied
        └── no approval authority required at this point

PAUSE / REQUEST HUMAN ACTION
        │
        ├── G1 User Approval
        ├── unresolved ambiguity
        ├── blocked workflow
        ├── exceptional condition
        └── configured human intervention point
```

Automatic Mode must never interpret the absence of a response as approval.

---

# 8. Workflow State Model

Design a formal state machine representing the actual DS-EO lifecycle.

The state model should be based on the existing four-phase / four-gate workflow rather than introducing an unrelated lifecycle.

The CTO must determine the canonical states and transitions.

The design should address states such as:

* `TASK_OPEN`
* `PLANNING`
* `WAITING_G1`
* `IMPLEMENTATION`
* `WAITING_G2`
* `REVIEW`
* `WAITING_G3`
* `FINAL_APPROVAL`
* `COMPLETED`
* `CHANGES_REQUESTED`
* `BLOCKED`
* `STALLED`

The final state names are to be determined by the CTO.

For every state, define:

* owner
* entry condition
* required artifacts
* permitted actions
* exit condition
* next valid states
* whether Manual Mode can advance it
* whether Automatic Mode can advance it
* whether human intervention is required

---

# 9. Transition Rules

The design MUST define explicit transition rules.

For example:

```text
Planning
   │
   ├── G1 approved ─────────→ Implementation
   │
   └── G1 changes requested → Planning
```

```text
Implementation
   │
   ├── G2 conditions satisfied → Review
   │
   └── incomplete / blocked ──→ Implementation / Blocked
```

```text
Review
   │
   ├── review passes → Final Approval
   │
   └── changes requested → Implementation
```

```text
Final Approval
   │
   ├── CTO approves → Completed
   │
   └── CTO rejects → appropriate rework state
```

The exact state machine must be derived from the current protocols and Gate Authority Matrix.

No transition may be introduced that contradicts existing DS-EO governance.

---

# 10. PM as Workflow Orchestrator

The PM should be designed as the orchestration layer for Automatic Mode, while retaining its existing role boundaries.

The PM may:

* observe workflow state
* verify prerequisites
* verify artifacts
* verify metadata
* determine whether a transition is eligible
* initiate the next permitted handoff
* maintain task status
* maintain project status
* report blockers
* coordinate rework loops
* detect stalled tasks

The PM may NOT:

* create architectural decisions
* change CTO plans
* approve or reject implementation
* perform review evaluation
* grant CTO approval
* bypass gates
* change protocol requirements
* perform Git operations
* modify source code

The design should explicitly preserve this distinction.

---

# 11. Configuration Model

Design a configuration mechanism for selecting execution mode.

A proposed conceptual configuration is:

```yaml
workflow:
  execution_mode: manual
```

Supported initial values:

```yaml
workflow:
  execution_mode: manual
```

and:

```yaml
workflow:
  execution_mode: automatic
```

Future modes may be considered only if justified by the architecture.

Potential future configuration areas may include:

```yaml
workflow:
  execution_mode: automatic

  approvals:
    g1: human
    g2: governed
    g3: governed
    g4: human
```

This is illustrative only.

The CTO must determine whether approval configuration should be part of this task or deferred to a future task.

No configuration option may weaken mandatory governance requirements.

---

# 12. Mode Selection Timing

The design must explicitly determine **when execution mode is selected**.

The architecture should support the principle that execution mode is selected for workflow execution rather than being embedded into individual agent prompts.

The CTO should determine whether mode selection occurs:

* at project initialization
* at task creation
* at workflow start
* through project configuration
* through a runtime control mechanism

The design should also address whether changing execution mode during an active task is permitted.

If mode switching is supported, the design must specify safe transition rules.

For example:

```text
Manual → Automatic
Automatic → Manual
```

must preserve the exact current workflow state and must not reset, skip, or repeat engineering gates.

---

# 13. Failure and Rework Handling

Automatic Mode must preserve existing rejection and rework behavior.

For example:

```text
Reviewer requests changes
        ↓
PM detects transition condition
        ↓
Implementer receives rework
        ↓
Implementation
        ↓
G2
        ↓
Reviewer
        ↓
G3
```

The PM may coordinate this loop automatically, but it must not reinterpret the Reviewer or CTO decision.

The design must also define behavior for:

* missing artifacts
* invalid metadata
* failed handoffs
* agent failure
* timeout
* blocked task
* repeated review failure
* unavailable agent
* configuration error
* unexpected workflow state

---

# 14. Artifact and Audit Requirements

Automatic execution must remain fully auditable.

Every automated transition should be reconstructable from task artifacts and status records.

The design should determine what information is required to record:

* task ID
* workflow state
* previous state
* next state
* execution mode
* triggering event
* responsible agent
* approval/gate status
* timestamp
* artifact verification result
* failure/blocker information

Automatic Mode must not create an opaque workflow in which the user cannot determine why a transition occurred.

---

# 15. Backward Compatibility

The design MUST preserve the current DS-EO OpenClaw Edition behavior.

Existing Manual Mode workflows must continue to work without requiring users to adopt Automatic Mode.

The following must remain compatible:

* current agents
* current protocols
* current task artifacts
* current G1–G4 governance
* current PM responsibilities
* current installation model
* future platform portability

The implementation must not require modification of the OpenClaw source itself.

---

# 16. Platform Portability

The design must remain consistent with DS-EO's long-term goal of supporting multiple agent platforms.

Do not design the execution-mode architecture around OpenClaw-specific internals where a platform-neutral abstraction is possible.

The architecture should allow future editions such as:

```text
DS-EO Core
    │
    ├── OpenClaw Edition
    ├── Claude Edition
    ├── Codex Edition
    └── Gemini Edition
```

Execution mode should therefore be a DS-EO workflow concept, with platform-specific adapters implemented separately where necessary.

---

# 17. Scope

## In Scope

This task includes:

* current-state workflow analysis
* Manual Mode definition
* Automatic Mode definition
* PM orchestration model
* workflow state machine
* transition rules
* gate interaction
* human intervention model
* execution-mode configuration
* mode-switching rules
* failure/rework behavior
* auditability requirements
* implementation roadmap

## Out of Scope

This task does NOT require:

* full Automatic Mode implementation
* modification of OpenClaw source code
* replacement of existing protocols
* removal of Manual Mode
* bypassing G1–G4
* redesigning CTO/PM/Implementer/Reviewer responsibilities
* automatic architecture decisions
* automatic approval of engineering work
* platform-specific workflow implementation

Implementation may be proposed as a future task only after the architecture is approved.

---

# 18. Deliverables

The CTO shall determine the final artifact structure according to the current DS-EO task and artifact protocols.

The primary design deliverable should document:

```text
Current workflow
        ↓
Execution-mode architecture
        ↓
Manual Mode
        ↓
Automatic Mode
        ↓
PM orchestration
        ↓
State machine
        ↓
Transition rules
        ↓
Gate / approval behavior
        ↓
Configuration
        ↓
Failure / rework handling
        ↓
Auditability
        ↓
Implementation roadmap
```

The task must use the current DS-EO artifact conventions rather than the obsolete `docs/reports/TASK_DS_EO_003/` structure from the original task.

---

# 19. Constraints

1. Manual Mode MUST remain supported.
2. Automatic Mode MUST use the same engineering workflow as Manual Mode.
3. Execution mode MUST NOT change gate authority.
4. PM MUST NOT acquire CTO, Reviewer, or Implementer authority.
5. Automatic Mode MUST NOT bypass required approvals.
6. Automatic Mode MUST NOT infer approval from silence or timeout.
7. Existing protocols remain authoritative.
8. `GATE_AUTHORITY_MATRIX.md` remains authoritative for gate governance.
9. Existing artifact and metadata requirements remain mandatory.
10. The design must preserve the current PM role boundaries.
11. The design must preserve current rejection and rework loops.
12. The design must remain platform-portable.
13. No OpenClaw source modification is required.
14. Automatic execution implementation is not required in this task.

---

# 20. Acceptance Criteria

TASK_DS_EO_019 is complete when the CTO-approved design establishes:

### Execution Modes

* [ ] Manual Mode is accurately documented according to the current DS-EO implementation.
* [ ] Automatic Mode is formally defined.
* [ ] The distinction between execution strategy and engineering authority is explicit.

### Workflow

* [ ] The current PM → CTO → Implementer → Reviewer → CTO lifecycle is accurately represented.
* [ ] G1–G4 are incorporated without redefining their authority.
* [ ] A formal workflow state machine is specified.
* [ ] Every permitted transition has explicit prerequisites and outcomes.
* [ ] Rework and rejection loops are defined.

### PM

* [ ] PM orchestration responsibilities are defined.
* [ ] PM authority boundaries are explicitly preserved.
* [ ] Automatic Mode does not turn PM into an approval authority.

### Configuration

* [ ] Execution mode configuration is defined.
* [ ] Manual and Automatic are supported as initial execution modes.
* [ ] Mode selection timing is defined.
* [ ] Safe mode switching behavior is defined or explicitly deferred.

### Governance

* [ ] Human approval points are explicitly identified.
* [ ] Automatic Mode cannot bypass mandatory gates.
* [ ] Failure and stalled-work behavior is specified.
* [ ] Automated transitions are auditable.

### Implementation

* [ ] A phased implementation roadmap is provided.
* [ ] Architecture/design work is clearly separated from future implementation work.
* [ ] The CTO identifies the appropriate follow-up task(s) required to implement Automatic Mode.

---

# 21. Success Definition

DS-EO provides **one engineering organization, one engineering lifecycle, and one governance model**, with configurable execution strategies.

The user can choose:

```text
MANUAL
User controls workflow progression
```

or:

```text
AUTOMATIC
PM coordinates eligible workflow progression
```

without changing:

```text
Roles
Protocols
Artifacts
Gates
Authority
Review standards
Approval requirements
Rework rules
```

The fundamental design principle is:

> **Execution mode controls HOW the workflow progresses; it does not change WHAT the workflow requires or WHO has authority to decide.**

TASK_DS_EO_019 should therefore establish the architecture for workflow orchestration without prematurely implementing automation.
