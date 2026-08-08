# Gate Authority Matrix

**Version**: 1.0  
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

## Zeroth Gate (G0) — Intake Handoff (NEW — TASK_DS_EO_030 fix)

| Gate | Phase From → To | Who Owns the Gate | Decision Authority | Required Artifacts | Transition Conditions |
|------|-----------------|-------------------|-------------------|-------------------|---------------------|
| G0 | User Request → Ready for CTO | PM (admin only) | PM creates workspace, then STOP. **PM does NOT plan, analyze architecture, or design solutions.** | `TASK_REQUEST.md` (verbatim), `MANIFEST.md`, task directory structure | PM completes intake per delegation_protocol.md §5.0 and outputs READY_FOR_CTO status. IMMEDIATE STOP after this point. |

### G0 Enforcement Rules
1. **PM may create workspace scaffolding only** — directories, verbatim request preservation, file organization. No technical planning.
2. **CTO creates the authoritative task directory and ID** per delegation_protocol.md §Step 1. (Note: TaskIntakeManager creates scaffolding; CTO owns the actual task artifact.)
3. **PM must not write `CTO_PLAN.md` under any circumstances** — this is CTO-exclusive.
4. **If PM writes `CTO_PLAN.md`, this is a process violation** that must be documented in `BOUNDARY_VIOLATION.md` and the CTO must re-do the plan independently.

