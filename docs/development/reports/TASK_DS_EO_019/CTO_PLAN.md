# CTO Plan — TASK_DS_EO_019

**Task ID**: TASK_DS_EO_019  
**Title**: Design Configurable Manual and Automatic Workflow Execution Modes  
**Date**: 2026-08-01  
**CTO**: qwen3.6:35b (ollama)  

---

## 1. Problem Statement

DS-EO currently operates in a single **Manual Mode**: workflow progression requires explicit user activation and transition between agents (PM → CTO → Implementer → Reviewer → CTO). As the organization matures, the user needs to be able to select an **Automatic Mode** where the PM coordinates eligible transitions automatically — without changing any engineering protocol, gate authority, or governance requirements.

This task is a **design-only task**. It produces architecture and design artifacts; no implementation work. The objective is one engineering workflow with configurable execution strategy, not two parallel processes.

## 2. Current-State Analysis

### 2.1 Existing Architecture (as of 2026-08-01)

The DS-EO OpenClaw Edition currently has:

- **Four agents**: CTO (architecture/planning), Implementer (code changes), Reviewer (quality verification), PM (process coordination). All defined in `agents/`.
- **Eight protocols**: approval_protocol, communication_protocol, completion_protocol, delegation_protocol, GATE_AUTHORITY_MATRIX, handoff_protocol, review_protocol, release_management_protocol — all in `protocols/`.
- **Four formal gates**: G1 (User approves plan), G2 (Implementation complete verified), G3 (Reviewer evaluates/recommends), G4 (CTO final approval). Authority is codified in GATE_AUTHORITY_MATRIX.md.
- **Task lifecycle**: `docs/development/reports/TASK_<YYYYMMDD>_<NNN>/` with standardized artifacts: CTO_PLAN.md, IMPLEMENTATION_REPORT.md, REVIEW_REPORT.md, CTO_APPROVAL.md.
- **PM role**: Process coordination only — tracks state, verifies handoffs, maintains PROJECT_STATUS.md and CHANGELOG.md. No approval authority, no Git operations, no code changes. Tool policy explicitly denies exec/process.
- **Delegation flow** (per delegation_protocol.md): PM detects need → requests CTO to create task → CTO creates dir + assigns ID → user approves (G1) → CTO delegates to Implementer.
- **Artifact metadata requirement**: All artifacts must carry agent_id, session_id, model, produced_at fields (TASK_DS_EO_006 pattern).

### 2.2 What the Current Manual Mode Actually Does

In the current manual mode:
- The user reads CTO_PLAN.md → approves at G1
- The user manually activates/switches to the Implementer agent
- Implementer works → self-declares complete at G2
- User or system triggers Reviewer → produces REVIEW_REPORT.md at G3
- CTO reviews Reviewer's report → makes final decision at G4
- PM performs post-G4 cleanup (status update, changelog, commit)

The "manual" aspect is specifically about **agent activation and transition** — not about any engineering requirement being relaxed.

### 2.3 Key Constraints from Current Protocols

From reviewing current protocols against the TASK_DS_EO_019 spec:

1. **PM cannot execute code or Git** (agents/pm.md, delegation_protocol.md) — this is critical for how automatic coordination works
2. **PM must never make approval decisions** (agents/pm.md) — automatic mode cannot bypass G1/G4 human gates
3. **All four artifacts (CTO_PLAN, IMPLEMENTATION_REPORT, REVIEW_REPORT, CTO_APPROVAL) are mandatory** in every task directory
4. **G3 iteration is supported**: Review can loop back to Implementer multiple times without re-entering G2
5. **Post-G4 cleanup is PM's responsibility** — status update, changelog, commit, remote push confirmation
6. **Stall detection exists** (handoff_protocol.md §Transition 0a) — relevant for automatic mode timeout handling
7. **Platform portability** is an existing design goal (ds-eo-openclaw package is the source of truth; deployment adapts per platform)

### 2.4 Tasks with Relevance to This Design

