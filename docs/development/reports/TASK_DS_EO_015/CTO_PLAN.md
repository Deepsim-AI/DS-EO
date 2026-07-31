# CTO Plan — TASK_DS_EO_015+017: Protocol & Governance Consistency Migration

**Produced by**: CTO  
**Agent ID**: cto  
**Model**: ollama/qwen3.6:35b  
**Date**: 2026-07-30  

---

## Overview

This plan merges TASK_DS_EO_016 (Protocol Consistency Pass) and TASK_DS_EO_017 (Capability Alignment Pass) into a single **Protocol & Governance Consistency Migration**. Protocol authority, artifact ownership, and capability alignment are coupled — changing one without the others creates new gaps. A single unified task is required.

**Gate**: This plan requests Gate G1 approval from the user before any implementation begins.

---

## Final Ownership Model (User-Approved)

The user approved this model explicitly. All changes in this plan align to it:

### CTO
| Responsibility | Artifact Produced | Tool Capability Required |
|---------------|------------------|------------------------|
| Architecture decisions | CTO_PLAN.md | read + write (task artifacts only) |
| Task creation and numbering | TASK_<id> directory, ID assignment | exec/process (for task skeleton) — delegated to PM per delegation_protocol |
| Planning and acceptance criteria | CTO_PLAN.md | write (to task dir) |
| Final approval/rejection | CTO_APPROVAL.md | write (to task dir) |
| Governance decisions | governance docs | write (to protocols/) |

**CTO tool policy**: `deny: [write, edit, apply_patch]` — **UNCHANGED**. CTO never modifies source code or implementation artifacts. CTO produces its own governance artifacts (CTO_PLAN.md, CTO_APPROVAL.md, governance docs) via behavioral rules and user-mediated write operations as needed.

### Implementer
| Responsibility | Artifact Produced | Tool Capability Required |
|---------------|------------------|------------------------|
| Code changes | source files | full FS access (existing) |
| Tests | test files + results | exec/process (existing) |
| Implementation report | IMPLEMENTATION_REPORT.md | write (via group:fs, existing) |

### Reviewer
| Responsibility | Artifact Produced | Tool Capability Required |
|---------------|------------------|------------------------|
| Quality evaluation | findings (chat artifact) | read + exec/process (existing) |
| Review report | **REVIEW_REPORT.md** | **write (to task dir only)** — NEW |

### PM
| Responsibility | Artifact Produced | Tool Capability Required |
|---------------|------------------|------------------------|
| Coordination and tracking | process artifacts | write + exec/deny (existing from TASK_DS_EO_014) |
| Status updates | PROJECT_STATUS.md, CHANGELOG.md | write (to designated paths only) |
| Workflow compliance verification | handoff readiness reports | write (to task dir only) |

**Critical principle**: Each agent produces its own deliverable artifacts. PM manages workflow tracking but does NOT create artifacts owned by other agents. This is the core correction to TASK_DS_EO_015's original plan.

---

## Section 1: Seven Protocol Inconsistencies — Revised Analysis

### P1: PM task creation vs. CTO ownership — **CONFLICT**

**Finding**: `delegation_protocol.md` §Step 1 assigns PM the actions "Creating directory... Assigning ID..." but AGENTS.md §5 states "The CTO exclusively owns task creation and numbering." This is a direct contradiction between two documents that should be consistent.

**Resolution**: Remove all PM task-creation language from `delegation_protocol.md`. Task creation flow becomes:
1. **CTO creates** the TASK directory and assigns ID (per AGENTS.md)
2. CTO writes `CTO_PLAN.md` placeholder skeleton with section headers + instructions for CTO to populate, or delegates placeholder creation to PM after task directory exists

The PM's role is limited to: detecting that a new task is needed (alerts CTO), and managing the lifecycle once CTO has created it. The PM does **not** create directories or assign IDs.

**Files changed**:
- `delegation_protocol.md` §Step 1 — replace PM creation actions with CTO ownership statement; keep PM's role as "requester/alertor" not "creator"
- `handoff_protocol.md` Transition 0 — clarify that PM triggers the skeleton but does not create it

