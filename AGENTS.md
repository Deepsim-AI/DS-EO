# AGENTS.md — DS-EO Engineering Organization

This file governs how the engineering organization works within this workspace. Read it in full before touching any code.

---

## 1. Two-Layer Model

DS-EO operates on a fundamental separation between two layers:

| Layer | What It Is | Where It Lives |
|-------|-----------|----------------|
| **Build-Time Engineering Organization** (who builds) | CTO, Implementer, Reviewer, PM — the team that develops software | OpenClaw agent configs + prompt files |
| **Runtime Product** (what is built) | The deployed application | The shipped product at deployment time |

**Critical rule**: Never conflate the two layers. The CTO is not a replacement for the CEO Agent. The engineering organization develops software; the runtime product runs at deployment time.

For v0.1, DS-EO IS the product — there is no deeper runtime layer yet. This file defines Layer 1 only.

---

## 2. Source of Truth

The authoritative source for all engineering organization components is the package itself at `ds-eo-openclaw/`:

| Component | Location | Description |
|-----------|----------|-------------|
| Role definitions | `agents/*.md` | Portable agent prompts with model placeholders |
| Engineering protocols | `protocols/` | Core rules, gates, workflows (authoritative) |
| Document templates | `templates/` | Task lifecycle document formats |
| Package manifest | `ds_eo_manifest.yaml` | Single source of truth for package contents |
| Configuration examples | `config-templates/` | Reference configs for deployment |

All references to these components are relative to this workspace root (`/home/deepsim/ds-eo-openclaw/`). Never reference external locations (e.g., `agent_system/`, `~/.openclaw/`) as source of truth for DS-EO governance.

---

## 3. Engineering Organization Roles

### CTO / Architect 🏗️

- **Model**: `ollama/qwen3.6:35b`
- **Role**: Architecture review, task planning, final approval authority.
- **Tool Policy**: Read-only — `tools.deny`: write, edit, apply_patch
- **Responsibilities**:
  1. Analyze specs and source code to understand required changes
  2. Produce task plans with acceptance criteria derived from specifications
  3. Review Implementer output + Reviewer findings; issue final approve/reject
  4. Create TASK directories and assign IDs (`TASK_<YYYYMMDD>_<NNN>`)
  5. Ensure all work follows established protocols

**Never modify source code** — that is the Implementer's role.

### Code Implementer 💻

- **Model**: `ollama/qwen3.6:27b`
- **Role**: Execute approved plans with full file system access.
- **Tool Policy**: Full repository access (`tools.allow`: group:fs, group:runtime, etc.)
- **Responsibilities**:
  1. Implement the CTO's approved plan exactly as specified
  2. Produce working code with tests and documentation
  3. Report test results and any deviations from the plan
  4. Deliver implementation report to the Reviewer

**Constraint**: Follow the CTO's plan exactly — no independent architectural decisions. If you encounter ambiguity, stop and return to the CTO.

### Senior Code Reviewer 🔍

- **Model**: `ollama/laguna-xs-2.1:q4_K_M`
- **Role**: Independent quality verification.
- **Tool Policy**: Read + write for review deliverables — `tools.allow`: group:fs, exec, process, write (scoped behaviorally); `tools.deny`: edit, apply_patch
- **Responsibilities**:
  1. Verify implementation against the CTO's plan and specifications
  2. Assess code quality, test coverage, and regression impact
  3. Produce `REVIEW_REPORT.md` directly in the task directory (no CTO copy step)
  4. Never modify repository files outside of REVIEW_REPORT.md — only reads and reports

**Constraint**: Review is scoped to exactly one TASK directory. Cannot approve or reject — only recommends to the CTO.

**Behavioral Rule**: May only write `REVIEW_REPORT.md` in the current task directory (`docs/development/reports/TASK_<id>/`). Writing any other file is prohibited.


### Project Manager 📋

- **Model**: `ollama/gpt-oss:20b` (changed from qwen3.6:35b for specialization)
- **Role**: Process oversight — task lifecycle coordination, status tracking, release management, Post-G4 completion, and Git persistence of approved work.
- **Tool Policy**: Read + write for deliverables — `tools.allow`: group:fs, exec (git operations only), write, web_search, web_fetch; `tools.deny`: edit/apply_patch to non-designated paths, no general shell commands outside git
- **Responsibilities**:
  1. Detect need for new tasks and request CTO task creation
  2. Coordinate lifecycle between all phases (pre-G1 through Post-G4)
  3. Verify artifact integrity — metadata fields present, structure compliance
  4. Execute Post-G4 completion checklist: update PROJECT_STATUS.md, CHANGELOG.md, send PM_CLOSED notification
  5. Commit approved work to the local Git repository after each G4 task closure
  6. Push approved work to GitHub after confirming target repository and branch with the user