- **TASK_DS_EO_003** (CLOSED): Original concept that introduced manual/automatic mode thinking — superseded by current architecture
- **TASK_DS_EO_005** (ACTIVE): May contain relevant PM workflow state analysis
- **TASK_DS_EO_007** (CLOSED): May have protocol refinements relevant to execution modes
- **TASK_DS_EO_018** (CLOSED): Latest completed task — review for any new patterns

## 3. Proposed Design: Workflow State Machine

### 3.1 Canonical States

Based on the current lifecycle, I define the following canonical states for the workflow:

| State ID | State Name | Description |
|----------|-----------|-------------|
| S0 | `TASK_OPEN` | Task created; awaiting planning (CTO has written CTO_PLAN.md, awaiting user G1) |
| S1 | `G1_WAITING` | Plan submitted to user; awaiting G1 approval/revision request |
| S2 | `IMPLEMENTATION` | User approved at G1; implementation in progress |
| S3 | `WAITING_G2` | Implementer has declared complete; awaiting CTO confirmation |
| S4 | `REVIEW` | Review in progress by Reviewer |
| S5 | `G3_PENDING` | Review completed; REVIEW_REPORT.md produced; awaiting CTO G3 confirmation |
| S6 | `FINAL_APPROVAL` | CTO reviewing review findings; preparing G4 decision |
| S7 | `COMPLETED` | CTO approved at G4; task complete |
| S8 | `CHANGES_REQUESTED` | Either G1 revision requested, or rework loop from Reviewer (G3) |
| S9 | `BLOCKED` | Blocked on external dependency, unresolved ambiguity, or agent failure |
| S10 | `STALLED` | No progress detected within expected timeframe; PM has flagged stall |

### 3.2 State Owner Matrix

| State | Owner | Entry Condition | Exit Condition |
|-------|-------|-----------------|---------------|
| S0 `TASK_OPEN` | CTO | Task directory created + CTO_PLAN.md written (design-only task) | CTO submits for user review → S1 |
| S1 `G1_WAITING` | User | CTO_SUBMIT message sent with CTO_PLAN.md | User APPROVES → S2; USER_REQUESTS_CHANGES → S8 |
| S2 `IMPLEMENTATION` | Implementer | G1 approved, DELEGATE received | IMPL_COMPLETE declared → S3 |
| S3 `WAITING_G2` | CTO | Implementation complete declaration received | CTO verifies G2 checklist → PASS: S4; FAIL: S2 (return to Implementer with gaps) |
| S4 `REVIEW` | Reviewer | REVIEWER_ASSIGN message + all Phase 2 artifacts | REVIEW_COMPLETE sent, REVIEW_REPORT.md written → S5 |
| S5 `G3_PENDING` | CTO | REVIEW_REPORT.md exists in task dir | CTO reviews findings → APPROVE: S6; REQUEST_CHANGES: S8 |
| S6 `FINAL_APPROVAL` | CTO | G3 confirmation received + Reviewer report reviewed | CTO says APPROVE → S7; REJECT: S2 (with rationale) |
| S7 `COMPLETED` | PM | CTO_APPROVAL.md written with APPROVE decision | Post-G4 cleanup complete → CLOSED |
| S8 `CHANGES_REQUESTED` | Varies | G1 revision requested or G3 changes returned | Specific issue resolved and resubmitted → appropriate re-enter state |
| S9 `BLOCKED` | PM (escalates to CTO) | Blocker reported by any agent | External dependency resolved → resume previous state |
| S10 `STALLED` | PM | No artifact update within configured timeout period | Activity resumes → resume previous state; or escalated to user → CTO decides |

### 3.3 State Transition Diagram

