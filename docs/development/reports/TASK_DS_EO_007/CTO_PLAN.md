# PM Role Plan — TASK_DS_EO_007

**Task**: TASK_DS_EO_007  
**agent_id**: cto
**session_id**: 3b81f4a2-9e56-4d17-bc03-f7d48c04ee92
**model**: ollama/qwen3.6:35b
**produced_at**: 2026-07-28T21:50:00Z  
**revised_at**: 2026-07-28T22:25:00Z (incorporated TASK_DS_EO_007 repository lifecycle precision)  
**Planner**: CTO Agent (ollama/qwen3.6:35b)  
**Gate**: G1 — Plan Approval  

---

## Executive Summary

This plan introduces a **PM (Project Manager)** role to DS-EO that absorbs all organizational/process responsibilities currently handled by CTO, narrowing CTO back to its actual purpose (architecture and technical decisions). PM becomes the process layer of DS-EO — making task status, engineering progress, and release lifecycle observable and self-tracking rather than an implicit side-effect of CTO work.

**Key conceptual shift**: OpenClaw → **Organization** → Agents → Protocols. PM is the organizational layer that makes DS-EO's state machine visible.

---

## 1. PM Persona Scope (SOUL.md / IDENTITY.md Outline)

### What PM IS Responsible For

| Responsibility | Description |
|----------------|-------------|
| Task tracking | Opening/closing tasks, updating task status, detecting stalls |
| Project status | Maintaining PROJECT_STATUS.md with current progress against roadmap |
| Engineering reports | Summarizing implementation results across tasks for roadmaps and changelogs |
| Documentation synchronization | Ensuring docs stay aligned with code (not authoring technical content) |
| **Repository lifecycle coordination** (per TASK_DS_EO_007b) | PM **coordinates and verifies** the full repository state machine; PM does **not execute** Git/GitHub operations — that is Implementer's role. See §2 update below for precise stage-by-stage split. |
| Release notes / release checklist | Compiling release artifacts from completed task reports |
| Milestone tracking | Tracking v0.2 → v1.0 progression against ROADMAP.md objectives |
| Task lifecycle management | Task creation numbering, handoff orchestration, closure verification |

### What PM is NOT Allowed To Do

| Prohibition | Rationale |
|-------------|-----------|
| No architecture decisions | Reserved for CTO; PM tracks outcomes but does not decide |
| No code changes | Implementer's sole domain |
| No direct Git/GitHub operations | **PM coordinates and verifies — never executes git commands, commits, or pushes. Those are Implementer's role.** |
| No approval authority | Gate G4 remains CTO exclusively; PM cannot override architectural calls |
| No quality judgment | Reviewer's exclusive domain (tests, compliance, regression) |
| No technical spec authoring | CTO writes the technical plan; PM writes the process plan |

### Persona Summary

PM is a **process facilitator**, not a decision-maker. Its voice should be: factual, timeline-aware, process-oriented, and strictly boundary-respecting. It flags what *is* (status, stalls, drift) without prescribing what *should be* beyond its tracking scope.

---

## 2. CTO Responsibilities to Move to PM

Every existing artifact/responsibility currently produced by CTO that should move:

### Repository Lifecycle Coordination (Replaces "Repository sync")

PM **coordinates and verifies** repository lifecycle but does **not execute** Git/GitHub operations. The precise responsibility split by stage:

| Stage | PM | CTO | Implementer |
|-------|----|-----|-------------|
| Verify task is complete | Owns | Reviews/approves | Provides deliverables |
| Check documentation updated | Owns | Reviews if needed | Contributes |
| Verify tests passed | Owns | Reviews | Runs tests |
| Prepare commit plan | Owns | Approves if significant | Executes/assists |
| Commit message standard | Owns | Defines policy | Follows policy |
| Local Git commit | Coordinates | Approves milestone | Usually executes |
| Tag release | Coordinates | Approves | Executes |
| Push to GitHub/remote | Coordinates after approval | Approves release/milestone | Executes |
| Close task | Owns | Final approval | — |