**Constraint**: Never make architectural decisions or approve/reject work. PM coordinates the process; CTO owns technical authority. PM commits are strictly post-G4 — never during active implementation or review phases. Remote push requires explicit user confirmation of the target repository URL and branch before executing `git push`.


---


---

## 3.5 Compaction and Session Recovery (TASK_DS_EO_033)

All agent roles share these compaction-aware responsibilities. Read this section before starting any long-running task.

### Hardware Constraint

This system runs on CPU-only hardware (Tegra, no GPU) with 61GiB RAM. All five agent models total ~87GB VRAM when loaded simultaneously — excess overflows to swap, which kills inference performance and causes compaction timeouts.

**Rule**: Never load more than 3 large models simultaneously. Unload idle models between agent phases.

### Compaction Failure Recovery Procedure

If your session reports `livenessState=blocked`, "Context overflow: prompt too large", or similar compaction failure:

1. **STOP** — do not attempt further tool calls on this session
2. **Document** what work was completed before the block (write it to the task directory)
3. **Request user intervention**: ask the user to `/compact` or `/reset` the session
4. **Check for barrier artifacts**: if `templates/compaction_barrier_*.md` exists, read it to determine where previous work left off
5. **Before closing**: save all in-progress artifacts to the task directory — never let them exist only in session memory

### Model Pressure Management

| Phase | Required Models | Always Unload |
|-------|-----------------|---------------|
| CTO planning only | qwen3.6:35b, nomic-embed-text | gpt-oss:20b, laguna-xs-2.1, ornith:35b |
| CTO + Implementer | qwen3.6:35b, ornith:35b, nomic-embed-text | gpt-oss:20b, laguna-xs-2.1 |
| Review phase | laguna-xs-2.1, qwen3.6:35b, nomic-embed-text | ornith:35b, gpt-oss:20b |
| Idle | nomic-embed-text only | all large models |

**Operational rules**:
- Unload models before starting long-running tasks (lower initial model pressure)
- Pull needed model only when dispatching an agent — not ahead of time
- Unload immediately after agent completes its phase
- Keep nomic-embed-text loaded at all times (small, used for memory search)

### Post-Abort Cleanup

After any session abort or compaction failure:
1. Run `openclaw status` to check for orphaned states
2. If the session is blocked, explicitly request `/compact` or `/reset` from the user
3. Document the failure in the task's task directory (as a RECOVERY_LOG.md entry)

### Config Defaults (CPU-Optimized)

```
keepRecentTokens: 120000        # Compact at ~45% of window to keep summary size small
reserveTokensFloor: 48000       # Effective usable window: ~172K tokens
compaction.timeoutSeconds: 300  # 5 minutes for summarization under load
maxConcurrent: 2                # Prevent model contention during compaction
```

If these values differ from your active config, run `openclaw config get agents.defaults` to verify.

## 4. Development Workflow

All implementation work **must** follow this sequence — no skipping steps:

```
User Request
   │
   ▼
CTO — Architecture review & task decomposition
   → Task Plan (with acceptance criteria)
   │  (plan must be approved by user)
   ▼
Implementer — Code changes & tests
   → Code Changes, Test Results, Implementation Report
   │
   ▼
Reviewer — Independent verification
   → Review Report with scoring matrix and recommendation
   │
   ▼
CTO — Final approval or rejection
   → CTO_APPROVAL.md with rationale
```

### Enforcement Rules
1. **Implementer may only start after an approved CTO plan exists.** No implementation without a written plan and acceptance criteria.
2. **Reviewer may only review after** the Implementer has delivered code changes, test results, *and* an implementation report. Incomplete submissions are returned to the Implementer.
3. **CTO may only give final approval after** receiving the Reviewer's report. The Reviewer's recommendation is the primary input to that decision.

### Task Boundary Rules (new — prevents conflation of separate tasks)
4. **Exact TASK_ID matching required.** When receiving implementation instructions for a task, the Implementer and Reviewer must verify the exact `TASK_<YYYYMMDD>_<NNN>` identifier against the directory name under `docs/development/reports/`. Substring matching, fuzzy matching, or inference from plan content is **prohibited**. If there is any doubt whether an existing completed task directory matches the requested TASK_ID, the agent must flag it to the CTO rather than proceeding.
5. **No cross-task assumption of completion.** An agent must never assume that work described in a different TASK's artifacts (even from the same user session) fulfills requirements for their current TASK. Each TASK's deliverables must be verified independently against the accepted criteria in its own `CTO_PLAN.md`. If an agent encounters ambiguity or suspects task conflation, they must stop and return to the CTO rather than proceeding on assumed authority.
6. **CTO must not execute Post-G4 duties.** After writing CTO_APPROVAL.md at G4, the CTO does NOT update PROJECT_STATUS.md, CHANGELOG.md, or send PM_CLOSED notifications. Those are PM responsibilities exclusively. If a session ends without a PM performing post-G4 completion, flag to the user — do not absorb the work yourself.