---

### P2+P7: PM_STALLED naming conflict — **NAMING FIX (same item)**

**Finding**: `communication_protocol.md` defines message type `PM_STALLED`. The audit flagged this as confusing because "PM" in the name implies agent ownership, while stall conditions are phase-level not agent-specific. No fix was applied after the audit.

**Resolution**: Rename `PM_STALLED` → `TASK_STALLED`. Update all references across both files that define or use this message type. This is a pure-naming change with no behavioral impact.

**Files changed**:
- `communication_protocol.md` — rename message type, update description (lines ~50-70)
- `handoff_protocol.md` Transition 0a — rename the handoff message label

---

### P3+P5: CTO capability mismatch for REVIEW_REPORT.md — **RESOLVED VIA REVERSED ASSIGNMENT**

**Finding**: Original plan suggested moving REVIEW_REPORT.md production to PM. **User corrected this.** The correct fix is: **Reviewer produces its own artifact, and the tool policy is updated to allow it.**

**Resolution**: Grant Reviewer `write` permission (scoped behaviorally to `docs/development/reports/TASK_*/REVIEW_REPORT.md` only) while keeping `exec` and `process` allowed for verification commands. Remove "CTO copies report" from both the CTO's role definition and all protocol handoff descriptions. Update agent role definitions and tool configs simultaneously.

**Files changed**:
- `agents/reviewer.md` — update role definition to say "You produce REVIEW_REPORT.md in your task directory" instead of "CTO copies your report"
- `review_protocol.md` — update review process step 7 from "produce findings as a chat artifact (cannot write files)" to "produce review_report.md in the task directory"
- `handoff_protocol.md` Transition 3 — update handoff method to note Reviewer writes REVIEW_REPORT.md directly
- `agents/cto.md` — remove "Copies Reviewer's report into REVIEW_REPORT.md after approval" from deliverables list
- `completion_protocol.md` — PM post-G4 artifact verification section: verify CTO already placed REVIEW_REPORT.md (written by Reviewer)
- `openclaw.json` — add `write` to Reviewer's allow list

**Important**: The write permission is granted to the config (which controls all file writes globally), but the **behavioral boundary** is enforced via role definition rules: "You may only write REVIEW_REPORT.md in your current task directory. Writing any other file is prohibited." This is the same approach used for PM's designated write paths. OpenClaw does not support path-scoped tool permissions at the config level, so the boundary is behavioral.

---

### P4: G2 gate criteria divergence — **UNIFIED CHECKLIST**

**Finding**: Three separate protocols define G2 prerequisites with overlapping but non-identical criteria:
- `approval_protocol.md` G2 section: "All required artifacts present; test results documented; report references acceptance criteria; no unresolved blockers"
- `completion_protocol.md` Implementer checklist (pre-G2): code changes committed, tests written, all existing tests passing, IMPLEMENTATION_REPORT.md with 5 sub-items
- `handoff_protocol.md` Transition 2: "Code changes applied; all tests run and results documented; IMPLEMENTATION_REPORT.md written"

**Resolution**: Create a **single authoritative G2 Gate Checklist** as an appendix to `approval_protocol.md`. Both `completion_protocol.md` and `handoff_protocol.md` reference this checklist by name rather than defining their own variant. The unified checklist combines all three sources into one definitive list:

```
G2 Gate Checklist (Unified):
- [ ] Code changes applied per CTO_PLAN.md scope
- [ ] All existing tests still passing (no regressions)
- [ ] IMPLEMENTATION_REPORT.md exists with:
  - [ ] Files changed summary
  - [ ] Design decisions and rationale
  - [ ] Test results (pass/fail for each)
  - [ ] Known limitations
  - [ ] Reference to acceptance criteria
- [ ] No unresolved TODOs/FIXMEs that block verification
- [ ] Artifacts carry required metadata (agent_id, produced_at)
```