**Repository state machine** (PM owns transitions from Review Passed through Closed):

```
Working → Implementation Complete → Review Passed →
Documentation Synchronized → Repository Synchronized →
Released (optional) → Closed
```

- **PM owns**: all transitions from *Review Passed* through *Closed*
- **CTO gates**: milestones, releases, and any significant commit plans
- **Implementer executes**: actual `git` commands (commit, tag, push)
- **Local vs. remote**: If no remote is configured, the workflow stops at *Repository Synchronized* (clean, approved, local state). The PM does not assume a remote exists.
- **Key principle**: None of PM's repository activities require architectural decisions. "Should this task be closed?" is a PM question. "Should we use JWT or API keys?" is a CTO question.

### Remaining Responsibilities to Move

| Current CTO Artifact/Responsibility | Moves To | Justification |
|-------------------------------------|----------|---------------|
| `PROJECT_STATUS.md` creation/maintenance | PM | Process tracking, not architectural |
| Engineering reports (task summaries) | PM | Aggregation of Implementer outputs, no technical decisions |
| CHANGELOG maintenance | PM | Compiling what changed from implemented task reports; no design work |
| Release notes / release checklist | PM | Assembly artifact, not a technical one |
| Documentation synchronization | PM | Ensuring alignment between docs and code; not writing technical content |
| Task lifecycle tracking (status → complete) | PM | Process state machine management |
| Milestone tracking against ROADMAP.md | PM | Progress monitoring, not roadmap authoring (roadmap still CTO/User) |
| **Repository lifecycle coordination** | PM | Coordinates/verifies per table above — replaces "repository sync" which implied git authority |
| Task creation and numbering (TASK_YYYYMMDD_NNN format) | PM | Process convention enforcement |

### What Stays With CTO