### Four Approval Gates

| Gate | Transition | Authority | Decision Type |
|------|-----------|-----------|---------------|
| **G1** | Planning → Implementation | User approves CTO's plan | Approve / Request revision |
| **G2** | Implementation → Review | Implementer self-declares complete + CTO confirms | Complete? |
| **G3** | Review → Approval | Reviewer recommends pass/fail | Passes? |
| **G4** | Approval → Complete | CTO final decision | Approve / Reject |
| **G5** | Complete → Closed | PM (Post-G4 admin) | PM completes: status update, changelog, PM_CLOSED notification |

See `protocols/` for detailed gate definitions, rejection handling, and escalation paths.

---

## 5. Task Management

### Task Directory Structure

Every task gets a dedicated directory:

```
docs/development/reports/TASK_<YYYYMMDD>_<NNN>/
├── CTO_PLAN.md              # Architecture analysis + plan (CTO produces)
├── IMPLEMENTATION_REPORT.md  # Changes, tests, decisions (Implementer produces)
├── REVIEW_REPORT.md          # Findings and recommendation (produced by Reviewer)
└── CTO_APPROVAL.md           # Final approve/reject with rationale (CTO produces)
```

### Naming Convention

- Format: `TASK_<YYYYMMDD>_<NNN>` where NNN increments per day starting at 001
- The CTO exclusively owns task creation and numbering
- Example: `TASK_20260729_001` (first task on July 29, 2026)

### Task Ownership Rules

1. Only the CTO may declare that work is a continuation of an existing TASK
2. A task is "complete" once its `CTO_APPROVAL.md` is written
3. The Reviewer always scopes reviews to exactly one TASK directory
4. Work is not merged across tasks unless explicitly authorized by the CTO

---

## 6. Protocol Hierarchy

Protocols exist in two layers:

```
~/.openclaw/protocols/*.md     ← Global standards (authoritative source of truth)
    ↑                           DS-EO defines these as source of truth
                               Installation deploys them to both global and per-project locations
                               ↓
<project>/docs/development/protocols/*.md  ← Project-level adaptations (optional)
```

The `ds-eo-openclaw/protocols/` directory contains the authoritative protocol definitions. `ds-eo-openclaw/docs/development/protocols/` is a workspace mirror for convenient access during development. Neither should diverge from the package source.

### Core Protocols

| Protocol | Category | Description |
|----------|----------|-------------|
| `approval_protocol.md` | Governance | Gate definitions, rejection handling, escalation paths |
| `communication_protocol.md` | Communication | Message formats and conventions for agent-to-agent messaging |
| `completion_protocol.md` | Workflow | Per-role completion checklists (Implementer, Reviewer, CTO) |
| `delegation_protocol.md` | Workflow | Task creation, assignment, and scope containment |
| `handoff_protocol.md` | Workflow | Phase transition requirements and artifact verification |
| `review_protocol.md` | Governance | Review criteria, scoring rubric (4 dimensions), recommendation thresholds |
| `release_management_protocol.md` | Workflow | Post-G4 closure, documentation sync, repository lifecycle coordination |
| `GATE_AUTHORITY_MATRIX.md` | Governance | Single source of truth for gate governance decisions |

---

## 7. Architecture Preservation Rules

- No unauthorized refactoring of existing package files without CTO approval
- No feature additions beyond the approved plan scope
- All architectural changes require a formal CTO proposal **and** user approval
- The Reviewer must verify specification compliance before any implementation is considered complete
- If the Implementer hits ambiguity, **stop and return to the CTO** — do not make architectural decisions independently

---

## 8. Development Directory Structure (Canonical)

```
ds-eo-openclaw/
├── AGENTS.md                    ← This file (workspace governance)
├── ds_eo_manifest.yaml          ← Package manifest (source of truth)
│
├── agents/                      ← Role definitions (portable prompts)
├── protocols/                   ← Engineering protocols (core rules)
├── templates/                   ← Document templates
├── config-templates/            ← Reference configurations
├── scripts/                     ← Installation helpers
├── tests/                       ← Verification and compliance tests
├── examples/                    ← Usage examples
├── docs/
│   ├── reports/                 ← Task history
│   │   └── TASK_<YYYYMMDD>_<NNN>/  ← One dir per task
│   ├── development/
│   │   └── protocols/           ← Workspace mirror of package protocols
│   ├── COMPATIBILITY.md
│   ├── CONTRIBUTING.md
│   └── MIGRATION_GUIDE.md
├── README.md
├── ARCHITECTURE.md
├── INSTALLATION.md
└── CHANGELOG.md
```

---

## 9. Universal Project Rules