**Files changed**:
- `approval_protocol.md` — add "G2 Gate Checklist" section as authoritative source
- `completion_protocol.md` — change Implementer pre-G2 checklist to "see G2 Gate Checklist in approval_protocol.md"; keep only agent-specific notes (e.g., "follow coding conventions") that don't appear in the unified checklist
- `handoff_protocol.md` Transition 2 — replace prerequisites with "see G2 Gate Checklist"

---

### P6: Metadata enforcement protocol siloing — **INTEGRATE INTO PROTOCOLS**

**Finding**: The metadata pattern (agent_id, session_id, model, produced_at) exists in PM's role definition but is referenced by zero protocols. No gate checks these fields during handoffs.

**Resolution**: Add metadata verification as a mandatory step in two places:
1. **G3 handoff prerequisites** (Transition 3 in handoff_protocol.md) — the CTO verifies metadata on all artifacts from Phase 2 and Phase 3 before accepting the handoff
2. **Reviewer completion checklist** (completion_protocol.md) — the Reviewer confirms its own findings include agent_id + produced_at

This makes metadata enforcement a protocol requirement, not just a role definition suggestion.

**Files changed**:
- `handoff_protocol.md` Transition 3 prerequisites — add "All Phase 2 and Phase 3 artifacts carry required metadata fields"
- `completion_protocol.md` Reviewer completion checklist — add "agent_id and produced_at present in review artifact"
- `approval_protocol.md` G4 decision criteria — add "All artifacts in task directory verified for required metadata"

---

## Section 2: Five Ownership Gaps — Revised Resolution

### Gap #1 (REVISED): REVIEW_REPORT.md ownership
**Original finding**: Nobody could produce it.  
**User-approved resolution**: Reviewer produces its own artifact + gets write permission. This directly addresses the gap by giving responsibility to an agent that also has the capability.

### Gap #2: Mid-lifecycle status documentation
**Finding**: PROJECT_STATUS.md and CHANGELOG.md are only updated in PM's Transition 0b (task close), not during active task lifecycle. Between G1 and G4, no agent is responsible for project-level status documents.

**Resolution**: Add mid-lifecycle status update triggers to PM's TRACKING state. When any gate transition occurs (G1→G2, G2→G3, G3→G4), the PM should:
- Update PROJECT_STATUS.md with the new phase
- Log to CHANGELOG.md if user-facing changes are relevant

This is a behavioral rule in `agents/pm.md`, not a protocol change. It adds responsibility to the TRACKING state without changing existing protocols.

### Gap #3: Post-rejection artifact cleanup
**Finding**: When CTO rejects at any gate, the protocol describes the return path but not what happens to artifacts from the rejected cycle. Stale artifacts (partial reviews, incomplete reports) remain in the task directory.

**Resolution**: Add a "Post-Rejection Artifact Cleanup" section to `approval_protocol.md` under rejection handling procedures. This specifies:
- CTO notes which artifacts should be kept vs. marked stale in its rejection rationale
- PM's post-rejection role includes flagging stale artifacts (not deleting them — deletion is an irreversible action the PM should not take)
- If the Implementer resubmits, only current-cycle artifacts are evaluated

### Gap #4: Spec lifecycle management
**Finding**: Protocols reference "spec" files but don't define who creates, updates, or archives specs. AGENTS.md mentions "Move spec to completed" at G4 but doesn't say who does it.

**Resolution**: Add a brief "Spec Lifecycle" section to `delegation_protocol.md`. This establishes:
- **CTO creates** specs (derived from user requirements) during planning phase
- **PM tracks** spec status (active/completed/archived) in PROJECT_STATUS.md
- **Implementer references** specs but never modifies them
- At G4 approval, the CTO moves the spec to "completed" status; PM records this update

### Gap #5: Tool-policy-vs-protocol conflict escalation
**Finding**: Multiple agents have responsibilities that their tool policies prevent from executing (historically — P3/P5 resolved by this task). There's no meta-governance path for detecting and fixing such mismatches going forward.

**Resolution**: Add a "Tool Policy Compliance" step to CTO's Gate G4 checklist in `completion_protocol.md` (CTO completion section). Before issuing final approval, the CTO verifies:
- No agent was asked to produce something their tool policy blocks
- Any identified gaps are logged and addressed before task closure

