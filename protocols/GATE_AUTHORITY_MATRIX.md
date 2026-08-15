# Gate Authority Matrix

**Version**: 1.2
**Updates**: Added lock model, expanded intake rules per `task_intake_protocol.md`  
**Status**: Active  
**Scope**: All OpenClaw workspaces using DS-EO  

---

## Purpose

Single source of truth for gate ownership, required artifacts, approval authority, and transition conditions across all four development gates (G1–G4). Replaces scattered gate definitions in `approval_protocol.md`, `completion_protocol.md`, and `handoff_protocol.md`. Protocols continue to exist for deep detail but reference this matrix.

---

## Gate Ownership Table

| Gate | Phase From → To | Who Owns the Gate | Decision Authority | Required Artifacts | Transition Conditions |
|------|-----------------|-------------------|-------------------|-------------------|---------------------|
| G1 | Planning → Implementation | User (CTO proposes) | User: Approve / Request revision | `CTO_PLAN.md` with acceptance criteria, spec ref, risk analysis | User says "APPROVE" or "REQUEST_CHANGES(reason)" |
| G2 | Implementation → Review | Implementer + CTO confirms | Implementer declares complete; CTO confirms artifacts present | All items on **G2 Gate Checklist** verified (see below) | G2 checklist fully satisfied |
| G3 | Review → Approval | Reviewer (recommends) → CTO (confirms) | Reviewer recommends APPROVE/REQUEST_CHANGES based on rubric | `REVIEW_REPORT.md` with scoring matrix, spec compliance, regression analysis; all artifacts carry required metadata | Scoring ≥ threshold per `review_protocol.md`; all dimensions checked |
| G4 | Approval → Complete | CTO (final decision) | CTO: Approve / Reject based on Reviewer findings + own assessment | All artifacts present; metadata verified; tool-policy compliance confirmed | CTO says "APPROVE" or "REJECT(reason)" |

---

## Artifact Ownership Summary

| Artifact | Producer | Tool Capability Required | Behavioral Boundary |
|----------|----------|-------------------------|---------------------|
| `CTO_PLAN.md` | CTO | write (task dir, via behavioral rules) | Only in task dirs; no source code changes |
| `IMPLEMENTATION_REPORT.md` | Implementer | write (full FS via group:fs) | As scoped in approved plan only |
| `REVIEW_REPORT.md` | Reviewer | write (task dir, newly granted) | Only this file in the current task directory |
| `CTO_APPROVAL.md` | CTO | write (task dir, via behavioral rules) | Only in task dirs; no source code changes |
| `PROJECT_STATUS.md` | PM | write (designated paths) | Workspace root only |
| `CHANGELOG.md` | PM | write (designated paths) | Workspace root only |

---

## G2 Gate Checklist (Unified)

This checklist is the authoritative source for Gate G2 prerequisites. Both `completion_protocol.md` and `handoff_protocol.md` reference this list — do not define parallel variants.

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

---

## Related Protocols

- `approval_protocol.md` — Detailed gate rules, decision criteria, rejection handling, escalation paths
- `completion_protocol.md` — Per-role completion checklists; references G2 Gate Checklist above
- `handoff_protocol.md` — Phase transition requirements; references G2 Gate Checklist for Transition 2
- `communication_protocol.md` — Message formats for gate transitions

---

## Zeroth Gate (G0) — Intake Handoff

### G0 Ownership Model — Request-Path-Based, Not Role-Based

**V1.1 correction**: G0 intake ownership is determined by **which agent receives the initial customer request**, not by a fixed role assignment. This replaces the previous "PM-only" model with a cleaner, more direct rule:

| Entry path | Who performs G0 intake | Artifacts produced |
|-----------|----------------------|-------------------|
| User → PM (secretary/intake) | **PM** creates task folder + `TASK_REQUEST.md` | `TASK_REQUEST.md`, task directory scaffold, user notification about adding supporting materials |
| User → CTO directly | **CTO** creates task folder + `TASK_REQUEST.md` | `TASK_REQUEST.md`, task directory scaffold |

**`TASK_REQUEST.md` is an intake artifact, not a PM-exclusive artifact.** It records the user's requirements verbatim regardless of which agent captured them. The distinction is:
- When PM handles G0: the workflow includes the secretary interaction (PM asks user about specs/docs, tells them they may add materials to the folder)
- When CTO handles G0 directly: the same artifact is produced, just without the intermediate secretary step

### G0 Required Artifacts

Regardless of who produces it, every G0 must produce:
1. **Task directory** — `docs/development/reports/TASK_<YYYYMMDD>_<NNN>/` (ID assigned by whoever creates it)
2. **`TASK_REQUEST.md`** — verbatim user request, captured requirements, any attached materials the user provided or adds later
3. **(If through PM)** — Notification to the user that they may add specifications, documents, examples, datasets, references, or other supporting materials to the task folder

### G0 Enforcement Rules

1. **Whoever receives the initial customer request owns G0 intake.** They create the task directory and write `TASK_REQUEST.md`. No agent may proceed past G0 without these artifacts existing in the task directory.
2. **`TASK_REQUEST.md` must contain the verbatim user request** plus any requirements gathered during intake (by PM) or confirmed with the user (by CTO in a direct path).
3. **The receiving agent must not perform CTO planning work during G0.** Whether PM or CTO handles intake, the rule is: capture requirements → create scaffold → STOP at G0. Technical analysis and architectural planning happen only in `CTO_PLAN.md` produced after G0 completion.
4. **PM does NOT plan, analyze architecture, or design solutions** during intake — this restriction applies identically whether PM or CTO produces the G0 artifacts.
5. **If an agent writes `CTO_PLAN.md` instead of `TASK_REQUEST.md`, that is a process violation.** Document in `BOUNDARY_VIOLATION.md`. The correct intake artifact is `TASK_REQUEST.md`; technical planning belongs in `CTO_PLAN.md` produced later by the CTO after G0 completion.
6. **Cross-path consistency:** It does not matter which path was used — what matters is that `TASK_REQUEST.md` exists and contains an accurate record of user requirements before any phase beyond G0 begins. The CTO verifies this before writing `CTO_PLAN.md`; if it's missing, the agent must halt and produce it (or request it from whoever should have).
