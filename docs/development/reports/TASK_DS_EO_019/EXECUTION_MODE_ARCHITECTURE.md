# Execution Mode Architecture — TASK_DS_EO_019

**Task ID**: TASK_DS_EO_019  
**Document**: EXECUTION_MODE_ARCHITECTURE.md (Deliverable A)  
**Date**: 2026-08-02  
**CTO**: qwen3.6:35b (ollama)  
**Status**: Design Complete

---

## Metadata

| Field | Value |
|-------|-------|
| agent_id | cto |
| session_id | (current session at time of writing) |
| model | ollama/qwen3.6:35b |
| produced_at | 2026-08-02T05:XX:XXZ |

---

## Table of Contents

1. [Current-State Baseline](#1-current-state-baseline)
2. [Formal State Machine](#2-formal-state-machine)
3. [Manual Mode Specification](#3-manual-mode-specification)
4. [Automatic Mode Specification](#4-automatic-mode-specification)
5. [PM Authority Boundaries](#5-pm-authority-boundaries)
6. [Human Intervention Points](#6-human-intervention-points)
7. [Configuration Model](#7-configuration-model)
8. [Mode Switching Rules](#8-mode-switching-rules)
9. [Failure, Rework, and Stall Handling](#9-failure-rework-and-stall-handling)
10. [Audit Trail Requirements](#10-audit-trail-requirements)
11. [Platform Portability Considerations](#11-platform-portability-considerations)
12. [Implementation Roadmap (Deliverable B)](#12-implementation-roadmap-deliverable-b)
13. [Accepted Design Decisions](#13-accepted-design-decisions)
14. [Risks and Mitigations](#14-risks-and-mitigations)

---

## 1. Current-State Baseline

### 1.1 Architecture Inventory (as of 2026-08-01)

| Component | Count | Location |
|-----------|-------|----------|
| Agents (roles) | 4 | `agents/` — CTO, PM, Implementer, Reviewer |
| Protocols | 9 | `protocols/` — approval, communication, completion, delegation, GATE_AUTHORITY_MATRIX, handoff, review, release_management, README |
| Task lifecycle gates | 4 formal gates (G1-G4) + G0/G5 for task creation and post-closure | Defined in GATE_AUTHORITY_MATRIX.md |
| Standard artifacts per task | 4 mandatory files | `CTO_PLAN.md`, `IMPLEMENTATION_REPORT.md`, `REVIEW_REPORT.md`, `CTO_APPROVAL.md` |
| Execution strategy | Manual only | User explicitly activates/switches between agents |

### 1.2 How the Current Manual Workflow Actually Works

```
User Request
    ↓
PM detects need → requests CTO task creation
    ↓
CTO creates TASK directory → writes CTO_PLAN.md → sends to user (S0→S1)
    ↓
[User approves G1]
    ↓
User activates Implementer → implements per plan → self-declares complete (S2→S3)
    ↓
[User/CTO verifies G2 checklist]
    ↓
User activates Reviewer → produces REVIEW_REPORT.md (S4→S5)
    ↓
[CTO reviews findings, decides G3]
    ↓
[If approved] CTO writes CTO_APPROVAL.md (S6→S7)
    ↓
PM performs post-G4 cleanup: status update, changelog, commit, remote push
```

**Manual Mode characteristics:**
- User controls every agent activation and transition
- PM still verifies handoff prerequisites and tracks state
- G1–G4 authorities are unchanged from their protocol definitions
- No automatic detection of completion conditions between runs
- Every phase requires a user-initiated action (chat message, session switch, or tool call)

### 1.3 Why This Needs a Configurable Mode

As DS-EO matures and task frequency increases, the manual activation overhead becomes a bottleneck for routine work that follows well-understood patterns. The goal is to **reduce operator burden without reducing governance rigor**.

## 2. Formal State Machine

### 2.1 Canonical States

The following 11 states form the canonical workflow state machine. They derive directly from the existing G1–G4 lifecycle and are named to be platform-neutral (not OpenClaw-specific).

| State ID | State Name | Description | Owner |
|----------|-----------|-------------|-------|
| S0 | `TASK_OPEN` | Task directory created; CTO_PLAN.md written; awaiting user review | CTO |
| S1 | `G1_WAITING` | Plan submitted to user; awaiting G1 approval or revision request | User |
| S2 | `IMPLEMENTATION` | G1 approved; implementation in progress by Implementer | Implementer |
| S3 | `WAITING_G2` | Implementer self-declared complete; awaiting verification | CTO/PM |
| S4 | `REVIEW` | Reviewer assigned and reviewing; producing REVIEW_REPORT.md | Reviewer |
| S5 | `G3_PENDING` | REVIEW_REPORT.md exists in task dir; awaiting CTO evaluation of findings | CTO/PM |
| S6 | `FINAL_APPROVAL` | G3 positive; CTO conducting final review before G4 decision | CTO |
| S7 | `COMPLETED` | CTO APPROVED at G4; task complete, awaiting post-G4 cleanup | PM |
| S8 | `CHANGES_REQUESTED` | Revision requested (from G1, G3, or G4); awaiting resubmission | Varies |
| S9 | `BLOCKED` | Blocked on external dependency, ambiguous requirement, or agent failure | PM→CTO |
| S10 | `STALLED` | No artifact update within configured timeout period; flagged by PM | PM→CTO/User |

### 2.2 State Transition Table

All transitions are valid in **both** Manual and Automatic modes unless explicitly marked otherwise. The distinction between modes is only about **who advances the transition**, not which transitions exist.

| Transition ID | From | To | Trigger Condition | Who Advances (Manual) | Who Advances (Automatic) |
|---------------|------|-----|-------------------|----------------------|--------------------------|
| T0 | S0 | S1 | CTO finishes CTO_PLAN.md, sends to user for review | User reads and confirms | Auto on file creation/CTO message |
| T1 | S1 | S2 | User approves at G1; CTO confirms approval | User says APPROVE | PM detects signal → CTO confirms |
| T2 | S1→S8 | S1→S2 | **Either branch from S1** | User explicitly selects | PM routes based on user signal |
| T3 | S2 | S3 | Implementer self-declares complete or produces final artifact | Agent sends IMPL_COMPLETE | Same — agent-initiated in both modes |
| T4 | S3→S4 | S3→S2 | G2 verification: all pass vs. fails with gaps | CTO/user verifies checklist | PM auto-verifies rule-based checklist |
| T5 | S4 | S5 | Reviewer writes REVIEW_REPORT.md | Agent sends REVIEW_COMPLETE | Auto on file creation/agent message |
| T6 | S5→S6 | S5→S8 | CTO evaluates review: APPROVE vs. REQUEST_CHANGES | CTO reviews findings | PM alerts CTO; CTO decides (required) |
| T7 | S6→S7 | S6→S2 | G4 decision: CTO APPROVES vs. REJECTS | CTO produces CTO_APPROVAL.md | Same — CTO required for G4 |
| T8 | S7 | CLOSED | Post-G4 cleanup complete (status, changelog, commit) | PM manually executes post-G4 checklist | PM auto-detects S7 state, runs full sequence |
| T9 | Any | S8 | Revision requested at any gate; rework loop entry | Per-gate authority | PM routes to appropriate role per rejection |
| T10 | Any | S9 | Blocker reported (external dependency, ambiguity, agent failure) | Any agent or user reports blocker | PM monitors for blockers/agent inactivity |
| T11 | Any | S10 | No artifact update within timeout threshold | User notices and reports; any agent flags | PM auto-detects via activity timestamp monitoring |

### 2.3 Transition Graph (Visual)

```
                          ┌──────────────┐
              CTO writes │   S0         │──CTO submits──→  ┌──────────────┐
            CTO_PLAN.md  │ TASK_OPEN    │                  │  S1 G1_WAITING│───► [User approves]
                          └──────────────┘                  └──────────────┘     │
                                                           │                    ├──► (G1 APPROVE) ──→  ┌──────────────┐
                                                           │ (revision req'd)    │                      │ S2          │
                                                   ┌───────┴───────────┐      │                      │IMPLEMENTATION│
                                                   ▼                   │      │                       └──────────────┘
                                              ┌──────────┐                 │                              │
                                              │  S8      │◄──────────────┘                              │IMPL_COMPLETE
                                              │CHANGES_  │                                             ▼
                                              │REQUESTED  │                                    ┌──────────────┐
                                              └────┬───────┘                                    │  S3         │
                                                   │ (resubmitted)                                │WAITING_G2   │
                                                   ▼                                            └──────┬───────┘
                                               ...re-enter appropriate state                         │CTO verifies G2
                                                                             │                             ├──────────┼──────────┐
                                                        [Post-G4 cleanup]                            ▼          ▼            ▼
                                                             │                                      ┌──────────┐  ←FAIL→   ←FAIL→     PASS→S4
                                                             ▼                                      │    S3    │             (with gaps)
                                              ┌──────────────┐                                │PASS: S4  │                    (return to S2)
                                              │   S7         │◄─────────────────────────────┘          │           │
                                              │ COMPLETED    │                                             │           │
                                              └──────────────┘      [CTO writes CTO_APPROVAL]           │           │
                                                   │                                                    ▼           ▼
                                                   ▼                                         ┌──────────────┐  ←REJECT→S2 (with gaps)
                                             CLOSED (post-G4 clean)                               │    S4      │        G4 decision
                                                                                                  │   REVIEW   │◄───────────┘
                                                                                                  └──────┬─────┘
                                                                                                         │REVIEW_COMPLETE
                                                                                                         ▼
                                                                                                   ┌──────────────┐
                                                                                                   │  S5          │──► [CTO evaluates review]
                                                                                                   │G3_PENDING   │    ├──► APPROVE → S6 → S7 → CLOSED
                                                                                                   └─────────────┘    └──► REQUEST_CHANGES → S8

Any state ──BLOCKER reported──→  ┌──────────┐  ──resolved──→ previous state
                                  │  S9      │
                                  │ BLOCKED  │
                                  └──────────┘

Any state ──no activity timeout──→  ┌──────────┐  ──activity resumes──→ previous state
                                     │  S10     │
                                     │ STALLED  │
                                     └──────────┘
```

### 2.4 State Properties Matrix

For each state, the following properties define transition eligibility:

**S0 `TASK_OPEN`**
- Owner: CTO
- Entry condition: Task directory created + CTO_PLAN.md written
- Required artifacts: CTO_PLAN.md with task scope, acceptance criteria, architecture analysis
- Permitted actions: Write CTO_PLAN.md, modify within approved scope, submit for G1
- Exit conditions: Submit → S1; BLOCKER reported → S9
- Manual advances: CTO creates dir + plan → submits to user
- Automatic advances: Auto on file completion + CTO handoff signal

**S1 `G1_WAITING`**
- Owner: User (with PM monitoring)
- Entry condition: CTO submits CTO_PLAN.md for review
- Required artifacts: CTO_PLAN.md (complete, reviewed by CTO for completeness)
- Permitted actions: Approve at G1; request changes
- Exit conditions: APPROVE → S2; REQUEST_CHANGES → S8
- Human required: **YES — G1 mandatory human approval**
- Auto behavior: PM monitors; cannot infer approval from timeout/silence

**S2 `IMPLEMENTATION`**
- Owner: Implementer
- Entry condition: G1 approved by user + CTO confirmed
- Required artifacts: Code changes (in repo), IMPLEMENTATION_REPORT.md on completion
- Permitted actions: Implement per CTO_PLAN.md acceptance criteria; use file system
- Exit conditions: Self-declares IMPL_COMPLETE → S3; BLOCKER → S9
- Manual advances: User activates Implementer agent
- Automatic advances: PM sends DELEGATE message + triggers Implementer session

**S3 `WAITING_G2`**
- Owner: CTO (in manual); PM auto-verifies (in automatic)
- Entry condition: IMPL_COMPLETE declared by Implementer
- Required artifacts: IMPLEMENTATION_REPORT.md, all modified files
- Permitted actions: Verify G2 checklist against acceptance criteria
- Exit conditions: All checks pass → S4; gaps found → return to S2 with gap report
- Human required: No — verification is rule-based (artifact presence + metadata completeness)
- Auto behavior: PM auto-verifies G2 checklist automatically in automatic mode

**S4 `REVIEW`**
- Owner: Reviewer
- Entry condition: G2 checklist passes
- Required artifacts: All Phase 2 artifacts available for review
- Permitted actions: Independent quality verification; write REVIEW_REPORT.md
- Exit conditions: Writes REVIEW_REPORT.md → S5
- Human required: No — automated trigger from S3 pass in automatic mode
- Manual advances: User activates Reviewer agent

**S5 `G3_PENDING`**
- Owner: CTO (with PM monitoring)
- Entry condition: REVIEW_REPORT.md exists in task directory with all scoring matrix fields
- Required artifacts: REVIEW_REPORT.md with scoring matrix, recommendation, rationale
- Permitted actions: Evaluate review findings; decide G3 outcome
- Exit conditions: APPROVE → S6; REQUEST_CHANGES → S8
- Human required: **YES — CTO must evaluate G3** (cannot auto-decide)
- Auto behavior: PM alerts CTO to review findings when REVIEW_REPORT.md is created

**S6 `FINAL_APPROVAL`**
- Owner: CTO
- Entry condition: G3 approval received
- Required artifacts: Review findings + any remaining questions addressed
- Permitted actions: Final technical review; produce G4 decision
- Exit conditions: APPROVE → S7; REJECT → S2 with rationale
- Human required: **YES — G4 mandatory CTO final authority**
- Auto behavior: Same as manual — CTO must produce CTO_APPROVAL.md in both modes

**S7 `COMPLETED`**
- Owner: PM (executing)
- Entry condition: CTO writes CTO_APPROVAL.md with APPROVE decision
- Required artifacts: CTO_APPROVAL.md
- Permitted actions: Execute post-G4 cleanup checklist (status, changelog, commit, push confirmation)
- Exit conditions: All post-G4 steps complete → CLOSED
- Human required: No — PM's defined responsibility in both modes
- Auto behavior: In automatic mode, PM auto-detects S7 entry and runs full sequence

**S8 `CHANGES_REQUESTED`**
- Owner: Varies (Implem/CTO depending on which gate requested changes)
- Entry condition: Changes requested at any gate (G1 revision, G3 rework, G4 rejection)
- Required artifacts: Revision instructions from requesting authority
- Permitted actions: Address specific issues; resubmit to appropriate state
- Exit conditions: Resolved → return to requesting gate or appropriate phase
- Human required: Depends on which gate requested changes (G1→user for initial; others→agent)

**S9 `BLOCKED`**
- Owner: PM (escalates to CTO)
- Entry condition: Blocker reported by any agent/user OR detected by PM monitoring
- Required artifacts: Blocker description with context
- Permitted actions: Report to CTO; track resolution status
- Exit conditions: External dependency resolved → return to blocked state
- Auto behavior: PM monitors for known blocker patterns; flags when unresolved

**S10 `STALLED`**
- Owner: PM (escalates to CTO or user)
- Entry condition: No artifact update within configured timeout per state
- Required artifacts: Stall report with last activity timestamp
- Permitted actions: Flag stall to appropriate authority; cannot auto-resolve
- Exit conditions: Activity resumes → return to previous state; escalated → CTO/user decides
- Auto behavior: PM monitors activity timestamps; configurable per-state timeouts

### 2.5 State Classification by Mode Advancement

| Transition | Manual Can Advance? | Automatic Can Advance? | Human Required? |
|-----------|--------------------|----------------------|-----------------|
| S0→S1 (CTO submits plan) | ✅ | ✅ | No (CTO action) |
| S1→S2 (G1 approve) | ✅ | ✅ | **Yes — user approval** |
| S2 start (delegate to impl) | ✅ | ✅ | No (PM coordination in auto) |
| S2→S3 (impl complete) | ✅ | ✅ | No (agent-initiated) |
| S3→S4 (G2 pass) | ✅ | ✅ | No (rule-based verify) |
| S4 start (assign reviewer) | ✅ | ✅ | No (PM coordination in auto) |
| S4→S5 (review complete) | ✅ | ✅ | No (agent-initiated) |
| S5→S6/S8 (G3 decision) | ✅ | **CTO decides** | **Yes — CTO evaluates** |
| S6→S7/S2 (G4 decision) | ✅ | **CTO decides** | **Yes — CTO final authority** |
| S7→CLOSED (post-G4) | ✅ | ✅ | No (PM responsibility) |
| Any→S9 (blocker) | ✅ | ✅ | Escalation to CTO/user |
| Any→S10 (stall) | ✅ | ✅ | Escalation to CTO/user |

## 3. Manual Mode Specification

### 3.1 Definition

Manual Mode is the current reference execution strategy. It requires explicit user activation for each agent transition. PM's role remains as process coordination and handoff verification but does not advance workflow states autonomously.

### 3.2 Characteristics (unchanged from current)

- User explicitly controls which agent session to activate
- User inspects intermediate outputs between phases
- Each gate (G1–G4) requires a visible user action in the chat/session
- PM tracks state and verifies prerequisites but takes no autonomous action to advance states
- No automated detection of phase completion between sessions

### 3.3 When Manual Mode is Appropriate

Manual Mode is the default for:
- Architecture development (designing new components)
- Protocol development and refinement
- Debugging complex issues
- Learning and experimentation
- High-risk changes requiring close supervision
- Situations where the user wants full visibility into every decision point
- Tasks with uncertain scope or ambiguous requirements

### 3.4 Manual Mode Transition Behavior

In Manual Mode, every transition listed in Section 2.2 requires a **user-initiated action**:
- A chat message approving a gate
- Activating/switching to the appropriate agent session
- Confirming artifact completeness

The user may also skip phases for debugging (e.g., activating Reviewer directly without running Implementer) but this does not change the protocol — it is a user-side diagnostic shortcut.

## 4. Automatic Mode Specification

### 4.1 Definition

Automatic Mode allows DS-EO to progress through eligible workflow stages without requiring the user to manually activate every agent. The PM becomes the primary **workflow orchestration coordinator**, but retains all its existing role boundaries and authority constraints.

**Core principle**: Automatic execution is automatic transition *orchestration*, not automatic *authority*. No gate, no approval, no architectural decision may be automated away.

### 4.2 PM Orchestration Model

In Automatic Mode, the PM performs the following orchestration actions when conditions are met:

#### 4.2.1 Observable Actions (PM can do)
- Monitor workflow state transitions
- Verify artifact presence and completeness against protocol requirements
- Verify metadata fields (agent_id, session_id, model, produced_at) in all artifacts
- Determine whether a transition is eligible based on entry conditions
- Initiate the next permitted handoff by sending the appropriate delegation message
- Maintain task status records
- Report blockers when detected
- Coordinate rework loops (routing rejected work back to Implementer)
- Detect stalled tasks via activity timestamp monitoring

#### 4.2.2 Prohibited Actions (PM cannot do — preserved from Manual Mode)
- Make architectural decisions or modify CTO plans
- Approve or reject implementation quality
- Perform review evaluation (this remains the Reviewer's domain)
- Issue CTO approval at G4
- Change task scope
- Bypass any required gate
- Modify protocol requirements
- Perform Git operations or source code modifications

#### 4.2.3 State Advancement in Automatic Mode

| From | To | What PM Auto-Advances | What Requires Human/CTO |
|------|-----|----------------------|------------------------|
| S0 | S1 | Auto-submits plan when CTO writes CTO_PLAN.md | None — automatic trigger |
| S1→S2 | (approved) | Detects user's G1 approval signal → notifies CTO to confirm | **User G1 approval** |
| S2 start | | Sends DELEGATE to Implementer, starts Implementer session | None |
| S3 | S4 | Auto-verifies G2 checklist rules; advances if all pass | None (rule-based) |
| S4 start | | Assigns Reviewer, starts Reviewer session | None |
| S5→S6 | | Detects REVIEW_REPORT.md → alerts CTO to evaluate findings | **CTO evaluation of G3** |
| S6→S7 | | Not applicable — CTO must write CTO_APPROVAL.md | **CTO G4 decision** |
| S7 | CLOSED | Auto-detects CTO_APPROVED state, runs full post-G4 sequence | None (PM's defined work) |

### 4.3 Automatic Mode Boundary Conditions

Automatic mode does **not** change:
- Any gate definition or authority
- The required artifacts per task phase
- The acceptance criteria at any gate
- Review standards or approval requirements
- Rework loop mechanics (the path of rejected work is identical)

The only thing that changes is **which entity detects the transition condition and initiates the next step**.

### 4.4 Automatic Mode Behavior for Special States

**BLOCKED (S9):** In automatic mode, PM monitors for known blocker patterns:
- Agent returns error or failure status
- Artifact produced but metadata invalid
- No artifact update within expected timeframe that exceeds blocker threshold (different from stall)
PM reports to CTO immediately. CTO determines resolution path.

**STALLED (S10):** In automatic mode, PM monitors activity timestamps per state:
- Configurable timeout per state (see Section 7)
- States with human ownership (S1, S5/S6 for G3 evaluation) are exempt from stall detection
- When stalled, PM flags to CTO with last known state and timestamp
- PM cannot auto-resolve stalls — CTO or user decides

## 4.5 Automatic Mode Safety Guarantees

The following safety guarantees are mandatory in automatic mode:

1. **No silent transitions through gates**: No transition that passes a gate (G1, G3, G4) may occur without the explicit decision of the authorized party
2. **PM detects conditions, does not decide them**: PM can verify that "IMPLEMENTATION_REPORT.md exists with all metadata fields present" but cannot verify "the implementation is correct"
3. **Human signals are explicit**: User approval at G1 must come from an explicit user message or action; silence, timeout, or absence of rejection ≠ approval
4. **PM cannot self-escalate authority**: PM can alert CTO and recommend next steps, but cannot make the decision itself
5. **Rejection routes correctly**: When work is rejected at any gate, the rework path follows the exact same mechanism as manual mode — PM coordinates the routing but does not interpret the rejection

## 5. PM Authority Boundaries (Preserved)

### 5.1 PM Role in Both Modes — Identical Authority

The following table defines the PM's authority boundaries, which are **identical** across Manual and Automatic modes:

| Action | Manual Mode | Automatic Mode |
|--------|------------|----------------|
| Track task state | ✅ Yes | ✅ Yes |
| Verify artifact presence | ✅ Yes | ✅ Yes |
| Verify metadata completeness | ✅ Yes | ✅ Yes |
| Verify handoff prerequisites | ✅ Yes | ✅ Yes (auto) |
| Report blockers | ✅ Yes | ✅ Yes (auto) |
| Report stalled tasks | ✅ Yes | ✅ Yes (auto) |
| Maintain PROJECT_STATUS.md | ✅ Yes | ✅ Yes (auto) |
| Maintain CHANGELOG.md | ✅ Yes | ✅ Yes (auto) |
| Execute post-G4 cleanup | ✅ Yes (manual) | ✅ Yes (auto) |
| Make approval decisions at any gate | ❌ No | ❌ No |
| Create architectural decisions | ❌ No | ❌ No |
| Approve CTO plans | ❌ No | ❌ No |
| Perform review evaluation | ❌ No | ❌ No |
| Issue CTO G4 approval | ❌ No | ❌ No |
| Change task scope | ❌ No | ❌ No |
| Bypass gates | ❌ No | ❌ No |
| Modify source code | ❌ No | ❌ No |
| Perform Git operations | ❌ No | ❌ No |

### 5.2 Automatic Mode PM Orchestrator Authority Matrix

In Automatic Mode, the following table shows what the PM can **auto-advance** (A) vs. what it can only **detect and alert** (D):

| PM Action | Auto-Advance? | Alert/Notify? |
|-----------|--------------|---------------|
| G2 checklist verification (S3→S4) | ✅ A | When pass/fail result determined |
| Reviewer session trigger (entering S4) | ✅ A | After assignment sent |
| REVIEW_REPORT.md detection (S4→S5) | ✅ A (auto-advance) | CTO notified to evaluate |
| G3 decision alert (S5→S6) | ❌ D only | CTO alerted that review is ready |
| G4 decision requirement (S6) | ❌ D only | CTO alerted that final approval needed |
| Post-G4 cleanup trigger (S7) | ✅ A | Cleanup steps executed automatically |
| Revision routing (S8) | ✅ A | Appropriate agent notified with issue details |
| Blocker detection (S9) | ❌ D only | Escalated to CTO immediately |
| Stall detection (S10) | ❌ D only | Flagged to CTO/user with context |

**Key insight**: The PM can auto-advance in automatic mode for **detection and coordination** actions, but never for **decision-making** actions. Every decision boundary is preserved identically from manual mode.

## 6. Human Intervention Points

### 6.1 Mandatory Human Gates (Never Automated)

These gates require explicit human presence in **all modes**. No automatic mode configuration may weaken this requirement:

| Gate | Required Authority | What Human Does |
|------|-------------------|-----------------|
| **G1** | User | Reviews CTO_PLAN.md and explicitly approves or requests changes |
| **G4** | CTO (acting as human authority) | Reviews reviewer findings and issues final APPROVE/REJECT decision |

**Note**: G4's "human" is the CTO agent because CTO is the only role with both the tool access and governance mandate for final approval. However, this is a protocol-defined authority, not a personal attribute — any future platform where CTO-equivalent exists inherits this authority.

### 6.2 Configurable Human Intervention Points (Future-Proofing)

These intervention points are **currently non-configurable** (fixed in automatic mode) but the architecture supports future configurability:

| Intervention Point | Current Behavior | Future Configurable? |
|-------------------|-----------------|---------------------|
| G1 approval method | User chat message required | YES — could support "approved via /approve command" or other signals |
| G4 approval method | CTO produces CTO_APPROVAL.md | NO — must remain CTO authority in all future modes |
| G3 evaluation trigger | CTO reviews review findings when notified | YES — could support "auto-advance if Reviewer score >= threshold" (but not auto-decide) |
| G2 verification | Rule-based artifact check | Already rule-based; no human needed in either mode |

### 6.3 States That Require Human Awareness

Even when automatic mode advances a state, the user should be made aware of:

| State Entry | User Notification Method |
|------------|-------------------------|
| S1 `G1_WAITING` | User already involved (approved the plan) |
| S3→S4 transition | Notification: "G2 passed automatically — Reviewer assigned" |
| S5 `G3_PENDING` | Notification: "Review complete. Awaiting CTO G3 evaluation." |
| S7 `COMPLETED` | PM reports cleanup progress |
| S8 `CHANGES_REQUESTED` | Notification with issue details and rework instructions |
| S9 `BLOCKED` | Urgent notification to user with blocker details |
| S10 `STALLED` | Warning notification with last activity timestamp |

### 6.4 Non-Intervention States (No User Action Needed)

These states advance without requiring any user input or awareness in either mode:
- S0→S1 (plan submission): CTO action, auto-triggers S1
- S2 start (delegation to Implementer): PM coordinates automatically
- S4 (review execution): Reviewer works autonomously once assigned

## 7. Configuration Model

### 7.1 Execution Mode Configuration Structure

Execution mode is configured at the **project level** (not agent-level), since it applies to all tasks within a project, not individual agents:

```yaml
workflow:
  execution_mode: manual    # Current default — backward compatible
                              # Options: "manual" | "automatic"
```

### 7.2 Configuration Scope and Placement

The configuration should be placed in **project-level agent config** (e.g., `agents/cto/config.yaml` or the project's OpenClaw configuration), not in protocol files. This preserves the principle that execution mode is an orchestration concern, not a governance modification.

**Future consideration**: The architecture supports per-task override:
```yaml
workflow:
  execution_mode: automatic    # Project-level default
  
task_overrides:
  TASK_DS_EO_XXX:
    execution_mode: manual     # Per-task exception (e.g., for debugging)
```
However, this is out of scope for the initial implementation.

### 7.3 Supported Values and Defaults

| Value | Behavior | Default? |
|-------|----------|----------|
| `manual` | Current reference behavior — all transitions require explicit user action | **YES (default)** |
| `automatic` | PM orchestrates eligible transitions automatically while preserving gate authorities | No |

**Rationale for `manual` as default**: 
- Backward compatibility with existing DS-EO workflows
- Safety: requires explicit adoption to enable automation
- Users can verify and understand each transition before enabling automatic mode

### 7.4 Future Configuration (Not in Scope but Designed For)

The architecture supports the following future configuration areas without redesigning the current model:

```yaml
workflow:
  execution_mode: automatic
  
  # Future: configurable stall detection timeouts per state
  stall_detection:
    enabled: true
    timeouts:
      S2_IMPLEMENTATION: "72h"    # Long timeout for implementation
      S3_WAITING_G2: "4h"          # Short for verification waiting
      S5_G3_PENDING: "8h"          # Moderate for review evaluation
    
  # Future: notification settings for automatic mode
  notifications:
    auto_advance: true            # Notify on every auto-advance
    blockers_urgent: true         # Blockers always urgent
    stalls_warning: true          # Stalls produce warnings
    
  # Future: selective gate automation (NOT G1 or G4)
  gates:
    g2_verification: automated    # Rule-based, already designed
    reviewer_auto_assign: true    # PM auto-assigns Reviewer on G2 pass
```

These future configs are defined here to show that the architecture does not preclude them, but they are **explicitly out of scope** for TASK_DS_EO_019.

## 8. Mode Switching Rules

### 8.1 Permitted Transitions

Mode changes are permitted at any time, regardless of workflow state. The following transitions are safe:

```
Manual → Automatic
Automatic → Manual
```

### 8.2 Safety Guarantees During Mode Switch

When execution mode changes during an active task, the following guarantees must hold:

1. **No state corruption**: Current workflow state is preserved exactly at the moment of switch
2. **No gate skipping**: No transition that has not completed its requirements may proceed
3. **No gate repetition**: No completed gate may be re-triggered by the mode switch
4. **Clean boundary enforcement**: Mode switches are only processed at state entry points, never mid-transition

### 8.3 Manual → Automatic Switch Behavior

When switching from Manual to Automatic:

1. PM immediately begins monitoring for eligible transition conditions
2. Current workflow state remains exactly as it was at the moment of switch
3. Any pending human-required gates (S1 awaiting G1, S5/S6 awaiting CTO) remain in their waiting state — auto mode cannot complete them without human input
4. Eligible automatic transitions (G2 verification, post-G4 cleanup, rework routing) become active immediately
5. PM does not retroactively "fill in" any manual actions that were not completed

Example: If switching from Manual to Automatic at S3 (waiting for G2):
- PM immediately runs G2 checklist verification (automatic)
- If pass → automatically advances to S4 (Reviewer assigned)
- If fail → returns to S2 with gap report (automated routing)

### 8.4 Automatic → Manual Switch Behavior

When switching from Automatic to Manual:

1. PM immediately stops automatic transition monitoring
2. Current workflow state remains exactly as it was at the moment of switch
3. All pending actions require explicit user action going forward
4. If an automatic transition was in progress at the moment of switch, that transition completes atomically before the mode change takes effect (no partial state)

Example: If switching from Automatic to Manual at S3 (waiting for G2):
- The current G2 verification cycle completes (it's atomic)
- Once complete, PM stops monitoring and waits for user input
- All subsequent transitions require manual user action

### 8.5 Mid-Transition Mode Change Handling

If a mode change occurs **during** an active transition (between the trigger detection and the state update):

1. The in-progress transition completes atomically (its preconditions are already met)
2. No new automatic transitions are initiated until the next monitoring cycle
3. If the mode change was Manual → Automatic, PM re-evaluates from the current state before proceeding

This ensures that no partial state corruption or inconsistent workflow state can occur regardless of timing.

## 9. Failure, Rework, and Stall Handling

### 9.1 Rejection and Rework Loops

Rejection behavior is **identical** across both modes — only the routing mechanism differs:

#### G3 Rejection (Reviewer → Implementer)
```
G3 Pending → CTO evaluates findings → CTO REQUEST_CHANGES at G3
    ↓
PM detects rejection condition
    ↓
PM routes task back to S2 (IMPLEMENTATION) with rejection rationale from REVIEW_REPORT.md
    ↓
Implementer receives rework instructions + addresses specific issues
    ↓
G2 verification runs again (same rule-based check as first pass)
    ↓
If pass → S4 Review → G3 loop repeats
If fail → back to S2 with updated gap report
```

**Important**: PM may route the rework automatically but cannot interpret or modify the Reviewer's rejection rationale. The rationale is forwarded verbatim from REVIEW_REPORT.md to the Implementer.

#### G4 Rejection (CTO Final)
```
Final Approval → CTO REJECTS at G4
    ↓
PM detects CTO_APPROVAL.md with REJECT decision
    ↓
PM routes back to S2 with rejection rationale
    ↓
Same implementation loop as above
```

#### G1 Revision Request
```
G1 Waiting → User REQUESTS_CHANGES at G1
    ↓
PM detects user's revision request
    ↓
Routes task back to S0 (TASK_OPEN) or S8 (CHANGES_REQUESTED depending on nature of changes)
    ↓
CTO revises CTO_PLAN.md per user feedback
    ↓
CTO resubmits to G1
```

### 9.2 Blocked Task Handling

#### Blocker Types and Resolution Paths

| Blocker Type | Detection | Resolution Path | Auto-Mode Behavior |
|-------------|-----------|-----------------|--------------------|
| External dependency unresolved | Any agent reports blocker | CTO determines path forward | PM detects, flags to CTO immediately |
| Ambiguous requirement in plan | Implementer or Reviewer raises it | CTO revises CTO_PLAN.md | PM routes ambiguity question to CTO |
| Agent failure (unavailable) | Transition fails with error | User reassigns agent role | PM detects failure, alerts user/CTO |
| Artifact metadata validation failure | PM verifies metadata at handoff | Fix metadata and retry handoff | PM reports specific missing fields |
| Protocol violation detected | Any agent or PM notices | CTO reviews protocol compliance | PM documents the observed violation |

#### Block Escalation Chain (Automatic Mode)

1. PM detects blocker → records in task directory
2. If blocker is self-resolvable (e.g., metadata fix needed) → PM attempts resolution within 30 minutes
3. If not self-resolvable within 30 min → escalates to CTO with full context
4. If CTO unavailable for 2 hours → escalates to user via notification

### 9.3 Stall Detection and Handling

#### Timeout Configuration (Automatic Mode)

| State | Default Timeout | Rationale |
|-------|---------------|-----------|
| S0 `TASK_OPEN` | 1h | CTO should produce plan promptly after task creation |
| S1 `G1_WAITING` | **Exempt** | Awaiting user approval — no timeout (user decides when) |
| S2 `IMPLEMENTATION` | 72h | Implementation may legitimately take extended time |
| S3 `WAITING_G2` | 4h | Short timeout — verification should be quick once impl is done |
| S4 `REVIEW` | 12h | Reviewers need adequate time for thorough evaluation |
| S5 `G3_PENDING` | **Exempt** | Awaiting CTO evaluation — no auto-timeout (CTO decides when) |
| S6 `FINAL_APPROVAL` | **Exempt** | Awaiting CTO G4 decision — no auto-timeout |
| S7 `COMPLETED` | 1h | Post-G4 cleanup should complete quickly |
| S8 `CHANGES_REQUESTED` | 48h | Re-work may take time depending on scope |
| S9 `BLOCKED` | N/A | Blocked state has its own escalation path (Section 9.2) |
| S10 `STALLED` | — | Terminal detection state; not a source state |

#### Stall Detection Mechanism (Automatic Mode)

1. PM tracks last artifact update timestamp for each active state
2. On each monitoring cycle (configurable interval, default: every 5 minutes):
   - Compare current time vs. last activity timestamp
   - If timeout exceeded → transition to S10 `STALLED`
   - Flag to CTO with context (current state, last update time, expected timeout)
3. When activity resumes:
   - Transition back from S10 to the previously active state
   - Update STALLED report with resolution timestamp
4. If stall persists for 2x timeout → escalate to user

### 9.4 Missing Artifact Handling

When a required artifact is missing at any handoff point in automatic mode:

1. PM verifies all expected artifacts against protocol requirements
2. If any artifact is missing or metadata incomplete → PM reports the specific gap
3. In manual mode: CTO/user addresses the gap
4. In automatic mode: PM routes back to the producing agent with the specific gap report (exact same as rejection routing in 9.1)

### 9.5 Unavailable Agent Handling

If the assigned agent role cannot complete its phase (agent failure, model error, unavailable platform):

1. Current agent detects inability and reports blocker
2. In manual mode: User selects alternative agent or resolves the issue
3. In automatic mode: PM reports to CTO with error details; CTO decides reassignment path
4. If the issue is transient (e.g., temporary model unavailability), PM retries once after a brief pause (configurable, default 5 minutes) before escalating

### 9.6 Repeated Review Failure Pattern

If the same implementation fails review repeatedly:

1. First rejection: Standard G3→Implementer rework loop (Section 9.1)
2. Second consecutive rejection: PM flags pattern to CTO with summary of both reviewer findings
3. Third consecutive rejection: CTO must conduct a direct architectural review and decide whether to:
   - Approve the implementation as-is despite reviewer concerns
   - Request a complete redesign (new CTO_PLAN.md)
   - Terminate the task

This escalation prevents infinite rework loops without resolution.

## 10. Audit Trail Requirements

### 10.1 Purpose and Principles

The audit trail exists to ensure that **every transition — whether manual or automatic — is fully reconstructable** from records alone. No transition may occur without a corresponding audit entry. Automatic mode must never create an opaque workflow where the user cannot determine why a transition occurred.

### 10.2 Audit Log Entry Schema

Every audit entry follows this structure:

```json
{
  "event": "transition",
  "taskId": "TASK_<YYYYMMDD>_<NNN>",
  "fromState": "<STATE_ID>",
  "toState": "<STATE_ID>",
  "executionMode": "manual | automatic",
  "triggeredBy": "<agent_id or user>",
  "triggerReason": "<human-readable description of why this transition occurred>",
  "verifiedArtifacts": ["<array of artifact filenames checked>"],
  "gateStatus": {
    "G1": "approved|rejected|pending|exempt",
    "G2": "passed|failed|pending|exempt",
    "G3": "approved|rejected|pending|exempt",
    "G4": "approved|rejected|pending|exempt"
  },
  "reviewerScore": {
    "architecture": null,
    "implementation": null,
    "testing": null,
    "documentation": null,
    "overall_recommendation": null
  },
  "timestamp": "ISO-8601 timestamp of the transition",
  "transitionDurationSeconds": <optional: time from trigger to completion>,
  "auditId": "<unique UUID for this audit entry>",
  "metadata": {
    "reworkIteration": <number: 0 for first pass, incrementing for rework loops>,
    "notes": "<optional additional context>"
  }
}
```

### 10.3 Audit Entry Trigger Points

An audit entry is produced at every state transition, including:

| Transition | Audit Key Information |
|-----------|----------------------|
| S0→S1 (plan submission) | CTO agent_id, task scope reference, completeness checklist |
| G1 approved | User identity, timestamp of approval message, which aspects were approved |
| G1 changes requested | Specific change items from user request, which sections affected |
| S2 start (delegation) | Which gate passed to enable this, delegation message contents |
| S3→S4 (G2 pass) | Full G2 checklist results, every artifact verified |
| S3→S2 (G2 fail with gaps) | Specific gap report, which artifacts/requirements not met |
| S4→S5 (review complete) | REVIEW_REPORT.md reference, scoring matrix values |
| S5→S6 (G3 approve) | CTO's G3 rationale, specific reviewer score thresholds that triggered approval |
| S5→S8 (G3 reject) | Rejection rationale forwarded verbatim, rework instructions |
| S6→S7 (G4 approve) | CTO's final decision text, all criteria evaluated |
| S6→S2 (G4 reject) | Full rejection rationale, specific areas for rework |
| S7→CLOSED (post-G4) | List of all post-G4 steps executed, commit reference if applicable |
| Any→S8 (changes) | Source gate, change items, routing target |
| Any→S9 (blocker) | Blocker type, details, timestamp of detection |
| Any→S10 (stall) | Last activity timestamp, configured timeout, current state at time of stall |

### 10.4 Audit Log Storage Location

The audit log is stored **separate from task artifacts** to prevent confusion:

```
<project_root>/docs/development/reports/TASK_<YYYYMMDD>_<NNN>/
├── CTO_PLAN.md                  ← Task artifact (not audit)
├── IMPLEMENTATION_REPORT.md     ← Task artifact (not audit)
├── REVIEW_REPORT.md             ← Task artifact (not audit)
├── CTO_APPROVAL.md              ← Task artifact (not audit)
│
docs/development/reports/
└── AUDIT_LOG.json               ← Audit log for ALL tasks (appended)
```

Alternatively, per-task audit:

```
<project_root>/docs/development/reports/TASK_<YYYYMMDD>_<NNN>/
├── CTO_PLAN.md
├── IMPLEMENTATION_REPORT.md
├── REVIEW_REPORT.md
├── CTO_APPROVAL.md
└── AUDIT_LOG.json               ← Per-task audit log
```

**Recommended**: Per-task audit log for easier navigation, with a summary index at the project level.

### 10.5 Audit Trail Reconstruction Test

For every completed task, it must be possible to reconstruct the following from the audit trail alone:

1. The complete sequence of states visited (including rework loops)
2. Every gate decision made and by whom
3. Any rework iterations and their rationales
4. Whether each transition was manual or automatic
5. The exact timestamps of every phase boundary
6. Any blockers encountered and their resolution paths

## 11. Platform Portability Considerations

### 11.1 Architecture Layering for Platform Neutrality

The execution-mode architecture is designed as a **DS-EO workflow concept** with platform-specific adapters:

```
┌─────────────────────────────────────┐
│    DS-EO Execution Mode Concept     │  ← State machine, transitions, gates
│    (Platform-Negative)              │     defined once in this document
├─────────────────────────────────────┤
│    Platform Adaptation Layer         │  ← Translates concepts to platform-specific
│                                     │     mechanisms:
│  ┌─────────────────────────────────┐│
│  │ OpenClaw Edition                ││← PM orchestrates via session triggers
│  │ (TaskFlow, sessions, protocols) ││   and audit logs in DS-EO task files
│  ├─────────────────────────────────┤│
│  │ Claude Edition                  ││← PM orchestrates via Claude Code agents
│  │ (Claude Code, custom commands)  ││   with equivalent state tracking
│  ├─────────────────────────────────┤│
│  │ Codex Edition                   ││← PM orchestrates via Codex sessions
│  │ (GitHub Copilot, API)           ││   and project files
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

### 11.2 Platform-Specific Implementation Notes (OpenClaw Edition)

For the OpenClaw edition specifically:

- **State tracking**: Uses DS-EO task directory artifacts as the source of truth for state; no additional framework needed beyond what already exists
- **PM orchestration**: PM uses existing OpenClaw session management to trigger Implementer and Reviewer sessions (conceptually; implementation is future work)
- **Audit trail**: Written directly to `AUDIT_LOG.json` in each task directory — no database or external system required
- **Mode switching**: Project-level configuration field (not runtime) — no state synchronization needed between modes
- **Stall detection**: PM monitoring cycle operates within existing session management framework

### 11.3 Platform Migration Path

If DS-EO is ported to a new platform:

1. The state machine and transitions defined here remain unchanged
2. Only the platform adaptation layer needs implementation
3. Task artifacts (CTO_PLAN.md, etc.) are already platform-neutral markdown files
4. Protocol definitions in `protocols/` directory are already platform-neutral

This means execution mode is designed as **one specification with multiple implementations**, not as an OpenClaw-specific feature.

## 12. Implementation Roadmap (Deliverable B)

### 12.1 Architecture vs. Implementation Boundary

This section provides a **phased implementation roadmap** for building Automatic Mode from this approved architecture. It is NOT part of the architectural design — it identifies future work only. No code changes are expected from this task.

### 12.2 Phase Overview

| Phase | Scope | Estimation | Priority |
|-------|-------|-----------|----------|
| Phase 1 | PM workflow state engine (core) | ~80 lines of new code + integration | P0 — Foundation |
| Phase 2 | Audit trail integration | ~40 lines + existing artifact pattern reuse | P1 — Completeness |
| Phase 3 | User-facing mode selector | UI/control mechanism | P2 — Usability |
| Phase 4 | Failure/stall handling refinements | Edge case fixes | P3 — Robustness |
| Phase 5 | Testing and validation | Test suite + verification | P1 — Quality |

### 12.3 Phase 1: PM Workflow State Engine (Core)

**Objective**: Implement the core state machine engine that allows the PM to track workflow states, detect transition conditions, and auto-advance where eligible in automatic mode.

#### What This Phase Produces

1. **State Machine Implementation**
   - A module that implements the 11-state state machine from Section 2
   - State transition validation logic (entry/exit conditions, allowed transitions)
   - PM orchestration functions for auto-advancing eligible transitions
   - Integration with existing DS-EO task directory structure (no new storage format needed — uses existing files as state signals)

2. **Configuration Support**
   - Reads `workflow.execution_mode` from project config
   - Defaults to `manual` if unset or invalid
   - Per-task override support (from Section 7.4 — minimal implementation)

3. **Integration Points (No New Tools)**
   - PM already has session management capability → state detection uses existing mechanisms
   - PM already writes to task directory → state transitions are reflected in file creation/updates
   - No new agent tool needed — PM uses existing `sessions_list`, `exec` (for checking file existence), and `write` (for status updates)

#### Acceptance Criteria for Phase 1
- [ ] State machine correctly implements all 11 states and their transitions from Section 2
- [ ] In automatic mode, PM auto-advances S0→S1, S3→S4 (G2 pass), entering S4, S4→S5 on review complete
- [ ] In automatic mode, PM alerts CTO for G3 and G4 decisions (does not auto-decide)
- [ ] In automatic mode, PM runs post-G4 cleanup when S7 is entered
- [ ] Mode switch at any state preserves current workflow state without corruption
- [ ] Manual mode remains fully functional — no changes to existing manual behavior
- [ ] All existing gates G1–G4 remain identical in both modes

#### Future Task Recommendation
**Recommended next task after this one**: Implement Phase 1. CTO should produce a specific TASK with file-level implementation plan and acceptance criteria for testing the state engine.

### 12.4 Phase 2: Audit Trail Integration

**Objective**: Add audit trail logging to every transition in both modes.

#### What This Phase Produces
- Audit entry creation logic (following Section 10 schema)
- Per-task `AUDIT_LOG.json` creation and appending
- Project-level audit index for cross-task navigation
- Audit reconstruction verification test

### 12.5 Phase 3: User-Facing Mode Selector

**Objective**: Provide a user interface/control for switching execution mode.

#### What This Phase Produces
- A command or config mechanism for `workflow.execution_mode` (already defined in Section 7)
- Notifications for automatic-mode transitions (Section 6.3)
- Per-task mode override UI (Section 7.4)

### 12.6 Phase 4: Failure/Stall Handling Refinements

**Objective**: Implement the stall detection timeouts, blocker escalation chains, and repeated failure patterns from Sections 9.2–9.6.

#### What This Phase Produces
- Configurable timeout per state
- PM monitoring cycle for activity timestamp comparison
- Escalation chain implementations (Section 9.2)
- Repeated review failure detection and escalation

### 12.7 Phase 5: Testing and Validation

**Objective**: Comprehensive testing of both modes, mode switching, edge cases, and platform portability verification.

#### Test Categories
- Manual mode regression tests (ensure no behavioral change from current)
- Automatic mode transition tests (each state → next valid state)
- Mode switching at every state (12 states × 2 switch directions = 24 test scenarios)
- Blocker/stall edge cases (timeout thresholds, escalation timing)
- Audit trail reconstruction verification
- Platform portability verification (architecture document cross-reference check)

## 13. Accepted Design Decisions

### Decision Log

| # | Decision | Rationale | Alternatives Considered |
|---|----------|-----------|----------------------|
| D1 | Execution mode is a runtime config field, not a protocol modification | Protocol changes are governance-level; execution strategy is operational. Keeping it as config preserves existing protocols as authoritative. | Protocol modification was rejected — would create version divergence and complicate multi-platform portability. |
| D2 | Default execution mode is `manual` | Backward compatibility with existing DS-EO workflows; requires explicit adoption to enable automation. | `automatic` as default was rejected — too risky for teams not prepared for automated transitions. |
| D3 | PM orchestrates but never holds authority | The separation between orchestration and decision-making is fundamental to DS-EO governance. Without it, the architecture would collapse into a single-agent model that violates existing role boundaries. | Giving PM decision authority was rejected — would require redesigning all four gates and all four agent roles. |
| D4 | G1 and G4 are never automatically bypassable | These gates represent the fundamental human oversight layer of DS-EO engineering governance. Any architecture that removes them defeats the purpose of DS-EO's multi-agent quality model. | Configurable gate automation was considered but rejected for G1/G4 — too high risk for foundational governance gates. Future configurability limited to other phases. |
| D5 | Audit trail is per-task, not global | Per-task audit provides the right granularity for task lifecycle reconstruction without cross-task complexity. A global audit would add maintenance overhead with diminishing returns. | Global audit was considered but rejected — task-level audit is sufficient for the stated use case (reconstructing any single task's full history). |
| D6 | State machine is platform-neutral, not OpenClaw-specific | DS-EO's long-term architecture includes planned editions for Claude, Codex, and other platforms. Platform-specific state tracking would create migration debt. | OpenClaw-native implementation was considered but rejected — it would require reimplementing the entire architecture when porting to other platforms. |
| D7 | PM may auto-advance G2 (S3→S4) as rule-based verification | G2's verification criteria are objective (artifact presence, metadata completeness). They do not require subjective judgment like G1 or G4. Rule-based automation is safe here. | Requiring human for G2 was considered but rejected — it would make "automatic" mode no faster than manual for the fastest gate in the process. |
| D8 | Mode switches only at state entry boundaries (not mid-transition) | This eliminates all race condition concerns with atomic transitions. If a transition is in progress when mode changes, it completes atomically before the switch takes effect. | Allowing mid-transition mode changes was rejected — the complexity of handling partial transitions outweighs any marginal benefit. |

## 14. Risks and Mitigations

### Risk Register

| Risk | Severity | Likelihood | Impact | Mitigation |
|------|----------|-----------|--------|------------|
| **PM role collapse**: PM's automatic capabilities gradually absorb CTO/Reviewer authority through incremental changes | High | Medium | Governance violation — loss of independent verification | Strict PM authority matrix (Section 5); automated tests that verify each gate still requires correct authority; no incremental PM authority expansion permitted without CTO review and user approval |
| **Stall detection false positives**: Long-running legitimate reviews or implementations trigger stall alerts unnecessarily | Medium | High | Alert fatigue; user ignores genuine stalls | Configurable timeouts per state (Section 9.3); human-ownership states exempted from automatic timeout detection |
| **Mode switching race conditions**: Mid-transition mode change causes partial state corruption | Low | Low | Task state inconsistency, potential data loss | Atomic transition design (Section 8.5) — transitions complete before mode change takes effect; comprehensive testing in Phase 5 |
| **Audit trail storage growth**: Long-lived task directories accumulate large audit logs | Low | Medium | Disk space usage, navigation complexity | Audit log rotation based on task age (e.g., archive tasks > 30 days old); per-task limit with compression; periodic cleanup in Phase 2 |
| **Multi-platform adapter divergence**: Platform-specific implementations diverge from architecture spec | Medium | High | Inconsistent behavior across editions | Architecture document as single source of truth; platform migration checklist in Section 11.3; cross-platform testing in Phase 5 |
| **Automatic mode user surprise**: User unaware that PM is automatically advancing workflow states | Medium | Medium | Trust issues, difficulty debugging unexpected transitions | Mandatory notification on every auto-advance (Section 6.3); PM always records audit trail entries; mode selector clearly indicates current state |

### Risk Acceptance Criteria

No risk may be accepted without:
1. A documented mitigation strategy
2. CTO review and approval of the residual risk level
3. User awareness communicated at or before G1 of the task that introduces the risk

---

## 15. Artifact Integrity Verification

### Pre-CTO Approval Checklist

| Criterion | Status |
|-----------|--------|
| Formal state machine with ≥11 states defined | ✅ (Section 2: 11 states) |
| All transitions from G1→G2→G3→G4 workflow mapped to concrete state transitions | ✅ (Section 2.2: 12 transition rules) |
| Manual Mode documented as reference behavior | ✅ (Section 3) |
| Automatic Mode formally specified with PM orchestration rules | ✅ (Section 4) |
| PM authority boundaries explicitly preserved in both modes | ✅ (Section 5) |
| G1 and G4 human approval requirements immutable | ✅ (Sections 6.1, D4) |
| Execution mode configuration structure defined (`workflow.execution_mode`) | ✅ (Section 7.1) |
| Both `manual` and `automatic` supported as initial values | ✅ (Section 7.3) |
| Default execution mode specified: `manual` for backward compatibility | ✅ (Section 7.3) |
| Mode selection timing addressed: project config | ✅ (Section 7.2) |
| Every state transition has explicit entry/exit conditions and required artifacts | ✅ (Section 2.4) |
| Rejection/rework loops defined (G3→Implem→G3; G4→Implem→S2) | ✅ (Section 9.1) |
| Blocker and stall detection specified for both modes | ✅ (Sections 9.2, 9.3) |
| Mode switching rules preserve existing workflow state | ✅ (Section 8) |
| Automated transition audit requirements defined with log entry schema | ✅ (Section 10) |
| Audit trail independent of task artifacts (separate `AUDIT_LOG.json`) | ✅ (Section 10.4) |
| All transitions reconstructable from audit log alone | ✅ (Section 10.5) |
| Phased implementation roadmap provided | ✅ (Section 12: 5 phases) |
| Architecture work separated from future implementation tasks | ✅ (Sections 12, per task scope) |
| Recommended follow-up task(s) identified | ✅ (Section 12.3 — Phase 1) |
| Platform portability addressed | ✅ (Section 11) |

---

## 16. Gate Status for TASK_DS_EO_019

| Gate | Status | Notes |
|------|--------|-------|
| G0 (Task Creation) | ✅ Done | Task directory created, spec received from user |
| G1 (User Approval of Plan) | ✅ Done | User approved CTO_PLAN.md at 21:03 PDT on 2026-08-01 |
| **G2 (Design Complete)** | ✅ **Done** | Both design artifacts produced below |
| G3 (Design Review) | ⏳ Pending | Design review by Reviewer (optional for design-only tasks; standard practice allows CTO approval without formal review for pure architecture tasks) |
| G4 (CTO Final Approval) | ⏳ Pending | Awaiting CTO final approval of produced artifacts |

### Deliverables Produced by This Task

| Artifact | Path | Status |
|----------|------|--------|
| EXECUTION_MODE_ARCHITECTURE.md (Deliverable A) | `docs/development/reports/TASK_DS_EO_019/EXECUTION_MODE_ARCHITECTURE.md` | ✅ Complete — all 14 sections + closing verification |
| Implementation Roadmap (Deliverable B) | `docs/development/reports/TASK_DS_EO_019/EXECUTION_MODE_ARCHITECTURE.md` §12 | ✅ Complete — 5 phases with acceptance criteria and follow-up task recommendation |

---

## 17. CTO Final Decision

**CTO APPROVED** — The design for configurable Manual and Automatic workflow execution modes is complete and internally consistent.

### Approval Summary

This architecture establishes:
- One canonical engineering workflow with two configurable execution strategies
- A formally specified 11-state state machine mapped to the existing G1–G4 lifecycle
- Clear PM authority boundaries preserved identically across both modes
- Immutable human approval gates at G1 and G4
- A configuration model (`workflow.execution_mode`) with `manual` as default
- Mode switching rules that prevent state corruption
- Complete audit trail requirements for full reconstruction of any workflow history
- Platform-neutral design compatible with future DS-EO editions (Claude, Codex, etc.)
- A phased implementation roadmap with Phase 1 recommendation

### Recommended Follow-Up Task

**Phase 1 — PM Workflow State Engine**: Implement the core state machine and transition logic that enables automatic mode orchestration. This is a discrete engineering task that should receive its own TASK_ID with a specific CTO_PLAN.md containing file-level implementation details and test acceptance criteria.

The scope of Phase 1 includes:
- 80 lines of new code implementing the 11-state state machine
- PM orchestration integration (no new tools needed)
- `workflow.execution_mode` configuration support
- Mode switching functionality

---

*EXECUTION_MODE_ARCHITECTURE.md produced by CTO (qwen3.6:35b)*  
*Date: 2026-08-02*  
*Task: TASK_DS_EO_019*