This is a lightweight governance rule that catches future mismatches before they become workflow blockers.

---

## Section 3: Audit Recommendations — Final Status

| R | Description | Status | Notes |
|---|-------------|--------|-------|
| R1 | PM write access fix | ✅ Done | TASK_DS_EO_014 |
| R2 | PM write-failure protocol | ✅ Done | TASK_DS_EO_014 |
| R3 | Unified G2 Gate Checklist | ⏳ This task | See P4 above |
| R4 | Rename PM_STALLED → TASK_STALLED | ⏳ This task | See P2+P7 above |
| R5 | Post-G4 metadata enforcement | ⏳ This task | See P6 above |
| R6 | Reviewer write capability for review artifact | ⏳ This task | See P3+P5 above — reversed from original plan per user correction |
| R7 | PM_STALLED naming fix | ⏳ Same as R4 | Single rename covers both |
| R8 | Path-scoping residual risk | ⏳ This task | Assessment + mitigations below |

---

## Section 4: Path-Scoping Residual Risk — Revised Assessment

**Context**: Both PM and Reviewer now have `write` access. OpenClaw does not support path-scoped tool permissions. Both agents can technically write any file in the workspace. This is an **acceptable residual risk** with the following mitigations:

### Mitigation 1: Behavioral rules (already in place)
PM's role definition (`agents/pm.md`) has explicit designated write paths and a Write-Failure Protocol. The Reviewer role definition will have a corresponding rule: "You may only write REVIEW_REPORT.md in your current task directory."

### Mitigation 2: Post-G4 integrity check (new)
Add to CTO's Gate G4 checklist: verify that no agent wrote to another agent's designated path during the task. Specifically:
- No non-Implementer files outside their artifact paths were modified
- Role definition files (`agents/*.md`) are unmodified by non-owner agents
- Protocol files are only modified via approved TASKs

### Mitigation 3: Auto-reject rule (new)
Add to `approval_protocol.md`: "If any agent writes to a file outside its designated artifact paths, this is an automatic REJECT at Gate G4 — the responsible agent reports the write as a BLOCKER and CTO investigates."

### Risk verdict
**Acceptable.** The implementer already has unrestricted write. Adding controlled write to PM (with behavioral rules) and Reviewer (with behavioral rules) does not materially increase risk because:
- These are governance tools, not production infrastructure
- Agreements on artifacts are explicit per-agent in this plan
- Detection is built into post-G4 integrity checks

---

## Section 5: GATE_AUTHORITY_MATRIX.md — New Artifact

A new single source of truth for gate ownership and artifact requirements:

### Structure (to be created at `protocols/GATE_AUTHORITY_MATRIX.md`)

```markdown
# Gate Authority Matrix

| Gate | Phase From → To | Who Owns the Gate | Decision Authority | Required Artifacts | Transition Conditions |
|------|-----------------|-------------------|-------------------|-------------------|---------------------|
| G1 | Planning → Implementation | User (CTO proposes) | User: Approve / Request revision | CTO_PLAN.md with acceptance criteria, spec ref, risk analysis | User says "APPROVE" or "REQUEST_CHANGES(reason)" |
| G2 | Implementation → Review | Implementer + CTO confirms | Implementer declares complete; CTO confirms artifacts present | IMPLEMENTATION_REPORT.md, test results, code changes per G2 checklist below | All items on G2 checklist verified |
| G3 | Review → Approval | Reviewer (recommends) | Reviewer recommends APPROVE/REQUEST_CHANGES based on rubric | REVIEW_REPORT.md with scoring matrix, spec compliance, regression analysis | Scoring ≥ threshold per review_protocol.md; all dimensions checked |
| G4 | Approval → Complete | CTO (final decision) | CTO: Approve / Reject based on Reviewer findings + own assessment | All artifacts present; metadata verified; no unresolved concerns | CTO says "APPROVE" or "REJECT(reason)" |

## Artifact Ownership Summary

| Artifact | Producer | Tool Capability Required | Behavioral Boundary |
|----------|----------|------------------------|-------------------|
| CTO_PLAN.md | CTO | write (task dir) | Only in task dirs; no source code changes |
| IMPLEMENTATION_REPORT.md | Implementer | write (full FS via group:fs) | As scoped in approved plan only |
| REVIEW_REPORT.md | Reviewer | write (task dir, NEW) | Only this file in the current task directory |
| CTO_APPROVAL.md | CTO | write (task dir) | Only in task dirs; no source code changes |
| PROJECT_STATUS.md | PM | write (designated paths) | Workspace root only |
| CHANGELOG.md | PM | write (designated paths) | Workspace root only |

## G2 Gate Checklist (Unified)

- [ ] Code changes applied per CTO_PLAN.md scope
- [ ] All existing tests still passing (no regressions)
- [ ] IMPLEMENTATION_REPORT.md exists with: Files changed, Design decisions, Test results, Known limitations, Acceptance criteria reference
- [ ] No unresolved TODOs/FIXMEs that block verification
- [ ] Artifacts carry required metadata (agent_id, produced_at)
```