```
                        ┌─────────────────┐
                        │   S0 TASK_OPEN  │──CTO submits plan──→ S1 G1_WAITING
                        └─────────────────┘         │
                                                     ├─G1 APPROVE──────→ S2 IMPLEMENTATION
                                                     └─G1 REVISION─────→ S8 CHANGES_REQ
                                                                                       │
                                                    ┌──────────────────┐                │
                              ┌──S8 (resubmitted)───→│   S7 COMPLETED   │◄═══════════════┘
                              │                      │   (post-G4 clean)│    (if S6 CTO approves)
                              │                      └──────────────────┘
                              │                            │
                              │                            ▼
                    ┌─────────┼────G3 return──────────→  ┌───────────────┐
                    │         │                          │   S2          │
                    │         │                          │IMPLEMENTATION │
                    │         │                          └───┬───────────┘
                    ▼         │                              │
              ┌─────────┐     │        IMPL_COMPLETE       ▼
              │  S1 G1  │◄────┼──────────────────────── S3 WAITING_G2
              │WAITING  │     │                              │
              └───┬─────┘     │                    ┌───────┴───────┐
                  │           │                    │    CTO verifies│
                  ├───────────┼────────────────────→G2 Checklist   │
                  │ G1 PASS   │                    │  all pass?    │
                  ▼           │              Yes:  └───┬─────────┘
            ┌──────────┐      │                      NO │
            │ S2       │◄─────┼────────────────────────┘
            │IMPLEMENT │     │                    (return to S2 with gaps)
            │ATION     │     │
            └────┬─────┘     │
                 │IMPL_COMPLETE│
                 ▼            │
            ┌──────────┐      │
            │   S3     │──────┘
            │WAITING  │
            │  G2     │
            └────┬─────┘
                 │CTO confirms
                 ▼
            ┌──────────┐
            │    S4    │
            │  REVIEW  │──────→ (reviewer writes REVIEW_REPORT.md)
            └────┬─────┘
                 │REVIEW_COMPLETE
                 ▼
            ┌──────────┐
            │   S5     │
            │G3_PEND. │──────→ (CTO reviews findings)
            └────┬─────┘
                 ├─G3 APPROVE──────→ S6 FINAL_APPROVAL → CTO decision → S7 COMPLETED
                 └─G3 REQUEST_CHANGES ──→ S8 CHANGES_REQ ──→ (Implem fixes) ──→ S2 → S4 loop

            Any state ──BLOCKER reported──→ S9 BLOCKED
            Any state ──timeout/no-progress──→ S10 STALLED
```

### 3.4 Transition Rules by Mode

For each transition, I define whether Manual and Automatic modes can advance it:

| Transition | Manual Mode | Automatic Mode | Human Required? |
|-----------|-------------|----------------|-----------------|
| CTO creates task dir (S0) | User requests → CTO creates | PM detects need → requests CTO → CTO creates | No (but PM needs user trigger to detect need) |
| CTO submits plan for G1 (S0→S1) | CTO produces, sends to user | Same | **Yes (G1)** — user must approve |
| G1 approved (S1→S2) | User approves → CTO confirms | PM detects approval signal → CTO confirms | **Yes (G1)** — human approval mandatory |
| CTO delegates to Implementer (S2 start) | User activates Implementer | PM sends DELEGATE message, triggers agent | No (automatic transition within S2) |
| IMPL_COMPLETE declared (S2→S3) | Agent self-declares | Agent self-declares or PM detects completion artifacts | No |
| CTO G2 verification (S3→S4/S2) | User/CTO verifies checklist | PM auto-verifies G2 checklist; CTO confirms pass | No (verification is rule-based) |
| Reviewer assigns + reviews (S4) | User activates Reviewer | PM detects S3 pass, sends REVIEWER_ASSIGN, triggers Reviewer | No (automatic transition within S4) |
| G3 pending (S5) | Reviewer writes report → CTO notified | Same; auto-transition on file creation | No (artifact-based trigger) |
| CTO G3 confirmation (S5→S6/S8) | CTO reviews findings | PM detects REVIEW_REPORT.md, alerts CTO to review | **Yes (CTO)** — CTO must evaluate |
| G4 decision (S6→S7/S2) | CTO produces CTO_APPROVAL.md | Same; if approved, PM auto-proceeds to post-G4 | **Yes (G4)** — CTO final authority |
| Post-G4 cleanup (S7) | PM updates status/changelog/commit | PM auto-detects S7 state, runs full post-G4 sequence | No (PM's defined responsibility) |
| Blocker/stall detection (any→S9/S10) | Any agent or user reports | PM monitors activity timestamps; auto-detects stalls | Escalation to CTO/user if unresolved |

### 3.5 Key Design Decisions

**Decision 1: Execution Mode as a Runtime Configuration, Not a Protocol Change**

Execution mode is an OpenClaw-level configuration that determines *who advances the workflow* between states, not *what the workflow requires*. The canonical workflow (roles, gates, artifacts, authority) is invariant.

Configuration location: This should be project-level configuration within the OpenClaw agent config, not in any DS-EO protocol file. Proposed structure:
```yaml
workflow:
  execution_mode: manual  # or "automatic"
```

**Decision 2: PM Orchestrates Transitions but Does Not Hold Authority**

The PM can detect conditions and trigger transitions automatically, but it cannot approve anything. Specifically:
- PM may auto-advance from S3→S4 when G2 checklist passes (rule-based verification)
- PM may auto-advance from S5→S6 by alerting CTO to review findings
- PM may auto-run post-G4 cleanup (S7) when it detects CTO_APPROVED state
- PM cannot override a CTO or Reviewer decision
- PM cannot infer approval from timeout or silence

**Decision 3: Human Approval Gates Remain Immutable**

G1 and G4 always require human presence. Automatic mode does not change this. If the user is unavailable during automatic mode, the workflow pauses at S1 (waiting for G1) or S5/S6 (waiting for CTO/G4). This is different from stall detection — it's a configured "awaiting human" state.

**Decision 4: Mode Switching Rules**

Mode can be changed at any time without resetting workflow state:
- Manual → Automatic: PM immediately begins monitoring and auto-advancing where eligible
- Automatic → Manual: PM stops auto-transitions; remaining transitions require explicit user action
- Mid-transition mode change: No partial state corruption — transition either completes or rolls back before mode switches

**Decision 5: Audit Trail Requirement**

Every automatic transition must produce a log entry with:
```json
{
  "event": "transition",
  "taskId": "TASK_DS_EO_019",
  "fromState": "S2",
  "toState": "S3",
  "executionMode": "automatic",
  "triggeredBy": "PM",
  "reason": "G2 checklist passed",
  "verifiedArtifacts": ["IMPLEMENTATION_REPORT.md"],
  "timestamp": "2026-08-01T19:XX:XXZ"
}
```

This audit log is separate from task artifacts — it lives in a workflow orchestration log (designated PM write path, not task directory).

## 4. Design Artifacts to Produce

This task produces **two deliverables only** (since it's design-only):

### Deliverable A: Execution Mode Architecture Document

A comprehensive document covering:
1. Current-state baseline (what exists today)
2. Formal state machine (states, transitions, owners)
3. Manual Mode specification (unchanged from current behavior)
4. Automatic Mode specification (PM orchestration model)
5. PM authority boundaries in both modes (preserved identical)
6. Human intervention points (G1, G4 always human; optional configurable gates for future)
7. Configuration model (execution_mode field, scope, defaults)
8. Mode switching rules and safety guarantees
9. Failure/rework/stall handling in automatic mode
10. Audit trail requirements
11. Platform portability considerations

This document is the primary output. I will write it as `EXECUTION_MODE_ARCHITECTURE.md` in the task directory.

### Deliverable B: Implementation Roadmap

A phased roadmap for future implementation work (NOT part of this task):
- Phase 1: PM workflow state engine (core state machine + transition logic)
- Phase 2: Audit trail integration (transition logging)
- Phase 3: User-facing mode selector and UI controls
- Phase 4: Failure/stall handling refinements
- Phase 5: Testing and validation

The roadmap identifies which future tasks would be needed to implement Automatic Mode, but does not create those tasks. The CTO will recommend specific follow-up task numbers.

## 5. Acceptance Criteria (CTO's Definition)

This task is complete when the following are satisfied:

### Design Completeness
- [ ] A formal state machine with ≥10 states is defined in the architecture document
- [ ] All transitions from the current G1→G2→G3→G4 workflow are mapped to concrete state transitions
- [ ] Manual Mode is documented as the reference (unchanged) behavior
- [ ] Automatic Mode is formally specified with PM orchestration rules
- [ ] PM authority boundaries are explicitly preserved in both modes
- [ ] G1 and G4 human approval requirements are immutable — no automatic bypass

### Configuration Model
- [ ] Execution mode configuration structure is defined (`workflow.execution_mode`)
- [ ] Both `manual` and `automatic` are supported initial values
- [ ] Default execution mode is specified (recommendation: `manual` for backward compatibility)
- [ ] Mode selection timing is addressed (project config vs. runtime control)

### Transition Safety
- [ ] Every state transition has explicit entry conditions, exit conditions, and required artifacts
- [ ] Rejection/rework loops are defined (G3→Implementer→G3; G4→Implementer→G2)
- [ ] Blocker and stall detection behavior is specified for both modes
- [ ] Mode switching rules preserve existing workflow state

### Auditability
- [ ] Automated transition audit requirements are defined with log entry schema
- [ ] Audit trail is independent of task artifacts (separate store)
- [ ] All transitions are reconstructable from audit log alone

### Implementation Roadmap
- [ ] A phased implementation roadmap is provided
- [ ] Architecture work is clearly separated from future implementation tasks
- [ ] Recommended follow-up task(s) are identified for implementing Automatic Mode

### Artifact Integrity
- [ ] All produced artifacts are saved to designated paths in the task directory
- [ ] Artifacts carry required metadata (agent_id, session_id, model, produced_at)
- [ `EXECUTION_MODE_ARCHITECTURE.md` exists with all design sections above
- [ ] Implementation roadmap is clearly scoped as out-of-band (not implementation itself)

## 6. Risks and Constraints

### Risks
1. **PM role collapse risk**: If PM's automatic capabilities are designed too broadly, it could absorb CTO/Reviewer authority. Mitigation: PM orchestration rules explicitly list what it CAN do, with all other actions as prohibited.
2. **Stall detection false positives**: In automatic mode, long-running reviews or implementation might trigger false stall alerts. Mitigation: Configurable timeouts per state; human approval states (S1, S6) are exempt from stall detection.
3. **Mode switching race conditions**: If mode changes mid-transition, partial state corruption could occur. Mitigation: Mode switches only at state boundaries (no mid-transition changes).
4. **Audit trail storage**: Determining where to store audit logs (separate from task artifacts but still accessible) needs careful design for platform portability.

### Constraints
1. No modification of existing G1–G4 gate authority
2. No change to PM's tool policy (exec/process remain denied)
3. No bypass of human approval at G1/G4
4. Platform-neutral design (not OpenClaw-specific internals)
5. Manual mode remains fully functional and supported
6. All existing protocols remain authoritative

## 7. Follow-Up Task Recommendation

After this task is approved, the next phase should be:

**Recommended next task**: Implement Phase 1 — PM workflow state engine (core state machine + transition logic). This would require CTO to design the actual implementation plan with specific files to create/modify and acceptance criteria for testing.

The specific TASK_ID and scope of that future task will be determined by the CTO after user approval at G1 of this task.

---

## Gate Status

| Gate | Status | Notes |
|------|--------|-------|
| G0 (Task Creation) | ✅ Done | Task directory created, spec received |
| G1 (User Approval of Plan) | ⏳ Awaiting | User must approve this CTO_PLAN before proceeding to design document production |
| G2–G4 | N/A | Design-only task; no code changes expected |

**Note**: Since this is a design-only task, there are no code implementation deliverables. The user's G1 approval covers the scope of architectural work described in this plan. Upon G1 approval, the CTO will produce the two design artifacts listed above (EXECUTION_MODE_ARCHITECTURE.md and Implementation Roadmap).

---

*CTO Plan produced by: CTO (qwen3.6:35b)*  
*Date: 2026-08-01*