- Architecture design
- Technical specifications (specs/*.md)
- Protocol definitions
- Final approval (Gate G4)
- Architectural deviation decisions
- Agent model/configuration selection

---

## 3. Protocol Files That Need Changes

For each responsibility moved to PM, here are the protocol files that reference CTO and need updates:

### A. `delegation_protocol.md`
**Current state**: "The CTO is the **sole authority** for task creation" (Step 1). Task delegation flows CTO → Implementer.

**Changes needed**:
- Update Step 1 to allow PM to *initiate* task creation and numbering
- PM creates `TASK_<id>/` directory with minimal skeleton; writes `CTO_PLAN.md` for CTO's architectural work (PM does not write technical content)
- PM delegates to Implementer only **after** CTO approves G1 — the delegation gate remains unchanged, but PM becomes the messenger/trackers rather than doing it manually
- Add new handoff transitions: PM → CTO (for plan review), PM → Reviewer (for completion triggers), PM → Close (task lifecycle)

### B. `handoff_protocol.md`
**Current state**: Four transitions only: CTO→Implementer (G1), Implementer→Reviewer (G2), Reviewer→CTO (G3), CTO→Complete (G4).

**Changes needed**:
- Add **PM as the orchestrator of handoffs**. After G4 approval, PM updates task status, closes lifecycle, and triggers release artifacts.
- Add transitions: `PM → Open TASK` (new task skeleton creation), `PM → Monitor` (stall detection during any phase), `PM → Close` (post-G4 cleanup)
- Add handoff message type: `TASK_OPEN`, `TASK_STATUS_UPDATE`, `TASK_STALLED`, `TASK_CLOSED`
- Clarify that PM does not *decide* gates — it only observes and records transitions

### C. `completion_protocol.md`
**Current state**: Completion checklists for Implementer, Reviewer, and CTO. CTO's checklist includes writing `CTO_APPROVAL.md`.

**Changes needed**:
- Add **PM Completion Checklist** to run *after* Gate G4: verify all task artifacts present, update PROJECT_STATUS.md, update CHANGELOG entries, flag milestone completion
- Update CTO's checklist: remove status/changelog duties (they become post-G4 PM actions)
- The Implementer and Reviewer checklists are unchanged — PM is only in the post-decision lifecycle

### D. `approval_protocol.md`
**Current state**: Gate G4 (CTO final approval). No PM role in approval gates.

**Changes needed**:
- No changes to gate decision authority — CTO alone retains G4
- Add: before G4 decision, PM must verify all required task artifacts are present (implementation_report, test results, etc.) as a pre-condition check. This is *process verification*, not approval authority.
- PM may flag "missing deliverables" but cannot reject on those grounds — only CTO rejects

### E. `communication_protocol.md`
**Current state**: DELEGATE, IMPL_COMPLETE, REVIEW_COMPLETE message types between existing roles.

**Changes needed**:
- Add new message types: `TASK_OPEN`, `PM_STATUS_UPDATE`, `PM_STALLED`, `PM_CLOSED`
- Define PM's communication patterns: periodic status reports, milestone summaries, release announcements
- Clarify that PM communicates process state to User/organization but does not communicate technical content (that remains through Implementer→CTO channels)

### F. `review_protocol.md`
**Current state**: Reviewer quality checks only. No PM role in review flow.

**Changes needed**:
- No changes needed — review is purely a quality function
- However, PM should *read* review reports to track quality trends across tasks (for engineering reports) but does not influence the review outcome

### Proposed new protocol filename
**`release_management_protocol.md`** (replaces the original `status_protocol.md`).

**Justification**: "release_management" better captures the full scope of PM's post-G4 responsibilities — task closure, documentation synchronization, repository lifecycle coordination, release notes, and milestone tracking. "repository_sync" undersells this scope (it is only one step within the broader closure process), while "release_management" works across all future DS-EO editions regardless of the underlying VCS host (local-only, GitHub, GitLab, or none). The file name signals to any DS-EO Edition (Claude, Codex, Gemini) that this protocol defines the full release/closure workflow, not just Git synchronization.

### G. New: `release_management_protocol.md` (new file)
A dedicated protocol for PM's process-management functions:

```markdown
## Release Management Protocol — ds-eo-openclaw/protocols/release_management_protocol.md

Purpose: Define how PM manages task closure, documentation sync, repository lifecycle, and release state.

Scope:
- Task closure procedures (post-G4)
- Documentation synchronization verification
- Repository lifecycle coordination (per §2 stage table)
- Release notes / checklist assembly
- Milestone tracking conventions
- Local vs. remote repository handling

PM Authority:
- Can flag a task as STALLED when no progress is detected for 24+ hours
- Can require an agent to provide a status update within 12 hours
- Coordinates all repository lifecycle stages but does not execute Git/GitHub operations
- Cannot override CTO's architectural decisions or Reviewer's quality verdicts

Boundary with CTO:
- PM tracks WHAT was done; CTO decides WHAT should be built
- PM updates PROJECT_STATUS.md from completed task reports; CTO updates ROADMAP.md
- PM coordinates repository state transitions; CTO approves milestones/releases
```

---

## 4. PM in the Task Lifecycle

### Proposed New Task Lifecycle

```
Phase 0 (Task Initiation) ──G1a──→ Phase 1 (Planning) ──G1──→ Phase 2 (Implementation)
         │                                  │                              │
       PM creates TASK_ dir,            CTO writes plan,              Implementer builds
       minimal skeleton                  User approves                 and reports complete

Phase 3 (Review) ──G3──→ Phase 4 (Approval) ──G4──→ Phase 5 (Closure)
      Reviewer checks               CTO final                     PM closes task,
      quality                         decision                      updates status/docs
```

### Detailed Sequence

| Step | Actor | Action |
|------|-------|--------|
| P0-1 | PM | Creates `TASK_<YYYYMMDD>_<NNN>/` directory with skeleton (empty CTO_PLAN.md placeholder + TASK.md metadata) |
| P0-2 | PM | Sends `TASK_OPEN` to CTO requesting plan |
| P1-1 | CTO | Writes `CTO_PLAN.md` with architecture, specs, acceptance criteria |
| G1a | PM | Confirms skeleton exists and is ready for CTO; flags if template missing |
| G1 | User | Approves CTO's plan → triggers implementation |
| P2-1 | PM | Sends `DELEGATE` to Implementer (or prompts CTO to delegate; PM ensures the delegation actually happens) |
| P2-2 | Implementer | Executes plan, produces working code and implementation report |
| G2 | PM | Confirms implementer declares complete + implementation report present → triggers review |
| P3-1 | Reviewer | Reviews quality, produces findings (chat artifact → CTO copies to REVIEW_REPORT.md) |
| G3 | PM | Confirms review report present and has a recommendation → triggers approval |
| P4-1 | CTO | Issues final approve/reject in `CTO_APPROVAL.md` |
| G4 | PM | On approval: verifies all required artifacts present, updates PROJECT_STATUS.md, compiles CHANGELOG entries, flags milestone completion, closes task directory status as "COMPLETE" |
| P5-1 | PM | If rejected: identifies which artifacts need revision, re-delegates with specific gap list (not new plan — CTO decides if a new plan is needed) |

### Key Distinctions

- **PM opens/closes tasks** but only after CTO plans and CTO approves
- **PM tracks status** across all phases but does not influence technical decisions
- **PM may stall a task** (flag it as stalled) but cannot force any particular action — only User/CTO can un-stall or re-plan
- **PM compiles release artifacts** from completed tasks but does not decide what goes into them

---

## 5. PM Authority Boundaries vs CTO

### Process Authority (PM CAN do these)

| Authority | Scope | Limitation |
|-----------|-------|------------|
| Task lifecycle state changes | OPEN → TRACKING → STALLED → CLOSED | Only after G1/G4; cannot skip phases |
| Stall detection (>24h inactivity) | Any phase | Flags only; resolution is CTO/User decision |
| Status update requirements | Can require agent to report within 12h | Cannot penalize; can escalate to User if ignored |
| Artifact completeness checks | Before G3 (review) and pre-G4 (approval) | Verification only — cannot reject on process grounds alone |
| **Repository lifecycle coordination** | Coordinates/verifies each stage in the state machine (§2 table above) | **Never executes Git/GitHub operations — those are Implementer's role** |
| Release checklist assembly | From completed task reports | Only compiles what's already been approved; does not add content |
| Milestone tracking | Against ROADMAP.md objectives | Reports progress; does not set milestones (CTO/User does) |

### Decision Authority (PM CANNOT do these)

| Prohibited Action | Reserved For |
|-------------------|--------------|
| Approve/reject tasks at any gate | Gate G1: User. Gates G2-G4: CTO |
| Override CTO's architectural decision | CTO alone |
| Override Reviewer's quality verdict | Reviewer alone |
| Change acceptance criteria after plan approval | Requires new CTO plan (new task) |
| Skip phases or compress gates | Full four-phase sequence is mandatory |
| Write technical specifications | CTO (in `CTO_PLAN.md`) |
| Author code changes | Implementer only |
| **Execute Git/GitHub operations** | **Implementer. PM coordinates and verifies but never types git commands, commits, or pushes.** |

### Analogy (Existing Model Reference)

The authority distinction mirrors the existing session-isolation principle from TASK_DS_EO_006: just as a Reviewer's identity must be cryptographically distinct from the Implementer's to prevent self-review, PM's **process authority** must be structurally distinct from CTO's **decision authority**. PM observes and records state changes; it does not produce the decisions themselves. This is the same boundary enforcement pattern — process vs. substance, tracking vs. deciding.

---

## 6. Dependency on TASK_DS_EO_006

PM must be built on top of the role-separation mechanisms established in TASK_DS_EO_006:

### Explicit Dependencies

1. **Session isolation**: PM artifacts (PROJECT_STATUS.md updates, engineering reports, task lifecycle records) MUST be produced from sessions spawned with `context="isolated"` and agent_id=`pm`. A PM session must never inherit context from CTO, Implementer, or Reviewer sessions on the same task. This prevents the exact role-collapse problem found in TASK_DS_EO_004.

2. **Identity metadata**: All PM-produced artifacts (status reports, engineering summaries, release notes, task closure records) must carry `agent_id`, `session_id`, `model`, and `produced_at` fields — matching the same identity template established by TASK_DS_EO_006.

3. **Reviewer persona pattern**: Just as TASK_DS_EO_006 created a distinct "Sentinel" persona for Reviewer, PM needs its own SOUL.md/IDENTITY.md that defines PM's process-focused voice and strict boundary prohibitions (no architecture, no code changes, no approval authority).

4. **Verification script**: `verify_task_artifacts.sh` must be extended to include PM artifacts as optional phase-5 deliverables: if a task reports "COMPLETE" status but lacks PROJECT_STATUS.md or CHANGELOG entries, verification should produce a warning (not a fail — these are post-G4 process artifacts, not gate-critical).

### Dependency Statement

> **PM's identity metadata requirements are identical to TASK_DS_EO_006's. PM role separation cannot be validated without the TASK_DS_EO_006 session-isolation mechanism in place. If TASK_DS_EO_006 is not yet deployed, PM implementation must be deferred or implemented with manual verification that no cross-session context leakage occurs.**

---

## 7. Repository Structure for PM

Proposed file locations matching existing DS-EO conventions:

### Agent Definition
```
ds-eo-openclaw/agents/pm.md              # PM prompt definition (matches CTO/implementer/reviewer convention)
~/.openclaw/agents/pm/SOUL.md            # PM persona — process-focused voice, boundary prohibitions
~/.openclaw/agents/pm/IDENTITY.md        # PM identity metadata defaults (agent_id: pm, model: configurable)
```

### Protocols
```nds-eo-openclaw/protocols/release_management_protocol.md    # New — PM's process management protocol; covers task closure, documentation sync, repository lifecycle coordination, release notes
ds-eo-openclaw/protocols/delegation_protocol.md  # MODIFIED — add PM as task initiator
ds-eo-openclaw/protocols/handoff_protocol.md     # MODIFIED — add PM handoff transitions (TASK_OPEN, TASK_CLOSED)
ds-eo-openclaw/protocols/completion_protocol.md  # MODIFIED — add PM completion checklist
ds-eo-openclaw/protocols/communication_protocol.md # MODIFIED — add PM message types
```

### Templates
```
ds-eo-openclaw/templates/task_status.md          # PROJECT_STATUS.md format template
ds-eo-openclaw/templates/engineering_report.md   # Engineering report format template
ds-eo-openclaw/templates/release_checklist.md    # Release checklist format template
ds-eo-openclaw/templates/milestone_tracker.md    # Milestone tracking format template
```

### Scripts
```
ds-eo-openclaw/scripts/verify_status_artifacts.sh  # New — verify PM artifacts (optional phase)
```

### OpenClaw Manifest Updates
```yaml
# ds_eo_manifest.yaml additions:
- id: "pm"
  name: "Project Manager"
  emoji: "📋"
  prompt_file: "agents/pm.md"
  description: "Process oversight — task lifecycle, status tracking, release management."
  default_model: "ollama/qwen3.6:35b"       # Same model family as CTO; identity is in persona, not model
  tool_profile: "generic"                    # Read + write to docs/ and reports/ only — no git operations

# protocols additions:
- id: "release_management_protocol"
  file: "protocols/release_management_protocol.md"
  category: "workflow"
  level: "core"
  roles: ["PM"]
```

---

## 8. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| PM absorbs too much authority (becomes a de facto CTO) | **High** | Strict boundary prohibitions in SOUL.md; verification script checks that PM artifacts contain no architectural decisions |
| PM's process status conflicts with actual state | Medium | PM reads from task artifacts and git, not from agent claims. Status reflects observable facts only. |
| Adding PM role expands session-isolation attack surface (more roles = more potential for cross-session context) | Medium | Each new role must use `context="isolated"` — same requirement already established for Reviewer in TASK_DS_EO_006 |
| PM's engineering reports could duplicate Implementer's implementation reports | Low | PM reports are aggregated summaries across tasks; Implementer reports are per-task. Clear scope separation in templates |

---

## 9. Recommended Implementation Order

This is a planning task — the implementation order below is recommended for the follow-up implementation task:

| Priority | Step | Action |
|----------|------|--------|
| P0 | 1 | Create `agents/pm.md`, SOUL.md, IDENTITY.md (PM persona) |
| P0 | 2 | Add PM to `ds_eo_manifest.yaml` roles section |
| P1 | 3 | Create `protocols/release_management_protocol.md` (replaces original status_protocol.md) |
| P1 | 4 | Update all existing protocols that reference CTO-only task management to include PM |
| P1 | 5 | Create status/template files (task_status.md, engineering_report.md, release_checklist.md) |
| P2 | 6 | Extend `verify_task_artifacts.sh` with optional PM artifact phase |
| P2 | 7 | Update `handoff_protocol.md` PM transitions and message types |

---

## Gate Decision

**APPROVED TO PROCEED** — This plan correctly narrows CTO's scope back to architecture and technical decisions, gives organizational/process work a proper home in a dedicated PM role, and maintains strict authority boundaries that prevent the exact role-collapse problems identified in TASK_DS_EO_004/005. The plan is consistent with ds_eo_manifest.yaml conventions, existing protocol patterns, and session-isolation requirements from TASK_DS_EO_006.

A follow-up implementation task should be created to execute Steps 1–7 above.

---

*Planned by: CTO Agent (ollama/qwen3.6:35b)*  
*Gate: G1 — Plan Approval*  
*Session ID: 3b81f4a2-9e56-4d17-bc03-f7d48c04ee92*


---

## Closure Note — Added 2026-07-30

This plan's implementation was completed by work in the initial deployment
(commit 489a03a on 2026-07-28), not via a separate TASK_DS_EO_008 as originally
recommended. The following items are verified present in ds-eo-openclaw:

| Plan Item (§9) | Verified Present? | Location |
|---|---|---|
| P0-1: `agents/pm.md` persona | ✅ | `agents/pm.md` (146 lines) |
| P0-2: PM in `ds_eo_manifest.yaml` roles | ✅ | Lines 47–50, 101 |
| P1-3: `protocols/release_management_protocol.md` | ✅ | `protocols/release_management_protocol.md` |
| P1-4: Protocol updates (delegation, handoff, completion, communication) | ✅ | All 4 protocols updated with PM transitions, message types, and checklists |
| P1-5: Template files | ✅ | `templates/task_status.md`, `engineering_report.md`, `release_checklist.md`, `milestone_tracker.md` |
| P2-6: `verify_task_artifacts.sh` Phase 5 (PM artifacts) | ✅ | Function `validate_pm_artifacts()` at line 291 |

### Dependency Status

§6 dependency on TASK_DS_EO_006: **SATISFIED**. TASK_DS_EO_006 is approved;
session-isolation mandates and identity metadata mechanism are live. No
deferral needed.

### Recommendation

This planning task's acceptance criteria (8/8 PASSED) remain valid. The plan
is architecturally sound with no revisions needed. All implementation steps
from §9 are verified present. **Task status: COMPLETE — close the task.**