This matrix replaces the scattered gate definitions across three protocol files. Protocols continue to exist for deep detail but reference this matrix as the single source of truth for ownership and requirements.

---

## Section 6: Complete List of File Changes

### Protocol Files (authoritative in `protocols/`)

| # | File | Change Type | Detail |
|---|------|------------|--------|
| 1 | `approval_protocol.md` | Add section | G2 Gate Checklist as authoritative source; add metadata enforcement to G4 criteria; add auto-reject rule for off-path writes |
| 2 | `communication_protocol.md` | Edit (naming) | Rename `PM_STALLED` → `TASK_STALLED` everywhere |
| 3 | `completion_protocol.md` | Edit (multiple) | PM post-G4: verify REVIEW_REPORT.md written by Reviewer; add CTO tool-policy compliance step; update Implementer pre-G2 checklist to reference G2 Gate Checklist; add metadata to Reviewer checklist |
| 4 | `delegation_protocol.md` §Step 1 | Edit (ownership correction) | Remove PM task-creation actions; replace with "PM requests, CTO creates and assigns ID"; add Spec Lifecycle section |
| 5 | `handoff_protocol.md` Transition 0 | Edit | Clarify PM triggers skeleton but CTO owns task creation |
| 6 | `handoff_protocol.md` Transition 0a | Edit (naming) | Rename TASK_OPEN handoff message label → TASK_STALLED |
| 7 | `handoff_protocol.md` Transition 3 | Edit (method update) | Reviewer writes REVIEW_REPORT.md directly; CTO no longer copies it |
| 8 | `handoff_protocol.md` Transition 2 | Edit | Replace prerequisites list with reference to G2 Gate Checklist |
| 9 | **NEW** `GATE_AUTHORITY_MATRIX.md` | Create | Single source of truth for gate ownership, required artifacts, and approval authority |

### Agent Role Definitions (workspace in `agents/`)

| # | File | Change Type | Detail |
|---|------|------------|--------|
| 10 | `agents/reviewer.md` | Edit | Update role definition: "You produce REVIEW_REPORT.md in your task directory." Remove "CTO copies your report." Update deliverables section. Update tool policy docs to reflect new write capability. Add behavioral rule: "You may only write REVIEW_REPORT.md in the current task directory." |
| 11 | `agents/cto.md` | Edit | Remove "Copies Reviewer's report into REVIEW_REPORT.md after approval" from Required Deliverables. Add G4 tool-policy compliance verification step. Keep write deny unchanged (for source code). |
| 12 | `agents/pm.md` | Edit | Update mid-lifecycle status update responsibility to TRACKING state; verify CTO_PLAN.md placeholder creation flow in delegation section doesn't contradict new task-creation rules |

### OpenClaw Config (`~/.openclaw/openclaw.json`)