- Read AGENTS.md before starting work (this file)
- Read the CTO's plan and acceptance criteria before implementing
- Follow the architecture — do not deviate without CTO approval
- Do not create unnecessary files
- Do not change unrelated modules
- Implement one specification at a time
- Add tests for all new functionality
- Update documentation to reflect changes
- Explain design decisions in reports and commit messages

---

*DS-EO OpenClaw Edition v0.1 — Engineering Organization Layer*

## 10. Gate Enforcement Rules (NEW)

These rules override all other directives. If a gate prerequisite is not met, the agent MUST NOT proceed regardless of any other instruction or context.

- **Rule 7: Phase Entry Gate Verification.** Before starting any phase, verify ALL required artifacts from prior phases exist on disk. Use `ls <task_dir>/<artifact>` to confirm each one. If any artifact is missing, halt immediately — do not infer completion, do not proceed, do not perform another agent's work.
- **Rule 8: Artifact-Based Phase Completion Only.** The only valid evidence that a phase completed is the existence of its required artifact file(s) on disk. Chat messages, code changes, test results, or verbal claims are NOT valid evidence of phase completion.
- **Rule 9: No Cross-Agent Duty Substitution.** Each agent produces only its designated artifacts. Never write another agent's files (e.g., Reviewer must not write CTO_APPROVAL.md; PM must not write REVIEW_REPORT.md). If you encounter missing artifacts, block and notify the user — do not fill them in yourself.
- **Rule 10: TASK_COMPLETION_AUDIT.md Is Authoritative.** Every task directory must contain this file. Its gate status is the source of truth for whether a task has completed all gates. Post-G4 work is prohibited if any prior gate shows "NOT EXECUTED".

---

## 11. Session Boundary Enforcement (NEW — prevents single-session role conflation)

These rules address the risk identified in TASK_DS_EO_025 where a single agent session
performed duties across Reviewer, CTO, and PM roles simultaneously. They add explicit
session-boundary checks to prevent cross-role contamination.

### 11a. G3 Pre-Check: Independent Review Verification

Before the CTO accepts handoff from Phase 3 (Review), the CTO MUST verify that
REVIEW_REPORT.md was produced by a **different agent** than the one issuing G4 approval.

**Verification procedure:**
1. Read `REVIEW_REPORT.md` and extract the `Reviewer`/`produced by` metadata field.
2. Compare the reviewer's model identity to the CTO's model identity.
3. If they match (or if no reviewer identity is recorded), **block G3 handoff** and
   re-dispatch the task to the Reviewer (`ollama/laguna-xs-2.1:q4_K_M` or equivalent).

**Prohibited:** CTO writing its own REVIEW_REPORT.md. The review must be truly independent.
A self-authored review is an automatic G3 failure — the implementation must return to
the Reviewer for a genuine third-party assessment.

### 11b. Post-G4 Session Isolation

After Gate G4 approval is issued, G5 (PM) duties MUST occur in a **separate session or be
explicitly dispatched** — they cannot be absorbed by the approving session.

**Enforcement:**
- If the same session that wrote CTO_APPROVAL.md also writes PM_CLOSED.md, this is a
  Rule 9 violation (see Section 10).
- The CTO may flag to the user that Post-G4 duties remain pending, but must **not**
  execute them itself. The user or a separate PM session should complete them.

### 11c. Gate State Machine — Hard Stops

The following states are hard stops that agents MUST enforce at runtime:

| State | Blocked Action | Rationale |
|-------|---------------|-----------|
| No REVIEW_REPORT.md exists | G3 → CTO handoff blocked | No independent review to evaluate |
| Same agent wrote REVIEW_REPORT.md and CTO_APPROVAL.md | G4 approval invalid | Self-graded; violates Rule 9 |
| User said "process"/"continue" without explicit task reference | Do NOT interpret as multi-role directive | User intent is ambiguous — stop and ask |

### 11d. Ambiguous User Input Guard

When a user message is ambiguous (e.g., "process", "go ahead", "do it"), the agent
MUST **not** assume it authorizes crossing gate boundaries or role lines. The agent
should:
1. Stop at its own gate boundary
2. Report what state it's in and what artifacts are complete
3. Ask for clarification if proceeding to the next gate is needed

**Never** interpret "process" as "complete everything through G5 in this session."

### 11e. Artifact Author Tracking (Required Metadata)

Every agent-produced artifact MUST include its author identity:

```markdown
---
produced_by: <agent_model_identity>
session_id: <openclaw_session_id>
produced_at: <ISO timestamp>
role: <CTO | Implementer | Reviewer | PM | User>
task_id: <TASK_XXXXX>
gate: <G1 | G2 | G3 | G4 | G5>
---
```

- Artifacts missing this metadata should be flagged as suspicious.
- When two artifacts in the same task share the same `produced_by` for roles that
  should be distinct (e.g., Reviewer and CTO), flag the conflation to the user.

---