| # | Field | Change |
|---|-------|--------|
| 13 | `agents.list[reviewer].tools.allow` | Add `write` to allow list |
| 14 | `agents.list[reviewer].tools.deny` | Keep `["edit", "apply_patch"]` — write is now allowed, but edit/apply_patch remain blocked (Reviewer reads code via group:fs exec, doesn't modify it) |

### AGENTS.md (workspace root governance)

| # | Field | Change |
|---|-------|--------|
| 15 | §3 Reviewer section | Update tool policy description to note write access for review deliverables |
| 16 | §4 Development Workflow | No changes — G2 gate definition unchanged, only the artifact requirements (implemented in protocols) |

### AGENTS.md §5 Task Directory Structure

| # | Field | Change |
|---|-------|--------|
| 17 | REVIEW_REPORT.md annotation | Clarify "(produced by Reviewer)" instead of "Reviewer → CTO copies" |

---

## Section 7: Acceptance Criteria

The following criteria must all be met for this task to be considered complete:

### A. Protocol Consistency
1. All four gate definitions (G1–G4) are consistent across `approval_protocol.md`, `completion_protocol.md`, and `handoff_protocol.md` — no divergent criteria
2. No protocol references `PM_STALLED`; all instances renamed to `TASK_STALLED`
3. `delegation_protocol.md` §Step 1 correctly assigns task creation to CTO with PM as requestor, not creator
4. A single G2 Gate Checklist exists and is referenced by all three protocols

### B. Artifact Ownership Alignment
5. Each agent's role definition matches its actual write capability in openclaw.json:
   - CTO: can produce CTO_PLAN.md + CTO_APPROVAL.md (via behavioral rules, config unchanged)
   - Implementer: produces IMPLEMENTATION_REPORT.md (existing full access)
   - Reviewer: produces REVIEW_REPORT.md (newly granted write capability)
   - PM: produces PROJECT_STATUS.md + CHANGELOG.md + status reports (existing write capability)
6. No agent is assigned a responsibility that its tool policy prevents it from executing

### C. Governance Infrastructure
7. `GATE_AUTHORITY_MATRIX.md` exists as a single source of truth for gate ownership
8. Artifact metadata verification is enforced at G3 (handoff prerequisites) and G4 (CTO checklist)
9. Post-rejection artifact handling procedure is documented in `approval_protocol.md`
10. Spec lifecycle process is defined in `delegation_protocol.md`

### D. Integrity Verification
11. No agent role definition file was modified by a non-owner agent during the task
12. Protocol files are consistent with AGENTS.md §3 ownership model (the table in this plan)
13. Config changes match protocol changes — every tool policy change has a corresponding responsibility assignment

---

## Section 8: Implementation Steps (for Implementer, after G1 approval)

After user approves Gate G1, the CTO will produce the following delegation package for the Implementer:

### Deliverable Package
The Implementer receives these as input to this task:
- `CTO_PLAN.md` (this file) — the full plan and acceptance criteria
- Updated protocol text snippets (see Section 6) organized by file path
- Config change JSON snippet for openclaw.json reviewer tools update

### Implementation Order
1. **Config changes first** (`openclaw.json` Reviewer tool update) — enables the capability change that everything else depends on
2. **Role definitions second** (`agents/reviewer.md`, `agents/cto.md`) — aligns capabilities with responsibilities
3. **Protocol files third** (9 protocol files per Section 6 table) — the substantive governance updates
4. **GATE_AUTHORITY_MATRIX.md fourth** — new artifact tying everything together
5. **AGENTS.md fifth** — update workspace-level governance references

### Verification
After implementation, the CTO (or PM via verification) will confirm:
- All 13 items in Section 7 acceptance criteria are met
- No protocol file was changed outside its documented scope
- Config changes match exactly one Reviewer tool policy addition (write only)
- Agent role definitions are internally consistent (responsibilities match capabilities)

---

## Gate G1 Approval Requested

Please approve this merged TASK_DS_EO_016+017 plan. The user has explicitly approved:
- ✅ Reviewer produces its own REVIEW_REPORT.md (with write capability)
- ✅ Each agent owns its own deliverable artifacts
- ✅ CTO write restrictions unchanged for source code
- ✅ Single unified governance overhaul

No implementation will begin until this gate is cleared.
